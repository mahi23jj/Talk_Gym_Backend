from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import AttemptStatus, TrainingMode

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.recording import Recording
    from app.models.training import TrainingAnalysis, TrainingAttempt, TrainingProgress, TrainingRecommendation


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    recording_id: int = Field(foreign_key="recordings.id", unique=True)

    transcript: str
    status: AttemptStatus = Field(default=AttemptStatus.active)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    user: Optional["User"] = Relationship(back_populates="attempts")
    recording: Optional["Recording"] = Relationship(back_populates="attempt")

    analysis: Optional["InterviewAnalysis"] = Relationship(back_populates="attempt")
    recommendations: list["TrainingRecommendation"] = Relationship(
        back_populates="attempt"
    )
    progress: Optional["TrainingProgress"] = Relationship(back_populates="attempt")
    training_attempts: list["TrainingAttempt"] = Relationship(back_populates="attempt")


class InterviewAnalysis(SQLModel, table=True):
    __tablename__ = "analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", unique=True)

    score: int
    feedback: str
    raw_analysis_json: dict = Field(default_factory=dict, sa_type=JSON)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    attempt: Optional["Attempt"] = Relationship(back_populates="analysis")
