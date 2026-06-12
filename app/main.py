from fastapi import FastAPI
from api.router import api_router
from api.chat import router as chat_router
from core.config import settings


app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}

