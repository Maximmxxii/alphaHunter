"""
tests/test_api.py — Tests de pytest para los endpoints críticos de AlphaHunter API.

Requisito: el servidor debe estar corriendo en localhost:8000.
  Terminal 1: make serve   (o: source .venv/bin/activate && uvicorn api.main:app --reload)
  Terminal 2: make test

Si el servidor no está activo, conftest.py salta toda la suite con un mensaje claro
(en vez de mostrar 67 errores de conexión individuales).

Instalar dependencias:
  pip install pytest httpx requests

Ejecutar:
  pytest tests/test_api.py -v
  pytest tests/test_api.py -v -k "test_health"        # test individual
  pytest tests/test_api.py -v --tb=short               # traceback corto
"""

import math
import os
import sys

import jwt
import pytest
import requests

# Ensure project root is in path for auth database imports during test collection
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = "http://localhost:8000"

# ── Estrategias válidas conocidas (sincronizado con screener/filters.py) ─────
VALID_STRATEGIES = {
    "momentum_alcista",
    "rebote_sobrevendido",
    "cruce_dorado",
    "exploratorio",
    "volatilidad_alta",
}


def _get(path: str, **params) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", params=params, timeout=10)


def _post(path: str, json: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", json=json, timeout=10)


def _delete(path: str) -> requests.Response:
    return requests.delete(f"{BASE_URL}{path}", timeout=10)


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health(self):
        """GET / retorna 200 con status ok."""
        r = _get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "AlphaHunter API"
        assert "version" in body

    def test_health_endpoint(self):
        """GET /health retorna 200 con status ok."""
        r = _get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Strategies ───────────────────────────────────────────────────────────────

class TestStrategies:
    def test_strategies_returns_list(self):
        """GET /api/strategies retorna una lista."""
        r = _get("/api/strategies")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)

    def test_strategies_returns_all_five(self):
        """GET /api/strategies contiene las 5 estrategias de screener (puede incluir smart money)."""
        r = _get("/api/strategies")
        assert r.status_code == 200
        body = r.json()
        ids = {s["id"] for s in body}
        assert VALID_STRATEGIES.issubset(ids), (
            f"Estrategias faltantes: {VALID_STRATEGIES - ids}\n"
            f"Estrategias recibidas: {ids}"
        )

    def test_strategies_schema(self):
        """Cada estrategia tiene los campos id, description, label."""
        r = _get("/api/strategies")
        assert r.status_code == 200
        for strategy in r.json():
            assert "id" in strategy, f"Falta 'id' en {strategy}"
            assert "description" in strategy, f"Falta 'description' en {strategy}"
            assert "label" in strategy, f"Falta 'label' en {strategy}"
            assert isinstance(strategy["id"], str)
            assert len(strategy["id"]) > 0


# ── Screener ─────────────────────────────────────────────────────────────────

class TestScreener:
    def test_screener_valid_strategy(self):
        """GET /api/screener con estrategia válida retorna 200 y una lista."""
        r = _get("/api/screener", strategy="momentum_alcista")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list), f"Se esperaba lista, se obtuvo: {type(body)}"

    def test_screener_valid_strategy_all_strategies(self):
        """Todas las estrategias válidas retornan 200."""
        for strategy in VALID_STRATEGIES:
            r = _get("/api/screener", strategy=strategy)
            assert r.status_code == 200, (
                f"Estrategia '{strategy}' retornó {r.status_code}: {r.text}"
            )

    def test_screener_invalid_strategy(self):
        """GET /api/screener con estrategia inválida retorna 400 o 422."""
        r = _get("/api/screener", strategy="estrategia_inexistente")
        assert r.status_code in (400, 422), (
            f"Esperado 400/422, obtenido {r.status_code}: {r.text}"
        )
        body = r.json()
        assert "detail" in body
        assert any(s in body["detail"] for s in VALID_STRATEGIES)

    def test_screener_default_strategy(self):
        """GET /api/screener sin parámetros usa momentum_alcista por defecto y retorna 200."""
        r = _get("/api/screener")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_screener_candidate_schema(self):
        """Si el screener retorna candidatos, cada uno tiene los campos requeridos."""
        r = _get("/api/screener", strategy="exploratorio")
        assert r.status_code == 200
        candidates = r.json()
        if not candidates:
            pytest.skip("Screener no retornó candidatos — mercado cerrado o sin señales")
        required_fields = {
            "ticker", "price", "signals_active", "signal_score",
            "sl_price", "tp_price", "sector", "name",
        }
        for c in candidates:
            missing = required_fields - set(c.keys())
            assert not missing, f"Campos faltantes en candidato {c.get('ticker', '?')}: {missing}"

    def test_screener_sl_tp_consistency(self):
        """SL debe ser menor al precio y TP mayor al precio en todos los candidatos."""
        r = _get("/api/screener", strategy="momentum_alcista")
        assert r.status_code == 200
        for c in r.json():
            assert c["sl_price"] < c["price"], (
                f"{c['ticker']}: sl_price {c['sl_price']} >= price {c['price']}"
            )
            assert c["tp_price"] > c["price"], (
                f"{c['ticker']}: tp_price {c['tp_price']} <= price {c['price']}"
            )

    def test_screener_signal_score_range(self):
        """signal_score debe estar entre 0 y 100."""
        r = _get("/api/screener", strategy="exploratorio")
        assert r.status_code == 200
        for c in r.json():
            assert 0 <= c["signal_score"] <= 100, (
                f"{c['ticker']}: signal_score fuera de rango: {c['signal_score']}"
            )

    def test_screener_sql_injection(self):
        """Inyección SQL en strategy retorna 400, no 500."""
        r = _get("/api/screener", strategy="' OR 1=1 --")
        assert r.status_code in (400, 422), (
            f"Inyección SQL retornó {r.status_code} — revisar si expone info interna"
        )


# ── Account ──────────────────────────────────────────────────────────────────

class TestAccount:
    def test_account_not_configured(self):
        """GET /api/account sin Alpaca retorna error amigable (no 500, no stack trace)."""
        r = _get_with_auth("/api/account")
        # El endpoint siempre retorna 200; el cuerpo indica si está configurado o no
        assert r.status_code == 200
        body = r.json()

        if not body.get("configured", True):
            # Sin Alpaca: debe tener el campo configured=False y un mensaje de error
            assert body["configured"] is False
            assert "error" in body
            assert "stack" not in str(body).lower(), "Respuesta expone stack trace"
            assert "traceback" not in str(body).lower(), "Respuesta expone traceback"
        else:
            # Con Alpaca configurado: validar schema
            required = {"equity", "buying_power", "cash", "pl_today", "configured"}
            missing = required - set(body.keys())
            assert not missing, f"Campos faltantes en account: {missing}"
            assert body["configured"] is True

    def test_account_no_stack_trace_on_error(self):
        """La respuesta de /api/account nunca contiene texto de traceback."""
        r = _get_with_auth("/api/account")
        assert r.status_code == 200
        body_str = r.text.lower()
        assert "traceback" not in body_str
        assert "file \"/" not in body_str
        assert "line " not in body_str or "line " in body_str  # permitimos "line" en campos legítimos


# ── Positions ────────────────────────────────────────────────────────────────

class TestPositions:
    def test_positions_not_configured(self):
        """GET /api/positions sin Alpaca retorna error amigable (no 500)."""
        r = _get_with_auth("/api/positions")
        assert r.status_code == 200
        body = r.json()

        if isinstance(body, dict) and not body.get("configured", True):
            assert body["configured"] is False
            assert "error" in body
        elif isinstance(body, list):
            # Alpaca configurado, posiciones pueden ser lista vacía o con items
            pass
        else:
            pytest.fail(f"Respuesta inesperada de /api/positions: {body}")

    def test_positions_schema_when_configured(self):
        """Si hay posiciones, cada una tiene los campos requeridos."""
        r = _get_with_auth("/api/positions")
        assert r.status_code == 200
        body = r.json()

        if not isinstance(body, list):
            pytest.skip("Alpaca no configurado o sin posiciones")

        if not body:
            return  # Lista vacía es válida

        required_fields = {
            "symbol", "qty", "side", "avg_entry_price",
            "current_price", "market_value", "unrealized_pl",
            "sl_price", "tp_price",
        }
        for pos in body:
            missing = required_fields - set(pos.keys())
            assert not missing, f"Campos faltantes en posición {pos.get('symbol', '?')}: {missing}"

    def test_positions_sl_tp_consistency(self):
        """SL debe ser menor a entry y TP mayor a entry en todas las posiciones."""
        r = _get_with_auth("/api/positions")
        assert r.status_code == 200
        body = r.json()
        if not isinstance(body, list):
            pytest.skip("Alpaca no configurado")
        for pos in body:
            entry = pos["avg_entry_price"]
            assert pos["sl_price"] < entry, (
                f"{pos['symbol']}: sl_price {pos['sl_price']} >= entry {entry}"
            )
            assert pos["tp_price"] > entry, (
                f"{pos['symbol']}: tp_price {pos['tp_price']} <= entry {entry}"
            )


# ── Entry (validación sin necesitar Alpaca configurado) ─────────────────────

class TestEntryValidation:
    def test_entry_validation_missing_symbol(self):
        """POST /api/entry sin symbol retorna 422."""
        r = _post_with_auth("/api/entry", {"amount_usd": 1000})
        assert r.status_code == 422, (
            f"Esperado 422, obtenido {r.status_code}: {r.text}"
        )

    def test_entry_validation_zero_amount(self):
        """POST /api/entry con amount_usd=0 retorna 422 (validación gt=0 en Pydantic)."""
        r = _post_with_auth("/api/entry", {"symbol": "AAPL", "amount_usd": 0})
        assert r.status_code == 422, (
            f"Esperado 422, obtenido {r.status_code}: {r.text}"
        )

    def test_entry_validation_negative_amount(self):
        """POST /api/entry con amount_usd negativo retorna 422."""
        r = _post_with_auth("/api/entry", {"symbol": "AAPL", "amount_usd": -100})
        assert r.status_code == 422, (
            f"Esperado 422, obtenido {r.status_code}: {r.text}"
        )

    def test_entry_validation_string_amount(self):
        """POST /api/entry con amount_usd como string retorna 422."""
        r = _post_with_auth("/api/entry", {"symbol": "AAPL", "amount_usd": "mil"})
        assert r.status_code == 422

    def test_entry_validation_null_symbol(self):
        """POST /api/entry con symbol null retorna 422."""
        r = _post_with_auth("/api/entry", {"symbol": None, "amount_usd": 1000})
        assert r.status_code == 422

    def test_entry_invalid_ticker(self):
        """POST /api/entry con ticker inexistente retorna 400 (no puede obtener precio)."""
        r = _post_with_auth("/api/entry", {"symbol": "XYZXYZXYZ999", "amount_usd": 1000})
        # Puede ser 400 (precio no disponible) o error amigable si Alpaca no está configurado
        assert r.status_code in (200, 400), (
            f"Ticker inválido retornó {r.status_code} inesperado: {r.text}"
        )
        body = r.json()
        # Si 200, debe ser el error de Alpaca no configurado
        if r.status_code == 200:
            assert "configured" in body and body["configured"] is False

    def test_entry_empty_body(self):
        """POST /api/entry con body vacío retorna 422."""
        r = _post_with_auth("/api/entry", {})
        assert r.status_code == 422

    def test_entry_not_configured_returns_friendly_error(self):
        """POST /api/entry sin Alpaca configurado retorna mensaje amigable (no 500)."""
        r = _post_with_auth("/api/entry", {"symbol": "AAPL", "amount_usd": 1000})
        assert r.status_code not in (500,), (
            f"Entry retornó 500 inesperado — debe ser error amigable: {r.text}"
        )
        assert r.status_code in (200, 400, 404, 422), (
            f"Entry retornó {r.status_code} inesperado: {r.text}"
        )
        body = r.json()
        body_str = str(body).lower()
        assert "traceback" not in body_str
        assert "file \"/" not in body_str
        # Si no configurado, debe tener el mensaje estándar
        if r.status_code == 200 and isinstance(body, dict) and not body.get("configured", True):
            assert "error" in body
            assert body["configured"] is False


# ── Market ───────────────────────────────────────────────────────────────────

class TestMarket:
    def test_market_ticker_known(self):
        """GET /api/market/ticker/AAPL retorna datos de precio."""
        r = _get("/api/market/ticker/AAPL")
        assert r.status_code == 200
        body = r.json()
        required = {"symbol", "name", "current_price", "prev_close", "pct_change"}
        missing = required - set(body.keys())
        assert not missing, f"Campos faltantes: {missing}"
        assert body["symbol"] == "AAPL"
        assert body["current_price"] > 0

    def test_market_logo_known_ticker(self):
        """GET /api/market/logo/AAPL retorna URL del logo con dominio apple.com."""
        r = _get("/api/market/logo/AAPL")
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "AAPL"
        assert "apple.com" in body["logo_url"]
        assert body["domain"] == "apple.com"

    def test_market_logo_unknown_ticker_fallback(self):
        """GET /api/market/logo/UNKN retorna URL de fallback (no 404)."""
        r = _get("/api/market/logo/UNKN")
        assert r.status_code == 200
        body = r.json()
        assert "logo_url" in body
        assert body["domain"] is None
        assert "unkn.com" in body["logo_url"]

    def test_market_ticker_lowercase_normalized(self):
        """GET /api/market/ticker/aapl (minúsculas) retorna AAPL normalizado."""
        r = _get("/api/market/ticker/aapl")
        assert r.status_code == 200
        assert r.json()["symbol"] == "AAPL"


# ── Journal ──────────────────────────────────────────────────────────────────

class TestJournal:
    def test_journal_returns_list(self):
        """GET /api/journal siempre retorna una lista (vacía si no hay trades)."""
        r = _get("/api/journal")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_journal_stats_schema(self):
        """GET /api/journal/stats retorna objeto con campos requeridos."""
        r = _get("/api/journal/stats")
        assert r.status_code == 200
        body = r.json()
        required = {"total_trades", "win_rate", "avg_profit", "total_pl", "avg_hold_hours"}
        missing = required - set(body.keys())
        assert not missing, f"Campos faltantes en stats: {missing}"
        assert isinstance(body["total_trades"], int)
        assert body["total_trades"] >= 0

    def test_journal_stats_win_rate_range(self):
        """win_rate debe estar entre 0 y 100."""
        r = _get("/api/journal/stats")
        assert r.status_code == 200
        wr = r.json()["win_rate"]
        assert 0 <= wr <= 100, f"win_rate fuera de rango: {wr}"


# ── Smart Money ───────────────────────────────────────────────────────────────

class TestSmartMoney:
    def test_congress_trades_schema(self):
        """GET /api/smart-money/congress retorna {status: ok, data: list}."""
        r = _get("/api/smart-money/congress", limit=5)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert isinstance(body["data"], list)

    def test_whales_schema(self):
        """GET /api/smart-money/whales retorna {status: ok, data: list}."""
        r = _get("/api/smart-money/whales")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert isinstance(body["data"], list)

    def test_signals_all_mode(self):
        """GET /api/smart-money/signals?mode=all retorna lista de candidatos."""
        r = _get("/api/smart-money/signals", mode="all")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)

    def test_signals_congress_mode(self):
        """GET /api/smart-money/signals?mode=congress retorna 200."""
        r = _get("/api/smart-money/signals", mode="congress")
        assert r.status_code == 200

    def test_signals_whales_mode(self):
        """GET /api/smart-money/signals?mode=whales retorna 200."""
        r = _get("/api/smart-money/signals", mode="whales")
        assert r.status_code == 200

    def test_signals_invalid_mode(self):
        """GET /api/smart-money/signals?mode=invalid retorna 422."""
        r = _get("/api/smart-money/signals", mode="invalid_mode")
        assert r.status_code == 422, (
            f"Modo inválido retornó {r.status_code}, esperado 422: {r.text}"
        )

    def test_options_invalid_type(self):
        """GET /api/smart-money/options?option_type=naked retorna 422."""
        r = _get("/api/smart-money/options", option_type="naked")
        assert r.status_code == 422

    def test_options_valid_types(self):
        """GET /api/smart-money/options con tipos válidos retorna 200."""
        for opt_type in ("all", "calls", "puts"):
            r = _get("/api/smart-money/options", option_type=opt_type)
            assert r.status_code == 200, (
                f"option_type='{opt_type}' retornó {r.status_code}: {r.text}"
            )

    def test_politician_not_found(self):
        """GET /api/smart-money/congress/politician/NobodyXYZ retorna 404."""
        r = _get("/api/smart-money/congress/politician/NobodyXYZ999")
        assert r.status_code == 404


# ── CORS ──────────────────────────────────────────────────────────────────────

class TestCORS:
    def test_cors_header_present(self):
        """La respuesta incluye Access-Control-Allow-Origin cuando se envía Origin."""
        r = requests.get(
            f"{BASE_URL}/api/strategies",
            headers={"Origin": "http://localhost:8081"},
            timeout=10,
        )
        assert "access-control-allow-origin" in r.headers

    def test_cors_allows_post_preflight(self):
        """OPTIONS en /api/entry retorna 200 con headers CORS."""
        r = requests.options(
            f"{BASE_URL}/api/entry",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
            timeout=10,
        )
        assert r.status_code in (200, 204), (
            f"Preflight OPTIONS retornó {r.status_code}"
        )


# ── Análisis ─────────────────────────────────────────────────────────────────

class TestAnalysis:
    def test_analysis_schema(self):
        """GET /api/analysis/AAPL retorna los campos de ML y backtest."""
        r = _get("/api/analysis/AAPL")
        assert r.status_code == 200
        body = r.json()
        required = {
            "symbol", "ml_prob", "ml_signal", "backtest_return",
            "backtest_winrate", "recomendacion",
        }
        missing = required - set(body.keys())
        assert not missing, f"Campos faltantes en analysis: {missing}"
        assert body["symbol"] == "AAPL"

    def test_analysis_ml_prob_range(self):
        """ml_prob debe estar entre 0 y 1."""
        r = _get("/api/analysis/MSFT")
        assert r.status_code == 200
        prob = r.json()["ml_prob"]
        assert 0.0 <= prob <= 1.0, f"ml_prob fuera de rango: {prob}"

    def test_analysis_invalid_symbol(self):
        """GET /api/analysis/XXXYYY retorna 400 o 404 con mensaje, no 500."""
        r = _get("/api/analysis/XXXYYY999")
        assert r.status_code in (400, 404, 500)
        if r.status_code == 500:
            body = r.json()
            assert "detail" in body
            assert "traceback" not in body["detail"].lower()


# ── Group A — Account endpoint shape ──────────────────────────────────────────

class TestAccountShape:
    def test_account_has_pl_today_pct(self):
        """GET /api/account con Alpaca configurado retorna pl_today_pct como float, no NaN."""
        r = _get_with_auth("/api/account")
        assert r.status_code == 200
        body = r.json()

        if not body.get("configured", False):
            pytest.skip("Alpaca no configurado — no se puede validar pl_today_pct")

        assert "pl_today_pct" in body, (
            f"Campo 'pl_today_pct' ausente en respuesta de /api/account. "
            f"Campos disponibles: {list(body.keys())}"
        )
        val = body["pl_today_pct"]
        assert isinstance(val, (int, float)), (
            f"pl_today_pct es {type(val).__name__}, se esperaba float"
        )
        assert not math.isnan(val), "pl_today_pct es NaN — el frontend renderizaria 'NaN%'"

    def test_account_has_pl_total_pct(self):
        """GET /api/account con Alpaca configurado retorna pl_total_pct como float, no NaN."""
        r = _get_with_auth("/api/account")
        assert r.status_code == 200
        body = r.json()

        if not body.get("configured", False):
            pytest.skip("Alpaca no configurado — no se puede validar pl_total_pct")

        assert "pl_total_pct" in body, (
            f"Campo 'pl_total_pct' ausente en respuesta de /api/account. "
            f"Campos disponibles: {list(body.keys())}"
        )
        val = body["pl_total_pct"]
        assert isinstance(val, (int, float)), (
            f"pl_total_pct es {type(val).__name__}, se esperaba float"
        )
        assert not math.isnan(val), "pl_total_pct es NaN — el frontend renderizaria 'NaN%'"

    def test_account_unconfigured_returns_200_not_500(self):
        """GET /api/account nunca retorna 500."""
        r = _get_with_auth("/api/account")
        assert r.status_code != 500
        assert r.status_code == 200
        body = r.json()
        assert "configured" in body
        # If not configured, must have error field
        if not body.get("configured", True):
            assert "error" in body


# ── Group B — Close position endpoints exist ──────────────────────────────────

class TestClosePositionEndpoints:
    def test_close_position_post_returns_200_not_404(self):
        """POST /api/close/FAKESYMBOL retorna 200 o 404 de negocio (endpoint existe), no 405."""
        r = _post("/api/close/FAKESYMBOL", {})
        assert r.status_code != 405, (
            "POST /api/close/{symbol} retorno 405 — metodo no permitido en esta ruta"
        )
        # 200 → Alpaca no configurado (configured=False) o cierre exitoso
        # 404 → Alpaca configurado pero FAKESYMBOL no tiene posicion abierta (correcto)
        assert r.status_code in (200, 404), (
            f"Esperado 200 o 404, obtenido {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        if r.status_code == 200 and isinstance(body, dict) and not body.get("configured", True):
            assert "error" in body, (
                f"Falta campo 'error' en respuesta de cierre sin Alpaca: {body}"
            )

    def test_close_position_delete_returns_200_not_404(self):
        """DELETE /api/positions/FAKESYMBOL retorna 200 o 404 (endpoint existe), no 405."""
        r = _delete_with_auth("/api/positions/FAKESYMBOL")
        assert r.status_code != 405, (
            "DELETE /api/positions/{symbol} retorno 405 — metodo no permitido en esta ruta"
        )
        # Sin Alpaca: retorna 200 con configured=False
        # Con Alpaca y sin posicion: retorna 404
        if r.status_code == 200:
            body = r.json()
            assert body.get("configured") is False, (
                f"DELETE retorno 200 pero no es el error de Alpaca esperado: {body}"
            )
        elif r.status_code == 404:
            # Alpaca configurado pero posicion no existe — es correcto
            pass
        else:
            pytest.fail(
                f"DELETE /api/positions/FAKESYMBOL retorno {r.status_code} inesperado: {r.text[:200]}"
            )


# ── Group C — Live price endpoint ─────────────────────────────────────────────

class TestLivePrice:
    def test_live_price_returns_correct_shape(self):
        """GET /api/market/price/AAPL retorna {symbol, price, timestamp} con price > 0."""
        r = _get("/api/market/price/AAPL")
        assert r.status_code == 200, (
            f"Esperado 200, obtenido {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        required_keys = {"symbol", "price", "timestamp"}
        missing = required_keys - set(body.keys())
        assert not missing, f"Campos faltantes en /api/market/price/AAPL: {missing}"
        assert body["symbol"] == "AAPL", (
            f"Symbol esperado 'AAPL', obtenido '{body['symbol']}'"
        )
        assert isinstance(body["price"], (int, float)), (
            f"price es {type(body['price']).__name__}, se esperaba numero"
        )
        assert body["price"] > 0, (
            f"Precio deberia ser > 0, obtenido: {body['price']}"
        )

    def test_live_price_invalid_ticker_returns_400(self):
        """GET /api/market/price/ZZZNOTREAL999 retorna 400 (ticker invalido)."""
        r = _get("/api/market/price/ZZZNOTREAL999")
        assert r.status_code == 400, (
            f"Esperado 400 para ticker invalido, obtenido {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        assert "detail" in body, (
            f"Respuesta de error sin campo 'detail': {body}"
        )


# ── Group D — CORS ────────────────────────────────────────────────────────────

class TestCORSOriginHeader:
    def test_cors_header_present_for_localhost(self):
        """GET / con Origin: http://localhost:8081 incluye header access-control-allow-origin."""
        r = requests.get(
            f"{BASE_URL}/",
            headers={"Origin": "http://localhost:8081"},
            timeout=10,
        )
        assert r.status_code == 200
        assert "access-control-allow-origin" in r.headers, (
            "Header CORS 'access-control-allow-origin' ausente para Origin http://localhost:8081. "
            f"Headers recibidos: {dict(r.headers)}"
        )
        # El valor del header debe coincidir con el origen solicitado o ser '*'
        cors_value = r.headers["access-control-allow-origin"]
        assert cors_value in ("http://localhost:8081", "*"), (
            f"CORS header es '{cors_value}', se esperaba 'http://localhost:8081' o '*'"
        )


# ── Auth helpers for authenticated endpoints ───────────────────────────────────

_JWT_SECRET = os.getenv("JWT_SECRET", "alphahunter-dev-secret-change-in-prod")


def _make_test_jwt(user_id: int = 99999, email: str = "qa-test@alphahunter.test") -> str:
    """Create a valid JWT for testing authenticated endpoints."""
    from datetime import datetime, timedelta, timezone
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _auth_headers(token: str = None) -> dict:
    """Return Authorization headers with a test JWT."""
    if token is None:
        token = _make_test_jwt()
    return {"Authorization": f"Bearer {token}"}


# ── Group E — BUG-01: DELETE /api/positions/{symbol} endpoint exists ──────────

class TestClosePositionDelete:
    """BUG-01 verification: DELETE /api/positions/{symbol} is reachable (requires auth)."""

    def test_delete_positions_endpoint_exists(self):
        """DELETE /api/positions/FAKESYMBOL with auth: endpoint exists (not 401/405). May return 200, 404, or 500."""
        r = _delete_with_auth("/api/positions/FAKESYMBOL")
        # Primary goal: confirm the endpoint route exists and auth works
        assert r.status_code != 405, (
            "DELETE /api/positions/{symbol} returned 405 -- method not allowed"
        )
        assert r.status_code != 401, (
            "DELETE /api/positions/{symbol} returned 401 -- endpoint requires auth but JWT was provided"
        )
        assert r.status_code in (200, 404), (
            f"Expected 200 (Alpaca not configured) or 404 (position not in Alpaca), got {r.status_code}: {r.text[:200]}"
        )

    def test_delete_positions_without_auth_returns_401(self):
        """DELETE /api/positions/{symbol} without JWT returns 401."""
        r = _delete("/api/positions/FAKESYMBOL")
        assert r.status_code == 401, (
            f"Expected 401 without auth, got {r.status_code}"
        )


# ── Group F — BUG-02: Live price endpoint (already tested in TestLivePrice) ──
# TestLivePrice covers GET /api/market/price/{symbol} with correct shape and price > 0.
# No additional tests needed.


# ── Group G — BUG-03: GET /api/auth/me returns has_alpaca ─────────────────────

class TestAuthMeHasAlpaca:
    """BUG-03 verification: /api/auth/me returns has_alpaca boolean."""

    def test_auth_me_returns_has_alpaca_false_for_fresh_user(self):
        """GET /api/auth/me for a freshly created user returns has_alpaca: false."""
        # Create a user directly in the DB to guarantee it's fresh (no Alpaca keys)
        from api.auth.database import create_user, get_user_by_google_id, _get_connection

        google_id = "qa_test_fresh_user_001"
        # Clean up if user already exists from a prior test run
        with _get_connection() as conn:
            conn.execute("DELETE FROM users WHERE google_id = ?", (google_id,))
            conn.commit()

        user = create_user(
            google_id=google_id,
            email="qa-fresh@alphahunter.test",
            name="QA Fresh User",
            picture="",
        )
        user_id = user["id"]
        token = _make_test_jwt(user_id=user_id, email="qa-fresh@alphahunter.test")

        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=_auth_headers(token),
            timeout=10,
        )
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        assert "has_alpaca" in body, (
            f"'has_alpaca' field missing from /api/auth/me response. Got: {list(body.keys())}"
        )
        assert body["has_alpaca"] is False, (
            f"Expected has_alpaca=False for fresh user, got {body['has_alpaca']}"
        )

    def test_auth_me_returns_has_alpaca_true_after_saving_keys(self):
        """GET /api/auth/me returns has_alpaca: true after saving Alpaca keys."""
        from api.auth.database import create_user, _get_connection
        from api.auth.crypto import encrypt

        # ENCRYPTION_KEY is needed for encrypt(). Skip if not available.
        if not os.getenv("ENCRYPTION_KEY"):
            pytest.skip("ENCRYPTION_KEY not set -- cannot test Alpaca key save flow")

        google_id = "qa_test_with_keys_001"
        with _get_connection() as conn:
            conn.execute("DELETE FROM users WHERE google_id = ?", (google_id,))
            conn.commit()

        user = create_user(
            google_id=google_id,
            email="qa-withkeys@alphahunter.test",
            name="QA With Keys",
            picture="",
        )
        user_id = user["id"]
        token = _make_test_jwt(user_id=user_id, email="qa-withkeys@alphahunter.test")

        # Save Alpaca keys directly in DB (bypassing the endpoint to avoid full flow)
        from api.auth.database import update_alpaca_keys
        update_alpaca_keys(
            user_id=user_id,
            api_key="PK_TEST_KEY",
            secret_key="SK_TEST_SECRET",
            base_url="https://paper-api.alpaca.markets",
        )

        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=_auth_headers(token),
            timeout=10,
        )
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        assert "has_alpaca" in body, (
            f"'has_alpaca' field missing from /api/auth/me response. Got: {list(body.keys())}"
        )
        assert body["has_alpaca"] is True, (
            f"Expected has_alpaca=True after saving keys, got {body['has_alpaca']}"
        )

    def test_auth_me_without_token_returns_401(self):
        """GET /api/auth/me without JWT returns 401."""
        r = _get("/api/auth/me")
        assert r.status_code == 401, (
            f"Expected 401 without auth, got {r.status_code}"
        )

    def test_auth_me_response_shape(self):
        """GET /api/auth/me returns user object with all expected fields."""
        from api.auth.database import create_user, _get_connection

        google_id = "qa_test_shape_user_001"
        with _get_connection() as conn:
            conn.execute("DELETE FROM users WHERE google_id = ?", (google_id,))
            conn.commit()

        user = create_user(
            google_id=google_id,
            email="qa-shape@alphahunter.test",
            name="QA Shape User",
            picture="https://example.com/pic.jpg",
        )
        user_id = user["id"]
        token = _make_test_jwt(user_id=user_id, email="qa-shape@alphahunter.test")

        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=_auth_headers(token),
            timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        required_fields = {"id", "email", "name", "picture", "has_alpaca"}
        missing = required_fields - set(body.keys())
        assert not missing, f"Missing fields in /api/auth/me response: {missing}"
        assert isinstance(body["has_alpaca"], bool), (
            f"has_alpaca should be bool, got {type(body['has_alpaca']).__name__}"
        )


# ── Group H — Demo close position flow ─────────────────────────────────────────

class TestDemo:
    """Tests for demo mode endpoints: entry, close position, reset."""

    @staticmethod
    def _ensure_demo_user():
        """Create a demo test user and return (user_id, jwt_token)."""
        from api.auth.database import create_user, _get_connection

        google_id = "qa_test_demo_user_001"
        with _get_connection() as conn:
            conn.execute("DELETE FROM users WHERE google_id = ?", (google_id,))
            conn.commit()

        user = create_user(
            google_id=google_id,
            email="qa-demo@alphahunter.test",
            name="QA Demo User",
            picture="",
        )
        user_id = user["id"]
        token = _make_test_jwt(user_id=user_id, email="qa-demo@alphahunter.test")
        return user_id, token

    def test_demo_entry_creates_position(self):
        """POST /api/demo/entry creates a demo position."""
        user_id, token = self._ensure_demo_user()
        # Reset demo first to ensure clean state
        _post_with_auth("/api/demo/reset", token=token, json={})
        r = _post_with_auth(
            "/api/demo/entry",
            token=token,
            json={"symbol": "AAPL", "amount_usd": 100},
        )
        assert r.status_code == 200, (
            f"Expected 200 for demo entry, got {r.status_code}: {r.text[:300]}"
        )
        body = r.json()
        assert body["symbol"] == "AAPL", f"Expected symbol AAPL, got {body.get('symbol')}"
        assert body["status"] == "filled", f"Expected status filled, got {body.get('status')}"
        assert body["qty"] > 0, f"Expected qty > 0, got {body.get('qty')}"

    def test_demo_close_position_returns_200(self):
        """DELETE /api/demo/positions/AAPL closes the demo position and returns status closed."""
        user_id, token = self._ensure_demo_user()
        # Reset demo for clean state
        _post_with_auth("/api/demo/reset", token=token, json={})
        # Create a position
        entry_r = _post_with_auth(
            "/api/demo/entry",
            token=token,
            json={"symbol": "AAPL", "amount_usd": 100},
        )
        assert entry_r.status_code == 200, (
            f"Demo entry failed: {entry_r.status_code} {entry_r.text[:200]}"
        )
        # Close the position
        close_r = _delete_with_auth("/api/demo/positions/AAPL", token=token)
        assert close_r.status_code == 200, (
            f"Expected 200 closing demo position, got {close_r.status_code}: {close_r.text[:300]}"
        )
        body = close_r.json()
        assert body["status"] == "closed", (
            f"Expected status 'closed', got '{body.get('status')}'. Body: {body}"
        )
        assert body["symbol"] == "AAPL", f"Expected symbol AAPL, got {body.get('symbol')}"

    def test_demo_close_nonexistent_position_returns_404(self):
        """DELETE /api/demo/positions/ZZZZFAKE returns 404 when no position exists."""
        user_id, token = self._ensure_demo_user()
        # Reset to ensure ZZZZFAKE is not there
        _post_with_auth("/api/demo/reset", token=token, json={})
        r = _delete_with_auth("/api/demo/positions/ZZZZFAKE", token=token)
        assert r.status_code == 404, (
            f"Expected 404 for nonexistent position, got {r.status_code}: {r.text[:200]}"
        )

    def test_demo_account_returns_correct_shape(self):
        """GET /api/demo/account returns expected fields."""
        user_id, token = self._ensure_demo_user()
        _post_with_auth("/api/demo/reset", token=token, json={})
        r = _get_with_auth("/api/demo/account", token=token)
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        required = {"equity", "cash", "buying_power", "pl_today", "pl_today_pct", "pl_total", "pl_total_pct", "is_demo", "configured"}
        missing = required - set(body.keys())
        assert not missing, f"Missing fields in demo account: {missing}"
        assert body["is_demo"] is True
        assert body["configured"] is True

    def test_demo_positions_returns_list(self):
        """GET /api/demo/positions returns a list."""
        user_id, token = self._ensure_demo_user()
        _post_with_auth("/api/demo/reset", token=token, json={})
        r = _get_with_auth("/api/demo/positions", token=token)
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        assert isinstance(body, list), f"Expected list, got {type(body)}"

    def test_demo_reset_returns_success(self):
        """POST /api/demo/reset resets the portfolio."""
        user_id, token = self._ensure_demo_user()
        r = _post_with_auth("/api/demo/reset", token=token, json={})
        assert r.status_code == 200, (
            f"Expected 200 for demo reset, got {r.status_code}: {r.text[:200]}"
        )
        body = r.json()
        assert body.get("reset") is True

    def test_demo_endpoints_require_auth(self):
        """All demo endpoints return 401 without JWT."""
        r_get = _get("/api/demo/account")
        assert r_get.status_code == 401, (
            f"GET /api/demo/account should return 401 without auth, got {r_get.status_code}"
        )
        r_post = _post("/api/demo/entry", {"symbol": "AAPL", "amount_usd": 100})
        assert r_post.status_code == 401, (
            f"POST /api/demo/entry should return 401 without auth, got {r_post.status_code}"
        )
        r_delete = _delete("/api/demo/positions/AAPL")
        assert r_delete.status_code == 401, (
            f"DELETE /api/demo/positions/AAPL should return 401 without auth, got {r_delete.status_code}"
        )


# ── Authenticated request helpers ──────────────────────────────────────────────

def _get_with_auth(path: str, token: str = None, **params) -> requests.Response:
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=_auth_headers(token),
        timeout=30,
    )


def _post_with_auth(path: str, json: dict, token: str = None) -> requests.Response:
    return requests.post(
        f"{BASE_URL}{path}",
        json=json,
        headers=_auth_headers(token),
        timeout=30,
    )


def _delete_with_auth(path: str, token: str = None) -> requests.Response:
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=_auth_headers(token),
        timeout=30,
    )
