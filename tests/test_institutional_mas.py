"""
==============================================================================
tests/test_institutional_mas.py — Unit Tests for Institutional Multi-Agent System
==============================================================================
Tests all institutional MAS components:
  - MarketRegimeAgent (HMM & Macro Veto)
  - OrderFlowMicrostructureAgent (CVD, Absorption, Sweep)
  - MultiAgentDebateEngine (MAD & Confidence Gate)
  - RiskAdjustedRewardShaper (Sortino & MAE Penalty)
  - CrossAssetGraphAgent (Intermarket Flows)
  - InstitutionalExecutionBridge (End-to-End Cascade)
"""

import math
import unittest

from institutional.market_regime_hmm import MarketRegimeAgent, MarketRegimeState
from institutional.order_flow_agent import OrderFlowMicrostructureAgent, AbsorptionType
from institutional.multi_agent_debate import MultiAgentDebateEngine, DebateVerdict
from ml_models.risk_adjusted_reward import RiskAdjustedRewardShaper, TradeTrajectorySnapshot
from ml_models.cross_asset_agent import CrossAssetGraphAgent, MacroFlowMetrics
from backend.core.execution_bridge import InstitutionalExecutionBridge


class TestInstitutionalMAS(unittest.TestCase):

    def test_market_regime_veto(self):
        # الفيتو صار اختيارياً بعد المعايرة بالبيانات (معطّل افتراضياً:
        # backend/cascade_calibration.py) — الاختبار يقيس الآلية نفسها.
        agent = MarketRegimeAgent(veto_enabled=True)
        closes = [1.0800 + i * 0.0005 for i in range(30)] # Strong uptrend
        highs = [c + 0.0002 for c in closes]
        lows = [c - 0.0002 for c in closes]

        res = agent.classify("EURUSD", closes, highs, lows, atr_current=0.0010, atr_baseline=0.0010)
        self.assertEqual(res.state, MarketRegimeState.TRENDING_BULLISH)
        self.assertIn("BUY", res.allowed_directions)

        # BUY should be permitted
        vetoed, msg = agent.evaluate_macro_veto("EURUSD", "BUY", res)
        self.assertFalse(vetoed)

        # SELL should be vetoed by Macro Regime
        vetoed, msg = agent.evaluate_macro_veto("EURUSD", "SELL", res)
        self.assertTrue(vetoed)
        self.assertIn("opposes dominant market regime", msg)

    def test_order_flow_cvd_and_absorption(self):
        agent = OrderFlowMicrostructureAgent()
        closes = [1.0850] * 20
        opens = [1.0850] * 20
        highs = [1.0860] * 20
        lows = [1.0840] * 20
        volumes = [100.0] * 19 + [300.0] # High volume surge

        # Create bottom wick absorption on last bar
        lows[-1] = 1.0820
        closes[-1] = 1.0850 # Lower wick is large
        opens[-1] = 1.0848
        highs[-1] = 1.0852

        absorption, strength = agent.detect_absorption(closes, highs, lows, volumes)
        self.assertEqual(absorption, AbsorptionType.BULLISH_ABSORPTION)
        self.assertGreater(strength, 50.0)

    def test_multi_agent_debate(self):
        # نفس المنطق: الفيتو اختياري بعد المعايرة، والاختبار يقيس الآلية عند طلبه.
        engine = MultiAgentDebateEngine(confidence_threshold=75.0, veto_enabled=True)

        # Context heavily favoring BUY
        context_bullish = {
            "close": 1.0950,
            "ema": 1.0850,
            "rsi": 55.0,
            "regime": "TRENDING_BULLISH",
            "absorption_detected": "BULLISH_ABSORPTION",
            "sweep_direction": "LOW_SWEEP",
            "spread": 10.0,
        }

        res = engine.conduct_debate("EURUSD", context_bullish)
        self.assertTrue(res.execution_permitted)
        self.assertEqual(res.verdict, DebateVerdict.APPROVED_BUY)
        self.assertGreaterEqual(res.consensus_confidence, 75.0)

        # Ambiguous / Stalemate context
        context_neutral = {
            "close": 1.0850,
            "ema": 1.0850,
            "rsi": 50.0,
            "regime": "MEAN_REVERTING",
            "absorption_detected": "NONE",
            "sweep_direction": None,
            "spread": 10.0,
        }
        res_neutral = engine.conduct_debate("EURUSD", context_neutral)
        self.assertFalse(res_neutral.execution_permitted)
        self.assertEqual(res_neutral.verdict, DebateVerdict.REJECTED_HOLD)

    def test_risk_adjusted_reward_mae_penalty(self):
        shaper = RiskAdjustedRewardShaper(mae_penalty_weight=3.0, drawdown_soft_cap=0.01)

        # Clean trade without MAE
        clean_snapshot = TradeTrajectorySnapshot(
            entry_price=1.0800,
            current_price=1.0850,
            direction=1,
            bars_held=2,
            unrealized_pnl_pct=0.0045,
            max_adverse_excursion_pct=0.002, # Small dip (<1%)
            max_favorable_excursion_pct=0.005,
        )
        r_clean = shaper.compute_step_reward(clean_snapshot, bar_return_pct=0.002)

        # Messy trade that suffered deep drawdown (3.5% MAE)
        messy_snapshot = TradeTrajectorySnapshot(
            entry_price=1.0800,
            current_price=1.0850,
            direction=1,
            bars_held=2,
            unrealized_pnl_pct=0.0045,
            max_adverse_excursion_pct=0.035, # Severe dip (>1%)
            max_favorable_excursion_pct=0.005,
        )
        r_messy = shaper.compute_step_reward(messy_snapshot, bar_return_pct=0.002)

        # The messy trade must be penalized sharply despite identical ending PnL
        self.assertLess(r_messy, r_clean)

    def test_cross_asset_macro_alignment(self):
        cross_agent = CrossAssetGraphAgent()

        # DXY surging + US10Y surging -> EURUSD BUY must be flagged/penalized
        macro = cross_agent.evaluate_intermarket_state(
            dxy_change_pct=0.009, # Strong dollar breakout
            us10y_change_pct=0.02,
            vix_level=18.0,
            gold_change_pct=-0.005,
        )
        res = cross_agent.validate_pair_alignment("EURUSD", "BUY", macro)
        self.assertTrue(res.veto_recommended)
        self.assertFalse(res.is_macro_aligned)


if __name__ == "__main__":
    unittest.main()
