"""
    对话接口
    提供基于RAG Agent 的普通对话和流式对话接口
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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
    try:
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
    except Exception as e:
        logger.error(f"会话{request.id}, 对话请求处理失败:{e}")
        return {
            "code": 500,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "errorMessage": str(e)
            }
        }

@router.post("/stream_chat")
async def stream_chat(request: ChatRequest):
    """
    流式对话接口
    """
    try:
        logger.info(f"会话{request.id}, 收到流式对话请求:{request.question}")
        async def event_generator():
            import json
            async for chunk in ai_chat_service.stream_chat(request.question, request.id):
                logger.info(f"本次流式响应：{chunk}")
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"会话{request.id}, 流式对话请求处理失败:{e}")
        return {
            "code": 500,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "errorMessage": str(e)
            }
        }

    
