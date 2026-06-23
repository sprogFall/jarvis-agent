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

    # Redis 连接字符串，默认为空
    redis_conn_string: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()
