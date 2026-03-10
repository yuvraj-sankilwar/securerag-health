"""Database session factory with RLS context support."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Async engine using asyncpg
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def set_rls_context(session: AsyncSession, user_id: str, role_name: str, tenant_id: str) -> None:
    """
    Set Row-Level Security context for the current transaction.

    This MUST be called within the same transaction as any query touching
    document_chunks or documents tables. Uses SET LOCAL so the settings
    are automatically reverted when the transaction ends.
    """
    await session.execute(text(f"SET LOCAL app.user_id = '{user_id}'"))
    await session.execute(text(f"SET LOCAL app.role_name = '{role_name}'"))
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def get_db() -> AsyncSession:
    """Async dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
