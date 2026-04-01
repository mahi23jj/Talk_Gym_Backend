from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


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


class Recording(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    audio_url: str = Field(max_length=500)
    duration_seconds: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    attempt_type: AttemptType = Field(default=AttemptType.normal)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    recording_id: int = Field(foreign_key="recording.id", index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    ended_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_session_id: int = Field(foreign_key="chatsession.id", index=True)
    sender_type: SenderType
    message_text: str | None = Field(default=None)
    audio_url: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class AIAnalysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_session_id: int = Field(foreign_key="chatsession.id", unique=True, index=True)
    recording_id: int = Field(foreign_key="recording.id", unique=True, index=True)
    summary: str
    feedback: str
    tips: str
    score: int = Field(ge=0, le=100)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
