import pandas as pd
import numpy as np


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    """Media móvil simple."""
    return df['Close'].rolling(window=period).mean()


def ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Media móvil exponencial."""
    return df['Close'].ewm(span=period, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (0-100).
    < 30: sobrevendido | > 70: sobrecomprado
    """
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD = EMA(fast) - EMA(slow)
    Retorna DataFrame con: macd, signal, histogram
    """
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({
        'macd':      macd_line,
        'signal':    signal_line,
        'histogram': macd_line - signal_line,
    })


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """
    Bandas de Bollinger.
    Retorna: upper, middle, lower, bandwidth, %b
    """
    middle = df['Close'].rolling(window=period).mean()
    std_dev = df['Close'].rolling(window=period).std()
    upper = middle + std * std_dev
    lower = middle - std * std_dev
    bandwidth = (upper - lower) / middle
    pct_b = (df['Close'] - lower) / (upper - lower)
    return pd.DataFrame({
        'bb_upper':     upper,
        'bb_middle':    middle,
        'bb_lower':     lower,
        'bb_bandwidth': bandwidth,
        'bb_pct_b':     pct_b,
    })


def volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Ratio de volumen actual vs promedio.
    > 2.0: volumen inusualmente alto (señal de interés)
    """
    avg_volume = df['Volume'].rolling(window=period).mean()
    return df['Volume'] / avg_volume


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — mide volatilidad."""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula todos los indicadores y los agrega al DataFrame.
    Retorna el DataFrame enriquecido.
    """
    result = df.copy()

    result['sma_20']       = sma(df, 20)
    result['sma_50']       = sma(df, 50)
    result['sma_200']      = sma(df, 200)
    result['ema_9']        = ema(df, 9)
    result['rsi_14']       = rsi(df, 14)
    result['vol_ratio']    = volume_ratio(df, 20)
    result['atr_14']       = atr(df, 14)

    macd_df = macd(df)
    result['macd']         = macd_df['macd']
    result['macd_signal']  = macd_df['signal']
    result['macd_hist']    = macd_df['histogram']

    bb = bollinger_bands(df)
    result['bb_upper']     = bb['bb_upper']
    result['bb_lower']     = bb['bb_lower']
    result['bb_bandwidth'] = bb['bb_bandwidth']
    result['bb_pct_b']     = bb['bb_pct_b']

    return result.dropna()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '..')
    from utils.data_fetcher import get_ohlcv

    df = get_ohlcv("AAPL", period="1y")
    result = compute_all(df)
    print(result[['Close', 'rsi_14', 'macd', 'vol_ratio', 'bb_pct_b']].tail(5))
