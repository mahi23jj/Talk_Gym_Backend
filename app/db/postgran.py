"""Database package."""


from fastapi.params import Depends
from sqlmodel import create_engine , Session, SQLModel
from typing import Annotated, Optional

from app.core.config import settings


engine = create_engine(settings.postgres_url, pool_pre_ping=True)

def get_session() -> Session: # type: ignore
    """Get a new database session."""
    with Session(engine) as session:
        yield session

def init_db() -> None:
    """Initialize the database."""
    # Ensure model metadata is registered before creating tables.
    from app.models.auth import User  # noqa: F401
    from app.models.speaking import (  # noqa: F401
        AIAnalysis,
        ChatMessage,
        ChatSession,
        Question,
        Recording,
    )

    SQLModel.metadata.create_all(engine)


SessionType = Annotated[Session, Depends(get_session)]



