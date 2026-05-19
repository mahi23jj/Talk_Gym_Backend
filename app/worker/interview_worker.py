# from app.core.redis import async_redis_client
# import asyncio

# async def clear():
#     await async_redis_client.delete("TRANSCRIPTION")

# asyncio.run(clear())

from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.db.postgran import engine
from app.models.job import Job
from app.models.interview import Attempt, InterviewAnalysis
from app.models.recording import Recording
from app.models.enums import AttemptStage, TrainingMode
from app.models.question import Question
from app.core.redis import async_redis_client, TRANSCRIPTION

from app.services.final_interview import build_interview_report
from app.services.Ai_Transaltion import transcribe_audio_path
from app.services.ai_service import mock_ai_analysis
from app.services.voice_analyzer import build_voice_metrics, extract_voice_features
from traning_recomendation import select_training_mode


MAX_CONCURRENT_JOBS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
TRANSCRIPTION_TIMEOUT_SECONDS = 300
VOICE_ANALYSIS_TIMEOUT_SECONDS = 180


async def _extract_voice_features(audio_url: str) -> dict[str, Any] | None:

    try:

        return await asyncio.wait_for(
            asyncio.to_thread(extract_voice_features, audio_url),
            timeout=VOICE_ANALYSIS_TIMEOUT_SECONDS,
        )

    except Exception:

        traceback.print_exc()

        return None


async def process_job(payload: dict):

    async with semaphore:

        job_id = int(payload["job_id"])

        with Session(engine) as db:

            job = db.get(Job, job_id)

            if not job:
                return

            job.status = "processing"
            db.add(job)
            db.commit()

            try:

                user_id = int(payload["user_id"])
                question_id = int(payload["question_id"])
                session_id = int(payload["session_id"])
                audio_url = str(payload["audio_url"])
                duration_seconds = int(payload["duration_seconds"])
                size_bytes = int(payload["size_bytes"])

                stage_value = payload.get(
                    "stage",
                    AttemptStage.INITIAL.value
                )

                attempt_stage = AttemptStage(stage_value)

                question = db.get(Question, question_id)

                if not question:
                    raise ValueError("Question not found")

                print(f"Processing job {job_id}")

                transcription_task = asyncio.create_task(
                    asyncio.to_thread(transcribe_audio_path, audio_url)
                )

                voice_analysis_task = asyncio.create_task(
                    _extract_voice_features(audio_url)
                )

                # -------------------------
                # TRANSCRIBE
                # -------------------------
                transcript_items = await asyncio.wait_for(
                    transcription_task,
                    timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
                )

                transcript = " ".join(
                    item.get("sentence", "")
                    for item in transcript_items
                ).strip()

                # -------------------------
                # ANALYZE
                # -------------------------
                analysis_payload = mock_ai_analysis(
                    transcript=transcript_items,
                    question=f"{question.title}. {question.description}",
                )

                voice_metrics = None
                voice_features = await voice_analysis_task

                if voice_features is not None:

                    try:

                        voice_metrics = build_voice_metrics(
                            raw_features=voice_features,
                            transcript=transcript_items,
                            duration_seconds=duration_seconds,
                        )

                    except Exception:

                        traceback.print_exc()

                        voice_metrics = None

                analysis_payload["voice_metrics"] = voice_metrics

                ordered_candidates = select_training_mode(
                    analysis_payload
                )

                ordered_plan = []

                for mode in ordered_candidates:

                    normalized = (
                        mode
                        if isinstance(mode, TrainingMode)
                        else TrainingMode(str(mode))
                    )

                    if normalized not in ordered_plan:
                        ordered_plan.append(normalized)

                # -------------------------
                # RECORDING
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
                # ATTEMPT
                # -------------------------
                attempt = Attempt(
                    user_id=user_id,
                    question_id=question_id,
                    recording_id=recording.id,
                    transcript=transcript,
                    session_id=session_id,
                    stage=attempt_stage,
                )

                db.add(attempt)
                db.flush()

                # -------------------------
                # ANALYSIS SAVE
                # -------------------------
                score = int(
                    round(
                        float(
                            analysis_payload.get(
                                "overall_score",
                                0
                            )
                        ) * 10
                    )
                )

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

                # -------------------------
                # CACHE INITIAL
                # -------------------------
                if attempt_stage == AttemptStage.INITIAL:

                    await async_redis_client.set(
                        f"attempt_result:{job.id}",
                        json.dumps(
                            {
                                "id": analysis.id,
                                "attempt_id": analysis.attempt_id,
                                "score": analysis.score,
                                "feedback": analysis.feedback,
                                "voice_metrics": analysis_payload.get("voice_metrics"),
                                "raw_analysis_json": analysis.raw_analysis_json,
                                "created_at": analysis.created_at.isoformat(),
                            },
                            default=str,
                        ),
                        ex=3600,
                    )

                # -------------------------
                # CACHE FINAL REPORT
                # -------------------------
                if attempt_stage == AttemptStage.FINAL:

                    initial_attempt = db.exec(
                        select(Attempt)
                        .where(
                            Attempt.session_id == session_id,
                            Attempt.stage == AttemptStage.INITIAL,
                        )
                        .options(
                            selectinload(
                                Attempt.analysis
                            )
                        )
                    ).first()

                    if (
                        initial_attempt
                        and initial_attempt.analysis
                    ):

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

                print(f"Job {job_id} completed")

            except Exception:

                traceback.print_exc()

                db.rollback()

                failed_job = db.get(Job, job_id)

                if failed_job:
                    failed_job.status = "failed"
                    db.add(failed_job)
                    db.commit()


async def worker():

    print("Worker started...")

    while True:

        try:

            job_data = await async_redis_client.blpop(
                TRANSCRIPTION,
                timeout=30,
            )

            if not job_data:
                continue

            _, raw_payload = job_data

            payload = json.loads(raw_payload)

            asyncio.create_task(
                process_job(payload)
            )

        except Exception:

            traceback.print_exc()

            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(worker())