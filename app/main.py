from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from api.router import api_router
from api.chat import router as chat_router
from api.file import router as file_router
from api.chat_history import router as chat_history_router
from db.session import engine
from db.base import Base
from core.config import settings
# 导入所有模型，确保 create_all 能建表
from model import document, chat  # noqa: F401



@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    print("数据库创建完毕")

    # 启动飞书机器人（需在 .env 配置 FEISHU_ENABLED=true 及凭证）
    if settings.feishu_enabled and settings.feishu_app_id and settings.feishu_app_secret:
        from services.feishu.feishu_bot import feishu_bot
        try:
            await feishu_bot.start()
            logger.info("飞书机器人已启动")
        except Exception as e:
            logger.warning(f"飞书机器人启动失败（不影响主服务）: {e}")

    yield

    # 关闭飞书机器人长连接
    if settings.feishu_enabled and settings.feishu_app_id:
        from services.feishu.feishu_bot import feishu_bot
        try:
            await feishu_bot.stop()
        except Exception as e:
            logger.warning(f"飞书机器人关闭失败（不影响主服务）: {e}")
            pass

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

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
app.include_router(chat_history_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}

