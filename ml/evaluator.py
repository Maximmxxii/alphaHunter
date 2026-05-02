"""
ml/evaluator.py — Evaluación de performance del modelo ML

Métricas calculadas:
    Accuracy   : % de predicciones correctas (baseline: 50%)
    Precision  : De las veces que predijo "sube", cuántas realmente subió
    Recall     : De las veces que realmente subió, cuántas predijo correctamente
    F1 Score   : Media armónica de precision y recall
    AUC-ROC    : Área bajo la curva ROC (1.0 = perfecto, 0.5 = aleatorio)
    Log Loss   : Penaliza predicciones confiadas pero incorrectas

Umbral óptimo:
    Por defecto XGBoost usa 0.5 como umbral de decisión.
    Esta función busca el umbral que maximiza el F1 score en el test set,
    lo cual es más útil en datos desbalanceados.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, log_loss, confusion_matrix,
    classification_report,
)


def evaluate(result: dict, threshold: float = 0.5) -> dict:
    """
    Evalúa el modelo sobre el conjunto de test.

    Args:
        result    : Dict retornado por trainer.train()
        threshold : Umbral de decisión para clase positiva (default 0.5)

    Returns:
        Dict con todas las métricas de evaluación
    """
    model     = result['model']
    X_test    = result['X_test']
    y_test    = result['y_test']
    ticker    = result['ticker']

    y_prob  = model.predict_proba(X_test)[:, 1]
    y_pred  = (y_prob >= threshold).astype(int)

    acc       = round(accuracy_score(y_test, y_pred) * 100, 2)
    precision = round(precision_score(y_test, y_pred, zero_division=0) * 100, 2)
    recall    = round(recall_score(y_test, y_pred, zero_division=0) * 100, 2)
    f1        = round(f1_score(y_test, y_pred, zero_division=0) * 100, 2)
    auc       = round(roc_auc_score(y_test, y_prob), 4)
    logloss   = round(log_loss(y_test, y_prob), 4)
    cm        = confusion_matrix(y_test, y_pred)

    return {
        "ticker":    ticker,
        "threshold": threshold,
        "accuracy":  acc,
        "precision": precision,
        "recall":    recall,
        "f1_score":  f1,
        "auc_roc":   auc,
        "log_loss":  logloss,
        "confusion_matrix": cm,
        "n_test":    len(y_test),
        "n_positive": int(y_test.sum()),
        "n_negative": int((y_test == 0).sum()),
    }


def find_optimal_threshold(result: dict, metric: str = "f1") -> float:
    """
    Busca el umbral de decisión que maximiza una métrica dada.

    Args:
        result : Dict retornado por trainer.train()
        metric : Métrica a maximizar ('f1', 'precision', 'recall', 'accuracy')

    Returns:
        Umbral óptimo (float entre 0 y 1)
    """
    model  = result['model']
    X_test = result['X_test']
    y_test = result['y_test']

    y_prob = model.predict_proba(X_test)[:, 1]
    thresholds = np.arange(0.3, 0.8, 0.01)
    best_score = -1
    best_threshold = 0.5

    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        if metric == "f1":
            s = f1_score(y_test, y_pred, zero_division=0)
        elif metric == "precision":
            s = precision_score(y_test, y_pred, zero_division=0)
        elif metric == "recall":
            s = recall_score(y_test, y_pred, zero_division=0)
        else:
            s = accuracy_score(y_test, y_pred)

        if s > best_score:
            best_score = s
            best_threshold = t

    return round(best_threshold, 2)


def print_evaluation(metrics: dict) -> None:
    """Imprime reporte de evaluación formateado."""
    cm = metrics['confusion_matrix']
    print(f"\n{'='*50}")
    print(f"  Evaluación ML — {metrics['ticker']}")
    print(f"{'='*50}")
    print(f"  Muestras test    : {metrics['n_test']} ({metrics['n_positive']} positivos / {metrics['n_negative']} negativos)")
    print(f"  Umbral decisión  : {metrics['threshold']}")
    print(f"{'─'*50}")
    print(f"  Accuracy         : {metrics['accuracy']}%")
    print(f"  Precision        : {metrics['precision']}%")
    print(f"  Recall           : {metrics['recall']}%")
    print(f"  F1 Score         : {metrics['f1_score']}%")
    print(f"  AUC-ROC          : {metrics['auc_roc']}")
    print(f"  Log Loss         : {metrics['log_loss']}")
    print(f"{'─'*50}")
    print(f"  Matriz de confusión:")
    print(f"              Pred Baja  Pred Sube")
    print(f"  Real Baja   {cm[0][0]:>8}   {cm[0][1]:>8}")
    print(f"  Real Sube   {cm[1][0]:>8}   {cm[1][1]:>8}")
    print(f"{'='*50}")


def evaluate_multiple(train_results: dict) -> pd.DataFrame:
    """
    Evalúa múltiples modelos y retorna tabla comparativa.

    Args:
        train_results: {ticker: resultado_train} — de trainer.train_multiple()

    Returns:
        DataFrame comparativo ordenado por AUC-ROC
    """
    rows = []
    for ticker, result in train_results.items():
        try:
            opt_threshold = find_optimal_threshold(result, metric="f1")
            m = evaluate(result, threshold=opt_threshold)
            print_evaluation(m)
            rows.append({
                "ticker":         ticker,
                "auc_roc":        m['auc_roc'],
                "accuracy_pct":   m['accuracy'],
                "precision_pct":  m['precision'],
                "recall_pct":     m['recall'],
                "f1_pct":         m['f1_score'],
                "log_loss":       m['log_loss'],
                "opt_threshold":  opt_threshold,
                "train_score":    result['train_score'],
                "test_score":     result['test_score'],
            })
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")

    return pd.DataFrame(rows).sort_values("auc_roc", ascending=False)


if __name__ == "__main__":
    from utils.data_fetcher import get_ohlcv
    from ml.trainer import train

    df = get_ohlcv("AAPL", period="3y")
    result = train(df, ticker="AAPL", save=False)

    opt = find_optimal_threshold(result, metric="f1")
    print(f"\nUmbral óptimo (F1): {opt}")

    metrics = evaluate(result, threshold=opt)
    print_evaluation(metrics)
