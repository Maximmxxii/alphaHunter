"""
Combina señales de congresistas, ballenas institucionales y flujo de opciones
en un score de convicción unificado para el screener.
"""

from __future__ import annotations

from collections import defaultdict

from .congress import get_congress_trades
from .whales import get_consensus_buys
from .options_flow import get_unusual_options
from .cache import get_cached, set_cached


def _build_congress_index(limit: int = 200) -> dict[str, list[dict]]:
    """Crea índice ticker → trades de congresistas."""
    trades = get_congress_trades(limit=limit)
    index: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        index[t["ticker"]].append(t)
    return index


def _build_whales_index(min_investors: int = 2) -> dict[str, dict]:
    """Crea índice ticker → datos de consenso ballenas."""
    consensus = get_consensus_buys(min_investors=min_investors)
    return {item["ticker"]: item for item in consensus}


def _build_options_index() -> dict[str, list[dict]]:
    """Crea índice ticker → opciones inusuales."""
    opts = get_unusual_options(option_type="all")
    index: dict[str, list[dict]] = defaultdict(list)
    for o in opts:
        index[o["ticker"]].append(o)
    return index


def _score_congress(trades: list[dict]) -> tuple[int, str]:
    """Calcula score parcial de señal de congresistas (0-40)."""
    if not trades:
        return 0, ""

    buys = [t for t in trades if t["transaction_type"] == "buy"]
    sells = [t for t in trades if t["transaction_type"] == "sell"]
    net_bias = len(buys) - len(sells)

    # Número de políticos únicos
    unique_politicians = len({t["politician"] for t in trades})

    score = min(40, unique_politicians * 8 + max(0, net_bias) * 5)
    politicians_str = ", ".join({t["politician"] for t in trades})
    summary = f"{len(buys)} compras / {len(sells)} ventas por {unique_politicians} congresistas ({politicians_str})"
    return score, summary


def _score_whales(whale_data: dict | None) -> tuple[int, str]:
    """Calcula score parcial de señal de ballenas (0-35)."""
    if not whale_data:
        return 0, ""

    n = whale_data.get("n_investors", 0)
    consensus = whale_data.get("consensus_score", 0)
    score = min(35, int(consensus * 0.35))
    investors = ", ".join(whale_data.get("investors_list", []))
    summary = f"{n} superinversores lo tienen (consensus={consensus}): {investors}"
    return score, summary


def _score_options(opts: list[dict]) -> tuple[int, str]:
    """Calcula score parcial de señal de opciones (0-25)."""
    if not opts:
        return 0, ""

    calls = [o for o in opts if o["option_type"] == "call"]
    puts = [o for o in opts if o["option_type"] == "put"]

    bullish_premium = sum(o["premium_usd"] for o in calls)
    bearish_premium = sum(o["premium_usd"] for o in puts)

    # Sesgo neto hacia calls
    total = bullish_premium + bearish_premium
    if total == 0:
        return 0, ""

    call_pct = bullish_premium / total
    max_strength = max((o["signal_strength"] for o in opts), default=0)

    score = min(25, int(call_pct * 15 + max_strength * 0.10))
    top_opt = sorted(opts, key=lambda x: x["signal_strength"], reverse=True)[0]
    summary = (
        f"Flujo: ${bullish_premium/1e6:.1f}M calls / ${bearish_premium/1e6:.1f}M puts | "
        f"Top: {top_opt['option_type'].upper()} ${top_opt['strike']} exp {top_opt['expiration']}"
    )
    return score, summary


def get_smart_money_signals(tickers: list[str] | None = None) -> list[dict]:
    """
    Para cada ticker, combina señales de las 3 fuentes.
    Retorna lista ordenada por conviction_score desc.

    Cada item:
        ticker: str
        conviction_score: int (0-100)
        sources: list[str] (cuáles fuentes lo tienen: congress/whales/options)
        summary: str (texto en lenguaje simple explicando la señal)
        details: dict (detalles de cada fuente)
    """
    cache_key = f"signals:all:{','.join(sorted(tickers)) if tickers else 'all'}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    print("[signals] Generando smart money signals...")

    congress_idx = _build_congress_index()
    whales_idx = _build_whales_index()
    options_idx = _build_options_index()

    # Universo de tickers a analizar
    all_tickers = set(congress_idx.keys()) | set(whales_idx.keys()) | set(options_idx.keys())
    if tickers:
        all_tickers = all_tickers & set(t.upper() for t in tickers)

    results = []
    for ticker in all_tickers:
        congress_trades = congress_idx.get(ticker, [])
        whale_data = whales_idx.get(ticker)
        opt_list = options_idx.get(ticker, [])

        congress_score, congress_summary = _score_congress(congress_trades)
        whale_score, whale_summary = _score_whales(whale_data)
        options_score, options_summary = _score_options(opt_list)

        conviction_score = congress_score + whale_score + options_score

        sources = []
        if congress_score > 0:
            sources.append("congress")
        if whale_score > 0:
            sources.append("whales")
        if options_score > 0:
            sources.append("options")

        # Resumen en lenguaje simple
        parts = []
        if congress_summary:
            parts.append(f"Congresistas: {congress_summary}")
        if whale_summary:
            parts.append(f"Ballenas: {whale_summary}")
        if options_summary:
            parts.append(f"Opciones: {options_summary}")

        summary = " | ".join(parts) if parts else "Sin señal activa"

        results.append({
            "ticker": ticker,
            "conviction_score": conviction_score,
            "sources": sources,
            "summary": summary,
            "details": {
                "congress": {
                    "score": congress_score,
                    "trades": congress_trades,
                    "summary": congress_summary,
                },
                "whales": {
                    "score": whale_score,
                    "data": whale_data,
                    "summary": whale_summary,
                },
                "options": {
                    "score": options_score,
                    "flows": opt_list,
                    "summary": options_summary,
                },
            },
        })

    results.sort(key=lambda x: x["conviction_score"], reverse=True)
    set_cached(cache_key, results)
    return results


def get_signals_for_mode(mode: str) -> list[dict]:
    """
    mode: 'congress' | 'whales' | 'options_flow' | 'all'
    Retorna señales filtradas por modo para el dropdown del frontend.
    """
    if mode == "all":
        return get_smart_money_signals()

    cache_key = f"signals:mode:{mode}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if mode == "congress":
        trades = get_congress_trades(limit=100)
        # Agrupar por ticker
        ticker_map: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            ticker_map[t["ticker"]].append(t)

        result = []
        for ticker, t_list in ticker_map.items():
            buys = [t for t in t_list if t["transaction_type"] == "buy"]
            politicians = list({t["politician"] for t in t_list})
            score, summary = _score_congress(t_list)
            result.append({
                "ticker": ticker,
                "conviction_score": score,
                "sources": ["congress"],
                "summary": summary,
                "details": {"congress": {"trades": t_list}},
            })
        result.sort(key=lambda x: x["conviction_score"], reverse=True)

    elif mode == "whales":
        consensus = get_consensus_buys(min_investors=2)
        result = []
        for item in consensus:
            score, summary = _score_whales(item)
            result.append({
                "ticker": item["ticker"],
                "conviction_score": score,
                "sources": ["whales"],
                "summary": summary,
                "details": {"whales": item},
            })
        result.sort(key=lambda x: x["conviction_score"], reverse=True)

    elif mode == "options_flow":
        opts = get_unusual_options(option_type="all")
        ticker_map_o: dict[str, list[dict]] = defaultdict(list)
        for o in opts:
            ticker_map_o[o["ticker"]].append(o)

        result = []
        for ticker, o_list in ticker_map_o.items():
            score, summary = _score_options(o_list)
            result.append({
                "ticker": ticker,
                "conviction_score": score,
                "sources": ["options"],
                "summary": summary,
                "details": {"options": {"flows": o_list}},
            })
        result.sort(key=lambda x: x["conviction_score"], reverse=True)

    else:
        result = []

    set_cached(cache_key, result)
    return result
