"""
tests/test_unit.py — Unit tests for AlphaHunter modules (no server needed).
Uses only pytest + unittest.mock.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── utils/alpaca.py: is_configured() ─────────────────────────────────────────

class TestAlpacaIsConfigured:
    """is_configured() returns True only when both API_KEY and SECRET_KEY are real."""

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "PKTEST123",
        "ALPACA_SECRET_KEY": "SKTEST456",
    })
    def test_returns_true_when_both_keys_set(self):
        import importlib
        import utils.alpaca
        importlib.reload(utils.alpaca)
        assert utils.alpaca.is_configured() is True

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "",
        "ALPACA_SECRET_KEY": "",
    })
    def test_returns_false_when_empty(self):
        import importlib
        import utils.alpaca
        importlib.reload(utils.alpaca)
        assert utils.alpaca.is_configured() is False

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "TU_API_KEY_AQUI",
        "ALPACA_SECRET_KEY": "TU_SECRET_KEY_AQUI",
    })
    def test_returns_false_when_placeholder(self):
        import importlib
        import utils.alpaca
        importlib.reload(utils.alpaca)
        assert utils.alpaca.is_configured() is False

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "PKTEST123",
        "ALPACA_SECRET_KEY": "",
    })
    def test_returns_false_when_only_api_key_set(self):
        import importlib
        import utils.alpaca
        importlib.reload(utils.alpaca)
        assert utils.alpaca.is_configured() is False

    @patch("utils.alpaca.API_KEY", "")
    @patch("utils.alpaca.SECRET_KEY", "")
    def test_returns_false_when_env_vars_missing(self):
        from utils.alpaca import is_configured
        assert is_configured() is False


# ── screener/filters.py: STRATEGIES dict ──────────────────────────────────────

class TestStrategies:
    """Each strategy is a valid key with required fields."""

    EXPECTED_STRATEGIES = {
        "momentum_alcista",
        "rebote_sobrevendido",
        "cruce_dorado",
        "exploratorio",
        "volatilidad_alta",
    }

    def test_all_five_strategies_exist(self):
        from screener.filters import STRATEGIES
        assert set(STRATEGIES.keys()) == self.EXPECTED_STRATEGIES

    def test_each_strategy_has_description(self):
        from screener.filters import STRATEGIES
        for name, strat in STRATEGIES.items():
            assert "description" in strat, f"Strategy '{name}' missing 'description'"
            assert isinstance(strat["description"], str)
            assert len(strat["description"]) > 0

    def test_each_strategy_has_filters_list(self):
        from screener.filters import STRATEGIES
        for name, strat in STRATEGIES.items():
            assert "filters" in strat, f"Strategy '{name}' missing 'filters'"
            assert isinstance(strat["filters"], list)
            assert len(strat["filters"]) > 0, f"Strategy '{name}' has empty filters"

    def test_each_filter_is_callable(self):
        from screener.filters import STRATEGIES
        for name, strat in STRATEGIES.items():
            for i, f in enumerate(strat["filters"]):
                assert callable(f), f"Filter {i} in '{name}' is not callable"


# ── ml/predictor.py: predict_screener_candidates() ───────────────────────────

class TestPredictScreenerCandidates:
    """predict_screener_candidates returns DataFrame with expected columns."""

    @patch("ml.predictor.predict_ticker")
    def test_returns_dataframe_with_prediction_columns(self, mock_predict):
        from ml.predictor import predict_screener_candidates

        mock_predict.return_value = {
            "ticker": "AAPL",
            "prob_sube": 0.72,
            "prob_baja": 0.28,
            "señal": "FUERTE_COMPRA",
            "precio_actual": 185.50,
        }

        screener_df = pd.DataFrame([{
            "ticker": "AAPL",
            "precio": 185.50,
            "rsi": 55.0,
            "vol_ratio": 2.1,
        }])

        data_dict = {"AAPL": MagicMock()}

        result = predict_screener_candidates(screener_df, data_dict, auto_train=False)

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "prob_sube" in result.columns
        assert "señal" in result.columns
        assert result.iloc[0]["ticker"] == "AAPL"

    @patch("ml.predictor.predict_ticker")
    def test_empty_screener_returns_empty_df(self, mock_predict):
        from ml.predictor import predict_screener_candidates

        screener_df = pd.DataFrame()
        data_dict = {}

        result = predict_screener_candidates(screener_df, data_dict, auto_train=False)

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ── backtesting/metrics.py: calculate_metrics() ──────────────────────────────

class TestBacktestMetrics:
    """Metric calculations with synthetic data."""

    def _make_result(self, n_days=100, initial=10000.0) -> dict:
        """Create a synthetic backtest result dict."""
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
        returns = np.random.normal(0.001, 0.015, n_days)
        equity = initial * (1 + returns).cumprod()
        equity = pd.Series(equity, index=dates)

        trades = pd.DataFrame([
            {"entry_date": dates[i], "exit_date": dates[i + 5], "pnl": 100.0, "pnl_pct": 1.0}
            for i in range(0, n_days - 5, 10)
        ])

        return {
            "equity_curve": equity,
            "trades": trades if not trades.empty else pd.DataFrame(
                columns=["entry_date", "exit_date", "pnl", "pnl_pct"]
            ),
            "initial_capital": initial,
            "final_capital": float(equity.iloc[-1]),
            "period_start": dates[0],
            "period_end": dates[-1],
        }

    def test_calculate_metrics_returns_all_keys(self):
        from backtesting.metrics import calculate_metrics

        result = self._make_result()
        metrics = calculate_metrics(result)

        expected_keys = {
            "total_return_pct", "annual_return_pct", "max_drawdown_pct",
            "sharpe_ratio", "sortino_ratio", "n_trades", "win_rate_pct",
            "avg_win_pct", "avg_loss_pct", "profit_factor", "avg_duration_days",
            "initial_capital", "final_capital", "period_days",
        }
        assert expected_keys.issubset(set(metrics.keys()))

    def test_total_return_is_correct(self):
        from backtesting.metrics import calculate_metrics

        result = self._make_result(initial=10000.0)
        metrics = calculate_metrics(result)

        expected = round((result["final_capital"] / 10000.0 - 1) * 100, 2)
        assert metrics["total_return_pct"] == expected

    def test_max_drawdown_is_negative_or_zero(self):
        from backtesting.metrics import calculate_metrics

        result = self._make_result()
        metrics = calculate_metrics(result)

        assert metrics["max_drawdown_pct"] <= 0

    def test_win_rate_with_all_winning_trades(self):
        from backtesting.metrics import calculate_metrics

        result = self._make_result()
        # Override trades: all winning
        trades = pd.DataFrame([
            {"entry_date": "2025-01-01", "exit_date": "2025-01-06",
             "pnl": 50.0, "pnl_pct": 0.5},
            {"entry_date": "2025-01-10", "exit_date": "2025-01-15",
             "pnl": 100.0, "pnl_pct": 1.0},
        ])
        result["trades"] = trades
        metrics = calculate_metrics(result)

        assert metrics["win_rate_pct"] == 100.0
        assert metrics["n_trades"] == 2

    def test_score_returns_float_between_0_and_100(self):
        from backtesting.metrics import calculate_metrics, score

        result = self._make_result()
        metrics = calculate_metrics(result)
        s = score(metrics)

        assert isinstance(s, float)
        assert 0 <= s <= 100
