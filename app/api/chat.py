"""
    对话接口
    提供基于RAG Agent 的普通对话和流式对话接口，并自动持久化消息到MySQL
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from services.ai_chat_service import AIChatService
from services.chat_history_service import ChatHistoryService
from loguru import logger
from schema.request import ChatRequest
from db.session import get_session


router = APIRouter()
ai_chat_service = AIChatService()


def _ensure_session_and_save_user_message(db: Session, session_id: str, question: str):
    """
    确保会话存在，并保存用户消息。
    如果是新会话的第一条消息，以该消息作为会话标题。
    """
    existing = ChatHistoryService.get_session(db, session_id)
    if not existing:
        # 新会话，以第一条消息摘要为标题
        title = question[:50] + ("..." if len(question) > 50 else "")
        ChatHistoryService.ensure_session(db, session_id, title=title)
    ChatHistoryService.add_message(db, session_id, "user", question)


@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_session)):
    """
    普通对话接口
    """
    try:
        logger.info(f"会话{request.id}, 收到非流式对话请求:{request.question}")

        # 确保会话存在 & 保存用户消息
        _ensure_session_and_save_user_message(db, request.id, request.question)

        answer = await ai_chat_service.chat(request.question, request.id)

        # 保存AI回答
        ChatHistoryService.add_message(db, request.id, "assistant", answer)

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
async def stream_chat(request: ChatRequest, db: Session = Depends(get_session)):
    """
    流式对话接口
    """
    try:
        logger.info(f"会话{request.id}, 收到流式对话请求:{request.question}")

        # 确保会话存在 & 保存用户消息
        _ensure_session_and_save_user_message(db, request.id, request.question)

        # 用于在流结束后保存完整回答
        collected_answer = []

        async def event_generator():
            import json
            async for chunk in ai_chat_service.stream_chat(request.question, request.id):
                # 收集完整回答
                if chunk.get("content"):
                    collected_answer.append(chunk["content"])
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # 流结束后，保存完整AI回答到数据库
            full_answer = "".join(collected_answer)
            if full_answer:
                ChatHistoryService.add_message(db, request.id, "assistant", full_answer)
                logger.info(f"本次流式响应session_id={request.id}, 完整回答：{full_answer}")

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
