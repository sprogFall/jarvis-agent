"""
    对话接口
    提供基于RAG Agent 的普通对话和流式对话接口
"""

from fastapi import APIRouter
from services.ai_chat_service import AIChatService
from loguru import logger
from model.request import ChatRequest


router = APIRouter()
ai_chat_service = AIChatService()

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    普通对话接口
    """
    logger.info(f"会话{request.id}, 收到非流式对话请求:{request.question}")

    answer = await ai_chat_service.chat(request.question, request.id)
    response = {
        "code": 200,
        "message": "success",
        "data": {
            "success": True,
            "answer": answer,
            "errorMsg": None
        }
    }
    logger.info(f"会话{request.id}, 返回对话结果:{response}")
    return response
