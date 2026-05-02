"""
api/auth/models.py — Modelo de usuario para AlphaHunter

Tabla users:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  google_id       TEXT UNIQUE NOT NULL
  email           TEXT NOT NULL
  name            TEXT
  picture         TEXT
  alpaca_api_key  TEXT
  alpaca_secret_key TEXT
  alpaca_base_url TEXT
  created_at      TEXT
  last_login      TEXT
"""

# Schema de referencia — la tabla se crea en database.py
USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    google_id         TEXT UNIQUE NOT NULL,
    email             TEXT NOT NULL,
    name              TEXT,
    picture           TEXT,
    alpaca_api_key    TEXT,
    alpaca_secret_key TEXT,
    alpaca_base_url   TEXT DEFAULT 'https://paper-api.alpaca.markets',
    created_at        TEXT NOT NULL,
    last_login        TEXT NOT NULL
)
"""
