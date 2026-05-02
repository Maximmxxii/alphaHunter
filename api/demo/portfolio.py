"""
api/demo/portfolio.py — Portafolio demo ficticio pero realista.

Persiste en data/demo_portfolios.json: { user_id: { cash, positions, orders, history } }
Capital inicial: $25,000
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

DEMO_INITIAL_CASH = 25_000.0

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
_PORTFOLIOS_FILE = os.path.join(_DATA_DIR, "demo_portfolios.json")


# ── Persistencia ──────────────────────────────────────────────────────────────

def _load_all() -> dict:
    """Carga el JSON de todos los portafolios demo."""
    if not os.path.exists(_DATA_DIR):
        os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.exists(_PORTFOLIOS_FILE):
        return {}
    try:
        with open(_PORTFOLIOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    """Guarda el JSON de todos los portafolios demo."""
    if not os.path.exists(_DATA_DIR):
        os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_PORTFOLIOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_current_price(symbol: str) -> float:
    """Obtiene el precio actual de un símbolo vía yfinance."""
    try:
        import yfinance as yf
        fast = yf.Ticker(symbol).fast_info
        return float(fast.last_price)
    except Exception:
        return 0.0


def _get_company_name(symbol: str) -> str:
    """Obtiene el nombre de la empresa vía yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol


def _build_initial_portfolio() -> dict:
    """
    Crea el portafolio inicial con 2 posiciones de ejemplo:
    - MSFT: 2 acciones compradas hace 3 días (ligero profit)
    - NVDA: 1 acción comprada hace 1 día (ligera pérdida)
    """
    now = datetime.utcnow()

    msft_price = _get_current_price("MSFT")
    nvda_price = _get_current_price("NVDA")

    # MSFT: precio de entrada ligeramente inferior → ganancia
    msft_entry = round(msft_price * 0.975, 2) if msft_price > 0 else 400.0
    # NVDA: precio de entrada ligeramente superior → pérdida pequeña
    nvda_entry = round(nvda_price * 1.012, 2) if nvda_price > 0 else 850.0

    msft_qty = 2.0
    nvda_qty = 1.0

    positions = [
        {
            "symbol": "MSFT",
            "qty": msft_qty,
            "avg_entry_price": msft_entry,
            "sl_price": round(msft_entry * 0.95, 2),
            "tp_price": round(msft_entry * 1.20, 2),
            "opened_at": (now - timedelta(days=3)).isoformat() + "Z",
        },
        {
            "symbol": "NVDA",
            "qty": nvda_qty,
            "avg_entry_price": nvda_entry,
            "sl_price": round(nvda_entry * 0.95, 2),
            "tp_price": round(nvda_entry * 1.20, 2),
            "opened_at": (now - timedelta(days=1)).isoformat() + "Z",
        },
    ]

    # Descontar el costo de las posiciones iniciales del cash
    spent = msft_entry * msft_qty + nvda_entry * nvda_qty
    cash = round(DEMO_INITIAL_CASH - spent, 2)

    return {
        "cash": cash,
        "positions": positions,
        "orders": [],
        "history": [],
        "created_at": now.isoformat() + "Z",
    }


def _get_portfolio(user_id: str) -> tuple[dict, dict]:
    """Retorna (all_portfolios, user_portfolio). Crea si no existe."""
    all_data = _load_all()
    if user_id not in all_data:
        all_data[user_id] = _build_initial_portfolio()
        _save_all(all_data)
    return all_data, all_data[user_id]


# ── API pública ───────────────────────────────────────────────────────────────

def get_demo_account(user_id: str) -> dict:
    """
    Retorna cuenta demo del usuario.
    Si no existe, inicializa con $25,000 y 2 posiciones de ejemplo.
    Mismo formato que get_account() de Alpaca:
    { equity, cash, buying_power, pl_today, pl_today_pct, pl_total, pl_total_pct }
    """
    _, portfolio = _get_portfolio(user_id)

    cash = portfolio["cash"]
    positions = portfolio["positions"]

    # Calcular market value de posiciones con precios actuales
    market_value = 0.0
    for pos in positions:
        price = _get_current_price(pos["symbol"])
        market_value += price * pos["qty"]

    equity = round(cash + market_value, 2)

    # P&L total: equity vs capital inicial
    pl_total = round(equity - DEMO_INITIAL_CASH, 2)
    pl_total_pct = round((pl_total / DEMO_INITIAL_CASH) * 100, 2)

    # P&L de hoy: simplificado — usamos 0 si no hay snapshot anterior
    pl_today = round(pl_total * 0.3, 2)  # aproximación demo
    pl_today_pct = round((pl_today / DEMO_INITIAL_CASH) * 100, 2)

    return {
        "equity": equity,
        "cash": round(cash, 2),
        "buying_power": round(cash, 2),
        "pl_today": pl_today,
        "pl_today_pct": pl_today_pct,
        "pl_total": pl_total,
        "pl_total_pct": pl_total_pct,
        "is_demo": True,
        "configured": True,
    }


def get_demo_positions(user_id: str) -> list[dict]:
    """
    Retorna posiciones demo del usuario.
    Si no existe, retorna 2 posiciones de ejemplo: MSFT y NVDA.
    Mismo formato que get_positions() de Alpaca.
    Los precios actuales los obtiene de yfinance en tiempo real.
    """
    _, portfolio = _get_portfolio(user_id)

    result = []
    for pos in portfolio["positions"]:
        symbol = pos["symbol"]
        entry = float(pos["avg_entry_price"])
        qty = float(pos["qty"])

        current_price = _get_current_price(symbol)
        if current_price <= 0:
            current_price = entry  # fallback

        unrealized_pl = round((current_price - entry) * qty, 2)
        unrealized_plpc = round(((current_price - entry) / entry) * 100, 2) if entry > 0 else 0.0

        name = _get_company_name(symbol)

        result.append({
            "symbol": symbol,
            "name": name,
            "qty": qty,
            "avg_entry_price": round(entry, 2),
            "current_price": round(current_price, 2),
            "unrealized_pl": unrealized_pl,
            "unrealized_plpc": unrealized_plpc,
            "sl_price": round(float(pos["sl_price"]), 2),
            "tp_price": round(float(pos["tp_price"]), 2),
            "trailing_floor": round(float(pos["sl_price"]), 2),
            "opened_at": pos.get("opened_at", ""),
        })

    return result


def execute_demo_entry(user_id: str, symbol: str, amount_usd: float) -> dict:
    """
    Simula una entrada: descuenta el cash, agrega la posición.
    Precio de entrada = precio actual de yfinance.
    SL = precio * 0.95, TP = precio * 1.20
    Retorna mismo formato que place_order() de Alpaca.
    """
    symbol = symbol.upper()
    all_data, portfolio = _get_portfolio(user_id)

    price = _get_current_price(symbol)
    if price <= 0:
        raise ValueError(f"No se pudo obtener precio de {symbol}")

    if amount_usd > portfolio["cash"]:
        raise ValueError(f"Fondos insuficientes. Cash disponible: ${portfolio['cash']:.2f}")

    qty = round(amount_usd / price, 4)
    sl_price = round(price * 0.95, 2)
    tp_price = round(price * 1.20, 2)
    cost = round(price * qty, 2)

    # Buscar si ya existe posición para este símbolo (avg-in)
    existing = next((p for p in portfolio["positions"] if p["symbol"] == symbol), None)
    if existing:
        old_qty = float(existing["qty"])
        old_entry = float(existing["avg_entry_price"])
        new_qty = round(old_qty + qty, 4)
        new_entry = round((old_entry * old_qty + price * qty) / new_qty, 2)
        existing["qty"] = new_qty
        existing["avg_entry_price"] = new_entry
        existing["sl_price"] = round(new_entry * 0.95, 2)
        existing["tp_price"] = round(new_entry * 1.20, 2)
    else:
        portfolio["positions"].append({
            "symbol": symbol,
            "qty": qty,
            "avg_entry_price": round(price, 2),
            "sl_price": sl_price,
            "tp_price": tp_price,
            "opened_at": datetime.utcnow().isoformat() + "Z",
        })

    portfolio["cash"] = round(portfolio["cash"] - cost, 2)

    order_id = f"demo_{symbol}_{int(datetime.utcnow().timestamp())}"
    order = {
        "id": order_id,
        "symbol": symbol,
        "side": "buy",
        "qty": qty,
        "amount_usd": round(amount_usd, 2),
        "entry_price": round(price, 2),
        "sl_price": sl_price,
        "tp_price": tp_price,
        "status": "filled",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    portfolio["orders"].append(order)

    all_data[user_id] = portfolio
    _save_all(all_data)

    return order


def close_demo_position(user_id: str, symbol: str) -> dict:
    """
    Cierra una posición demo: calcula P&L, devuelve cash, registra en historial.
    """
    symbol = symbol.upper()
    all_data, portfolio = _get_portfolio(user_id)

    pos = next((p for p in portfolio["positions"] if p["symbol"] == symbol), None)
    if pos is None:
        raise ValueError(f"No hay posición abierta para {symbol}")

    current_price = _get_current_price(symbol)
    if current_price <= 0:
        current_price = float(pos["avg_entry_price"])

    qty = float(pos["qty"])
    entry = float(pos["avg_entry_price"])
    pl = round((current_price - entry) * qty, 2)
    proceeds = round(current_price * qty, 2)

    # Registrar en historial
    history_entry = {
        "symbol": symbol,
        "qty": qty,
        "avg_entry_price": round(entry, 2),
        "close_price": round(current_price, 2),
        "pl": pl,
        "closed_at": datetime.utcnow().isoformat() + "Z",
        "opened_at": pos.get("opened_at", ""),
    }
    portfolio["history"].append(history_entry)

    # Devolver cash
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)

    # Remover posición
    portfolio["positions"] = [p for p in portfolio["positions"] if p["symbol"] != symbol]

    all_data[user_id] = portfolio
    _save_all(all_data)

    return {
        "status": "closed",
        "symbol": symbol,
        "close_price": round(current_price, 2),
        "qty": qty,
        "pl": pl,
        "proceeds": proceeds,
    }


def reset_demo(user_id: str) -> dict:
    """Resetea el portafolio demo a $25,000 con posiciones de ejemplo."""
    all_data = _load_all()
    all_data[user_id] = _build_initial_portfolio()
    _save_all(all_data)
    return {"reset": True, "user_id": user_id, "initial_cash": DEMO_INITIAL_CASH}
