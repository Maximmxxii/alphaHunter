import pandas as pd
import numpy as np


def calculate_metrics(result: dict) -> dict:
    """
    Calcula métricas de performance a partir del resultado del backtest.

    Args:
        result: Dict retornado por engine.run_backtest()

    Returns:
        Dict con todas las métricas
    """
    equity = result['equity_curve']
    trades = result['trades']
    initial = result['initial_capital']
    final = result['final_capital']

    # Retorno total
    total_return_pct = round((final / initial - 1) * 100, 2)

    # Retorno anualizado
    days = (result['period_end'] - result['period_start']).days
    years = days / 365.25
    if years > 0 and final > 0:
        annual_return_pct = round(((final / initial) ** (1 / years) - 1) * 100, 2)
    else:
        annual_return_pct = 0.0

    # Drawdown máximo
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown_pct = round(drawdown.min(), 2)

    # Sharpe ratio (diario, anualizado)
    daily_returns = equity.pct_change().dropna()
    if daily_returns.std() > 0:
        sharpe = round((daily_returns.mean() / daily_returns.std()) * np.sqrt(252), 2)
    else:
        sharpe = 0.0

    # Sortino ratio (solo downside)
    downside = daily_returns[daily_returns < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = round((daily_returns.mean() / downside.std()) * np.sqrt(252), 2)
    else:
        sortino = 0.0

    # Métricas de trades
    if not trades.empty:
        n_trades      = len(trades)
        winning       = trades[trades['pnl'] > 0]
        losing        = trades[trades['pnl'] <= 0]
        win_rate      = round(len(winning) / n_trades * 100, 1)
        avg_win_pct   = round(winning['pnl_pct'].mean(), 2) if not winning.empty else 0.0
        avg_loss_pct  = round(losing['pnl_pct'].mean(), 2) if not losing.empty else 0.0
        profit_factor = round(
            winning['pnl'].sum() / abs(losing['pnl'].sum()), 2
        ) if not losing.empty and losing['pnl'].sum() != 0 else float('inf')
        avg_duration  = (
            (pd.to_datetime(trades['exit_date']) - pd.to_datetime(trades['entry_date']))
            .dt.days.mean()
        )
        avg_duration  = round(avg_duration, 1) if not pd.isna(avg_duration) else 0
    else:
        n_trades = win_rate = avg_win_pct = avg_loss_pct = profit_factor = avg_duration = 0

    # Buy & Hold para comparación
    prices = equity  # usamos equity como proxy de precio
    bh_return = round((equity.iloc[-1] / equity.iloc[0] - 1) * 100, 2)

    return {
        "total_return_pct":  total_return_pct,
        "annual_return_pct": annual_return_pct,
        "max_drawdown_pct":  max_drawdown_pct,
        "sharpe_ratio":      sharpe,
        "sortino_ratio":     sortino,
        "n_trades":          n_trades,
        "win_rate_pct":      win_rate,
        "avg_win_pct":       avg_win_pct,
        "avg_loss_pct":      avg_loss_pct,
        "profit_factor":     profit_factor,
        "avg_duration_days": avg_duration,
        "initial_capital":   initial,
        "final_capital":     final,
        "period_days":       days,
    }


def score(metrics: dict) -> float:
    """
    Puntaje compuesto para rankear estrategias/tickers (0-100).
    Pondera: Sharpe, win rate, profit factor, drawdown.
    """
    sharpe_score  = min(metrics['sharpe_ratio'] * 20, 30)
    winrate_score = min(metrics['win_rate_pct'] * 0.4, 25)
    pf_score      = min(metrics['profit_factor'] * 5, 25) if metrics['profit_factor'] != float('inf') else 25
    dd_score      = max(20 + metrics['max_drawdown_pct'], 0)  # drawdown es negativo

    return round(sharpe_score + winrate_score + pf_score + dd_score, 1)
