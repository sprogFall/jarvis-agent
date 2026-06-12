from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import settings


app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}

