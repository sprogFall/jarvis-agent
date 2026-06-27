"""知识库检索工具 - 从向量数据库中检索相关信息
支持向量检索 + BM25 关键词检索的混合模式
"""

from typing import Dict, List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_classic.retrievers import EnsembleRetriever
from core.config import settings
from services.vector_store_manager import vector_store_manager
from loguru import logger


@tool(description="从知识库检索相关信息回答问题", response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """
    从知识库检索相关信息回答问题
    当用户的问题涉及专业知识、文档内容或需要参考资料时，使用此工具。
    :param query: 用户问题
    :return: 格式化后的上下文文本，原始文档列表
    """
    try:
        logger.info(f"知识检索工具被调用, query='{query}', hybrid={settings.hybrid_search_enabled}")

        if settings.hybrid_search_enabled:
            docs = _hybrid_search(query)
        else:
            docs = _vector_search(query)

        if not docs:
            logger.info(f"未找到相关知识, query='{query}'")
            return "未找到相关知识", []

        content = format_docs(docs)
        logger.info(f"知识检索成功，检索到{len(docs)}个相关文档")
        return content, docs
    except Exception as e:
        raise e


def _hybrid_search(query: str) -> List[Document]:
    """
    混合检索：向量检索 + BM25 关键词检索，通过 RRF 融合排序
    """
    bm25_retriever = vector_store_manager.get_bm25_retriever()
    if bm25_retriever is None:
        logger.warning("BM25 检索器未就绪，回退到纯向量检索")
        return _vector_search(query)

    vector_store = vector_store_manager.get_vector_store()
    vector_retriever = vector_store.as_retriever(search_kwargs={"k": settings.vector_search_k})

    # 分别执行检索
    vector_doc: List[Document] = vector_retriever.invoke(query)
    bm25_doc: List[Document] = bm25_retriever.invoke(query)

    # 给文档打来源标签
    for doc in vector_doc:
        doc.metadata["_from_source"] = "vector"
        doc.metadata["_retriever_score"] = doc.metadata.get("score", 0.0)
    

    for doc in bm25_doc:
        doc.metadata["_from_source"] = "bm25"
        doc.metadata["_retriever_score"] = doc.metadata.get("score", 0.0)

    # 手动RRF融合
    from collections import defaultdict

    doc_map: Dict[str, Document] = {}
    for doc in vector_doc + bm25_doc:
        doc_id = doc.metadata.get("id") or doc.page_content
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
            doc_map[doc_id].metadata["_retriever_source"] = []
            doc_map[doc_id].metadata["_rrf_score"] = 0
    
    # 计算RRF分数

    def _calculate_rff(docs: List[Document], weight):
        for rank, doc in enumerate(docs, 1):
            doc_id = doc.metadata.get("id") or doc.page_content
            doc_map[doc_id].metadata["_retriever_source"].append(doc.metadata.get("_from_source"))
            doc_map[doc_id].metadata["_rrf_score"] += weight * (1.0 / (60 + rank))

    # 分别计算两个检索器的rff
    bm25_weight = 1.0 - settings.vector_weight
    _calculate_rff(vector_doc, settings.vector_weight)
    _calculate_rff(bm25_doc, bm25_weight)

    # 排序并返回
    sorted_docs = sorted(
        doc_map.values(),
        key=lambda d: d.metadata["_rrf_score"],
        reverse=True
    )
    final_docs = sorted_docs[:settings.final_top_k]
    if settings.debug:
        # 调试模式打印RFF排名和来源
        for rank, doc in enumerate(final_docs, 1):
            logger.info(f"文档来源: {doc.metadata['_retriever_source']}, RRF分数: {doc.metadata['_rrf_score']:.4f}, 排名: {rank}")

    return final_docs


def _vector_search(query: str) -> List[Document]:
    """
    纯向量检索（回退方案）
    """
    vector_store = vector_store_manager.get_vector_store()
    docs = vector_store.similarity_search(query, k=settings.vector_search_k)
    return docs


def format_docs(docs: List[Document]) -> str:
    """
    格式化文档列表为字符串
    :param docs: 文档列表
    :return: 格式化后的字符串
    """
    formatted_docs = []
    for i, doc in enumerate(docs):
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        headers = []
        # 获取标题信息
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])

        # 格式化标题信息(如果存在)
        header_str = " > ".join(headers) if headers else ""
        # 构建格式化文本
        formatted = f"【参考资料{i}】"
        if header_str:
            formatted += f"\n标题: {header_str}"
        formatted += f"\n来源: {source}"
        formatted += f"\n内容: {doc.page_content}\n"
        formatted_docs.append(formatted)
    return "\n".join(formatted_docs)
