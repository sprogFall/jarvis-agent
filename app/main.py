from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import api_router
from api.chat import router as chat_router
from api.file import router as file_router
from core.config import settings
from services.vector_store_manager import vector_store_manager

app = FastAPI(title=settings.PROJECT_NAME)

# 配置 CORS 中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境建议指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(file_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}

