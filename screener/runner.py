import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from utils.data_fetcher import get_ohlcv, get_fundamentals
from screener.indicators import compute_all
from screener.filters import apply_strategy, STRATEGIES

# Lista de tickers por defecto (S&P 500 muestra + crypto + forex)
DEFAULT_TICKERS = [
    # Tech
    "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META",
    "NFLX", "AMD", "INTC", "CRM", "ORCL", "ADBE", "QCOM", "AVGO",
    # ETFs
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO",
    "XLF", "XLE", "XLK", "ARKK",
    # Leveraged / volatilidad
    "TQQQ", "SQQQ", "SPXU", "UVXY",
    # Growth / especulativos
    "COIN", "HOOD", "RIVN", "LCID", "PLTR", "SOFI",
    "MARA", "RIOT", "SMCI", "ARM", "IONQ", "RKLB", "SOUN", "BBAI",
    # Financiero
    "JPM", "BAC", "GS", "WFC",
    # Energía
    "XOM", "CVX", "OXY",
    # Salud
    "UNH", "JNJ", "PFE",
    # Industrial
    "BA", "CAT", "DE",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD",
    "DOGE-USD", "LINK-USD", "LTC-USD",
]


def run_screener(
    tickers: list[str] = None,
    strategy: str = "momentum_alcista",
    period: str = "1y",
    include_fundamentals: bool = False,
) -> pd.DataFrame:
    """
    Ejecuta el screener sobre una lista de tickers.

    Args:
        tickers: Lista de símbolos. Si None, usa DEFAULT_TICKERS
        strategy: Nombre de la estrategia a aplicar
        period: Período histórico para descargar datos
        include_fundamentals: Si True, agrega P/E, market cap, sector

    Returns:
        DataFrame con los tickers que pasaron el filtro
    """
    if tickers is None:
        tickers = DEFAULT_TICKERS

    if strategy not in STRATEGIES:
        raise ValueError(f"Estrategia inválida. Opciones: {list(STRATEGIES.keys())}")

    print(f"\nAlphaHunter Screener")
    print(f"Estrategia : {strategy} — {STRATEGIES[strategy]['description']}")
    print(f"Tickers    : {len(tickers)}")
    print(f"Período    : {period}")
    print("-" * 50)

    resultados = []

    for ticker in tickers:
        try:
            df_raw = get_ohlcv(ticker, period=period)
            df = compute_all(df_raw)

            if len(df) < 50:
                continue

            passed, signals = apply_strategy(df, strategy)

            if passed:
                last = df.iloc[-1]
                entry = {
                    "ticker":      ticker,
                    "precio":      round(last['Close'], 2),
                    "rsi":         round(last['rsi_14'], 1),
                    "vol_ratio":   round(last['vol_ratio'], 2),
                    "macd":        round(last['macd'], 4),
                    "bb_pct_b":    round(last['bb_pct_b'], 2),
                    "sma_20":      round(last['sma_20'], 2),
                    "sma_50":      round(last['sma_50'], 2),
                    "señales":     signals,
                }

                if include_fundamentals:
                    try:
                        fund = get_fundamentals(ticker)
                        entry.update({
                            "pe_ratio":   fund.get("pe_ratio"),
                            "market_cap": fund.get("market_cap"),
                            "sector":     fund.get("sector"),
                        })
                    except Exception:
                        pass

                resultados.append(entry)
                print(f"  ✓ {ticker:<12} RSI={entry['rsi']} | Vol={entry['vol_ratio']}x | Precio={entry['precio']}")

        except Exception as e:
            print(f"  ✗ {ticker:<12} {e}")

    print("-" * 50)

    if not resultados:
        print("Ningún ticker pasó los filtros.")
        return pd.DataFrame()

    df_result = pd.DataFrame(resultados).sort_values("vol_ratio", ascending=False)
    print(f"\n{len(df_result)} candidatos encontrados:\n")
    print(df_result.to_string(index=False))
    return df_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlphaHunter Screener")
    parser.add_argument("--strategy", default="momentum_alcista", choices=list(STRATEGIES.keys()))
    parser.add_argument("--period", default="1y")
    parser.add_argument("--fundamentals", action="store_true")
    parser.add_argument("--tickers", nargs="+", default=None)
    args = parser.parse_args()

    df = run_screener(
        tickers=args.tickers,
        strategy=args.strategy,
        period=args.period,
        include_fundamentals=args.fundamentals,
    )
