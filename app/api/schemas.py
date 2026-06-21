from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    customer_id: str = Field(..., description="进酒宝客户 ID")
    token: Optional[str] = Field(None, description="进酒宝登录 token，用于拉取客户专属价格")
    llm_provider: Optional[str] = Field(None, description="kimi 或 deepseek")


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(default="", description="用户文本消息")
    quick_reply_value: Optional[str] = Field(None, description="快捷选项 value")


class SessionResponse(BaseModel):
    session_id: str
    customer_id: str
    phase: str
    profile: dict
    handoff: Optional[dict] = None
    message_count: int
