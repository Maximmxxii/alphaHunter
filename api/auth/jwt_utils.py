"""
api/auth/jwt_utils.py — Utilidades JWT para AlphaHunter
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET environment variable is required. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
    )
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET is too weak (< 32 characters). "
        "Generate a strong one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
    )
ALGORITHM = "HS256"
EXPIRE_HOURS = 24 * 7  # 7 días

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def create_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Retorna el payload si el token es válido, o None si es inválido/expirado."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — retorna el payload del JWT o lanza 401."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
