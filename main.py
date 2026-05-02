"""
main.py — Pipeline completo de AlphaHunter

Orquesta las 3 etapas del sistema en un solo comando:

    [Screener] → filtra candidatos del mercado
         ↓
    [Backtesting] → valida cada candidato históricamente
         ↓
    [ML Predicción] → rankea por probabilidad de subida
         ↓
    [Output] → tabla final priorizada + CSV opcional

Uso:
    python main.py
    python main.py --strategy combined --period 2y --capital 10000
    python main.py --tickers AAPL MSFT NVDA --csv
    python main.py --dashboard    # abre el dashboard en el navegador
"""

import sys
import os
import argparse
import subprocess
import pandas as pd

from utils.data_fetcher import get_multiple
from screener.runner import run_screener
from screener.filters import STRATEGIES as SCREENER_STRATEGIES
from backtesting.report import run_report
from backtesting.strategy import STRATEGIES as BT_STRATEGIES
from ml.predictor import predict_screener_candidates
from ml.trainer import train_multiple

# Tickers por defecto
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMZN",
    "JPM", "V", "UNH", "JNJ", "XOM",
    "BTC-USD", "ETH-USD", "SOL-USD",
    "SPY", "QQQ",
]


def run_pipeline(
    tickers: list[str],
    screener_strategy: str = "momentum_alcista",
    bt_strategy: str = "combined",
    period: str = "2y",
    capital: float = 10_000.0,
    stop_loss: float = 0.07,
    auto_train_ml: bool = True,
    save_csv: bool = False,
) -> pd.DataFrame:
    """
    Ejecuta el pipeline completo: screener → backtesting → ML.

    Args:
        tickers            : Lista de símbolos a analizar
        screener_strategy  : Estrategia de filtrado del screener
        bt_strategy        : Estrategia de backtesting
        period             : Período histórico de datos
        capital            : Capital inicial para backtesting
        stop_loss          : Stop loss porcentual (0.07 = 7%)
        auto_train_ml      : Si True, entrena modelos ML automáticamente
        save_csv           : Si True, guarda resultados en data/

    Returns:
        DataFrame final con ranking combinado: score_bt + prob_sube ML
    """
    print("\n" + "="*60)
    print("  AlphaHunter — Pipeline completo")
    print("="*60)
    print(f"  Tickers    : {len(tickers)}")
    print(f"  Screener   : {screener_strategy}")
    print(f"  Backtesting: {bt_strategy}")
    print(f"  Período    : {period}")
    print(f"  Capital    : ${capital:,.0f}")
    print("="*60)

    # ── Etapa 1: Screener ──────────────────────────────────────
    print("\n📡 ETAPA 1 — SCREENER")
    screener_df = run_screener(
        tickers=tickers,
        strategy=screener_strategy,
        period=period,
    )

    if screener_df.empty:
        print("\nNo hay candidatos. Prueba con otra estrategia o más tickers.")
        return pd.DataFrame()

    candidatos = screener_df['ticker'].tolist()
    print(f"\n→ {len(candidatos)} candidatos: {candidatos}")

    # ── Carga de datos para candidatos ────────────────────────
    print("\n📥 Cargando datos históricos de candidatos...")
    data_dict = get_multiple(candidatos, period=period)

    # ── Etapa 2: Backtesting ───────────────────────────────────
    print("\n⚙️  ETAPA 2 — BACKTESTING")
    bt_summary = run_report(
        tickers=candidatos,
        strategy_name=bt_strategy,
        period=period,
        initial_capital=capital,
        stop_loss_pct=stop_loss,
        save_csv=save_csv,
    )

    # ── Etapa 3: ML Predicción ─────────────────────────────────
    print("\n🤖 ETAPA 3 — ML PREDICCIÓN")

    if auto_train_ml:
        print("Entrenando modelos ML para candidatos...")
        train_multiple(data_dict, forward_days=5, target_threshold=0.02)

    ml_df = predict_screener_candidates(screener_df, data_dict, auto_train=auto_train_ml)

    # ── Combinar resultados ────────────────────────────────────
    if not ml_df.empty and not bt_summary.empty:
        final = ml_df.merge(
            bt_summary[['ticker', 'score', 'retorno_pct', 'sharpe', 'win_rate_pct']],
            on='ticker',
            how='left',
        )
        # Score final: 60% ML + 40% backtesting
        if 'score' in final.columns:
            final['score_final'] = (
                final['prob_sube'] * 60 +
                final['score'].fillna(0) * 0.40
            ).round(2)
            final = final.sort_values("score_final", ascending=False)
        else:
            final = final.sort_values("prob_sube", ascending=False)
    else:
        final = ml_df if not ml_df.empty else screener_df

    # ── Output final ───────────────────────────────────────────
    print("\n" + "="*60)
    print("  RANKING FINAL ALPHAHUNTER")
    print("="*60)

    cols_show = ['ticker', 'señal', 'prob_sube', 'precio_actual',
                 'score_final', 'retorno_pct', 'sharpe', 'win_rate_pct', 'rsi', 'vol_ratio']
    cols_show = [c for c in cols_show if c in final.columns]
    print(final[cols_show].to_string(index=False))

    if save_csv:
        out_path = os.path.join('data', 'ranking_final.csv')
        final.to_csv(out_path, index=False)
        print(f"\n💾 Ranking guardado en: {out_path}")

    return final


def main():
    parser = argparse.ArgumentParser(
        description="AlphaHunter — Sistema cuantitativo de análisis de mercados"
    )
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_TICKERS,
        help="Lista de símbolos a analizar"
    )
    parser.add_argument(
        "--screener-strategy", default="momentum_alcista",
        choices=list(SCREENER_STRATEGIES.keys()),
        help="Estrategia del screener"
    )
    parser.add_argument(
        "--bt-strategy", default="combined",
        choices=list(BT_STRATEGIES.keys()),
        help="Estrategia de backtesting"
    )
    parser.add_argument("--period",   default="2y",      help="Período histórico")
    parser.add_argument("--capital",  type=float, default=10_000.0, help="Capital inicial USD")
    parser.add_argument("--stop-loss", type=float, default=0.07,    help="Stop loss porcentual")
    parser.add_argument("--csv",      action="store_true", help="Guardar resultados en CSV")
    parser.add_argument("--no-ml",    action="store_true", help="Saltar etapa ML")
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Abrir el dashboard de Streamlit"
    )

    args = parser.parse_args()

    if args.dashboard:
        dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'app.py')
        print("Abriendo dashboard AlphaHunter...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])
        return

    run_pipeline(
        tickers=args.tickers,
        screener_strategy=args.screener_strategy,
        bt_strategy=args.bt_strategy,
        period=args.period,
        capital=args.capital,
        stop_loss=args.stop_loss,
        auto_train_ml=not args.no_ml,
        save_csv=args.csv,
    )


if __name__ == "__main__":
    main()
