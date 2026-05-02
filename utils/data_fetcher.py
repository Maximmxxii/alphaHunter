import os
import hashlib
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(ticker: str, period: str, interval: str) -> str:
    key = f"{ticker}_{period}_{interval}"
    filename = hashlib.md5(key.encode()).hexdigest() + ".parquet"
    return os.path.join(CACHE_DIR, filename)


def _is_cache_valid(path: str, max_age_hours: int = 4) -> bool:
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=max_age_hours)


def get_ohlcv(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Descarga datos OHLCV para un ticker.

    Args:
        ticker: Símbolo del activo (ej. 'AAPL', 'BTC-USD')
        period: Período histórico ('1mo', '3mo', '6mo', '1y', '2y', '5y')
        interval: Intervalo de velas ('1d', '1wk', '1mo')
        use_cache: Si True, usa cache local de 4 horas

    Returns:
        DataFrame con columnas: Open, High, Low, Close, Volume
    """
    cache_path = _cache_path(ticker, period, interval)

    if use_cache and _is_cache_valid(cache_path):
        return pd.read_parquet(cache_path)

    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No se encontraron datos para '{ticker}'")

    df.index = pd.to_datetime(df.index)

    # Aplanar MultiIndex ANTES de seleccionar columnas
    # yfinance 1.2+ retorna ('Close', 'AMD') en vez de 'Close'
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Eliminar columnas duplicadas que pueden aparecer tras el aplanado
    df = df.loc[:, ~df.columns.duplicated()]

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

    if use_cache:
        df.to_parquet(cache_path)

    return df


def get_multiple(
    tickers: list[str],
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True
) -> dict[str, pd.DataFrame]:
    """
    Descarga datos para múltiples tickers.

    Returns:
        Dict {ticker: DataFrame} — omite tickers sin datos
    """
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = get_ohlcv(ticker, period, interval, use_cache)
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")
    return results


def get_fundamentals(ticker: str) -> dict:
    """
    Retorna métricas fundamentales básicas de un ticker.

    Returns:
        Dict con: pe_ratio, market_cap, dividend_yield, sector, industry
    """
    info = yf.Ticker(ticker).info
    return {
        "pe_ratio":       info.get("trailingPE"),
        "forward_pe":     info.get("forwardPE"),
        "market_cap":     info.get("marketCap"),
        "dividend_yield": info.get("dividendYield"),
        "sector":         info.get("sector"),
        "industry":       info.get("industry"),
        "country":        info.get("country"),
    }


def clear_cache() -> None:
    """Elimina todos los archivos de cache."""
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".parquet"):
            os.remove(os.path.join(CACHE_DIR, f))
    print(f"Cache limpiado: {CACHE_DIR}")


if __name__ == "__main__":
    # Prueba rápida
    print("Descargando AAPL...")
    df = get_ohlcv("AAPL", period="6mo")
    print(df.tail(3))
    print(f"\nFilas: {len(df)} | Columnas: {list(df.columns)}")

    print("\nFundamentales AAPL:")
    f = get_fundamentals("AAPL")
    for k, v in f.items():
        print(f"  {k}: {v}")
