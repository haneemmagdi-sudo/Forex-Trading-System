"""
tests/test_learning_champion_rollback.py — اختبارات الدفعة الأولى (2026)
=========================================================================
تتحقق من:
  1. ExponentialAttributionBandit: التقليص الإحصائي للعينات الصغيرة والحدود الآمنة.
  2. ChampionChallengerManager: تقييد الخطوة (±0.25)، الترقية بعد Probation، التراجع التلقائي
     المبكر (4 خسائر متتالية)، التراجع عند تدهور الأداء، فترة التهدئة، والحفظ الذري على القرص.
  3. LearningAgent: الميزات الثماني المستقرة عبر الأزواج (EURUSD vs XAUUSD)، وربط
     التراجع التلقائي فعلياً مع VotingEngine و SignalBus (champion_rollback).
  4. MarketAnalystAgent: تطبيق _regime_confidence_boost فعلياً لمنع الإشارات منخفضة الثقة.
"""
import asyncio
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.champion_challenger import ChampionChallengerManager, ExponentialAttributionBandit
from core.voting_engine import VotingEngine
from core.signal_bus import BusMessage
from agents.learning_agent import LearningAgent
from agents.market_analyst import MarketAnalystAgent


class TestExponentialAttributionBandit(unittest.TestCase):
    def test_empirical_bayes_shrinkage_damps_small_samples(self):
        small_sample = {
            "regime_stats": {"STRONG_TREND": {"trades": 2, "wins": 2, "losses": 0, "profit": 20.0}},
            "high_conf_wr": 60.0,
        }
        large_sample = {
            "regime_stats": {"STRONG_TREND": {"trades": 40, "wins": 36, "losses": 4, "profit": 400.0}},
            "high_conf_wr": 60.0,
        }
        w_small = ExponentialAttributionBandit.compute_multipliers(small_sample)
        w_large = ExponentialAttributionBandit.compute_multipliers(large_sample)

        # العينة الصغيرة تبقى قريبة جداً من 1.0، بينما العينة الكبيرة ترفع وزن الاتجاه بوضوح
        self.assertGreater(w_large["ema"], w_small["ema"])
        self.assertLess(abs(w_small["ema"] - 1.0), 0.16)
        for v in list(w_small.values()) + list(w_large.values()):
            self.assertTrue(0.3 <= v <= 3.0)


class TestChampionChallengerManager(unittest.TestCase):
    def test_step_clamping_promotion_and_disk_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = os.path.join(td, "cc_state.json")
            mgr = ChampionChallengerManager(
                state_path=state_file, probation_trades=5, max_weight_step=0.25
            )
            # محاولة قفزة عنيفة إلى 2.8 → تُقيَّد بـ 1.0 + 0.25 = 1.25
            accepted, reason, applied = mgr.propose_challenger(
                {"ema": 2.8, "ha": 0.4}, current_win_rate=55.0, current_expectancy=1.0
            )
            self.assertTrue(accepted, reason)
            self.assertAlmostEqual(applied["ema"], 1.25, places=4)
            self.assertAlmostEqual(applied["ha"], 0.75, places=4)

            # 4 رابحة + 1 خاسرة → ترقية إلى Champion v2
            outcomes = [3.0, 2.5, -1.0, 4.0, 2.0]
            res = None
            for p in outcomes:
                res = mgr.record_trade_outcome(p)
            self.assertEqual(res["action"], "PROMOTED")
            self.assertEqual(mgr.champion.version, 2)
            self.assertEqual(mgr.promotions_count, 1)

            # إعادة التحميل من القرص تحفظ النسخة v2 والأوزان المرقّاة
            reloaded = ChampionChallengerManager(state_path=state_file)
            self.assertEqual(reloaded.champion.version, 2)
            self.assertAlmostEqual(reloaded.champion.weights["ema"], 1.25, places=4)

    def test_early_auto_rollback_on_consecutive_losses_and_cooldown(self):
        mgr = ChampionChallengerManager(
            probation_trades=10, max_consecutive_losses=4, rollback_cooldown_trades=3
        )
        accepted, _, applied = mgr.propose_challenger({"ema": 1.20}, current_win_rate=60.0, current_expectancy=2.0)
        self.assertTrue(accepted)
        self.assertAlmostEqual(applied["ema"], 1.20, places=4)

        for _ in range(3):
            r = mgr.record_trade_outcome(-5.0)
            self.assertEqual(r["action"], "NONE")
        r4 = mgr.record_trade_outcome(-5.0)
        self.assertEqual(r4["action"], "AUTO_ROLLBACK")
        self.assertAlmostEqual(r4["weights"]["ema"], 1.0, places=4)
        self.assertEqual(mgr.rollbacks_count, 1)

        # أثناء فترة التهدئة (3 صفقات) يُرفض أي اقتراح جديد
        ok_cd, reason_cd, _ = mgr.propose_challenger({"ema": 1.15})
        self.assertFalse(ok_cd)
        self.assertIn("cooldown", reason_cd)

        # بعد 3 صفقات تنتهي فترة التهدئة ويُقبل الاقتراح مجدداً
        for _ in range(3):
            mgr.record_trade_outcome(2.0)
        ok_after, _, _ = mgr.propose_challenger({"ema": 1.15})
        self.assertTrue(ok_after)

    def test_probation_end_rollback_on_degraded_expectancy(self):
        mgr = ChampionChallengerManager(probation_trades=5, max_consecutive_losses=4)
        mgr.propose_challenger({"ema": 1.20}, current_win_rate=70.0, current_expectancy=5.0)
        # أداء متدهور (2 فوز صغير، 3 خسائر كبيرة) دون 4 خسائر متتالية
        res = None
        for p in [-4.0, 1.0, -4.0, 1.0, -4.0]:
            res = mgr.record_trade_outcome(p)
        self.assertEqual(res["action"], "AUTO_ROLLBACK")
        self.assertAlmostEqual(mgr.active_weights["ema"], 1.0, places=4)


class TestLearningAgentAndMarketAnalystIntegration(unittest.TestCase):
    def test_stationary_feature_vector_is_scale_invariant_across_symbols(self):
        # EURUSD (سعر 1.1020، EMA 1.1000، ATR 0.0010 → المسافة = +2.0 ATR)
        f_eur = LearningAgent.build_stationary_feature_vector(
            buy_score=5.0, sell_score=1.0, confidence=75.0,
            price=1.1020, ema_value=1.1000, rsi_value=62.0,
            macd_value=0.0005, adx_value=28.0, atr_value=0.0010,
        )
        # XAUUSD (سعر 2704.0، EMA 2700.0، ATR 2.0 → المسافة = +2.0 ATR أيضاً!)
        f_xau = LearningAgent.build_stationary_feature_vector(
            buy_score=5.0, sell_score=1.0, confidence=75.0,
            price=2704.0, ema_value=2700.0, rsi_value=62.0,
            macd_value=1.0, adx_value=28.0, atr_value=2.0,
        )
        self.assertEqual(len(f_eur), 8)
        self.assertEqual(len(f_xau), 8)
        self.assertAlmostEqual(f_eur[3], 2.0, places=4)
        self.assertAlmostEqual(f_xau[3], 2.0, places=4)
        self.assertAlmostEqual(f_eur[5], f_xau[5], places=4)

    def test_learning_agent_auto_rollback_restores_voting_engine_and_emits_bus_event(self):
        with tempfile.TemporaryDirectory() as td:
            ve = VotingEngine()
            la = LearningAgent(voting_engine=ve)
            la.champion_manager = ChampionChallengerManager(
                state_path=os.path.join(td, "cc.json"),
                probation_trades=6,
                max_consecutive_losses=3,
            )
            la._write_reflections = lambda: 0

            # تفعيل Challenger
            ok, _, w = la.champion_manager.propose_challenger({"ema": 1.25}, 60.0, 2.0)
            self.assertTrue(ok)
            ve.update_weights(w)
            self.assertAlmostEqual(ve.learned_multipliers["ema"], 1.25, places=4)

            rollbacks_seen = []
            la.bus.subscribe("champion_rollback", lambda m: rollbacks_seen.append(m.data))

            async def _feed_losses():
                for i in range(3):
                    await la._on_trade_closed_event(BusMessage(
                        topic="trade_closed", sender="MonitorAgent",
                        data={"ticket": None, "profit": -4.0, "regime": "STRONG_TREND", "symbol": "EURUSD"},
                    ))

            asyncio.run(_feed_losses())
            # يجب استعادة وزن Champion (1.0) تلقائياً وبث حدث champion_rollback
            self.assertAlmostEqual(ve.learned_multipliers["ema"], 1.0, places=4)
            self.assertEqual(len(rollbacks_seen), 1)
            self.assertEqual(la.stats["rollbacks_count"], 1)

    def test_market_analyst_enforces_regime_confidence_boost(self):
        class _DummyMT5:
            data_source = "TEST"
            def get_ohlcv(self, symbol, bars=200): return [1] * 80
            def get_tick(self, symbol): return {"spread": 1.0}

        ma = MarketAnalystAgent(_DummyMT5())
        # محاكاة استلام تشديد +15% للنظام STRONG_TREND → العتبة الفعالة 55 + 15 = 70%
        ma._regime_confidence_boost["STRONG_TREND"] = 15.0

        emitted = []
        saved_rejections = []
        ma._maybe_emit_signal = mock.AsyncMock(side_effect=lambda *a, **k: emitted.append(a))
        ma._check_higher_timeframe = mock.AsyncMock(return_value=True)
        ma._save_signal_to_db = lambda *a, **kw: saved_rejections.append(kw.get("rejection_reason"))

        dummy_iv = SimpleNamespace(
            is_valid=lambda: True, close=1.1, ema=1.09, rsi=60.0, macd=0.001, adx=30.0,
            atr=0.001, stoch_k=50.0, bb_upper=1.11, bb_lower=1.08, ha_bullish=True,
            tenkan=1.1, kijun=1.095, spread=1.0,
        )
        dummy_fsm = SimpleNamespace(
            regime=SimpleNamespace(value="STRONG_TREND"),
            trade_allowed=True,
            to_dict=lambda: {"regime": "STRONG_TREND"},
        )
        # ثقة 65% < 70% → يجب حجب الإشارة بـ ADAPTIVE_CONFIDENCE_FILTER
        low_vote = SimpleNamespace(
            direction="BUY", signal_strong=True, confidence=65.0,
            to_dict=lambda: {"direction": "BUY", "confidence": 65.0},
        )
        ma.indicators.calculate = lambda df, sp: dummy_iv
        ma.fsm.detect = lambda iv: dummy_fsm
        ma.voting.vote = lambda iv, fsm: low_vote

        asyncio.run(ma._analyze_symbol("EURUSD"))
        self.assertEqual(len(emitted), 0)
        self.assertTrue(any(r and r.startswith("ADAPTIVE_CONFIDENCE_FILTER") for r in saved_rejections))

        # ثقة 76% >= 70% → يجب تمرير الإشارة
        high_vote = SimpleNamespace(
            direction="BUY", signal_strong=True, confidence=76.0,
            to_dict=lambda: {"direction": "BUY", "confidence": 76.0},
        )
        ma.voting.vote = lambda iv, fsm: high_vote
        asyncio.run(ma._analyze_symbol("EURUSD"))
        self.assertEqual(len(emitted), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
