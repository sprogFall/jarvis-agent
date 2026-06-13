

from langchain_core.messages import HumanMessage, SystemMessage
from core import config
from langchain_openai import ChatOpenAI
from loguru import logger


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


    def _build_system_prompt(self) -> str:
        """
        构建系统提示
        """
        from textwrap import dedent
        return dedent("""
        你是一个专业的AI助手，能够使用多种工具来帮助用户解决问题
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
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question)
            ]
            aiMessage = self.model.invoke(messages)
            return aiMessage.content
        except Exception as e:
            raise e

