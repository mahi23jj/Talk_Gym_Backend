from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.interview import Attempt, AttemptStatus, TrainingMode
from app.models.question import Question
from app.models.training import (
    TrainingAnalysis,
    TrainingAttempt,
    TrainingProgress,
    TrainingRecommendation,
)
from app.services.ai_service import (
    build_training_followups,
    build_training_instructions,
    mock_ai_analysis,
    select_training_mode,
)


async def submit_training_attempt(
    db: Session,
    user_id: int,
    attempt_id: int,
    training_type: TrainingMode,
    transcript: str,
) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

    recommendation_row = db.exec(
        select(TrainingRecommendation).where(
            TrainingRecommendation.attempt_id == attempt_id,
            TrainingRecommendation.training_type == training_type,
        )
    ).first()
    if not recommendation_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Training type is not part of the recommendation plan",
        )

    training_attempt = TrainingAttempt(
        attempt_id=attempt_id,
        training_type=training_type,
        transcript=transcript,
    )
    db.add(training_attempt)
    db.commit()
    db.refresh(training_attempt)

    question = db.get(Question, attempt.question_id)
    question_text = f"{question.title}. {question.description}" if question else "Training follow-up response"
    analysis_payload = mock_ai_analysis(transcript=transcript, question=question_text)
    selected_modes = {
        mode if isinstance(mode, TrainingMode) else TrainingMode(str(mode))
        for mode in select_training_mode(analysis_payload)
    }
    score = int(round(float(analysis_payload.get("overall_score", 0.0)) * 10))
    passed = score >= 70 and training_type not in selected_modes
    feedback = (
        "Training objective met. You can move to the next step."
        if passed
        else f"Keep practicing {training_type.value.replace('_', ' ')}."
    )

    analysis = TrainingAnalysis(
        training_attempt_id=training_attempt.id,
        training_type=training_type,
        score=score,
        passed=passed,
        feedback=feedback,
        raw_analysis_json=analysis_payload,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    recommendation = "next" if analysis.passed else "repeat"
    return {
        "training_attempt": training_attempt,
        "analysis": analysis,
        "recommendation": recommendation,
    }


async def get_current_training(db: Session, attempt_id: int, user_id: int) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

    progress = db.exec(select(TrainingProgress).where(TrainingProgress.attempt_id == attempt_id)).first()
    if not progress:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training progress not found")

    current_training = None
    if not progress.completed:
        current_training = db.exec(
            select(TrainingRecommendation).where(
                TrainingRecommendation.attempt_id == attempt_id,
                TrainingRecommendation.priority == progress.current_priority,
            )
        ).first()

    return {
        "attempt_id": attempt_id,
        "current_priority": progress.current_priority,
        "completed": progress.completed,
        "current_training": current_training,
    }


async def move_to_next_training(db: Session, attempt_id: int, user_id: int) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

    progress = db.exec(select(TrainingProgress).where(TrainingProgress.attempt_id == attempt_id)).first()
    if not progress:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training progress not found")

    priorities = db.exec(
        select(TrainingRecommendation.priority).where(TrainingRecommendation.attempt_id == attempt_id)
    ).all()
    if not priorities:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No training recommendations found")

    max_priority = max(priorities)
    if progress.current_priority >= max_priority:
        progress.completed = True
        attempt.status = AttemptStatus.completed
    else:
        progress.current_priority += 1

    db.add(progress)
    db.add(attempt)
    db.commit()
    db.refresh(progress)

    next_training = None
    if not progress.completed:
        next_training = db.exec(
            select(TrainingRecommendation).where(
                TrainingRecommendation.attempt_id == attempt_id,
                TrainingRecommendation.priority == progress.current_priority,
            )
        ).first()

    return {
        "attempt_id": attempt_id,
        "current_priority": progress.current_priority,
        "completed": progress.completed,
        "next_training": next_training,
    }


def get_training_guidance(training_mode: TrainingMode) -> dict[str, Any]:
    return {
        "training_mode": training_mode,
        "instructions": build_training_instructions(training_mode.value),
        "followups": build_training_followups(training_mode.value),
    }
