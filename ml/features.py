"""
ml/features.py — Construcción de features para el modelo ML

Transforma indicadores técnicos en features numéricas listas para
entrenar y predecir con XGBoost.

Lógica de etiquetado (target):
    - Se calcula el retorno del precio N días hacia adelante
    - Si el retorno >= umbral positivo → clase 1 (sube)
    - Si el retorno <= umbral negativo → clase -1 (baja)
    - En caso contrario → clase 0 (neutral, excluido del entrenamiento)

Features incluidas:
    Momentum   : rsi_14, macd, macd_hist, bb_pct_b
    Tendencia  : distancia % a SMA20, SMA50, SMA200
    Volatilidad: atr_14 normalizado, bb_bandwidth
    Volumen    : vol_ratio, cambio de volumen 5d
    Precio     : retornos 1d, 3d, 5d, 10d, 20d
    Polymarket : sentiment_score, prob_recession, prob_fed_cut (opcionales)
                 Se agregan como constantes en la fila actual de predicción.
                 No se usan en entrenamiento histórico (no había datos pasados).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from screener.indicators import compute_all


def build_features(
    df: pd.DataFrame,
    forward_days: int = 5,
    target_threshold: float = 0.02,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Genera la matriz de features X y el vector de targets y.

    Args:
        df               : DataFrame OHLCV crudo
        forward_days     : Días hacia adelante para calcular el retorno objetivo
        target_threshold : Umbral mínimo de retorno para etiquetar como sube/baja
                           (ej. 0.02 = 2%)

    Returns:
        X : DataFrame de features (una fila por día)
        y : Series con etiquetas binarias (1=sube, 0=no sube)
            Solo incluye filas con señal clara (excluye neutral)
    """
    df = compute_all(df)

    features = pd.DataFrame(index=df.index)

    # --- Momentum ---
    features['rsi_14']      = df['rsi_14']
    features['rsi_norm']    = (df['rsi_14'] - 50) / 50          # normalizado -1 a 1
    features['macd']        = df['macd']
    features['macd_hist']   = df['macd_hist']
    features['bb_pct_b']    = df['bb_pct_b']

    # --- Tendencia: distancia % del precio a cada media ---
    features['dist_sma20']  = (df['Close'] / df['sma_20'] - 1) * 100
    features['dist_sma50']  = (df['Close'] / df['sma_50'] - 1) * 100
    features['dist_sma200'] = (df['Close'] / df['sma_200'] - 1) * 100
    features['sma20_50']    = (df['sma_20'] / df['sma_50'] - 1) * 100   # cruce

    # --- Volatilidad ---
    features['atr_pct']     = df['atr_14'] / df['Close'] * 100  # ATR como % del precio
    features['bb_width']    = df['bb_bandwidth']

    # --- Volumen ---
    features['vol_ratio']   = df['vol_ratio']
    features['vol_change5'] = df['Volume'].pct_change(5) * 100

    # --- Retornos históricos ---
    for n in [1, 3, 5, 10, 20]:
        features[f'ret_{n}d'] = df['Close'].pct_change(n) * 100

    # --- Target: retorno futuro ---
    future_return = df['Close'].shift(-forward_days) / df['Close'] - 1

    # Etiquetado binario: 1 si sube >= threshold, 0 si no
    target = pd.Series(np.nan, index=df.index)
    target[future_return >= target_threshold]  = 1
    target[future_return <= -target_threshold] = 0

    # Alinear y limpiar
    features = features.dropna()
    target = target.dropna()
    common = features.index.intersection(target.index)

    X = features.loc[common]
    y = target.loc[common]

    # Eliminar filas con NaN en target (neutras)
    mask = y.notna()
    return X[mask], y[mask].astype(int)


def build_features_live(df: pd.DataFrame, polymarket_sentiment: dict = None) -> pd.DataFrame:
    """
    Genera features para predicción en tiempo real (sin target).
    Retorna solo la última fila disponible con todas las features.

    Args:
        df                   : DataFrame OHLCV crudo
        polymarket_sentiment : Dict retornado por get_macro_sentiment().
                               Si se provee, agrega prob_recession, prob_fed_cut
                               y sentiment_score como features adicionales.

    Returns:
        DataFrame de 1 fila con las features del día actual
    """
    df = compute_all(df)
    features = pd.DataFrame(index=df.index)

    features['rsi_14']      = df['rsi_14']
    features['rsi_norm']    = (df['rsi_14'] - 50) / 50
    features['macd']        = df['macd']
    features['macd_hist']   = df['macd_hist']
    features['bb_pct_b']    = df['bb_pct_b']
    features['dist_sma20']  = (df['Close'] / df['sma_20'] - 1) * 100
    features['dist_sma50']  = (df['Close'] / df['sma_50'] - 1) * 100
    features['dist_sma200'] = (df['Close'] / df['sma_200'] - 1) * 100
    features['sma20_50']    = (df['sma_20'] / df['sma_50'] - 1) * 100
    features['atr_pct']     = df['atr_14'] / df['Close'] * 100
    features['bb_width']    = df['bb_bandwidth']
    features['vol_ratio']   = df['vol_ratio']
    features['vol_change5'] = df['Volume'].pct_change(5) * 100

    for n in [1, 3, 5, 10, 20]:
        features[f'ret_{n}d'] = df['Close'].pct_change(n) * 100

    result = features.dropna().iloc[[-1]]  # solo última fila

    # Agregar features de Polymarket si están disponibles
    if polymarket_sentiment:
        result['poly_sentiment']    = polymarket_sentiment.get('sentiment_score', 0.5)
        result['poly_recession']    = polymarket_sentiment.get('prob_recession') or 0.5
        result['poly_fed_cut']      = polymarket_sentiment.get('prob_fed_cut') or 0.5
        result['poly_btc_crash']    = polymarket_sentiment.get('prob_btc_crash') or 0.5
        result['poly_sp_crash']     = polymarket_sentiment.get('prob_sp_crash') or 0.5

    return result


if __name__ == "__main__":
    from utils.data_fetcher import get_ohlcv

    df = get_ohlcv("AAPL", period="2y")
    X, y = build_features(df, forward_days=5, target_threshold=0.02)

    print(f"Features  : {X.shape[1]} columnas")
    print(f"Muestras  : {len(X)} filas")
    print(f"Balance   : {y.mean():.1%} positivos ({y.sum()} sube / {(y==0).sum()} baja)")
    print(f"\nFeatures:\n{list(X.columns)}")
    print(f"\nÚltima fila:\n{X.tail(1).T}")
