from typing import List

from langchain_core.documents import Document
from loguru import logger

from core.config import settings


class RerankService:
    """
    rerank服务
    """
    def __init__(self):
        self.api_url = settings.rerank_api_url
        self.api_key = settings.rerank_api_key
        self.model = settings.rerank_model
        self.candidate_k = settings.rerank_candidate_k

    def rerank(self, query: str, docs: List[Document], final_top_k: int) -> List[Document]:
        """
        根据用户输入进行重排序
        """
        import requests
        try:
            candidate_docs = docs[:self.candidate_k]
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            document_str_array = [doc.page_content for doc in candidate_docs]
            payload = {
                "model": self.model,
                "query": query,
                "documents": document_str_array,
                "return_documents": False,
                "top_n": final_top_k
            }
            response = requests.post(self.api_url, json=payload, headers=headers)
            if response.status_code != 200:
                # 重排序失败，回退至前k排序
                logger.warning(f"rerank失败，rerank接口异常，回退至前k排序，错误信息: {response.text}")
                return candidate_docs[:final_top_k]
            result = response.json()
            results = result.get("results", [])
            reranked: List[Document] = []
            for rerank_rank, item in enumerate(results, 1):
                idx = item["index"]
                score = item["relevance_score"]
                doc = candidate_docs[idx]
                doc.metadata["_rerank_score"] = score
                reranked.append(doc)
                if settings.debug:
                    logger.info(f"文档id:{doc.metadata.get('_doc_id')},原排序:{idx}, 分数{doc.metadata.get('_rrf_score')}; "
                                f"rerank后排序:{rerank_rank},rerank分数:{score:.4f}")
            logger.info(f"rerank完成，候选{len(document_str_array)}条，返回{len(reranked)}条")

            return reranked
        except Exception as e:
            logger.error(f"rerank失败，内部异常，回退至前k排序，错误信息: {e}")
            return docs[:final_top_k]



rerank_service = RerankService()