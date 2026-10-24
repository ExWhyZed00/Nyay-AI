"""Request / response shapes for the HTTP API."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.config import SUPPORTED_LANGUAGES


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    conversation_id: uuid.UUID | None = None
    language: str = "auto"

    @field_validator("message")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message is empty")
        return v

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"language must be one of {SUPPORTED_LANGUAGES}")
        return v


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[dict[str, Any]]
    verified: bool | None
    created_at: datetime
