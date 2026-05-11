# import json

# from app.core.redis import async_redis_client, TRANSCRIPTION_QUEUE 
# from sqlmodel import Session

# from app.db.postgran import engine
# from app.models import (
#     Recording,
#     Attempt,
#     InterviewAnalysis,
#     TrainingRecommendation,
#     TrainingProgress,
# )
# from app.models.job import Job
# from app.models.enums import AttemptStage, TrainingMode
# from app.models.question import Question
# from app.services.Ai_Transaltion import transcribe_audio_path
# from app.services.ai_service import mock_ai_analysis
# from traning_recomendation import select_training_mode


# while True:

#     print("Worker started...")

#     job_data = async_redis_client.blpop(TRANSCRIPTION_QUEUE )
#     if not job_data:
#         continue
    
#     print(async_redis_client.llen(TRANSCRIPTION_QUEUE ))
#     try:
#         payload = json.loads(job_data[1].decode("utf-8"))
#     except (UnicodeDecodeError, json.JSONDecodeError) as exc:
#         print(f"Invalid queue payload: {exc}")
#         continue

#     job_id = payload.get("job_id")
#     if job_id is None:
#         print("Queue payload is missing job_id")
#         continue

#     with Session(engine) as db:
#         job_entry = db.get(Job, int(job_id))
#         if not job_entry:
#             print(f"Job not found for id={job_id}")
#             continue

#         job_entry.status = "processing"
#         db.add(job_entry)
#         db.commit()

#         try:
#             user_id = int(payload["user_id"])
#             question_id = int(payload["question_id"])
#             audio_url = str(payload["audio_url"])
#             duration_seconds = int(payload["duration_seconds"])
#             size_bytes = int(payload["size_bytes"])
#             stage = str(payload.get("stage", "initial"))
#             session_id = int(payload["session_id"])

#             question = db.get(Question, question_id)
#             if not question:
#                 raise ValueError(f"Question not found for id={question_id}")

#             print(f"Processing job {job_id} for user {user_id}, question {question_id}")

#             transcript_items = transcribe_audio_path(audio_url)
#             transcript = " ".join(item.get("sentence", "") for item in transcript_items).strip()

#             print(f"AI analysis for transcript: {transcript}")
#             analysis_payload = mock_ai_analysis(
#                 transcript=transcript_items,
#                 question=f"{question.title}. {question.description}",
#             )

#             ordered_candidates = select_training_mode(analysis_payload)
#             ordered_plan: list[TrainingMode] = []
#             for mode in ordered_candidates:
#                 normalized = (
#                     mode if isinstance(mode, TrainingMode) else TrainingMode(str(mode))
#                 )
#                 if normalized not in ordered_plan:
#                     ordered_plan.append(normalized)

#             recording = Recording(
#                 user_id=user_id,
#                 question_id=question_id,
#                 audio_url=audio_url,
#                 duration_seconds=duration_seconds,
#                 size_bytes=size_bytes,
#                 transcription=transcript,
#             )
#             db.add(recording)
#             db.flush()

#             stage_value = payload.get("stage", AttemptStage.INITIAL.value)
#             attempt_stage = (
#                 AttemptStage(stage_value)
#                 if stage_value in AttemptStage._value2member_map_
#                 else AttemptStage.INITIAL
#             )

#             attempt = Attempt(
#                 user_id=user_id,
#                 question_id=question_id,
#                 recording_id=recording.id,
#                 transcript=transcript,
#                 stage=attempt_stage,
#                 session_id = session_id
#             )
#             db.add(attempt)
#             db.flush()

#             score = int(round(float(analysis_payload.get("overall_score", 0.0)) * 10))
#             feedback = "Mock AI analysis completed for the submitted answer."

#             analysis = InterviewAnalysis(
#                 attempt_id=attempt.id,
#                 score=score,
#                 feedback=feedback,
#                 raw_analysis_json=analysis_payload,
#             )
#             db.add(analysis)
#             db.flush()

#             job_entry.status = "done"
#             job_entry.attempt_id = attempt.id
#             db.add(job_entry)
#             db.commit()
#         except Exception as exc:
#             print(f"Error occurred while processing job {job_id}: {exc}")
#             db.rollback()
#             failed_job = db.get(Job, int(job_id))
#             if failed_job:
#                 failed_job.status = "failed"
#                 db.add(failed_job)
#                 db.commit()
#             continue

#         # return {
#         #     "recording": recording,
#         #     "attempt": attempt,
#         #     "analysis": analysis,
#         #     "recommendations": recommendations,
#         #     "progress": progress,
#         # }

from __future__ import annotations

import asyncio
import json
import traceback

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.db.postgran import engine
from app.models.interview import (
    Job,
    Attempt,
    Recording,
    InterviewAnalysis,
    AttemptStage,
)
from app.models.question import Question
from app.core.redis import async_redis_client
from app.services.final_interview import build_interview_report
from app.services import (
    transcribe_audio_path,
    mock_ai_analysis,
    select_training_mode,
    TrainingMode,
)

TRANSCRIPTION_QUEUE = "transcription_queue"


async def process_job(payload: dict):

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

            # -----------------------------
            # Transcription
            # -----------------------------
            transcript_items = transcribe_audio_path(
                audio_url
            )

            transcript = " ".join(
                item.get("sentence", "")
                for item in transcript_items
            ).strip()

            # -----------------------------
            # AI analysis
            # -----------------------------
            analysis_payload = mock_ai_analysis(
                transcript=transcript_items,
                question=f"{question.title}. {question.description}",
            )

            ordered_candidates = select_training_mode(
                analysis_payload
            )

            ordered_plan: list[TrainingMode] = []

            for mode in ordered_candidates:
                normalized = (
                    mode
                    if isinstance(mode, TrainingMode)
                    else TrainingMode(str(mode))
                )

                if normalized not in ordered_plan:
                    ordered_plan.append(normalized)

            # -----------------------------
            # Save recording
            # -----------------------------
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

            # -----------------------------
            # Save attempt
            # -----------------------------
            attempt = Attempt(
                user_id=user_id,
                question_id=question_id,
                recording_id=recording.id,
                transcript=transcript,
                stage=attempt_stage,
                session_id=session_id,
            )

            db.add(attempt)
            db.flush()

            # -----------------------------
            # Save analysis
            # -----------------------------
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

            # -----------------------------
            # Finish job
            # -----------------------------
            job.status = "done"
            job.attempt_id = attempt.id

            db.add(job)
            db.commit()

            # ====================================================
            # CACHE INITIAL RESULT
            # ====================================================
            if attempt_stage == AttemptStage.INITIAL:
                await async_redis_client.set(
                    f"attempt_result:{job.id}",
                    json.dumps(
                        analysis,
                        default=str
                    ),
                    ex=3600,
                )

            # ====================================================
            # CACHE FINAL SESSION REPORT
            # ====================================================
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
                        json.dumps(
                            report,
                            default=str
                        ),
                        ex=3600,
                    )

            print(
                f"Job {job_id} completed"
            )

        except Exception as e:

            traceback.print_exc()

            db.rollback()

            failed_job = db.get(
                Job,
                job_id
            )

            if failed_job:
                failed_job.status = "failed"
                db.add(failed_job)
                db.commit()


async def worker():

    print("Worker started...")

    while True:

        try:

            job_data = await async_redis_client.blpop(
                TRANSCRIPTION_QUEUE
            )

            if not job_data:
                continue

            payload = json.loads(
                job_data[1]
            )

            asyncio.create_task(
                process_job(payload)
            )

        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(worker())