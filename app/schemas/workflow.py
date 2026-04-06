from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.interview import AttemptStatus, TrainingMode


class AttemptSubmitRequest(BaseModel):
    question_id: int = Field(gt=0)
    audio_url: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    audio_input: str | None = Field(default=None, min_length=1)


class AttemptRead(BaseModel):
    id: int
    user_id: int
    question_id: int
    recording_id: int
    transcript: str
    status: AttemptStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordingRead(BaseModel):
    id: int
    user_id: int
    question_id: int
    audio_url: str
    duration_seconds: int
    size_bytes: int
    transcription: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewAnalysisRead(BaseModel):
    id: int
    attempt_id: int
    score: int
    feedback: str
    raw_analysis_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRecommendationRead(BaseModel):
    id: int
    attempt_id: int
    training_type: TrainingMode
    priority: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingProgressRead(BaseModel):
    id: int
    attempt_id: int
    current_priority: int
    completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttemptSubmitResponse(BaseModel):
    recording: RecordingRead
    attempt: AttemptRead
    analysis: InterviewAnalysisRead
    recommendations: list[TrainingRecommendationRead]
    progress: TrainingProgressRead


class TrainingSubmitRequest(BaseModel):
    attempt_id: int = Field(gt=0)
    training_type: TrainingMode
    transcript: str = Field(min_length=3)


class TrainingAttemptRead(BaseModel):
    id: int
    attempt_id: int
    training_type: TrainingMode
    transcript: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingAnalysisRead(BaseModel):
    id: int
    training_attempt_id: int
    training_type: TrainingMode
    score: int
    passed: bool
    feedback: str
    raw_analysis_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingSubmitResponse(BaseModel):
    training_attempt: TrainingAttemptRead
    analysis: TrainingAnalysisRead
    recommendation: str


class CurrentTrainingResponse(BaseModel):
    attempt_id: int
    current_priority: int
    completed: bool
    current_training: TrainingRecommendationRead | None


class TrainingNextRequest(BaseModel):
    attempt_id: int = Field(gt=0)


class TrainingNextResponse(BaseModel):
    attempt_id: int
    current_priority: int
    completed: bool
    next_training: TrainingRecommendationRead | None


class TrainingGuidanceResponse(BaseModel):
    training_mode: TrainingMode
    instructions: list[str]
    followups: list[str]
