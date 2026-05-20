
from typing import Any

import json
import logging
import traceback
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.core import redis
from app.models.interview import Attempt
from fastapi import HTTPException, status

from app.models.job import Job
from app.models.question import Question
from app.models.training import TrainingAnalysis, TrainingAttempt
from app.models.enums import TrainingMode

from app.core.redis import async_redis_client
from app.services.ai_service import mock_ai_beveviral_analysis

import traceback

logger = logging.getLogger(__name__)


async def summit_behevioral_traning(
    db: Session,
    user_id: int,
    job_id: int,
    transcript: str,
) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    attempt = db.get(Attempt, job.attempt_id)
    if not attempt:
        raise HTTPException(404, "Associated attempt not found")

    # limit attempts
    previous_attempts = db.exec(
        select(TrainingAttempt)
        .where(
            TrainingAttempt.attempt_id == attempt.id,
            TrainingAttempt.training_type == TrainingMode.behavioral_training,
        )
        .options(selectinload(TrainingAttempt.analysis))
    ).all()

    print(previous_attempts)

    if len(previous_attempts) >= 2:
        raise HTTPException(400, "Max behavioral training attempts reached")

    for a in previous_attempts:
        if a.analysis and a.analysis.passed:
            raise HTTPException(400, "Already passed behavioral training")

    # create training attempt
    training_attempt = TrainingAttempt(
        attempt_id=attempt.id,
        training_type=TrainingMode.behavioral_training,
        transcript=transcript,
    )

    db.add(training_attempt)
    db.flush()

    job.status = "pending"
    db.add(job)
    db.commit()

    return {
        "job_id": job.id,
        "training_attempt_id": training_attempt.id,
        "status": "pending",
        "message": "Behavioral training submitted successfully",
    }

async def process_behavioral_sync(
    db: Session,
    job_id: int,
) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # cache first
    cached = await async_redis_client.get(f"behavioral_result:{job_id}")
    if cached:
        return {"status": "done", "analysis": json.loads(cached)}

    if not job.attempt_id:
        return {"status": "pending", "message": "Missing attempt"}

    job.status = "processing"
    db.add(job)
    db.commit()

    try:
        attempt = db.get(Attempt, job.attempt_id)
        if not attempt:
            raise ValueError("Attempt not found")

        training_attempt = db.exec(
            select(TrainingAttempt)
            .where(
                TrainingAttempt.attempt_id == attempt.id,
                TrainingAttempt.training_type == TrainingMode.behavioral_training,
            )
            .order_by(TrainingAttempt.created_at.desc())
        ).first()

        if not training_attempt:
            raise ValueError("Training attempt not found")

        question = db.get(Question, attempt.question_id)
        question_text = (
            f"{question.title}. {question.description}"
            if question else "Behavioral training"
        )

        # -------------------------
        # AI ANALYSIS (SYNC)
        # -------------------------
        analysis_payload = mock_ai_beveviral_analysis(
            transcript=training_attempt.transcript,
            question=question_text,
        )

        score = int(round(
            float(
                analysis_payload.get(
                    "overall_Behevioral_score",
                    analysis_payload.get("overall_score", 0.0),
                )
            ) * 10
        ))

        passed = bool(
            analysis_payload.get(
                "pass",
                analysis_payload.get("passed", score >= 60),
            )
        )

        flag = str(analysis_payload.get("flag"))
        feedback = str(
            analysis_payload.get(
                "short_feedback",
                "Behavioral analysis completed." + (f" Flag: {flag}" if flag else ""),
            )
        )

        # -------------------------
        # SAVE ANALYSIS
        # -------------------------
        analysis = TrainingAnalysis(
            training_attempt_id=training_attempt.id,
            score=score,
            passed=passed,
            feedback=feedback,
            raw_analysis_json=analysis_payload,
        )

        db.add(analysis)
        db.flush()

        # -------------------------
        # UPDATE JOB
        # -------------------------
        job.status = "done"
        db.add(job)
        db.commit()

        # -------------------------
        # CACHE RESULT
        # -------------------------
        cache_payload = {
            "id": analysis.id,
            "training_attempt_id": training_attempt.id,
            "score": analysis.score,
            "passed": analysis.passed,
            "feedback": analysis.feedback,
            "raw_analysis_json": analysis.raw_analysis_json,
            "created_at": analysis.created_at.isoformat(),
        }

        await async_redis_client.set(
            f"behavioral_result:{job_id}",
            json.dumps(cache_payload, default=str),
            ex=3600,
        )

        return {"status": "done", "analysis": cache_payload}

    except Exception as exc:

        error = traceback.format_exc()

        logger.error(error)

        db.rollback()

        print(error)

        job.status = "failed"
        db.add(job)
        db.commit()

        return {
            "status": "failed",
            "message": str(exc),
            "type": type(exc).__name__,
            "traceback": error,
        }

async def get_behvioral_attempt_result(
    db: Session,
    job_id: int
) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # failed shortcut
    # if job.status == "failed":
        # return {"status": "failed", "message": "Processing failed"}

    # cache hit
    # cached = await async_redis_client.get(f"behavioral_result:{job_id}")
    # if cached:
        # return {"status": "done", "analysis": json.loads(cached)}

    # if no attempt linked
    # if not job.attempt_id:
    #     return {"status": "pending", "message": "Still initializing"}

    # 🔥 SYNC TRIGGER (THIS replaces worker)
    result = await process_behavioral_sync(db, job_id)

    return result