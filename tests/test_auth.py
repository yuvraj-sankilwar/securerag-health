"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthRegister:
    """Tests for POST /auth/register."""

    async def test_register_valid_user(self, client: AsyncClient):
        """Test registering a new user with valid data."""
        response = await client.post(
            "/auth/register",
            json={
                "email": "test.newuser@hospital.com",
                "password": "SecurePass123",
                "full_name": "Test User",
                "role_name": "PHYSICIAN",
                "department_code": "TEST-001",
            },
        )
        # May return 201 (created) or 409 (already exists from previous test run)
        assert response.status_code in [201, 409]
        if response.status_code == 201:
            data = response.json()
            assert "user_id" in data
            assert data["email"] == "test.newuser@hospital.com"
            assert data["role_name"] == "PHYSICIAN"

    async def test_register_invalid_role(self, client: AsyncClient):
        """Test that registering with an invalid role name is rejected."""
        response = await client.post(
            "/auth/register",
            json={
                "email": "invalid.role@hospital.com",
                "password": "SecurePass123",
                "full_name": "Invalid Role User",
                "role_name": "NONEXISTENT_ROLE",
                "department_code": "TEST-001",
            },
        )
        assert response.status_code == 400
        assert "Invalid role" in response.json()["detail"]

    async def test_register_duplicate_email(self, client: AsyncClient):
        """Test that registering with a duplicate email is rejected."""
        # First registration
        await client.post(
            "/auth/register",
            json={
                "email": "duplicate@hospital.com",
                "password": "SecurePass123",
                "full_name": "First User",
                "role_name": "NURSE",
                "department_code": "TEST-001",
            },
        )
        # Second registration with same email
        response = await client.post(
            "/auth/register",
            json={
                "email": "duplicate@hospital.com",
                "password": "SecurePass123",
                "full_name": "Second User",
                "role_name": "NURSE",
                "department_code": "TEST-001",
            },
        )
        assert response.status_code == 409


@pytest.mark.asyncio
class TestAuthLogin:
    """Tests for POST /auth/login."""

    async def test_login_valid_credentials(self, client: AsyncClient):
        """Test logging in with valid demo credentials."""
        response = await client.post(
            "/auth/login",
            json={"email": "dr.smith@hospital.com", "password": "Demo@1234"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role_name"] == "PHYSICIAN"

    async def test_login_invalid_password(self, client: AsyncClient):
        """Test that invalid password is rejected."""
        response = await client.post(
            "/auth/login",
            json={"email": "dr.smith@hospital.com", "password": "WrongPassword"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test that nonexistent email is rejected."""
        response = await client.post(
            "/auth/login",
            json={"email": "nonexistent@hospital.com", "password": "Demo@1234"},
        )
        assert response.status_code == 401

    async def test_jwt_token_contains_claims(self, client: AsyncClient):
        """Test that the JWT token contains required claims."""
        from jose import jwt

        from app.config import settings

        response = await client.post(
            "/auth/login",
            json={"email": "dr.smith@hospital.com", "password": "Demo@1234"},
        )
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert "user_id" in payload
        assert "email" in payload
        assert "role_name" in payload
        assert "tenant_id" in payload
        assert "exp" in payload
        assert payload["email"] == "dr.smith@hospital.com"
        assert payload["role_name"] == "PHYSICIAN"
