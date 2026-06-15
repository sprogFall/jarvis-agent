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

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()
