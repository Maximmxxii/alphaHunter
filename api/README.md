# AlphaHunter API

Backend REST para el frontend React Native / Expo de AlphaHunter.

## Arrancar

```bash
# Desde el root del proyecto
python api/run.py

# O directamente con uvicorn
uvicorn api.main:app --reload --port 8000
```

Docs interactivos: http://localhost:8000/docs

---

## Endpoints

### Health

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Estado del servicio |
| GET | `/health` | Health check |

---

### Screener

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/screener` | Ejecuta el screener |
| GET | `/api/strategies` | Lista de estrategias disponibles |

**GET /api/screener**

Query params:
- `strategy` (default: `momentum_alcista`) — nombre de la estrategia
- `period` (default: `1y`) — período histórico (`6mo`, `1y`, `2y`)

Respuesta:
```json
[
  {
    "ticker": "NVDA",
    "precio": 875.40,
    "señales_activas": ["Tendencia de fondo positiva", "Impulso creciente"],
    "signal_score": 60,
    "sl_price": 831.63,
    "tp_price": 1050.48,
    "sector": "Technology",
    "nombre_empresa": "NVIDIA Corporation"
  }
]
```

**GET /api/strategies**

```json
[
  {
    "name": "momentum_alcista",
    "description": "Busca acciones con impulso alcista: volumen alto, tendencia positiva y MACD creciente.",
    "label": "Momentum Alcista"
  }
]
```

---

### Market

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/market/ticker/{symbol}` | Precio actual y datos del ticker |
| GET | `/api/market/logo/{symbol}` | URL del logo de la empresa |

**GET /api/market/ticker/AAPL**

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "sector": "Technology",
  "current_price": 189.30,
  "prev_close": 187.00,
  "pct_change": 1.23,
  "market_cap": 2950000000000,
  "currency": "USD"
}
```

**GET /api/market/logo/AAPL**

```json
{
  "symbol": "AAPL",
  "logo_url": "https://logo.clearbit.com/apple.com",
  "domain": "apple.com"
}
```

---

### Trading (Alpaca)

> Si Alpaca no está configurado (sin API keys en `.env`), todos los endpoints retornan `{"error": "Alpaca no configurado", "configured": false}` con status 200.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/account` | Balance y P&L de la cuenta |
| GET | `/api/positions` | Posiciones abiertas |
| POST | `/api/entry` | Colocar orden de compra bracket |
| DELETE | `/api/positions/{symbol}` | Cerrar posición |

**GET /api/account**

```json
{
  "balance": 25430.12,
  "buying_power": 18200.00,
  "cash": 12100.00,
  "pl_today": 340.50,
  "pl_total": 1430.12,
  "configured": true
}
```

**GET /api/positions**

```json
[
  {
    "symbol": "AAPL",
    "qty": 10.0,
    "avg_entry_price": 180.00,
    "current_price": 189.30,
    "unrealized_pl": 93.00,
    "unrealized_plpc": 5.17,
    "sl_price": 171.00,
    "tp_price": 216.00,
    "trailing_floor": 171.00
  }
]
```

**POST /api/entry**

Body:
```json
{
  "symbol": "AAPL",
  "amount_usd": 1000
}
```

Respuesta:
```json
{
  "id": "abc123",
  "status": "accepted",
  "symbol": "AAPL",
  "qty": 5.2834,
  "amount_usd": 1000.00,
  "sl_price": 179.54,
  "tp_price": 226.80,
  "entry_price": 189.30
}
```

**DELETE /api/positions/AAPL**

```json
{
  "status": "closed",
  "symbol": "AAPL"
}
```

---

### Analysis

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/analysis/{symbol}` | Backtesting + ML para un ticker |

Query params:
- `strategy` (default: `combined`) — estrategia de backtesting
- `period` (default: `1y`) — período histórico

```json
{
  "symbol": "AAPL",
  "ml_prob": 0.72,
  "ml_signal": "FUERTE_COMPRA",
  "backtest_return": 18.40,
  "backtest_winrate": 62.5,
  "backtest_trades": 8,
  "recomendacion": "El modelo ML ve una oportunidad de compra fuerte. La estrategia histórica generó +18.4% con 63% de operaciones ganadoras."
}
```

---

### Journal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/journal` | Trades cerrados con P&L |
| GET | `/api/journal/stats` | Estadísticas agregadas |

**GET /api/journal/stats**

```json
{
  "total_trades": 42,
  "win_rate": 61.9,
  "avg_profit": 3.42,
  "total_pl": 2340.80,
  "avg_hold_hours": 6.2
}
```

---

## Variables de entorno requeridas (`.env`)

```env
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```
