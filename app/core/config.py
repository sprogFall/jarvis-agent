from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Jarvis-Agent"
    ai_base_url: str = ""
    ai_temperature: float = 0.7
    ai_api_key: str = ""
    ai_model: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_api_base: str = ""
    # 向量维度，默认1536
    embedding_dimension: int = 1536

    # 分片最大字数，默认800
    chunk_max_size: int = 800
    # 分片重叠字数，默认100
    chunk_overlap: int = 100

    # OCR相关配置
    ocr_api_url: str = ""
    ocr_api_key: str = ""
    ocr_model: str = ""
    ocr_enabled: bool = True

    # Redis 连接字符串，默认为空
    redis_conn_string: str = ""
    # MySQL连接地址
    mysql_url: str = ""
    # 知识库文件上传地址
    upload_dir: str = str((BASE_DIR.parent / "uploads").resolve())
    sqlalchemy_echo: bool = True

    # 混合检索配置
    # 向量检索返回数量
    vector_search_k: int = 10
    # BM25检索返回数量
    bm25_search_k: int = 10
    # 最终返回给LLM的文档数量
    final_top_k: int = 5
    # 向量检索权重，BM25权重为 1 - vector_weight
    vector_weight: float = 0.6
    # 是否启用混合检索（False则纯向量检索）
    hybrid_search_enabled: bool = True

    # 流式响应超时（秒）：单个 chunk 之间最大等待时间
    # 设置较大的值防止模型思考时间较长时被误判超时，默认 300 秒
    stream_chunk_timeout: int = 300

    # 调试模式
    debug: bool = False

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()
