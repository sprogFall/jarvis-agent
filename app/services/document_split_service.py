

import datetime
import uuid
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from core.config import settings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger


class DocumentSplitService:
    """
    文档分割服务，使用LangChain分割器
    """

    def __init__(self):
        """
        初始化文档分割服务
        """
        self.chunk_size = settings.chunk_max_size
        self.chunk_overlap = settings.chunk_overlap

        # markdown分割器
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            # 只按一级和二级标题分割
            headers_to_split_on=[("#", "h1"), ("##", "h2")],
            # 不去除标题
            strip_headers=False
        )

        # 递归字符分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            # 分片大小为chunk_size * 2，减少分片数量
            chunk_size=self.chunk_size * 2,
            chunk_overlap=self.chunk_overlap,
            # 使用字符串长度作为分片长度
            length_function=len,
            # 不将分隔符作为分片
            is_separator_regex=False
        )
        
        logger.info(
            f"文档分割服务初始化完成, chunk_size={self.chunk_size}, "
            f"secondary_chunk_size={self.chunk_size * 2}, "
            f"overlap={self.chunk_overlap}"
        )
    
    def split_text(self, content: str, file_path: str = "") -> List[Document]:
        """
        分割普通文档
        """
        if not content or not content.strip():
            logger.warning(f"文本文档内容为空: {file_path}")
        try:
            docs = self.text_splitter.create_documents(
                texts=[content],
                metadatas=[
                    {
                        "_source": file_path,
                        "_extension": Path(file_path).suffix,
                        "_file_name": Path(file_path).name,
                        "_create_time": datetime.datetime.now(),
                    }
                ]
            )
            self.common_doc_set(docs)
            logger.info(f"文本文档分割完成: {file_path}, 分片数量: {len(docs)}")
            return docs
        except Exception as e:
            logger.error(f"文本文档分割错误: {file_path}, 错误信息: {e}")
            raise


    def split_markdown(self, content: str, file_path: str = "") -> List[Document]:
        """
        分割Markdown文档
        """
        if not content or not content.strip():
            logger.warning(f"Markdown文档内容为空: {file_path}")
            return []
        try:
            # 1.按标题分割
            md_docs = self.markdown_splitter.split_text(content)
            # 2.按文件大小进行分割
            docs_after_split = self.text_splitter.split_documents(md_docs)
            # TODO 后续补充 3.合并太小的分片
            final_docs = docs_after_split
            # 添加文件源路径
            for doc in final_docs:
                doc.metadata["_source"] = file_path
                doc.metadata["_extension"] = Path(file_path).suffix
                doc.metadata["_file_name"] = Path(file_path).name
                doc.metadata["_create_time"] = datetime.datetime.now()
            self.common_doc_set(final_docs)
            logger.info(f"Markdown文档分割完成，{file_path}, 分片数量: {len(final_docs)}")
            return final_docs
        except Exception as e:
            logger.error(f"Markdown文档分割错误: {file_path}, 错误信息: {e}")
            raise

    def split_document(self, content: str, file_path: str = "") -> List[Document]:
        """
        智能根据文件类型分割文档
        """
        if Path(file_path).suffix == ".md":
            return self.split_markdown(content, file_path)
        else:
            return self.split_text(content, file_path)


    def common_doc_set(self, docs: List[Document]):
        """
        对文档的统一处理逻辑
        """
        for doc in docs:
            doc.metadata["_doc_id"] = uuid.uuid4()

# 创建文档分割服务实例
document_split_service = DocumentSplitService()