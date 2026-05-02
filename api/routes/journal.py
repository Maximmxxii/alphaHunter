"""
api/routes/journal.py — Historial de trades y estadísticas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter

router = APIRouter()


@router.get("/journal")
def get_journal():
    """Historial de trades cerrados con P&L."""
    from utils.trade_journal import get_closed_trades
    try:
        trades = get_closed_trades()
    except Exception:
        trades = []

    result = []
    for t in trades:
        result.append({
            "id":               t.get("id"),
            "ticker":           t.get("ticker"),
            "entry_time":       t.get("entry_time"),
            "exit_time":        t.get("exit_time"),
            "entry_price":      _round(t.get("entry_price")),
            "exit_price":       _round(t.get("exit_price")),
            "qty":              t.get("qty"),
            "monto_usd":        _round(t.get("monto_usd")),
            "pnl_usd":          _round(t.get("pnl_usd")),
            "pnl_pct":          _round(t.get("pnl_pct")),
            "exit_reason":      t.get("exit_reason"),
            "strategy":         t.get("screener_strategy"),
            "hold_hours":       _round(t.get("hold_hours")),
        })

    return result


@router.get("/journal/stats")
def get_journal_stats():
    """Estadísticas agregadas del trade journal."""
    from utils.trade_journal import compute_stats
    try:
        stats = compute_stats()
    except Exception:
        return {
            "total_trades": 0,
            "win_rate":     0.0,
            "avg_profit":   0.0,
            "total_pl":     0.0,
            "avg_hold_hours": 0.0,
        }

    return {
        "total_trades":   int(stats.get("total_trades", 0)),
        "win_rate":       _round(stats.get("win_rate", 0.0)),
        "avg_profit":     _round(stats.get("avg_profit_pct", stats.get("avg_profit", 0.0))),
        "total_pl":       _round(stats.get("total_pnl_usd", stats.get("total_pl", 0.0))),
        "avg_hold_hours": _round(stats.get("avg_hold_hours", 0.0)),
        "best_trade":     _round(stats.get("best_trade_pct", stats.get("best_trade"))),
        "worst_trade":    _round(stats.get("worst_trade_pct", stats.get("worst_trade"))),
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _round(val, decimals: int = 2):
    """Redondea a 2 decimales si es número, sin crashear."""
    if val is None:
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return val
