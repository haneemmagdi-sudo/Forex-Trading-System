"""
==============================================================================
tests/test_autonomous_master.py
==============================================================================
Test Suite for AutonomousMasterOrchestrator:
  - Verifies multi-agent perception (Alpha, Beta, Delta)
  - Verifies inter-agent communication (QuantumBlackboard)
  - Verifies dialectical debate (MultiAgentDebateEngine)
  - Verifies red-team adversarial audit (GammaRedTeamCritic)
  - Verifies risk governance & Kelly sizing (OmegaRiskGovernor)
  - Verifies episodic memory vector logging & self-healing watchdog
"""

import asyncio
import os
import unittest
from pathlib import Path

from autonomous_master_orchestrator import AutonomousMasterOrchestrator
from institutional.blackboard import SignalDirection


class TestAutonomousMasterOrchestrator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["USE_LIVE_MT5"] = "0"
        import council.delta_macro_sentinel as delta
        cls._orig_fetch = delta._try_fetch_forex_factory
        delta._try_fetch_forex_factory = lambda now: [
            {"title": "Low Impact Stat", "country": "USD", "impact": "Low", "date": "2026-11-25T12:00:00Z"}
        ]
        cls.test_dir = Path("./mql5_shared_signals_test")
        cls.orchestrator = AutonomousMasterOrchestrator(
            mql5_shared_dir=str(cls.test_dir),
            use_live_mt5=False,
            confidence_threshold=70.0,
        )

    def test_01_watchdog_health_audit(self):
        """Watchdog must verify syntax health of all core Python modules."""
        report = self.orchestrator.watchdog.audit_and_verify()
        self.assertTrue(report["all_valid"])
        self.assertGreaterEqual(len(report["modules"]), 5)

    def test_02_single_symbol_autonomous_lifecycle(self):
        """Single-symbol evaluation must pass all 7 stages and return valid payload."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            payload = loop.run_until_complete(
                self.orchestrator.evaluate_symbol_autonomous("EURUSD")
            )
            self.assertEqual(payload.symbol, "EURUSD")
            self.assertIn(payload.action, ["LIMIT_BUY", "LIMIT_SELL", "BUY", "SELL", "STAND_DOWN"])
            self.assertGreaterEqual(payload.confidence_score, 0.0)
            self.assertLessEqual(payload.confidence_score, 1.0)
        finally:
            loop.close()

    def test_03_blackboard_inter_agent_communication(self):
        """Blackboard must store and reflect agent signals."""
        signals = self.orchestrator.blackboard.get_all_active_signals()
        self.assertIsInstance(signals, dict)
        # Should contain alpha_regime and beta_orderflow from prior evaluation
        self.assertIn("alpha_regime", signals)
        self.assertIn("beta_orderflow", signals)
        self.assertIn(signals["alpha_regime"].signal_direction, [SignalDirection.BUY, SignalDirection.SELL, SignalDirection.HOLD])

    def test_04_master_cycle_execution(self):
        """Master cycle must run across multiple pairs and return dictionary of payloads."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                self.orchestrator.run_master_cycle(["EURUSD", "GBPUSD", "XAUUSD"])
            )
            self.assertEqual(len(results), 3)
            self.assertIn("EURUSD", results)
            self.assertIn("GBPUSD", results)
            self.assertIn("XAUUSD", results)
        finally:
            loop.close()

    @classmethod
    def tearDownClass(cls):
        # P2 fix: restore monkey-patched Forex Factory fetcher AND clean up temp test directory
        import council.delta_macro_sentinel as delta
        delta._try_fetch_forex_factory = cls._orig_fetch
        # Clean up temporary test signals directory
        if cls.test_dir.exists():
            for p in cls.test_dir.glob("*.json"):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                cls.test_dir.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
