import json

from app.core.redis import redis_client, ANALYSIS_QUEUE
from sqlmodel import Session

from app.db.postgran import engine
from app.models.job import Job
from app.models.training import TrainingAnalysis
from app.services.ai_service import mock_ai_beveviral_analysis


while True:

    print("Worker started...")

    job_data = redis_client.blpop(ANALYSIS_QUEUE)
    if not job_data:
        continue
    
    print(redis_client.llen(ANALYSIS_QUEUE))
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
            question_text = str(payload["question_text"])
            transcript = str(payload["transcript"])
            attempt_id = int(payload["attempt_id"])
            training_attempt_id = int(payload["training_attempt_id"])
         

            print(f"Processing job {job_id} for user {user_id}, question {question_id}")
            print(f"AI analysis for transcript: {transcript}")


            analysis_payload = mock_ai_beveviral_analysis(
                transcript=transcript,
                question=question_text,
            )

            score = int(round(float(analysis_payload.get("overall_Behevioral_score", analysis_payload.get("overall_score", 0.0))) * 10))
            passed = bool(analysis_payload.get("pass", analysis_payload.get("passed", score >= 60)))
            feedback = str(
                analysis_payload.get(
                    "short_feedback",
                    "Behavioral analysis completed for the submitted answer.",
                )
            )

            analysis = TrainingAnalysis(
                training_attempt_id=training_attempt_id,
                score=score,
                passed=passed,
                feedback=feedback,
                raw_analysis_json=analysis_payload,
            )
            db.add(analysis)

   

            job_entry.status = "done"
            job_entry.attempt_id = attempt_id
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


