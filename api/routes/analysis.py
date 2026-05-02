"""
api/routes/analysis.py — Análisis combinado: backtesting + ML por ticker
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

# Umbrales para la recomendación en lenguaje simple
def _build_recomendacion(ml_signal: str, ml_prob: float, backtest_return: float, winrate: float) -> str:
    """Genera recomendación en lenguaje simple combinando ML y backtest."""
    parts = []

    # ML
    if ml_signal in ("FUERTE_COMPRA",):
        parts.append("El modelo ML ve una oportunidad de compra fuerte")
    elif ml_signal == "COMPRA":
        parts.append("El modelo ML sugiere compra con moderada confianza")
    elif ml_signal in ("FUERTE_VENTA",):
        parts.append("El modelo ML anticipa caída")
    elif ml_signal == "VENTA":
        parts.append("El modelo ML sugiere precaución")
    else:
        parts.append("El modelo ML no tiene señal clara")

    # Backtest
    if backtest_return > 20:
        parts.append(f"la estrategia histórica generó +{backtest_return:.1f}% con {winrate:.0f}% de operaciones ganadoras")
    elif backtest_return > 5:
        parts.append(f"el backtest muestra retorno positivo de {backtest_return:.1f}%")
    elif backtest_return < -5:
        parts.append(f"el backtest histórico fue negativo ({backtest_return:.1f}%)")
    else:
        parts.append(f"el backtest muestra retorno neutro de {backtest_return:.1f}%")

    return ". ".join(parts).capitalize() + "."


@router.get("/analysis/{symbol}")
def analyze_symbol(
    symbol: str,
    strategy: str = Query(default="combined", description="Estrategia de backtesting"),
    period: str   = Query(default="1y",      description="Período histórico (ej: 1y, 6mo)"),
):
    """
    Análisis completo de un ticker: backtesting histórico + predicción ML.
    """
    from utils.data_fetcher import get_ohlcv
    from backtesting.engine import run_backtest
    from backtesting.metrics import calculate_metrics
    from ml.predictor import predict_ticker

    sym = symbol.upper()

    # 1. Datos OHLCV
    try:
        df = get_ohlcv(sym, period=period)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo obtener datos de {sym}: {str(e)}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Sin datos para {sym}")

    # 2. Backtesting
    backtest_return = 0.0
    backtest_winrate = 0.0
    backtest_trades = 0
    try:
        bt_result = run_backtest(df, strategy_name=strategy)
        metrics   = calculate_metrics(bt_result)
        backtest_return  = round(float(metrics.get("total_return_pct", 0.0)), 2)
        backtest_winrate = round(float(metrics.get("win_rate", 0.0)), 2)
        backtest_trades  = int(metrics.get("total_trades", 0))
    except Exception:
        # Backtest puede fallar si la estrategia no aplica; no es fatal
        pass

    # 3. ML
    ml_prob   = 0.5
    ml_signal = "NEUTRAL"
    try:
        pred      = predict_ticker(df, sym, auto_train=True)
        ml_prob   = round(float(pred["prob_sube"]), 4)
        ml_signal = pred["señal"]
    except Exception:
        pass

    recomendacion = _build_recomendacion(ml_signal, ml_prob, backtest_return, backtest_winrate)

    return {
        "symbol":           sym,
        "strategy":         strategy,
        "period":           period,
        "ml_prob":          ml_prob,
        "ml_signal":        ml_signal,
        "backtest_return":  backtest_return,
        "backtest_winrate": backtest_winrate,
        "backtest_trades":  backtest_trades,
        "recomendacion":    recomendacion,
    }
