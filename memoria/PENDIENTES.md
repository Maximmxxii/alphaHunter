# Pendientes AlphaHunter

Fecha de registro: 2026-04-21
Fuente: revisión manual de la app por el usuario

## Bugs detectados

### BUG-01 — "Cerrar Posición" no cierra la posición
- **Pestaña:** Mis Trades
- **Síntoma:** El botón "Cerrar Posición" no ejecuta el cierre de la posición.
- **Estado:** CERRADO (2026-04-29). Verificado con tests `TestClosePositionDelete` y `TestDemo::test_demo_close_position_returns_200`. Endpoints `DELETE /api/positions/{symbol}` y `DELETE /api/demo/positions/{symbol}` funcionales.

### BUG-02 — Precio actual y P&L no son dinámicos en tarjeta de trade
- **Pestaña:** Mis Trades
- **Síntoma:** Los valores de precio actual y P&L estaban estáticos.
- **Estado:** CERRADO (2026-04-29). Verificado con tests `TestLivePrice`. Endpoint `GET /api/market/price/{symbol}` retorna `{symbol, price, timestamp}` con `price > 0` para AAPL.

### BUG-03 — Barra "MODO DEMO" no reacciona al estado de conexión con Alpaca
- **Ubicación:** barra global "MODO DEMO" (app entera).
- **Síntoma:** Barra siempre visible sin importar estado de Alpaca.
- **Estado:** CERRADO (2026-04-29). Verificado con tests `TestAuthMeHasAlpaca`. Endpoint `GET /api/auth/me` retorna `has_alpaca: bool` correctamente (`false` para usuario nuevo, `true` tras guardar keys).
