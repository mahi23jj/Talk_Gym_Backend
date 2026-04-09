from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.enums import TrainingMode
from app.models.interview import Attempt, InterviewAnalysis
from app.models.question import Question
from app.models.recording import Recording
from app.models.training import TrainingProgress, TrainingRecommendation
from app.services.ai_service import mock_ai_analysis, mock_transcript, select_training_mode


async def submit_normal_attempt(
    db: Session,
    user_id: int,
    question_id: int,
    audio_url: str,
    duration_seconds: int,
    size_bytes: int,
) -> dict[str, Any]:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    transcript = mock_transcript(audio_url)

    recording = Recording(
        user_id=user_id,
        question_id=question.id,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
        transcription=transcript,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    analysis_payload = mock_ai_analysis(
        transcript=transcript,
        question=f"{question.title}. {question.description}",
    )

    ordered_candidates = select_training_mode(analysis_payload)
    ordered_plan: list[TrainingMode] = []
    for mode in ordered_candidates:
        normalized = mode if isinstance(mode, TrainingMode) else TrainingMode(str(mode))
        if normalized not in ordered_plan:
            ordered_plan.append(normalized)

    attempt = Attempt(
        user_id=user_id,
        question_id=question.id,
        recording_id=recording.id,
        transcript=transcript,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    score = int(round(float(analysis_payload.get("overall_score", 0.0)) * 10))
    feedback = "Mock AI analysis completed for the submitted answer."

    analysis = InterviewAnalysis(
        attempt_id=attempt.id,
        score=score,
        feedback=feedback,
        raw_analysis_json=analysis_payload,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    recommendations: list[TrainingRecommendation] = []
    for priority, training_type in enumerate(ordered_plan, start=1):
        row = TrainingRecommendation(
            attempt_id=attempt.id,
            training_type=training_type,
            priority=priority,
        )
        db.add(row)
        recommendations.append(row)

    progress = TrainingProgress(
        attempt_id=attempt.id,
        current_priority=1,
        completed=False,
    )
    db.add(progress)
    db.commit()

    for row in recommendations:
        db.refresh(row)
    db.refresh(progress)

    return {
        "recording": recording,
        "attempt": attempt,
        "analysis": analysis,
        "recommendations": recommendations,
        "progress": progress,
    }
