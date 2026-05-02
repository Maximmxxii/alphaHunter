"""
utils/entry_manager.py — Gestión de entradas con protección automática

Flujo de una entrada:
    1. Validar: cuenta configurada, buying power suficiente, no está ya en cartera
    2. Calcular qty desde amount_usd y precio actual
    3. Colocar orden de compra (market)
    4. Al llenar: colocar trailing stop (trail_pct% de distancia)
    5. Al llenar: colocar take profit limit (precio * (1 + tp_pct/100))
    6. Registrar en trade_journal
    7. Retornar resumen completo al frontend
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.alpaca import (
    is_configured,
    get_account,
    get_positions,
    place_order_with_trailing_stop,
    yf_to_alpaca,
)
from utils.data_fetcher import get_ohlcv
from utils.trade_journal import record_entry

DEFAULT_SL_PCT    = 5.0   # Stop loss = 5% bajo precio de entrada (referencia)
DEFAULT_TP_PCT    = 20.0  # Take profit = 20% sobre precio de entrada
DEFAULT_TRAIL_PCT = 5.0   # Trailing stop sigue el precio con 5% de distancia


def execute_entry(
    symbol: str,
    amount_usd: float,
    strategy_name: str = "manual",
    sl_pct: float = DEFAULT_SL_PCT,
    tp_pct: float = DEFAULT_TP_PCT,
    trail_pct: float = DEFAULT_TRAIL_PCT,
) -> dict:
    """
    Ejecuta una entrada completa con protección automática.

    Args:
        symbol:        Ticker en formato yfinance (ej: 'AAPL', 'BTC-USD')
        amount_usd:    Monto en USD a invertir
        strategy_name: Nombre de la estrategia para el journal
        sl_pct:        % de stop loss (solo se usa para calcular sl_price en el resumen)
        tp_pct:        % de take profit sobre precio de entrada
        trail_pct:     % de trailing stop (distancia dinámica al máximo)

    Retorna:
        {
            "success":         bool,
            "symbol":          str,
            "qty":             int,
            "entry_price":     float,
            "sl_price":        float,   # precio * (1 - sl_pct/100) — referencia
            "tp_price":        float,   # precio * (1 + tp_pct/100)
            "trail_pct":       float,
            "amount_invested": float,
            "order_id":        str,
            "ts_order_id":     str,
            "tp_order_id":     str | None,
            "error":           str | None,
        }
    """
    result_base = {
        "success":         False,
        "symbol":          symbol,
        "qty":             0,
        "entry_price":     0.0,
        "sl_price":        0.0,
        "tp_price":        0.0,
        "trail_pct":       trail_pct,
        "amount_invested": 0.0,
        "order_id":        "",
        "ts_order_id":     "",
        "tp_order_id":     None,
        "error":           None,
    }

    # ── 1. Validar configuración ──────────────────────────────
    if not is_configured():
        result_base["error"] = "Alpaca no configurado: falta ALPACA_API_KEY o ALPACA_SECRET_KEY"
        return result_base

    # ── 2. Verificar buying power ─────────────────────────────
    try:
        account = get_account()
        buying_power = account["buying_power"]
    except Exception as e:
        result_base["error"] = f"No se pudo obtener cuenta: {e}"
        return result_base

    if buying_power < amount_usd:
        result_base["error"] = (
            f"Buying power insuficiente: ${buying_power:,.2f} < ${amount_usd:,.2f}"
        )
        return result_base

    # ── 3. Verificar que no está ya en cartera ────────────────
    alpaca_symbol = yf_to_alpaca(symbol)
    try:
        positions = get_positions()
        en_cartera = {p["symbol"] for p in positions}
        if alpaca_symbol.upper() in en_cartera:
            result_base["error"] = f"{symbol} ya está en cartera"
            return result_base
    except Exception:
        pass  # si falla, continuamos (no es crítico)

    # ── 4. Precio actual y cálculo de qty ─────────────────────
    try:
        df = get_ohlcv(symbol, period="5d")
        precio_actual = float(df["Close"].iloc[-1])
    except Exception as e:
        result_base["error"] = f"No se pudo obtener precio de {symbol}: {e}"
        return result_base

    qty = int(amount_usd / precio_actual)
    if qty < 1:
        result_base["error"] = (
            f"Monto ${amount_usd:.2f} insuficiente para 1 acción a ${precio_actual:.2f}"
        )
        return result_base

    sl_price = round(precio_actual * (1 - sl_pct / 100), 4)
    tp_price = round(precio_actual * (1 + tp_pct / 100), 4)
    amount_invested = round(qty * precio_actual, 2)

    # ── 5. Colocar orden con trailing stop ────────────────────
    try:
        order = place_order_with_trailing_stop(
            symbol=alpaca_symbol,
            qty=qty,
            trail_percent=trail_pct,
            take_profit_price=tp_price,
        )
    except Exception as e:
        result_base["error"] = f"Error colocando orden: {e}"
        return result_base

    entry_order = order["entry_order"]
    ts_order    = order["trailing_stop_order"]
    tp_order    = order.get("take_profit_order")

    # ── 6. Registrar en trade journal ─────────────────────────
    try:
        record_entry(
            ticker=symbol,
            screener_strategy=strategy_name,
            entry_price=precio_actual,
            qty=qty,
            monto_usd=amount_invested,
            ml_prob=None,
            stop_loss_pct=trail_pct,
            take_profit_pct=tp_pct,
        )
    except Exception:
        pass  # journal no es crítico

    return {
        "success":         True,
        "symbol":          symbol,
        "qty":             qty,
        "entry_price":     precio_actual,
        "sl_price":        sl_price,
        "tp_price":        tp_price,
        "trail_pct":       trail_pct,
        "amount_invested": amount_invested,
        "order_id":        entry_order["id"],
        "ts_order_id":     ts_order["id"],
        "tp_order_id":     tp_order["id"] if tp_order else None,
        "error":           None,
    }


def get_entry_preview(symbol: str, amount_usd: float) -> dict:
    """
    Preview de una entrada sin ejecutarla.
    Útil para mostrar en el frontend antes de confirmar.

    Retorna:
        {
            "symbol":          str,
            "amount_usd":      float,
            "current_price":   float,
            "qty":             int,
            "amount_invested": float,
            "sl_price":        float,   # precio * (1 - DEFAULT_SL_PCT/100)
            "tp_price":        float,   # precio * (1 + DEFAULT_TP_PCT/100)
            "trail_pct":       float,
            "risk_usd":        float,   # pérdida máxima estimada
            "reward_usd":      float,   # ganancia estimada al TP
            "risk_reward":     float,   # ratio reward/risk
            "error":           str | None,
        }
    """
    base = {
        "symbol":          symbol,
        "amount_usd":      amount_usd,
        "current_price":   0.0,
        "qty":             0,
        "amount_invested": 0.0,
        "sl_price":        0.0,
        "tp_price":        0.0,
        "trail_pct":       DEFAULT_TRAIL_PCT,
        "risk_usd":        0.0,
        "reward_usd":      0.0,
        "risk_reward":     0.0,
        "error":           None,
    }

    try:
        df = get_ohlcv(symbol, period="5d")
        precio = float(df["Close"].iloc[-1])
    except Exception as e:
        base["error"] = f"No se pudo obtener precio de {symbol}: {e}"
        return base

    qty = int(amount_usd / precio)
    if qty < 1:
        base["error"] = (
            f"Monto ${amount_usd:.2f} insuficiente para 1 acción a ${precio:.2f}"
        )
        return base

    amount_invested = round(qty * precio, 2)
    sl_price        = round(precio * (1 - DEFAULT_SL_PCT / 100), 4)
    tp_price        = round(precio * (1 + DEFAULT_TP_PCT / 100), 4)
    risk_usd        = round(qty * (precio - sl_price), 2)
    reward_usd      = round(qty * (tp_price - precio), 2)
    risk_reward     = round(reward_usd / risk_usd, 2) if risk_usd > 0 else 0.0

    return {
        "symbol":          symbol,
        "amount_usd":      amount_usd,
        "current_price":   precio,
        "qty":             qty,
        "amount_invested": amount_invested,
        "sl_price":        sl_price,
        "tp_price":        tp_price,
        "trail_pct":       DEFAULT_TRAIL_PCT,
        "risk_usd":        risk_usd,
        "reward_usd":      reward_usd,
        "risk_reward":     risk_reward,
        "error":           None,
    }
