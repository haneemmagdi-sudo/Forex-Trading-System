"""
==============================================================================
tests/test_p1_closed_loop_and_quant.py — Verification Suite for Batch 2 (P1)
==============================================================================
Tests every P1 fix:
  1. Bailey & Lopez de Prado DSR operates on per-trade scale (noise -> not significant, edge -> significant, more trials -> lower DSR)
  2. max_drawdown_pct is true percentage over equity curve (not raw pips)
  3. WalkForwardBacktester covers 100% of post-warmup bars and avoids .bfill() look-ahead
  4. MetaLabelingClassifier computes TRUE Out-of-Sample metrics via PurgedKFold (no leakage on random noise) + joblib save/load
  5. TradeJournalDB closes live ticket loop with costs/MAE/MFE + ISO-8601 24h stale sweep + single close()
  6. End-to-end wiring checks in SafeExecutionGateway, MonitorAgent, LearningAgent, autonomous_master_orchestrator
"""

import ast
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from quant_core.labeling import StatisticalEdgeValidator
from quant_core.backtester import WalkForwardBacktester
from memory_rag.adaptive_trade_journal import TradeJournalDB, TradeVectorRecord

try:
    from quant_core.meta_model import MetaLabelingClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    MetaLabelingClassifier = None
    SKLEARN_AVAILABLE = False


class TestP1ClosedLoopAndQuant(unittest.TestCase):

    def test_01_dsr_per_trade_scale_and_trial_penalty(self):
        rng = np.random.default_rng(123)
        # Pure zero-mean noise should NOT look statistically significant
        noise = rng.normal(loc=0.0, scale=10.0, size=200)
        dsr_noise = StatisticalEdgeValidator.compute_deflated_sharpe_ratio(noise, num_trials=10)
        self.assertLess(dsr_noise, 0.95, f"Pure noise produced falsely significant DSR={dsr_noise}")

        # Genuine strong edge should produce high DSR, and increasing num_trials must strictly lower DSR
        edge = rng.normal(loc=4.0, scale=5.0, size=200)
        dsr_5 = StatisticalEdgeValidator.compute_deflated_sharpe_ratio(edge, num_trials=5)
        dsr_100 = StatisticalEdgeValidator.compute_deflated_sharpe_ratio(edge, num_trials=100)
        self.assertGreater(dsr_5, 0.95)
        self.assertLess(dsr_100, dsr_5)

    def test_02_max_drawdown_pct_is_true_percentage(self):
        # Start with 1000 pips equity, gain 50, then lose 105 -> peak=1050, trough=945 -> dd = 105/1050 = 10.0%
        pnls = [50.0, -105.0, 20.0]
        rep = StatisticalEdgeValidator.evaluate_performance(pnls, num_trials=1, initial_equity_pips=1000.0)
        self.assertAlmostEqual(rep.max_drawdown_pct, 10.0, places=2)

    def test_03_walkforward_full_coverage_and_no_bfill(self):
        rng = np.random.default_rng(7)
        n = 600
        close = 1.1000 + np.cumsum(rng.normal(0, 0.0005, n))
        df = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=n, freq="1h"),
            "open": close,
            "high": close + 0.0006,
            "low": close - 0.0006,
            "close": close,
        })
        bt = WalkForwardBacktester(num_windows=3, max_holding_bars=12)
        res = bt.run_walk_forward(df, symbol="EURUSD")
        self.assertEqual(len(res.windows), 3)
        # Final test window must reach total_bars (600), not stop at 450!
        self.assertEqual(res.windows[-1].test_indices[1], n)

        src = open(os.path.join(ROOT_DIR, "quant_core", "backtester.py"), encoding="utf-8").read()
        self.assertNotIn("df.bfill()", src)
        self.assertIn("return df.ffill().fillna(0.0)", src)

    def test_04_meta_model_structure_and_persistence_methods(self):
        src = open(os.path.join(ROOT_DIR, "quant_core", "meta_model.py"), encoding="utf-8").read()
        self.assertIn("oos_probs = np.full", src)
        self.assertIn("for train_idx, test_idx in cv.split", src)
        self.assertIn("def save(self, filepath: str)", src)
        self.assertIn("def load(cls, filepath: str)", src)

    @unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn required for MetaLabelingClassifier runtime test")
    def test_05_meta_model_true_oos_no_leakage_and_persistence(self):
        rng = np.random.default_rng(42)
        n = 160
        X_noise = rng.normal(size=(n, 6))
        y_noise = rng.integers(0, 2, size=n)

        clf_noise = MetaLabelingClassifier(calibration_method="sigmoid", n_splits=4, random_state=42)
        m_noise = clf_noise.fit(X_noise, y_noise)
        self.assertLess(m_noise.roc_auc, 0.65, f"Leaked OOS ROC-AUC on noise: {m_noise.roc_auc}")
        self.assertLess(m_noise.out_of_sample_accuracy, 65.0)
        self.assertNotEqual(m_noise.in_sample_accuracy, m_noise.out_of_sample_accuracy)

        X_sig = rng.normal(size=(n, 6))
        y_sig = ((1.5 * X_sig[:, 0] - 1.2 * X_sig[:, 1]) > 0).astype(int)
        clf_sig = MetaLabelingClassifier(calibration_method="sigmoid", n_splits=4, random_state=42)
        m_sig = clf_sig.fit(X_sig, y_sig)
        self.assertGreater(m_sig.roc_auc, 0.75)

        sample = X_sig[0].tolist()
        p_before = clf_sig.predict_probability(sample)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "meta_model.pkl")
            clf_sig.save(path)
            loaded = MetaLabelingClassifier.load(path)
            p_after = loaded.predict_probability(sample)
        self.assertAlmostEqual(p_before, p_after, places=6)

    def test_06_trade_vectors_closed_loop_and_iso8601_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_p1.db"
            journal = TradeJournalDB(db_path=db_path)

            old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            fresh_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            rec_live = TradeVectorRecord(
                timestamp_utc=fresh_ts, symbol="EURUSD", ticket=777001,
                regime_state="STRONG_TREND", setup_type="LIVE_VOTING_ENGINE",
                hurst=0.6, atr_ratio=1.1, z_score=0.5, ofi_z=0.3, spread_ratio=0.05,
                proposed_action="BUY", final_action="BUY", signal_confidence=0.8, net_score=0.8,
                sl_pips=20.0, tp1_pips=40.0, risk_percent=1.0, outcome="OPEN", execution_mode="LIVE",
            )
            rec_stale = TradeVectorRecord(
                timestamp_utc=old_ts, symbol="EURUSD", ticket=777002,
                regime_state="STRONG_TREND", setup_type="LIVE_VOTING_ENGINE",
                hurst=0.6, atr_ratio=1.1, z_score=0.5, ofi_z=0.3, spread_ratio=0.05,
                proposed_action="BUY", final_action="BUY", signal_confidence=0.8, net_score=0.8,
                sl_pips=20.0, tp1_pips=40.0, risk_percent=1.0, outcome="OPEN", execution_mode="LIVE",
            )
            journal.insert_record(rec_live)
            journal.insert_record(rec_stale)

            ok = journal.update_outcome_by_ticket(
                ticket=777001, pnl_pips=18.5, outcome="WIN",
                spread_cost=1.1, commission=-0.7, swap=-0.2, mae_pips=-4.2, mfe_pips=22.0,
            )
            self.assertTrue(ok)

            swept = journal.sweep_stale_open_records(max_age_hours=24.0)
            self.assertEqual(swept, 1)

            conn = journal._get_conn()
            r1 = conn.execute("SELECT outcome, commission, swap, mae_pips, mfe_pips FROM trade_vectors WHERE ticket=777001").fetchone()
            r2 = conn.execute("SELECT outcome FROM trade_vectors WHERE ticket=777002").fetchone()
            self.assertEqual(r1["outcome"], "WIN")
            self.assertAlmostEqual(r1["commission"], -0.7)
            self.assertAlmostEqual(r1["mae_pips"], -4.2)
            self.assertEqual(r2["outcome"], "STALE_CLOSED")
            journal.close()

        src = open(os.path.join(ROOT_DIR, "memory_rag", "adaptive_trade_journal.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TradeJournalDB":
                close_methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "close"]
                self.assertEqual(len(close_methods), 1)

    def test_07_end_to_end_wiring_in_gateway_monitor_learning_orchestrator(self):
        gw_src = open(os.path.join(BACKEND_DIR, "core", "safe_execution_gateway.py"), encoding="utf-8").read()
        mon_src = open(os.path.join(BACKEND_DIR, "agents", "monitor_agent.py"), encoding="utf-8").read()
        lrn_src = open(os.path.join(BACKEND_DIR, "agents", "learning_agent.py"), encoding="utf-8").read()
        amo_src = open(os.path.join(ROOT_DIR, "autonomous_master_orchestrator.py"), encoding="utf-8").read()

        self.assertIn("self._record_trade_vector(", gw_src)
        self.assertIn("_excursion_tracker", mon_src)
        self.assertIn('"commission": deal_commission', mon_src)
        self.assertIn("hedge_sl", mon_src)
        self.assertIn("sweep_stale_open_records", lrn_src)
        self.assertIn('mae_pips=float(data.get("mae_pips")', lrn_src)
        self.assertIn("self.recorder._db.update_outcome_by_ticket(", amo_src)
        self.assertIn("sweep_stale_open_records", amo_src)


if __name__ == "__main__":
    unittest.main()
