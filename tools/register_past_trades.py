"""
tools/register_past_trades.py — Registra trades pasados manualmente en el journal.

Uso:
    python tools/register_past_trades.py

Llena la lista TRADES_DE_ANOCHE con tus datos y ejecuta.
El script inserta las entradas en data/trade_journal.json.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.trade_journal import record_entry, record_exit

# ─────────────────────────────────────────────────────────────────
# EDITA ESTA LISTA con los datos reales de anoche.
#
# Para saber el precio de entrada/salida podés revisar:
#   - Alpaca paper account → Activity / Orders history
#   - O usar el precio de cierre del día en yfinance
#
# Ejemplo real:
#   ticker          = "AMD"
#   entry_price     = 92.50    # precio al que compraste
#   exit_price      = 96.80    # precio al que se cerró (TP o manual)
#   exit_reason     = "take_profit"  | "stop_loss" | "manual"
#   pnl ganado      = lo calcula el script automáticamente
# ─────────────────────────────────────────────────────────────────

TRADES_DE_ANOCHE = [
    # { "ticker": "AMD",   "entry_price": 92.50,  "exit_price": 96.80,  "qty": 54, "monto_usd": 4995.0,  "ml_prob": 0.71, "won": True  },
    # { "ticker": "NVDA",  "entry_price": 110.20, "exit_price": 108.50, "qty": 45, "monto_usd": 4959.0,  "ml_prob": 0.65, "won": False },
    # Agrega uno por ticker que hayas operado...
]

SCREENER_STRATEGY   = "exploratorio"
STOP_LOSS_PCT       = 7.0
TAKE_PROFIT_PCT     = 15.0
ENTRY_TIME_PREFIX   = "2026-04-12 22"   # hora aproximada de entrada (solo para referencia)


def main():
    if not TRADES_DE_ANOCHE:
        print("⚠  Lista TRADES_DE_ANOCHE vacía. Edita el script y vuelve a correrlo.")
        return

    for i, t in enumerate(TRADES_DE_ANOCHE):
        ticker = t["ticker"]

        # Registrar entrada
        trade_id = record_entry(
            ticker=ticker,
            screener_strategy=SCREENER_STRATEGY,
            entry_price=t["entry_price"],
            qty=t["qty"],
            monto_usd=t["monto_usd"],
            ml_prob=t.get("ml_prob", 0.0),
            stop_loss_pct=STOP_LOSS_PCT,
            take_profit_pct=TAKE_PROFIT_PCT,
        )

        # Registrar salida
        exit_reason = "take_profit" if t.get("won", True) else "stop_loss"
        result = record_exit(ticker, t["exit_price"], exit_reason)

        pnl = result["pnl_pct"] if result else 0
        sign = "✅" if pnl > 0 else "❌"
        print(f"{sign} {ticker:6s}  entrada=${t['entry_price']:.2f}  salida=${t['exit_price']:.2f}  P&L={pnl:+.2f}%  ({exit_reason})")

    print(f"\n✔  {len(TRADES_DE_ANOCHE)} trades registrados en data/trade_journal.json")
    print("   Abrí el dashboard → tab 📒 Historial para ver las estadísticas.")


if __name__ == "__main__":
    main()
