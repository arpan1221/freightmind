import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Required for SQLite
)

SessionLocal = sessionmaker(engine, autocommit=False, autoflush=False)

Base = declarative_base()


_NEW_EXTRACTED_DOCUMENT_COLUMNS = [
    "ALTER TABLE extracted_documents ADD COLUMN hs_code TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN port_of_loading TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN port_of_discharge TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN incoterms TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN description_of_goods TEXT",
    # Multi-document support (Bill of Lading + Packing List)
    "ALTER TABLE extracted_documents ADD COLUMN document_type TEXT NOT NULL DEFAULT 'commercial_invoice'",
    "ALTER TABLE extracted_documents ADD COLUMN bl_number TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN vessel_name TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN container_numbers TEXT",
    "ALTER TABLE extracted_documents ADD COLUMN package_count INTEGER",
]

_NEW_VERIFICATION_COLUMNS = [
    # Batch verification: track which document each field came from
    "ALTER TABLE verification_fields ADD COLUMN source_document TEXT",
]


def init_db() -> None:
    """Create all tables and indexes. No-op if they already exist.

    Also runs safe ALTER TABLE migrations for columns added in Part 2.
    SQLite does not support IF NOT EXISTS for columns, so we suppress
    the duplicate-column error gracefully.
    """
    # Models must be imported before this call so Base.metadata knows about them.
    # Imports happen in app/main.py before init_db() is called.
    with engine.begin() as conn:
        Base.metadata.create_all(conn)

    # Part 2: migrate new columns onto existing tables
    with engine.begin() as conn:
        for stmt in _NEW_EXTRACTED_DOCUMENT_COLUMNS + _NEW_VERIFICATION_COLUMNS:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists — safe to ignore

    logger.info("Database schema initialised (create_all + Part 2 migrations complete)")


def get_db():
    """FastAPI dependency: yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
