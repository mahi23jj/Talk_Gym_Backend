from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TrainingMode


class AttemptSubmitSchema(BaseModel):
    question_id: int = Field(gt=0)
    recording_id: int | None = Field(default=None, gt=0)
    audio_input: str | None = Field(default=None, min_length=1)


class FinalAttemptSchema(BaseModel):
    recording_id: int | None = Field(default=None, gt=0)
    audio_input: str | None = Field(default=None, min_length=1)


class AttemptReadSchema(BaseModel):
    id: int
    user_id: int
    question_id: int
    recording_id: int | None
    parent_attempt_id: int | None
    transcript: str
    training_mode: TrainingMode
    analysis_json: dict[str, Any]
    detected_issues: list[str]
    recommendations: list[str]
    is_final_attempt: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowUpSchema(BaseModel):
    id: int
    training_mode: TrainingMode
    question_text: str
    difficulty_level: int

    model_config = ConfigDict(from_attributes=True)


class TrainingSessionSchema(BaseModel):
    attempt_id: int
    training_mode: TrainingMode
    instructions: list[str]
    followups: list[FollowUpSchema]
    recommendations: list[str]


class AnalysisReadSchema(BaseModel):
    id: int
    attempt_id: int
    raw_analysis_json: dict[str, Any]
    primary_training_mode: TrainingMode
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProgressSchema(BaseModel):
    user_id: int
    total_attempts: int
    final_attempts: int
    delivery_training_count: int
    structure_training_count: int
    behavioral_training_count: int
    average_score: float
    best_score: float
    last_training_mode: TrainingMode | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttemptSubmitResponseSchema(BaseModel):
    attempt: AttemptReadSchema
    analysis: AnalysisReadSchema
    training_session: TrainingSessionSchema
    progress: ProgressSchema


class AttemptResultSchema(BaseModel):
    attempt: AttemptReadSchema
    analysis: AnalysisReadSchema


class FinalAttemptResponseSchema(BaseModel):
    attempt: AttemptReadSchema
    analysis: AnalysisReadSchema
    progress_update: dict[str, Any]


class FollowUpResponseSchema(BaseModel):
    training_mode: TrainingMode
    followups: list[FollowUpSchema]
