"""
tests/test_foundation_models_integration.py — اختبارات دمج نماذج الأساس (2026)
==============================================================================
تتحقق من:
  1. حارس ترخيص TimesFM: يسمح بـ TimesFM 2.5 (Apache-2.0) ويمنع TimesFM 3.0 غير التجاري في الإنتاج.
  2. CachedTimesFMService: كاش TTL يمنع إعادة الاستدلال داخل دورة الـ 5 ثوانٍ مع تدهور آمن عند غياب الأوزان.
  3. HybridNewsSentimentEngine: مسار FinBERT السريع + مسار Gemma العميق لأخبار HIGH + التراجع الحتمي + عكس الإشارة لعملة التسعير (Quote Currency).
  4. NewsAgent & MarketAnalystAgent: تمرير درجات المشاعر المستمرة وميزات TimesFM وتشديد الثقة عند ارتفاع عدم اليقين.
  5. LearningAgent: متجه v2 (12 ميزة) وبوابة ترقية v2 فوق v1 عبر META_GATE و OOS AUC.
"""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ml_models.timesfm_extractor import validate_timesfm_repo_license, CachedTimesFMService
from core.news_sentiment_engine import HybridNewsSentimentEngine, logger as news_logger
from agents.learning_agent import LearningAgent
from agents.market_analyst import MarketAnalystAgent


class TestTimesFM25LicenseAndCache(unittest.TestCase):
    def test_license_guard_allows_25_and_blocks_30_in_production(self):
        ok_25, _ = validate_timesfm_repo_license("google/timesfm-2.5-200m-pytorch", allow_non_commercial=False)
        ok_30_prod, msg_30 = validate_timesfm_repo_license("google/timesfm-3.0-pytorch", allow_non_commercial=False)
        ok_30_res, _ = validate_timesfm_repo_license("google/timesfm-3.0-pytorch", allow_non_commercial=True)
        self.assertTrue(ok_25)
        self.assertFalse(ok_30_prod)
        self.assertIn("Apache-2.0", msg_30)
        self.assertTrue(ok_30_res)

        with self.assertRaises(ValueError):
            CachedTimesFMService(repo_id="google/timesfm-3.0-pytorch", allow_non_commercial=False)

    def test_cached_timesfm_service_caches_within_ttl(self):
        calls = []

        class _FakeExtractor:
            def extract_foundation_features(self, df):
                calls.append(len(df))
                return {
                    "timesfm_alpha_delta": 0.0015,
                    "forecast_momentum_slope": 0.0002,
                    "forecast_variance_risk": 1e-6,
                    "forecast_vector": [1.1] * 10,
                    "last_close": 1.1,
                    "is_valid": True,
                    "backend": "cpu",
                    "inference_count": len(calls),
                }

        svc = CachedTimesFMService(cache_ttl_sec=300.0, extractor=_FakeExtractor())
        df = pd.DataFrame({"close": [1.10 + i * 0.0001 for i in range(70)]})

        r1 = svc.get_features("EURUSD", df, now_monotonic=1000.0)
        r2 = svc.get_features("EURUSD", df, now_monotonic=1100.0)  # داخل TTL → من الكاش
        r3 = svc.get_features("EURUSD", df, now_monotonic=1350.0)  # بعد TTL → استدلال جديد

        self.assertTrue(r1["is_valid"])
        self.assertEqual(r1["inference_count"], 1)
        self.assertEqual(r2["inference_count"], 1)
        self.assertEqual(r3["inference_count"], 2)
        self.assertEqual(len(calls), 2)


class TestHybridNewsSentimentEngine(unittest.TestCase):
    def test_finbert_fast_path_and_gemma_high_impact_fusion(self):
        gemma_calls = []
        fake_finbert = lambda txt: [{"label": "positive", "score": 0.80}]

        def fake_gemma(headline):
            gemma_calls.append(headline)
            return {
                "central_bank_tone": "HAWKISH",
                "sentiment_score": 0.90,
                "recommended_action": "AVOID_NEW_TRADES",
            }

        eng = HybridNewsSentimentEngine(finbert_pipeline=fake_finbert, gemma_client=fake_gemma)

        # خبر MEDIUM → FinBERT فقط (لا يُستدعى Gemma)
        res_med = eng.analyze_headline("ECB manufacturing PMI ticks up slightly", impact="MEDIUM")
        self.assertEqual(res_med.engine_used, "FINBERT")
        self.assertEqual(len(gemma_calls), 0)

        # خبر HIGH → FinBERT + Gemma
        res_hi = eng.analyze_headline("Fed signals hawkish rate hike after hot CPI", impact="HIGH")
        self.assertEqual(res_hi.engine_used, "FINBERT+GEMMA")
        self.assertEqual(res_hi.central_bank_tone, "HAWKISH")
        self.assertEqual(res_hi.recommended_action, "AVOID_NEW_TRADES")
        self.assertGreater(res_hi.sentiment_score, 0.80)
        self.assertEqual(len(gemma_calls), 1)

    def test_quote_currency_inversion_and_lexicon_fallback(self):
        eng = HybridNewsSentimentEngine(use_finbert=False, use_gemma_for_high_impact=False)
        items = [
            {"headline": "Fed hawkish rate hike boosts USD strongly", "impact": "HIGH", "related_symbols": ["EURUSD", "USDJPY"]},
        ]
        labels, scores, tones = eng.aggregate_symbol_sentiment(items)
        # خبر إيجابي للـ USD → صاعد لـ USDJPY وهابط لـ EURUSD
        self.assertGreater(scores["USDJPY"], 0.0)
        self.assertLess(scores["EURUSD"], 0.0)
        self.assertEqual(labels["USDJPY"], "BULLISH")
        self.assertEqual(labels["EURUSD"], "BEARISH")
        self.assertEqual(tones["USDJPY"], "HAWKISH")

    def test_finbert_missing_warns_and_falls_back_to_lexicon(self):
        eng = HybridNewsSentimentEngine(use_finbert=True, use_gemma_for_high_impact=False)
        with mock.patch.dict(sys.modules, {"transformers": None}):
            with self.assertLogs(news_logger, level="WARNING") as cm:
                pipe = eng._ensure_finbert()

        self.assertIsNone(pipe)
        self.assertEqual(len(cm.records), 1)
        self.assertIn("lexicon fallback", cm.output[0].lower())


class TestLearningV2AndMarketAnalystIntegration(unittest.TestCase):
    def test_learning_agent_v2_feature_vector_and_promotion_gate(self):
        vec12 = LearningAgent.build_v2_feature_vector(
            buy_score=5.2, sell_score=1.1, confidence=78.0,
            price=1.1020, ema_value=1.1000, rsi_value=61.0,
            macd_value=0.0005, adx_value=29.0, atr_value=0.0010,
            timesfm_alpha_delta=0.0021, forecast_momentum_slope=0.0003,
            forecast_variance_risk=1.2e-6, news_sentiment_score=0.65,
        )
        self.assertEqual(len(vec12), 12)
        self.assertAlmostEqual(vec12[3], 2.0, places=4)    # ema_dist_atr
        self.assertAlmostEqual(vec12[11], 0.65, places=4)  # news_sentiment_score

        # بوابة ترقية v2 ترفض إذا لم يجتز META_GATE أو كان المكسب أقل من 0.015
        ok_fail_gate, _ = LearningAgent.should_promote_v2_model(0.58, 0.65, 0.05, v2_gate_active=False)
        ok_small_gain, _ = LearningAgent.should_promote_v2_model(0.60, 0.61, 0.05, v2_gate_active=True)
        ok_pass, _ = LearningAgent.should_promote_v2_model(0.58, 0.62, 0.04, v2_gate_active=True)
        self.assertFalse(ok_fail_gate)
        self.assertFalse(ok_small_gain)
        self.assertTrue(ok_pass)

    def test_market_analyst_tightens_confidence_on_high_timesfm_uncertainty(self):
        class _DummyMT5:
            data_source = "TEST"
            def get_ohlcv(self, symbol, bars=200): return pd.DataFrame({"close": [1.1] * 70})
            def get_tick(self, symbol): return {"spread": 1.0}

        ma = MarketAnalystAgent(_DummyMT5())
        # حقن TimesFM بحالة عدم يقين مرتفع (variance > 5e-5) → يشدّد العتبة إلى 55 + 5 = 60%
        ma._timesfm_service = SimpleNamespace(
            get_features=lambda sym, df: {
                "timesfm_alpha_delta": 0.001, "forecast_momentum_slope": 0.0,
                "forecast_variance_risk": 2e-4, "is_valid": True,
            }
        )
        ma.reflection_reader = SimpleNamespace(
            evaluate_pair_regime=lambda s, r: SimpleNamespace(
                temporary_cooldown=False, confidence_penalty=0.0, summary="clean"
            )
        )
        emitted = []
        rejections = []
        ma._maybe_emit_signal = mock.AsyncMock(side_effect=lambda *a, **k: emitted.append(a))
        ma._check_higher_timeframe = mock.AsyncMock(return_value=True)
        ma._save_signal_to_db = lambda *a, **kw: rejections.append(kw.get("rejection_reason"))

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
        vote_58 = SimpleNamespace(
            direction="BUY", signal_strong=True, confidence=58.0,
            to_dict=lambda: {"direction": "BUY", "confidence": 58.0},
        )
        ma.indicators.calculate = lambda df, sp: dummy_iv
        ma.fsm.detect = lambda iv: dummy_fsm
        ma.voting.vote = lambda iv, fsm: vote_58

        asyncio.run(ma._analyze_symbol("EURUSD"))
        self.assertEqual(len(emitted), 0)
        self.assertTrue(any(r and r.startswith("ADAPTIVE_CONFIDENCE_FILTER") for r in rejections))
        self.assertTrue(ma.latest["EURUSD"]["timesfm"]["is_valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
