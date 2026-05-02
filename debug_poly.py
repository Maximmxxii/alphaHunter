import sys
sys.path.insert(0, 'C:/Users/maxim/AlphaHunter')
import requests
from utils.polymarket import search_financial_markets, FINANCIAL_TAG_IDS

# Step 1: raw API call
print("=== STEP 1: Raw API ===")
url = "https://gamma-api.polymarket.com/markets"
params = {"limit": 10, "active": True, "tag_id": 102000}
r = requests.get(url, params=params, timeout=10)
data = r.json()
print(f"Mercados recibidos: {len(data)}")
for m in data[:3]:
    print(f"  question : {m.get('question')}")
    print(f"  volume   : {m.get('volume')}")
    print(f"  liquidity: {m.get('liquidity')}")
    print(f"  outcomePrices: {m.get('outcomePrices')}")
    print()

# Step 2: search_financial_markets con traceo interno
print("=== STEP 2: search_financial_markets traceo ===")
import time, traceback
from utils.polymarket import get_markets, FINANCIAL_TAG_IDS

all_markets = []
for tag_id in FINANCIAL_TAG_IDS:
    try:
        markets = get_markets(limit=10, tag_id=tag_id)
        print(f"  tag_id={tag_id} → tipo={type(markets)} | len={len(markets) if isinstance(markets, list) else 'N/A'}")
        if isinstance(markets, list):
            all_markets.extend(markets)
    except Exception as e:
        print(f"  tag_id={tag_id} → ERROR: {e}")
        traceback.print_exc()
    time.sleep(0.1)

print(f"\nTotal mercados acumulados: {len(all_markets)}")
if all_markets:
    print("Primer mercado:", all_markets[0].get('question'))

# Ahora procesar filas
print("\n=== STEP 2b: Procesando filas ===")
rows = []
for m in all_markets[:3]:
    try:
        prices = m.get('outcomePrices', ['0.5', '0.5'])
        print(f"  prices raw: {prices} | tipo: {type(prices)}")
        prob_yes = float(prices[0]) if prices else 0.5
        print(f"  prob_yes: {prob_yes}")
        rows.append({"question": m.get('question'), "prob_yes": prob_yes})
    except Exception as e:
        print(f"  ERROR procesando: {e}")
        traceback.print_exc()
print(f"Filas procesadas: {len(rows)}")

# Step 3: keyword matching manual
print("\n=== STEP 3: Keyword match manual ===")
kw_inflation = ["inflation", "cpi", "pce", "price index"]
for m in data:
    q = m.get('question', '').lower()
    for kw in kw_inflation:
        if kw in q:
            print(f"  MATCH '{kw}' → {m.get('question')}")

