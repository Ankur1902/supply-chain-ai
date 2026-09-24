"""
Database session management.

Two separate engines are maintained on purpose:
  - `engine` / `SessionLocal`: read-write, used by the application (API, services).
  - `readonly_engine` / `ReadOnlySessionLocal`: connects as a MySQL user that has
    been granted SELECT-only privileges. This is the ONLY connection the AI
    text-to-SQL / analytics layer is allowed to use. See docs/security.md.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Read-only engine for AI analytics / text-to-SQL. Uses a MySQL account that
# only has SELECT grants (enforced at the DB level, not just app level).
readonly_engine = create_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    execution_options={"postgresql_readonly": False},
)
ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_readonly_db() -> Generator[Session, None, None]:
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()
