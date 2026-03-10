"""RLS policy helper utilities."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_rls_context


@asynccontextmanager
async def rls_transaction(session: AsyncSession, user_id: str, role_name: str, tenant_id: str):
    """
    Context manager that sets RLS context within a transaction.

    Usage:
        async with rls_transaction(session, user_id, role_name, tenant_id):
            result = await session.execute(query)

    The SET LOCAL statements are automatically scoped to the transaction,
    ensuring they are reverted when the context manager exits.
    """
    async with session.begin():
        await set_rls_context(session, user_id, role_name, tenant_id)
        yield session
