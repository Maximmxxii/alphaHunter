"""
ml/predictor.py — Predicción en tiempo real para candidatos del screener

Toma la lista de tickers que pasaron el screener y genera
una predicción de probabilidad de subida para cada uno.

Flujo:
    1. Cargar modelo entrenado para cada ticker (o usar modelo genérico)
    2. Extraer features del día actual con build_features_live()
    3. Predecir probabilidad de subida (clase 1)
    4. Combinar con métricas del screener para ranking final

Interpretación de probabilidad:
    >= 0.70 : señal fuerte de compra
    0.55–0.70: señal moderada
    < 0.55  : señal débil / no operar
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from ml.features import build_features_live
from ml.trainer import load_model, train


def predict_ticker(
    df: pd.DataFrame,
    ticker: str,
    auto_train: bool = True,
    period_for_train: str = "3y",
) -> dict:
    """
    Genera predicción de probabilidad de subida para un ticker.

    Args:
        df              : DataFrame OHLCV crudo del ticker
        ticker          : Símbolo del activo
        auto_train      : Si True y no existe modelo, lo entrena automáticamente
        period_for_train: Período a usar si hay que entrenar desde cero

    Returns:
        Dict con: ticker, prob_sube, señal, precio_actual, features_hoy
    """
    # Cargar o entrenar modelo
    try:
        model, meta = load_model(ticker)
        feature_names = meta['feature_names']
    except FileNotFoundError:
        if not auto_train:
            raise
        print(f"[predictor] Modelo no encontrado para {ticker}. Entrenando...")
        from utils.data_fetcher import get_ohlcv
        df_train = get_ohlcv(ticker, period=period_for_train)
        result = train(df_train, ticker, save=True)
        model = result['model']
        feature_names = result['feature_names']

    # Features del día actual
    X_live = build_features_live(df)

    if X_live.empty:
        raise ValueError(f"No se pudieron calcular features para {ticker}")

    # Alinear columnas con las del modelo
    X_live = X_live.reindex(columns=feature_names, fill_value=0)

    # Probabilidad de subida (clase 1)
    prob = model.predict_proba(X_live)[0]
    prob_sube = round(float(prob[1]), 4)
    prob_baja = round(float(prob[0]), 4)

    # Clasificar señal
    if prob_sube >= 0.70:
        signal = "FUERTE_COMPRA"
    elif prob_sube >= 0.55:
        signal = "COMPRA"
    elif prob_baja >= 0.70:
        signal = "FUERTE_VENTA"
    elif prob_baja >= 0.55:
        signal = "VENTA"
    else:
        signal = "NEUTRAL"

    return {
        "ticker":        ticker,
        "prob_sube":     prob_sube,
        "prob_baja":     prob_baja,
        "señal":         signal,
        "precio_actual": round(df['Close'].iloc[-1], 2),
    }


def predict_screener_candidates(
    screener_df: pd.DataFrame,
    data_dict: dict,
    auto_train: bool = True,
) -> pd.DataFrame:
    """
    Genera predicciones ML para todos los tickers que salieron del screener.

    Args:
        screener_df : DataFrame retornado por screener.runner.run_screener()
        data_dict   : {ticker: DataFrame OHLCV} — de get_multiple()
        auto_train  : Si True, entrena modelos faltantes automáticamente

    Returns:
        DataFrame combinado con métricas del screener + predicción ML,
        ordenado por probabilidad de subida descendente
    """
    if screener_df.empty:
        print("[predictor] No hay candidatos del screener para predecir.")
        return pd.DataFrame()

    predicciones = []

    for _, row in screener_df.iterrows():
        ticker = row['ticker']
        if ticker not in data_dict:
            print(f"[WARN] {ticker}: sin datos OHLCV, saltando")
            continue

        try:
            pred = predict_ticker(data_dict[ticker], ticker, auto_train=auto_train)
            entry = {**row.to_dict(), **pred}
            predicciones.append(entry)
            print(f"  {ticker:<12} prob_sube={pred['prob_sube']:.2%} | señal={pred['señal']}")
        except Exception as e:
            print(f"  [WARN] {ticker}: {e}")

    if not predicciones:
        return pd.DataFrame()

    df_result = pd.DataFrame(predicciones)

    # Columnas relevantes primero
    cols_orden = ['ticker', 'señal', 'prob_sube', 'prob_baja', 'precio_actual',
                  'rsi', 'vol_ratio', 'macd', 'señales']
    cols_orden = [c for c in cols_orden if c in df_result.columns]
    otros = [c for c in df_result.columns if c not in cols_orden]

    return df_result[cols_orden + otros].sort_values("prob_sube", ascending=False)


if __name__ == "__main__":
    from utils.data_fetcher import get_ohlcv

    ticker = "AAPL"
    df = get_ohlcv(ticker, period="2y")

    print(f"\nPrediciendo {ticker}...")
    result = predict_ticker(df, ticker, auto_train=True)

    print(f"\n{'='*40}")
    print(f"  Ticker     : {result['ticker']}")
    print(f"  Precio     : ${result['precio_actual']}")
    print(f"  Prob sube  : {result['prob_sube']:.2%}")
    print(f"  Prob baja  : {result['prob_baja']:.2%}")
    print(f"  Señal      : {result['señal']}")
    print(f"{'='*40}")
