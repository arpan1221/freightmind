import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Required for SQLite
)

SessionLocal = sessionmaker(engine, autocommit=False, autoflush=False)

Base = declarative_base()


def init_db() -> None:
    """Create all tables and indexes. No-op if they already exist."""
    # Models must be imported before this call so Base.metadata knows about them.
    # Imports happen in app/main.py before init_db() is called.
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
    logger.info("Database schema initialised (create_all complete)")


def get_db():
    """FastAPI dependency: yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
