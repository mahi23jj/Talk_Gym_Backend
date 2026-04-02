from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, JSON
from sqlmodel import Field, SQLModel


class TrainingMode(str, Enum):
    delivery_training = "delivery_training"
    structure_training = "structure_training"
    behavioral_training = "behavioral_training"


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    recording_id: int | None = Field(default=None, foreign_key="recording.id", index=True)
    parent_attempt_id: int | None = Field(default=None, foreign_key="attempts.id", index=True)
    transcript: str
    training_mode: TrainingMode = Field(index=True)
    analysis_json: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    detected_issues: list[str] = Field(default_factory=list, sa_type=JSON)
    recommendations: list[str] = Field(default_factory=list, sa_type=JSON)
    is_final_attempt: bool = Field(default=False, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class InterviewAnalysis(SQLModel, table=True):
    __tablename__ = "analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", unique=True, index=True)
    raw_analysis_json: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    primary_training_mode: TrainingMode = Field(index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class TrainingFollowUp(SQLModel, table=True):
    __tablename__ = "training_followups"

    id: Optional[int] = Field(default=None, primary_key=True)
    training_mode: TrainingMode = Field(index=True)
    question_text: str = Field(max_length=255)
    difficulty_level: int = Field(ge=1, le=3, default=1)


class UserProgress(SQLModel, table=True):
    __tablename__ = "user_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    total_attempts: int = Field(default=0, ge=0)
    final_attempts: int = Field(default=0, ge=0)
    delivery_training_count: int = Field(default=0, ge=0)
    structure_training_count: int = Field(default=0, ge=0)
    behavioral_training_count: int = Field(default=0, ge=0)
    average_score: float = Field(default=0.0, ge=0)
    best_score: float = Field(default=0.0, ge=0)
    last_training_mode: TrainingMode | None = Field(default=None, index=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
