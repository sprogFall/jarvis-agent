

from typing import Any, AsyncGenerator, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis
from core import config
from langchain_openai import ChatOpenAI
from loguru import logger
from tools import DEFAULT_LOCAL_AGENT_TOOLS


class AIChatService:
    def __init__(self, streaming: bool = True):
        """
        初始化AI聊天服务
        :param streaming: 是否启用流式返回
        """
        self.model_name = config.settings.ai_model
        self.streaming = streaming
        self.system_prompt = self._build_system_prompt()
        # 构建模型
        self.model = ChatOpenAI(
            model=self.model_name,
            api_key=config.settings.ai_api_key,
            temperature=config.settings.ai_temperature,
            streaming=self.streaming,
            base_url=config.settings.ai_base_url
        )
        # 默认工具
        self.tools = list(DEFAULT_LOCAL_AGENT_TOOLS)
        # agent初始化状态
        self._agent_initialized = False

        self.agent = None

        self.checkpointer = None



    def _build_system_prompt(self) -> str:
        """
        构建系统提示
        """
        from textwrap import dedent
        return dedent("""
        你是一个专业的AI助手，能够使用多种工具来帮助用户解决问题
            工作原则:
            1. 理解用户需求，选择合适的工具来完成任务
            2. 当需要获取实时信息或专业知识时，主动使用相关工具
            3. 基于工具返回的结果提供准确、专业的回答
            4. 如果工具无法提供足够信息，请诚实地告知用户

            回答要求:
            - 保持友好、专业的语气
            - 回答简洁明了，重点突出
            - 基于事实，不编造信息
            - 如有不确定的地方，明确说明

            请根据用户的问题，灵活使用可用工具，提供高质量的帮助。
        """).strip()


    async def chat(self, question: str, session_id: str) -> str:
        """
        非流式聊天
        :param question: 用户问题
        :param session_id: 会话ID

        :return: AI助手回答
        """
        try:
            logger.info(f"会话{session_id}, 收到非流式对话请求, 用户问题:{question}")
            await self._initialize_agent()
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question)
            ]
            # 配置 thread_id（用于会话持久化）
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }
            input = {"messages": messages}
            response = await self.agent.ainvoke(
                input=input,
                config=config_dict
            )
            aiMessage = response.get("messages", "")
            if aiMessage:
                last_message = aiMessage[-1]
                answer = last_message.content if hasattr(last_message, "content") else str(last_message)
                return answer
            logger.warning(f"会话{session_id}, AI助手未返回有效信息")
            return ""
        except Exception as e:
            raise e



    async def stream_chat(
        self, 
        question: str, 
        session_id: str
        ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天
        :param question: 用户问题
        :param session_id: 会话ID
        """
        logger.info(f"会话{session_id}, 收到流式对话请求, 用户问题:{question}")
        try:
            await self._initialize_agent()
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question)
            ]
            input = {"messages": messages}
            # 配置 thread_id（用于会话持久化）
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }
            async for token, metadata in self.agent.astream(
                input=input, 
                config=config_dict,
                stream_mode="messages"
            ):
                message_type = type(token).__name__
                if message_type in ("AIMessage", "AIMessageChunk"):
                    content_blocks = getattr(token, 'content_blocks', None)
                    if content_blocks and isinstance(content_blocks, list):
                        for block in content_blocks:
                            text_content = block.get("text", "")
                            yield {
                                "session_id": session_id,
                                "content": text_content,
                                "done": False
                            }
            # 结束
            yield {
                "session_id": session_id,
                "content": "",
                "done": True
            }
        except Exception as e:
            raise e       

    async def _initialize_agent(self):
        """异步初始化Agent"""
        if self._agent_initialized:
            return
        redis_client = Redis.from_url(config.settings.redis_conn_string)
        self.checkpointer = AsyncRedisSaver(
            redis_client=redis_client,
            ttl={"default_ttl": 10080}
        )
        await self.checkpointer.setup()
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            checkpointer=self.checkpointer
        )
        self._agent_initialized = True

        if self.tools:
            tool_names = [tool.name if hasattr(tool, "name") else str(tool) for tool in self.tools]
            logger.info(f"可用工具列表: {', '.join(tool_names)}")