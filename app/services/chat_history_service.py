
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from model.chat import ChatSession, ChatMessage


class ChatHistoryService:
    """
    聊天记录管理服务
    """

    @staticmethod
    def create_session(db: Session, title: str = "新会话") -> ChatSession:
        """
        创建新会话
        :param db: 数据库会话
        :param title: 会话标题
        :return: ChatSession
        """
        session_id = str(uuid.uuid4())
        chat_session = ChatSession(
            session_id=session_id,
            title=title,
            status="active"
        )
        db.add(chat_session)
        db.commit()
        return chat_session

    @staticmethod
    def get_sessions(db: Session) -> List[ChatSession]:
        """
        获取所有会话列表（按更新时间倒序）
        """
        return db.query(ChatSession).order_by(ChatSession.update_time.desc()).all()

    @staticmethod
    def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
        """
        获取单个会话
        """
        return db.query(ChatSession).filter(ChatSession.session_id == session_id).first()

    @staticmethod
    def get_messages(db: Session, session_id: str) -> List[ChatMessage]:
        """
        获取某会话的所有消息（按时间正序）
        """
        return db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.create_time.asc()).all()

    @staticmethod
    def add_message(db: Session, session_id: str, role: str, content: str) -> ChatMessage:
        """
        追加消息
        """
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(message)
        return message

    @staticmethod
    def ensure_session(db: Session, session_id: str, title: str = "新会话") -> ChatSession:
        """
        确保会话存在，不存在则创建
        """
        session = ChatHistoryService.get_session(db, session_id)
        if not session:
            session = ChatSession(
                session_id=session_id,
                title=title,
                status="active"
            )
            db.add(session)
        return session

    @staticmethod
    def update_session_title(db: Session, session_id: str, title: str) -> Optional[ChatSession]:
        """
        更新会话标题
        """
        session = ChatHistoryService.get_session(db, session_id)
        if session:
            session.title = title[:100] if len(title) > 100 else title
        return session

    @staticmethod
    def close_session(db: Session, session_id: str) -> Optional[ChatSession]:
        """
        关闭会话
        """
        session = ChatHistoryService.get_session(db, session_id)
        if session:
            session.status = "closed"
        return session

    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        """
        删除会话及其所有消息
        """
        try:
            db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
            db.query(ChatSession).filter(ChatSession.session_id == session_id).delete()
            db.commit()
            return True
        except Exception:
            return False

    @staticmethod
    def get_message_count(db: Session, session_id: str) -> int:
        """
        获取会话消息数量
        """
        return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
