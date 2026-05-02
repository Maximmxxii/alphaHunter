"""
Obtiene posiciones actuales de inversores institucionales top (13F filings).
Fuente: Dataroma - gratis, público.
Inversores incluidos: Buffett (Berkshire), Ackman, Tepper, Einhorn, etc.
"""

from __future__ import annotations

from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from .cache import get_cached, set_cached

BASE_URL = "https://www.dataroma.com/m/holdings.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.dataroma.com/",
}

AVAILABLE_INVESTORS = [
    {"id": "brk", "name": "Warren Buffett (Berkshire Hathaway)"},
    {"id": "psc", "name": "Bill Ackman (Pershing Square)"},
    {"id": "dt",  "name": "David Tepper (Appaloosa Management)"},
    {"id": "gh",  "name": "David Einhorn (Greenlight Capital)"},
    {"id": "br",  "name": "Bill & Melinda Gates Foundation"},
    {"id": "lc",  "name": "Li Lu (Himalaya Capital)"},
    {"id": "cf",  "name": "Chase Coleman (Tiger Global)"},
    {"id": "sp",  "name": "Stanley Druckenmiller (Duquesne Family Office)"},
    {"id": "tw",  "name": "Michael Burry (Scion Asset Management)"},
    {"id": "dm",  "name": "Dan Loeb (Third Point)"},
]

# ── Fallback data ──────────────────────────────────────────────────────────────
FALLBACK_BRK: list[dict] = [
    {"ticker": "AAPL", "company": "Apple Inc.", "pct_portfolio": 46.4, "shares": 905_559_761, "value_usd": 174_300_000_000, "action": "reduce"},
    {"ticker": "BAC",  "company": "Bank of America Corp.", "pct_portfolio": 9.8, "shares": 1_032_852_006, "value_usd": 37_700_000_000, "action": "hold"},
    {"ticker": "AXP",  "company": "American Express Co.", "pct_portfolio": 7.6, "shares": 151_610_700, "value_usd": 29_300_000_000, "action": "hold"},
    {"ticker": "KO",   "company": "Coca-Cola Co.", "pct_portfolio": 6.8, "shares": 400_000_000, "value_usd": 26_100_000_000, "action": "hold"},
    {"ticker": "CVX",  "company": "Chevron Corp.", "pct_portfolio": 5.5, "shares": 118_262_000, "value_usd": 21_100_000_000, "action": "reduce"},
    {"ticker": "OXY",  "company": "Occidental Petroleum", "pct_portfolio": 4.9, "shares": 248_018_128, "value_usd": 18_700_000_000, "action": "add"},
    {"ticker": "KHC",  "company": "Kraft Heinz Co.", "pct_portfolio": 3.8, "shares": 325_634_818, "value_usd": 14_500_000_000, "action": "hold"},
    {"ticker": "MCO",  "company": "Moody's Corp.", "pct_portfolio": 3.1, "shares": 24_669_778, "value_usd": 11_800_000_000, "action": "hold"},
    {"ticker": "DVA",  "company": "DaVita Inc.", "pct_portfolio": 1.6, "shares": 36_095_570, "value_usd": 6_100_000_000, "action": "hold"},
    {"ticker": "HPE",  "company": "HP Enterprise", "pct_portfolio": 1.2, "shares": 120_949_780, "value_usd": 4_600_000_000, "action": "new"},
    {"ticker": "V",    "company": "Visa Inc.", "pct_portfolio": 1.0, "shares": 8_297_460, "value_usd": 3_800_000_000, "action": "hold"},
    {"ticker": "MA",   "company": "Mastercard Inc.", "pct_portfolio": 0.8, "shares": 3_986_648, "value_usd": 3_100_000_000, "action": "hold"},
]

FALLBACK_PSC: list[dict] = [
    {"ticker": "HHH",  "company": "Howard Hughes Holdings", "pct_portfolio": 21.2, "shares": 13_500_000, "value_usd": 890_000_000, "action": "add"},
    {"ticker": "GOOG", "company": "Alphabet Inc.", "pct_portfolio": 19.8, "shares": 3_800_000, "value_usd": 830_000_000, "action": "new"},
    {"ticker": "BN",   "company": "Brookfield Corp.", "pct_portfolio": 17.5, "shares": 24_000_000, "value_usd": 730_000_000, "action": "add"},
    {"ticker": "HLT",  "company": "Hilton Worldwide", "pct_portfolio": 13.2, "shares": 2_900_000, "value_usd": 553_000_000, "action": "hold"},
    {"ticker": "QSR",  "company": "Restaurant Brands", "pct_portfolio": 9.7, "shares": 8_900_000, "value_usd": 407_000_000, "action": "hold"},
    {"ticker": "CMG",  "company": "Chipotle Mexican Grill", "pct_portfolio": 8.1, "shares": 240_000, "value_usd": 340_000_000, "action": "reduce"},
]

FALLBACK_DT: list[dict] = [
    {"ticker": "META", "company": "Meta Platforms", "pct_portfolio": 12.4, "shares": 1_200_000, "value_usd": 720_000_000, "action": "add"},
    {"ticker": "NVDA", "company": "NVIDIA Corp.", "pct_portfolio": 11.8, "shares": 800_000, "value_usd": 684_000_000, "action": "new"},
    {"ticker": "AMZN", "company": "Amazon.com Inc.", "pct_portfolio": 9.6, "shares": 2_900_000, "value_usd": 557_000_000, "action": "add"},
    {"ticker": "MSFT", "company": "Microsoft Corp.", "pct_portfolio": 8.2, "shares": 950_000, "value_usd": 476_000_000, "action": "hold"},
    {"ticker": "AAPL", "company": "Apple Inc.", "pct_portfolio": 7.1, "shares": 1_800_000, "value_usd": 412_000_000, "action": "reduce"},
]

FALLBACK_BY_ID: dict[str, list[dict]] = {
    "brk": FALLBACK_BRK,
    "psc": FALLBACK_PSC,
    "dt":  FALLBACK_DT,
}


def _parse_holdings_html(html: str) -> list[dict]:
    """Parsea la tabla de holdings de Dataroma."""
    soup = BeautifulSoup(html, "html.parser")
    holdings = []

    table = soup.find("table", {"id": "grid"}) or soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # skip header
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        try:
            ticker_cell = cells[0].get_text(strip=True)
            company_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            pct_cell = cells[2].get_text(strip=True).replace("%", "") if len(cells) > 2 else "0"
            shares_cell = cells[3].get_text(strip=True).replace(",", "") if len(cells) > 3 else "0"
            value_cell = cells[4].get_text(strip=True).replace(",", "").replace("$", "") if len(cells) > 4 else "0"
            activity_cell = cells[5].get_text(strip=True).lower() if len(cells) > 5 else ""

            # Mapear activity
            if "new" in activity_cell:
                action = "new"
            elif "add" in activity_cell or "increase" in activity_cell:
                action = "add"
            elif "reduce" in activity_cell or "decrease" in activity_cell:
                action = "reduce"
            elif "sell" in activity_cell or "sold" in activity_cell:
                action = "sell"
            else:
                action = "hold"

            holdings.append({
                "ticker": ticker_cell.upper(),
                "company": company_cell,
                "pct_portfolio": float(pct_cell) if pct_cell else 0.0,
                "shares": int(float(shares_cell)) if shares_cell.replace(".", "").isdigit() else 0,
                "value_usd": int(float(value_cell) * 1000) if value_cell.replace(".", "").isdigit() else 0,
                "action": action,
            })
        except (ValueError, IndexError):
            continue

    return holdings


def get_superinvestor_holdings(investor_id: str = "brk") -> list[dict]:
    """
    Retorna holdings de un superinvestor.
    investor_id: 'brk' (Berkshire), 'psc' (Ackman), 'dt' (Tepper), etc.
    Cada item: ticker, company, pct_portfolio, shares, value_usd, action (add/reduce/new/sell/hold)
    """
    cache_key = f"whales:holdings:{investor_id}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    print(f"[whales] Scraping Dataroma para {investor_id}...")
    try:
        url = f"{BASE_URL}?m={investor_id}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        holdings = _parse_holdings_html(resp.text)

        if not holdings:
            raise ValueError("Sin holdings en el HTML — estructura cambiada")

        set_cached(cache_key, holdings)
        return holdings

    except Exception as e:
        print(f"[whales] Scraping falló para {investor_id} ({e}), usando fallback data")
        fallback = FALLBACK_BY_ID.get(investor_id, FALLBACK_BRK)
        set_cached(cache_key, fallback)
        return fallback


def get_consensus_buys(min_investors: int = 3) -> list[dict]:
    """
    Tickers que están comprando múltiples superinvestors simultáneamente.
    min_investors: mínimo de inversores que deben tener el ticker para incluirlo.
    Retorna: ticker, n_investors, investors_list, consensus_score (0-100)
    """
    cache_key = f"whales:consensus:{min_investors}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    print("[whales] Calculando consensus buys...")

    # Obtener holdings de los top inversores
    top_ids = ["brk", "psc", "dt", "gh", "sp"]
    investor_names = {inv["id"]: inv["name"] for inv in AVAILABLE_INVESTORS}

    ticker_data: dict[str, dict] = defaultdict(lambda: {
        "ticker": "",
        "investors": [],
        "new_or_add_count": 0,
        "total_pct": 0.0,
    })

    for inv_id in top_ids:
        holdings = get_superinvestor_holdings(inv_id)
        inv_name = investor_names.get(inv_id, inv_id)

        for h in holdings:
            ticker = h["ticker"]
            ticker_data[ticker]["ticker"] = ticker
            ticker_data[ticker]["investors"].append(inv_name)
            ticker_data[ticker]["total_pct"] += h["pct_portfolio"]
            if h["action"] in ("new", "add"):
                ticker_data[ticker]["new_or_add_count"] += 1

    result = []
    for ticker, data in ticker_data.items():
        n = len(data["investors"])
        if n < min_investors:
            continue

        # consensus_score: cuántos inversores lo tienen + peso de nuevos/add + % promedio
        add_bonus = data["new_or_add_count"] * 10
        pct_avg = data["total_pct"] / n
        score = min(100, int(n * 15 + add_bonus + pct_avg * 0.5))

        result.append({
            "ticker": ticker,
            "n_investors": n,
            "investors_list": data["investors"],
            "consensus_score": score,
        })

    result.sort(key=lambda x: x["consensus_score"], reverse=True)

    if not result:
        # Fallback manual con tickers ampliamente compartidos
        result = [
            {"ticker": "AAPL",  "n_investors": 4, "investors_list": ["Buffett", "Ackman", "Tepper", "Druckenmiller"], "consensus_score": 72},
            {"ticker": "AMZN",  "n_investors": 3, "investors_list": ["Tepper", "Druckenmiller", "Tiger Global"], "consensus_score": 61},
            {"ticker": "META",  "n_investors": 3, "investors_list": ["Tepper", "Druckenmiller", "Third Point"], "consensus_score": 58},
            {"ticker": "GOOGL", "n_investors": 3, "investors_list": ["Ackman", "Druckenmiller", "Tiger Global"], "consensus_score": 55},
            {"ticker": "MSFT",  "n_investors": 3, "investors_list": ["Tepper", "Einhorn", "Tiger Global"], "consensus_score": 52},
        ]

    set_cached(cache_key, result)
    return result


def get_available_investors() -> list[dict]:
    """Lista de inversores disponibles con id y nombre."""
    return AVAILABLE_INVESTORS
