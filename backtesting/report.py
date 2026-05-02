import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from utils.data_fetcher import get_ohlcv, get_multiple
from backtesting.engine import run_backtest, run_multiple
from backtesting.metrics import calculate_metrics, score
from backtesting.strategy import STRATEGIES


def print_report(ticker: str, result: dict, metrics: dict) -> None:
    """Imprime reporte formateado de un backtest individual."""
    print(f"\n{'='*55}")
    print(f"  {ticker} — {result['strategy']}")
    print(f"  {result['period_start'].date()} → {result['period_end'].date()}")
    print(f"{'='*55}")
    print(f"  Capital inicial : ${metrics['initial_capital']:>10,.2f}")
    print(f"  Capital final   : ${metrics['final_capital']:>10,.2f}")
    print(f"  Retorno total   : {metrics['total_return_pct']:>+8.2f}%")
    print(f"  Retorno anual   : {metrics['annual_return_pct']:>+8.2f}%")
    print(f"  Max drawdown    : {metrics['max_drawdown_pct']:>8.2f}%")
    print(f"  Sharpe ratio    : {metrics['sharpe_ratio']:>8.2f}")
    print(f"  Sortino ratio   : {metrics['sortino_ratio']:>8.2f}")
    print(f"{'─'*55}")
    print(f"  Trades totales  : {metrics['n_trades']}")
    print(f"  Win rate        : {metrics['win_rate_pct']:>8.1f}%")
    print(f"  Avg ganancia    : {metrics['avg_win_pct']:>+8.2f}%")
    print(f"  Avg pérdida     : {metrics['avg_loss_pct']:>+8.2f}%")
    print(f"  Profit factor   : {metrics['profit_factor']:>8.2f}")
    print(f"  Duración media  : {metrics['avg_duration_days']:>5.1f} días")
    print(f"{'─'*55}")
    print(f"  Score AlphaHunter: {score(metrics):.1f}/100")

    if not result['trades'].empty:
        print(f"\n  Últimos 5 trades:")
        cols = ['entry_date', 'exit_date', 'entry_price', 'exit_price', 'pnl_pct', 'exit_reason']
        print(result['trades'][cols].tail(5).to_string(index=False))


def run_report(
    tickers: list[str],
    strategy_name: str = "combined",
    period: str = "2y",
    initial_capital: float = 10_000.0,
    stop_loss_pct: float = 0.07,
    take_profit_pct: float = None,
    save_csv: bool = False,
) -> pd.DataFrame:
    """
    Genera reporte completo de backtest para múltiples tickers.

    Returns:
        DataFrame con métricas comparativas ordenadas por score
    """
    print(f"\nAlphaHunter Backtesting Report")
    print(f"Estrategia : {strategy_name} — {STRATEGIES[strategy_name].__doc__.strip().splitlines()[0]}")
    print(f"Tickers    : {len(tickers)} | Período: {period} | Capital: ${initial_capital:,.0f}")

    data = get_multiple(tickers, period=period)
    results_raw = run_multiple(data, strategy_name, initial_capital,
                               stop_loss_pct=stop_loss_pct,
                               take_profit_pct=take_profit_pct)

    summary = []
    for ticker, result in results_raw.items():
        try:
            m = calculate_metrics(result)
            s = score(m)
            print_report(ticker, result, m)
            summary.append({
                "ticker":            ticker,
                "score":             s,
                "retorno_pct":       m['total_return_pct'],
                "retorno_anual_pct": m['annual_return_pct'],
                "sharpe":            m['sharpe_ratio'],
                "max_drawdown_pct":  m['max_drawdown_pct'],
                "win_rate_pct":      m['win_rate_pct'],
                "profit_factor":     m['profit_factor'],
                "n_trades":          m['n_trades'],
                "capital_final":     m['final_capital'],
            })
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")

    df_summary = pd.DataFrame(summary).sort_values("score", ascending=False)

    print(f"\n{'='*55}")
    print("  RANKING FINAL")
    print(f"{'='*55}")
    print(df_summary.to_string(index=False))

    if save_csv:
        out = os.path.join(os.path.dirname(__file__), '..', 'data', f'backtest_{strategy_name}.csv')
        df_summary.to_csv(out, index=False)
        print(f"\nResultados guardados en: {out}")

    return df_summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlphaHunter Backtesting")
    parser.add_argument("--tickers", nargs="+", default=["AAPL", "MSFT", "NVDA", "TSLA", "BTC-USD"])
    parser.add_argument("--strategy", default="combined", choices=list(STRATEGIES.keys()))
    parser.add_argument("--period", default="2y")
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--stop-loss", type=float, default=0.07)
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()

    run_report(
        tickers=args.tickers,
        strategy_name=args.strategy,
        period=args.period,
        initial_capital=args.capital,
        stop_loss_pct=args.stop_loss,
        save_csv=args.csv,
    )
