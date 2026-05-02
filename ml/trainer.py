"""
ml/trainer.py — Entrenamiento del modelo XGBoost

Flujo de entrenamiento:
    1. Construir features con ml/features.py
    2. Dividir en train/test respetando el orden temporal (sin shuffle)
    3. Balancear clases con scale_pos_weight
    4. Entrenar XGBoostClassifier con early stopping
    5. Guardar modelo en data/models/{ticker}_model.json

Por qué XGBoost:
    - Robusto con datos financieros ruidosos
    - Maneja features con escalas distintas sin normalización
    - Feature importance nativa para interpretar el modelo
    - Rápido en datasets medianos (< 50k filas)

División temporal:
    Usamos los primeros 80% del tiempo para train y el 20% restante
    para test. NO usamos shuffle para evitar data leakage (usar datos
    futuros para predecir el pasado).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pickle
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from ml.features import build_features

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)


def train(
    df: pd.DataFrame,
    ticker: str,
    forward_days: int = 5,
    target_threshold: float = 0.02,
    test_size: float = 0.2,
    n_estimators: int = 300,
    learning_rate: float = 0.05,
    max_depth: int = 4,
    save: bool = True,
) -> dict:
    """
    Entrena un modelo XGBoost para predecir si el precio sube en N días.

    Args:
        df               : DataFrame OHLCV crudo
        ticker           : Símbolo del activo (para nombrar el modelo guardado)
        forward_days     : Horizonte de predicción en días
        target_threshold : Retorno mínimo para etiquetar como "sube" (ej. 0.02 = 2%)
        test_size        : Fracción de datos para test (temporal, sin shuffle)
        n_estimators     : Número de árboles en el ensemble
        learning_rate    : Tasa de aprendizaje (eta)
        max_depth        : Profundidad máxima de cada árbol
        save             : Si True, guarda el modelo en data/models/

    Returns:
        Dict con: model, feature_names, train_score, test_score,
                  X_test, y_test, ticker, params
    """
    print(f"\n[trainer] Construyendo features para {ticker}...")
    X, y = build_features(df, forward_days=forward_days, target_threshold=target_threshold)

    if len(X) < 100:
        raise ValueError(f"Datos insuficientes: {len(X)} muestras. Se necesitan al menos 100.")

    # División temporal estricta — sin shuffle
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"[trainer] Train: {len(X_train)} muestras | Test: {len(X_test)} muestras")
    print(f"[trainer] Balance train: {y_train.mean():.1%} positivos")

    # Compensar desbalance de clases
    pos = (y_train == 1).sum()
    neg = (y_train == 0).sum()
    scale_pos_weight = neg / pos if pos > 0 else 1.0

    model = XGBClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    train_score = round(model.score(X_train, y_train) * 100, 2)
    test_score  = round(model.score(X_test, y_test) * 100, 2)

    print(f"[trainer] Accuracy train: {train_score}% | test: {test_score}%")

    # Feature importance top 10
    importance = pd.Series(model.feature_importances_, index=X.columns)
    top10 = importance.nlargest(10)
    print(f"\n[trainer] Top 10 features más importantes:")
    for feat, imp in top10.items():
        print(f"  {feat:<20} {imp:.4f}")

    result = {
        "model":         model,
        "feature_names": list(X.columns),
        "train_score":   train_score,
        "test_score":    test_score,
        "X_test":        X_test,
        "y_test":        y_test,
        "ticker":        ticker,
        "forward_days":  forward_days,
        "threshold":     target_threshold,
        "params": {
            "n_estimators":  n_estimators,
            "learning_rate": learning_rate,
            "max_depth":     max_depth,
        }
    }

    if save:
        _save_model(result)

    return result


def _save_model(result: dict) -> None:
    """Guarda el modelo y sus metadatos en data/models/."""
    ticker = result['ticker']
    model_path = os.path.join(MODELS_DIR, f"{ticker}_model.pkl")
    meta_path  = os.path.join(MODELS_DIR, f"{ticker}_meta.json")

    with open(model_path, 'wb') as f:
        pickle.dump(result['model'], f)

    meta = {
        "ticker":        ticker,
        "feature_names": result['feature_names'],
        "train_score":   result['train_score'],
        "test_score":    result['test_score'],
        "forward_days":  result['forward_days'],
        "threshold":     result['threshold'],
        "params":        result['params'],
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"[trainer] Modelo guardado → {model_path}")


def load_model(ticker: str) -> tuple:
    """
    Carga un modelo previamente entrenado desde disco.

    Args:
        ticker: Símbolo del activo

    Returns:
        (model, meta_dict)

    Raises:
        FileNotFoundError si el modelo no existe
    """
    model_path = os.path.join(MODELS_DIR, f"{ticker}_model.pkl")
    meta_path  = os.path.join(MODELS_DIR, f"{ticker}_meta.json")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modelo no encontrado para '{ticker}'. Entrena primero con trainer.train()")

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    with open(meta_path, 'r') as f:
        meta = json.load(f)

    return model, meta


def train_multiple(
    data_dict: dict,
    forward_days: int = 5,
    target_threshold: float = 0.02,
    **kwargs,
) -> dict:
    """
    Entrena modelos para múltiples tickers.

    Args:
        data_dict: {ticker: DataFrame} — salida de get_multiple()

    Returns:
        {ticker: resultado_train}
    """
    results = {}
    for ticker, df in data_dict.items():
        try:
            results[ticker] = train(df, ticker, forward_days, target_threshold, **kwargs)
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")
    return results


if __name__ == "__main__":
    from utils.data_fetcher import get_ohlcv

    df = get_ohlcv("AAPL", period="3y")
    result = train(df, ticker="AAPL", forward_days=5, target_threshold=0.02)
    print(f"\nTest accuracy: {result['test_score']}%")
