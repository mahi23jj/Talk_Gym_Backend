from __future__ import annotations

from pydantic import BaseModel, Field




class AudioUploadRequestMeta(BaseModel):
    question_id: int = Field(gt=0)
    duration_seconds: int = Field(gt=0)
    


class AudioUploadResponse(BaseModel):
    recording_id: int
    audio_url: str
    size_bytes: int
    duration_seconds: int
