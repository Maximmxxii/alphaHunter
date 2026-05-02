import pandas as pd


def rsi_oversold(df: pd.DataFrame, threshold: float = 35.0) -> bool:
    """RSI por debajo del umbral — posible zona de compra."""
    return df['rsi_14'].iloc[-1] < threshold


def rsi_overbought(df: pd.DataFrame, threshold: float = 65.0) -> bool:
    """RSI por encima del umbral — posible zona de venta."""
    return df['rsi_14'].iloc[-1] > threshold


def golden_cross(df: pd.DataFrame) -> bool:
    """SMA20 cruza por encima de SMA50 — señal alcista."""
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return prev['sma_20'] <= prev['sma_50'] and curr['sma_20'] > curr['sma_50']


def death_cross(df: pd.DataFrame) -> bool:
    """SMA20 cruza por debajo de SMA50 — señal bajista."""
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return prev['sma_20'] >= prev['sma_50'] and curr['sma_20'] < curr['sma_50']


def above_sma200(df: pd.DataFrame) -> bool:
    """Precio por encima de SMA200 — tendencia alcista de largo plazo."""
    return df['Close'].iloc[-1] > df['sma_200'].iloc[-1]


def high_volume(df: pd.DataFrame, multiplier: float = 2.0) -> bool:
    """Volumen actual es N veces el promedio de 20 días."""
    return df['vol_ratio'].iloc[-1] >= multiplier


def macd_bullish_cross(df: pd.DataFrame) -> bool:
    """MACD cruza por encima de su señal — momentum alcista."""
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return prev['macd'] <= prev['macd_signal'] and curr['macd'] > curr['macd_signal']


def near_bb_lower(df: pd.DataFrame, threshold: float = 0.2) -> bool:
    """Precio cerca de la banda inferior de Bollinger — posible rebote."""
    return df['bb_pct_b'].iloc[-1] < threshold


def price_momentum(df: pd.DataFrame, days: int = 5, min_pct: float = 3.0) -> bool:
    """Precio subió al menos min_pct% en los últimos N días."""
    pct_change = (df['Close'].iloc[-1] / df['Close'].iloc[-days] - 1) * 100
    return pct_change >= min_pct


# --- Estrategias predefinidas ---

STRATEGIES = {
    "momentum_alcista": {
        "description": "RSI moderado + cruce dorado + volumen alto",
        "filters": [
            lambda df: not rsi_overbought(df, 70),
            above_sma200,
            high_volume,
            macd_bullish_cross,
        ]
    },
    "rebote_sobrevendido": {
        "description": "RSI sobrevendido + cerca banda inferior Bollinger",
        "filters": [
            lambda df: rsi_oversold(df, 35),
            near_bb_lower,
            above_sma200,
        ]
    },
    "cruce_dorado": {
        "description": "Golden cross SMA20/SMA50",
        "filters": [
            golden_cross,
            above_sma200,
        ]
    },
    "exploratorio": {
        "description": "Exploración amplia — RSI bajo o volumen alto (mercados volátiles)",
        "filters": [
            lambda df: rsi_oversold(df, 45) or high_volume(df, 1.5),
        ]
    },
    "volatilidad_alta": {
        "description": "Volumen inusual + MACD alcista (sin restricción de tendencia)",
        "filters": [
            lambda df: high_volume(df, 1.5),
            macd_bullish_cross,
        ]
    },
}


def apply_strategy(df: pd.DataFrame, strategy_name: str) -> tuple[bool, list[str]]:
    """
    Aplica una estrategia predefinida al DataFrame con indicadores.

    Returns:
        (pasa_filtro, señales_activas)
    """
    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        raise ValueError(f"Estrategia '{strategy_name}' no existe. Opciones: {list(STRATEGIES.keys())}")

    signals = []
    for f in strategy["filters"]:
        try:
            if f(df):
                signals.append(f.__name__ if hasattr(f, '__name__') else "condición_ok")
        except Exception:
            return False, []

    passed = len(signals) == len(strategy["filters"])
    return passed, signals
