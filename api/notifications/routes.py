"""
api/notifications/routes.py — Endpoints de push notifications

POST   /api/notifications/register-token    — registra token de dispositivo
DELETE /api/notifications/unregister-token  — elimina token de dispositivo
POST   /api/notifications/test              — envía notificación de prueba
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

from api.notifications.token_store import save_token, remove_token
from api.notifications.push_service import send_push

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    expo_token: str
    user_id:    str = "default"


class TestPayload(BaseModel):
    expo_token: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/notifications/register-token", tags=["Notifications"])
def register_token(payload: TokenPayload):
    """
    Registra el Expo push token de un dispositivo para un usuario.
    Llamar desde la app al obtener el token por primera vez o al renovarlo.
    """
    try:
        save_token(payload.user_id, payload.expo_token)
        return {"success": True, "message": f"Token registrado para usuario '{payload.user_id}'"}
    except Exception as e:
        logger.error(f"[Routes] Error guardando token: {e}")
        return {"success": False, "message": str(e)}


@router.delete("/notifications/unregister-token", tags=["Notifications"])
def unregister_token(payload: TokenPayload):
    """
    Elimina el token de un dispositivo (ej: al cerrar sesión o revocar permisos).
    """
    try:
        remove_token(payload.user_id, payload.expo_token)
        return {"success": True, "message": "Token eliminado"}
    except Exception as e:
        logger.error(f"[Routes] Error eliminando token: {e}")
        return {"success": False, "message": str(e)}


@router.post("/notifications/test", tags=["Notifications"])
def test_notification(payload: TestPayload):
    """
    Envía una notificación de prueba al dispositivo especificado.
    Útil para verificar que el token es válido y las notificaciones funcionan.
    """
    result = send_push(
        expo_token=payload.expo_token,
        title="⚡ AlphaHunter — Test",
        body="Las notificaciones push están funcionando correctamente.",
        data={"action": "test"},
    )

    if "error" in result:
        return {"success": False, "message": result["error"]}

    ticket = result.get("data", {})
    if ticket.get("status") == "error":
        return {"success": False, "message": ticket.get("message", "Error desconocido de Expo")}

    return {"success": True, "message": "Notificación de prueba enviada"}
