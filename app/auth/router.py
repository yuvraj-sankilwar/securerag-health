"""Authentication router: /auth/register, /auth/login."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import create_access_token
from app.auth.models import Role, Tenant, User
from app.auth.schemas import (
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.

    - Validates role_name exists in the roles table
    - Finds or creates a tenant by department_code
    - Hashes password with bcrypt
    - Creates user record
    - Returns user_id, email, role_name, tenant_id
    """
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{request.email}' already exists",
        )

    # Validate role
    role_result = await db.execute(select(Role).where(Role.name == request.role_name.upper()))
    role = role_result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: '{request.role_name}'. Valid roles: PHYSICIAN, NURSE, RADIOLOGIST, "
            "PHARMACIST, PATIENT, LAB_TECHNICIAN, ADMINISTRATOR, COMPLIANCE_OFFICER",
        )

    # Find or create tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.department_code == request.department_code))
    tenant = tenant_result.scalars().first()
    if not tenant:
        tenant = Tenant(
            name=f"Department - {request.department_code}",
            department_code=request.department_code,
        )
        db.add(tenant)
        await db.flush()
        logger.info(f"Created new tenant for department_code='{request.department_code}'")

    # Create user
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role_id=role.id,
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    logger.info(f"Registered user '{request.email}' with role '{role.name}' in tenant '{tenant.department_code}'")

    return UserRegisterResponse(
        user_id=user.id,
        email=user.email,
        role_name=role.name,
        tenant_id=tenant.id,
    )


@router.post("/login", response_model=UserLoginResponse)
async def login_user(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and issue a JWT token.

    - Verifies email and password
    - Issues JWT with user_id, email, role_name, tenant_id
    - Returns access_token, token_type, role_name
    """
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Get role name
    role_result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = role_result.scalars().first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no assigned role",
        )

    # Create token
    access_token = create_access_token(
        data={
            "user_id": str(user.id),
            "email": user.email,
            "role_name": role.name,
            "tenant_id": str(user.tenant_id),
        }
    )

    logger.info(f"User '{user.email}' logged in with role '{role.name}'")

    return UserLoginResponse(
        access_token=access_token,
        token_type="bearer",
        role_name=role.name,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
