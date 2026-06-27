"""
    聊天记录管理接口
    提供会话管理、历史消息查看、重启会话等功能
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from db.session import get_session
from services.chat_history_service import ChatHistoryService


router = APIRouter()


@router.post("/sessions")
def create_session(db: Session = Depends(get_session)):
    """
    创建新会话
    """
    try:
        session = ChatHistoryService.create_session(db)
        logger.info(f"创建新会话: {session.session_id}")
        return {
            "code": 200,
            "message": "success",
            "data": {
                "session_id": session.session_id,
                "title": session.title,
                "status": session.status,
                "create_time": session.create_time.isoformat() if session.create_time else None
            }
        }
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_session)):
    """
    获取会话列表
    """
    try:
        sessions = ChatHistoryService.get_sessions(db)
        return {
            "code": 200,
            "message": "success",
            "data": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "status": s.status,
                    "create_time": s.create_time.isoformat() if s.create_time else None,
                    "update_time": s.update_time.isoformat() if s.update_time else None
                }
                for s in sessions
            ]
        }
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_session)):
    """
    获取某会话的消息列表
    """
    try:
        session = ChatHistoryService.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = ChatHistoryService.get_messages(db, session_id)
        return {
            "code": 200,
            "message": "success",
            "data": {
                "session_id": session_id,
                "title": session.title,
                "status": session.status,
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "create_time": m.create_time.isoformat() if m.create_time else None
                    }
                    for m in messages
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_session)):
    """
    删除会话及其所有消息
    """
    try:
        success = ChatHistoryService.delete_session(db, session_id)
        if not success:
            raise HTTPException(status_code=404, detail="会话不存在或删除失败")

        logger.info(f"删除会话: {session_id}")
        return {
            "code": 200,
            "message": "success",
            "data": {"deleted": True}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/restart")
def restart_session(session_id: str, db: Session = Depends(get_session)):
    """
    重启会话：关闭旧会话，创建新会话
    """
    try:
        # 关闭旧会话
        old_session = ChatHistoryService.get_session(db, session_id)
        if old_session:
            ChatHistoryService.close_session(db, old_session.session_id)
            logger.info(f"关闭旧会话: {session_id}")

        # 创建新会话
        new_session = ChatHistoryService.create_session(db)
        logger.info(f"重启会话，新会话ID: {new_session.session_id}")

        return {
            "code": 200,
            "message": "success",
            "data": {
                "old_session_id": session_id,
                "new_session_id": new_session.session_id,
                "title": new_session.title,
                "status": new_session.status,
                "create_time": new_session.create_time.isoformat() if new_session.create_time else None
            }
        }
    except Exception as e:
        logger.error(f"重启会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
