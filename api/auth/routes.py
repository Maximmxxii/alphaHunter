"""
api/auth/routes.py — Endpoints de autenticación de AlphaHunter
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.auth.google import verify_google_token
from api.auth.database import (
    create_user,
    get_user_by_google_id,
    get_user_by_id,
    update_alpaca_keys,
    update_last_login,
)
from api.auth.jwt_utils import create_token, get_current_user
from api.limiter import limiter

router = APIRouter()


# ── Modelos ────────────────────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    id_token: str


class AlpacaKeysRequest(BaseModel):
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"


# ── Helpers ────────────────────────────────────────────────────────────────

def _user_response(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"],
        "has_alpaca": bool(user.get("alpaca_api_key")),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/auth/google")
@limiter.limit("5/minute")
def login_with_google(request: Request, body: GoogleLoginRequest):
    """
    Verifica el ID token de Google, busca o crea el usuario en la DB,
    y retorna un JWT propio junto con los datos del usuario.
    """
    google_data = verify_google_token(body.id_token)

    user = get_user_by_google_id(google_data["sub"])

    if user is None:
        user = create_user(
            google_id=google_data["sub"],
            email=google_data["email"],
            name=google_data["name"],
            picture=google_data["picture"],
        )
    else:
        update_last_login(user["id"])

    token = create_token(user["id"], user["email"])

    return {
        "token": token,
        "user": _user_response(user),
    }


@router.get("/auth/me")
def get_me(payload: dict = Depends(get_current_user)):
    """Retorna los datos del usuario autenticado a partir del JWT."""
    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return _user_response(user)


@router.post("/auth/alpaca-keys")
def save_alpaca_keys(
    body: AlpacaKeysRequest,
    payload: dict = Depends(get_current_user),
):
    """Guarda las API keys de Alpaca del usuario autenticado."""
    user_id = int(payload["sub"])
    success = update_alpaca_keys(
        user_id=user_id,
        api_key=body.api_key,
        secret_key=body.secret_key,
        base_url=body.base_url,
    )
    return {"success": success}


@router.post("/auth/logout")
def logout():
    """El cliente descarta el JWT — el servidor no necesita hacer nada."""
    return {"success": True}
