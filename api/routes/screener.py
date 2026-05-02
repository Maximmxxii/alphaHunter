"""
api/routes/screener.py — Endpoints del screener cuantitativo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from screener.runner import run_screener
from screener.filters import STRATEGIES as SCREENER_STRATEGIES

router = APIRouter()

# Mapa ticker → dominio para logos Clearbit
TICKER_DOMAINS: dict[str, str] = {
    "AAPL":  "apple.com",
    "MSFT":  "microsoft.com",
    "NVDA":  "nvidia.com",
    "GOOGL": "google.com",
    "GOOG":  "google.com",
    "AMZN":  "amazon.com",
    "META":  "meta.com",
    "TSLA":  "tesla.com",
    "AMD":   "amd.com",
    "INTC":  "intel.com",
    "NFLX":  "netflix.com",
    "CRM":   "salesforce.com",
    "ORCL":  "oracle.com",
    "ADBE":  "adobe.com",
    "QCOM":  "qualcomm.com",
    "AVGO":  "broadcom.com",
    "JPM":   "jpmorganchase.com",
    "BAC":   "bankofamerica.com",
    "GS":    "gs.com",
    "WFC":   "wellsfargo.com",
    "XOM":   "exxonmobil.com",
    "CVX":   "chevron.com",
    "COIN":  "coinbase.com",
    "PLTR":  "palantir.com",
    "HOOD":  "robinhood.com",
    "SOFI":  "sofi.com",
    "RIVN":  "rivian.com",
    "SPY":   "ssga.com",
    "QQQ":   "invesco.com",
    "ARKK":  "ark-invest.com",
    "UNH":   "unitedhealthgroup.com",
    "JNJ":   "jnj.com",
    "PFE":   "pfizer.com",
    "BA":    "boeing.com",
    "CAT":   "caterpillar.com",
    "DE":    "deere.com",
    "OXY":   "oxy.com",
}


def _ticker_domain(symbol: str) -> str:
    """Devuelve dominio para Clearbit o fallback genérico."""
    sym = symbol.upper().replace("-USD", "").replace("/", "")
    return TICKER_DOMAINS.get(sym, f"{sym.lower()}.com")

# Traducciones de señales técnicas → lenguaje simple
SIGNAL_LABELS = {
    "above_sma200":      "Tendencia de fondo positiva",
    "golden_cross":      "Cruce de tendencia alcista",
    "high_volume":       "Volumen inusual hoy",
    "macd_bullish":      "Impulso creciente",
    "macd_bullish_cross": "Impulso creciente",
    "near_bb_lower":     "En zona de soporte",
    "rsi_oversold":      "Caído más de lo normal, posible rebote",
    "rsi_overbought":    "Sobrecomprado, precaución",
    "death_cross":       "Cruce de tendencia bajista",
    "below_sma200":      "Por debajo de tendencia principal",
}

# Metadata completa por estrategia: label, description, icon
STRATEGY_META: dict[str, dict] = {
    "momentum_alcista": {
        "label":       "Acciones con impulso",
        "description": "Busca acciones con impulso alcista: volumen alto, tendencia positiva y MACD creciente.",
        "icon":        "⚡",
    },
    "rebote_sobrevendido": {
        "label":       "Rebote desde zona de apoyo",
        "description": "Detecta activos que han caído demasiado y podrían rebotar desde soporte.",
        "icon":        "🔄",
    },
    "cruce_dorado": {
        "label":       "Cambio de tendencia",
        "description": "Golden cross: la media de 20 días cruza por encima de la de 50 días.",
        "icon":        "🌅",
    },
    "volatilidad_alta": {
        "label":       "Mercado activo",
        "description": "Volumen inusual combinado con impulso alcista en MACD.",
        "icon":        "🌊",
    },
    "exploratorio": {
        "label":       "Vista amplia",
        "description": "Exploración amplia: RSI bajo o volumen inusual. Útil en mercados volátiles.",
        "icon":        "🗺️",
    },
    # Smart money — manejados por /api/smart-money/signals?mode=...
    "congress": {
        "label":       "Siguiendo congresistas",
        "description": "Compras recientes reportadas por miembros del Congreso de EE.UU.",
        "icon":        "🏛️",
    },
    "whales": {
        "label":       "Siguiendo ballenas",
        "description": "Tickers con compras simultáneas de múltiples superinversores (13F filings).",
        "icon":        "🐋",
    },
    "options_flow": {
        "label":       "Opciones inusuales",
        "description": "Flujo inusual de opciones: calls de gran volumen y premium elevado.",
        "icon":        "📊",
    },
}

STRATEGY_ALIASES: dict[str, str] = {
    "momentum":  "momentum_alcista",
    "bounce":    "rebote_sobrevendido",
    "reversal":  "cruce_dorado",
    "volume":    "volatilidad_alta",
    "all":       "exploratorio",
}


def _translate_signal(raw: str) -> str:
    """Convierte nombre de función/filtro a etiqueta legible."""
    key = raw.lower().replace(" ", "_")
    return SIGNAL_LABELS.get(key, raw.replace("_", " ").capitalize())


def _signal_score(signals: list[str]) -> int:
    """Puntaje 0-100 basado en cantidad de señales activas."""
    max_signals = 5
    return min(100, round(len(signals) / max_signals * 100))


@router.get("/screener")
def screener_run(
    strategy: str = Query(default="momentum_alcista", description="Nombre de la estrategia"),
    period: str = Query(default="1y", description="Período histórico (ej: 6mo, 1y, 2y)"),
):
    """
    Ejecuta el screener con la estrategia y período indicados.
    Retorna candidatos enriquecidos con señales en lenguaje simple.
    """
    strategy = STRATEGY_ALIASES.get(strategy, strategy)
    if strategy not in SCREENER_STRATEGIES:
        raise HTTPException(
            status_code=422,
            detail=f"Estrategia inválida. Opciones: {list(SCREENER_STRATEGIES.keys())}",
        )

    try:
        df = run_screener(strategy=strategy, period=period, include_fundamentals=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if df is None or df.empty:
        return []

    resultados = []
    for _, row in df.iterrows():
        ticker = row.get("ticker", "")
        price  = float(row.get("precio", row.get("price", 0)))

        # Señales activas: columna puede ser lista, int o string CSV
        raw_signals = row.get("señales_activas", row.get("señales", []))
        if isinstance(raw_signals, (int, float)):
            raw_signals = []
        if isinstance(raw_signals, str):
            raw_signals = [s.strip() for s in raw_signals.split(",") if s.strip()]

        signals_active = [_translate_signal(s) for s in raw_signals]

        # change_pct: usa columna si existe, o calcula desde precio y prev_close
        change_pct = 0.0
        if row.get("change_pct") is not None:
            change_pct = round(float(row["change_pct"]), 2)
        elif row.get("prev_close") and float(row["prev_close"]) != 0:
            change_pct = round((price - float(row["prev_close"])) / float(row["prev_close"]) * 100, 2)

        resultados.append({
            "ticker":         ticker,
            "name":           row.get("nombre", row.get("longName", ticker)),
            "price":          round(price, 2),
            "change_pct":     change_pct,
            "signal_score":   _signal_score(raw_signals),
            "signals_active": signals_active,
            "sl_price":       round(price * 0.95, 2),
            "tp_price":       round(price * 1.20, 2),
            "sector":         row.get("sector", ""),
            "logo_url":       _ticker_domain(ticker),
        })

    return resultados


@router.get("/strategies")
def list_strategies():
    """Retorna las estrategias disponibles con id, label, description e icon."""
    result = []
    for strategy_id, meta in STRATEGY_META.items():
        result.append({
            "id":          strategy_id,
            "label":       meta["label"],
            "description": meta["description"],
            "icon":        meta["icon"],
        })
    return result
