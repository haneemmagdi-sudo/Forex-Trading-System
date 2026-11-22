"""
==============================================================================
tests/test_phase2_quant_measurement.py — Unit Tests for Quantitative Measurement
==============================================================================
Verifies Phase 2 items from IMPROVEMENT_PLAN.md:
  1. Triple-Barrier labeling at candle level with ATR boundaries
  2. Realistic spread and cost deduction
  3. Deflated Sharpe Ratio (DSR) & Statistical Significance
  4. Monte Carlo Random Entry Baseline comparison
  5. Rejected signal logging with complete indicator feature vectors
"""

import unittest
import numpy as np
import pandas as pd

from quant_core.labeling import TripleBarrierLabeler, StatisticalEdgeValidator, BarrierEvent
from backend.models.database import Signal, SignalDirection, FSMRegime


class TestPhase2QuantMeasurement(unittest.TestCase):

    def setUp(self):
        # Create a synthetic OHLCV dataframe with 100 bars
        np.random.seed(42)
        n = 100
        close = 1.1000 + np.cumsum(np.random.normal(0, 0.0005, size=n))
        high = close + np.random.uniform(0.0001, 0.0005, size=n)
        low = close - np.random.uniform(0.0001, 0.0005, size=n)
        open_p = close + np.random.normal(0, 0.0002, size=n)
        volume = np.random.uniform(100, 1000, size=n)

        self.df = pd.DataFrame({
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "atr": np.full(n, 0.0010),
        })

    def test_triple_barrier_labeler(self):
        """Test triple-barrier labeling generates events with valid boundaries."""
        labeler = TripleBarrierLabeler(pt_atr_mult=1.5, sl_atr_mult=1.0, max_holding_bars=10, cost_pips=1.5)
        events = labeler.label_candle_series(self.df, symbol="EURUSD", direction=1)

        self.assertGreater(len(events), 50)
        first_ev = events[0]
        self.assertIsInstance(first_ev, BarrierEvent)
        self.assertIn(first_ev.barrier_hit, ("UPPER", "LOWER", "VERTICAL"))
        self.assertIn(first_ev.label, (-1, 0, 1))
        self.assertGreaterEqual(first_ev.holding_bars, 1)
        self.assertLessEqual(first_ev.holding_bars, 10)

    def test_statistical_edge_validator(self):
        """Test Deflated Sharpe Ratio and Monte Carlo random baseline."""
        # A series of profitable trades with an edge
        np.random.seed(42)
        winning_trades = np.random.normal(loc=4.5, scale=5.0, size=150)
        report = StatisticalEdgeValidator.evaluate_performance(list(winning_trades), num_trials=5)

        self.assertEqual(report.total_trades, 150)
        self.assertGreater(report.win_rate, 60.0)
        self.assertGreater(report.net_expectancy_pips, 0.0)
        self.assertGreater(report.annualized_sharpe, 1.0)
        self.assertGreater(report.deflated_sharpe_ratio, 0.8)
        self.assertGreater(report.edge_over_random_pips, 0.0)

    def test_signal_rejection_reason_field(self):
        """Test that Signal model properly supports rejection_reason."""
        sig = Signal(
            symbol="EURUSD",
            direction=SignalDirection.BUY,
            fsm_regime=FSMRegime.SLOW_TREND,
            buy_score=4.0,
            sell_score=1.0,
            total_weight=5.0,
            confidence=80.0,
            executed=False,
            rejection_reason="SPREAD_TOO_HIGH_3.5",
            ema_value=1.1020,
            rsi_value=55.4,
            price=1.1015,
        )
        sig_dict = sig.to_dict()
        self.assertFalse(sig_dict["executed"])
        self.assertEqual(sig_dict["rejection_reason"], "SPREAD_TOO_HIGH_3.5")


if __name__ == "__main__":
    unittest.main()
