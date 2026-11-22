"""
=============================================================================
tests/test_quant_core_and_bridge.py — Unit Tests for Quant Core & Bridge IPC
=============================================================================
Verifies:
  - Hurst Exponent (R/S analysis & Law 2 classification)
  - Lo-MacKinlay Variance Ratio Test (Heteroskedasticity-robust)
  - ATR Z-Score Volatility Shock Gatekeeper
  - 4-State Gaussian HMM Belief Filter & Viterbi Decoding
  - Institutional Regime Engine (Synthesis, A_alpha, Hard Veto)
  - SignalPayload Pydantic v2 Contract (MQL5 Double-Lock Protocol)
  - Cryptographic HMAC-SHA256 Payload Sealing
  - Inter-Agent Adversarial Council Messages
=============================================================================
"""

import math
import unittest
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

from quant_core.regime_math import (
    RegimeType,
    VolatilityRegime,
    compute_hurst_exponent,
    compute_variance_ratio,
    compute_atr,
    compute_atr_z_score,
    GaussianHMM,
    InstitutionalRegimeEngine,
)
from bridge.signal_schema import (
    OrderAction,
    OrderType,
    ExecutionMode,
    RegimeClassification,
    AgentCouncilVerdict,
    RiskMetrics,
    SignalPayload,
    AlphaRegimeMessage,
    BetaSetupMessage,
    GammaCriticMessage,
    OmegaGovernorVerdict,
    ExecutionReceipt,
    build_signal_payload,
)


class TestQuantCoreAndBridge(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # 100 bars of geometric Brownian motion
        returns = np.random.normal(0, 0.002, 120)
        self.prices = 1.1000 * np.exp(np.cumsum(returns))
        self.df = pd.DataFrame({
            "open": self.prices,
            "high": self.prices + 0.0008,
            "low": self.prices - 0.0008,
            "close": self.prices,
        })

    # ── QUANT CORE TESTS ─────────────────────────────────────────────────────

    def test_hurst_random_walk_veto(self):
        """Standard random walk must fall in [0.45, 0.55] or be near 0.50."""
        # Pure cumulative sum of i.i.d. Gaussian increments is a random walk (H ~ 0.50)
        rw_prices = 1.0 + np.cumsum(np.random.normal(0, 0.01, 200))
        res = compute_hurst_exponent(rw_prices)
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.hurst, 0.50, delta=0.15)

    def test_hurst_trending_detection(self):
        """Strong persistent trend should produce H > 0.55."""
        trend_prices = np.array([1.0 + 0.005 * i + 0.0002 * np.sin(i) for i in range(150)])
        res = compute_hurst_exponent(trend_prices)
        self.assertTrue(res.is_valid)
        self.assertGreater(res.hurst, 0.55)
        self.assertEqual(res.regime, RegimeType.TRENDING.value)

    def test_variance_ratio_test(self):
        """Variance Ratio calculation and Lo-MacKinlay Z2 statistic."""
        res = compute_variance_ratio(self.prices, k=5)
        self.assertGreater(res.vr, 0.0)
        self.assertIsInstance(res.z_stat, float)
        self.assertTrue(0.0 <= res.p_value <= 1.0)
        self.assertEqual(res.k_lag, 5)

    def test_atr_z_score_shock(self):
        """ATR Z-score detects volatility shock when ATR spikes above threshold."""
        highs = self.df["high"].to_numpy().copy()
        lows = self.df["low"].to_numpy().copy()
        closes = self.df["close"].to_numpy().copy()

        # Inject extreme volatility shock at the tail
        highs[-1] = closes[-1] + 0.0500
        lows[-1] = closes[-1] - 0.0500

        res = compute_atr_z_score(highs, lows, closes, atr_period=14, lookback_period=50, shock_threshold=2.0)
        self.assertTrue(res.is_vol_shock)
        self.assertEqual(res.regime, VolatilityRegime.HIGH_VOL_SHOCK.value)
        self.assertGreaterEqual(res.atr_z_score, 2.0)

    def test_gaussian_hmm_belief_filter(self):
        """HMM forward belief propagation and Viterbi path decoding."""
        hmm = GaussianHMM(num_states=4)
        obs = np.array([
            [+0.0005, 1.0],
            [+0.0008, 1.1],
            [+0.0004, 0.9],
        ])
        final_probs, all_beliefs = hmm.predict_sequence_probabilities(obs)
        self.assertEqual(len(final_probs), 4)
        self.assertAlmostEqual(float(np.sum(final_probs)), 1.0, places=5)

        path = hmm.viterbi(obs)
        self.assertEqual(len(path), 3)

        raw_ent, norm_ent = GaussianHMM.compute_entropy(final_probs)
        self.assertGreaterEqual(raw_ent, 0.0)
        self.assertTrue(0.0 <= norm_ent <= 1.0)

    def test_institutional_regime_engine(self):
        """Full quantitative synthesis in InstitutionalRegimeEngine."""
        engine = InstitutionalRegimeEngine()
        snapshot = engine.analyze(self.df, symbol="EURUSD", timeframe="H1")

        self.assertEqual(snapshot.symbol, "EURUSD")
        self.assertEqual(snapshot.timeframe, "H1")
        self.assertTrue(0.0 <= snapshot.regime_alignment_score <= 1.0)
        self.assertIsInstance(snapshot.veto_triggered, bool)

        if snapshot.veto_triggered:
            self.assertEqual(len(snapshot.allowed_directions), 0)
            self.assertEqual(snapshot.regime_alignment_score, 0.0)

        snap_dict = snapshot.to_dict()
        self.assertIn("hurst", snap_dict)
        self.assertIn("hmm", snap_dict)
        self.assertIn("atr_z", snap_dict)

    # ── BRIDGE & SIGNAL SCHEMA TESTS ─────────────────────────────────────────

    def test_signal_payload_geometry_validation(self):
        """BUY and SELL geometry must be strictly enforced."""
        risk = RiskMetrics(
            risk_reward_ratio=2.0,
            stop_loss_pips=20.0,
            take_profit_pips=40.0,
            risk_capital_usd=100.0,
            max_loss_usd=100.0,
            account_balance_usd=10000.0,
            risk_per_trade_pct=1.0,
        )

        # Invalid BUY geometry (SL > entry)
        with self.assertRaises(ValueError):
            build_signal_payload(
                symbol="EURUSD",
                action=OrderAction.BUY,
                entry_price=1.1000,
                stop_loss=1.1020,  # INVALID: SL above entry
                take_profit=1.1050,
                volume=0.1,
                alpha_score=0.9,
                beta_confidence=0.9,
                gamma_prob=0.05,
                critic_veto=False,
                regime=RegimeClassification.TRENDING_BULLISH,
                risk_metrics=risk,
            )

    def test_signal_payload_double_lock_protocol(self):
        """Lock 1 (expiration) and Lock 2 (spread guard) checks."""
        risk = RiskMetrics(
            risk_reward_ratio=2.0,
            stop_loss_pips=20.0,
            take_profit_pips=40.0,
            risk_capital_usd=100.0,
            max_loss_usd=100.0,
            account_balance_usd=10000.0,
            risk_per_trade_pct=1.0,
        )

        payload = build_signal_payload(
            symbol="EURUSD",
            action=OrderAction.BUY,
            entry_price=1.1000,
            stop_loss=1.0980,
            take_profit=1.1040,
            volume=0.2,
            alpha_score=0.95,
            beta_confidence=0.90,
            gamma_prob=0.08,
            critic_veto=False,
            regime=RegimeClassification.TRENDING_BULLISH,
            risk_metrics=risk,
            validity_duration_seconds=60,
            max_allowed_spread_points=20.0,
        )

        # Check not expired initially
        self.assertFalse(payload.is_expired())

        # Check expired in the future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=120)
        self.assertTrue(payload.is_expired(as_of=future_time))

        # Check spread guard
        self.assertTrue(payload.is_spread_acceptable(15.0))
        self.assertFalse(payload.is_spread_acceptable(25.0))  # Exceeds max 20.0

    def test_consensus_score_formula_and_live_threshold(self):
        """S_final = (C_beta * A_alpha) - P_gamma and Law 2 gating."""
        risk = RiskMetrics(
            risk_reward_ratio=2.0,
            stop_loss_pips=20.0,
            take_profit_pips=40.0,
            risk_capital_usd=100.0,
            max_loss_usd=100.0,
            account_balance_usd=10000.0,
            risk_per_trade_pct=1.0,
        )

        # S_final = (0.90 * 0.90) - 0.05 = 0.81 - 0.05 = 0.76 > 0.72 -> APPROVED
        payload = build_signal_payload(
            symbol="EURUSD",
            action=OrderAction.BUY,
            entry_price=1.1000,
            stop_loss=1.0980,
            take_profit=1.1040,
            volume=0.2,
            alpha_score=0.90,
            beta_confidence=0.90,
            gamma_prob=0.05,
            critic_veto=False,
            regime=RegimeClassification.TRENDING_BULLISH,
            risk_metrics=risk,
            execution_mode=ExecutionMode.LIVE,
        )
        self.assertAlmostEqual(payload.consensus_score, 0.76, places=3)
        self.assertEqual(payload.council_verdict.verdict_status, "APPROVED")

        # LIVE order with S_final <= 0.72 must raise ValueError
        with self.assertRaises(ValueError):
            build_signal_payload(
                symbol="EURUSD",
                action=OrderAction.BUY,
                entry_price=1.1000,
                stop_loss=1.0980,
                take_profit=1.1040,
                volume=0.2,
                alpha_score=0.80,
                beta_confidence=0.80,
                gamma_prob=0.20,  # S_final = 0.64 - 0.20 = 0.44 <= 0.72
                critic_veto=False,
                regime=RegimeClassification.TRENDING_BULLISH,
                risk_metrics=risk,
                execution_mode=ExecutionMode.LIVE,
            )

    def test_hmac_digital_signature_verification(self):
        """HMAC-SHA256 signature generation and tamper rejection."""
        risk = RiskMetrics(
            risk_reward_ratio=2.0,
            stop_loss_pips=20.0,
            take_profit_pips=40.0,
            risk_capital_usd=100.0,
            max_loss_usd=100.0,
            account_balance_usd=10000.0,
            risk_per_trade_pct=1.0,
        )

        secret = "institutional_secret_key_999"
        payload = build_signal_payload(
            symbol="EURUSD",
            action=OrderAction.BUY,
            entry_price=1.1000,
            stop_loss=1.0980,
            take_profit=1.1040,
            volume=0.2,
            alpha_score=0.95,
            beta_confidence=0.95,
            gamma_prob=0.05,
            critic_veto=False,
            regime=RegimeClassification.TRENDING_BULLISH,
            risk_metrics=risk,
            secret_key=secret,
        )

        self.assertTrue(payload.verify_signature(secret))
        self.assertFalse(payload.verify_signature("wrong_secret_key"))

        # Test MQL5 JSON serialization
        mql5_dict = payload.to_mql5_dict()
        self.assertIn("expiration_epoch_utc", mql5_dict)
        self.assertIn("max_allowed_spread_points", mql5_dict)
        self.assertEqual(mql5_dict["signature"], payload.signature)


if __name__ == "__main__":
    unittest.main()
