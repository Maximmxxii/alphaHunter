"""
utils/trade_journal.py — Historial persistente de trades de AlphaHunter

Formato de cada trade en data/trade_journal.json:
{
    "id":               "AAPL_20260412_143522",
    "ticker":           "AAPL",
    "screener_strategy":"exploratorio",
    "entry_time":       "2026-04-12 14:35:22",
    "entry_price":      175.40,
    "qty":              28,
    "monto_usd":        4911.20,
    "ml_prob":          0.72,
    "stop_loss_pct":    7.0,
    "take_profit_pct":  15.0,
    "status":           "open" | "closed",
    "exit_time":        "2026-04-12 23:12:05",   # None si aún abierto
    "exit_price":       183.20,                   # None si aún abierto
    "exit_reason":      "take_profit" | "stop_loss" | "manual",
    "pnl_usd":          219.20,                   # None si aún abierto
    "pnl_pct":          4.47,                     # None si aún abierto
    "hold_hours":       8.61,                     # None si aún abierto
}
"""

import json
import os
from datetime import datetime
from typing import Optional

JOURNAL_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'trade_journal.json')


def _load() -> list[dict]:
    if not os.path.exists(JOURNAL_PATH):
        return []
    with open(JOURNAL_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save(trades: list[dict]) -> None:
    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    with open(JOURNAL_PATH, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────

def record_entry(
    ticker: str,
    screener_strategy: str,
    entry_price: float,
    qty: int,
    monto_usd: float,
    ml_prob: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> str:
    """Registra la apertura de una posición. Retorna el ID del trade."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    trade = {
        "id":                trade_id,
        "ticker":            ticker,
        "screener_strategy": screener_strategy,
        "entry_time":        ts,
        "entry_price":       round(entry_price, 4),
        "qty":               qty,
        "monto_usd":         round(monto_usd, 2),
        "ml_prob":           round(ml_prob, 4),
        "stop_loss_pct":     stop_loss_pct,
        "take_profit_pct":   take_profit_pct,
        "status":            "open",
        "exit_time":         None,
        "exit_price":        None,
        "exit_reason":       None,
        "pnl_usd":           None,
        "pnl_pct":           None,
        "hold_hours":        None,
    }

    trades = _load()
    trades.append(trade)
    _save(trades)
    return trade_id


def record_exit(
    ticker: str,
    exit_price: float,
    exit_reason: str,   # "take_profit" | "stop_loss" | "manual"
) -> Optional[dict]:
    """
    Cierra el trade abierto más reciente para ese ticker.
    Retorna el trade actualizado o None si no se encontró.
    """
    trades = _load()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Buscar el trade abierto más reciente para este ticker
    target = None
    for t in reversed(trades):
        if t["ticker"] == ticker and t["status"] == "open":
            target = t
            break

    if target is None:
        return None

    entry_dt = datetime.strptime(target["entry_time"], "%Y-%m-%d %H:%M:%S")
    exit_dt  = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    hold_h   = (exit_dt - entry_dt).total_seconds() / 3600

    pnl_pct = ((exit_price - target["entry_price"]) / target["entry_price"]) * 100
    pnl_usd = pnl_pct / 100 * target["monto_usd"]

    target["status"]      = "closed"
    target["exit_time"]   = ts
    target["exit_price"]  = round(exit_price, 4)
    target["exit_reason"] = exit_reason
    target["pnl_usd"]     = round(pnl_usd, 2)
    target["pnl_pct"]     = round(pnl_pct, 4)
    target["hold_hours"]  = round(hold_h, 2)

    _save(trades)
    return target


def get_all_trades() -> list[dict]:
    return _load()


def get_open_trades() -> list[dict]:
    return [t for t in _load() if t["status"] == "open"]


def get_closed_trades() -> list[dict]:
    return [t for t in _load() if t["status"] == "closed"]


# ─────────────────────────────────────────────
# Estadísticas
# ─────────────────────────────────────────────

def sync_from_alpaca(after: str = None, screener_strategy: str = "desconocido") -> dict:
    """
    Sincroniza el historial de trades desde Alpaca usando fills reales.

    Algoritmo FIFO por ticker:
        - Agrupa todos los fills por símbolo
        - Ordena cronológicamente
        - Empareja cada BUY con el SELL siguiente (FIFO)
        - Calcula P&L real con precios de ejecución de Alpaca
        - Inserta en el journal evitando duplicados (por alpaca_fill_id)

    Args:
        after:             ISO timestamp para filtrar desde esa fecha.
                           Ej: '2026-04-12T00:00:00Z'
                           Si es None, trae los últimos 500 fills.
        screener_strategy: Estrategia a asignar a los trades importados
                           (Alpaca no guarda esta info — ponerla manualmente si se sabe).

    Retorna:
        {"importados": N, "ya_existian": M, "abiertos": K}
    """
    from utils.alpaca import get_activities, alpaca_to_yf
    from collections import defaultdict

    activities = get_activities(activity_type="FILL", after=after)
    if not activities:
        return {"importados": 0, "ya_existian": 0, "abiertos": 0}

    # IDs ya registrados para no duplicar
    existing_trades = _load()
    existing_ids = {t.get("alpaca_fill_id") for t in existing_trades if t.get("alpaca_fill_id")}

    # Agrupar fills por símbolo y ordenar por tiempo ascendente
    by_symbol: dict = defaultdict(list)
    for a in activities:
        by_symbol[a["symbol"]].append(a)

    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda x: x["transaction_time"])

    importados = 0
    ya_existian = 0
    abiertos_count = 0

    for symbol, fills in by_symbol.items():
        yf_ticker = alpaca_to_yf(symbol)

        # Cola FIFO de compras pendientes de emparejar
        buy_queue: list[dict] = []

        for fill in fills:
            if fill["side"] == "buy":
                buy_queue.append(fill)

            elif fill["side"] == "sell" and buy_queue:
                buy_fill = buy_queue.pop(0)

                # ID compuesto para dedup
                fill_id = f"{buy_fill['id']}_{fill['id']}"
                if fill_id in existing_ids:
                    ya_existian += 1
                    continue

                # Parsear tiempos
                def _parse_ts(ts_str: str) -> str:
                    """Normaliza ISO timestamp a 'YYYY-MM-DD HH:MM:SS'."""
                    try:
                        from datetime import timezone
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        dt_local = dt.astimezone(tz=None).replace(tzinfo=None)
                        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        return ts_str[:19].replace("T", " ")

                entry_ts   = _parse_ts(buy_fill["transaction_time"])
                exit_ts    = _parse_ts(fill["transaction_time"])
                entry_price = buy_fill["price"]
                exit_price  = fill["price"]
                qty         = min(buy_fill["qty"], fill["qty"])
                monto_usd   = round(entry_price * qty, 2)

                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                pnl_usd = round(pnl_pct / 100 * monto_usd, 2)

                entry_dt = datetime.strptime(entry_ts, "%Y-%m-%d %H:%M:%S")
                exit_dt  = datetime.strptime(exit_ts,  "%Y-%m-%d %H:%M:%S")
                hold_h   = round((exit_dt - entry_dt).total_seconds() / 3600, 2)

                # Inferir razón de salida (heurística)
                if pnl_pct <= -5:
                    exit_reason = "stop_loss"
                elif pnl_pct >= 10:
                    exit_reason = "take_profit"
                else:
                    exit_reason = "manual"

                trade = {
                    "id":                f"{yf_ticker}_{datetime.strptime(entry_ts, '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d_%H%M%S')}",
                    "ticker":            yf_ticker,
                    "screener_strategy": screener_strategy,
                    "entry_time":        entry_ts,
                    "entry_price":       round(entry_price, 4),
                    "qty":               int(qty),
                    "monto_usd":         monto_usd,
                    "ml_prob":           None,
                    "stop_loss_pct":     None,
                    "take_profit_pct":   None,
                    "status":            "closed",
                    "exit_time":         exit_ts,
                    "exit_price":        round(exit_price, 4),
                    "exit_reason":       exit_reason,
                    "pnl_usd":           pnl_usd,
                    "pnl_pct":           round(pnl_pct, 4),
                    "hold_hours":        hold_h,
                    "alpaca_fill_id":    fill_id,
                    "source":            "alpaca_sync",
                }

                existing_trades.append(trade)
                existing_ids.add(fill_id)
                importados += 1

        # Compras sin emparejar = posiciones aún abiertas
        for buy_fill in buy_queue:
            fill_id = f"{buy_fill['id']}_open"
            if fill_id in existing_ids:
                ya_existian += 1
                continue

            entry_ts    = _parse_ts(buy_fill["transaction_time"])
            entry_price = buy_fill["price"]
            qty         = buy_fill["qty"]

            trade = {
                "id":                f"{yf_ticker}_{datetime.strptime(entry_ts, '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d_%H%M%S')}",
                "ticker":            yf_ticker,
                "screener_strategy": screener_strategy,
                "entry_time":        entry_ts,
                "entry_price":       round(entry_price, 4),
                "qty":               int(qty),
                "monto_usd":         round(entry_price * qty, 2),
                "ml_prob":           None,
                "stop_loss_pct":     None,
                "take_profit_pct":   None,
                "status":            "open",
                "exit_time":         None,
                "exit_price":        None,
                "exit_reason":       None,
                "pnl_usd":           None,
                "pnl_pct":           None,
                "hold_hours":        None,
                "alpaca_fill_id":    fill_id,
                "source":            "alpaca_sync",
            }

            existing_trades.append(trade)
            existing_ids.add(fill_id)
            abiertos_count += 1

    _save(existing_trades)
    return {"importados": importados, "ya_existian": ya_existian, "abiertos": abiertos_count}


def compute_stats(trades: Optional[list[dict]] = None) -> dict:
    """
    Calcula estadísticas globales y por estrategia a partir de los trades cerrados.
    Si trades=None, carga desde el archivo.
    """
    if trades is None:
        trades = get_closed_trades()
    else:
        trades = [t for t in trades if t["status"] == "closed"]

    if not trades:
        return {"total": 0}

    pnls   = [t["pnl_pct"] for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    pnl_usd_total = sum(t["pnl_usd"] for t in trades)

    stats = {
        "total":          len(trades),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       round(len(wins) / len(trades) * 100, 1),
        "pnl_usd_total":  round(pnl_usd_total, 2),
        "avg_gain_pct":   round(sum(wins)   / len(wins)   if wins   else 0, 2),
        "avg_loss_pct":   round(sum(losses) / len(losses) if losses else 0, 2),
        "best_trade_pct": round(max(pnls), 2),
        "worst_trade_pct":round(min(pnls), 2),
        "avg_hold_hours": round(
            sum(t["hold_hours"] for t in trades if t["hold_hours"] is not None) / len(trades), 1
        ),
        "by_strategy":    _stats_by_strategy(trades),
    }
    return stats


def _stats_by_strategy(trades: list[dict]) -> dict:
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for t in trades:
        groups[t["screener_strategy"]].append(t)

    result = {}
    for strat, ts in groups.items():
        pnls = [t["pnl_pct"] for t in ts]
        wins = [p for p in pnls if p > 0]
        result[strat] = {
            "total":     len(ts),
            "wins":      len(wins),
            "win_rate":  round(len(wins) / len(ts) * 100, 1),
            "pnl_total": round(sum(t["pnl_usd"] for t in ts), 2),
            "avg_pnl":   round(sum(pnls) / len(pnls), 2),
        }
    return result
