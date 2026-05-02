"""
api/routes/market.py — Datos de mercado en tiempo real
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import yfinance as yf

router = APIRouter()

# Mapeo ticker → dominio para logos de Clearbit
TICKER_DOMAIN_MAP = {
    "AAPL":  "apple.com",
    "MSFT":  "microsoft.com",
    "GOOGL": "google.com",
    "GOOG":  "google.com",
    "AMZN":  "amazon.com",
    "TSLA":  "tesla.com",
    "META":  "meta.com",
    "NVDA":  "nvidia.com",
    "NFLX":  "netflix.com",
    "AMD":   "amd.com",
    "INTC":  "intel.com",
    "CRM":   "salesforce.com",
    "ORCL":  "oracle.com",
    "ADBE":  "adobe.com",
    "QCOM":  "qualcomm.com",
    "AVGO":  "broadcom.com",
    "JPM":   "jpmorganchase.com",
    "BAC":   "bankofamerica.com",
    "GS":    "goldmansachs.com",
    "WFC":   "wellsfargo.com",
    "XOM":   "exxonmobil.com",
    "CVX":   "chevron.com",
    "OXY":   "oxy.com",
    "UNH":   "unitedhealthgroup.com",
    "JNJ":   "jnj.com",
    "PFE":   "pfizer.com",
    "BA":    "boeing.com",
    "CAT":   "caterpillar.com",
    "DE":    "deere.com",
    "COIN":  "coinbase.com",
    "HOOD":  "robinhood.com",
    "PLTR":  "palantir.com",
    "SOFI":  "sofi.com",
    "RIVN":  "rivian.com",
    "SPY":   "ssga.com",
    "QQQ":   "invesco.com",
    "ARKK":  "ark-invest.com",
}


def _ticker_to_domain(symbol: str) -> str | None:
    """Retorna el dominio para el logo, o None si no se conoce."""
    sym = symbol.upper().replace("-USD", "").replace("-", "")
    return TICKER_DOMAIN_MAP.get(sym)


@router.get("/market/price/{symbol}")
def get_live_price(symbol: str):
    """
    Precio en tiempo real de un ticker.

    GET /api/market/price/{symbol}
    Response 200: { symbol: str, price: float, timestamp: str }
    Response 400: { detail: str }  — ticker inválido o sin datos
    Response 500: { detail: str }  — error inesperado
    """
    sym = symbol.upper()
    try:
        ticker = yf.Ticker(sym)
        fast   = ticker.fast_info
        price  = float(fast.last_price)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo obtener precio de {sym}: {str(e)}",
        )

    if not price or price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Precio inválido o no disponible para {sym}",
        )

    return {
        "symbol":    sym,
        "price":     round(price, 4),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/market/ticker/{symbol}")
def get_ticker_info(symbol: str):
    """
    Precio actual, % cambio hoy, nombre, sector de un ticker.
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info

        # Precio actual — fast_info es más confiable para precios live
        try:
            fast = ticker.fast_info
            current_price = round(float(fast.last_price), 2)
            prev_close    = round(float(fast.previous_close), 2)
        except Exception:
            current_price = round(float(info.get("currentPrice") or info.get("regularMarketPrice") or 0), 2)
            prev_close    = round(float(info.get("previousClose") or info.get("regularMarketPreviousClose") or 0), 2)

        pct_change = 0.0
        if prev_close and prev_close != 0:
            pct_change = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "symbol":        symbol.upper(),
            "name":          info.get("longName") or info.get("shortName") or symbol.upper(),
            "sector":        info.get("sector", ""),
            "industry":      info.get("industry", ""),
            "current_price": current_price,
            "prev_close":    prev_close,
            "pct_change":    pct_change,
            "market_cap":    info.get("marketCap"),
            "volume":        info.get("volume") or info.get("regularMarketVolume"),
            "currency":      info.get("currency", "USD"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos de {symbol}: {str(e)}")


@router.get("/market/logo/{symbol}")
def get_ticker_logo(symbol: str):
    """
    Retorna la URL del logo de la empresa via Clearbit.
    """
    domain = _ticker_to_domain(symbol)
    if domain:
        logo_url = f"https://logo.clearbit.com/{domain}"
    else:
        # Fallback: intentar con el símbolo en minúsculas como dominio
        sym_clean = symbol.upper().replace("-USD", "").lower()
        logo_url = f"https://logo.clearbit.com/{sym_clean}.com"

    return {
        "symbol":   symbol.upper(),
        "logo_url": logo_url,
        "domain":   domain,
    }
