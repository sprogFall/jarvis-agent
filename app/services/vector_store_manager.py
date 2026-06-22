"""
向量数据库管理 封装对向量数据库的操作
目前向量数据库使用Qdrant
"""
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from loguru import logger
from core.config import settings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from typing import List

COLLECTION_NAME = "Jarvis"

class VectorStoreManager:
    """
    向量存储管理器
    """

    def __init__(self):
        """
        初始化向量存储管理器
        """
        self.vector_store = None
        self.collection_name = COLLECTION_NAME
        self._initialize_vector_store()

    def _initialize_vector_store(self):
        """ 初始化Qdrant Vector Store """
        try:
            logger.info("开始初始化Vector Store")
            client = QdrantClient(
                url=settings.qdrant_url, 
                api_key=settings.qdrant_api_key
            )
            if not client.collection_exists(self.collection_name):
                self._create_collection(client)
                
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
            return document_ids
        except Exception as e:
            logger.error(f"添加文档到向量存储中失败: {e}")
            raise

    def get_vector_store(self) -> QdrantVectorStore:
        """
        获取向量存储
        :return: 向量存储
        """
        return self.vector_store


# 全局单例向量存储管理器
vector_store_manager = VectorStoreManager()
