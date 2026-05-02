"""
api/auth/google.py — Verificación de ID tokens de Google
"""

import os
import requests
from fastapi import HTTPException, status

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
EXPECTED_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


def verify_google_token(id_token: str) -> dict:
    """
    Verifica el ID token de Google usando la API pública de Google.
    Retorna: { sub, email, name, picture } o lanza HTTPException 401.
    """
    try:
        resp = requests.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token},
            timeout=10,
        )
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo contactar a Google: {str(e)}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido",
        )

    data = resp.json()

    # Verify audience if configured
    if EXPECTED_CLIENT_ID and data.get("aud") != EXPECTED_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido (audience mismatch)",
        )

    # Campos requeridos
    sub = data.get("sub")
    email = data.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google no contiene campos requeridos",
        )

    return {
        "sub": sub,
        "email": email,
        "name": data.get("name", email.split("@")[0]),
        "picture": data.get("picture", ""),
    }
