# AlphaHunter — Plan de Pruebas QA

**Versión:** 1.0  
**Fecha:** 2026-04-13  
**Stack:** FastAPI/Python (backend) · React Native/Expo (frontend) · Alpaca (broker) · yfinance

---

## 1. Test Cases por Pantalla

### 1.1 Home Screen (`app/(tabs)/index.tsx`)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| H-01 | Carga inicial con Alpaca configurado | Abrir app, ir a Home | Card muestra `cash` y `pl_today` con valores numéricos. Formato `$1,000` | P0 |
| H-02 | Carga inicial sin Alpaca configurado | Apagar backend o vaciar claves, abrir app | Card muestra `—` en capital y P&L. Sin crash ni stack trace visible | P0 |
| H-03 | Backend apagado al abrir app | Matar proceso `uvicorn`, abrir app | Card muestra `—`. No hay pantalla roja de error de React Native | P0 |
| H-04 | Dropdown muestra todas las estrategias | Tocar el ModeSelector | Se listan exactamente 5 estrategias: `momentum_alcista`, `rebote_sobrevendido`, `cruce_dorado`, `exploratorio`, `volatilidad_alta` | P1 |
| H-05 | Seleccionar modo y buscar | Seleccionar `rebote_sobrevendido`, pulsar BUSCAR | Navega a `/results` con `strategy=rebote_sobrevendido` en params | P0 |
| H-06 | P&L negativo se muestra en rojo | Simular cuenta con pérdida | `pl_today` aparece en `colors.danger` (rojo) con signo `-` | P1 |
| H-07 | P&L positivo se muestra en verde | Simular cuenta con ganancia | `pl_today` aparece en `colors.success` con signo `+` | P1 |
| H-08 | `pl_today_pct` no definido en respuesta | Backend retorna cuenta sin `pl_today_pct` | No crash al intentar `account.pl_today_pct * 100` — ver nota de bug abajo | P0 |

> **BUG POTENCIAL H-08:** `index.tsx` línea 71 accede a `account.pl_today_pct` pero el endpoint `/api/account` NO retorna ese campo (retorna `pl_today` y `pl_total`). Resultado: `undefined * 100 = NaN`, renderiza `NaN%`. Mismo problema en `positions.tsx` líneas 113 y 130.

---

### 1.2 Results Screen (`app/results.tsx`)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| R-01 | Animación de 4 pasos durante carga | Iniciar búsqueda | Los 4 pasos aparecen secuencialmente: 300ms, 900ms, 1600ms, 2300ms | P1 |
| R-02 | Transición a resultados cuando llega data | API responde antes que terminen los 4 pasos | Se espera a `progress >= 75` (paso 3) antes de mostrar lista | P1 |
| R-03 | Lista vacía — screener sin resultados | Estrategia con filtros muy estrictos | Pantalla vacía con mensaje y sugerencias, no lista en blanco sin texto | P0 |
| R-04 | Lista con 1 candidato | Screener retorna exactamente 1 resultado | Se muestra 1 card correctamente, sin errores de layout | P1 |
| R-05 | Lista con 20+ candidatos | Screener retorna muchos resultados | FlatList scrollea sin lag, rendimiento aceptable | P1 |
| R-06 | Tap en card navega a entry screen | Tocar una card de candidato | Navega a `/entry/[symbol]` con `candidateJson` en params | P0 |
| R-07 | Error de API durante carga | Backend devuelve 500 durante screener | Se muestra mensaje de error, no pantalla roja | P0 |
| R-08 | Estrategia inválida en params | Navegar a `/results?strategy=fake` | El backend retorna 400, el frontend lo maneja mostrando error o lista vacía | P1 |
| R-09 | `signal_score` se muestra en card | Revisar CandidateCard con candidato real | Badge de score visible (0-100), color coherente con valor | P2 |

---

### 1.3 Entry Screen (`app/entry/[symbol].tsx`)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| E-01 | SL y TP se muestran correctamente | Abrir entry de cualquier ticker | `sl_price = precio * 0.95`, `tp_price = precio * 1.20`. Valores visibles en ProtectionBlocks | P0 |
| E-02 | Cambiar monto recalcula shares en tiempo real | Escribir `500` en el input | `shares = 500 / precio`. Se actualiza sin pulsar enter | P0 |
| E-03 | Cambiar monto recalcula potencial en tiempo real | Escribir `2000` en el input | "Ganar hasta" y "Perder máx" se actualizan al instante | P0 |
| E-04 | Monto $0 bloqueado | Borrar el campo y dejar `0` o vacío | Alert: "Monto inválido — Ingresa un monto mayor a $0". Orden no se envía | P0 |
| E-05 | Monto vacío bloqueado | Borrar todo el texto del input | `parseFloat('') = NaN → amountNum = 0` → mismo alert que E-04 | P0 |
| E-06 | Monto mayor a buying_power bloqueado | Ingresar monto superior al disponible | Alert: "Fondos insuficientes — Tu poder de compra es $X". Orden no se envía | P0 |
| E-07 | Logo empresa se carga correctamente | Abrir entry de AAPL | Logo de apple.com visible en círculo superior izquierdo | P1 |
| E-08 | Logo no disponible muestra iniciales | Abrir entry de ticker sin logo (ej: ticker oscuro) | Se muestran las 2 primeras letras del ticker. Sin imagen rota | P1 |
| E-09 | Confirmar entrada exitosa | Flujo completo con Alpaca paper configurado | Navega a `/positions`, alert de confirmación con ticker y precio | P0 |
| E-10 | Error al confirmar entrada | Alpaca no configurado, pulsar confirmar | Alert: "Error al ejecutar la orden" con mensaje del backend | P0 |
| E-11 | Botón muestra monto actualizado | Escribir `750` | Botón dice `CONFIRMAR ENTRADA — $750` | P1 |
| E-12 | Ticker con precio alto (BRK.A ~$600k) | Abrir entry de BRK.A con monto $1000 | `shares = 0.0017`. Ningún crash. Validación de fondos insuficientes si aplica | P1 |
| E-13 | `candidateJson` corrupto en params | Navegar a entry con JSON malformado | Se muestra pantalla "Candidato no encontrado" con link de volver | P1 |
| E-14 | Doble tap en confirmar | Pulsar confirmar dos veces rápido | Solo se envía una orden. Botón queda disabled durante `submitting=true` | P0 |
| E-15 | Relación riesgo/beneficio | Verificar con SL=5%, TP=20% | RR ratio = `1 a 4.0` (20/5). Se muestra correctamente | P2 |

---

### 1.4 Positions Screen (`app/(tabs)/positions.tsx`)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| P-01 | Sin posiciones abiertas | Cuenta sin trades | Pantalla vacía con mensaje y sugerencia de ir a Home | P1 |
| P-02 | Posiciones cargadas correctamente | Cuenta con 2-3 posiciones paper | Cards muestran: symbol, qty, precio entrada, precio actual, P&L, SL/TP | P0 |
| P-03 | Barra SL/TP visible | Revisar PositionCard | Barra de progreso entre SL y TP con posición actual marcada | P1 |
| P-04 | P&L positivo en verde, negativo en rojo | Posición ganadora y perdedora | Colores correctos en `unrealized_pl` | P1 |
| P-05 | Cerrar posición — flujo completo | Tocar "Cerrar" en una posición | Alert de confirmación → pulsar "Cerrar" → posición desaparece de lista | P0 |
| P-06 | Cancelar cierre de posición | Tocar "Cerrar" → pulsar "Cancelar" | Posición permanece. No se llama al endpoint DELETE | P0 |
| P-07 | Estado cargando durante cierre | Pulsar "Cerrar" y confirmar | Card muestra indicador de carga mientras `isPending=true` para ese symbol | P1 |
| P-08 | Error en cierre de posición | Backend apagado, intentar cerrar | Alert con mensaje de error amigable. Posición no desaparece de lista | P0 |
| P-09 | Pull to refresh | Swipe hacia abajo en la lista | Refresca posiciones, spinner visible durante petición | P2 |
| P-10 | Alpaca no configurado | Sin claves de Alpaca | Backend retorna `{"error": "Alpaca no configurado", "configured": false}` y frontend lo maneja sin crash | P0 |
| P-11 | Métricas de cuenta en header | Revisrar grid de Capital/Hoy/Total | Valores consistentes con `/api/account`. `pl_today_pct` — ver bug H-08 | P0 |

---

### 1.5 Smart Money (modo congresistas / ballenas)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| SM-01 | Modo "Siguiendo congresistas" | Seleccionar modo y buscar | Llama a `/api/smart-money/signals?mode=congress`, retorna trades | P0 |
| SM-02 | Modo "Siguiendo ballenas" | Seleccionar modo y buscar | Llama a `/api/smart-money/signals?mode=whales`, retorna consensus buys | P0 |
| SM-03 | Lista de trades políticos — vacía | Capitol Trades sin datos nuevos | Muestra estado vacío, no crash. `data: []` con `status: ok` | P1 |
| SM-04 | Modo inválido en signals | GET `/api/smart-money/signals?mode=invalid` | Error 422 de FastAPI (pattern no cumplido) | P1 |
| SM-05 | option_type inválido en options | GET `/api/smart-money/options?option_type=xyz` | Error 422 de FastAPI (pattern `^(all|calls|puts)$` no cumplido) | P1 |
| SM-06 | Holdings de inversor desconocido | GET `/api/smart-money/whales/holdings/nobody` | Retorna lista vacía o error 404 con mensaje claro, no 500 | P1 |

---

### 1.6 History Screen (`app/(tabs)/history.tsx`)

| ID | Descripción | Pasos | Resultado esperado | Prioridad |
|----|-------------|-------|--------------------|-----------|
| HI-01 | Sin historial | Journal vacío | Pantalla vacía con mensaje, no lista en blanco | P1 |
| HI-02 | Estadísticas con trades cerrados | Journal con 5+ trades | `win_rate`, `avg_profit`, `total_pl` se muestran con formato correcto | P1 |
| HI-03 | `pnl_pct` null en un trade | Trade con campo faltante | No crash. Muestra `—` o `0.00%` | P1 |

---

## 2. Tests de API — Comandos curl

```bash
# ── Health ──────────────────────────────────────────────────────────────────

# GET /
curl -s http://localhost:8000/ | python3 -m json.tool
# Esperado: {"status": "ok", "service": "AlphaHunter API", "version": "1.0.0"}

# GET /health
curl -s http://localhost:8000/health
# Esperado: {"status": "ok"}


# ── Strategies ──────────────────────────────────────────────────────────────

# GET /api/strategies — lista de estrategias disponibles
curl -s http://localhost:8000/api/strategies | python3 -m json.tool
# Esperado: array de 5 objetos con keys: name, description, label


# ── Screener ────────────────────────────────────────────────────────────────

# Estrategia válida
curl -s "http://localhost:8000/api/screener?strategy=momentum_alcista" | python3 -m json.tool
# Esperado: array (puede ser vacío []) con objetos {ticker, precio, señales_activas, sl_price, tp_price, ...}

# Estrategia válida con período
curl -s "http://localhost:8000/api/screener?strategy=rebote_sobrevendido&period=6mo" | python3 -m json.tool

# Estrategia inválida → 400 (no 422)
curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000/api/screener?strategy=inexistente"
# Esperado: HTTP_STATUS:400 con detail que lista estrategias válidas

# Sin parámetros → usa default momentum_alcista
curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000/api/screener"
# Esperado: HTTP_STATUS:200


# ── Account ─────────────────────────────────────────────────────────────────

# Con Alpaca configurado
curl -s http://localhost:8000/api/account | python3 -m json.tool
# Esperado: {balance, buying_power, cash, pl_today, pl_total, portfolio_value, status, currency, configured: true}

# Sin Alpaca configurado (vaciar .env y reiniciar servidor)
curl -s http://localhost:8000/api/account
# Esperado: {"error": "Alpaca no configurado", "configured": false}  HTTP 200 (no 500)


# ── Positions ───────────────────────────────────────────────────────────────

# Con posiciones abiertas
curl -s http://localhost:8000/api/positions | python3 -m json.tool
# Esperado: array de objetos {symbol, qty, side, avg_entry_price, current_price, market_value, unrealized_pl, sl_price, tp_price}

# Sin Alpaca configurado
curl -s http://localhost:8000/api/positions
# Esperado: {"error": "Alpaca no configurado", "configured": false}


# ── Entry ────────────────────────────────────────────────────────────────────

# Entrada válida (requiere Alpaca paper configurado)
curl -s -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "amount_usd": 1000}' | python3 -m json.tool
# Esperado: {id, status, symbol, side, qty, amount_usd, sl_price, tp_price, entry_price}

# Sin symbol → 422
curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"amount_usd": 1000}'
# Esperado: HTTP_STATUS:422

# amount_usd = 0 → 422 (validación gt=0 en Pydantic)
curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "amount_usd": 0}'
# Esperado: HTTP_STATUS:422

# amount_usd negativo → 422
curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "amount_usd": -500}'
# Esperado: HTTP_STATUS:422

# Ticker inválido
curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XYZXYZXYZ999", "amount_usd": 1000}'
# Esperado: HTTP_STATUS:400 con mensaje "No se pudo obtener precio de XYZXYZXYZ999"

# Sin Alpaca configurado
curl -s -X POST http://localhost:8000/api/entry \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "amount_usd": 1000}'
# Esperado: {"error": "Alpaca no configurado", "configured": false}  HTTP 200


# ── Close position ──────────────────────────────────────────────────────────

# Cerrar posición existente (requiere posición abierta)
curl -s -X DELETE http://localhost:8000/api/positions/AAPL | python3 -m json.tool
# Esperado: {"status": "closed", "symbol": "AAPL", "detail": {...}}

# Sin Alpaca configurado
curl -s -X DELETE http://localhost:8000/api/positions/AAPL
# Esperado: {"error": "Alpaca no configurado", "configured": false}


# ── Market data ─────────────────────────────────────────────────────────────

# Ticker conocido
curl -s http://localhost:8000/api/market/ticker/AAPL | python3 -m json.tool
# Esperado: {symbol, name, sector, current_price, prev_close, pct_change, market_cap, volume, currency}

# Ticker desconocido
curl -s -w "\nHTTP_STATUS:%{http_code}" http://localhost:8000/api/market/ticker/XYZXYZ
# Esperado: HTTP_STATUS:500 con detail de error de yfinance

# Logo ticker conocido
curl -s http://localhost:8000/api/market/logo/AAPL
# Esperado: {"symbol": "AAPL", "logo_url": "https://logo.clearbit.com/apple.com", "domain": "apple.com"}

# Logo ticker desconocido (fallback)
curl -s http://localhost:8000/api/market/logo/UNKN
# Esperado: {"symbol": "UNKN", "logo_url": "https://logo.clearbit.com/unkn.com", "domain": null}


# ── Analysis ────────────────────────────────────────────────────────────────

# Análisis completo
curl -s "http://localhost:8000/api/analysis/MSFT?strategy=combined&period=1y" | python3 -m json.tool
# Esperado: {symbol, ml_prob, ml_signal, backtest_return, backtest_winrate, recomendacion}

# Símbolo sin datos
curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000/api/analysis/XXXYYY"
# Esperado: HTTP_STATUS:400 o 404


# ── Journal ─────────────────────────────────────────────────────────────────

curl -s http://localhost:8000/api/journal | python3 -m json.tool
curl -s http://localhost:8000/api/journal/stats | python3 -m json.tool


# ── Smart Money ─────────────────────────────────────────────────────────────

# Congress trades
curl -s "http://localhost:8000/api/smart-money/congress?limit=10" | python3 -m json.tool
# Esperado: {"status": "ok", "data": [...]}

# Whales — consensus buys
curl -s "http://localhost:8000/api/smart-money/whales?min_investors=3" | python3 -m json.tool

# Options flow
curl -s "http://localhost:8000/api/smart-money/options?option_type=calls" | python3 -m json.tool

# Signals combinadas
curl -s "http://localhost:8000/api/smart-money/signals?mode=all" | python3 -m json.tool
curl -s "http://localhost:8000/api/smart-money/signals?mode=congress" | python3 -m json.tool

# Modo inválido → 422
curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000/api/smart-money/signals?mode=invalid"
# Esperado: HTTP_STATUS:422

# option_type inválido → 422
curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000/api/smart-money/options?option_type=naked"
# Esperado: HTTP_STATUS:422


# ── CORS ────────────────────────────────────────────────────────────────────

# Verificar headers CORS
curl -s -I -H "Origin: http://localhost:8081" http://localhost:8000/api/strategies
# Esperado: Access-Control-Allow-Origin: *

# Preflight OPTIONS
curl -s -X OPTIONS \
  -H "Origin: http://localhost:8081" \
  -H "Access-Control-Request-Method: POST" \
  -I http://localhost:8000/api/entry
# Esperado: HTTP 200 con Access-Control-Allow-Methods que incluye POST
```

---

## 3. Tests de Seguridad Básicos

### 3.1 Inyección y inputs maliciosos

| ID | Vector | Endpoint | Payload | Resultado esperado |
|----|--------|----------|---------|-------------------|
| SEC-01 | SQL injection en estrategia | GET /api/screener | `strategy=' OR 1=1 --` | HTTP 400 — estrategia inválida. No expone info de BD |
| SEC-02 | Command injection en symbol | POST /api/entry | `symbol: "; rm -rf /"` | HTTP 422 o error de yfinance. Sin ejecución de comandos |
| SEC-03 | XSS en symbol market | GET /api/market/ticker/`<script>` | HTTP 200 o 500 de yfinance. El campo retornado es string plano, no ejecutado |
| SEC-04 | Path traversal en positions | DELETE /api/positions/../account | FastAPI no coincide la ruta, HTTP 404 |
| SEC-05 | JSON con campos extra | POST /api/entry con `{"symbol":"AAPL","amount_usd":100,"__proto__":{"admin":true}}` | Pydantic ignora campos extra. HTTP 200/error de Alpaca. Sin escalada |
| SEC-06 | Monto extremadamente grande | POST /api/entry con `amount_usd: 999999999999` | Alpaca rechaza la orden, no crash del servidor |
| SEC-07 | String como amount_usd | POST /api/entry con `amount_usd: "mil"` | HTTP 422 de Pydantic |
| SEC-08 | Null en symbol | POST /api/entry con `symbol: null` | HTTP 422 de Pydantic |

### 3.2 CORS

```bash
# allow_origins=["*"] con allow_credentials=True es una combinación inválida en browsers.
# Los browsers modernos rechazan credenciales cuando el origen es wildcard.
# RIESGO: si en el futuro se añaden cookies de sesión, esto romperá la autenticación.
# Recomendación: cambiar a allow_origins=["http://localhost:8081", "https://alphahunter.app"]
```

**SEC-09 — CORS configuración insegura:** `allow_origins=["*"]` con `allow_credentials=True` no es un bloqueo activo, pero es configuración incorrecta para producción. Registrar como deuda técnica.

### 3.3 Exposición de datos sensibles

| ID | Qué verificar | Cómo | Resultado esperado |
|----|--------------|------|-------------------|
| SEC-10 | Sin stack traces en producción | Forzar error 500, revisar `detail` | En producción, `detail` debe ser mensaje genérico, no traceback de Python |
| SEC-11 | Sin API keys en respuestas | Revisar cualquier endpoint de `/api/account` | La respuesta no contiene `API_KEY` ni `SECRET_KEY` |
| SEC-12 | `.env` no servido como archivo estático | GET /.env | HTTP 404 — FastAPI no monta archivos estáticos por defecto |
| SEC-13 | Sin `console.log` con datos sensibles en frontend | Revisar interceptor de axios en `api.ts` línea 26 | En producción (`!__DEV__`), el interceptor no loguea. Verificar que `__DEV__` sea false en builds de prod |

### 3.4 Autenticación (cuando se implemente)

> Actualmente no hay autenticación en ningún endpoint. Para cuando se implemente:

- Todo endpoint de `/api/` debe requerir token JWT válido
- Token expirado → HTTP 401 con mensaje claro
- Token malformado (`Bearer abc`) → HTTP 401
- Sin header Authorization → HTTP 401
- Token de otro usuario no debe acceder a posiciones ajenas

---

## 4. Checklist de Regresión Pre-Deploy

```
PRE-DEPLOY CHECKLIST — AlphaHunter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BACKEND (FastAPI)
[ ] GET / retorna {"status": "ok"} HTTP 200
[ ] GET /api/strategies retorna exactamente 5 estrategias
[ ] GET /api/screener?strategy=momentum_alcista retorna array (puede ser vacío)
[ ] GET /api/screener?strategy=invalida retorna HTTP 400
[ ] GET /api/account sin Alpaca retorna {"configured": false} HTTP 200 (no 500)
[ ] GET /api/positions sin Alpaca retorna {"configured": false} HTTP 200 (no 500)
[ ] POST /api/entry sin symbol retorna HTTP 422
[ ] POST /api/entry con amount_usd=0 retorna HTTP 422
[ ] POST /api/entry sin Alpaca retorna {"configured": false} HTTP 200 (no 500)
[ ] DELETE /api/positions/AAPL sin Alpaca retorna {"configured": false} HTTP 200 (no 500)
[ ] GET /api/smart-money/signals?mode=invalid retorna HTTP 422
[ ] Sin ningún console.log ni print() con datos de usuario en respuestas de API
[ ] Variables de entorno de producción configuradas (ALPACA_API_KEY, ALPACA_SECRET_KEY)

FRONTEND (React Native / Expo)
[ ] Home carga sin crash con backend apagado (muestra "—" en métricas)
[ ] Home carga sin crash con Alpaca no configurado
[ ] Dropdown muestra las 5 estrategias correctamente
[ ] Flujo búsqueda → resultados → entry → posiciones funciona end-to-end
[ ] Entry: monto $0 muestra alert sin enviar orden
[ ] Entry: monto > buying_power muestra alert sin enviar orden
[ ] Entry: doble tap en confirmar no envía dos órdenes
[ ] Logo no disponible muestra iniciales del ticker (no imagen rota)
[ ] Positions: lista vacía muestra estado vacío con mensaje
[ ] Positions: cerrar posición pide confirmación antes de ejecutar
[ ] Positions: error en cierre muestra alert (no pantalla roja)
[ ] Results: screener vacío muestra estado vacío con mensaje
[ ] Results: error de API muestra mensaje amigable
[ ] pl_today_pct accedido en index.tsx y positions.tsx — verificar que no retorna NaN

SMART MONEY
[ ] Modo congress retorna datos con estructura {status: "ok", data: [...]}
[ ] Modo whales retorna datos con estructura {status: "ok", data: [...]}
[ ] Cualquier falla de scraping retorna error 500 con mensaje, no crash del servidor

PERFORMANCE
[ ] Screener completa en menos de 30 segundos (timeout de axios = 30s)
[ ] Lista de 20+ candidatos no congela el UI (FlatList con keyExtractor)
[ ] Pull-to-refresh en positions funciona sin acumular llamadas duplicadas

SEGURIDAD
[ ] .env no está en el repositorio
[ ] No hay API keys hardcodeadas en el código fuente
[ ] allow_origins no es "*" en producción (cambiar a dominio específico)
```

---

## 5. Bugs Identificados Durante Revisión del Código

### BUG-01 — Alta — `pl_today_pct` no existe en respuesta de `/api/account`

**Componente:** Frontend (index.tsx línea 71, positions.tsx líneas 113 y 130)

**Pasos para reproducir:**
1. Tener Alpaca configurado
2. Abrir Home o Positions con cuenta activa

**Resultado esperado:** Porcentaje de P&L diario se muestra correctamente

**Resultado actual:** `account.pl_today_pct` es `undefined`. `undefined * 100 = NaN`. Se renderiza `NaN%`

**Posible causa:** El endpoint `GET /api/account` retorna `pl_today` y `pl_total` (valores absolutos) pero no los campos `pl_today_pct` ni `pl_total_pct` (porcentuales). El frontend asume que existen.

**Asignar a:** @backend — agregar `pl_today_pct` y `pl_total_pct` al response de `/api/account`, calculando `(pl_today / (portfolio_value - pl_today)) * 100`

---

### BUG-02 — Media — Estrategia inválida retorna HTTP 400, pero Pydantic retornaría 422

**Componente:** Backend (screener.py línea 62)

**Detalle:** El screener lanza `HTTPException(status_code=400)` para estrategia inválida, mientras que los endpoints de smart_money usan `Query(..., pattern=...)` y dejan que FastAPI retorne 422 automáticamente. Inconsistencia en el contrato de API. El frontend debe manejar ambos códigos o se debe estandarizar.

---

### BUG-03 — Baja — `logo_url` en Candidate viene del screener como campo vacío

**Componente:** Frontend / Backend

**Detalle:** El screener de `/api/screener` no retorna `logo_url` en el payload de candidatos. En `entry/[symbol].tsx` línea 64 se accede a `candidate.logo_url` pero el campo no está en la respuesta del screener (solo existe en `/api/market/logo/{symbol}`). Resultado: `logoUri = null` siempre, nunca se intenta cargar el logo desde la pantalla de entry.
