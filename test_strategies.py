#!/usr/bin/env python
"""
test_strategies.py — Prueba validación de estrategias y auto-trade
Ejecuta: python test_strategies.py
"""

import requests
import json
from datetime import datetime

API_URL = "http://localhost:8000/api"

def test_validate_ticker():
    """Prueba validación de un ticker contra estrategias."""
    print("\n" + "="*60)
    print("TEST 1: Validar AAPL contra todas las estrategias")
    print("="*60)

    try:
        response = requests.get(f"{API_URL}/validate/AAPL", timeout=10)
        data = response.json()

        if "error" in data:
            print(f"ERROR: {data['error']}")
            return

        print(f"\nTicker: {data['symbol']}")
        print(f"Estrategias que aplican: {', '.join(data['matching_strategies'])}")
        print(f"Total: {data['total_matching']}/{len(data['all_strategies'])}")

        # Mostrar detalles de la primera estrategia que pasa
        if data['matching_strategies']:
            strat = data['matching_strategies'][0]
            strat_data = data['all_strategies'][strat]
            print(f"\n📊 Detalles de {strat}:")
            print(f"  Precio actual: ${strat_data['price']}")
            print(f"  SL (5%): ${strat_data['sl_price']}")
            print(f"  TP (20%): ${strat_data['tp_price']}")
            print(f"  RSI 14: {strat_data['rsi_14']}")
            print(f"  Señales activas: {', '.join(strat_data['signals'])}")

    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar a la API. ¿Está corriendo en http://localhost:8000?")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_screener():
    """Prueba screener con estrategia específica."""
    print("\n" + "="*60)
    print("TEST 2: Ejecutar screener con momentum_alcista")
    print("="*60)

    try:
        response = requests.get(
            f"{API_URL}/screener",
            params={"strategy": "momentum_alcista", "period": "1y"},
            timeout=15
        )
        results = response.json()

        print(f"\nEncontrados {len(results)} candidatos")
        
        if results:
            print("\nTop 3 candidatos:")
            for i, candidate in enumerate(results[:3], 1):
                print(f"\n{i}. {candidate['ticker']} - ${candidate['price']}")
                print(f"   Signal Score: {candidate['signal_score']}/100")
                print(f"   Señales: {', '.join(candidate['signals_active'][:2])}")
                print(f"   SL: ${candidate['sl_price']}, TP: ${candidate['tp_price']}")

    except Exception as e:
        print(f"❌ Error: {e}")


def test_auto_trade():
    """Prueba trading automático REAL."""
    print("\n" + "="*60)
    print("TEST 3: EJECUTAR AUTO-TRADE")
    print("="*60)

    config = {
        "strategy": "momentum_alcista",
        "amount_usd": 500,
        "max_positions": 3,
        "sl_percent": 5,
        "tp_percent": 20
    }

    print(f"\nConfiguración:")
    print(f"  Estrategia: {config['strategy']}")
    print(f"  USD por trade: ${config['amount_usd']}")
    print(f"  Máximo posiciones: {config['max_positions']}")
    print(f"  Stop Loss: {config['sl_percent']}%")
    print(f"  Take Profit: {config['tp_percent']}%")

    print(f"\n🚀 EJECUTANDO en Alpaca paper trading...\n")

    try:
        response = requests.post(f"{API_URL}/auto-trade", json=config, timeout=30)
        result = response.json()

        status = result.get('status', 'unknown')
        print(f"Status: {status}")

        if result.get('message'):
            print(f"Mensaje: {result['message']}")

        trades = result.get('trades_placed', [])
        if trades:
            print(f"\n✓ {len(trades)} orden(es) colocada(s):")
            for trade in trades:
                print(f"  - {trade['symbol']}: {trade['qty']} shares")
                print(f"    Order ID: {trade['order_id']}")
                print(f"    Status: {trade['status']}")

        errors = result.get('errors', [])
        if errors:
            print(f"\n⚠️  {len(errors)} error(es):")
            for error in errors[:3]:
                print(f"  - {error}")

        config_result = result.get('config', {})
        if config_result:
            print(f"\n📊 Resumen:")
            print(f"  Estrategia: {config_result.get('strategy')}")
            print(f"  USD por trade: ${config_result.get('amount_per_trade')}")
            print(f"  Max posiciones: {config_result.get('max_positions')}")

    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar a la API en http://localhost:8000")
        print("   ¿Está corriendo: python api/run.py?")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_account():
    """Prueba obtener información de la cuenta."""
    print("\n" + "="*60)
    print("TEST 4: Estado de la cuenta Alpaca")
    print("="*60)

    try:
        response = requests.get(f"{API_URL}/account", timeout=5)
        account = response.json()

        if account.get("configured"):
            print(f"\n✓ Alpaca configurado")
            print(f"  Equity: ${account['equity']:,.2f}")
            print(f"  Cash: ${account['cash']:,.2f}")
            print(f"  Buying Power: ${account['buying_power']:,.2f}")
            print(f"  P&L Hoy: ${account['pl_today']:,.2f} ({account['pl_today_pct']:+.2f}%)")
            print(f"  P&L Total: ${account['pl_total']:,.2f} ({account['pl_total_pct']:+.2f}%)")
        else:
            print(f"\n❌ {account.get('error', 'No configurado')}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n🚀 AlphaHunter — Test de Estrategias y Auto-Trade")
    print(f"Timestamp: {datetime.now().isoformat()}")

    test_validate_ticker()
    test_screener()
    test_account()
    test_auto_trade()

    print("\n" + "="*60)
    print("Tests completados")
    print("="*60 + "\n")
