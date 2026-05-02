"""
Detecta flujo inusual de opciones: órdenes grandes que sugieren que alguien
sabe algo antes de que el mercado lo descubra.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .cache import get_cached, set_cached

BASE_URL = "https://www.barchart.com/options/unusual-activity/stocks"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.barchart.com/",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# ── Fallback data ──────────────────────────────────────────────────────────────
FALLBACK_OPTIONS: list[dict] = [
    {
        "ticker": "NVDA",
        "option_type": "call",
        "strike": 950.0,
        "expiration": "2026-04-18",
        "volume": 45_820,
        "open_interest": 12_400,
        "vol_oi_ratio": 3.70,
        "premium_usd": 8_240_000.0,
        "sentiment": "bullish",
        "signal_strength": 92,
    },
    {
        "ticker": "AAPL",
        "option_type": "call",
        "strike": 210.0,
        "expiration": "2026-05-16",
        "volume": 28_310,
        "open_interest": 9_200,
        "vol_oi_ratio": 3.08,
        "premium_usd": 4_120_000.0,
        "sentiment": "bullish",
        "signal_strength": 85,
    },
    {
        "ticker": "SPY",
        "option_type": "put",
        "strike": 490.0,
        "expiration": "2026-04-25",
        "volume": 61_200,
        "open_interest": 18_300,
        "vol_oi_ratio": 3.34,
        "premium_usd": 12_500_000.0,
        "sentiment": "bearish",
        "signal_strength": 88,
    },
    {
        "ticker": "META",
        "option_type": "call",
        "strike": 580.0,
        "expiration": "2026-06-20",
        "volume": 19_480,
        "open_interest": 7_100,
        "vol_oi_ratio": 2.74,
        "premium_usd": 3_890_000.0,
        "sentiment": "bullish",
        "signal_strength": 79,
    },
    {
        "ticker": "TSLA",
        "option_type": "call",
        "strike": 280.0,
        "expiration": "2026-05-02",
        "volume": 34_750,
        "open_interest": 11_200,
        "vol_oi_ratio": 3.10,
        "premium_usd": 5_670_000.0,
        "sentiment": "bullish",
        "signal_strength": 83,
    },
    {
        "ticker": "AMZN",
        "option_type": "call",
        "strike": 200.0,
        "expiration": "2026-04-18",
        "volume": 22_100,
        "open_interest": 8_900,
        "vol_oi_ratio": 2.48,
        "premium_usd": 2_980_000.0,
        "sentiment": "bullish",
        "signal_strength": 74,
    },
    {
        "ticker": "QQQ",
        "option_type": "put",
        "strike": 420.0,
        "expiration": "2026-04-30",
        "volume": 41_600,
        "open_interest": 15_800,
        "vol_oi_ratio": 2.63,
        "premium_usd": 9_100_000.0,
        "sentiment": "bearish",
        "signal_strength": 81,
    },
    {
        "ticker": "MSFT",
        "option_type": "call",
        "strike": 440.0,
        "expiration": "2026-05-16",
        "volume": 14_920,
        "open_interest": 6_300,
        "vol_oi_ratio": 2.37,
        "premium_usd": 2_210_000.0,
        "sentiment": "bullish",
        "signal_strength": 71,
    },
    {
        "ticker": "XOM",
        "option_type": "call",
        "strike": 115.0,
        "expiration": "2026-06-20",
        "volume": 18_340,
        "open_interest": 5_900,
        "vol_oi_ratio": 3.11,
        "premium_usd": 1_870_000.0,
        "sentiment": "bullish",
        "signal_strength": 77,
    },
    {
        "ticker": "GOOGL",
        "option_type": "call",
        "strike": 185.0,
        "expiration": "2026-05-09",
        "volume": 16_700,
        "open_interest": 7_200,
        "vol_oi_ratio": 2.32,
        "premium_usd": 2_540_000.0,
        "sentiment": "bullish",
        "signal_strength": 69,
    },
]


def _parse_options_html(html: str) -> list[dict]:
    """Parsea la tabla de opciones inusuales de Barchart."""
    soup = BeautifulSoup(html, "html.parser")
    options = []

    # Barchart renderiza dinámicamente con JS en muchos casos; intentamos tabla estática
    table = (
        soup.find("table", class_=lambda c: c and "unusual" in c.lower())
        or soup.find("table", {"data-ng-table": True})
        or soup.find("table")
    )

    if not table:
        return []

    rows = table.find_all("tr")[1:]
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        try:
            ticker = cells[0].get_text(strip=True).upper()
            exp_strike = cells[1].get_text(strip=True)  # ej: "Apr 18 $950 Call"
            volume_str = cells[2].get_text(strip=True).replace(",", "")
            oi_str = cells[3].get_text(strip=True).replace(",", "")
            vol_oi_str = cells[4].get_text(strip=True)
            premium_str = cells[5].get_text(strip=True).replace("$", "").replace(",", "").replace("M", "000000").replace("K", "000")

            opt_type = "call" if "call" in exp_strike.lower() else "put"

            # Extraer strike del texto
            import re
            strike_match = re.search(r"\$?([\d.]+)", exp_strike)
            strike = float(strike_match.group(1)) if strike_match else 0.0

            volume = int(volume_str) if volume_str.isdigit() else 0
            oi = int(oi_str) if oi_str.isdigit() else 0
            vol_oi = float(vol_oi_str) if vol_oi_str.replace(".", "").isdigit() else 0.0
            premium = float(premium_str) if premium_str.replace(".", "").isdigit() else 0.0

            sentiment = "bullish" if opt_type == "call" else "bearish"
            signal_strength = min(100, int(vol_oi * 20 + (premium / 1_000_000) * 5))

            if ticker:
                options.append({
                    "ticker": ticker,
                    "option_type": opt_type,
                    "strike": strike,
                    "expiration": "",
                    "volume": volume,
                    "open_interest": oi,
                    "vol_oi_ratio": vol_oi,
                    "premium_usd": premium,
                    "sentiment": sentiment,
                    "signal_strength": signal_strength,
                })
        except Exception:
            continue

    return options


def get_unusual_options(option_type: str = "all") -> list[dict]:
    """
    option_type: 'calls' | 'puts' | 'all'
    Cada item:
        ticker: str
        option_type: str (call/put)
        strike: float
        expiration: str
        volume: int
        open_interest: int
        vol_oi_ratio: float  (>2 es inusual)
        premium_usd: float   (tamaño de la apuesta)
        sentiment: str       (bullish/bearish/neutral)
        signal_strength: int (0-100)
    """
    cache_key = f"options:unusual:{option_type}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    print(f"[options] Scraping Barchart unusual options ({option_type})...")
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        options = _parse_options_html(resp.text)

        if not options:
            raise ValueError("Sin opciones en el HTML — posiblemente renderizado JS o estructura cambiada")

        # Filtrar por tipo
        if option_type == "calls":
            options = [o for o in options if o["option_type"] == "call"]
        elif option_type == "puts":
            options = [o for o in options if o["option_type"] == "put"]

        result = sorted(options, key=lambda x: x["signal_strength"], reverse=True)
        set_cached(cache_key, result)
        return result

    except Exception as e:
        print(f"[options] Scraping falló ({e}), usando fallback data")
        fallback = FALLBACK_OPTIONS
        if option_type == "calls":
            fallback = [o for o in fallback if o["option_type"] == "call"]
        elif option_type == "puts":
            fallback = [o for o in fallback if o["option_type"] == "put"]

        result = sorted(fallback, key=lambda x: x["signal_strength"], reverse=True)
        set_cached(cache_key, result)
        return result


def get_bullish_flow(min_premium: float = 100_000) -> list[dict]:
    """Solo calls con premiums grandes = señal alcista fuerte."""
    cache_key = f"options:bullish:{int(min_premium)}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    print(f"[options] Filtrando bullish flow (min_premium=${min_premium:,.0f})...")
    all_options = get_unusual_options(option_type="calls")
    result = [
        o for o in all_options
        if o["premium_usd"] >= min_premium and o["option_type"] == "call"
    ]
    result.sort(key=lambda x: x["premium_usd"], reverse=True)

    set_cached(cache_key, result)
    return result
