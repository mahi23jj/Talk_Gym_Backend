from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.db.postgran import get_session
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_signin_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/signin",
        json={
            "username": "mahi",
            "email": "mahi@example.com",
            "password": "strongpass1",
            "password_confirm": "strongpass1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_signin_duplicate_user_returns_400(client: TestClient) -> None:
    payload = {
        "username": "mahi",
        "email": "mahi@example.com",
        "password": "strongpass1",
        "password_confirm": "strongpass1",
    }

    first = client.post("/api/v1/auth/signin", json=payload)
    second = client.post("/api/v1/auth/signin", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == "User already exists"


def test_login_with_email_returns_token(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/signin",
        json={
            "username": "mahi",
            "email": "mahi@example.com",
            "password": "strongpass1",
            "password_confirm": "strongpass1",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "mahi@example.com",
            "password": "strongpass1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)


def test_login_with_invalid_password_returns_401(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/signin",
        json={
            "username": "mahi",
            "email": "mahi@example.com",
            "password": "strongpass1",
            "password_confirm": "strongpass1",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "mahi@example.com",
            "password": "wrongpass1",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
