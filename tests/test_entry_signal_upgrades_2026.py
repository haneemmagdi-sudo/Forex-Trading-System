"""
tests/test_entry_signal_upgrades_2026.py — اختبارات ترقيات إشارة الدخول (2026 v2)
=================================================================================
تغطي التطويرات فوق P3/P4/P5:
  1. محرك التصويت: سقوف المحاور المتكيفة مع FSM + إنتروبيا التشتت + حارس التعارض (Anti-Groupthink).
  2. BetaOrderFlowAgent (تحت council/): فلترة إزاحة FVG مقابل ATR + حارس تدفق OFI المعاكس المستمر.
  3. AdaptiveTrapMemory: التضائل الزمني الأسي (FinMem Time-Decay) + نسبة الفوز الخاصة بكل نظام + الذاكرة التقابلية للرابحين.
  4. GammaRedTeamCritic: تشابه Top-K المرجح بالتضائل + التخفيف التقابلي للرابحين + قاطع الدائرة المزدوج (صدمة التقلب + انهيار ثقة النظام).
  5. OmegaRiskGovernor: دمج الاحتمال المعايَر (Calibrated Probability Fusion) + عتبات التكيف حسب أداء النظام الحالي.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.voting_engine import VotingEngine
from core.fsm_engine import FSMResult, Regime
from council.alpha_regime_agent import RegimeOutput, RegimeState
from council.beta_orderflow_agent import BetaOrderFlowAgent, OrderFlowProposal
from council.gamma_redteam_critic import GammaRedTeamCritic, CriticAssessment
from council.omega_risk_governor import OmegaRiskGovernor, AdaptiveThresholdEngine
from quant_core.orderflow import OFIResult
from memory_rag.adaptive_trade_journal import (
    TradeJournalDB,
    AdaptiveTrapMemory,
    TradeVectorRecord,
)


def _mock_iv(
    close=1.1050, ema=1.1000, ema_angle=5.0,
    ha_bull=True, ha_bear=False,
    macd=0.002, macd_sig=0.001, macd_hist=0.001,
    rsi=60.0, adx=30.0, di_p=28.0, di_m=12.0,
    senkou_a=1.0980, senkou_b=1.0990, tenkan=1.1030, kijun=1.1010,
    smc_bull_ob=False, smc_bear_ob=False,
    momentum=103.5, atr=0.0010,
    bb_upper=1.1100, bb_lower=1.0900,
):
    return SimpleNamespace(
        close=close, ema=ema, ema_angle=ema_angle,
        ha_bullish=ha_bull, ha_bearish=ha_bear,
        ha_open=1.1020, ha_close=1.1050, ha_low=1.1020, ha_high=1.1055,
        macd=macd, macd_signal=macd_sig, macd_hist=macd_hist,
        rsi=rsi, adx=adx, di_plus=di_p, di_minus=di_m,
        senkou_a=senkou_a, senkou_b=senkou_b, tenkan=tenkan, kijun=kijun,
        smc_bullish_ob=smc_bull_ob, smc_bullish_fvg=False,
        smc_bearish_ob=smc_bear_ob, smc_bearish_fvg=False,
        momentum=momentum, atr=atr,
        bb_upper=bb_upper, bb_lower=bb_lower,
    )


def _mock_fsm(regime=Regime.STRONG_TREND, allowed=True):
    return SimpleNamespace(
        regime=regime,
        trade_allowed=allowed,
        reason="test",
        vote_weights={k: 1.0 for k in ("ema", "ha", "macd", "rsi", "adx", "ichi", "smc", "momentum", "st")},
    )


class TestVotingEngine2026V2(unittest.TestCase):
    def test_regime_dynamic_pillar_caps_preserve_total_weight(self):
        ve = VotingEngine()
        iv = _mock_iv(smc_bull_ob=True)
        res_trend = ve.vote(iv, _mock_fsm(Regime.STRONG_TREND))
        res_lowvol = ve.vote(iv, _mock_fsm(Regime.LOW_VOL_RANGE))

        self.assertAlmostEqual(res_trend.total_weight, 7.5, places=3)
        self.assertAlmostEqual(res_lowvol.total_weight, 7.5, places=3)
        # في STRONG_TREND سقف الاتجاه أعلى من LOW_VOL، بينما في LOW_VOL سقف الهيكل أعلى
        self.assertGreater(res_trend.pillar_scores["trend"]["cap"], res_lowvol.pillar_scores["trend"]["cap"])
        self.assertGreater(res_lowvol.pillar_scores["structure"]["cap"], res_trend.pillar_scores["structure"]["cap"])

    def test_conflict_guard_penalizes_confidence_and_tracks_entropy(self):
        ve = VotingEngine()
        # اتجاه + قوة صاعدان (BUY) لكن الهيكل SMC هابط بقوة (opposing_pillars=1) والزخم محايد
        iv_conflict = _mock_iv(
            macd=0.0, macd_sig=0.0, macd_hist=0.0,
            rsi=50.0, momentum=100.0,
            smc_bull_ob=False, smc_bear_ob=True,
        )
        iv_clean = _mock_iv(
            macd=0.0, macd_sig=0.0, macd_hist=0.0,
            rsi=50.0, momentum=100.0,
            smc_bull_ob=False, smc_bear_ob=False,
        )
        res_conf = ve.vote(iv_conflict, _mock_fsm(Regime.STRONG_TREND))
        res_clean = ve.vote(iv_clean, _mock_fsm(Regime.STRONG_TREND))

        self.assertEqual(res_conf.opposing_pillars, 1)
        self.assertGreater(res_conf.pillar_entropy, 0.0)
        self.assertLess(res_conf.confidence, res_clean.confidence)
        self.assertFalse(res_conf.signal_strong)


class TestBetaOrderFlow2026V2(unittest.TestCase):
    def _build_fvg_df(self, gap_size=0.0010):
        rows = []
        base = 1.1000
        for i in range(30):
            rows.append({
                "open": base, "high": base + 0.0005, "low": base - 0.0005,
                "close": base + 0.0002, "tick_volume": 100.0,
            })
            base += 0.0001
        # اصنع فجوة صاعدة غير مملوءة بحجم gap_size بين الشمعة -4 و -2
        c1_h = rows[-4]["high"]
        rows[-3]["low"] = c1_h + gap_size * 0.2
        rows[-3]["high"] = c1_h + gap_size + 0.0006
        rows[-3]["close"] = rows[-3]["high"] - 0.0001
        rows[-2]["low"] = c1_h + gap_size
        rows[-2]["high"] = c1_h + gap_size + 0.0008
        rows[-2]["close"] = c1_h + gap_size + 0.0005
        rows[-1]["low"] = c1_h + gap_size + 0.0002
        rows[-1]["high"] = c1_h + gap_size + 0.0010
        rows[-1]["close"] = c1_h + gap_size + 0.0007
        return pd.DataFrame(rows)

    def test_fvg_displacement_filter_rejects_micro_noise_gap(self):
        df_tiny = self._build_fvg_df(gap_size=0.00005)
        df_large = self._build_fvg_df(gap_size=0.00120)
        self.assertIsNone(BetaOrderFlowAgent.detect_fvg(df_tiny, min_gap_size=0.0003)["bullish_fvg"])
        fvg_ok = BetaOrderFlowAgent.detect_fvg(df_large, min_gap_size=0.0003)["bullish_fvg"]
        self.assertIsNotNone(fvg_ok)
        self.assertIn("age_bars", fvg_ok)
        self.assertGreaterEqual(fvg_ok["gap_size"], 0.0010)

    def test_severe_counter_flow_ofi_sharply_reduces_confidence(self):
        agent = BetaOrderFlowAgent(point_value=0.00001, use_live_mt5=False)
        df = self._build_fvg_df(gap_size=0.0012)
        regime = RegimeOutput(
            symbol="EURUSD",
            regime_state=RegimeState.TRENDING_LOW_VOL,
            regime_confidence=0.88,
            hurst_exponent=0.65,
            atr_ratio=1.1,
            atr_points=100.0,
            rolling_z_score=0.8,
            directional_bias="BULLISH",
            rationale="test",
            diagnostics={},
        )
        now = datetime(2026, 11, 22, 13, 0, tzinfo=timezone.utc)
        ofi_aligned = OFIResult(symbol="EURUSD", ofi_z_score=1.6, cumulative_delta=100.0, buy_volume_pct=0.72, sell_volume_pct=0.28, tick_count_used=120, source="SIMULATED")
        ofi_counter = OFIResult(symbol="EURUSD", ofi_z_score=-2.4, cumulative_delta=-180.0, buy_volume_pct=0.22, sell_volume_pct=0.78, tick_count_used=120, source="SIMULATED")

        p_aligned = agent._propose_sync("EURUSD", df, regime, now, ofi_aligned)
        p_counter = agent._propose_sync("EURUSD", df, regime, now, ofi_counter)

        self.assertEqual(p_aligned.proposed_action, "LIMIT_BUY")
        self.assertTrue(p_counter.metadata.get("ofi_counter_flow"))
        self.assertGreater(p_aligned.signal_confidence - p_counter.signal_confidence, 0.15)


class TestEpisodicMemoryAndGamma2026V2(unittest.TestCase):
    def _make_record(self, ts_utc, regime, outcome, pnl_pips, vec):
        return TradeVectorRecord(
            timestamp_utc=ts_utc, symbol="EURUSD", ticket=None,
            regime_state=regime, setup_type="TREND_FVG_PULLBACK_LONG",
            hurst=vec[0], atr_ratio=vec[1], z_score=vec[2], ofi_z=vec[3], spread_ratio=vec[4],
            proposed_action="LIMIT_BUY", final_action="LIMIT_BUY",
            signal_confidence=0.85, net_score=0.78, sl_pips=15.0, tp1_pips=30.0, risk_percent=0.5,
            pnl_pips=pnl_pips, outcome=outcome, execution_mode="LIVE",
        )

    def test_time_decay_weights_and_regime_win_rate(self):
        with tempfile.TemporaryDirectory() as td:
            db = TradeJournalDB(Path(td) / "test.db")
            now = datetime.now(timezone.utc)
            recent_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            old_ts = (now - timedelta(days=56)).strftime("%Y-%m-%dT%H:%M:%SZ")

            db.insert_record(self._make_record(recent_ts, "TRENDING_LOW_VOL", "LOSS", -20.0, [0.62, 1.2, 1.5, -1.0, 0.08]))
            db.insert_record(self._make_record(old_ts, "TRENDING_LOW_VOL", "LOSS", -20.0, [0.62, 1.2, 1.5, -1.0, 0.08]))
            db.insert_record(self._make_record(recent_ts, "TRENDING_LOW_VOL", "WIN", 30.0, [0.68, 1.0, 0.6, 1.4, 0.05]))
            db.insert_record(self._make_record(recent_ts, "MEAN_REVERTING_RANGE", "WIN", 25.0, [0.38, 0.9, 1.8, 0.9, 0.06]))

            vecs, weights = db.fetch_losing_vectors_with_weights(regime_state="TRENDING_LOW_VOL", half_life_days=14.0)
            self.assertEqual(len(vecs), 2)
            # الخسارة الحديثة وزنها أعلى بكثير من الخسارة التي مضى عليها 56 يوماً (4 أعمار نصف)
            self.assertGreater(weights[0], weights[1] * 5.0)

            wr_trend = db.recent_win_rate(last_n=20, regime_state="TRENDING_LOW_VOL")
            wr_range = db.recent_win_rate(last_n=20, regime_state="MEAN_REVERTING_RANGE")
            self.assertAlmostEqual(wr_trend, 1.0 / 3.0, places=3)
            self.assertAlmostEqual(wr_range, 1.0, places=3)
            db.close()

    def test_dual_memory_circuit_breaker_on_low_regime_confidence(self):
        critic = GammaRedTeamCritic()
        proposal = OrderFlowProposal(
            symbol="EURUSD", proposed_action="LIMIT_BUY", signal_confidence=0.86,
            entry_price=1.1000, stop_loss=1.0985, take_profit_1=1.1030, take_profit_2=1.1050,
            setup_type="TREND_FVG_PULLBACK_LONG", liquidity_sweep_detected=False,
            ofi_z_score=1.2, ofi_buy_pct=0.65, ofi_source="SIMULATED",
            killzone_active=True, rationale="test", metadata={},
        )
        # نظام غير صدمي لكنه يعاني انهياراً في ثقة التصنيف (< 0.45)
        regime_uncertain = RegimeOutput(
            symbol="EURUSD", regime_state=RegimeState.TRENDING_LOW_VOL,
            regime_confidence=0.35, hurst_exponent=0.52, atr_ratio=1.1,
            atr_points=100.0, rolling_z_score=0.5, directional_bias="BULLISH", rationale="transition", diagnostics={},
        )
        df_h1 = pd.DataFrame({"high": [1.1200] * 15, "low": [1.0800] * 15})
        res = critic._audit_sync(proposal, regime_uncertain, df_h1, current_spread_points=8.0)

        self.assertTrue(res.memory_circuit_breaker_active)
        self.assertEqual(res.episodic_similarity_loss_rate, 0.0)
        self.assertTrue(any("MEMORY_CIRCUIT_BREAKER" in f for f in res.fatal_flaws))

    def test_contrastive_win_relief_softens_trap_penalty(self):
        with tempfile.TemporaryDirectory() as td:
            db = TradeJournalDB(Path(td) / "contrastive.db")
            now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            # إدخال 5 خسائر و5 صفقات رابحة قريبة من نفس البصمة في TRENDING_LOW_VOL
            for i in range(5):
                db.insert_record(self._make_record(now_ts, "TRENDING_LOW_VOL", "LOSS", -15.0, [0.60 + i * 0.01, 1.2, 1.1, 0.9, 0.06]))
                db.insert_record(self._make_record(now_ts, "TRENDING_LOW_VOL", "WIN", 35.0, [0.62 + i * 0.005, 1.15, 1.0, 1.1, 0.06]))
            mem = AdaptiveTrapMemory(db)
            critic = GammaRedTeamCritic(adaptive_memory=mem)
            proposal = OrderFlowProposal(
                symbol="EURUSD", proposed_action="LIMIT_BUY", signal_confidence=0.88,
                entry_price=1.1000, stop_loss=1.0985, take_profit_1=1.1030, take_profit_2=1.1050,
                setup_type="TREND_FVG_PULLBACK_LONG", liquidity_sweep_detected=False,
                ofi_z_score=1.1, ofi_buy_pct=0.68, ofi_source="SIMULATED",
                killzone_active=True, rationale="test", metadata={},
            )
            regime = RegimeOutput(
                symbol="EURUSD", regime_state=RegimeState.TRENDING_LOW_VOL,
                regime_confidence=0.90, hurst_exponent=0.63, atr_ratio=1.15,
                atr_points=100.0, rolling_z_score=1.0, directional_bias="BULLISH", rationale="trend", diagnostics={},
            )
            df_h1 = pd.DataFrame({"high": [1.1200] * 15, "low": [1.0800] * 15})
            res = critic._audit_sync(proposal, regime, df_h1, current_spread_points=6.0)
            self.assertGreater(res.contrastive_win_similarity, 0.70)
            db.close()


class TestOmegaGovernor2026V2(unittest.TestCase):
    def _sample_inputs(self):
        regime = RegimeOutput(
            symbol="EURUSD", regime_state=RegimeState.TRENDING_LOW_VOL,
            regime_confidence=0.92, hurst_exponent=0.66, atr_ratio=1.1,
            atr_points=100.0, rolling_z_score=0.7, directional_bias="BULLISH", rationale="trend", diagnostics={},
        )
        proposal = OrderFlowProposal(
            symbol="EURUSD", proposed_action="LIMIT_BUY", signal_confidence=0.90,
            entry_price=1.1000, stop_loss=1.0985, take_profit_1=1.1030, take_profit_2=1.1050,
            setup_type="TREND_FVG_PULLBACK_LONG", liquidity_sweep_detected=True,
            ofi_z_score=1.4, ofi_buy_pct=0.72, ofi_source="SIMULATED",
            killzone_active=True, rationale="test", metadata={},
        )
        critic = CriticAssessment(
            symbol="EURUSD", critic_veto_triggered=False, failure_probability_score=0.05,
            fatal_flaws=[], critic_notes="clean", spread_to_atr_ratio=0.06,
            episodic_similarity_loss_rate=0.05,
        )
        return regime, proposal, critic

    def test_calibrated_probability_fusion_blocks_overconfident_heuristic(self):
        gov = OmegaRiskGovernor()
        regime, proposal, critic = self._sample_inputs()

        # بدون معايرة Meta-Model: الدرجة الهيكلية 0.90*0.92 - 0.05 = 0.778 >= 0.72 → قبول
        res_uncal = gov.adjudicate(regime, proposal, critic)
        self.assertEqual(res_uncal.action, "LIMIT_BUY")

        # مع Meta-Model معايَر يشير إلى احتمال نجاح منخفض (0.48): الدمج يمنع الثقة المفرطة → STAND_DOWN
        res_cal_low = gov.adjudicate(regime, proposal, critic, calibrated_p_win=0.48)
        self.assertEqual(res_cal_low.action, "STAND_DOWN")
        self.assertLess(res_cal_low.confidence_score, res_uncal.confidence_score)

    def test_adaptive_threshold_tightens_on_low_regime_win_rate_and_flaws(self):
        eng = AdaptiveThresholdEngine()
        regime, _, _ = self._sample_inputs()
        base = eng.compute(regime, rolling_win_rate=0.55)
        tight = eng.compute(regime, rolling_win_rate=0.55, regime_win_rate=0.35, critic_flaw_count=2)
        self.assertAlmostEqual(tight - base, 0.08, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
