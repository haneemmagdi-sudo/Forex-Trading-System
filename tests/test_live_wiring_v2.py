"""
tests/test_live_wiring_v2.py — اختبارات الدفعة الثانية من «التوصيل الحي» (2026)
================================================================================
  1. ميزة ATR مستقرة (٪ من السعر) ومطابقة بين التدريب والتنبؤ.
  2. مفاتيح الإعداد التي كانت «زخرفية» صارت تحكم السلوك فعلاً (beta/gamma/omega/self-healing/reflection).
  3. AlphaDecayGuard: استمرارية الحالة، منع تسجيل الصفقة مرتين، وتنفيذ فعلي للتحويل للظل.
  4. قياس زمن التنفيذ واستعادة MT5 دون تحويل صامت إلى yfinance.
  5. طابور الأولويات: مسار المنتجين الحيين للتنبيهات.
"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.runtime_resilience import (  # noqa: E402
    AlphaDecayGuard,
    RuntimeResilienceWatchdog,
    load_self_healing_config,
)
from core.signal_bus import BusMessage, SignalBus  # noqa: E402


def _feat(price, atr):
    from agents.learning_agent import LearningAgent
    return LearningAgent.build_stationary_feature_vector(
        buy_score=60, sell_score=20, confidence=70, price=price,
        ema_value=price, rsi_value=55, macd_value=0.0, adx_value=25, atr_value=atr,
    )


class TestAtrFeature(unittest.TestCase):
    def test_atr_feature_is_percent_of_price_and_scale_invariant(self):
        eur, xau = _feat(1.10, 0.0011), _feat(2000.0, 2.0)
        self.assertAlmostEqual(eur[-1], 0.1, places=4)
        self.assertAlmostEqual(eur[-1], xau[-1], places=4)

    def test_atr_feature_missing_or_bad_price_is_zero_and_clamped(self):
        self.assertEqual(_feat(None, 1.0)[-1], 0.0)
        self.assertEqual(_feat(1.1, 0.0)[-1], 0.0)
        self.assertEqual(_feat(1.0, 100.0)[-1], 5.0)


class TestConfigIsNoLongerDecorative(unittest.TestCase):
    def _patched_block(self, name, **overrides):
        import council.tuning as tuning
        block = dict(tuning.get_block(name))
        block.update(overrides)
        return mock.patch.dict(tuning._cache, {name: block})

    def test_tuning_reads_real_config_and_degrades_to_empty(self):
        import council.tuning as tuning
        self.assertEqual(tuning.get_value("ENTRY_UPGRADES_2026", "ofi_counter_flow_z", None), 1.8)
        self.assertEqual(tuning.get_block("NO_SUCH_BLOCK"), {})

    def test_beta_and_gamma_take_values_from_config(self):
        from council.beta_orderflow_agent import BetaOrderFlowAgent
        from council.gamma_redteam_critic import GammaRedTeamCritic
        with self._patched_block(
            "ENTRY_UPGRADES_2026", fvg_min_atr_ratio=0.33, ofi_counter_flow_z=2.4,
            episodic_top_k=7, episodic_half_life_days=3.0, memory_cb_atr_ratio=9.0, memory_cb_min_regime_conf=0.8,
        ):
            beta = BetaOrderFlowAgent(point_value=0.00001)
            gamma = GammaRedTeamCritic()
        self.assertEqual((beta._fvg_min_atr_ratio, beta._ofi_counter_flow_z), (0.33, 2.4))
        self.assertEqual((gamma._top_k, gamma._half_life_days, gamma._cb_atr_ratio, gamma._cb_min_regime_conf),
                         (7, 3.0, 9.0, 0.8))

    def test_omega_calibrated_fusion_weight_comes_from_config(self):
        from council.omega_risk_governor import OmegaRiskGovernor
        from tests.test_entry_signal_upgrades_2026 import TestOmegaGovernor2026V2
        regime, proposal, critic = TestOmegaGovernor2026V2()._sample_inputs()
        gov = OmegaRiskGovernor()
        with self._patched_block("ENTRY_UPGRADES_2026", calibrated_fusion_weight=0.0):
            self.assertEqual(gov.adjudicate(regime, proposal, critic, calibrated_p_win=0.48).action, "LIMIT_BUY")
        with self._patched_block("ENTRY_UPGRADES_2026", calibrated_fusion_weight=1.0):
            self.assertEqual(gov.adjudicate(regime, proposal, critic, calibrated_p_win=0.48).action, "STAND_DOWN")

    def test_self_healing_values_reach_watchdog_and_guard(self):
        cfg = {"heartbeat_max_silence_sec": 90.0, "latency_spike_ms": 700.0, "mt5_max_reconnect_attempts": 5,
               "mt5_reconnect_cooldown_sec": 12.0, "ph_delta": 0.2, "ph_threshold": 7.0, "ph_min_samples": 15}
        wd = RuntimeResilienceWatchdog.from_config(cfg)
        self.assertEqual((wd.heartbeat_max_silence_sec, wd.latency_spike_ms, wd.max_reconnect_attempts,
                          wd.reconnect_cooldown_sec), (90.0, 700.0, 5, 12.0))
        g = AlphaDecayGuard.from_config(cfg=cfg)
        self.assertEqual((g.delta, g.threshold, g.min_samples), (0.2, 7.0, 15))
        self.assertEqual(load_self_healing_config()["ph_threshold"], 4.0)  # القراءة الحرفية من backend/config.py

    def test_reflection_reader_from_config(self):
        import main_orchestrator as mo
        with self._patched_block("COMMUNICATION_REFLECTION_2026", reflection_max_omega_penalty=0.05,
                                 reflection_lookback_days=3):
            reader = mo.make_reflection_reader()
        self.assertEqual((reader.max_omega_penalty, reader.lookback_days), (0.05, 3))


class TestSuggestModeAssertion(unittest.TestCase):
    def test_non_suggest_agent_is_refused_when_flag_true(self):
        import autonomous_master_orchestrator as amo
        from institutional.code_healing_agent import AgentExecutionMode
        fake = SimpleNamespace(mode=AgentExecutionMode.AUTONOMOUS_SANDBOX)
        with mock.patch.object(amo.CodeHealingAgent, "for_http_api", return_value=fake):
            with self.assertRaises(RuntimeError):
                amo.SelfHealingWatchdog(Path(ROOT))


class TestAlphaGuardPersistenceAndEnforcement(unittest.TestCase):
    def _drift(self, guard, key="EURUSD", start=0):
        for i in range(12):
            guard.record_trade(key, 20.0, deal_id=start + i)
        for i in range(10):
            guard.record_trade(key, -30.0, deal_id=start + 100 + i)

    def test_state_and_demotion_survive_a_new_process(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "g.json"
            g1 = AlphaDecayGuard(); g1.enable_persistence(path); self._drift(g1)
            self.assertTrue(g1.is_demoted("EURUSD"))
            g2 = AlphaDecayGuard(); g2.enable_persistence(path)
            self.assertTrue(g2.is_demoted("EURUSD"))
            self.assertEqual(g2._detectors["EURUSD"].n, 22)

    def test_same_deal_is_never_counted_twice_across_runs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "g.json"
            g1 = AlphaDecayGuard(); g1.enable_persistence(path)
            for i in range(5):
                g1.record_trade("EURUSD", -5.0, deal_id=i)
            g2 = AlphaDecayGuard(); g2.enable_persistence(path)  # تشغيل جديد يعيد قراءة نفس الصفقات
            for i in range(5):
                g2.record_trade("EURUSD", -5.0, deal_id=i)
            self.assertEqual(g2._detectors["EURUSD"].n, 5)

    def test_promote_back_is_persisted_and_corrupt_state_starts_clean(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "g.json"
            g1 = AlphaDecayGuard(); g1.enable_persistence(path); self._drift(g1)
            g1.promote_back("EURUSD")
            g2 = AlphaDecayGuard(); g2.enable_persistence(path)
            self.assertFalse(g2.is_demoted("EURUSD"))
            path.write_text("{not json", encoding="utf-8")
            g3 = AlphaDecayGuard(); g3.enable_persistence(path)
            self.assertEqual(g3.demoted_keys(), [])

    def test_demoted_symbol_gets_stand_down_from_the_live_orchestrator(self):
        import autonomous_master_orchestrator as amo
        from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
        with tempfile.TemporaryDirectory() as td:
            orch = None
            try:
                with mock.patch.object(amo, "TradeOutcomeRecorder", lambda: TradeOutcomeRecorder(db_path=Path(td) / "j.db")):
                    orch = amo.AutonomousMasterOrchestrator(mql5_shared_dir=str(Path(td) / "s"), use_live_mt5=False)
                guard = orch.watchdog.alpha_guard
                guard.enable_persistence(Path(td) / "g.json")
                self._drift(guard, "EURUSD")
                res = asyncio.run(orch.evaluate_symbol_autonomous("EURUSD"))
                self.assertEqual(res.action, "STAND_DOWN")
                self.assertIn("ALPHA DECAY", res.critic_notes)
                res2 = asyncio.run(orch.evaluate_symbol_autonomous("GBPUSD"))
                self.assertNotIn("ALPHA DECAY", res2.critic_notes)
            finally:
                if orch is not None:
                    orch.recorder._db.close()

    def test_audit_report_states_how_many_agents_are_monitored(self):
        import autonomous_master_orchestrator as amo
        wd = amo.SelfHealingWatchdog(Path(ROOT))
        wd.alpha_guard._state_path = None
        self.assertEqual(wd.audit_and_verify()["monitored_agents"], 0)


class TestLatencyAndMt5Recovery(unittest.TestCase):
    def test_order_send_latency_is_fed_to_the_watchdog(self):
        import core.mt5_connector as mc
        wd = RuntimeResilienceWatchdog(latency_spike_ms=100.0)
        fake_mt5 = SimpleNamespace(order_send=lambda req: "ok")
        with mock.patch.object(mc, "mt5", fake_mt5, create=True), mock.patch.object(mc, "get_runtime_watchdog", return_value=wd), \
                mock.patch.object(mc.time, "perf_counter", side_effect=[0.0, 5.0]):
            self.assertEqual(mc.MT5Connector()._timed_order_send({}), "ok")
        self.assertEqual(wd._consecutive_latency_spikes, 1)

    def test_reconnect_never_downgrades_live_connector_to_yfinance(self):
        import core.mt5_connector as mc
        conn = mc.MT5Connector()
        conn._use_yfinance = False
        with mock.patch.object(mc, "MT5_AVAILABLE", True), mock.patch.object(mc, "mt5", SimpleNamespace(shutdown=lambda: None), create=True), \
                mock.patch.object(conn, "_connect_mt5", return_value=False):
            self.assertFalse(conn.reconnect())
        self.assertFalse(conn.connected)
        self.assertFalse(conn._use_yfinance)

    def test_reconnect_is_noop_in_yfinance_mode(self):
        import core.mt5_connector as mc
        conn = mc.MT5Connector()
        conn._use_yfinance = True
        with mock.patch.object(conn, "_connect_mt5") as c:
            self.assertFalse(conn.reconnect())
        c.assert_not_called()

    def test_monitor_recovers_after_three_spikes_then_respects_cooldown(self):
        import agents.monitor_agent as ma
        wd = RuntimeResilienceWatchdog(latency_spike_ms=100.0, reconnect_cooldown_sec=3600.0)
        calls = []

        class _Conn:
            connected = True
            def refresh_connection_state(self): pass
            def reconnect(self):
                calls.append(1); return True

        fake_self = SimpleNamespace(mt5=_Conn())
        with mock.patch.object(ma, "get_runtime_watchdog", return_value=wd):
            ma.MonitorAgent._recover_mt5_if_needed(fake_self)
            self.assertEqual(calls, [])                      # سليم: لا إعادة اتصال
            for _ in range(3):
                wd.record_execution_latency(5000.0)
            ma.MonitorAgent._recover_mt5_if_needed(fake_self)
            self.assertEqual(len(calls), 1)
            for _ in range(3):
                wd.record_execution_latency(5000.0)
            ma.MonitorAgent._recover_mt5_if_needed(fake_self)
            self.assertEqual(len(calls), 1)                  # التهدئة تمنع التكرار

    def test_monitor_skips_connectors_without_recovery_support(self):
        import agents.monitor_agent as ma
        ma.MonitorAgent._recover_mt5_if_needed(SimpleNamespace(mt5=object()))  # لا يرمي


class TestAlertDispatch(unittest.TestCase):
    def test_without_dispatcher_alert_is_published_directly(self):
        async def run():
            bus, got = SignalBus(), []
            bus.subscribe("dd_alert", lambda m: got.append(m.data["dd_pct"]))
            await bus.emit_dd_alert("t", 7.5, "SOFT_STOP")
            return got
        self.assertEqual(asyncio.run(run()), [7.5])

    def test_with_dispatcher_alert_goes_through_priority_queue_first(self):
        async def run():
            bus, order = SignalBus(), []
            bus.subscribe("*", lambda m: order.append(m.topic))
            task = bus.start_dispatcher()
            await asyncio.sleep(0)                      # يتيح للموزّع الدخول في انتظاره
            bus.enqueue(BusMessage(topic="agent_log", sender="t", priority=0, data={}))
            await bus.emit_dd_alert("t", 7.5, "SOFT_STOP")
            queued_not_delivered = order == []          # دخل الطابور ولم يُنشر مباشرة
            await asyncio.sleep(0.05)
            await bus.stop_dispatcher()
            return queued_not_delivered, order
        queued, order = asyncio.run(run())
        self.assertTrue(queued)
        self.assertEqual(order, ["dd_alert", "agent_log"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
