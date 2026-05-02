"""
utils/trailing_monitor.py — Monitor de trailing stops para posiciones abiertas

Se ejecuta cada 5 minutos durante horario de mercado.

Para posiciones que no usan órdenes nativas de trailing stop de Alpaca,
este monitor:
    1. Revisa el precio actual vs el floor guardado por posición
    2. Si el precio subió por encima de (floor / (1 - trail_pct/100)), sube el floor
    3. Si el precio cayó al nivel del floor o por debajo, cierra la posición

Los floors se persisten en data/trailing_floors.json con el formato:
    {
        "AAPL": {
            "floor": 175.30,
            "entry_price": 170.00,
            "updated_at": "2026-04-13T12:00:00"
        },
        ...
    }
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from datetime import datetime

try:
    from api.notifications.triggers import notify_stop_loss, notify_trailing_floor_update
    _NOTIFICATIONS_ENABLED = True
except ImportError:
    _NOTIFICATIONS_ENABLED = False

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
FLOORS_FILE = os.path.join(DATA_DIR, 'trailing_floors.json')


def _load_floors() -> dict:
    """Carga floors guardados desde disco. Retorna {} si no existe."""
    if not os.path.exists(FLOORS_FILE):
        return {}
    try:
        with open(FLOORS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_floors(floors: dict) -> None:
    """Persiste floors en disco."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FLOORS_FILE, 'w', encoding='utf-8') as f:
        json.dump(floors, f, indent=2)


def get_trailing_floors() -> dict:
    """
    Retorna el estado actual de todos los trailing floors.

    Retorna:
        { symbol: floor_price, ... }
    """
    floors = _load_floors()
    return {sym: data["floor"] for sym, data in floors.items()}


def update_trailing_floors(trail_pct: float = 5.0) -> list[dict]:
    """
    Actualiza el trailing stop para todas las posiciones abiertas.

    Para cada posición:
        - Calcula nuevo floor candidato = current_price * (1 - trail_pct/100)
        - Si ese floor es mayor que el floor guardado → sube el floor
        - Si current_price <= floor guardado → cierra la posición (stop activado)
        - Si la posición no tiene floor registrado, inicializa desde avg_entry_price

    Persiste los floors en data/trailing_floors.json.

    Retorna lista de acciones tomadas:
        [
            {"action": "floor_updated", "symbol": "AAPL", "old_floor": 170.0, "new_floor": 175.0},
            {"action": "stop_triggered", "symbol": "TSLA", "floor": 180.0, "price": 179.5},
            ...
        ]
    """
    from utils.alpaca import is_configured, get_positions, close_position
    from utils.trade_journal import record_exit

    if not is_configured():
        return []

    try:
        positions = get_positions()
    except Exception:
        return []

    floors  = _load_floors()
    actions = []
    ts_str  = datetime.now().isoformat(timespec='seconds')

    for pos in positions:
        symbol        = pos["symbol"]
        current_price = pos["current_price"]
        entry_price   = pos["avg_entry_price"]

        # Inicializar floor si no existe
        if symbol not in floors:
            initial_floor = round(entry_price * (1 - trail_pct / 100), 4)
            floors[symbol] = {
                "floor":       initial_floor,
                "entry_price": entry_price,
                "updated_at":  ts_str,
            }
            actions.append({
                "action":      "floor_initialized",
                "symbol":      symbol,
                "entry_price": entry_price,
                "floor":       initial_floor,
            })

        saved_floor = floors[symbol]["floor"]

        # ¿El precio cayó al floor o debajo? → cerrar
        if current_price <= saved_floor:
            try:
                close_position(symbol)
                actions.append({
                    "action": "stop_triggered",
                    "symbol": symbol,
                    "floor":  saved_floor,
                    "price":  current_price,
                })
                try:
                    record_exit(symbol, current_price, "trailing_stop")
                except Exception:
                    pass
                if _NOTIFICATIONS_ENABLED:
                    try:
                        pl_pct = (current_price - floors[symbol].get("entry_price", current_price)) / floors[symbol].get("entry_price", current_price) * 100
                        notify_stop_loss(symbol, pl_pct)
                    except Exception:
                        pass
                # Eliminar floor de la posición cerrada
                del floors[symbol]
                continue
            except Exception as e:
                actions.append({
                    "action": "close_error",
                    "symbol": symbol,
                    "error":  str(e),
                })
                continue

        # ¿Subió el precio? → actualizar floor si el nuevo floor > floor actual
        new_floor = round(current_price * (1 - trail_pct / 100), 4)
        if new_floor > saved_floor:
            old_floor = saved_floor
            floors[symbol]["floor"]      = new_floor
            floors[symbol]["updated_at"] = ts_str
            actions.append({
                "action":    "floor_updated",
                "symbol":    symbol,
                "old_floor": old_floor,
                "new_floor": new_floor,
                "price":     current_price,
            })
            if _NOTIFICATIONS_ENABLED:
                try:
                    notify_trailing_floor_update(symbol, new_floor, old_floor)
                except Exception:
                    pass

    # Limpiar floors de posiciones ya cerradas (no están en positions actuales)
    active_symbols = {p["symbol"] for p in positions}
    stale = [s for s in list(floors.keys()) if s not in active_symbols]
    for s in stale:
        del floors[s]

    _save_floors(floors)
    return actions
