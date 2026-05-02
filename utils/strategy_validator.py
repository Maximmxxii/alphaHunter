"""
utils/strategy_validator.py — Validación de activos contra estrategias
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Tuple
import pandas as pd
from utils.data_fetcher import get_ohlcv
from screener.indicators import compute_all
from screener.filters import apply_strategy, STRATEGIES


def validate_ticker_against_strategy(
    symbol: str,
    strategy_name: str,
    period: str = "1y"
) -> Tuple[bool, List[str], Dict]:
    """
    Valida si un ticker cumple con una estrategia específica.

    Returns:
        (passes_strategy, signals_active, metadata)
    """
    try:
        # Descargar datos históricos
        df = get_ohlcv(symbol, period=period)
        if df is None or df.empty:
            return False, [], {"error": f"No hay datos para {symbol}"}

        # Calcular indicadores
        df = compute_all(df)

        # Aplicar estrategia
        passes, signals = apply_strategy(df, strategy_name)

        # Obtener precio actual
        current_price = float(df['Close'].iloc[-1])

        metadata = {
            "symbol": symbol,
            "strategy": strategy_name,
            "passes": passes,
            "signals": signals,
            "price": round(current_price, 2),
            "sl_price": round(current_price * 0.95, 2),
            "tp_price": round(current_price * 1.20, 2),
            "rsi_14": round(float(df['rsi_14'].iloc[-1]), 2),
            "sma_20": round(float(df['sma_20'].iloc[-1]), 2),
            "sma_50": round(float(df['sma_50'].iloc[-1]), 2),
            "sma_200": round(float(df['sma_200'].iloc[-1]), 2),
            "macd": round(float(df['macd'].iloc[-1]), 4),
            "volume": int(df['Volume'].iloc[-1]),
        }

        return passes, signals, metadata

    except Exception as e:
        return False, [], {"error": str(e)}


def validate_ticker_against_all_strategies(
    symbol: str,
    period: str = "1y"
) -> Dict[str, Dict]:
    """
    Valida un ticker contra TODAS las estrategias disponibles.

    Returns:
        {strategy_name: {passes, signals, ...}}
    """
    results = {}

    for strategy_name in STRATEGIES.keys():
        passes, signals, metadata = validate_ticker_against_strategy(
            symbol,
            strategy_name,
            period
        )

        results[strategy_name] = {
            "passes": passes,
            "signals": signals,
            **metadata
        }

    return results


def find_matching_strategies(
    symbol: str,
    period: str = "1y"
) -> Tuple[List[str], Dict]:
    """
    Encuentra TODAS las estrategias que un ticker cumple.

    Returns:
        (list_of_matching_strategies, full_validation_data)
    """
    validation = validate_ticker_against_all_strategies(symbol, period)

    # Extraer solo las estrategias que pasan
    matching_strategies = [
        strategy for strategy, data in validation.items()
        if data.get("passes", False)
    ]

    return matching_strategies, validation
