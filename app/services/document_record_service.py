
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from model.document import Document


class DocumentRecordService:
    """
    文档解析/上传记录入数据库服务
    """
    @staticmethod
    def save_or_update_document(db: Session, doc_name: str, doc_path: str, doc_type: str, doc_hash: str,
                      doc_source: str, chunk_count: int, status: str = "active") -> Document:
        """
        保存或更新文档信息
        :param db: 数据库会话
        :param doc_name: 文档名
        :param doc_path: 文档路径
        :param doc_type: 文档类型
        :param doc_hash: 文档内容hash
        :param doc_source: 文档来源
        :param chunk_count: 分片数
        :param status: 状态
        :return: 文档信息
        """
        document = Document(
            doc_name=doc_name,
            doc_hash=doc_hash,
            doc_path=doc_path,
            doc_type=doc_type,
            doc_source=doc_source,
            chunk_count=chunk_count,
            status=status,
        )
        existing = db.query(Document).filter(Document.doc_name == document.doc_name).first()
        if existing:
            document.id = existing.id
            document.version = existing.version + 1 if existing.version else 1
            db.merge(document)
            db.flush()
        else:
            db.add(document)
            db.flush()
        return document

    @staticmethod
    def get_by_name_like(db: Session, doc_name: str) -> Sequence[Document]:
        """
        根据文档名称查询文档列表
        :param db: 数据库会话
        :param doc_name: 文档名称(可选, 模糊搜索)
        :return: 文档列表
        """
        if doc_name:
            stmt = select(Document).where(Document.doc_name.like(f"%{doc_name}%"))
            return db.execute(stmt).scalars().all()
        else:
            return db.execute(select(Document)).scalars().all()

    @staticmethod
    def get_by_name(db: Session, doc_name: str) -> Document:
        """
        根据文档名称，精准匹配文档数据
        :param db: 数据库会话
        :param doc_name: 文档名
        """
        return db.execute(select(Document).where(Document.doc_name == doc_name)).scalars().first()


    @staticmethod
    def delete_by_id(db: Session, doc_id: int) -> bool:
        """
        根据ID删除文档
        :param db: 数据库会话
        :param doc_id: 文档ID
        :return: 是否删除成功
        """
        try:
            db.query(Document).filter(Document.id == doc_id).delete()
            db.commit()
            return True
        except Exception as e:
            print(e)
            return False
