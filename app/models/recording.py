from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.auth import User
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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    user: Mapped[Optional["User"]] = Relationship(back_populates="recordings")
    attempt: Mapped[Optional["Attempt"]] = Relationship(back_populates="recording")
