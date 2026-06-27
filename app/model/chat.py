
from sqlalchemy import String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChatSession(Base):
    """
    聊天会话表
    """
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="主键ID")
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="会话唯一标识(LangGraph thread_id)")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新会话", server_default="新会话", comment="会话标题")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active", comment="会话状态: active/closed")


class ChatMessage(Base):
    """
    聊天消息表
    """
    __tablename__ = "chat_message"
    __table_args__ = (
        Index("idx_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="主键ID")
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联会话ID")
    role: Mapped[str] = mapped_column(String(32), nullable=False, comment="角色: user/assistant")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
