from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.postgran import get_session
from app.main import app
from app.models.auth import User
from app.models.question import Question, Recording
from app.services.auth import get_current_user
from app.services.interview import seed_training_followups


def _override_get_current_user() -> dict[str, str]:
    return {"username": "interview_user", "email": "interview@example.com"}



def test_interview_flow_end_to_end() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        seed_training_followups(session)
        user = User(username="interview_user", email="interview@example.com", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        question = Question(title="Tell me about a challenge", description="Describe a difficult situation and how you handled it.", day_unlock=1)
        session.add(question)
        session.commit()
        session.refresh(question)

        recording = Recording(
            user_id=user.id,
            question_id=question.id,
            audio_url="storage://audio-1",
            duration_seconds=42,
            size_bytes=12345,
        )
        session.add(recording)
        session.commit()
        session.refresh(recording)

        user_id = user.id
        question_id = question.id
        recording_id = recording.id

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app) as client:
        submit_response = client.post(
            "/api/v1/attempts/",
            json={
                "question_id": question_id,
                "recording_id": recording_id,
                "audio_input": "structure",
            },
        )
        assert submit_response.status_code == 200
        submit_body = submit_response.json()
        attempt_id = submit_body["attempt"]["id"]

        assert submit_body["training_session"]["training_mode"] == "structure_training"
        assert len(submit_body["training_session"]["followups"]) >= 2

        session_response = client.get(f"/api/v1/training/{attempt_id}")
        assert session_response.status_code == 200
        assert session_response.json()["training_mode"] == "structure_training"

        followups_response = client.get("/api/v1/followups/structure_training")
        assert followups_response.status_code == 200
        assert followups_response.json()["training_mode"] == "structure_training"
        assert len(followups_response.json()["followups"]) >= 2

        result_response = client.get(f"/api/v1/attempts/{attempt_id}")
        assert result_response.status_code == 200
        assert result_response.json()["analysis"]["primary_training_mode"] == "structure_training"

        final_response = client.post(
            f"/api/v1/attempts/{attempt_id}/final",
            json={
                "recording_id": recording_id,
                "audio_input": "behavior",
            },
        )
        assert final_response.status_code == 200
        assert "score_delta" in final_response.json()["progress_update"]

        progress_response = client.get(f"/api/v1/progress/{user_id}")
        assert progress_response.status_code == 200
        progress_body = progress_response.json()
        assert progress_body["user_id"] == user_id
        assert progress_body["total_attempts"] >= 2

    app.dependency_overrides.clear()
