"""
飞书机器人核心模块

职责：
1. 通过 lark-channel-sdk 的 FeishuChannel 建立与飞书的双向通道（WebSocket 长连接）
2. 收到 @机器人 / 私聊消息后，复用现有 ai_chat_service 进行 AI 对话
3. 用 channel.stream() 实现流式回复（实时更新飞书卡片）
4. 会话隔离：session_id = "feishu:{chat_id}"，复用 Redis Checkpoint 实现多轮对话
5. 复用 ChatHistoryService 将对话历史持久化到 MySQL（Web 端可见）

设计原则（与 feishu-cli.md 一致）：
- 交互层交给官方 Channel SDK，不手写事件解析/去重/长连接
- Agent 对话逻辑零改动，直接复用 ai_chat_service
- 飞书层只负责"收消息 → 调 Agent → 发回答"，不碰切片/向量化/检索
"""
import asyncio

# lark_channel 的 ws/client.py 在模块导入时通过 asyncio.get_event_loop() 捕获了
# uvicorn 正在运行的事件循环。后续 start() 调用 run_until_complete 时会失败。
# 修复：导入后立即用新的 clean event loop 替换模块级 loop 变量，
# 让 WSClient 在后台线程中运行自己的事件循环，不与 uvicorn 冲突。
import lark_channel.ws.client as _ws_client  # noqa: E402
_ws_client.loop = asyncio.new_event_loop()

from lark_channel import InboundMessage,FeishuChannel, PolicyConfig  # noqa: E402
from loguru import logger

from core.config import settings


class FeishuBot:
    """
    飞书机器人单例。

    生命周期：
        bot = FeishuBot()
        await bot.start()   # 在 FastAPI lifespan 中调用，后台启动长连接
        ...
        await bot.stop()    # 服务关闭时调用
    """

    def __init__(self):
        self._channel = None
        self._started = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self):
        """
        启动飞书机器人：初始化 FeishuChannel、注册事件处理、后台建立长连接。
        在 FastAPI lifespan 的启动阶段调用。
        """
        if self._started:
            logger.warning("飞书机器人已在运行，跳过重复启动")
            return

        # 构造 PolicyConfig：群聊需 @机器人（默认），可选群白名单
        policy_kwargs = {
            "require_mention": True,   # 群聊必须 @机器人才响应，避免话痨
            "respond_to_mention_all": False,
        }

        self._channel = FeishuChannel(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            domain=settings.feishu_domain,
            policy=PolicyConfig(**policy_kwargs),
        )

        # 注册消息事件处理器
        self._channel.on("message", self._on_message)

        # 后台启动长连接（不阻塞 FastAPI 主循环）
        await self._channel.start_background(timeout=30)
        self._started = True
        logger.info("飞书机器人长连接已启动，等待消息…")

    async def stop(self):
        """停止飞书机器人，关闭长连接。"""
        if self._channel and self._started:
            await self._channel.disconnect()
            self._started = False
            logger.info("飞书机器人已停止")

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    async def _on_message(self, msg: InboundMessage):
        """
        收到飞书消息的统一入口。

        msg 为 lark_channel.InboundMessage，SDK 已完成：
        - 消息归一化（content_text 为纯文本）
        - @机器人 检测（群聊 require_mention=True 时仅 @机器人 才回调）
        - 消息去重

        此处只做：提取文本 → 复用 Agent 对话 → 流式回复 → 持久化
        """
        try:
            # 只处理文本类消息
            raw_type = getattr(msg, "raw_content_type", "")
            if raw_type not in ("text", "post", ""):
                await self._channel.send(
                    msg.chat_id,
                    {"text": "暂仅支持文本消息，请发送文字与我对话。"},
                    {"reply_to": msg.message_id},
                )
                return

            question = (msg.content_text or "").strip()
            if not question:
                return

            chat_id = msg.chat_id
            chat_type = getattr(msg, "chat_type", "group")
            sender_name = getattr(msg, "sender_name", None) or "用户"

            logger.info(
                f"飞书消息 chat_id={chat_id} chat_type={chat_type} "
                f"sender={sender_name} question={question[:80]}"
            )

            # 会话标识：同一群聊/私聊共用一个 Agent 会话，天然多轮
            session_id = f"feishu:{chat_id}"

            # 复用现有 Agent 流式对话，并通过飞书流式卡片实时输出
            full_answer = await self._stream_reply(msg, question, session_id)


        except Exception as e:
            logger.exception(f"处理飞书消息失败: {e}")
            try:
                await self._channel.send(
                    msg.chat_id,
                    {"text": f"处理消息时出错：{e}"},
                )
            except Exception as e:
                logger.error(f"发送错误消息失败: {e}")
                pass

    # ------------------------------------------------------------------
    # 流式回复
    # ------------------------------------------------------------------

    async def _stream_reply(self, msg, question: str, session_id: str) -> str:
        """
        用 channel.stream() 流式输出 Agent 回答到飞书卡片。
        流式失败时降级为非流式文本回复。

        :return: 完整的 AI 回答文本（用于持久化）
        """
        # 复用现有 ai_chat_service 单例（与 Web 端共享 Agent + Redis Checkpoint）
        from api.chat import ai_chat_service

        collected: list[str] = []

        async def producer(stream):
            """流式生产者：遍历 Agent 的流式输出，逐块追加到飞书卡片"""
            async for chunk in ai_chat_service.stream_chat(question, session_id):
                text = chunk.get("content", "")
                if text:
                    collected.append(text)
                    await stream.append(text)

        try:
            await self._channel.stream(
                msg.chat_id,
                {"markdown": producer},
                {"reply_to": msg.message_id},
            )
            return "".join(collected)
        except Exception as e:
            logger.warning(f"飞书流式回复失败，降级为非流式: {e}")
            # 降级：直接用非流式 chat 拿完整回答
            try:
                answer = await ai_chat_service.chat(question, session_id)
                await self._channel.send(
                    msg.chat_id,
                    {"markdown": answer},
                    {"reply_to": msg.message_id},
                )
                return answer
            except Exception as e2:
                logger.error(f"非流式回复也失败: {e2}")
                await self._channel.send(
                    msg.chat_id,
                    {"text": f"回答失败：{e2}"},
                )
                return ""


# 模块级单例，供 main.py lifespan 使用
feishu_bot = FeishuBot()
