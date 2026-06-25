"""
请求数据模型
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    id: str = Field(..., description="会话ID", alias="Id")
    question: str = Field(..., description="用户问题", alias="Question")
