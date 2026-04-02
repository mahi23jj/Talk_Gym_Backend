from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.auth import User
from app.models.interview import (
    Attempt,
    InterviewAnalysis,
    TrainingFollowUp,
    TrainingMode,
)
from app.models.speaking import Question, Recording
from app.schemas.interview import FollowUpSchema, TrainingSessionSchema
from app.services.ai_service import (
    build_training_instructions,
    generate_recommendations,
    mock_ai_analysis,
    mock_transcript,
    select_training_mode,
)
from app.services.progress_service import evaluate_progress, upsert_user_progress

DEFAULT_FOLLOWUPS: dict[str, list[tuple[str, int]]] = {
    TrainingMode.delivery_training.value: [
        ("Can you answer in 60 seconds?", 1),
        ("Remove filler words and retry", 1),
        ("Speak like you are confident you already solved it", 2),
    ],
    TrainingMode.structure_training.value: [
        ("Break your answer into STAR format", 1),
        ("What was the Situation?", 1),
        ("What was the measurable Result?", 2),
    ],
    TrainingMode.behavioral_training.value: [
        ("What did YOU specifically do?", 1),
        ("How did YOU take initiative?", 1),
        ("What measurable impact did YOU create?", 2),
    ],
}


def seed_training_followups(db: Session) -> None:
    existing = db.exec(select(func.count(TrainingFollowUp.id))).one()
    if int(existing) > 0:
        return

    for training_mode, items in DEFAULT_FOLLOWUPS.items():
        for question_text, difficulty_level in items:
            db.add(
                TrainingFollowUp(
                    training_mode=training_mode,
                    question_text=question_text,
                    difficulty_level=difficulty_level,
                )
            )
    db.commit()


async def get_random_followups(db: Session, training_mode: str, limit: int = 3) -> list[TrainingFollowUp]:
    rows = db.exec(
        select(TrainingFollowUp).where(TrainingFollowUp.training_mode == training_mode)
    ).all()
    if not rows:
        seed_training_followups(db)
        rows = db.exec(
            select(TrainingFollowUp).where(TrainingFollowUp.training_mode == training_mode)
        ).all()
    if len(rows) <= limit:
        return rows
    return random.sample(rows, limit)


async def submit_attempt(
    db: Session,
    user: User,
    question_id: int,
    recording_id: int | None,
    audio_input: str | None,
) -> dict[str, Any]:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    recording = db.get(Recording, recording_id) if recording_id else None
    if recording_id and not recording:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    if recording and recording.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recording does not belong to user")

    transcript = mock_transcript(audio_input or (recording.audio_url if recording else None))
    analysis = mock_ai_analysis(transcript=transcript, question=f"{question.title} {question.description}")
    training_mode = select_training_mode(analysis)
    recommendations = generate_recommendations(analysis, training_mode)
    followups = await get_random_followups(db, training_mode)

    attempt = Attempt(
        user_id=user.id,
        question_id=question.id,
        recording_id=recording_id,
        transcript=transcript,
        training_mode=training_mode,
        analysis_json=analysis,
        detected_issues=analysis.get("flags", []),
        recommendations=recommendations,
        is_final_attempt=False,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    analysis_row = InterviewAnalysis(
        attempt_id=attempt.id,
        raw_analysis_json=analysis,
        primary_training_mode=training_mode,
    )
    db.add(analysis_row)
    db.commit()
    db.refresh(analysis_row)

    progress = await upsert_user_progress(db, user.id, training_mode, float(analysis.get("overall_score", 0)), is_final=False)

    return {
        "attempt": attempt,
        "analysis": analysis_row,
        "training_session": TrainingSessionSchema(
            attempt_id=attempt.id,
            training_mode=training_mode,
            instructions=build_training_instructions(training_mode),
            followups=[FollowUpSchema.model_validate(row) for row in followups],
            recommendations=recommendations,
        ),
        "progress": progress,
    }


async def create_final_attempt(
    db: Session,
    user: User,
    attempt_id: int,
    recording_id: int | None,
    audio_input: str | None,
) -> dict[str, Any]:
    base_attempt = db.get(Attempt, attempt_id)
    if not base_attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if base_attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

    question = db.get(Question, base_attempt.question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    recording = db.get(Recording, recording_id) if recording_id else None
    if recording_id and not recording:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    if recording and recording.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recording does not belong to user")

    transcript = mock_transcript(audio_input or (recording.audio_url if recording else None))
    analysis = mock_ai_analysis(transcript=transcript, question=f"{question.title} {question.description}")
    training_mode = select_training_mode(analysis)
    recommendations = generate_recommendations(analysis, training_mode)

    final_attempt = Attempt(
        user_id=user.id,
        question_id=question.id,
        recording_id=recording_id or base_attempt.recording_id,
        parent_attempt_id=base_attempt.id,
        transcript=transcript,
        training_mode=training_mode,
        analysis_json=analysis,
        detected_issues=analysis.get("flags", []),
        recommendations=recommendations,
        is_final_attempt=True,
    )
    db.add(final_attempt)
    db.commit()
    db.refresh(final_attempt)

    analysis_row = InterviewAnalysis(
        attempt_id=final_attempt.id,
        raw_analysis_json=analysis,
        primary_training_mode=training_mode,
    )
    db.add(analysis_row)
    db.commit()
    db.refresh(analysis_row)

    progress_update = await evaluate_progress(base_attempt, final_attempt)

    progress = await upsert_user_progress(db, user.id, training_mode, float(analysis.get("overall_score", 0)), is_final=True)
    progress_update["progress"] = progress

    return {
        "attempt": final_attempt,
        "analysis": analysis_row,
        "progress_update": progress_update,
    }


async def build_training_session(db: Session, attempt: Attempt) -> TrainingSessionSchema:
    followups = await get_random_followups(db, attempt.training_mode)
    return TrainingSessionSchema(
        attempt_id=attempt.id,
        training_mode=attempt.training_mode,
        instructions=build_training_instructions(attempt.training_mode),
        followups=[FollowUpSchema.model_validate(row) for row in followups],
        recommendations=attempt.recommendations,
    )


async def get_followups_by_mode(db: Session, training_mode: str, limit: int = 3) -> list[FollowUpSchema]:
    rows = await get_random_followups(db, training_mode, limit)
    return [FollowUpSchema.model_validate(row) for row in rows]
