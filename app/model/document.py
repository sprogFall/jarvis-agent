

from sqlalchemy import Column, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class Document(Base):
    """
    知识库文档信息表
    """
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="文档ID")
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="文档名称")
    doc_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="文档哈希值")
    doc_path: Mapped[str] = mapped_column(String(255), nullable=False, comment="文档路径")
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="文档类型")
    doc_source: Mapped[str] = mapped_column(String(32), nullable=False, comment="文档来源")
    version: Mapped[int] = mapped_column(nullable=False, comment="文档版本", default=1, server_default="1")
    chunk_count: Mapped[int] = mapped_column(nullable=False, comment="分片数量")
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="文档状态")
