"""
Almacena los Expo push tokens de cada usuario.
Persiste en data/push_tokens.json: { user_id: [token1, token2] }
Un usuario puede tener múltiples dispositivos.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
TOKENS_FILE = os.path.join(DATA_DIR, 'push_tokens.json')


def _load() -> dict:
    """Carga tokens desde disco. Retorna {} si no existe o está corrupto."""
    if not os.path.exists(TOKENS_FILE):
        return {}
    try:
        with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[TokenStore] Error leyendo tokens: {e}")
        return {}


def _save(data: dict) -> None:
    """Persiste tokens en disco."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def save_token(user_id: str, expo_token: str) -> None:
    """
    Guarda un token para el usuario. Si ya existe, no lo duplica.

    Args:
        user_id:    Identificador del usuario (email o "default")
        expo_token: Token Expo del dispositivo
    """
    if not expo_token or not expo_token.startswith("ExponentPushToken"):
        logger.warning(f"[TokenStore] Token inválido ignorado: {expo_token!r}")
        return

    data = _load()
    tokens = data.get(user_id, [])

    if expo_token not in tokens:
        tokens.append(expo_token)
        data[user_id] = tokens
        _save(data)
        logger.info(f"[TokenStore] Token guardado para usuario '{user_id}'")
    else:
        logger.debug(f"[TokenStore] Token ya registrado para '{user_id}'")


def get_tokens(user_id: str) -> list[str]:
    """
    Retorna todos los tokens activos de un usuario.

    Args:
        user_id: Identificador del usuario

    Returns:
        Lista de tokens (vacía si el usuario no tiene tokens)
    """
    data = _load()
    return data.get(user_id, [])


def remove_token(user_id: str, expo_token: str) -> None:
    """
    Elimina un token de un usuario (ej: al desinstalar la app o revocar permisos).

    Args:
        user_id:    Identificador del usuario
        expo_token: Token a eliminar
    """
    data = _load()
    tokens = data.get(user_id, [])

    if expo_token in tokens:
        tokens.remove(expo_token)
        if tokens:
            data[user_id] = tokens
        else:
            # Si no quedan tokens, eliminar la entrada del usuario
            data.pop(user_id, None)
        _save(data)
        logger.info(f"[TokenStore] Token eliminado para usuario '{user_id}'")
    else:
        logger.debug(f"[TokenStore] Token no encontrado para '{user_id}'")


def get_all_tokens() -> dict:
    """
    Retorna todos los tokens registrados.

    Returns:
        { user_id: [token1, token2, ...], ... }
    """
    return _load()
