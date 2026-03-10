"""Shared test fixtures for SecureRAG-Health tests."""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test environment variables before importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rag_app_user:apppass@localhost:5432/securerag")
os.environ.setdefault("DATABASE_SYNC_URL", "postgresql+psycopg2://rag_app_user:apppass@localhost:5432/securerag")
os.environ.setdefault("SPICEDB_ENDPOINT", "localhost:50051")
os.environ.setdefault("SPICEDB_PRESHARED_KEY", "dev-secret-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def login_as(client: AsyncClient, email: str, password: str = "Demo@1234") -> str:
    """
    Helper to login and return the access token.

    Args:
        client: Test HTTP client
        email: User email
        password: User password

    Returns:
        JWT access token string
    """
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    """Create Authorization headers from a token."""
    return {"Authorization": f"Bearer {token}"}
