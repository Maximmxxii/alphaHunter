"""
utils/polymarket.py — Integración con Polymarket para sentimiento de mercado

Polymarket es un mercado de predicciones donde los precios reflejan
probabilidades implícitas del mercado sobre eventos futuros.

Cómo se usa en AlphaHunter:
    1. Sentimiento macro  : ¿qué probabilidad le da el mercado a recesión,
                            subida de tasas, caída del S&P 500?
    2. Feature ML         : prob_recesion, prob_fed_sube, prob_btc_100k
                            se agregan como features adicionales al modelo XGBoost
    3. Filtro de contexto : si prob_recesion > 0.6, el screener reduce
                            el umbral de vol_ratio exigido (mercado nervioso)
    4. Divergencia        : cuando XGBoost dice +72% subida pero Polymarket
                            dice +68% caída → señal de alerta, no operar

API utilizada:
    Gamma API (pública, sin autenticación)
    Base URL: https://gamma-api.polymarket.com

Tags financieros relevantes (IDs confirmados):
    102000 → Macro Indicators
    102973 → macro
    100968 → commodity
    101528 → altcoin
    101531 → Strategic Bitcoin Reserve
    101622 → Debt
    103678 → initial jobless claims
"""

import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

GAMMA_API  = "https://gamma-api.polymarket.com"
TIMEOUT    = 10  # segundos por request

# Tags con mayor relevancia financiera
FINANCIAL_TAG_IDS = [102000, 102973, 100968, 101528, 101531, 101622, 103678]

# Palabras clave para filtrar mercados financieros por texto
FINANCIAL_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "s&p", "sp500",
    "nasdaq", "recession", "fed", "interest rate", "inflation", "cpi",
    "gdp", "unemployment", "oil", "gold", "dollar", "rate cut", "rate hike",
    "stock", "market crash", "bull", "bear", "ipo", "tariff", "trade war",
    # keywords adicionales para mercados con tag 102000
    "upper bound", "lower bound", "dollarize", "gdp growth",
    "federal reserve", "rate hike", "rate cut", "yield", "treasury",
    "debt", "deficit", "jobless", "payroll", "pce", "core",
    "commodity", "crude", "natural gas", "silver", "copper",
]


def _get(endpoint: str, params: dict = None) -> list | dict:
    """Wrapper de GET con manejo de errores y timeout."""
    url = f"{GAMMA_API}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        raise ConnectionError(f"Polymarket API timeout ({TIMEOUT}s): {url}")
    except requests.exceptions.HTTPError as e:
        raise ConnectionError(f"Polymarket API error {e.response.status_code}: {url}")


def get_markets(
    limit: int = 100,
    active: bool = True,
    tag_id: int = None,
) -> list[dict]:
    """
    Obtiene mercados activos de Polymarket.

    Args:
        limit  : Máximo de mercados a retornar (máx. 100 por request)
        active : Si True, solo mercados activos y no cerrados
        tag_id : Filtrar por ID de tag específico

    Returns:
        Lista de dicts con datos crudos de cada mercado
    """
    params = {"limit": limit, "active": active}
    if tag_id:
        params["tag_id"] = tag_id
    return _get("/markets", params)


def search_financial_markets(
    keywords: list[str] = None,
    min_volume: float = 0.0,
    min_liquidity: float = 0.0,
) -> pd.DataFrame:
    """
    Busca mercados de Polymarket relacionados con finanzas y economía.

    Estrategia de búsqueda:
        1. Fetcha TODOS los tags financieros conocidos (principal fuente)
        2. Complementa con pool general filtrando por keywords
        3. Descarta duplicados por id

    Nota: min_volume y min_liquidity son 0 por defecto porque los mercados
    financieros de Polymarket suelen tener menor volumen que los virales.
    Ajustar solo si hay demasiado ruido.

    Args:
        keywords     : Lista adicional de keywords a buscar.
                       Si None, usa FINANCIAL_KEYWORDS por defecto.
        min_volume   : Volumen mínimo en USD (default 0 = sin filtro)
        min_liquidity: Liquidez mínima en USD (default 0 = sin filtro)

    Returns:
        DataFrame con columnas: question, prob_yes, prob_no,
        volume, liquidity, end_date
    """
    kw_list = keywords or FINANCIAL_KEYWORDS
    all_markets = []

    # Fuente primaria: tags financieros conocidos (no filtrar por keyword aquí)
    for tag_id in FINANCIAL_TAG_IDS:
        try:
            markets = get_markets(limit=100, tag_id=tag_id)
            if isinstance(markets, list):
                all_markets.extend(markets)
            time.sleep(0.15)  # respetar rate limit
        except Exception:
            pass

    # Fuente secundaria: pool general filtrado por keyword
    try:
        general = get_markets(limit=100)
        if isinstance(general, list):
            for m in general:
                q = m.get('question', '').lower()
                if any(kw in q for kw in kw_list):
                    all_markets.append(m)
    except Exception:
        pass

    # Eliminar duplicados por id
    seen = set()
    unique = []
    for m in all_markets:
        if m.get('id') not in seen:
            seen.add(m.get('id'))
            unique.append(m)

    # Los mercados de tags financieros ya son relevantes — no filtrar por keyword
    # Solo aplicar keyword filter a los del pool general (ya filtrados arriba)
    filtered = unique

    if not filtered:
        return pd.DataFrame()

    rows = []
    for m in filtered:
        try:
            prices_raw = m.get('outcomePrices', '["0.5", "0.5"]')
            # outcomePrices llega como string JSON → parsear primero
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            prob_yes = float(prices[0]) if prices else 0.5
            prob_no  = float(prices[1]) if len(prices) > 1 else 1 - prob_yes

            volume    = float(m.get('volume', 0) or 0)
            liquidity = float(m.get('liquidity', 0) or 0)

            # Aplicar filtros mínimos
            if volume < min_volume or liquidity < min_liquidity:
                continue

            end_raw = m.get('endDate', '')
            try:
                end_date = datetime.fromisoformat(end_raw.replace('Z', '+00:00')).date()
            except Exception:
                end_date = None

            rows.append({
                "id":         m.get('id'),
                "question":   m.get('question', ''),
                "prob_yes":   round(prob_yes, 3),
                "prob_no":    round(prob_no, 3),
                "volume":     round(volume, 2),
                "liquidity":  round(liquidity, 2),
                "end_date":   end_date,
                "active":     m.get('active', True),
                "closed":     m.get('closed', False),
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    return df.sort_values("volume", ascending=False).reset_index(drop=True)


def get_macro_sentiment() -> dict:
    """
    Extrae señales macro del mercado de predicciones.

    Busca mercados específicos sobre:
        - Recesión en EE.UU.
        - Decisiones de la Fed (tasas de interés)
        - Bitcoin sobre $100K
        - Crash del S&P 500
        - Inflación / CPI

    Returns:
        Dict con probabilidades normalizadas (0.0 a 1.0) para cada señal.
        Incluye 'sentiment_score': promedio ponderado por volumen.

    Ejemplo de retorno:
        {
            "prob_recession":   0.42,
            "prob_fed_cut":     0.61,
            "prob_btc_100k":    0.38,
            "prob_sp_crash":    0.15,
            "prob_inflation":   0.55,
            "sentiment_score":  0.47,   # > 0.5 = mercado pesimista
            "markets_found":    8,
            "total_volume":     4_250_000,
        }
    """
    # Categorías de búsqueda con keywords adaptados a las preguntas reales de Polymarket
    categories = {
        "prob_recession":  ["recession", "gdp contraction", "negative gdp", "gdp growth", "gdp negative", "negative growth"],
        "prob_fed_cut":    ["rate cut", "fed cut", "lower bound", "fed lower", "fed's lower", "rate decrease"],
        "prob_fed_hike":   ["rate hike", "fed hike", "upper bound", "fed's upper", "rate increase", "rate higher"],
        "prob_btc_100k":   ["bitcoin above 100", "btc above 100", "bitcoin 100k", "btc 100k", "bitcoin hit $1", "bitcoin $1m", "bitcoin reach"],
        "prob_btc_crash":  ["bitcoin below 50", "btc below 50", "bitcoin crash", "btc crash", "bitcoin below"],
        "prob_sp_crash":   ["s&p 500 below", "nasdaq crash", "market crash", "stock crash", "s&p below"],
        "prob_inflation":  ["inflation", "cpi", "pce", "price index"],
    }

    try:
        df = search_financial_markets(min_volume=0, min_liquidity=0)
    except Exception as e:
        return {"error": str(e), "sentiment_score": 0.5, "markets_found": 0}

    if df.empty:
        return {"sentiment_score": 0.5, "markets_found": 0, "total_volume": 0}

    result = {}
    total_volume = 0
    markets_found = 0

    for key, kw_list in categories.items():
        matches = df[df['question'].str.lower().apply(
            lambda q: any(kw in q for kw in kw_list)
        )]

        if not matches.empty:
            # Promedio ponderado por volumen
            weighted_prob = (matches['prob_yes'] * matches['volume']).sum() / matches['volume'].sum()
            result[key] = round(weighted_prob, 3)
            total_volume += matches['volume'].sum()
            markets_found += len(matches)
        else:
            result[key] = None  # sin datos suficientes

    # Sentiment score: señales bajistas ponderadas
    bearish_signals = [
        result.get('prob_recession'),
        result.get('prob_btc_crash'),
        result.get('prob_sp_crash'),
        result.get('prob_fed_hike'),
    ]
    valid = [s for s in bearish_signals if s is not None]
    result['sentiment_score'] = round(sum(valid) / len(valid), 3) if valid else 0.5
    result['markets_found']   = markets_found
    result['total_volume']    = round(total_volume, 2)
    result['timestamp']       = datetime.now().isoformat()

    return result


def get_asset_sentiment(asset: str) -> dict:
    """
    Obtiene el sentimiento específico de Polymarket para un activo.

    Útil para enriquecer la predicción ML de un ticker particular.

    Args:
        asset: Nombre del activo (ej. 'bitcoin', 'ethereum', 'gold', 'oil')

    Returns:
        Dict con: prob_up, prob_down, n_markets, total_volume, markets
    """
    try:
        df = search_financial_markets(keywords=[asset.lower()], min_volume=0, min_liquidity=0)
    except Exception as e:
        return {"error": str(e), "prob_up": 0.5, "prob_down": 0.5, "n_markets": 0}

    if df.empty:
        return {"prob_up": 0.5, "prob_down": 0.5, "n_markets": 0, "total_volume": 0}

    # Clasificar mercados como alcistas o bajistas por keyword en la pregunta
    bullish_kw = ["above", "higher", "over", "exceed", "reach", "bull", "rise", "gain"]
    bearish_kw = ["below", "lower", "under", "fall", "crash", "bear", "drop", "decline"]

    bull_markets = df[df['question'].str.lower().apply(
        lambda q: any(kw in q for kw in bullish_kw)
    )]
    bear_markets = df[df['question'].str.lower().apply(
        lambda q: any(kw in q for kw in bearish_kw)
    )]

    def weighted_avg(subset):
        if subset.empty:
            return 0.5
        return (subset['prob_yes'] * subset['volume']).sum() / subset['volume'].sum()

    return {
        "asset":        asset,
        "prob_up":      round(weighted_avg(bull_markets), 3),
        "prob_down":    round(weighted_avg(bear_markets), 3),
        "n_markets":    len(df),
        "total_volume": round(df['volume'].sum(), 2),
        "markets":      df[['question', 'prob_yes', 'volume', 'end_date']].to_dict('records'),
    }


def print_sentiment_report(sentiment: dict) -> None:
    """Imprime reporte de sentimiento macro formateado."""
    print("\n" + "="*55)
    print("  Polymarket — Sentimiento Macro")
    print("="*55)

    labels = {
        "prob_recession":  "Recesión EE.UU.",
        "prob_fed_cut":    "Fed recorta tasas",
        "prob_fed_hike":   "Fed sube tasas",
        "prob_btc_100k":   "Bitcoin > $100K",
        "prob_btc_crash":  "Bitcoin crash",
        "prob_sp_crash":   "S&P 500 crash",
        "prob_inflation":  "Inflación alta",
    }

    for key, label in labels.items():
        val = sentiment.get(key)
        if val is not None:
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"  {label:<22} {bar} {val:.1%}")

    score = sentiment.get('sentiment_score', 0.5)
    print(f"\n  Sentiment score  : {score:.1%} ", end="")
    if score > 0.6:
        print("⚠️  MERCADO PESIMISTA — cautela")
    elif score < 0.4:
        print("✅ MERCADO OPTIMISTA — favorable")
    else:
        print("↔️  NEUTRAL")

    print(f"  Mercados usados  : {sentiment.get('markets_found', 0)}")
    print(f"  Volumen total    : ${sentiment.get('total_volume', 0):,.0f}")
    print("="*55)


if __name__ == "__main__":
    print("Consultando sentimiento macro en Polymarket...")
    sentiment = get_macro_sentiment()
    print_sentiment_report(sentiment)

    print("\nSentimiento específico: Bitcoin")
    btc = get_asset_sentiment("bitcoin")
    print(f"  Prob sube : {btc['prob_up']:.1%}")
    print(f"  Prob baja : {btc['prob_down']:.1%}")
    print(f"  Mercados  : {btc['n_markets']}")
    print(f"  Volumen   : ${btc['total_volume']:,.0f}")
