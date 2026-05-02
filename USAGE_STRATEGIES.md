# Validación de Estrategias y Trading Automático

AlphaHunter ahora tiene **validación de activos por estrategia** y **trading automático** completamente integrado.

## 1. Validar un Ticker contra Estrategias

### Endpoint
```
GET /api/validate/{symbol}
```

### Ejemplo
```bash
curl http://localhost:8000/api/validate/AAPL
```

### Respuesta
```json
{
  "symbol": "AAPL",
  "matching_strategies": ["momentum_alcista", "cruce_dorado"],
  "total_matching": 2,
  "all_strategies": {
    "momentum_alcista": {
      "passes": true,
      "signals": ["high_volume", "macd_bullish_cross"],
      "symbol": "AAPL",
      "price": 215.43,
      "sl_price": 204.66,
      "tp_price": 258.52,
      "rsi_14": 45.23,
      "sma_20": 210.15,
      "sma_50": 205.87,
      "sma_200": 195.42,
      "macd": 0.0045,
      "volume": 52100000
    },
    "rebote_sobrevendido": {
      "passes": false,
      "signals": [],
      ...
    },
    ...
  }
}
```

## 2. Estrategias Disponibles en Screener

Tienes 5 estrategias predefinidas:

### `momentum_alcista` ⚡
**Descripción:** Acciones con impulso alcista
- RSI no sobrecomprado (<70)
- Precio por encima de SMA200
- Volumen alto (2x promedio)
- MACD cruce alcista

### `rebote_sobrevendido` 🔄
**Descripción:** Rebote desde zona de apoyo
- RSI sobrevendido (<35)
- Precio cerca banda inferior Bollinger
- Precio por encima de SMA200

### `cruce_dorado` 🌅
**Descripción:** Cambio de tendencia
- SMA20 cruza por encima de SMA50
- Precio por encima de SMA200

### `volatilidad_alta` 🌊
**Descripción:** Mercado activo
- Volumen inusual (1.5x promedio)
- MACD cruce alcista

### `exploratorio` 🗺️
**Descripción:** Exploración amplia
- RSI bajo (<45) O volumen alto (1.5x)

## 3. Trading Automático

### Endpoint
```
POST /api/auto-trade
```

### Configuración
```json
{
  "strategy": "momentum_alcista",
  "amount_usd": 500.0,
  "max_positions": 5,
  "sl_percent": 5.0,
  "tp_percent": 20.0
}
```

### Parámetros
- `strategy` — Estrategia screener a usar (default: momentum_alcista)
- `amount_usd` — USD invertidos por trade (default: 500)
- `max_positions` — Máximo de posiciones abiertas (default: 5)
- `sl_percent` — Stop loss como % del precio (default: 5%)
- `tp_percent` — Take profit como % del precio (default: 20%)

### Ejemplo con curl
```bash
curl -X POST http://localhost:8000/api/auto-trade \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "momentum_alcista",
    "amount_usd": 1000,
    "max_positions": 5,
    "sl_percent": 5,
    "tp_percent": 20
  }'
```

### Respuesta
```json
{
  "status": "success",
  "trades_placed": [
    {
      "symbol": "NVDA",
      "qty": 2.45,
      "order_id": "abc123",
      "status": "pending",
      "timestamp": "2026-04-17T14:32:10.123456"
    },
    {
      "symbol": "AMD",
      "qty": 5.12,
      "order_id": "def456",
      "status": "pending",
      "timestamp": "2026-04-17T14:32:11.456789"
    }
  ],
  "total_errors": 0,
  "errors": [],
  "config": {
    "strategy": "momentum_alcista",
    "amount_per_trade": 1000.0,
    "max_positions": 5
  }
}
```

## 4. Flujo Completo

### 1️⃣ Validar un activo
```bash
curl http://localhost:8000/api/validate/TSLA
```
→ Ver qué estrategias aplican

### 2️⃣ Ejecutar screener manual
```bash
curl "http://localhost:8000/api/screener?strategy=momentum_alcista&period=1y"
```
→ Ver candidatos completos con señales

### 3️⃣ Trading automático
```bash
curl -X POST http://localhost:8000/api/auto-trade \
  -H "Content-Type: application/json" \
  -d '{"strategy": "momentum_alcista", "amount_usd": 500}'
```
→ Coloca órdenes automáticamente

## 5. Ejemplos en Python

```python
import requests

API_URL = "http://localhost:8000"

# Validar AAPL
response = requests.get(f"{API_URL}/api/validate/AAPL")
data = response.json()

print(f"Estrategias que aplican: {data['matching_strategies']}")
print(f"Total: {data['total_matching']}")

# Auto-trade
config = {
    "strategy": "momentum_alcista",
    "amount_usd": 500,
    "max_positions": 5,
    "sl_percent": 5,
    "tp_percent": 20
}

response = requests.post(f"{API_URL}/api/auto-trade", json=config)
result = response.json()

print(f"Órdenes colocadas: {len(result['trades_placed'])}")
for trade in result['trades_placed']:
    print(f"  - {trade['symbol']}: {trade['qty']} @ {trade['status']}")
```

## 6. Reglas Importantes

- **Máximo de posiciones:** Respeta `max_positions`. Si ya tienes 5, no coloca más.
- **No duplicate:** No abre posición si ya tienes una abierta en ese símbolo.
- **SL/TP automático:** Cada orden incluye stop loss y take profit.
- **Validación de datos:** Si no hay datos para un ticker, lo salta.
- **Errores no detienen:** Si falla un trade, continúa con los demás.

## 7. Endpoints relacionados

- `GET /api/account` — Balance y P&L
- `GET /api/positions` — Posiciones abiertas
- `POST /api/entry` — Orden manual
- `DELETE /api/positions/{symbol}` — Cerrar posición
- `GET /api/strategies` — Listar estrategias disponibles
- `GET /api/screener?strategy=...&period=...` — Ejecutar screener
- `GET /api/validate/{symbol}` — Validar contra estrategias ⭐ NUEVO
- `POST /api/auto-trade` — Trading automático ⭐ NUEVO
