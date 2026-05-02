"""
Endpoints FastAPI para el módulo smart_money.

Para registrar en la app principal (ej: api/app.py o main FastAPI app):

    from smart_money.api_routes import router as smart_money_router
    app.include_router(smart_money_router)

Endpoints disponibles:
    GET /api/smart-money/congress          → últimos trades de congresistas
    GET /api/smart-money/whales            → consensus buys de ballenas
    GET /api/smart-money/options           → flujo inusual de opciones
    GET /api/smart-money/signals?mode=all  → señales combinadas
"""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException

from .congress import get_congress_trades, get_top_politicians, get_politician_trades
from .whales import get_superinvestor_holdings, get_consensus_buys, get_available_investors
from .options_flow import get_unusual_options, get_bullish_flow
from .signals import get_smart_money_signals, get_signals_for_mode

router = APIRouter(prefix="/api/smart-money", tags=["smart-money"])


# ── Congress ──────────────────────────────────────────────────────────────────

@router.get("/congress")
def congress_trades(
    limit: int = Query(default=50, ge=1, le=200, description="Número de trades a retornar"),
):
    """Últimos trades de congresistas de EE.UU."""
    try:
        return {"status": "ok", "data": get_congress_trades(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/congress/politicians")
def top_politicians(
    min_trades: int = Query(default=10, ge=1, description="Mínimo de trades para incluir"),
):
    """Políticos más activos con histórico consistente de reportes."""
    try:
        return {"status": "ok", "data": get_top_politicians(min_trades=min_trades)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/congress/politician/{name}")
def politician_trades(name: str):
    """Trades de un político específico por nombre (parcial o completo)."""
    try:
        data = get_politician_trades(name)
        if not data:
            raise HTTPException(status_code=404, detail=f"No se encontraron trades para '{name}'")
        return {"status": "ok", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Whales ────────────────────────────────────────────────────────────────────

@router.get("/whales")
def consensus_buys(
    min_investors: int = Query(default=3, ge=2, description="Mínimo de superinversores"),
):
    """Tickers con compras simultáneas de múltiples superinversores (13F filings)."""
    try:
        return {"status": "ok", "data": get_consensus_buys(min_investors=min_investors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whales/investors")
def available_investors():
    """Lista de superinversores disponibles."""
    return {"status": "ok", "data": get_available_investors()}


@router.get("/whales/holdings/{investor_id}")
def investor_holdings(investor_id: str):
    """Holdings completos de un superinversor específico."""
    try:
        data = get_superinvestor_holdings(investor_id=investor_id)
        return {"status": "ok", "investor_id": investor_id, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Options Flow ──────────────────────────────────────────────────────────────

@router.get("/options")
def unusual_options(
    option_type: str = Query(default="all", pattern="^(all|calls|puts)$", description="all | calls | puts"),
):
    """Flujo inusual de opciones ordenado por signal_strength."""
    try:
        return {"status": "ok", "data": get_unusual_options(option_type=option_type)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/bullish")
def bullish_flow(
    min_premium: float = Query(default=100_000, ge=0, description="Premium mínimo en USD"),
):
    """Calls con premiums grandes: señal alcista fuerte."""
    try:
        return {"status": "ok", "data": get_bullish_flow(min_premium=min_premium)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Signals (combinado) ───────────────────────────────────────────────────────

@router.get("/signals")
def smart_money_signals(
    mode: str = Query(
        default="all",
        pattern="^(all|congress|whales|options_flow)$",
        description="all | congress | whales | options_flow",
    ),
    tickers: str = Query(default=None, description="Tickers separados por coma, ej: AAPL,NVDA,MSFT"),
):
    """
    Señales combinadas de dinero inteligente ordenadas por conviction_score.
    Retorna lista de Candidate[] directamente para consumo del frontend.
    """
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None

        if mode == "all":
            raw = get_smart_money_signals(tickers=ticker_list)
        else:
            raw = get_signals_for_mode(mode=mode)
            if ticker_list:
                raw = [s for s in raw if s.get("ticker") in ticker_list]

        return _normalize_smart_money_candidates(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dominio map reutilizado del screener
_TICKER_DOMAINS: dict[str, str] = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "NVDA": "nvidia.com",
    "GOOGL": "google.com", "AMZN": "amazon.com", "META": "meta.com",
    "TSLA": "tesla.com", "AMD": "amd.com", "INTC": "intel.com",
    "NFLX": "netflix.com", "CRM": "salesforce.com", "ORCL": "oracle.com",
    "ADBE": "adobe.com", "QCOM": "qualcomm.com", "AVGO": "broadcom.com",
    "JPM": "jpmorganchase.com", "BAC": "bankofamerica.com", "GS": "gs.com",
    "XOM": "exxonmobil.com", "CVX": "chevron.com", "COIN": "coinbase.com",
    "PLTR": "palantir.com", "HOOD": "robinhood.com", "SOFI": "sofi.com",
    "SPY": "ssga.com", "QQQ": "invesco.com",
}


def _normalize_smart_money_candidates(raw: list[dict]) -> list[dict]:
    """
    Normaliza señales de smart money al contrato Candidate del frontend.
    Cada item de raw puede tener distintas formas según la fuente (congress/whales/options).
    """
    result = []
    for item in raw:
        ticker = str(item.get("ticker", "")).upper()
        price  = float(item.get("price", item.get("precio", 0)) or 0)
        domain = _TICKER_DOMAINS.get(ticker, f"{ticker.lower()}.com")

        # Construir signals_active desde cualquier campo disponible
        signals_raw = item.get("signals_active", item.get("señales_activas", []))
        if isinstance(signals_raw, str):
            signals_raw = [s.strip() for s in signals_raw.split(",") if s.strip()]
        if not isinstance(signals_raw, list):
            signals_raw = []

        result.append({
            "ticker":         ticker,
            "name":           item.get("name", item.get("nombre", ticker)),
            "price":          round(price, 2),
            "change_pct":     round(float(item.get("change_pct", 0) or 0), 2),
            "signal_score":   int(item.get("signal_score", item.get("conviction_score", 0)) or 0),
            "signals_active": signals_raw,
            "sl_price":       round(float(item.get("sl_price", price * 0.95) or price * 0.95), 2),
            "tp_price":       round(float(item.get("tp_price", price * 1.20) or price * 1.20), 2),
            "sector":         str(item.get("sector", "") or ""),
            "logo_url":       domain,
        })
    return result
