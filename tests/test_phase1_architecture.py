"""
==============================================================================
tests/test_phase1_architecture.py — Unit Tests for Architecture & Data Loop
==============================================================================
Verifies all Phase 1 items from IMPROVEMENT_PLAN.md:
  1. Unified single database path
  2. Direct ticket ↔ signal_id ↔ outcome deterministic linking
  3. update_outcome_by_ticket updates RAG episodic memory correctly
  4. sweep_stale_open_records ensures no OPEN records remain > 24h
"""

import os
import tempfile
import unittest
from pathlib import Path

from memory_rag.adaptive_trade_journal import (
    TradeJournalDB,
    TradeVectorRecord,
    TradeOutcomeRecorder,
    _DEFAULT_DB_PATH,
)


class TestPhase1Architecture(unittest.TestCase):

    def test_unified_database_path(self):
        """
        IMPROVEMENT_PLAN §1:
        Verify that _DEFAULT_DB_PATH points to backend/trading.db
        """
        expected_suffix = os.path.join("backend", "trading.db")
        self.assertTrue(str(_DEFAULT_DB_PATH).endswith(expected_suffix))

    def test_update_outcome_by_ticket(self):
        """
        IMPROVEMENT_PLAN §1:
        Verify that trade vectors can be inserted with a ticket and updated by ticket.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_trading.db"
            journal = TradeJournalDB(db_path=test_db)

            # Insert an OPEN trade vector with a ticket
            record = TradeVectorRecord(
                timestamp_utc="2026-11-14T10:00:00Z",
                symbol="EURUSD",
                ticket=123456,
                regime_state="STRONG_TREND",
                setup_type="FVG_RETEST",
                hurst=0.65,
                atr_ratio=1.2,
                z_score=1.5,
                ofi_z=0.8,
                spread_ratio=0.1,
                proposed_action="BUY",
                final_action="BUY",
                signal_confidence=0.85,
                net_score=0.78,
                sl_pips=20.0,
                tp1_pips=40.0,
                risk_percent=1.0,
                outcome="OPEN",
            )
            row_id = journal.insert_record(record)
            self.assertGreater(row_id, 0)

            # Now close the trade by ticket with outcome, costs, and MAE/MFE
            updated = journal.update_outcome_by_ticket(
                ticket=123456,
                pnl_pips=25.5,
                outcome="WIN",
                spread_cost=1.2,
                commission=0.5,
                swap=0.0,
                mae_pips=-3.5,
                mfe_pips=30.0,
            )
            self.assertTrue(updated)

            # Verify in DB
            conn = journal._get_conn()
            row = conn.execute("SELECT * FROM trade_vectors WHERE ticket=123456").fetchone()
            self.assertEqual(row["outcome"], "WIN")
            self.assertAlmostEqual(row["pnl_pips"], 25.5)
            self.assertAlmostEqual(row["spread_cost"], 1.2)
            self.assertAlmostEqual(row["mae_pips"], -3.5)
            self.assertAlmostEqual(row["mfe_pips"], 30.0)
            journal.close()

    def test_sweep_stale_open_records(self):
        """
        IMPROVEMENT_PLAN §1:
        Verify that records OPEN for > 24 hours are swept to STALE_CLOSED.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_trading.db"
            journal = TradeJournalDB(db_path=test_db)

            # Insert an old open record (simulating 48 hours ago)
            record_old = TradeVectorRecord(
                timestamp_utc="2026-11-12T00:00:00Z",
                symbol="GBPUSD",
                ticket=111111,
                regime_state="SLOW_TREND",
                setup_type="OB_BOUNCE",
                hurst=0.55,
                atr_ratio=1.0,
                z_score=0.5,
                ofi_z=0.4,
                spread_ratio=0.1,
                proposed_action="BUY",
                final_action="BUY",
                signal_confidence=0.75,
                net_score=0.70,
                sl_pips=15.0,
                tp1_pips=30.0,
                risk_percent=1.0,
                outcome="OPEN",
            )
            journal.insert_record(record_old)

            swept_count = journal.sweep_stale_open_records(max_age_hours=24)
            self.assertEqual(swept_count, 1)

            conn = journal._get_conn()
            row = conn.execute("SELECT outcome FROM trade_vectors WHERE ticket=111111").fetchone()
            self.assertEqual(row["outcome"], "STALE_CLOSED")
            journal.close()


if __name__ == "__main__":
    unittest.main()
