"""
tests/test_bus_priority_and_reflection.py — اختبارات الدفعة الثانية (2026)
==========================================================================
تتحقق من:
  1. SignalBus: طابور الأولويات الحقيقي (dd_alert priority=2 يسبق signal priority=1 و analysis priority=0)
     مع FIFO داخل نفس الأولوية، وأولوية تنفيذ المشتركين (subscriber priority).
  2. CouncilStateBridge: نقل dd_alert و news_alert و meta_learning_update و champion_rollback
     إلى سياق حي يستهلكه OmegaRiskGovernor.
  3. ReflectionMemoryReader: القراءة الفعلية من جدول SQLite `agent_reflections` وحساب
     عقوبات الثقة والعتبة والتبريد المؤقت (4 خسائر متتالية خلال 48 ساعة) مع الكاش وإلغائه.
  4. التكامل الكامل في MarketAnalystAgent و OmegaRiskGovernor.
"""
import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.signal_bus import SignalBus, BusMessage
from core.reflection_memory import ReflectionMemoryReader
from agents.market_analyst import MarketAnalystAgent
from council.alpha_regime_agent import RegimeOutput, RegimeState
from council.beta_orderflow_agent import OrderFlowProposal
from council.gamma_redteam_critic import CriticAssessment
from council.omega_risk_governor import OmegaRiskGovernor


class TestSignalBusPriorityAndBridge(unittest.TestCase):
    def test_priority_queue_dispatches_emergency_before_normal_with_fifo(self):
        bus = SignalBus()
        order = []
        bus.subscribe("*", lambda m: order.append((m.topic, m.priority, m.data.get("id"))))

        msgs = [
            BusMessage(topic="analysis", sender="A", priority=0, data={"id": "n1"}),
            BusMessage(topic="signal", sender="A", priority=1, data={"id": "h1"}),
            BusMessage(topic="analysis", sender="A", priority=0, data={"id": "n2"}),
            BusMessage(topic="dd_alert", sender="M", priority=2, data={"id": "e1"}),
            BusMessage(topic="news_alert", sender="N", priority=2, data={"id": "e2"}),
            BusMessage(topic="trade_closed", sender="M", priority=1, data={"id": "h2"}),
        ]
        count = asyncio.run(bus.publish_batch(msgs))
        self.assertEqual(count, 6)
        self.assertEqual(
            [x[2] for x in order],
            ["e1", "e2", "h1", "h2", "n1", "n2"],
        )

    def test_subscriber_priority_runs_critical_handler_first(self):
        bus = SignalBus()
        seq = []
        bus.subscribe("dd_alert", lambda m: seq.append("logger"), priority=0)
        bus.subscribe("dd_alert", lambda m: seq.append("risk_kill_switch"), priority=2)
        bus.subscribe("dd_alert", lambda m: seq.append("monitor_sync"), priority=1)

        asyncio.run(bus.publish(BusMessage(topic="dd_alert", sender="M", priority=2, data={"dd_pct": 5.5})))
        self.assertEqual(seq, ["risk_kill_switch", "monitor_sync", "logger"])

    def test_council_state_bridge_propagates_live_bus_events(self):
        bus = SignalBus()
        bridge = bus.attach_council_bridge()

        async def _emit():
            await bus.publish(BusMessage(
                topic="meta_learning_update", sender="LearningAgent", priority=1,
                data={"regime_threshold_shifts": {"STRONG_TREND": 5.0}},
            ))
            await bus.publish(BusMessage(
                topic="news_alert", sender="NewsAgent", priority=2,
                data={"impact": "HIGH", "recommendation": "AVOID_NEW_TRADES", "related_symbols": ["EURUSD"]},
            ))
            await bus.publish(BusMessage(
                topic="dd_alert", sender="MonitorAgent", priority=2,
                data={"dd_pct": 5.2, "mode": "EMERGENCY_STOP"},
            ))
            await bus.publish(BusMessage(
                topic="champion_rollback", sender="LearningAgent", priority=1,
                data={"version": 3, "reason": "early_losses"},
            ))

        asyncio.run(_emit())
        ctx = bridge.get_council_context("EURUSD", "STRONG_TREND")
        self.assertTrue(ctx["emergency_dd_active"])
        self.assertTrue(ctx["news_blackout"])
        self.assertAlmostEqual(ctx["bus_threshold_shift"], 0.05, places=4)
        self.assertTrue(ctx["recent_rollback"])
        self.assertEqual(ctx["champion_version"], 3)


class TestReflectionMemoryReader(unittest.TestCase):
    def _create_db(self, path: Path, rows):
        conn = sqlite3.connect(str(path))
        conn.execute(
            """
            CREATE TABLE agent_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_ticket INTEGER,
                symbol TEXT,
                fsm_regime TEXT,
                council_would_block INTEGER,
                outcome_pnl REAL,
                outcome TEXT,
                created_at TEXT
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

    def test_sqlite_reflection_reader_computes_penalties_and_cooldown(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "trading.db"
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            # 4 خسائر متتالية على EURUSD/STRONG_TREND (مع حالتين كان المجلس سيمنعهما)
            rows = [
                (1, "EURUSD", "STRONG_TREND", 1, -10.0, "LOSS", now_iso),
                (2, "EURUSD", "STRONG_TREND", 1, -8.0, "LOSS", now_iso),
                (3, "EURUSD", "STRONG_TREND", 0, -6.0, "LOSS", now_iso),
                (4, "EURUSD", "STRONG_TREND", 0, -5.0, "LOSS", now_iso),
                # زوج آخر رابح لا يتأثر
                (5, "GBPUSD", "STRONG_TREND", 0, 15.0, "WIN", now_iso),
            ]
            self._create_db(db_path, rows)

            reader = ReflectionMemoryReader(db_path=db_path, cooldown_consecutive_losses=4)
            adv_eur = reader.evaluate_pair_regime("EURUSD", "STRONG_TREND")
            adv_gbp = reader.evaluate_pair_regime("GBPUSD", "STRONG_TREND")

            self.assertTrue(adv_eur.temporary_cooldown)
            self.assertEqual(adv_eur.consecutive_losses, 4)
            self.assertEqual(adv_eur.veto_saved_losses, 2)
            self.assertGreater(adv_eur.confidence_penalty, 0.0)
            self.assertGreater(adv_eur.threshold_penalty, 0.0)

            self.assertFalse(adv_gbp.temporary_cooldown)
            self.assertEqual(adv_gbp.confidence_penalty, 0.0)


class TestMarketAnalystAndOmegaReflectionIntegration(unittest.TestCase):
    def test_market_analyst_blocks_signal_on_reflection_cooldown(self):
        class _DummyMT5:
            data_source = "TEST"
            def get_ohlcv(self, symbol, bars=200): return [1] * 80
            def get_tick(self, symbol): return {"spread": 1.0}

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "trading.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE agent_reflections (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, fsm_regime TEXT, council_would_block INTEGER, outcome_pnl REAL, outcome TEXT, created_at TEXT)"
            )
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            for _ in range(4):
                conn.execute(
                    "INSERT INTO agent_reflections (symbol, fsm_regime, council_would_block, outcome_pnl, outcome, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("EURUSD", "STRONG_TREND", 1, -12.0, "LOSS", now_iso),
                )
            conn.commit()
            conn.close()

            ma = MarketAnalystAgent(_DummyMT5())
            ma.reflection_reader = ReflectionMemoryReader(db_path=db_path, cooldown_consecutive_losses=4)

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
            high_vote = SimpleNamespace(
                direction="BUY", signal_strong=True, confidence=90.0,
                to_dict=lambda: {"direction": "BUY", "confidence": 90.0},
            )
            ma.indicators.calculate = lambda df, sp: dummy_iv
            ma.fsm.detect = lambda iv: dummy_fsm
            ma.voting.vote = lambda iv, fsm: high_vote

            asyncio.run(ma._analyze_symbol("EURUSD"))
            self.assertEqual(len(emitted), 0)
            self.assertIn("REFLECTION_COOLDOWN", rejections)

    def test_omega_governor_enforces_bus_emergency_and_reflection_penalties(self):
        gov = OmegaRiskGovernor()
        regime = RegimeOutput(
            symbol="EURUSD", regime_state=RegimeState.TRENDING_LOW_VOL,
            regime_confidence=0.92, hurst_exponent=0.66, atr_ratio=1.1,
            atr_points=100.0, rolling_z_score=0.7, directional_bias="BULLISH",
            rationale="trend", diagnostics={},
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

        # 1. بدون طوارئ → قبول
        ok = gov.adjudicate(regime, proposal, critic)
        self.assertEqual(ok.action, "LIMIT_BUY")

        # 2. طوارئ DD من SignalBus → فيتو فوري STAND_DOWN
        veto_dd = gov.adjudicate(regime, proposal, critic, bus_context={"emergency_dd_active": True})
        self.assertEqual(veto_dd.action, "STAND_DOWN")
        self.assertIn("BUS EMERGENCY DD", veto_dd.critic_notes)

        # 3. تبريد ذاكرة التأمل → فيتو فوري STAND_DOWN
        veto_refl = gov.adjudicate(
            regime, proposal, critic,
            reflection_advisory={"temporary_cooldown": True, "summary": "COOLDOWN(4 losses)"},
        )
        self.assertEqual(veto_refl.action, "STAND_DOWN")
        self.assertIn("REFLECTION COOLDOWN", veto_refl.critic_notes)

        # 4. عقوبة تأمّل + تشديد Bus ترفع العتبة الديناميكية فوق 0.778 → رفض منضبط
        tight = gov.adjudicate(
            regime, proposal, critic,
            reflection_advisory={"temporary_cooldown": False, "threshold_penalty": 0.05},
            bus_context={"bus_threshold_shift": 0.04},
        )
        self.assertGreater(tight.approval_threshold_used, ok.approval_threshold_used)
        self.assertEqual(tight.action, "STAND_DOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
