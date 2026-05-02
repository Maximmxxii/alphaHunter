import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from backtesting.strategy import STRATEGIES


def run_backtest(
    df: pd.DataFrame,
    strategy_name: str = "combined",
    initial_capital: float = 10_000.0,
    commission: float = 0.001,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
) -> dict:
    """
    Ejecuta un backtest vectorizado sobre un DataFrame OHLCV.

    Args:
        df              : DataFrame con columnas OHLCV
        strategy_name   : Nombre de la estrategia en STRATEGIES
        initial_capital : Capital inicial en USD
        commission      : Comisión por operación (0.001 = 0.1%)
        stop_loss_pct   : Stop loss porcentual (ej. 0.05 = 5%). None = desactivado
        take_profit_pct : Take profit porcentual. None = desactivado

    Returns:
        Dict con equity_curve, trades, métricas base
    """
    if strategy_name not in STRATEGIES:
        raise ValueError(f"Estrategia inválida. Opciones: {list(STRATEGIES.keys())}")

    signal = STRATEGIES[strategy_name](df)
    signal = signal.reindex(df.index).fillna(0)

    prices = df['Close'].copy()
    equity = pd.Series(index=df.index, dtype=float)
    trades = []

    cash = initial_capital
    shares = 0.0
    entry_price = None
    entry_date = None
    in_position = False

    for i in range(1, len(df)):
        date = df.index[i]
        price = prices.iloc[i]
        prev_signal = signal.iloc[i - 1]
        curr_signal = signal.iloc[i]

        # Entrada
        if not in_position and prev_signal == 0 and curr_signal == 1:
            cost = cash * (1 - commission)
            shares = cost / price
            cash = 0.0
            entry_price = price
            entry_date = date
            in_position = True

        # Salida por señal
        elif in_position and curr_signal == 0:
            proceeds = shares * price * (1 - commission)
            pnl = proceeds - (shares * entry_price)
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   date,
                "entry_price": round(entry_price, 4),
                "exit_price":  round(price, 4),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round((price / entry_price - 1) * 100, 2),
                "exit_reason": "señal",
            })
            cash = proceeds
            shares = 0.0
            in_position = False
            entry_price = None

        # Stop loss
        elif in_position and stop_loss_pct and price <= entry_price * (1 - stop_loss_pct):
            proceeds = shares * price * (1 - commission)
            pnl = proceeds - (shares * entry_price)
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   date,
                "entry_price": round(entry_price, 4),
                "exit_price":  round(price, 4),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round((price / entry_price - 1) * 100, 2),
                "exit_reason": "stop_loss",
            })
            cash = proceeds
            shares = 0.0
            in_position = False
            entry_price = None

        # Take profit
        elif in_position and take_profit_pct and price >= entry_price * (1 + take_profit_pct):
            proceeds = shares * price * (1 - commission)
            pnl = proceeds - (shares * entry_price)
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   date,
                "entry_price": round(entry_price, 4),
                "exit_price":  round(price, 4),
                "pnl":         round(pnl, 2),
                "pnl_pct":     round((price / entry_price - 1) * 100, 2),
                "exit_reason": "take_profit",
            })
            cash = proceeds
            shares = 0.0
            in_position = False
            entry_price = None

        # Equity actual
        equity.iloc[i] = cash + shares * price

    # Cerrar posición abierta al final
    if in_position:
        last_price = prices.iloc[-1]
        proceeds = shares * last_price * (1 - commission)
        pnl = proceeds - (shares * entry_price)
        trades.append({
            "entry_date":  entry_date,
            "exit_date":   df.index[-1],
            "entry_price": round(entry_price, 4),
            "exit_price":  round(last_price, 4),
            "pnl":         round(pnl, 2),
            "pnl_pct":     round((last_price / entry_price - 1) * 100, 2),
            "exit_reason": "fin_periodo",
        })
        cash = proceeds

    equity.iloc[0] = initial_capital
    equity = equity.ffill()

    return {
        "equity_curve":      equity,
        "trades":            pd.DataFrame(trades) if trades else pd.DataFrame(),
        "initial_capital":   initial_capital,
        "final_capital":     round(cash if not in_position else cash + shares * prices.iloc[-1], 2),
        "strategy":          strategy_name,
        "period_start":      df.index[0],
        "period_end":        df.index[-1],
    }


def run_multiple(
    data_dict: dict,
    strategy_name: str = "combined",
    initial_capital: float = 10_000.0,
    **kwargs,
) -> dict:
    """
    Ejecuta backtest para múltiples tickers.

    Args:
        data_dict: {ticker: DataFrame} — salida de get_multiple()

    Returns:
        {ticker: resultado_backtest}
    """
    results = {}
    for ticker, df in data_dict.items():
        try:
            results[ticker] = run_backtest(df, strategy_name, initial_capital, **kwargs)
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")
    return results
