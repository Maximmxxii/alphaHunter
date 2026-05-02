"""
utils/alpaca.py — Cliente Alpaca Paper Trading para AlphaHunter

Funcionalidades:
    - get_account()                   : Balance, buying power, equity
    - get_positions()                 : Posiciones abiertas
    - get_orders()                    : Historial de órdenes
    - place_order()                   : Enviar orden de compra/venta (bracket estático)
    - place_trailing_stop_order()     : Trailing stop puro para posición existente
    - place_order_with_trailing_stop(): Compra market + trailing stop + TP opcional
    - close_position()                : Cerrar posición de un ticker
    - get_portfolio_history()         : Curva de equity de la cuenta
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY    = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID":     API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY,
    "Content-Type":        "application/json",
}


def _build_headers(api_key: str = None, secret_key: str = None) -> dict:
    key = api_key or API_KEY
    secret = secret_key or SECRET_KEY
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: dict = None, headers: dict = None, base_url: str = None) -> dict | list:
    h = headers or HEADERS
    b = base_url or BASE_URL
    url = f"{b}/v2/{endpoint}"
    r = requests.get(url, headers=h, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(endpoint: str, payload: dict, headers: dict = None, base_url: str = None) -> dict:
    h = headers or HEADERS
    b = base_url or BASE_URL
    url = f"{b}/v2/{endpoint}"
    r = requests.post(url, headers=h, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def _delete(endpoint: str, headers: dict = None, base_url: str = None) -> dict:
    h = headers or HEADERS
    b = base_url or BASE_URL
    url = f"{b}/v2/{endpoint}"
    r = requests.delete(url, headers=h, timeout=10)
    r.raise_for_status()
    return r.json() if r.content else {}


def is_configured(api_key: str = None, secret_key: str = None) -> bool:
    """True si las API keys están cargadas (no son placeholder)."""
    key = api_key or API_KEY
    sec = secret_key or SECRET_KEY
    return bool(
        key and key not in ("TU_API_KEY_AQUI", "PKxxxxxxxxxxxxxxxxxxxxxxxxxx", "")
        and sec and sec not in ("TU_SECRET_KEY_AQUI", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "")
    )


def yf_to_alpaca(ticker: str) -> str:
    """
    Convierte ticker de formato yfinance a formato Alpaca.
    Ejemplo: 'BTC-USD' → 'BTC/USD'  |  'AAPL' → 'AAPL'
    """
    return ticker.replace("-USD", "/USD")


def alpaca_to_yf(ticker: str) -> str:
    """
    Convierte ticker de formato Alpaca a formato yfinance.
    Ejemplo: 'BTC/USD' → 'BTC-USD'  |  'AAPL' → 'AAPL'
    """
    return ticker.replace("/USD", "-USD")


def is_crypto(ticker: str) -> bool:
    """True si el ticker es crypto (contiene /USD o -USD)."""
    return "/USD" in ticker or "-USD" in ticker


# ─────────────────────────────────────────────
# Cuenta
# ─────────────────────────────────────────────

def get_account(api_key: str = None, secret_key: str = None, base_url: str = None) -> dict:
    """
    Retorna info de la cuenta.

    Keys relevantes:
        equity, cash, buying_power, portfolio_value,
        daytrade_count, pattern_day_trader
    """
    h = _build_headers(api_key, secret_key)
    data = _get("account", headers=h, base_url=base_url)
    return {
        "equity":          float(data["equity"]),
        "cash":            float(data["cash"]),
        "buying_power":    float(data["buying_power"]),
        "portfolio_value": float(data["portfolio_value"]),
        "pl_total":        float(data["equity"]) - float(data.get("last_equity", data["equity"])),
        "status":          data["status"],
        "currency":        data["currency"],
        "daytrade_count":  int(data.get("daytrade_count", 0)),
        "raw":             data,
    }


# ─────────────────────────────────────────────
# Posiciones
# ─────────────────────────────────────────────

def get_positions(api_key: str = None, secret_key: str = None, base_url: str = None) -> list[dict]:
    """
    Retorna lista de posiciones abiertas.

    Cada item:
        symbol, qty, side, avg_entry_price,
        current_price, market_value, unrealized_pl, unrealized_plpc
    """
    h = _build_headers(api_key, secret_key)
    data = _get("positions", headers=h, base_url=base_url)
    result = []
    for p in data:
        result.append({
            "symbol":           p["symbol"],
            "qty":              float(p["qty"]),
            "side":             p["side"],
            "avg_entry_price":  float(p["avg_entry_price"]),
            "current_price":    float(p["current_price"]),
            "market_value":     float(p["market_value"]),
            "unrealized_pl":    float(p["unrealized_pl"]),
            "unrealized_plpc":  float(p["unrealized_plpc"]) * 100,
        })
    return result


# ─────────────────────────────────────────────
# Órdenes
# ─────────────────────────────────────────────

def get_orders(status: str = "all", limit: int = 50, api_key: str = None, secret_key: str = None, base_url: str = None) -> list[dict]:
    """
    Retorna historial de órdenes.

    status: 'open' | 'closed' | 'all'
    """
    h = _build_headers(api_key, secret_key)
    data = _get("orders", params={"status": status, "limit": limit, "direction": "desc"}, headers=h, base_url=base_url)
    result = []
    for o in data:
        filled_qty = float(o.get("filled_qty") or 0)
        filled_avg = float(o.get("filled_avg_price") or 0)
        result.append({
            "id":               o["id"],
            "symbol":           o["symbol"],
            "side":             o["side"],
            "type":             o["type"],
            "qty":              float(o.get("qty") or 0),
            "filled_qty":       filled_qty,
            "filled_avg_price": filled_avg,
            "status":           o["status"],
            "submitted_at":     o.get("submitted_at", ""),
            "filled_at":        o.get("filled_at", ""),
            "total_value":      round(filled_qty * filled_avg, 2),
        })
    return result


# ─────────────────────────────────────────────
# Órdenes — enviar
# ─────────────────────────────────────────────

def place_order(
    symbol: str,
    qty: float = None,
    notional: float = None,
    side: str = "buy",
    order_type: str = "market",
    time_in_force: str = "day",
    limit_price: float = None,
    stop_price: float = None,
    take_profit_price: float = None,
    stop_loss_price: float = None,
    stop_loss_limit_price: float = None,
    api_key: str = None,
    secret_key: str = None,
    base_url: str = None,
) -> dict:
    """
    Envía una orden. Soporta órdenes bracket (SL + TP simultáneos).

    Args:
        symbol:               Ticker (ej: "AAPL")
        qty:                  Cantidad de acciones
        notional:             Monto en USD en vez de qty
        side:                 'buy' | 'sell'
        order_type:           'market' | 'limit' | 'stop' | 'stop_limit'
        time_in_force:        'day' | 'gtc' | 'ioc' | 'fok'
        limit_price:          Requerido para 'limit' y 'stop_limit'
        stop_price:           Requerido para 'stop' y 'stop_limit'
        take_profit_price:    Si se provee, activa orden bracket con limit TP
        stop_loss_price:      Precio stop para el SL del bracket
        stop_loss_limit_price: Si se provee, el SL es stop-limit en vez de stop-market

    Notas bracket:
        - Requiere qty (no notional) y time_in_force='gtc'
        - Alpaca ejecuta ambas legs automáticamente y cancela la otra al tocar una
    """
    if qty is None and notional is None:
        raise ValueError("Debes especificar qty o notional")

    is_bracket = take_profit_price is not None or stop_loss_price is not None

    payload = {
        "symbol":        symbol.upper(),
        "side":          side,
        "type":          order_type,
        "time_in_force": "gtc" if is_bracket else time_in_force,
    }

    if notional is not None and not is_bracket:
        payload["notional"] = str(round(notional, 2))
    else:
        payload["qty"] = str(qty)

    if limit_price is not None:
        payload["limit_price"] = str(round(limit_price, 2))
    if stop_price is not None:
        payload["stop_price"] = str(round(stop_price, 2))

    if is_bracket:
        payload["order_class"] = "bracket"
        if take_profit_price is not None:
            payload["take_profit"] = {"limit_price": str(round(take_profit_price, 2))}
        if stop_loss_price is not None:
            sl = {"stop_price": str(round(stop_loss_price, 2))}
            if stop_loss_limit_price is not None:
                sl["limit_price"] = str(round(stop_loss_limit_price, 2))
            payload["stop_loss"] = sl

    h = _build_headers(api_key, secret_key)
    data = _post("orders", payload, headers=h, base_url=base_url)
    return {
        "id":     data["id"],
        "status": data["status"],
        "symbol": data["symbol"],
        "side":   data["side"],
        "type":   data["order_type"],
        "qty":    data.get("qty"),
        "raw":    data,
    }


def place_trailing_stop_order(
    symbol: str,
    qty: int,
    trail_percent: float = 5.0,
    side: str = "sell",
    api_key: str = None,
    secret_key: str = None,
    base_url: str = None,
) -> dict:
    """
    Coloca una orden de trailing stop pura para una posición existente.
    Alpaca endpoint: POST /v2/orders con type='trailing_stop'
    El floor sube automáticamente con el precio; si el precio cae trail_percent
    desde su máximo, la orden se dispara como market sell.

    Args:
        symbol:        Ticker (ej: 'AAPL')
        qty:           Cantidad entera de acciones
        trail_percent: % de distancia del trailing stop respecto al máximo
        side:          'sell' (para proteger una posición long)
    """
    payload = {
        "symbol":        symbol.upper(),
        "qty":           str(int(qty)),
        "side":          side,
        "type":          "trailing_stop",
        "time_in_force": "gtc",
        "trail_percent": str(round(trail_percent, 2)),
    }
    h = _build_headers(api_key, secret_key)
    data = _post("orders", payload, headers=h, base_url=base_url)
    return {
        "id":            data["id"],
        "status":        data["status"],
        "symbol":        data["symbol"],
        "side":          data["side"],
        "type":          data["order_type"],
        "qty":           data.get("qty"),
        "trail_percent": trail_percent,
        "raw":           data,
    }


def place_order_with_trailing_stop(
    symbol: str,
    qty: int,
    trail_percent: float = 5.0,
    take_profit_price: float = None,
    api_key: str = None,
    secret_key: str = None,
    base_url: str = None,
) -> dict:
    """
    Coloca una orden de compra market y, al completarse, agrega protección
    mediante trailing stop y opcionalmente una limit order de take profit.

    Estrategia de dos pasos (OTO no soporta trailing en leg SL de bracket):
        1. Orden market de compra (GTC, qty entera)
        2. Trailing stop order separada (tipo 'trailing_stop', GTC)
        3. Opcional: limit order de take profit separada (GTC)

    Args:
        symbol:             Ticker (ej: 'AAPL' o 'BTC/USD')
        qty:                Cantidad entera de acciones
        trail_percent:      % de trail para el stop dinámico
        take_profit_price:  Precio límite de salida por ganancia (opcional)

    Retorna dict con:
        entry_order, trailing_stop_order, take_profit_order (si aplica), symbol, qty
    """
    sym = symbol.upper()
    h = _build_headers(api_key, secret_key)

    # Paso 1: orden de compra market
    entry_payload = {
        "symbol":        sym,
        "qty":           str(int(qty)),
        "side":          "buy",
        "type":          "market",
        "time_in_force": "day",
    }
    entry_data = _post("orders", entry_payload, headers=h, base_url=base_url)
    entry_result = {
        "id":     entry_data["id"],
        "status": entry_data["status"],
        "symbol": entry_data["symbol"],
        "side":   entry_data["side"],
        "type":   entry_data["order_type"],
        "qty":    entry_data.get("qty"),
        "raw":    entry_data,
    }

    # Paso 2: trailing stop order
    ts_result = place_trailing_stop_order(
        symbol=sym,
        qty=int(qty),
        trail_percent=trail_percent,
        side="sell",
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url,
    )

    result = {
        "symbol":               sym,
        "qty":                  qty,
        "trail_percent":        trail_percent,
        "entry_order":          entry_result,
        "trailing_stop_order":  ts_result,
        "take_profit_order":    None,
    }

    # Paso 3: take profit limit (opcional)
    if take_profit_price is not None:
        tp_payload = {
            "symbol":        sym,
            "qty":           str(int(qty)),
            "side":          "sell",
            "type":          "limit",
            "time_in_force": "gtc",
            "limit_price":   str(round(take_profit_price, 4)),
        }
        tp_data = _post("orders", tp_payload, headers=h, base_url=base_url)
        result["take_profit_order"] = {
            "id":          tp_data["id"],
            "status":      tp_data["status"],
            "limit_price": take_profit_price,
            "raw":         tp_data,
        }

    return result


def cancel_order(order_id: str, api_key: str = None, secret_key: str = None, base_url: str = None) -> dict:
    """Cancela una orden abierta por su ID."""
    h = _build_headers(api_key, secret_key)
    return _delete(f"orders/{order_id}", headers=h, base_url=base_url)


def close_position(symbol: str, api_key: str = None, secret_key: str = None, base_url: str = None) -> dict:
    """Cierra completamente la posición de un ticker."""
    h = _build_headers(api_key, secret_key)
    return _delete(f"positions/{symbol.upper()}", headers=h, base_url=base_url)


# ─────────────────────────────────────────────
# Historial de portafolio
# ─────────────────────────────────────────────

def get_portfolio_history(period: str = "1M", timeframe: str = "1D", api_key: str = None, secret_key: str = None, base_url: str = None) -> dict:
    """
    Curva de equity histórica de la cuenta.

    period:    '1D' | '1W' | '1M' | '3M' | '6M' | '1A'
    timeframe: '1Min' | '5Min' | '15Min' | '1H' | '1D'

    Retorna:
        timestamps: lista de epoch seconds
        equity:     lista de valores de equity
        pl:         lista de P&L acumulado
    """
    h = _build_headers(api_key, secret_key)
    data = _get("account/portfolio/history", params={
        "period":    period,
        "timeframe": timeframe,
    }, headers=h, base_url=base_url)
    return {
        "timestamps": data.get("timestamp", []),
        "equity":     data.get("equity", []),
        "pl":         data.get("profit_loss", []),
        "pl_pct":     data.get("profit_loss_pct", []),
        "base_value": data.get("base_value", 0),
    }


# ─────────────────────────────────────────────
# Actividades de cuenta (fills reales)
# ─────────────────────────────────────────────

def get_activities(activity_type: str = "FILL", after: str = None, limit: int = 500, api_key: str = None, secret_key: str = None, base_url: str = None) -> list[dict]:
    """
    Retorna actividades de la cuenta.
    activity_type: 'FILL' (ejecuciones), 'JNLC', 'PTC', etc.
    after: ISO timestamp para filtrar desde esa fecha (ej: '2026-04-12T00:00:00Z')
    limit: máx 500 por llamada

    Cada item retornado:
        id, symbol, side, qty, price, total_value,
        transaction_time, order_id, activity_type
    """
    params = {"activity_type": activity_type, "page_size": limit, "direction": "desc"}
    if after:
        params["after"] = after

    h = _build_headers(api_key, secret_key)
    data = _get(f"account/activities/{activity_type}", params=params, headers=h, base_url=base_url)
    if not isinstance(data, list):
        data = [data]

    result = []
    for a in data:
        try:
            qty   = float(a.get("qty") or 0)
            price = float(a.get("price") or 0)
            result.append({
                "id":               a.get("id", ""),
                "symbol":           a.get("symbol", ""),
                "side":             a.get("side", ""),          # 'buy' | 'sell'
                "qty":              qty,
                "price":            price,
                "total_value":      round(qty * price, 2),
                "transaction_time": a.get("transaction_time", ""),
                "order_id":         a.get("order_id", ""),
                "activity_type":    a.get("activity_type", ""),
                "raw":              a,
            })
        except Exception:
            continue

    return result


# ─────────────────────────────────────────────
# Test de conexión
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not is_configured():
        print("⚠️  Configura ALPACA_API_KEY y ALPACA_SECRET_KEY en .env")
    else:
        acc = get_account()
        print(f"OK Conectado - Equity: ${acc['equity']:,.2f} | Cash: ${acc['cash']:,.2f}")
        positions = get_positions()
        print(f"   Posiciones abiertas: {len(positions)}")
        for p in positions:
            pl_sign = "+" if p['unrealized_pl'] >= 0 else ""
            print(f"   {p['symbol']:<6} {p['qty']} acciones @ ${p['avg_entry_price']:.2f}"
                  f" | P&L: {pl_sign}${p['unrealized_pl']:.2f} ({pl_sign}{p['unrealized_plpc']:.1f}%)")
