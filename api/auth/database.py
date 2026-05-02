"""
api/auth/database.py — Conexión SQLite para autenticación de usuarios
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

from api.auth.models import USER_SCHEMA
from api.auth.crypto import encrypt, decrypt

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "alphahunter.db",
)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea la tabla de usuarios si no existe."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _get_connection() as conn:
        conn.execute(USER_SCHEMA)
        conn.commit()
    print(f"[Auth DB] Inicializada en {DB_PATH}")


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    return dict(row)


def _decrypt_user_keys(user: Optional[dict]) -> Optional[dict]:
    if user:
        if user.get("alpaca_api_key"):
            user["alpaca_api_key"] = decrypt(user["alpaca_api_key"])
        if user.get("alpaca_secret_key"):
            user["alpaca_secret_key"] = decrypt(user["alpaca_secret_key"])
    return user


def get_user_by_google_id(google_id: str) -> Optional[dict]:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
    return _decrypt_user_keys(_row_to_dict(row))


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _decrypt_user_keys(_row_to_dict(row))


def create_user(google_id: str, email: str, name: str, picture: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (google_id, email, name, picture, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (google_id, email, name, picture, now, now),
        )
        conn.commit()
        user_id = cursor.lastrowid

    return get_user_by_id(user_id)


def update_last_login(user_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (now, user_id)
        )
        conn.commit()


def update_alpaca_keys(
    user_id: int, api_key: str, secret_key: str, base_url: str
) -> bool:
    enc_api = encrypt(api_key)
    enc_secret = encrypt(secret_key)
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET alpaca_api_key = ?, alpaca_secret_key = ?, alpaca_base_url = ?
            WHERE id = ?
            """,
            (enc_api, enc_secret, base_url, user_id),
        )
        conn.commit()
    return True
