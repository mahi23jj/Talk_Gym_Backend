from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models.auth import User
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel, Relationship


class AttemptType(str, Enum):
    normal = "normal"
    speed = "speed"
    concise = "concise"


class SenderType(str, Enum):
    user = "user"
    ai = "ai"


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=200)
    description: str
    day_unlock: int = Field(ge=1, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


