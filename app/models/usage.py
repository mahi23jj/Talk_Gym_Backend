from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.auth import User


class AIUsage(SQLModel, table=True):
    __tablename__ = "ai_usage"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    usage_date: date = Field(index=True)
    ai_requests_count: int = Field(default=0, ge=0)
    voice_requests_count: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)

    user: Optional["User"] = Relationship(back_populates="recordings")
