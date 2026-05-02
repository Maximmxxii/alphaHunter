"""
Servicio de push notifications usando Expo Push API (gratuito).
No requiere cuenta de Apple Developer ni Google Firebase para desarrollo.
En producción con Expo EAS Build, funciona nativo en iOS y Android.
"""

import logging
import requests

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push(
    expo_token: str,
    title: str,
    body: str,
    data: dict = None,
    sound: str = "default",
    badge: int = None,
) -> dict:
    """
    Envía una notificación push via Expo Push API.

    Args:
        expo_token: Token del dispositivo, ej. "ExponentPushToken[xxxxx]"
        title:      Título de la notificación
        body:       Cuerpo del mensaje
        data:       Datos extra para la app (ej: {"symbol": "MSFT", "action": "sl_triggered"})
        sound:      Sonido a reproducir ("default" o None para silencioso)
        badge:      Número de badge para iOS

    Returns:
        dict con la respuesta de Expo o {"error": ...} si falla
    """
    if not expo_token or not expo_token.startswith("ExponentPushToken"):
        logger.warning(f"[Push] Token inválido: {expo_token!r}")
        return {"error": "invalid_token"}

    payload: dict = {
        "to":    expo_token,
        "title": title,
        "body":  body,
        "sound": sound,
    }
    if data:
        payload["data"] = data
    if badge is not None:
        payload["badge"] = badge

    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            json=payload,
            headers={
                "Accept":       "application/json",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        # Expo devuelve {"data": {"status": "ok"}} o {"data": {"status": "error", "message": ...}}
        ticket = result.get("data", {})
        if ticket.get("status") == "error":
            logger.warning(f"[Push] Expo rechazó la notificación: {ticket.get('message')}")
        else:
            logger.info(f"[Push] Enviado a {expo_token[:30]}... | {title}")

        return result

    except requests.exceptions.Timeout:
        logger.error("[Push] Timeout al contactar Expo Push API")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[Push] Error de conexión: {e}")
        return {"error": "connection_error"}
    except Exception as e:
        logger.error(f"[Push] Error inesperado: {e}")
        return {"error": str(e)}


def send_push_batch(notifications: list[dict]) -> list[dict]:
    """
    Envía múltiples notificaciones en batch (máx 100 por request).

    Cada elemento de `notifications` debe tener las mismas claves que
    los parámetros de send_push: to, title, body, [data], [sound], [badge].

    Returns:
        Lista de resultados (uno por notificación)
    """
    if not notifications:
        return []

    # Expo acepta hasta 100 por batch
    results = []
    for i in range(0, len(notifications), 100):
        chunk = notifications[i : i + 100]
        try:
            resp = requests.post(
                EXPO_PUSH_URL,
                json=chunk,
                headers={
                    "Accept":       "application/json",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            # Expo retorna {"data": [ticket1, ticket2, ...]} para batch
            tickets = data.get("data", [])
            results.extend(tickets)
            logger.info(f"[Push Batch] {len(chunk)} notificaciones enviadas")
        except Exception as e:
            logger.error(f"[Push Batch] Error en chunk {i}-{i+len(chunk)}: {e}")
            results.extend([{"error": str(e)}] * len(chunk))

    return results
