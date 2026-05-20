from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.models.job import Job
from app.models.interview import InterviewAnalysis, InterviewSession, Attempt
from app.models.question import Question
from app.models.recording import Recording
from app.models.enums import AttemptStage, TrainingMode

from app.core.redis import async_redis_client
from app.services.Ai_Transaltion import transcribe_audio_path
from app.services.ai_service import ai_analysis_async, mock_ai_analysis
from app.services.final_interview import build_interview_report
from app.services.voice_analyzer import _download_to_temp, build_voice_metrics, extract_voice_features
from traning_recomendation import select_training_mode


logger = logging.getLogger(__name__)

TRANSCRIPTION_TIMEOUT_SECONDS = 300
VOICE_ANALYSIS_TIMEOUT_SECONDS = 180


# ---------------------------
# Helpers
# ---------------------------

async def _extract_voice_features(audio_url: str) -> dict[str, Any] | None:
    try:
        logger = logging.getLogger(__name__)
        logger.info("_extract_voice_features: requesting analysis for %s", audio_url)
        result = await asyncio.wait_for(
            asyncio.to_thread(extract_voice_features, audio_url),
            timeout=VOICE_ANALYSIS_TIMEOUT_SECONDS,
        )
        logger.info("_extract_voice_features: success for %s", audio_url)
        return result
    except Exception:
        logger = logging.getLogger(__name__)
        logger.exception("_extract_voice_features: failed for %s", audio_url)
        return None


def _build_attempt_analysis_response(
    analysis_row: InterviewAnalysis,
    voice_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_analysis = analysis_row.raw_analysis_json or {}
    return {
        "id": analysis_row.id,
        "attempt_id": analysis_row.attempt_id,
        "score": analysis_row.score,
        "feedback": analysis_row.feedback,
        "raw_analysis_json": raw_analysis,
        "voice_metrics": voice_metrics if voice_metrics is not None else raw_analysis.get("voice_metrics"),
        "created_at": analysis_row.created_at,
    }


def _build_cached_analysis_response(
    data: dict[str, Any],
    job: Job,
) -> dict[str, Any]:
    created_at = data.get("created_at")
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    return {
        "id": data.get("analysis_id", job.attempt_id or job.id),
        "attempt_id": job.attempt_id,
        "score": data.get("score", 0),
        "feedback": data.get("feedback", ""),
        "raw_analysis_json": data.get("raw_analysis_json", {}),
        "voice_metrics": data.get("voice_metrics"),
        "created_at": created_at,
    }


# ---------------------------
# CORE PROCESSING
# ---------------------------

async def process_job_sync(
    db: Session,
    job_id: int,
    payload: dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    job.status = "processing"
    db.add(job)
    db.commit()

    try:
        # -------------------------
        # Extract payload (accept either a dict or individual kwargs)
        # -------------------------
        if payload is None:
            payload = kwargs

        user_id = int(payload["user_id"])
        question_id = int(payload["question_id"])
        session_id = int(payload["session_id"])
        audio_url = str(payload["audio_url"])
        duration_seconds = int(payload["duration_seconds"])
        size_bytes = int(payload["size_bytes"])
        stage = AttemptStage(payload.get("stage", AttemptStage.INITIAL.value))

        question = db.get(Question, question_id)
        if not question:
            raise ValueError("Question not found")

        local_audio = await asyncio.to_thread(_download_to_temp, audio_url)
        
        # -------------------------
        # PARALLEL PROCESSING
        # -------------------------
        transcription_task = asyncio.create_task(
            asyncio.to_thread(transcribe_audio_path, local_audio)
        )

        voice_task = asyncio.create_task(
        asyncio.to_thread(extract_voice_features, audio_url)
        )

        transcript_items = await asyncio.wait_for(
            transcription_task,
            timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
        )

        transcript = " ".join(
            i.get("sentence", "") for i in transcript_items
        ).strip()

        # -------------------------
        # AI ANALYSIS
        # -------------------------
        analysis_task = asyncio.create_task(
            ai_analysis_async(
            transcript=transcript_items,
            question=f"{question.title}. {question.description}",
            )
        )
     

        voice_features, analysis_payload = await asyncio.gather(
            voice_task,
            analysis_task,
        )
        logger = logging.getLogger(__name__)
        voice_metrics = None

        if voice_features is None:
            logger.warning("Voice features analysis returned None for job_id=%s, user=%s", job_id, user_id)
        else:
            logger.info("Voice features obtained for job_id=%s: keys=%s", job_id, list(voice_features.keys()))
            try:
                voice_metrics = build_voice_metrics(
                    raw_features=voice_features,
                    transcript=transcript_items,
                    duration_seconds=duration_seconds,
                )
                logger.info("Voice metrics built for job_id=%s: %s", job_id, voice_metrics)
            except Exception as exc:
                logger.exception("Failed to build voice metrics for job_id=%s: %s", job_id, exc)

        analysis_payload["voice_metrics"] = voice_metrics

        # -------------------------
        # TRAINING PLAN
        # -------------------------
        ordered_plan = []
        for mode in select_training_mode(analysis_payload):
            normalized = (
                mode if isinstance(mode, TrainingMode)
                else TrainingMode(str(mode))
            )
            if normalized not in ordered_plan:
                ordered_plan.append(normalized)

        # -------------------------
        # SAVE RECORDING
        # -------------------------
        recording = Recording(
            user_id=user_id,
            question_id=question_id,
            audio_url=audio_url,
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            transcription=transcript,
        )
        db.add(recording)
        db.flush()

        # -------------------------
        # SAVE ATTEMPT
        # -------------------------
        attempt = Attempt(
            user_id=user_id,
            question_id=question_id,
            recording_id=recording.id,
            transcript=transcript,
            session_id=session_id,
            stage=stage,
        )
        db.add(attempt)
        db.flush()

        # -------------------------
        # SAVE ANALYSIS
        # -------------------------
        score = int(round(
            float(analysis_payload.get("overall_score", 0)) * 10
        ))

        analysis = InterviewAnalysis(
            attempt_id=attempt.id,
            score=score,
            feedback="Analysis completed",
            raw_analysis_json=analysis_payload,
        )
        db.add(analysis)
        db.flush()

        # -------------------------
        # COMPLETE JOB
        # -------------------------
        job.status = "done"
        job.attempt_id = attempt.id
        db.add(job)
        db.commit()

        # =========================================================
        # CACHE RESULT
        # =========================================================

        result_payload = {
            "attempt_id": attempt.id,
            "analysis": _build_attempt_analysis_response(
                analysis_row=analysis,
                voice_metrics=voice_metrics,
            ),
            "stage": stage.value,
        }

        # INITIAL CACHE
        if stage == AttemptStage.INITIAL:

            await async_redis_client.set(
                f"attempt_result:{job_id}",
                json.dumps(result_payload, default=str),
                ex=3600,
            )

        # FINAL CACHE (SESSION REPORT)
        elif stage == AttemptStage.FINAL:

            initial_attempt = db.exec(
                select(Attempt)
                .where(
                    Attempt.session_id == session_id,
                    Attempt.stage == AttemptStage.INITIAL,
                )
                .options(selectinload(Attempt.analysis))
            ).first()

            if initial_attempt and initial_attempt.analysis:

                report = build_interview_report(
                    initial_attempt=initial_attempt,
                    final_attempt=attempt,
                    initial_analysis=initial_attempt.analysis,
                    final_analysis=analysis,
                )

                await async_redis_client.set(
                    f"session_result:{session_id}",
                    json.dumps(report, default=str),
                    ex=3600,
                )

                return report

        return result_payload

    except Exception:
        logger.error("process_job_sync failed", exc_info=True)
        traceback.print_exc()
        db.rollback()

        job.status = "failed"
        db.add(job)
        db.commit()

        raise HTTPException(500, "Processing failed")

# ---------------------------
# SUBMIT JOB
# ---------------------------

async def submit_normal_attempt(
    db: Session,
    user_id: int,
    question_id: int,
    duration_seconds: int,
    size_bytes: int,
    audio_url: str,
) -> dict[str, Any]:

    try:
        session = InterviewSession(
            user_id=user_id,
            question_id=question_id,
        )
        db.add(session)
        db.flush()

        job = Job(status="pending")
        db.add(job)
        db.flush()
        db.commit()

        payload = {
            "user_id": user_id,
            "question_id": question_id,
            "session_id": session.id,
            "audio_url": audio_url,
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
        }

        await async_redis_client.set(
            f"job_payload:{job.id}",
            json.dumps(payload),
            ex=3600,
        )

        return {
            "job_id": job.id,
            "message": "Attempt submitted successfully."
        }

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ---------------------------
# GET RESULT (POLLING)
# ---------------------------

async def get_attempt_result(db: Session, job_id: int) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # ---------------------------
    # If pending → try Redis payload
    # ---------------------------
    if job.status == "pending":

        cached = await async_redis_client.get(f"job_payload:{job_id}")

        if not cached:
            return {
                "status": "processing",
                "message": "Job still initializing..."
            }

        payload = json.loads(cached)

        await process_job_sync(
            db=db,
            job_id=job_id,
            user_id=payload["user_id"],
            question_id=payload["question_id"],
            session_id=payload["session_id"],
            audio_url=payload["audio_url"],
            duration_seconds=payload["duration_seconds"],
            size_bytes=payload["size_bytes"],
        )

    # ---------------------------
    # DONE CASE
    # ---------------------------
    if job.status == "done":
        analysis_row = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == job.attempt_id
            )
        ).first()

        if analysis_row:
            cached = await async_redis_client.get(f"attempt_result:{job_id}")
            cached_voice_metrics = None
            if cached:
                cached_data = json.loads(cached)
                if isinstance(cached_data, dict):
                    cached_voice_metrics = cached_data.get("analysis", {}).get("voice_metrics")
                    if cached_voice_metrics is None:
                        cached_voice_metrics = cached_data.get("voice_metrics")

            return {
                "status": "done",
                "analysis": _build_attempt_analysis_response(
                    analysis_row,
                    voice_metrics=cached_voice_metrics,
                ),
            }

        cached = await async_redis_client.get(f"attempt_result:{job_id}")
        if cached:
            data = json.loads(cached)
            analysis_data = data.get("analysis") if isinstance(data, dict) else None
            if analysis_data is None and isinstance(data, dict):
                analysis_data = _build_cached_analysis_response(data, job)
            return {"status": "done", "analysis": analysis_data}

        return {"status": "done", "analysis": None}

    # ---------------------------
    # FAILED CASE
    # ---------------------------
    if job.status == "failed":
        return {
            "status": "failed",
            "message": "Processing failed"
        }

    return {
        "status": "processing",
        "message": "Still processing..."
    }


# ---------------------------
# OPTIONAL CLEAN RESULT FETCH
# ---------------------------

async def get_analysis_result(db: Session, job_id: int) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if job.status == "done":
        analysis_row = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == job.attempt_id
            )
        ).first()
        if analysis_row:
            return {
                "status": "done",
                "analysis": _build_attempt_analysis_response(analysis_row),
            }

    cached = await async_redis_client.get(f"attempt_result:{job_id}")
    if cached:
        data = json.loads(cached)
        if isinstance(data, dict) and "analysis" in data:
            return {"status": "done", "analysis": data["analysis"]}

        return {
            "status": "done",
            "analysis": _build_cached_analysis_response(data, job),
        }

    result = await get_attempt_result(db, job_id)

    if result.get("status") != "done":
        return result

    return result