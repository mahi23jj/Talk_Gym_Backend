from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

from app.models.interview import Attempt, TrainingMode



class TrainingRecommendation(SQLModel, table=True):
    __tablename__ = "training_recommendations"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", index=True)

    training_type: TrainingMode
    priority: int

    attempt: Optional["Attempt"] = Relationship(back_populates="recommendations")




class TrainingProgress(SQLModel, table=True):
    __tablename__ = "training_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", unique=True)

    current_priority: int = 1
    completed: bool = False

    attempt: Optional["Attempt"] = Relationship(back_populates="progress")


class TrainingAttempt(SQLModel, table=True):
    __tablename__ = "training_attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempts.id", index=True)

    training_type: TrainingMode
    transcript: str

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

    training_attempt: Optional["TrainingAttempt"] = Relationship(back_populates="analysis")

