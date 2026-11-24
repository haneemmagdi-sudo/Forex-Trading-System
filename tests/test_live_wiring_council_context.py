"""
tests/test_live_wiring_council_context.py — اختبارات «التوصيل الحي» (2026 Wiring Fix)
==========================================================================================
الاختبارات السابقة كانت تستدعي الوحدات مباشرة فلم تكشف أن المسار الحي لا يستهلكها.
هذه الاختبارات تمرّ عبر المنسّقين الفعليين وتتحقق من:
  1. OmegaRiskGovernor يتلقى bus_context و reflection_advisory فعلاً داخل evaluate_symbol.
  2. صلاحية التنبيهات (TTL): dd_alert لا يُبثّ عند التعافي، فلا يجوز أن يبقى الفيتو للأبد.
  3. تصدير الحالة بين العمليتين (backend → council) عبر ملف ذري: غائب/تالف/قديم ⇒ بلا فيتو.
  4. استعلام التأمّل على مستوى الزوج (مفردات أنظمة المجلس ≠ fsm_regime المخزَّن).
  5. AlphaDecayGuard يتلقى نتائج الصفقات المغلقة داخل run_master_cycle.
  6. نبضات الوكلاء: حد صمت متناسب مع فاصل الدورة + MonitorAgent يبلغ عن التوقف مرة واحدة.
"""
import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.signal_bus import (  # noqa: E402
    SignalBus,
    BusMessage,
    CouncilStateBridge,
    load_council_context,
)
from core.reflection_memory import ReflectionMemoryReader  # noqa: E402
from core.runtime_resilience import RuntimeResilienceWatchdog, get_runtime_watchdog  # noqa: E402


def _emit(bus: SignalBus, topic: str, data: dict, priority: int = 2):
    asyncio.run(bus.publish(BusMessage(topic=topic, sender="test", priority=priority, data=data)))


def _create_reflections_db(path: Path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE agent_reflections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_ticket INTEGER, symbol TEXT, fsm_regime TEXT,
            council_would_block INTEGER, outcome_pnl REAL, outcome TEXT, created_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO agent_reflections (trade_ticket, symbol, fsm_regime, council_would_block, outcome_pnl, outcome, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


class TestBridgeTTLAndStateExport(unittest.TestCase):
    def test_emergency_dd_expires_because_recovery_is_never_broadcast(self):
        bus = SignalBus()
        bridge = CouncilStateBridge(bus, ttl_sec=1800.0)
        _emit(bus, "dd_alert", {"dd_pct": 5.2, "mode": "EMERGENCY_STOP"})
        self.assertTrue(bridge.get_council_context("EURUSD", "X")["emergency_dd_active"])

        bridge.last_dd_ts = time.time() - 3600  # آخر تنبيه قبل ساعة، ولا تنبيه تعافٍ يُبثّ أبداً
        self.assertFalse(bridge.get_council_context("EURUSD", "X")["emergency_dd_active"])

        _emit(bus, "dd_alert", {"dd_pct": 5.3, "mode": "EMERGENCY_STOP"})  # الخطر مستمر ⇒ تنبيه جديد يجدد
        self.assertTrue(bridge.get_council_context("EURUSD", "X")["emergency_dd_active"])

    def test_news_blackout_expires_and_is_per_symbol(self):
        bus = SignalBus()
        bridge = CouncilStateBridge(bus, ttl_sec=1800.0)
        _emit(bus, "news_alert", {
            "impact": "HIGH", "recommendation": "AVOID_NEW_TRADES", "related_symbols": ["EURUSD"],
        })
        self.assertTrue(bridge.get_council_context("EURUSD", "X")["news_blackout"])
        self.assertFalse(bridge.get_council_context("GBPUSD", "X")["news_blackout"])

        bridge._news_blackout_ts["EURUSD"] = time.time() - 4000
        self.assertFalse(bridge.get_council_context("EURUSD", "X")["news_blackout"])

    def test_state_file_roundtrip_between_processes(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            path = Path(td) / "council_bus_state.json"
            bus = SignalBus()
            bridge = CouncilStateBridge(bus)
            bridge.enable_state_export(path)
            self.assertFalse(load_council_context("EURUSD", "X", path)["emergency_dd_active"])

            _emit(bus, "dd_alert", {"dd_pct": 6.0, "mode": "EMERGENCY_STOP"})
            ctx = load_council_context("EURUSD", "X", path)  # «عملية المجلس» تقرأ الملف فقط
            self.assertTrue(ctx["emergency_dd_active"])
            self.assertAlmostEqual(ctx["last_dd_pct"], 6.0)

    def test_missing_corrupt_or_stale_state_means_no_veto(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            path = Path(td) / "council_bus_state.json"
            self.assertIsNone(load_council_context("EURUSD", "X", path))  # backend غير شغّال

            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(load_council_context("EURUSD", "X", path))

            path.write_text(json.dumps({"emergency_dd_active": True, "last_dd_ts": time.time() - 7200}), encoding="utf-8")
            self.assertFalse(load_council_context("EURUSD", "X", path)["emergency_dd_active"])


class TestReflectionPairLevelQuery(unittest.TestCase):
    def test_council_regime_vocabulary_finds_nothing_but_pair_level_does(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "trading.db"
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            _create_reflections_db(db, [
                (1, "EURUSD", "STRONG_TREND", 0, -10.0, "LOSS", now_iso),
                (2, "EURUSD", "SLOW_TREND", 0, -8.0, "LOSS", now_iso),
                (3, "EURUSD", "STRONG_TREND", 0, -6.0, "LOSS", now_iso),
                (4, "EURUSD", "LOW_VOL_RANGE", 0, -5.0, "LOSS", now_iso),
            ])
            reader = ReflectionMemoryReader(db_path=db, cooldown_consecutive_losses=4)
            # هذا ما كان سيحدث لو ربطنا المجلس بمفرداته: صفر صفوف ⇒ توصية محايدة وميتة
            self.assertFalse(reader.evaluate_pair_regime("EURUSD", "TRENDING_LOW_VOL").temporary_cooldown)
            self.assertTrue(reader.evaluate_pair_regime("EURUSD", reader.ANY_REGIME).temporary_cooldown)


class TestOrchestratorsReallyFeedOmega(unittest.TestCase):
    """المسار الحي الفعلي: لا استدعاء مباشر لـ adjudicate."""

    @classmethod
    def setUpClass(cls):
        import council.delta_macro_sentinel as delta
        cls._delta = delta
        cls._orig_fetch = delta._try_fetch_forex_factory
        delta._try_fetch_forex_factory = lambda now: [
            {"title": "Low Impact Stat", "country": "USD", "impact": "Low", "date": "2026-11-25T12:00:00Z"}
        ]

    @classmethod
    def tearDownClass(cls):
        cls._delta._try_fetch_forex_factory = cls._orig_fetch

    def _make_orchestrator(self, td: str):
        import main_orchestrator as mo
        from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
        with mock.patch.object(mo, "TradeOutcomeRecorder", lambda: TradeOutcomeRecorder(db_path=Path(td) / "journal.db")):
            orch = mo.MultiAgentOrchestrator(mql5_shared_dir=str(Path(td) / "signals"), use_live_mt5=False)
        return orch

    def test_evaluate_symbol_passes_bus_and_reflection_context_and_vetoes(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            state = Path(td) / "council_bus_state.json"
            state.write_text(json.dumps({
                "emergency_dd_active": True, "last_dd_pct": 5.5, "last_dd_ts": time.time(),
            }), encoding="utf-8")

            db = Path(td) / "trading.db"
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            _create_reflections_db(db, [
                (i, "EURUSD", "STRONG_TREND", 0, -5.0, "LOSS", now_iso) for i in range(1, 5)
            ])

            orch = self._make_orchestrator(td)
            orch._reflection_reader = ReflectionMemoryReader(db_path=db)
            spy = mock.Mock(wraps=orch.omega.adjudicate)
            orch.omega.adjudicate = spy

            with mock.patch("core.signal_bus.DEFAULT_COUNCIL_STATE_PATH", state):
                payload = asyncio.run(orch.evaluate_symbol("EURUSD"))

            self.assertTrue(spy.called, "Omega لم يُستدعَ — الدورة توقفت قبله")
            kwargs = spy.call_args.kwargs
            self.assertTrue(kwargs["bus_context"]["emergency_dd_active"])
            self.assertTrue(kwargs["reflection_advisory"]["temporary_cooldown"])
            self.assertEqual(payload.action, "STAND_DOWN")

    def test_evaluate_symbol_without_backend_state_passes_no_bus_veto(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            orch = self._make_orchestrator(td)
            orch._reflection_reader = ReflectionMemoryReader(db_path=Path(td) / "absent.db")
            spy = mock.Mock(wraps=orch.omega.adjudicate)
            orch.omega.adjudicate = spy

            with mock.patch("core.signal_bus.DEFAULT_COUNCIL_STATE_PATH", Path(td) / "absent.json"):
                asyncio.run(orch.evaluate_symbol("EURUSD"))

            kwargs = spy.call_args.kwargs
            self.assertIsNone(kwargs["bus_context"])  # لا ملف ⇒ لا سياق، وليس فيتو
            self.assertFalse(kwargs["reflection_advisory"]["temporary_cooldown"])

    def test_autonomous_orchestrator_uses_same_live_context(self):
        import autonomous_master_orchestrator as amo
        from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            with mock.patch.object(amo, "TradeOutcomeRecorder", lambda: TradeOutcomeRecorder(db_path=Path(td) / "j.db")):
                orch = amo.AutonomousMasterOrchestrator(mql5_shared_dir=str(Path(td) / "s"), use_live_mt5=False)
            calls = []
            real = amo.build_omega_live_context

            def _spy(symbol, regime_value, reader=None):
                calls.append((symbol, regime_value, reader))
                return real(symbol, regime_value, reader)

            with mock.patch.object(amo, "build_omega_live_context", _spy):
                for sym in ("EURUSD", "GBPUSD", "XAUUSD"):
                    asyncio.run(orch.evaluate_symbol_autonomous(sym))
            self.assertTrue(calls, "المنسّق المستقل لم يصل إلى خطوة Omega لأي رمز")
            self.assertIs(calls[0][2], orch._reflection_reader)


class TestAlphaGuardFedByMasterCycle(unittest.TestCase):
    def test_closed_deals_reach_alpha_guard_and_audit_reports_demotion(self):
        import autonomous_master_orchestrator as amo
        from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            with mock.patch.object(amo, "TradeOutcomeRecorder", lambda: TradeOutcomeRecorder(db_path=Path(td) / "j.db")):
                orch = amo.AutonomousMasterOrchestrator(mql5_shared_dir=str(Path(td) / "s"), use_live_mt5=False)

            orch.watchdog.alpha_guard.enable_persistence(Path(td) / "guard.json")
            deals = [
                {"symbol": sym, "profit_usd": pnl, "deal_ticket": i}
                for i, (sym, pnl) in enumerate(
                    [("EURUSD", 20.0)] * 12 + [("EURUSD", -30.0)] * 10 + [("GBPUSD", 20.0)] * 12
                )
            ]
            orch.feedback.inspect_and_sync_closed_deals = lambda hours_back=12: deals

            async def _no_cycle(sym, *a, **k):
                raise RuntimeError("skip evaluation")

            orch.evaluate_symbol_autonomous = _no_cycle
            asyncio.run(orch.run_master_cycle(["EURUSD"]))

            guard = orch.watchdog.alpha_guard
            self.assertTrue(guard.is_demoted("EURUSD"))
            self.assertFalse(guard.is_demoted("GBPUSD"))
            self.assertEqual(orch.watchdog.audit_and_verify()["shadow_demoted_strategies"], ["EURUSD"])


class TestHeartbeats(unittest.TestCase):
    def test_silence_limit_scales_with_agent_interval(self):
        wd = RuntimeResilienceWatchdog(heartbeat_max_silence_sec=60.0)
        wd.record_heartbeat("LearningAgent", now_monotonic=0.0, interval_sec=3600.0)
        wd.record_heartbeat("MonitorAgent", now_monotonic=0.0, interval_sec=1.0)
        self.assertEqual(wd.check_stalled_agents(now_monotonic=3601.0), ["MonitorAgent"])  # التعلم صامت بشكل طبيعي
        self.assertEqual(sorted(wd.check_stalled_agents(now_monotonic=10801.0)), ["LearningAgent", "MonitorAgent"])

    def test_forget_heartbeat_removes_intentionally_stopped_agent(self):
        wd = RuntimeResilienceWatchdog()
        wd.record_heartbeat("A", now_monotonic=0.0)
        wd.forget_heartbeat("A")
        self.assertEqual(wd.check_stalled_agents(now_monotonic=10_000.0), [])

    def test_base_agent_loop_records_heartbeat_and_stop_forgets_it(self):
        from agents.base_agent import BaseAgent

        class _Dummy(BaseAgent):
            async def run_cycle(self):
                pass

        async def _scenario():
            agent = _Dummy("WiringDummy", interval_sec=300.0)
            await agent.start()
            await asyncio.sleep(0.05)
            wd = get_runtime_watchdog()
            self.assertIn("WiringDummy", wd._heartbeats)
            self.assertEqual(wd._silence_limits["WiringDummy"], 900.0)
            await agent.stop()
            self.assertNotIn("WiringDummy", wd._heartbeats)

        asyncio.run(_scenario())

    def test_monitor_reports_each_stall_once_and_recovery(self):
        from agents.monitor_agent import MonitorAgent
        m = MonitorAgent.__new__(MonitorAgent)
        m.name = "MonitorAgent"
        m._stalled_reported = set()
        wd = get_runtime_watchdog()
        wd.record_heartbeat("GhostAgent", now_monotonic=time.monotonic() - 1000.0, interval_sec=1.0)
        try:
            with mock.patch("agents.monitor_agent.logger") as log:
                m._report_stalled_agents()
                m._report_stalled_agents()  # الدورة الثانية لا تكرر البلاغ
                self.assertEqual(log.error.call_count, 1)
                wd.record_heartbeat("GhostAgent", interval_sec=1.0)
                m._report_stalled_agents()
                self.assertEqual(log.info.call_count, 1)
        finally:
            wd.forget_heartbeat("GhostAgent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
