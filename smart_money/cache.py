"""
Cache simple en archivo JSON para evitar scraping en cada request.
"""

import json
import os
import time
from typing import Any

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "smart_money_cache.json")

CACHE_TTL = {
    "congress": 3600,    # 1 hora
    "whales": 86400,     # 24 horas (13F es trimestral)
    "options": 900,      # 15 minutos
}


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_cached(key: str) -> Any | None:
    """Retorna datos cacheados si existen y no han expirado. None si expiró o no existe."""
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None

    source = key.split(":")[0]  # 'congress', 'whales', 'options'
    ttl = CACHE_TTL.get(source, 3600)
    age = time.time() - entry.get("timestamp", 0)

    if age > ttl:
        print(f"[cache] MISS (expirado {age:.0f}s > {ttl}s): {key}")
        return None

    print(f"[cache] HIT ({age:.0f}s de antigüedad): {key}")
    return entry.get("data")


def set_cached(key: str, data: Any) -> None:
    """Guarda datos en cache con timestamp actual."""
    cache = _load_cache()
    cache[key] = {
        "timestamp": time.time(),
        "data": data,
    }
    _save_cache(cache)
    print(f"[cache] SET: {key} ({len(data) if isinstance(data, list) else 1} items)")


def invalidate(key: str) -> None:
    """Elimina una entrada del cache."""
    cache = _load_cache()
    if key in cache:
        del cache[key]
        _save_cache(cache)
