from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models.auth import User
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel, Relationship

from app.models.interview import Attempt


class Recording(SQLModel, table=True):
    __tablename__ = "recordings"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)

    audio_url: str
    duration_seconds: int
    size_bytes: int
    transcription: Optional[str] = None

    user: Optional["User"] = Relationship(back_populates="recordings")
    attempt: Optional["Attempt"] = Relationship(back_populates="recording")
