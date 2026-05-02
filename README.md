# AlphaHunter

Sistema cuantitativo de análisis y predicción de mercados financieros.

## Arquitectura

```
AlphaHunter/
├── screener/       # Filtrado masivo de tickers
├── backtesting/    # Validación histórica de estrategias
├── ml/             # Modelos de predicción
├── dashboard/      # Visualización de resultados
├── data/           # Datos descargados y cache
└── utils/          # Funciones compartidas
```

## Pipeline

[Screener] → [Backtesting] → [ML] → [Decisión]

## Stack

- yfinance — datos históricos y fundamentales
- pandas / numpy — procesamiento
- backtrader / vectorbt — backtesting
- scikit-learn / xgboost — predicción ML
- streamlit / plotly — dashboard
