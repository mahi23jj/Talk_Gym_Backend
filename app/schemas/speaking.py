from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.speaking import AttemptType, SenderType


class QuestionCreateSchema(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    day_unlock: int = Field(ge=1)


class QuestionReadSchema(QuestionCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordingCreateSchema(BaseModel):
    user_id: int = Field(gt=0)
    question_id: int = Field(gt=0)
    audio_url: str = Field(min_length=5, max_length=500)
    duration_seconds: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    attempt_type: AttemptType = AttemptType.normal


class RecordingReadSchema(RecordingCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreateSchema(BaseModel):
    user_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)


class ChatSessionEndSchema(BaseModel):
    is_active: bool = False
    ended_at: datetime


class ChatSessionReadSchema(BaseModel):
    id: int
    user_id: int
    recording_id: int
    is_active: bool
    created_at: datetime
    ended_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreateSchema(BaseModel):
    chat_session_id: int = Field(gt=0)
    sender_type: SenderType
    message_text: str | None = Field(default=None, min_length=1)
    audio_url: str | None = Field(default=None, min_length=5, max_length=500)

    @model_validator(mode="after")
    def require_text_or_audio(self) -> "ChatMessageCreateSchema":
        if not self.message_text and not self.audio_url:
            raise ValueError("Either message_text or audio_url must be provided")
        return self


class ChatMessageReadSchema(BaseModel):
    id: int
    chat_session_id: int
    sender_type: SenderType
    message_text: str | None
    audio_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisCreateSchema(BaseModel):
    chat_session_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    summary: str = Field(min_length=10)
    feedback: str = Field(min_length=10)
    tips: str = Field(min_length=5)
    score: int = Field(ge=0, le=100)


class AIAnalysisReadSchema(AIAnalysisCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
