"""
utils/auto_trader.py — Trading automático basado en screener + estrategias
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from datetime import datetime
from screener.runner import run_screener
from utils.strategy_validator import find_matching_strategies
from utils.alpaca import place_order as alpaca_place_order


class AutoTradeConfig:
    """Configuración para trading automático."""

    def __init__(
        self,
        strategy: str = "momentum_alcista",
        amount_usd_per_trade: float = 500.0,
        max_positions: int = 5,
        sl_percent: float = 5.0,
        tp_percent: float = 20.0,
        period: str = "1y",
        require_all_matching: bool = False,
    ):
        self.strategy = strategy
        self.amount_usd_per_trade = amount_usd_per_trade
        self.max_positions = max_positions
        self.sl_percent = sl_percent
        self.tp_percent = tp_percent
        self.period = period
        self.require_all_matching = require_all_matching


class AutoTrader:
    """Ejecuta trading automático."""

    def __init__(self, config: AutoTradeConfig):
        self.config = config
        self.trades = []
        self.errors = []

    def _get_current_positions(self) -> Dict[str, Dict]:
        """Obtiene posiciones actuales de Alpaca."""
        try:
            from utils.alpaca import get_positions
            positions = get_positions()
            return {p["symbol"]: p for p in positions}
        except Exception as e:
            self.errors.append(f"Error obteniendo posiciones: {str(e)}")
            return {}

    def run_screener_and_trade(self) -> Dict:
        """Ejecuta screener, valida estrategias y coloca órdenes."""
        # Ejecutar screener
        try:
            screener_results = run_screener(
                strategy=self.config.strategy,
                period=self.config.period,
                include_fundamentals=True
            )

            if screener_results is None or screener_results.empty:
                return {
                    "status": "no_candidates",
                    "message": f"No hay candidatos para {self.config.strategy}",
                    "trades_placed": [],
                    "config": vars(self.config),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error en screener: {str(e)}",
                "trades_placed": [],
                "errors": [str(e)],
            }

        # Obtener posiciones actuales
        current_positions = self._get_current_positions()
        available_slots = self.config.max_positions - len(current_positions)

        if available_slots <= 0:
            return {
                "status": "max_positions_reached",
                "message": f"Máximo de posiciones alcanzado ({self.config.max_positions})",
                "trades_placed": [],
            }

        # Validar candidatos
        candidates = []
        for _, row in screener_results.iterrows():
            ticker = row.get("ticker", "")
            if ticker and ticker not in current_positions:
                candidates.append({"ticker": ticker, "screener_strategy": self.config.strategy})

        candidates = candidates[:available_slots]

        # Colocar órdenes
        trades_placed = []
        for candidate in candidates:
            ticker = candidate["ticker"]
            try:
                qty = self._calculate_qty(ticker)
                order_result = alpaca_place_order(
                    symbol=ticker,
                    qty=qty,
                    side="buy",
                    order_type="market",
                    take_profit_price=self._calculate_tp(ticker),
                    stop_loss_price=self._calculate_sl(ticker),
                )

                trades_placed.append({
                    "symbol": ticker,
                    "qty": qty,
                    "order_id": order_result.get("id"),
                    "status": order_result.get("status"),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            except Exception as e:
                self.errors.append(f"Error en {ticker}: {str(e)}")

        return {
            "status": "success" if trades_placed else "no_trades",
            "trades_placed": trades_placed,
            "total_errors": len(self.errors),
            "errors": self.errors[:5],  # Primeros 5 errores
            "config": {
                "strategy": self.config.strategy,
                "amount_per_trade": self.config.amount_usd_per_trade,
                "max_positions": self.config.max_positions,
            }
        }

    def _calculate_qty(self, symbol: str) -> float:
        try:
            import yfinance as yf
            price = float(yf.Ticker(symbol).fast_info.last_price)
            return round(self.config.amount_usd_per_trade / price, 4)
        except:
            return 0.0

    def _calculate_sl(self, symbol: str) -> float:
        try:
            import yfinance as yf
            price = float(yf.Ticker(symbol).fast_info.last_price)
            return round(price * (1 - self.config.sl_percent / 100), 2)
        except:
            return 0.0

    def _calculate_tp(self, symbol: str) -> float:
        try:
            import yfinance as yf
            price = float(yf.Ticker(symbol).fast_info.last_price)
            return round(price * (1 + self.config.tp_percent / 100), 2)
        except:
            return 0.0


def run_auto_trade(config: AutoTradeConfig) -> Dict:
    """Helper para ejecutar auto-trading."""
    trader = AutoTrader(config)
    return trader.run_screener_and_trade()
