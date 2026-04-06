from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import TrainingMode

if TYPE_CHECKING:
    from app.models.interview import Attempt



class TrainingRecommendation(SQLModel, table=True):
    __tablename__ = "training_recommendations"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", index=True)

    training_type: TrainingMode
    priority: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    attempt: Optional["Attempt"] = Relationship(back_populates="recommendations")




class TrainingProgress(SQLModel, table=True):
    __tablename__ = "training_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", unique=True)

    current_priority: int = 1
    completed: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    attempt: Optional["Attempt"] = Relationship(back_populates="progress")


class TrainingAttempt(SQLModel, table=True):
    __tablename__ = "training_attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", index=True)

    training_type: TrainingMode
    transcript: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    attempt: Optional["Attempt"] = Relationship(back_populates="training_attempts")
    analysis: Optional["TrainingAnalysis"] = Relationship(back_populates="training_attempt")



class TrainingAnalysis(SQLModel, table=True):
    __tablename__ = "training_analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    training_attempt_id: int = Field(
        foreign_key="training_attempts.id", unique=True
    )

    score: int
    passed: bool
    feedback: str
    raw_analysis_json: dict = Field(default_factory=dict, sa_type=JSON)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    training_attempt: Optional["TrainingAttempt"] = Relationship(back_populates="analysis")

