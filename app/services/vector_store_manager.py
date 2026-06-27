"""向量数据库管理 封装对向量数据库的操作
目前向量数据库使用Qdrant，支持向量检索 + BM25 混合检索
"""
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, PayloadSchemaType, VectorParams
from loguru import logger
from core.config import settings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from typing import List, Optional
import jieba


def _chinese_tokenize(text: str) -> List[str]:
    """
    中文分词函数，用于 BM25 检索
    使用 jieba 分词，并过滤空白 token
    """
    return [t for t in jieba.lcut(text) if t.strip()]

COLLECTION_NAME = "Jarvis"

class VectorStoreManager:
    """
    向量存储管理器
    """

    def __init__(self):
        """
        初始化向量存储管理器
        """
        self.vector_store: QdrantVectorStore = None
        self.collection_name = COLLECTION_NAME
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._initialize_vector_store()
        # 初始化后构建 BM25 索引
        self._build_bm25_index()

    def _initialize_vector_store(self):
        """ 初始化Qdrant Vector Store """
        try:
            logger.info("开始初始化Vector Store")
            client = QdrantClient(
                url=settings.qdrant_url, 
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
            )
            if not client.collection_exists(self.collection_name):
                self._create_collection(client)
            else:
                self._ensure_payload_indexes(client)
                
            embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.embedding_api_key,
                openai_api_base=settings.embedding_api_base,
            )
            self.vector_store = QdrantVectorStore(
                client=client, 
                embedding=embeddings, 
                collection_name=self.collection_name
            )
            logger.info("Vector Store初始化成功")

        except Exception as e:
            logger.error(f"初始化Vector Store失败: {e}")
            raise


    def _create_collection(self, client: QdrantClient) -> None:
        """
        创建Qdrant Collection
        """
        logger.info(f"Collection '{self.collection_name}' 不存在，开始创建")
        client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                # 向量维度
                size=settings.embedding_dimension, 
                # 余弦相似度计算方式
                distance=Distance.COSINE
            )
        )
        logger.info(f"Collection '{self.collection_name}' 创建成功")
        self._ensure_payload_indexes(client)

    def _ensure_payload_indexes(self, client: QdrantClient) -> None:
        """
        确保关键字段已创建 payload 索引（用于过滤查询）
        """
        indexed_fields = ["metadata._file_name", "metadata._source"]
        for field in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD
                )
                logger.info(f"Payload 索引 '{field}' 创建/已存在")
            except Exception as e:
                logger.warning(f"创建 Payload 索引 '{field}' 时出现异常: {e}")

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        批量添加文档到向量存储中
        :param documents: 文档列表
        :return: 添加的文档ID列表
        """
        try:
            import time
            import uuid
            start_time = time.time()
            # 为每个文档生成一个唯一的ID
            document_ids = [str(uuid.uuid4()) for _ in documents]
            # 添加文档到向量存储中 (会自动调用embedding_function)
            self.vector_store.add_documents(documents, ids=document_ids)
            cost_time = time.time() - start_time
            logger.info(f"添加 {len(documents)} 个文档到向量存储中成功，耗时 {cost_time:.2f} 秒, 平均耗时 {cost_time/len(documents):.2f} 秒")
            # 刷新 BM25 索引
            self._build_bm25_index()
            return document_ids
        except Exception as e:
            logger.error(f"添加文档到向量存储中失败: {e}")
            raise

    def delete_documents_by_name(self, doc_name: str):
        """
        根据文档名称删除文档
        :param doc_name: 文档名称
        """
        try:
            logger.info(f"开始根据文档名称删除文档: {doc_name}")
            client: QdrantClient = self.vector_store.client
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="metadata._file_name",
                        match=MatchValue(value=doc_name)
                    )
                ]
            )
            client.delete(
                collection_name=self.collection_name,
                points_selector=search_filter
            )
            logger.info(f"根据文档名称删除文档成功: {doc_name}")
            # 刷新 BM25 索引
            self._build_bm25_index()
        except Exception as e:
            logger.error(f"根据文档名称删除文档失败: {e}")
            raise

    def get_bm25_retriever(self) -> Optional[BM25Retriever]:
        """获取 BM25 检索器（如果已构建）"""
        return self._bm25_retriever

    def rebuild_bm25_index(self):
        """手动重建 BM25 索引（供外部调用）"""
        self._build_bm25_index()

    def _build_bm25_index(self):
        """
        从 Qdrant 中拉取全部文档，构建/重建 BM25 索引
        """
        try:
            import time
            start_time = time.time()
            logger.info("开始构建 BM25 索引...")
            client: QdrantClient = self.vector_store.client

            all_docs: List[Document] = []
            next_offset = None

            while True:
                scroll_params = {
                    "collection_name": self.collection_name,
                    "limit": 100,
                    "with_vectors": False,
                }
                if next_offset is not None:
                    scroll_params["offset"] = next_offset

                points, next_offset = client.scroll(**scroll_params)

                for point in points:
                    payload = point.payload or {}
                    metadata = payload.get("metadata", {})
                    text = payload.get("page_content", "")
                    if text:
                        all_docs.append(Document(page_content=text, metadata=metadata))

                if next_offset is None:
                    break

            if not all_docs:
                logger.warning("Qdrant 中没有文档，跳过 BM25 索引构建")
                self._bm25_retriever = None
                return

            self._bm25_retriever = BM25Retriever.from_documents(
                all_docs,
                k=settings.bm25_search_k,
                # 使用 jieba 中文分词，替换默认的空白分词
                preprocess_func=_chinese_tokenize,
            )
            cost_time = time.time() - start_time
            logger.info(
                f"BM25 索引构建成功，共 {len(all_docs)} 个文档，耗时 {cost_time:.2f} 秒"
            )
        except Exception as e:
            logger.error(f"构建 BM25 索引失败: {e}")
            self._bm25_retriever = None

    def get_vector_store(self) -> QdrantVectorStore:
        """
        获取向量存储
        :return: 向量存储
        """
        return self.vector_store


# 全局单例向量存储管理器
vector_store_manager = VectorStoreManager()
