"""
tests/test_p3_behavioral.py — اختبارات سلوكية لحزمة P3
=====================================================
كل اختبار هنا **يُشغّل الكود فعلاً** ويتحقق من النتيجة العددية/السلوكية؛ لا يوجد
اختبار يبحث عن نصوص داخل ملفات المصدر.

البنود:
  2) الاحتمال المعاير الحقيقي أو None (لا 0.5 مُختلَق ولا GBM غير معاير)
  3) بوابة التفعيل خارج العيّنة (OOS) قبل أن يصل الاحتمال إلى التحجيم
  5) قيمة البيب للذهب في مسار MT5 الحي متسقة مع حجم البيب (المخاطرة الفعلية = المقصودة)
  6) وحدة السبريد موحّدة (بيب) عبر كل الرموز ومطابقة لحدود symbol_spread_limits
  8) ml_models لا يستورد الوحدات الثقيلة عند import ml_models

التشغيل:  PYTHONPATH=. python -m unittest tests/test_p3_behavioral.py -v
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
import types

import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for _p in (ROOT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ───────────────────────── بيانات اصطناعية بحقيقة معروفة ─────────────────────────
def _informative(n=600, seed=7, strength=3.0):
    """y يعتمد فعلاً على f0 → نموذج جيد يجب أن يُظهر ميزة خارج العيّنة."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    p = 1.0 / (1.0 + np.exp(-strength * X[:, 0]))
    y = (rng.random(n) < p).astype(int)
    return X, y, p


def _noise(n=600, seed=11):
    """y مستقل تماماً عن X → لا ميزة؛ البوابة يجب أن تبقى مغلقة."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    y = (rng.random(n) < 0.5).astype(int)
    return X, y


# ═════════════════════════ 3) بوابة التفعيل (منطق خالص) ═════════════════════════
class TestActivationGate(unittest.TestCase):
    def setUp(self):
        from quant_core.activation_gate import MetaActivationGate
        self.Gate = MetaActivationGate
        self.gate = MetaActivationGate(min_oos_samples=200, n_bootstrap=400, block_size=5, seed=1)

    def test_informative_probabilities_open_the_gate(self):
        _, y, p_true = _informative(n=600)
        d = self.gate.evaluate(y, p_true)
        self.assertTrue(d.active, d.summary())
        self.assertGreater(d.auc_ci_low, 0.5)
        self.assertGreater(d.brier_skill, 0.0)
        self.assertEqual(d.n_oos, 600)

    def test_random_probabilities_keep_the_gate_closed(self):
        rng = np.random.default_rng(3)
        y = (rng.random(600) < 0.5).astype(int)
        p = rng.random(600)  # لا علاقة له بـ y
        d = self.gate.evaluate(y, p)
        self.assertFalse(d.active, d.summary())
        self.assertTrue(d.reasons)

    def test_too_few_oos_samples_closed_with_reason(self):
        _, y, p = _informative(n=60)
        d = self.gate.evaluate(y, p)
        self.assertFalse(d.active)
        self.assertEqual(d.n_oos, 60)
        self.assertIn("n_oos", d.reasons[0])

    def test_good_ranking_but_bad_calibration_is_rejected_by_brier_arm(self):
        """AUC جيد لكن احتمالات متطرفة وخاطئة غالباً ⇒ Brier Skill سالب ⇒ مغلقة."""
        rng = np.random.default_rng(5)
        n = 600
        y = (rng.random(n) < 0.5).astype(int)
        score = y * 0.8 + rng.normal(size=n)          # ترتيب جيد (AUC > 0.5)
        p = np.where(score > np.median(score), 0.99, 0.01)  # ثقة مفرطة
        d = self.gate.evaluate(y, p)
        self.assertGreater(d.auc, 0.5)
        self.assertLess(d.brier_skill, 0.0)
        self.assertFalse(d.active, d.summary())

    def test_single_class_and_missing_inputs_closed(self):
        self.assertFalse(self.gate.evaluate(np.ones(300, dtype=int), np.full(300, 0.6)).active)
        self.assertFalse(self.gate.evaluate(None, None).active)
        self.assertFalse(self.gate.evaluate([1, 0, 1], [0.5, 0.5]).active)

    def test_nan_predictions_are_dropped_not_counted(self):
        _, y, p = _informative(n=250)
        p = p.copy()
        p[:100] = np.nan  # 150 عيّنة صالحة فقط < 200
        d = self.gate.evaluate(y, p)
        self.assertEqual(d.n_oos, 150)
        self.assertFalse(d.active)

    def test_deterministic_for_same_seed(self):
        _, y, p = _informative(n=400)
        a = self.gate.evaluate(y, p)
        b = self.gate.evaluate(y, p)
        self.assertEqual(a, b)


# ═══════════════════ 2+3) MetaLabelingClassifier: OOS + احتمال صادق ═══════════════════
class TestMetaClassifierHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from quant_core.meta_model import MetaLabelingClassifier
        from quant_core.activation_gate import MetaActivationGate
        cls.Clf = MetaLabelingClassifier
        # ثقة افتراضية 0.99 كما في config.META_GATE
        cls.gate = MetaActivationGate(min_oos_samples=150, n_bootstrap=400, block_size=10, seed=42)
        Xi, yi, _ = _informative(n=500)
        cls.good = MetaLabelingClassifier(n_splits=4)
        cls.good.fit(Xi, yi)
        # ستة نماذج على ضجيج مستقل عن y (بذور 1000..1005: نفس مولّد محاكاة FPR الموثّقة في P3_CHANGELOG)
        cls.noise_models = []
        for s in range(6):
            Xn, yn = _noise(n=500, seed=1000 + s)
            m = MetaLabelingClassifier(n_splits=4)
            m.fit(Xn, yn)
            cls.noise_models.append(m)
        cls.Xi = Xi

    def test_unfitted_returns_none_not_fabricated_half(self):
        c = self.Clf()
        self.assertIsNone(c.predict_calibrated([0.0] * 8))
        self.assertFalse(c.activation_decision(self.gate).active)

    def test_fit_stores_true_oos_predictions(self):
        self.assertGreater(len(self.good.oos_labels_), 100)
        self.assertEqual(len(self.good.oos_labels_), len(self.good.oos_probs_))
        self.assertTrue(np.all((self.good.oos_probs_ > 0) & (self.good.oos_probs_ < 1)))

    def test_gate_opens_for_real_signal(self):
        dg = self.good.activation_decision(self.gate)
        self.assertTrue(dg.active, dg.summary())

    def test_gate_stays_closed_for_pure_noise_models(self):
        for i, m in enumerate(self.noise_models):
            d = m.activation_decision(self.gate)
            self.assertFalse(d.active, f"noise seed {1000 + i}: {d.summary()}")

    def test_predict_calibrated_range_and_direction(self):
        hi = self.good.predict_calibrated([3.0] + [0.0] * 7)
        lo = self.good.predict_calibrated([-3.0] + [0.0] * 7)
        self.assertTrue(0.01 <= lo <= hi <= 0.99)
        self.assertGreater(hi, 0.6)
        self.assertLess(lo, 0.4)

    def test_predict_calibrated_rejects_bad_feature_vectors(self):
        self.assertIsNone(self.good.predict_calibrated([0.0] * 5))              # طول خاطئ
        self.assertIsNone(self.good.predict_calibrated([float("nan")] + [0.0] * 7))
        self.assertIsNone(self.good.predict_calibrated({"f_0": 1.0}))           # مفاتيح ناقصة

    def test_save_load_roundtrip_keeps_decision_and_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.pkl")
            self.good.save(path)
            loaded = self.Clf.load(path)
            self.assertEqual(self.good.activation_decision(self.gate),
                             loaded.activation_decision(self.gate))
            f = [0.7] + [0.1] * 7
            self.assertAlmostEqual(self.good.predict_calibrated(f), loaded.predict_calibrated(f), places=9)

    def test_legacy_pickle_without_oos_is_closed(self):
        """ملف meta_model.pkl من P1/P2 (بلا OOS) ⇒ البوابة مغلقة حتى إعادة التدريب."""
        import joblib
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "legacy.pkl")
            joblib.dump({"model": self.good.model, "feature_names": self.good.feature_names,
                         "calibration_method": "sigmoid", "is_fitted": True}, path)
            legacy = self.Clf.load(path)
            dec = legacy.activation_decision(self.gate)
            self.assertFalse(dec.active)
            self.assertEqual(dec.n_oos, 0)


# ═════════════════ 2+3) المزوّد الحي: لا احتمال إلا بعد فتح البوابة ═════════════════
class TestMetaProbabilityProvider(unittest.TestCase):
    def setUp(self):
        from quant_core.meta_model import MetaLabelingClassifier
        from quant_core.activation_gate import MetaActivationGate
        from quant_core.meta_runtime import MetaProbabilityProvider
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "meta_model.pkl")
        self.gate = MetaActivationGate(min_oos_samples=150, n_bootstrap=400, block_size=10, seed=42)
        self.Gate = MetaActivationGate
        self.Provider = MetaProbabilityProvider
        self.Clf = MetaLabelingClassifier

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, X, y):
        c = self.Clf(n_splits=4)
        c.fit(X, y)
        c.save(self.path)
        # mtime يزداد 10 ثوانٍ في كل حفظ ⇒ المزوّد يكتشف التغيير حتى على أنظمة ملفات بدقة ثانية
        self._bump = getattr(self, "_bump", 0) + 10
        t = time.time() + self._bump
        os.utime(self.path, (t, t))

    def test_missing_file_gives_none(self):
        pr = self.Provider(self.path, gate=self.gate)
        self.assertIsNone(pr.probability([0.0] * 8))
        self.assertIn("model_file_missing", pr.decision().reasons[0])

    def test_closed_gate_never_yields_probability_even_for_a_good_model(self):
        """نموذج جيد فعلاً لكن البوابة تطلب عيّنات OOS أكثر مما لديه ⇒ لا احتمال."""
        X, y, _ = _informative(500)
        self._save(X, y)
        strict = self.Gate(min_oos_samples=10_000, n_bootstrap=200, seed=1)
        pr = self.Provider(self.path, gate=strict)
        self.assertIsNone(pr.probability([2.0] + [0.0] * 7))
        self.assertFalse(pr.decision().active)
        self.assertIn("n_oos", pr.decision().reasons[0])

    def test_informative_model_yields_probability(self):
        X, y, _ = _informative(500)
        self._save(X, y)
        pr = self.Provider(self.path, gate=self.gate)
        p = pr.probability([2.0] + [0.0] * 7)
        self.assertIsNotNone(p)
        self.assertGreater(p, 0.5)

    def test_hot_reload_after_retrain_closes_gate(self):
        X, y, _ = _informative(500)
        self._save(X, y)
        pr = self.Provider(self.path, gate=self.gate)
        self.assertIsNotNone(pr.probability([2.0] + [0.0] * 7))
        Xs, ys, _ = _informative(140, seed=9)   # إعادة تدريب على عيّنة أصغر: OOS < 150 ⇒ تُغلق البوابة
        self._save(Xs, ys)
        self.assertIsNone(pr.probability([2.0] + [0.0] * 7))
        self.assertLess(pr.decision().n_oos, 150)

    def test_corrupt_file_is_closed_not_exception(self):
        with open(self.path, "wb") as f:
            f.write(b"not a pickle")
        pr = self.Provider(self.path, gate=self.gate)
        self.assertIsNone(pr.probability([0.0] * 8))
        self.assertIn("model_load_failed", pr.decision().reasons[0])

    def test_none_features_give_none(self):
        X, y, _ = _informative(500)
        self._save(X, y)
        self.assertIsNone(self.Provider(self.path, gate=self.gate).probability(None))


class TestExecutionAgentUsesOnlyGatedProbability(unittest.TestCase):
    """يتجاهل shadow['ml_prob'] (مصدر غير مضمون) ويأخذ فقط ما يُرجعه المزوّد."""

    @classmethod
    def setUpClass(cls):
        try:
            from agents.execution_agent import ExecutionAgent
        except Exception as exc:  # pragma: no cover - بيئة ناقصة
            raise unittest.SkipTest(f"ExecutionAgent غير قابل للاستيراد هنا: {exc}")
        cls.EA = ExecutionAgent

    def _agent(self, provider):
        a = self.EA.__new__(self.EA)  # بدون __init__ (لا حاجة لـ MT5)
        a.meta_provider = provider
        return a

    class _Prov:
        def __init__(self, ret):
            self.ret, self.seen = ret, []

        def probability(self, f):
            self.seen.append(f)
            return self.ret

    def test_ignores_untrusted_ml_prob(self):
        prov = self._Prov(None)
        a = self._agent(prov)
        out = a._gated_meta_probability({"ml_prob": 0.93, "ml_features": [1, 2, 3, 4, 5, 6, 7, 8]})
        self.assertIsNone(out)
        self.assertEqual(prov.seen, [[1, 2, 3, 4, 5, 6, 7, 8]])

    def test_passes_provider_value_through(self):
        a = self._agent(self._Prov(0.64))
        self.assertEqual(a._gated_meta_probability({"ml_features": [0.0] * 8}), 0.64)

    def test_missing_shadow_data(self):
        prov = self._Prov(None)
        a = self._agent(prov)
        self.assertIsNone(a._gated_meta_probability({}))
        self.assertIsNone(a._gated_meta_probability(None))
        self.assertEqual(prov.seen, [None, None])


# ═════════════════ 5+6) قيمة البيب والسبريد عبر الواجهة العامة للموصل ═════════════════
class _FakeSymInfo:
    def __init__(self, digits, point, tick_value, tick_size):
        self.digits, self.point = digits, point
        self.trade_tick_value, self.trade_tick_size = tick_value, tick_size


class _FakeTick:
    def __init__(self, ask, bid):
        self.ask, self.bid, self.time = ask, bid, 1


class _FakeMT5:
    def __init__(self, infos, ticks=None):
        self._infos, self._ticks = infos, ticks or {}

    def symbol_info(self, s):
        return self._infos.get(s)

    def symbol_info_tick(self, s):
        return self._ticks.get(s)


# مواصفات تمثّل وسيطين مختلفين للذهب (خانتان / ثلاث خانات): 1$ لكل 0.01$ للوت القياسي (100 أونصة)
_GOLD_2D = _FakeSymInfo(2, 0.01, 1.0, 0.01)
_GOLD_3D = _FakeSymInfo(3, 0.001, 0.1, 0.001)
_EURUSD = _FakeSymInfo(5, 0.00001, 1.0, 0.00001)
_USDJPY = _FakeSymInfo(3, 0.001, 0.67, 0.001)


class TestPipValueAndSpreadUnits(unittest.TestCase):
    def setUp(self):
        import core.mt5_connector as m
        self.m = m
        self._saved = (m.MT5_AVAILABLE, getattr(m, "mt5", None))
        m.MT5_AVAILABLE = True
        self.conn = m.MT5Connector.__new__(m.MT5Connector)
        self.conn._use_yfinance = False
        self.conn.connected = True

    def tearDown(self):
        self.m.MT5_AVAILABLE = self._saved[0]
        self.m.mt5 = self._saved[1]
        if self._saved[1] is None:
            del self.m.mt5

    def _use(self, infos, ticks=None):
        self.m.mt5 = _FakeMT5(infos, ticks)

    # ── 5) قيمة البيب ──
    def test_gold_pip_value_is_ten_dollars_for_both_digit_conventions(self):
        for info in (_GOLD_2D, _GOLD_3D):
            self._use({"XAUUSD": info})
            self.assertAlmostEqual(self.conn.get_pip_value("XAUUSD"), 10.0, places=6,
                                   msg=f"digits={info.digits}")

    def test_major_and_jpy_pip_values_unchanged(self):
        self._use({"EURUSD": _EURUSD, "USDJPY": _USDJPY})
        self.assertAlmostEqual(self.conn.get_pip_value("EURUSD"), 10.0, places=6)
        self.assertAlmostEqual(self.conn.get_pip_value("USDJPY"), 6.7, places=6)

    def test_invalid_symbol_info_falls_back_to_documented_table_not_garbage(self):
        self._use({"XAUUSD": _FakeSymInfo(2, 0.01, 0.0, 0.0)})
        self.assertEqual(self.conn.get_pip_value("XAUUSD"), 10.0)  # الجدول الاحتياطي الموثّق

    def test_gold_realized_risk_equals_intended_risk_end_to_end(self):
        """
        الاختبار الجوهري: إذا ضرب السعر SL فالخسارة الفعلية بالدولار = المخاطرة المقصودة.
        خسارة SL الفعلية = lot × (مسافة SL ÷ tick_size) × tick_value (تعريف MT5).
        قبل P3: pip_value=1$ للذهب ⇒ لوت أكبر 10 مرات ⇒ خسارة فعلية ≈ 10× المقصود.
        """
        from core.risk_manager import RiskManager
        self._use({"XAUUSD": _GOLD_2D})
        rm = RiskManager()
        rm.cfg = dict(rm.cfg, manual_lot_enabled=False, use_dynamic_sl=True)
        pip_value = self.conn.get_pip_value("XAUUSD")
        balance, atr, entry = 100_000.0, 2.0, 2000.0
        tp = rm.calc_trade_params("XAUUSD", "BUY", entry, atr, balance, pip_value, digits=2)
        self.assertTrue(tp.valid)
        sl_distance = atr * rm.cfg["sl_atr_multiplier"]
        realized = tp.lot_size * (sl_distance / _GOLD_2D.trade_tick_size) * _GOLD_2D.trade_tick_value
        intended = balance * rm.cfg["risk_percent"] / 100.0
        self.assertAlmostEqual(realized / intended, 1.0, delta=0.02,
                               msg=f"realized={realized:.2f} intended={intended:.2f}")

    # ── 6) السبريد ──
    def test_get_tick_spread_is_in_pips_for_every_symbol_class(self):
        cases = [
            ("XAUUSD", _GOLD_2D, 2000.40, 2000.00, 4.0),    # 0.40$ = 4 بيب
            ("XAUUSD", _GOLD_3D, 2000.400, 2000.000, 4.0),  # نفس النتيجة بغضّ النظر عن خانات الوسيط
            ("EURUSD", _EURUSD, 1.10012, 1.10000, 1.2),
            ("USDJPY", _USDJPY, 150.012, 150.000, 1.2),
        ]
        for sym, info, ask, bid, expected in cases:
            self._use({sym: info}, {sym: _FakeTick(ask, bid)})
            tick = self.conn.get_tick(sym)
            self.assertAlmostEqual(tick["spread"], expected, places=1, msg=f"{sym} digits={info.digits}")

    def test_spread_limits_gate_gold_at_forty_cents(self):
        """السياسة المحفوظة: حد الذهب 0.40$. سبريد 0.30$ يمر، 0.60$ يُرفض (بعد توحيد الوحدات)."""
        from core.risk_manager import RiskManager
        rm = RiskManager()
        for ask, bid, ok in ((2000.30, 2000.00, True), (2000.60, 2000.00, False)):
            self._use({"XAUUSD": _GOLD_2D}, {"XAUUSD": _FakeTick(ask, bid)})
            spread = self.conn.get_tick("XAUUSD")["spread"]
            self.assertEqual(rm.check_spread(spread, "XAUUSD"), ok, msg=f"spread={spread}")

    def test_config_gold_limit_equals_forty_cents_in_dollars(self):
        from config import STRATEGY
        pip = self.m.MT5Connector.get_pip_size("XAUUSD")
        self.assertAlmostEqual(STRATEGY["symbol_spread_limits"]["XAUUSD"] * pip, 0.40, places=6)


# ═════════════════════════ 8) الاستيراد الكسول ═════════════════════════
class TestMlModelsLazyImport(unittest.TestCase):
    def _run(self, code: str) -> str:
        script = f"import sys; sys.path.insert(0, {ROOT_DIR!r}); {code}"
        out = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr[-800:])
        return out.stdout.strip()

    def test_import_ml_models_loads_no_heavy_submodule(self):
        out = self._run(
            "import ml_models; heavy=[m for m in ('ml_models.cross_asset_agent','ml_models.risk_adjusted_reward',"
            "'ml_models.timesfm_extractor','ml_models.timesfm_predictor','ml_models.orchestrator') if m in sys.modules];"
            "print(heavy)"
        )
        self.assertEqual(out, "[]", f"وحدات حُمّلت عند الاستيراد: {out}")

    def test_lazy_attribute_still_resolves_on_first_access(self):
        out = self._run(
            "import ml_models; assert 'ml_models.cross_asset_agent' not in sys.modules;"
            "cls = ml_models.CrossAssetGraphAgent;"
            "print(cls.__name__, 'ml_models.cross_asset_agent' in sys.modules)"
        )
        self.assertEqual(out, "CrossAssetGraphAgent True")

    def test_all_four_previously_eager_names_are_registered_lazily(self):
        out = self._run(
            "import ml_models; names=['RiskAdjustedRewardShaper','TradeTrajectorySnapshot',"
            "'CrossAssetGraphAgent','MacroFlowMetrics']; print(all(n in ml_models._LAZY_IMPORTS for n in names))"
        )
        self.assertEqual(out, "True")

    def test_unknown_attribute_raises_attribute_error(self):
        out = self._run(
            "import ml_models\ntry:\n    ml_models.no_such_thing\nexcept AttributeError:\n    print('AttributeError')"
        )
        self.assertEqual(out, "AttributeError")


if __name__ == "__main__":
    unittest.main(verbosity=2)
