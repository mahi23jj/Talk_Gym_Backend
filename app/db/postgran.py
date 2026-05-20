"""Database package."""


from fastapi.params import Depends
from sqlmodel import create_engine , Session, SQLModel
from typing import Annotated, Optional

from app.core.config import settings




engine = create_engine(
    settings.postgres_url,

    pool_size=5,
    max_overflow=10,

    pool_pre_ping=True,
    pool_recycle=180,

    pool_timeout=30,

    connect_args={
        "sslmode": "require",
        "connect_timeout": 15,
    },
)

def get_session() -> Session: # type: ignore
    """Get a new database session."""
    with Session(engine) as session:
        yield session


SessionType = Annotated[Session, Depends(get_session)]



