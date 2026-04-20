from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# ---------------------------------------------------------------------------
# Shared declarative base — all models (v0.1 + v1) register here so Alembic
# sees the full metadata in one place.
# ---------------------------------------------------------------------------
Base = declarative_base()


def _normalize(url: str, driver: str) -> str:
    """Normalize a DATABASE_URL to use the given SQLAlchemy driver.

    Accepts any of:
        postgres://...          (legacy heroku/railway shorthand)
        postgresql://...        (no driver — railway default)
        postgresql+asyncpg://...
        postgresql+psycopg2://...

    Returns a URL guaranteed to start with ``postgresql+{driver}://``.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return f"postgresql+{driver}://" + url[len(prefix):]
    if url.startswith("postgresql://"):
        return f"postgresql+{driver}://" + url[len("postgresql://"):]
    return url  # unknown shape — let SQLAlchemy complain


# ---------------------------------------------------------------------------
# Sync engine — used by v0.1 routes and Alembic (which needs psycopg2).
# ---------------------------------------------------------------------------
_sync_url = _normalize(settings.database_url, "psycopg2")
engine = create_engine(_sync_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async engine — used by v1 routes and services.
# ---------------------------------------------------------------------------
_async_url = _normalize(settings.database_url, "asyncpg")
async_engine = create_async_engine(_async_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session


# Convenience factory for worker tasks (no FastAPI dependency injection)
async_session_factory = AsyncSessionLocal
