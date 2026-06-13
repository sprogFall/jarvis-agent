from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Jarvis-Agent"
    ai_base_url: str = ""
    ai_temperature: float = 0.7
    ai_api_key: str = ""
    ai_model: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()
