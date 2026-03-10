"""Pydantic schemas for authentication endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    full_name: str = Field(..., description="Full name of the user")
    role_name: str = Field(..., description="Role name (e.g., PHYSICIAN, NURSE)")
    department_code: str = Field(..., description="Department code for tenant association")


class UserRegisterResponse(BaseModel):
    """Response body for user registration."""

    user_id: UUID
    email: str
    role_name: str
    tenant_id: UUID
    message: str = "User registered successfully"


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class UserLoginResponse(BaseModel):
    """Response body for user login."""

    access_token: str
    token_type: str = "bearer"
    role_name: str
    tenant_id: UUID
    user_id: UUID


class TokenPayload(BaseModel):
    """JWT token payload claims."""

    user_id: str
    email: str
    role_name: str
    tenant_id: str
    exp: Optional[int] = None
