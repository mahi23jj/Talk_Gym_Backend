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
from app.services.voice_analyzer import (
    _download_to_temp,
    build_voice_metrics,
    extract_voice_features,
)
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
        "voice_metrics": (
            voice_metrics
            if voice_metrics is not None
            else raw_analysis.get("voice_metrics")
        ),
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


def _normalize_analysis_payload(
    payload: dict[str, Any],
    *,
    analysis_row: InterviewAnalysis | None = None,
    job: Job | None = None,
) -> dict[str, Any]:
    normalized = dict(payload)

    analysis_id = normalized.get("id") or normalized.get("analysis_id")
    if analysis_id is None and analysis_row is not None:
        analysis_id = analysis_row.id
    if analysis_id is None and job is not None:
        analysis_id = job.attempt_id or job.id

    normalized["id"] = analysis_id
    return normalized


def _fallback_voice_metrics() -> dict[str, Any]:
    return {
        "confidence": {"score": 0.0, "level": "Needs Improvement"},
        "delivery": {
            "speech_rate_wps": 0.0,
            "pace": "Too Slow",
            "tip": "Try speaking a little faster to sound more natural.",
        },
        "nervousness": {
            "score": 0.0,
            "level": "Calm",
            "tip": "You sound relaxed and controlled.",
        },
        "voice_tone": {
            "variation_score": 0.0,
            "level": "Monotone",
            "tip": "Your voice lacks variation.",
        },
        "pausing": {
            "average_pause_seconds": 0.0,
            "long_pauses": 0,
            "silence_percent": 0.0,
        },
        "summary": "Needs improvement confidence, too slow, monotone, calm.",
    }


# ---------------------------
# CORE PROCESSING
# ---------------------------

# async def process_job_sync(
#     db: Session,
#     job_id: int,
#     payload: dict | None = None,
#     **kwargs: Any,
# ) -> dict[str, Any]:

#     job = db.get(Job, job_id)
#     if not job:
#         raise HTTPException(404, "Job not found")

#     job.status = "processing"
#     db.add(job)
#     db.commit()

#     try:
#         # -------------------------
#         # Extract payload (accept either a dict or individual kwargs)
#         # -------------------------
#         if payload is None:
#             payload = kwargs

#         user_id = int(payload["user_id"])
#         question_id = int(payload["question_id"])
#         session_id = int(payload["session_id"])
#         audio_url = str(payload["audio_url"])
#         duration_seconds = int(payload["duration_seconds"])
#         size_bytes = int(payload["size_bytes"])
#         stage = AttemptStage(payload.get("stage", AttemptStage.INITIAL.value))

#         question = db.get(Question, question_id)
#         if not question:
#             raise ValueError("Question not found")

#         local_audio = await asyncio.to_thread(_download_to_temp, audio_url)

#         # -------------------------
#         # PARALLEL PROCESSING
#         # -------------------------
#         transcription_task = asyncio.create_task(
#             asyncio.to_thread(transcribe_audio_path, local_audio)
#         )

#         voice_task = asyncio.create_task(
#         asyncio.to_thread(extract_voice_features, audio_url)
#         )

#         transcript_items = await asyncio.wait_for(
#             transcription_task,
#             timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
#         )

#         transcript = " ".join(
#             i.get("sentence", "") for i in transcript_items
#         ).strip()

#         # -------------------------
#         # AI ANALYSIS
#         # -------------------------
#         analysis_task = asyncio.create_task(
#             ai_analysis_async(
#             transcript=transcript_items,
#             question=f"{question.title}. {question.description}",
#             )
#         )


#         voice_features, analysis_payload = await asyncio.gather(
#             voice_task,
#             analysis_task,
#         )
#         logger = logging.getLogger(__name__)
#         voice_metrics = None

#         if voice_features is None:
#             logger.warning("Voice features analysis returned None for job_id=%s, user=%s", job_id, user_id)
#         else:
#             logger.info("Voice features obtained for job_id=%s: keys=%s", job_id, list(voice_features.keys()))
#             try:
#                 voice_metrics = build_voice_metrics(
#                     raw_features=voice_features,
#                     transcript=transcript_items,
#                     duration_seconds=duration_seconds,
#                 )
#                 logger.info("Voice metrics built for job_id=%s: %s", job_id, voice_metrics)
#             except Exception as exc:
#                 logger.exception("Failed to build voice metrics for job_id=%s: %s", job_id, exc)

#         analysis_payload["voice_metrics"] = voice_metrics

#         # -------------------------
#         # TRAINING PLAN
#         # -------------------------
#         ordered_plan = []
#         for mode in select_training_mode(analysis_payload):
#             normalized = (
#                 mode if isinstance(mode, TrainingMode)
#                 else TrainingMode(str(mode))
#             )
#             if normalized not in ordered_plan:
#                 ordered_plan.append(normalized)

#         # -------------------------
#         # SAVE RECORDING
#         # -------------------------
#         recording = Recording(
#             user_id=user_id,
#             question_id=question_id,
#             audio_url=audio_url,
#             duration_seconds=duration_seconds,
#             size_bytes=size_bytes,
#             transcription=transcript,
#         )
#         db.add(recording)
#         db.flush()

#         # -------------------------
#         # SAVE ATTEMPT
#         # -------------------------
#         attempt = Attempt(
#             user_id=user_id,
#             question_id=question_id,
#             recording_id=recording.id,
#             transcript=transcript,
#             session_id=session_id,
#             stage=stage,
#         )
#         db.add(attempt)
#         db.flush()

#         # -------------------------
#         # SAVE ANALYSIS
#         # -------------------------
#         score = int(round(
#             float(analysis_payload.get("overall_score", 0)) * 10
#         ))

#         analysis = InterviewAnalysis(
#             attempt_id=attempt.id,
#             score=score,
#             feedback="Analysis completed",
#             raw_analysis_json=analysis_payload,
#         )
#         db.add(analysis)
#         db.flush()

#         # -------------------------
#         # COMPLETE JOB
#         # -------------------------
#         job.status = "done"
#         job.attempt_id = attempt.id
#         db.add(job)
#         db.commit()

#         # =========================================================
#         # CACHE RESULT
#         # =========================================================

#         result_payload = {
#             "attempt_id": attempt.id,
#             "analysis": _build_attempt_analysis_response(
#                 analysis_row=analysis,
#                 voice_metrics=voice_metrics,
#             ),
#             "stage": stage.value,
#         }

#         # INITIAL CACHE
#         if stage == AttemptStage.INITIAL:

#             await async_redis_client.set(
#                 f"attempt_result:{job_id}",
#                 json.dumps(result_payload, default=str),
#                 ex=3600,
#             )

#         # FINAL CACHE (SESSION REPORT)
#         elif stage == AttemptStage.FINAL:

#             initial_attempt = db.exec(
#                 select(Attempt)
#                 .where(
#                     Attempt.session_id == session_id,
#                     Attempt.stage == AttemptStage.INITIAL,
#                 )
#                 .options(selectinload(Attempt.analysis))
#             ).first()

#             if initial_attempt and initial_attempt.analysis:

#                 report = build_interview_report(
#                     initial_attempt=initial_attempt,
#                     final_attempt=attempt,
#                     initial_analysis=initial_attempt.analysis,
#                     final_analysis=analysis,
#                 )

#                 await async_redis_client.set(
#                     f"session_result:{session_id}",
#                     json.dumps(report, default=str),
#                     ex=3600,
#                 )

#                 return report

#         return result_payload

#     except Exception:
#         logger.error("process_job_sync failed", exc_info=True)
#         traceback.print_exc()
#         db.rollback()

#         job.status = "failed"
#         db.add(job)
#         db.commit()

#         raise HTTPException(500, "Processing failed")


# async def process_job_sync(
#     db: Session,
#     job_id: int,
#     payload: dict,
# ) -> dict[str, Any]:

#     job = db.get(Job, job_id)
#     if not job:
#         raise HTTPException(404, "Job not found")

#     try:
#         step = payload.get("step", 1)

#         # -------------------------
#         # STEP 1
#         # download + convert
#         # -------------------------
#         if step == 1:

#             local_audio = await asyncio.to_thread(
#                 _download_to_temp,
#                 payload["audio_url"],
#             )

#             payload["local_audio"] = local_audio
#             payload["step"] = 2

#             await async_redis_client.set(
#                 f"job_payload:{job_id}",
#                 json.dumps(payload),
#                 ex=3600,
#             )

#             return {
#                 "status": "processing",
#                 "message": "Audio prepared"
#             }

#         # -------------------------
#         # STEP 2
#         # transcription + voice
#         # -------------------------
#         if step == 2:

#             local_audio = payload["local_audio"]

#             transcript_items = await asyncio.to_thread(
#                 transcribe_audio_path,
#                 local_audio,
#             )

#             payload["transcript_items"] = transcript_items
#             payload["step"] = 3

#             await async_redis_client.set(
#                 f"job_payload:{job_id}",
#                 json.dumps(payload),
#                 ex=3600,
#             )

#             return {"status": "processing", "message": "Transcript ready"}


#         # if step == 3:

#         #     local_audio = payload["local_audio"]

#         #     voice_features = await asyncio.to_thread(
#         #         extract_voice_features,
#         #         local_audio,   # ✅ LOCAL PATH ONLY
#         #     )

#         #     payload["voice_features"] = voice_features
#         #     payload["step"] = 4

#         #     await async_redis_client.set(
#         #         f"job_payload:{job_id}",
#         #         json.dumps(payload),
#         #         ex=3600,
#         #     )

#         #     return {"status": "processing", "message": "Voice analysis ready"}


#         # -------------------------
#         # STEP 4
#         # AI + save
#         # -------------------------
#         if step == 3:

#             question = db.get(
#                 Question,
#                 payload["question_id"],
#             )

#             analysis_payload = await ai_analysis_async(
#                 transcript=payload["transcript_items"],
#                 question=f"{question.title}. {question.description}",
#             )

#             """            voice_metrics = build_voice_metrics(
#                 raw_features=payload["voice_features"],
#                 transcript=payload["transcript_items"],
#                 duration_seconds=payload["duration_seconds"],
#             )

#             analysis_payload["voice_metrics"] = voice_metrics """

#             recording = Recording(
#                 user_id=payload["user_id"],
#                 question_id=payload["question_id"],
#                 audio_url=payload["audio_url"],
#                 duration_seconds=payload["duration_seconds"],
#                 size_bytes=payload["size_bytes"],
#                 transcription=" ".join(
#                     x["sentence"]
#                     for x in payload["transcript_items"]
#                 ),
#             )

#             db.add(recording)
#             db.flush()

#             attempt = Attempt(
#                 user_id=payload["user_id"],
#                 question_id=payload["question_id"],
#                 recording_id=recording.id,
#                 transcript=recording.transcription,
#                 session_id=payload["session_id"],
#                 stage=AttemptStage.INITIAL,
#             )

#             db.add(attempt)
#             db.flush()

#             analysis = InterviewAnalysis(
#                 attempt_id=attempt.id,
#                 score=int(
#                     round(
#                         float(
#                             analysis_payload.get(
#                                 "overall_score",
#                                 0
#                             )
#                         ) * 10
#                     )
#                 ),
#                 feedback="Analysis completed",
#                 raw_analysis_json=analysis_payload,
#             )

#             db.add(analysis)
#             db.flush()

#             job.status = "done"
#             job.attempt_id = attempt.id

#             db.add(job)
#             db.commit()

#             result = {
#                 "attempt_id": attempt.id,
#                 "analysis": _build_attempt_analysis_response(
#                     analysis
#                     # voice_metrics=voice_metrics,
#                 ),
#             }

#             await async_redis_client.set(
#                 f"attempt_result:{job_id}",
#                 json.dumps(result, default=str),
#                 ex=3600,
#             )

#             return {
#                 "status": "done",
#                 "analysis": result["analysis"],
#             }

#     except Exception:
#         logger.error(traceback.format_exc())

#         db.rollback()

#         job.status = "failed"
#         db.add(job)
#         db.commit()

#         raise HTTPException(500, "Processing failed")


async def process_job_sync(
    db: Session,
    job_id: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if payload is None:
        payload_raw = await async_redis_client.get(f"job_payload:{job_id}")
        if not payload_raw:
            return {"status": "processing", "message": "No payload yet"}

        payload = json.loads(payload_raw)
    step = payload.get("step", 1)

    try:
        # -------------------------
        # STEP 1: DOWNLOAD
        # -------------------------
        if step == 1:
            local_audio = await asyncio.to_thread(
                _download_to_temp,
                payload["audio_url"],
            )

            payload["local_audio"] = local_audio
            payload["step"] = 2

            await async_redis_client.set(
                f"job_payload:{job_id}",
                json.dumps(payload),
                ex=3600,
            )

            return {"status": "processing", "step": 1}

        # -------------------------
        # STEP 2: TRANSCRIBE
        # -------------------------
        if step == 2:
            transcript_items = await asyncio.to_thread(
                transcribe_audio_path,
                payload["local_audio"],
            )

            payload["transcript_items"] = transcript_items
            payload["step"] = 3

            await async_redis_client.set(
                f"job_payload:{job_id}",
                json.dumps(payload),
                ex=3600,
            )

            return {"status": "processing", "step": 2}


        # if step == :

            # local_audio = payload["local_audio"]

            # voice_features = await asyncio.to_thread(
            #     extract_voice_features,
            #     local_audio,   # ✅ LOCAL PATH ONLY
            # )

            # payload["voice_features"] = voice_features
            # payload["step"] = 4

            # await async_redis_client.set(
            #     f"job_payload:{job_id}",
            #     json.dumps(payload),
            #     ex=3600,
            # )

            # return {"status": "processing", "message": "Voice analysis ready"}


        # -------------------------
        # STEP 3: AI ANALYSIS + SAVE
        # -------------------------
        if step == 3:

            question = db.get(Question, payload["question_id"])

            analysis_payload = await ai_analysis_async(
                transcript=payload["transcript_items"],
                question=f"{question.title}. {question.description}",
            )

            voice_metrics = _fallback_voice_metrics()
            """ try:
                voice_features = payload.get("voice_features")
                if isinstance(voice_features, dict):
                    voice_metrics = build_voice_metrics(
                        raw_features=voice_features,
                        transcript=payload.get("transcript_items"),
                        duration_seconds=payload.get("duration_seconds"),
                    )
                else:
                    logger.warning(
                        "Missing voice_features in payload for job_id=%s; using fallback metrics",
                        job_id,
                    )
            except Exception:
                logger.exception(
                    "Failed to build voice metrics for job_id=%s; using fallback metrics",
                    job_id,
                ) """

            analysis_payload["voice_metrics"] = voice_metrics

            recording = Recording(
                user_id=payload["user_id"],
                question_id=payload["question_id"],
                audio_url=payload["audio_url"],
                duration_seconds=payload["duration_seconds"],
                size_bytes=payload["size_bytes"],
                transcription=" ".join(
                    x["sentence"] for x in payload["transcript_items"]
                ),
            )

            db.add(recording)
            db.flush()

            attempt = Attempt(
                user_id=payload["user_id"],
                question_id=payload["question_id"],
                recording_id=recording.id,
                transcript=recording.transcription,
                session_id=payload["session_id"],
                stage=AttemptStage(payload.get("stage")),
            )

            db.add(attempt)
            db.flush()

            analysis = InterviewAnalysis(
                attempt_id=attempt.id,
                score=int(round(float(analysis_payload.get("overall_score", 0)) * 10)),
                feedback="Analysis completed",
                raw_analysis_json=analysis_payload,
            )

            db.add(analysis)
            db.flush()

           
            result = {
                "attempt_id": attempt.id,
                "analysis": _build_attempt_analysis_response(
                    analysis,
                    voice_metrics=voice_metrics,
                ),
            }

            if payload.get("stage") == AttemptStage.FINAL.value:

                initial_attempt = db.exec(
                    select(Attempt)
                    .where(
                        Attempt.session_id == payload["session_id"],
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
                        f"session_result:{payload['session_id']}",
                        json.dumps(report, default=str),
                        ex=3600,
                    )

                    return {
                        "status": "done",
                        "analysis": report,
                        }
            
            job.status = "done"
            job.attempt_id = attempt.id


            db.add(job)
            db.commit()


            await async_redis_client.set(
                f"attempt_result:{job_id}",
                json.dumps(result, default=str),
                ex=3600,
            )

            return {
                "status": "done",
                "analysis": result["analysis"],
            }

    except Exception:
        logger.error(traceback.format_exc())
        db.rollback()

        job.status = "failed"
        db.add(job)
        db.commit()

        raise HTTPException(500, "Processing failed")

    return {"status": "processing"}


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
            "step": 1,
            "user_id": user_id,
            "question_id": question_id,
            "session_id": session.id,
            "audio_url": audio_url,
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
            "stage": AttemptStage.INITIAL.value,
        }

        await async_redis_client.set(
            f"job_payload:{job.id}",
            json.dumps(payload),
            ex=3600,
        )

        return {"job_id": job.id, "message": "Attempt submitted successfully."}

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ---------------------------
# GET RESULT (POLLING)
# ---------------------------


async def get_attempt_result(db: Session, job_id: int):

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # -----------------------------
    # FAILED
    # -----------------------------
    if job.status == "failed":
        return {"status": "failed", "message": "Processing failed"}

    # -----------------------------
    # DONE → ALWAYS VERIFY DB FIRST
    # -----------------------------
    if job.status == "done":

        analysis_row = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == job.attempt_id
            )
        ).first()

        # 🔥 IMPORTANT: if DB not ready yet, do NOT lie to frontend
        if not analysis_row:
            return {"status": "processing", "message": "Finalizing analysis..."}

        # Optional Redis cache (safe fallback only)
        cached = await async_redis_client.get(f"attempt_result:{job_id}")

        if cached:
            try:
                cached_data = json.loads(cached)
                if cached_data and "analysis" in cached_data:
                    cached_data["analysis"] = _normalize_analysis_payload(
                        cached_data["analysis"],
                        analysis_row=analysis_row,
                        job=job,
                    )
                    return cached_data
            except Exception:
                pass  # ignore broken cache

        # Build fresh response from DB (SOURCE OF TRUTH)
        analysis_payload = _build_attempt_analysis_response(analysis_row)

        response = {
            "status": "done",
            "analysis": analysis_payload,
        }

        # Update cache safely (best effort)
        try:
            await async_redis_client.set(
                f"attempt_result:{job_id}",
                json.dumps(response, default=str),
                ex=3600,
            )
        except Exception:
            pass

        return response

    # -----------------------------
    # PROCESSING → advance pipeline
    # -----------------------------
    payload_raw = await async_redis_client.get(f"job_payload:{job_id}")

    if payload_raw:
        payload = json.loads(payload_raw)
        return await process_job_sync(db, job_id, payload)

    return {"status": "processing", "message": "Still processing..."}


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
            return {
                "status": "done",
                "analysis": _normalize_analysis_payload(
                    data["analysis"],
                    job=job,
                ),
            }

        return {
            "status": "done",
            "analysis": _build_cached_analysis_response(data, job),
        }

    result = await get_attempt_result(db, job_id)

    if result.get("status") != "done":
        return result

    return result
