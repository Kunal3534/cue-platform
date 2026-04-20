from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# ---------------------------------------------------------------------------
# Shared declarative base — all models (v0.1 + v1) register here so Alembic
# sees the full metadata in one place.
# ---------------------------------------------------------------------------
Base = declarative_base()

# ---------------------------------------------------------------------------
# Sync engine — used by v0.1 routes and Alembic (which needs psycopg2).
# Derive by swapping the asyncpg driver out if the URL was set for v1.
# ---------------------------------------------------------------------------
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
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
_async_url = settings.database_url.replace("+psycopg2", "+asyncpg")
async_engine = create_async_engine(_async_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session


# Convenience factory for worker tasks (no FastAPI dependency injection)
async_session_factory = AsyncSessionLocal
