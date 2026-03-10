"""JWT token creation and verification."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.auth.schemas import TokenPayload
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token encoding user claims.

    Args:
        data: Dictionary with user_id, email, role_name, tenant_id

    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload with decoded claims

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        role_name: str = payload.get("role_name")
        tenant_id: str = payload.get("tenant_id")

        if user_id is None or email is None or role_name is None or tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing required claims",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenPayload(
            user_id=user_id,
            email=email,
            role_name=role_name,
            tenant_id=tenant_id,
            exp=payload.get("exp"),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenPayload:
    """
    FastAPI dependency that extracts and validates the current user from the JWT token.

    Usage:
        @router.get("/protected")
        async def protected_route(current_user: TokenPayload = Depends(get_current_user)):
            ...
    """
    return verify_token(token)
