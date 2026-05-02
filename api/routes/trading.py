"""
api/routes/trading.py — Endpoints de trading con Alpaca
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import requests as _requests

from api.auth.jwt_utils import get_current_user
from api.limiter import limiter

router = APIRouter()

ALPACA_NOT_CONFIGURED = {"error": "Alpaca no configurado", "configured": False}

# ── Helpers ────────────────────────────────────────────────────────────────

def _is_alpaca_configured() -> bool:
    from utils.alpaca import API_KEY, SECRET_KEY
    return bool(API_KEY and SECRET_KEY)


def _get_user_alpaca_creds(payload: dict = Depends(get_current_user)) -> tuple:
    from api.auth.database import get_user_by_id
    from utils.alpaca import API_KEY, SECRET_KEY, BASE_URL

    user_id = int(payload["sub"])
    db_user = get_user_by_id(user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return (
        db_user.get("alpaca_api_key") or API_KEY,
        db_user.get("alpaca_secret_key") or SECRET_KEY,
        db_user.get("alpaca_base_url") or BASE_URL,
    )


def _safe_alpaca(fn, *args, **kwargs):
    """Ejecuta una función de Alpaca y captura errores de configuración."""
    if not _is_alpaca_configured():
        return None, ALPACA_NOT_CONFIGURED
    try:
        return fn(*args, **kwargs), None
    except _requests.exceptions.HTTPError as e:
        if e.response is not None:
            status = e.response.status_code
            if status in (401, 403):
                return None, ALPACA_NOT_CONFIGURED
            if status == 404:
                raise HTTPException(status_code=404, detail="Posición no encontrada en Alpaca")
            if status == 422:
                raise HTTPException(status_code=422, detail="Datos inválidos para Alpaca")
            raise HTTPException(status_code=502, detail=f"Error Alpaca upstream: {status}")
        raise HTTPException(status_code=502, detail="Error de conexión con Alpaca")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Modelos ────────────────────────────────────────────────────────────────

class EntryOrderRequest(BaseModel):
    symbol:     str   = Field(..., description="Ticker (ej: AAPL)")
    amount_usd: float = Field(..., gt=0, description="Monto en USD a invertir")


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/account")
def get_account(payload: dict = Depends(get_current_user)):
    """Balance, buying power y P&L de la cuenta Alpaca."""
    from utils.alpaca import get_account as _get_account
    data, err = _safe_alpaca(_get_account)
    if err:
        return err

    equity = round(data["equity"], 2)
    raw    = data.get("raw", {})

    # P&L total: equity vs. initial deposit (long_market_value baseline)
    pl_total     = round(data.get("pl_total", 0.0), 2)
    last_equity  = float(raw.get("last_equity") or equity)
    pl_total_pct = round((pl_total / last_equity * 100) if last_equity else 0.0, 2)

    # P&L de hoy: equity vs. last_equity (cierre anterior)
    pl_today     = round(equity - last_equity, 2)
    pl_today_pct = round((pl_today / last_equity * 100) if last_equity else 0.0, 2)

    return {
        "equity":        equity,
        "buying_power":  round(data["buying_power"], 2),
        "cash":          round(data["cash"], 2),
        "pl_today":      pl_today,
        "pl_today_pct":  pl_today_pct,
        "pl_total":      pl_total,
        "pl_total_pct":  pl_total_pct,
        "configured":    True,
    }


@router.get("/positions")
def get_positions(payload: dict = Depends(get_current_user)):
    """Lista de posiciones abiertas con SL/TP/trailing calculados."""
    import yfinance as yf
    from utils.alpaca import get_positions as _get_positions, _get as _alpaca_raw

    data, err = _safe_alpaca(_get_positions)
    if err:
        return err

    # Fetch raw Alpaca positions to get created_at and asset_class per symbol
    try:
        raw_positions: list = _alpaca_raw("positions")
        raw_by_symbol = {p["symbol"]: p for p in raw_positions}
    except Exception:
        raw_by_symbol = {}

    result = []
    for p in data:
        symbol = p["symbol"]
        entry  = float(p["avg_entry_price"])
        sl     = round(entry * 0.95, 2)
        tp     = round(entry * 1.20, 2)

        # opened_at: Alpaca exposes it as created_at on the position object
        raw_p     = raw_by_symbol.get(symbol, {})
        opened_at = raw_p.get("created_at") or raw_p.get("opened_at") or ""

        # Company name: try yfinance fast_info, fall back to symbol
        try:
            info = yf.Ticker(symbol).info
            name = info.get("longName") or info.get("shortName") or symbol
        except Exception:
            name = symbol

        result.append({
            "symbol":           symbol,
            "name":             name,
            "qty":              round(p["qty"], 4),
            "avg_entry_price":  round(entry, 2),
            "current_price":    round(float(p["current_price"]), 2),
            "unrealized_pl":    round(float(p["unrealized_pl"]), 2),
            # unrealized_plpc already x100 from utils/alpaca.py
            "unrealized_plpc":  round(float(p["unrealized_plpc"]), 2),
            "sl_price":         sl,
            "tp_price":         tp,
            "trailing_floor":   sl,
            "opened_at":        opened_at,
        })

    return result


@router.post("/entry")
@limiter.limit("10/minute")
def place_entry(request: Request, order: EntryOrderRequest, payload: dict = Depends(get_current_user)):
    """
    Coloca una orden de compra bracket con SL=5% y TP=20%.
    Calcula qty a partir del monto en USD.
    """
    import yfinance as yf
    from utils.alpaca import place_order as _place_order

    symbol = order.symbol.upper()

    # Obtener precio actual para calcular qty
    try:
        ticker = yf.Ticker(symbol)
        fast   = ticker.fast_info
        price  = float(fast.last_price)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo obtener precio de {symbol}: {str(e)}")

    if price <= 0:
        raise HTTPException(status_code=400, detail=f"Precio inválido para {symbol}")

    qty        = order.amount_usd / price
    sl_price   = round(price * 0.95, 2)
    tp_price   = round(price * 1.20, 2)
    qty_rounded = round(qty, 4)

    data, err = _safe_alpaca(
        _place_order,
        symbol=symbol,
        qty=qty_rounded,
        side="buy",
        order_type="market",
        take_profit_price=tp_price,
        stop_loss_price=sl_price,
    )
    if err:
        return err

    return {
        "id":          data["id"],
        "status":      data["status"],
        "symbol":      data["symbol"],
        "side":        data["side"],
        "qty":         qty_rounded,
        "amount_usd":  round(order.amount_usd, 2),
        "sl_price":    sl_price,
        "tp_price":    tp_price,
        "entry_price": round(price, 2),
    }


@router.delete("/positions/{symbol}")
def close_position(symbol: str, payload: dict = Depends(get_current_user)):
    """Cierra la posición completa de un símbolo."""
    from utils.alpaca import close_position as _close_position
    data, err = _safe_alpaca(_close_position, symbol.upper())
    if err:
        return err

    return {"status": "closed", "symbol": symbol.upper(), "detail": data}


# ── Validación de estrategias ────────────────────────────────────────────────

@router.get("/validate/{symbol}")
def validate_ticker_against_strategies(symbol: str, payload: dict = Depends(get_current_user)):
    """
    Valida un ticker contra TODAS las estrategias disponibles.
    Retorna qué estrategias aplican y qué señales se detectan.
    """
    from utils.strategy_validator import validate_ticker_against_all_strategies, find_matching_strategies

    symbol = symbol.upper()

    # Obtener validación contra todas las estrategias
    validation = validate_ticker_against_all_strategies(symbol, period="1y")

    # Extraer estrategias que pasan
    matching, full_data = find_matching_strategies(symbol, period="1y")

    # Si hay error, retornarlo
    if "error" in full_data.get(list(full_data.keys())[0], {}):
        first_error = full_data[list(full_data.keys())[0]].get("error")
        return {"error": first_error, "symbol": symbol}

    return {
        "symbol": symbol,
        "matching_strategies": matching,
        "all_strategies": validation,
        "total_matching": len(matching),
    }


# ── Trading automático ────────────────────────────────────────────────────────

class AutoTradeRequest(BaseModel):
    strategy: str = Field(default="momentum_alcista", description="Estrategia screener")
    amount_usd: float = Field(default=500.0, gt=0, description="USD por trade")
    max_positions: int = Field(default=5, ge=1, description="Max posiciones")
    sl_percent: float = Field(default=5.0, gt=0, description="Stop loss %")
    tp_percent: float = Field(default=20.0, gt=0, description="Take profit %")


@router.post("/auto-trade")
def execute_auto_trade(request: AutoTradeRequest, payload: dict = Depends(get_current_user)):
    """
    Ejecuta trading automático:
    1. Corre screener con estrategia
    2. Valida activos
    3. Coloca órdenes automáticamente

    Respeta max_positions y no abre si ya tienes muchas posiciones.
    """
    from utils.auto_trader import AutoTrader, AutoTradeConfig

    config = AutoTradeConfig(
        strategy=request.strategy,
        amount_usd_per_trade=request.amount_usd,
        max_positions=request.max_positions,
        sl_percent=request.sl_percent,
        tp_percent=request.tp_percent,
    )

    trader = AutoTrader(config)
    result = trader.run_screener_and_trade()

    return result
