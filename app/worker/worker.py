import json

from app.core.redis import redis_client, queue_name
from sqlmodel import Session

from app.db.postgran import engine
from app.models import (
    Recording,
    Attempt,
    InterviewAnalysis,
    TrainingRecommendation,
    TrainingProgress,
)
from app.models.job import Job
from app.models.enums import TrainingMode
from app.services.Ai_Transaltion import transcribe_audio_path
from app.services.ai_service import mock_ai_analysis
from app.services.traning_recomendation import select_training_mode


while True:

    job_data = redis_client.blpop(queue_name)
    if not job_data:
        continue

    try:
        payload = json.loads(job_data[1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Invalid queue payload: {exc}")
        continue

    job_id = payload.get("job_id")
    if job_id is None:
        print("Queue payload is missing job_id")
        continue

    with Session(engine) as db:
        job_entry = db.get(Job, int(job_id))
        if not job_entry:
            print(f"Job not found for id={job_id}")
            continue

        job_entry.status = "processing"
        db.add(job_entry)
        db.commit()

        try:
            user_id = int(payload["user_id"])
            question_id = int(payload["question_id"])
            question_title = str(payload["question_title"])
            question_description = str(payload["question_description"])
            audio_url = str(payload["audio_url"])
            duration_seconds = int(payload["duration_seconds"])
            size_bytes = int(payload["size_bytes"])

            transcript = transcribe_audio_path(audio_url)
            analysis_payload = mock_ai_analysis(
                transcript=transcript,
                question=f"{question_title}. {question_description}",
            )

            ordered_candidates = select_training_mode(analysis_payload)
            ordered_plan: list[TrainingMode] = []
            for mode in ordered_candidates:
                normalized = (
                    mode if isinstance(mode, TrainingMode) else TrainingMode(str(mode))
                )
                if normalized not in ordered_plan:
                    ordered_plan.append(normalized)

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

            attempt = Attempt(
                user_id=user_id,
                question_id=question_id,
                recording_id=recording.id,
                transcript=transcript,
            )
            db.add(attempt)
            db.flush()

            score = int(round(float(analysis_payload.get("overall_score", 0.0)) * 10))
            feedback = "Mock AI analysis completed for the submitted answer."

            analysis = InterviewAnalysis(
                attempt_id=attempt.id,
                score=score,
                feedback=feedback,
                raw_analysis_json=analysis_payload,
            )
            db.add(analysis)

            for priority, training_type in enumerate(ordered_plan, start=1):
                row = TrainingRecommendation(
                    attempt_id=attempt.id,
                    training_type=training_type,
                    priority=priority,
                )
                db.add(row)

            progress = TrainingProgress(
                attempt_id=attempt.id,
                current_priority=1,
                completed=False,
            )
            db.add(progress)

            job_entry.status = "done"
            job_entry.attempt_id = attempt.id
            db.add(job_entry)
            db.commit()
        except Exception as exc:
            print(f"Error occurred while processing job {job_id}: {exc}")
            db.rollback()
            failed_job = db.get(Job, int(job_id))
            if failed_job:
                failed_job.status = "failed"
                db.add(failed_job)
                db.commit()
            continue

        # return {
        #     "recording": recording,
        #     "attempt": attempt,
        #     "analysis": analysis,
        #     "recommendations": recommendations,
        #     "progress": progress,
        # }
