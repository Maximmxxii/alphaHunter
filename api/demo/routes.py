"""
api/demo/routes.py — Endpoints del modo demo de AlphaHunter.

GET  /api/demo/account              → cuenta demo del usuario
GET  /api/demo/positions            → posiciones demo
POST /api/demo/entry                → body: { symbol, amount_usd } → entrada demo
DELETE /api/demo/positions/{symbol} → cierra posición demo
POST /api/demo/reset                → resetea portafolio a estado inicial
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth.jwt_utils import get_current_user
from api.demo.portfolio import (
    close_demo_position,
    execute_demo_entry,
    get_demo_account,
    get_demo_positions,
    reset_demo,
)

router = APIRouter(prefix="/demo")


# ── Modelos ────────────────────────────────────────────────────────────────

class DemoEntryRequest(BaseModel):
    symbol:     str   = Field(..., description="Ticker (ej: AAPL)")
    amount_usd: float = Field(..., gt=0, description="Monto en USD a invertir")


# ── Helpers ────────────────────────────────────────────────────────────────

def _user_id(payload: dict) -> str:
    return str(payload["sub"])


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/account")
def demo_account(payload: dict = Depends(get_current_user)):
    """Balance, buying power y P&L de la cuenta demo."""
    return get_demo_account(_user_id(payload))


@router.get("/positions")
def demo_positions(payload: dict = Depends(get_current_user)):
    """Lista de posiciones demo con precios en tiempo real."""
    return get_demo_positions(_user_id(payload))


@router.post("/entry")
def demo_entry(order: DemoEntryRequest, payload: dict = Depends(get_current_user)):
    """Simula una entrada en el portafolio demo."""
    try:
        return execute_demo_entry(_user_id(payload), order.symbol, order.amount_usd)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/positions/{symbol}")
def demo_close_position(symbol: str, payload: dict = Depends(get_current_user)):
    """Cierra una posición demo."""
    try:
        return close_demo_position(_user_id(payload), symbol.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reset")
def demo_reset(payload: dict = Depends(get_current_user)):
    """Resetea el portafolio demo a $25,000 con posiciones de ejemplo."""
    return reset_demo(_user_id(payload))
