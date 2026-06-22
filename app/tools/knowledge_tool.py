"""知识库检索工具 - 从向量数据库中检索相关信息"""

from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
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
        logger.info(f"知识检索工具被调用, query='{query}'")
        vector_store = vector_store_manager.get_vector_store()
        docs = vector_store.similarity_search(query)
        if not docs:
            logger.info(f"未找到相关知识, query='{query}'")
            return "未找到相关知识", []
        content = format_docs(docs)
        logger.info(f"知识检索成功，检索到{len(docs)}个相关文档，结果: {content}")
        return content, docs
    except Exception as e:
        raise e


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
