"""
tests/test_self_healing_and_alpha_drift.py — اختبارات الدفعة الثالثة والأخيرة (2026)
=====================================================================================
تتحقق من:
  1. PageHinkleyDriftDetector & AlphaDecayGuard: رصد انجراف الألفا الهابط (Alpha Decay)
     والتحويل التلقائي إلى وضع الظل (Shadow Demotion) وإمكانية إعادة الترقية بعد المراجعة.
  2. RuntimeResilienceWatchdog: كشف توقف نبضات الوكلاء (Heartbeat Stall)،
     وطفرات زمن التنفيذ، واسترداد اتصال MT5 بقاطع دائرة وفترة تهدئة.
  3. CodeHealingAgent: بوابة `unittest` الحتمية (ترفض التصحيح الذي يكسر الاختبارات
     وتقبل التصحيح السليم في وضع SUGGEST_MODE مع الحفاظ التام على الملف الأصلي دون تعديله).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.runtime_resilience import (
    PageHinkleyDriftDetector,
    AlphaDecayGuard,
    RuntimeResilienceWatchdog,
)
from institutional.code_healing_agent import (
    CodeHealingAgent,
    AgentExecutionMode,
    HealingStatus,
)


class TestAlphaDecayAndPageHinkley(unittest.TestCase):
    def test_stable_winning_stream_does_not_trigger_drift(self):
        guard = AlphaDecayGuard(delta=0.05, threshold=4.0, min_samples=10, pnl_scale=10.0)
        for _ in range(20):
            st = guard.record_trade("EURUSD_TREND", 12.0)
        self.assertFalse(st.drift_detected)
        self.assertFalse(guard.is_demoted("EURUSD_TREND"))

    def test_alpha_decay_triggers_automatic_shadow_demotion_and_promote_back(self):
        guard = AlphaDecayGuard(delta=0.05, threshold=3.5, min_samples=8, pnl_scale=10.0)
        # 6 صفقات رابحة تؤسس متوسطاً إيجابياً ثم انهيار مستمر في الأداء
        for _ in range(6):
            guard.record_trade("GBPUSD_RANGE", 15.0)
        st = None
        for _ in range(8):
            st = guard.record_trade("GBPUSD_RANGE", -15.0)
        self.assertTrue(st.drift_detected)
        self.assertTrue(st.shadow_demoted)
        self.assertTrue(guard.is_demoted("GBPUSD_RANGE"))
        self.assertIn("GBPUSD_RANGE", guard.demoted_keys())

        # إعادة التفعيل بعد المراجعة تعيد العداد إلى الصفر
        guard.promote_back("GBPUSD_RANGE")
        self.assertFalse(guard.is_demoted("GBPUSD_RANGE"))


class TestRuntimeResilienceWatchdog(unittest.TestCase):
    def test_heartbeat_stall_detection(self):
        wd = RuntimeResilienceWatchdog(heartbeat_max_silence_sec=60.0)
        wd.record_heartbeat("MarketAnalyst", now_monotonic=100.0)
        wd.record_heartbeat("MonitorAgent", now_monotonic=150.0)
        # عند الزمن 170: MarketAnalyst صامت منذ 70 ثانية (> 60) بينما MonitorAgent سليم (20 ثانية)
        stalled = wd.check_stalled_agents(now_monotonic=170.0)
        self.assertEqual(stalled, ["MarketAnalyst"])

    def test_mt5_circuit_breaker_reconnect_and_cooldown(self):
        class _FakeMT5:
            def __init__(self, succeed_on_attempt=2):
                self.connected = False
                self.calls = 0
                self.succeed_on_attempt = succeed_on_attempt
            def reconnect(self):
                self.calls += 1
                if self.calls >= self.succeed_on_attempt:
                    self.connected = True
                    return True
                return False

        wd = RuntimeResilienceWatchdog(max_reconnect_attempts=2, reconnect_cooldown_sec=30.0)
        mt5 = _FakeMT5(succeed_on_attempt=2)

        # المحاولة 1 تفشل عند t=100
        r1 = wd.check_and_recover_mt5(mt5, now_monotonic=100.0)
        self.assertEqual(r1["status"], "RECONNECT_FAILED")
        # عند t=110 (ضمن التهدئة 30 ثانية) لا يحاول إعادة الاتصال
        r_cd = wd.check_and_recover_mt5(mt5, now_monotonic=110.0)
        self.assertEqual(r_cd["status"], "COOLDOWN")
        self.assertEqual(mt5.calls, 1)
        # عند t=140 تنجح المحاولة الثانية ويُسترد الاتصال
        r2 = wd.check_and_recover_mt5(mt5, now_monotonic=140.0)
        self.assertEqual(r2["status"], "RECOVERED")
        self.assertTrue(r2["recovered"])
        self.assertEqual(wd.total_recoveries, 1)

    def test_mt5_circuit_opens_after_max_failed_attempts(self):
        class _DeadMT5:
            connected = False
            def connect(self): return False

        wd = RuntimeResilienceWatchdog(max_reconnect_attempts=2, reconnect_cooldown_sec=10.0)
        dead = _DeadMT5()
        wd.check_and_recover_mt5(dead, now_monotonic=100.0)
        wd.check_and_recover_mt5(dead, now_monotonic=120.0)
        r3 = wd.check_and_recover_mt5(dead, now_monotonic=140.0)
        self.assertEqual(r3["status"], "CIRCUIT_OPEN")


class TestCodeHealingUnittestGate(unittest.TestCase):
    def test_unittest_regression_gate_rejects_broken_patch_and_approves_valid_patch_in_suggest_mode(self):
        with tempfile.TemporaryDirectory() as td:
            mod_file = os.path.join(td, "calc_mod.py")
            test_file = os.path.join(td, "test_calc_mod.py")

            orig_src = "def safe_div(a, b):\n    return a / b\n"
            with open(mod_file, "w", encoding="utf-8") as f:
                f.write(orig_src)
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(
                    "import unittest\n"
                    "import calc_mod\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_div(self):\n"
                    "        self.assertAlmostEqual(calc_mod.safe_div(10.0, 2.0), 5.0)\n"
                    "        self.assertGreater(calc_mod.safe_div(10.0, 0.0), 0.0)\n"
                )

            agent = CodeHealingAgent.for_http_api(project_root=td)
            self.assertEqual(agent.mode, AgentExecutionMode.SUGGEST_MODE)

            # 1. تصحيح خاطئ (يرجع 0 دائماً) → تفشل بوابة unittest ويبقى الملف الأصلي سليماً
            bad_res = agent.heal_file(
                mod_file,
                error_message="ZeroDivisionError",
                target_line=2,
                custom_fix_snippet="def safe_div(a, b):\n    return 0.0\n",
                regression_tests=["test_calc_mod"],
                test_cwd=td,
            )
            self.assertEqual(bad_res.status, HealingStatus.VERIFICATION_FAILED)
            self.assertFalse(bad_res.verification_passed)
            self.assertEqual(open(mod_file, encoding="utf-8").read(), orig_src)

            # 2. تصحيح سليم (حماية القسمة على صفر) → تنجح بوابة unittest وتعود PENDING_APPROVAL في SUGGEST_MODE دون لمس الملف
            good_res = agent.heal_file(
                mod_file,
                error_message="ZeroDivisionError: division by zero",
                target_line=2,
                regression_tests=["test_calc_mod"],
                test_cwd=td,
            )
            self.assertEqual(good_res.status, HealingStatus.DIAGNOSED_PENDING_APPROVAL)
            self.assertTrue(good_res.verification_passed)
            self.assertEqual(open(mod_file, encoding="utf-8").read(), orig_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
