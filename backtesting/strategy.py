import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from screener.indicators import compute_all


def strategy_golden_cross(df: pd.DataFrame) -> pd.Series:
    """
    Señales basadas en cruce de medias SMA20/SMA50.

    Entrada : SMA20 cruza por encima de SMA50
    Salida  : SMA20 cruza por debajo de SMA50
    """
    df = compute_all(df)
    signal = pd.Series(0, index=df.index)
    signal[df['sma_20'] > df['sma_50']] = 1   # largo
    # 0 cuando SMA20 < SMA50 (fuera de posición — el engine detecta salida con curr_signal == 0)
    return signal


def strategy_rsi_reversion(df: pd.DataFrame, oversold: float = 35, overbought: float = 65) -> pd.Series:
    """
    Reversión a la media con RSI.

    Entrada : RSI < oversold
    Salida  : RSI > overbought
    """
    df = compute_all(df)
    signal = pd.Series(0, index=df.index)
    in_position = False

    for i in range(len(df)):
        rsi = df['rsi_14'].iloc[i]
        if not in_position and rsi < oversold:
            in_position = True
        elif in_position and rsi > overbought:
            in_position = False
        signal.iloc[i] = 1 if in_position else 0

    return signal


def strategy_macd_cross(df: pd.DataFrame) -> pd.Series:
    """
    Cruce de MACD con su línea de señal.

    Entrada : MACD cruza por encima de signal
    Salida  : MACD cruza por debajo de signal
    """
    df = compute_all(df)
    signal = pd.Series(0, index=df.index)
    signal[df['macd'] > df['macd_signal']] = 1
    signal[df['macd'] < df['macd_signal']] = 0
    return signal


def strategy_bollinger_bounce(df: pd.DataFrame) -> pd.Series:
    """
    Rebote desde banda inferior de Bollinger.

    Entrada : %b < 0.2 (precio cerca del límite inferior)
    Salida  : %b > 0.8 (precio cerca del límite superior)
    """
    df = compute_all(df)
    signal = pd.Series(0, index=df.index)
    in_position = False

    for i in range(len(df)):
        pct_b = df['bb_pct_b'].iloc[i]
        if not in_position and pct_b < 0.2:
            in_position = True
        elif in_position and pct_b > 0.8:
            in_position = False
        signal.iloc[i] = 1 if in_position else 0

    return signal


def strategy_combined(df: pd.DataFrame) -> pd.Series:
    """
    Estrategia combinada: golden cross + RSI no sobrecomprado + sobre SMA200.

    Entrada : SMA20 > SMA50 AND RSI < 65 AND precio > SMA200
    Salida  : cualquiera de las condiciones se rompe
    """
    df = compute_all(df)
    signal = pd.Series(0, index=df.index)

    cond = (
        (df['sma_20'] > df['sma_50']) &
        (df['rsi_14'] < 65) &
        (df['Close'] > df['sma_200'])
    )
    signal[cond] = 1
    return signal


STRATEGIES = {
    "golden_cross":       strategy_golden_cross,
    "rsi_reversion":      strategy_rsi_reversion,
    "macd_cross":         strategy_macd_cross,
    "bollinger_bounce":   strategy_bollinger_bounce,
    "combined":           strategy_combined,
}
