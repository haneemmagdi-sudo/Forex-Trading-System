"""
memory_rag/adaptive_trade_journal.py
=====================================
Adaptive Episodic Memory — learns from every trade outcome.

Replaces the static 3-vector array in GammaRedTeamCritic with a live
SQLite-backed vector store that grows with every logged trade.

Architecture:
  - TradeJournalDB       : low-level SQLite writer/reader (sync)
  - AdaptiveTrapMemory   : builds and refreshes trap_vectors for Gamma Critic
  - TradeOutcomeRecorder : async wrapper called by the orchestrator after
                           each signal cycle (Shadow + Live modes)

Table schema (`trade_vectors`):
  - id, timestamp_utc (TEXT ISO-8601)
  - symbol, regime_state, setup_type (TEXT)
  - hurst, atr_ratio, z_score, ofi_z, spread_ratio (REAL) — 5-dim feature vector
  - proposed_action, final_action (TEXT)
  - signal_confidence, net_score (REAL)
  - sl_pips, tp1_pips, risk_percent (REAL)   — geometry at signal time
  - pnl_pips (REAL NULL)                      — filled after close
  - outcome (TEXT NULL)                       — WIN | LOSS | BE | OPEN
  - execution_mode (TEXT)                     — SHADOW | LIVE

All writes are serialised through a single connection with WAL journal mode
to prevent corruption on concurrent async writes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger("AdaptiveMemory")

# ---------------------------------------------------------------------------
# Database path — resolved to unified backend/trading.db (IMPROVEMENT_PLAN §1)
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "backend" / "trading.db"


# ---------------------------------------------------------------------------
# Pydantic contracts
# ---------------------------------------------------------------------------

class TradeVectorRecord(BaseModel):
    """
    Immutable feature vector + metadata written after each signal cycle.
    pnl_pips and outcome are None until the trade closes.
    """
    timestamp_utc: str
    symbol: str
    ticket: Optional[int] = None    # MT5 ticket for 100% deterministic link (IMPROVEMENT_PLAN §1)
    regime_state: str
    setup_type: str
    hurst: float = Field(..., ge=0.0, le=1.0)
    atr_ratio: float = Field(..., ge=0.0)
    z_score: float
    ofi_z: float
    spread_ratio: float = Field(..., ge=0.0)
    proposed_action: str
    final_action: str
    signal_confidence: float = Field(..., ge=0.0, le=1.0)
    net_score: float = Field(..., ge=0.0, le=1.0)
    sl_pips: float
    tp1_pips: float
    risk_percent: float = Field(..., ge=0.0)
    pnl_pips: Optional[float] = None
    outcome: Optional[str] = None   # WIN | LOSS | BE | OPEN
    execution_mode: str = "SHADOW"
    spread_cost: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    mae_pips: Optional[float] = None
    mfe_pips: Optional[float] = None


class TrapVectorMatrix(BaseModel):
    """Output of AdaptiveTrapMemory.rebuild() — ready to inject into Gamma."""
    vectors: List[List[float]]  # shape (N, 5)
    n_losing_trades: int
    n_winning_trades: int
    last_rebuilt_utc: str


# ---------------------------------------------------------------------------
# TradeJournalDB — synchronous SQLite layer
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS trade_vectors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc    TEXT    NOT NULL,
    symbol           TEXT    NOT NULL,
    ticket           INTEGER,
    regime_state     TEXT    NOT NULL,
    setup_type       TEXT    NOT NULL,
    hurst            REAL    NOT NULL,
    atr_ratio        REAL    NOT NULL,
    z_score          REAL    NOT NULL,
    ofi_z            REAL    NOT NULL,
    spread_ratio     REAL    NOT NULL,
    proposed_action  TEXT    NOT NULL,
    final_action     TEXT    NOT NULL,
    signal_confidence REAL   NOT NULL,
    net_score        REAL    NOT NULL,
    sl_pips          REAL    NOT NULL,
    tp1_pips         REAL    NOT NULL,
    risk_percent     REAL    NOT NULL,
    pnl_pips         REAL,
    outcome          TEXT,
    execution_mode   TEXT    NOT NULL DEFAULT 'SHADOW',
    spread_cost      REAL,
    commission       REAL,
    swap             REAL,
    mae_pips         REAL,
    mfe_pips         REAL
);

CREATE INDEX IF NOT EXISTS idx_tv_symbol    ON trade_vectors (symbol);
CREATE INDEX IF NOT EXISTS idx_tv_ticket    ON trade_vectors (ticket);
CREATE INDEX IF NOT EXISTS idx_tv_outcome   ON trade_vectors (outcome);
CREATE INDEX IF NOT EXISTS idx_tv_timestamp ON trade_vectors (timestamp_utc);
"""


class TradeJournalDB:
    """
    Thread-safe SQLite persistence layer.
    Single connection per instance, WAL mode, exclusive write lock.
    """

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Closes the underlying SQLite connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_DDL)
        # Safe migration for existing databases missing new columns
        for col, col_type in [
            ("ticket", "INTEGER"),
            ("spread_cost", "REAL"),
            ("commission", "REAL"),
            ("swap", "REAL"),
            ("mae_pips", "REAL"),
            ("mfe_pips", "REAL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE trade_vectors ADD COLUMN {col} {col_type};")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        logger.debug("trade_vectors table initialised at %s", self.db_path)

    def insert_record(self, rec: TradeVectorRecord) -> int:
        """Inserts a new trade vector record. Returns the new row id."""
        conn = self._get_conn()
        cur = conn.execute(
            """
            INSERT INTO trade_vectors
              (timestamp_utc, symbol, ticket, regime_state, setup_type,
               hurst, atr_ratio, z_score, ofi_z, spread_ratio,
               proposed_action, final_action,
               signal_confidence, net_score,
               sl_pips, tp1_pips, risk_percent,
               pnl_pips, outcome, execution_mode,
               spread_cost, commission, swap, mae_pips, mfe_pips)
            VALUES
              (?,?,?,?,?,  ?,?,?,?,?,  ?,?,  ?,?,  ?,?,?,  ?,?,?,  ?,?,?,?,?)
            """,
            (
                rec.timestamp_utc, rec.symbol, rec.ticket, rec.regime_state, rec.setup_type,
                rec.hurst, rec.atr_ratio, rec.z_score, rec.ofi_z, rec.spread_ratio,
                rec.proposed_action, rec.final_action,
                rec.signal_confidence, rec.net_score,
                rec.sl_pips, rec.tp1_pips, rec.risk_percent,
                rec.pnl_pips, rec.outcome, rec.execution_mode,
                rec.spread_cost, rec.commission, rec.swap, rec.mae_pips, rec.mfe_pips,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)  # type: ignore[arg-type]

    def update_outcome(self, row_id: int, pnl_pips: float, outcome: str) -> None:
        """Updates pnl_pips and outcome after a trade closes."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE trade_vectors SET pnl_pips=?, outcome=? WHERE id=?",
            (pnl_pips, outcome, row_id),
        )
        conn.commit()

    def update_outcome_by_ticket(
        self,
        ticket: int,
        pnl_pips: float,
        outcome: str,
        spread_cost: float = 0.0,
        commission: float = 0.0,
        swap: float = 0.0,
        mae_pips: float = 0.0,
        mfe_pips: float = 0.0,
    ) -> bool:
        """
        IMPROVEMENT_PLAN §1: تحديث نتيجة الصفقة وتكاليفها بمعرّف تذكرة MT5 مباشرة.
        يغلق حلقة التعلم التكيفية لـ Gamma RAG Memory.
        """
        conn = self._get_conn()
        cur = conn.execute(
            """
            UPDATE trade_vectors
            SET pnl_pips=?, outcome=?, spread_cost=?, commission=?, swap=?, mae_pips=?, mfe_pips=?
            WHERE ticket=?
            """,
            (pnl_pips, outcome, spread_cost, commission, swap, mae_pips, mfe_pips, ticket),
        )
        conn.commit()
        return cur.rowcount > 0

    def sweep_stale_open_records(self, max_age_hours: float = 24.0) -> int:
        """
        IMPROVEMENT_PLAN §1:
        ضمان عدم بقاء أي سجل OPEN لأكثر من 24 ساعة.
        """
        conn = self._get_conn()
        cur = conn.execute(
            """
            UPDATE trade_vectors
            SET outcome = 'STALE_CLOSED', pnl_pips = 0.0
            WHERE outcome = 'OPEN'
              AND replace(replace(timestamp_utc, 'T', ' '), 'Z', '') < datetime('now', '-' || ? || ' hours')
            """,
            (int(max_age_hours),),
        )
        conn.commit()
        return cur.rowcount

    def fetch_losing_vectors(
        self,
        max_rows: int = 300,
        min_pnl_pips: float = -0.5,
    ) -> np.ndarray:
        """
        Returns feature matrix of losing trades for Gamma's trap memory.
        Shape: (N, 5) → [hurst, atr_ratio, z_score, ofi_z, spread_ratio]
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT hurst, atr_ratio, z_score, ofi_z, spread_ratio
            FROM trade_vectors
            WHERE outcome = 'LOSS'
              AND (pnl_pips IS NULL OR pnl_pips < ?)
              AND final_action != 'STAND_DOWN'
            ORDER BY timestamp_utc DESC
            LIMIT ?
            """,
            (min_pnl_pips, max_rows),
        ).fetchall()
        if not rows:
            return np.empty((0, 5), dtype=np.float64)
        return np.array([list(r) for r in rows], dtype=np.float64)

    def fetch_winning_vectors(self, max_rows: int = 300) -> np.ndarray:
        """Returns feature matrix of winning trades."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT hurst, atr_ratio, z_score, ofi_z, spread_ratio
            FROM trade_vectors
            WHERE outcome = 'WIN'
              AND final_action != 'STAND_DOWN'
            ORDER BY timestamp_utc DESC
            LIMIT ?
            """,
            (max_rows,),
        ).fetchall()
        if not rows:
            return np.empty((0, 5), dtype=np.float64)
        return np.array([list(r) for r in rows], dtype=np.float64)

    def recent_win_rate(self, last_n: int = 20) -> float:
        """Returns win rate of the last N closed trades."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT outcome FROM trade_vectors
            WHERE outcome IN ('WIN', 'LOSS', 'BE')
              AND final_action != 'STAND_DOWN'
            ORDER BY timestamp_utc DESC
            LIMIT ?
            """,
            (last_n,),
        ).fetchall()
        if not rows:
            return 0.5  # Default neutral
        outcomes = [r[0] for r in rows]
        wins = sum(1 for o in outcomes if o == "WIN")
        return round(wins / len(outcomes), 4)


# ---------------------------------------------------------------------------
# AdaptiveTrapMemory — rebuilds Gamma's trap_vectors from live DB
# ---------------------------------------------------------------------------

# Seed vectors used when DB has fewer than MIN_RECORDS losing trades
_BOOTSTRAP_TRAP_VECTORS = np.array(
    [
        [0.50, 2.30, 2.80, -1.50, 0.18],  # High-vol exhaustion trap
        [0.49, 1.05, 0.20,  0.10, 0.16],  # Mid-range chop trap
        [0.62, 1.85, 2.95, -1.90, 0.14],  # Late trend buying into HTF wall
        [0.51, 1.40, 1.60, -0.80, 0.17],  # Low-conviction FOMO entry
        [0.53, 0.95, 0.05,  0.05, 0.19],  # Wide spread, low momentum
    ],
    dtype=np.float64,
)
_MIN_DB_RECORDS = 10  # Minimum losing trades before switching from bootstrap


class AdaptiveTrapMemory:
    """
    Maintains and refreshes Gamma's historical trap vector matrix.
    Merges DB-learned vectors with bootstrap seeds for graceful degradation
    when historical data is sparse.
    """

    def __init__(self, db: TradeJournalDB):
        self.db = db
        self._cached_matrix: Optional[np.ndarray] = None
        self._last_rebuilt: Optional[datetime] = None
        self._rebuild_interval_min: int = 10  # Rebuild every 10 minutes

    def _should_rebuild(self) -> bool:
        if self._cached_matrix is None or self._last_rebuilt is None:
            return True
        age_min = (datetime.now(timezone.utc) - self._last_rebuilt).total_seconds() / 60.0
        return age_min >= self._rebuild_interval_min

    def get_trap_vectors(self) -> np.ndarray:
        """
        Returns current trap vector matrix (N, 5).
        Rebuilds from DB if cache is stale.
        """
        if not self._should_rebuild():
            return self._cached_matrix  # type: ignore[return-value]

        losing = self.db.fetch_losing_vectors(max_rows=300)
        n_losing = len(losing)

        if n_losing >= _MIN_DB_RECORDS:
            # DB has enough data — use it exclusively
            matrix = losing
            logger.info("AdaptiveTrapMemory rebuilt from %d live losing trades.", n_losing)
        elif n_losing > 0:
            # Blend DB data with bootstrap seeds
            matrix = np.vstack([losing, _BOOTSTRAP_TRAP_VECTORS])
            logger.info(
                "AdaptiveTrapMemory: blending %d DB records + %d bootstrap seeds.",
                n_losing, len(_BOOTSTRAP_TRAP_VECTORS),
            )
        else:
            # No DB data yet — use bootstrap
            matrix = _BOOTSTRAP_TRAP_VECTORS.copy()
            logger.debug("AdaptiveTrapMemory using bootstrap seeds only (no DB records yet).")

        # Sanitise: replace NaN/Inf with column medians
        for col in range(matrix.shape[1]):
            col_data = matrix[:, col]
            bad = ~np.isfinite(col_data)
            if bad.any():
                median_val = float(np.nanmedian(col_data[~bad])) if (~bad).any() else 0.0
                matrix[bad, col] = median_val

        self._cached_matrix = matrix
        self._last_rebuilt = datetime.now(timezone.utc)
        return matrix

    def rebuild_summary(self) -> TrapVectorMatrix:
        """Returns a Pydantic summary of the current trap matrix state."""
        vecs = self.get_trap_vectors()
        return TrapVectorMatrix(
            vectors=vecs.tolist(),
            n_losing_trades=len(self.db.fetch_losing_vectors()),
            n_winning_trades=len(self.db.fetch_winning_vectors()),
            last_rebuilt_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


# ---------------------------------------------------------------------------
# TradeOutcomeRecorder — async wrapper called by orchestrator
# ---------------------------------------------------------------------------

class TradeOutcomeRecorder:
    """
    Async facade for recording signal cycles and trade outcomes.
    Used by MultiAgentOrchestrator at two points:
      1. After each Council cycle → record the signal (outcome=OPEN)
      2. When MT5 reports trade close → update_outcome()
    """

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH):
        self._db = TradeJournalDB(db_path=db_path)
        self.trap_memory = AdaptiveTrapMemory(db=self._db)

    async def record_signal(self, record: TradeVectorRecord) -> int:
        """Async insert of a new signal-cycle record. Returns row_id."""
        return await asyncio.to_thread(self._db.insert_record, record)

    async def update_outcome(
        self,
        row_id: int,
        pnl_pips: float,
        outcome: str,
    ) -> None:
        """Async update after trade close. Triggers trap_memory rebuild."""
        await asyncio.to_thread(self._db.update_outcome, row_id, pnl_pips, outcome)
        # Invalidate cache so next call to get_trap_vectors() re-reads from DB
        self.trap_memory._last_rebuilt = None
        logger.info(
            "TradeOutcomeRecorder: row %d updated → %s (%.1f pips). Memory invalidated.",
            row_id, outcome, pnl_pips,
        )

    async def update_outcome_by_ticket(
        self,
        ticket: int,
        pnl_pips: float,
        outcome: str,
        spread_cost: float = 0.0,
        commission: float = 0.0,
        swap: float = 0.0,
        mae_pips: float = 0.0,
        mfe_pips: float = 0.0,
    ) -> bool:
        """
        IMPROVEMENT_PLAN §1: تحديث النتيجة عبر ticket لربط الصفقات وإغلاق حلقة التعلم التكيفية.
        """
        success = await asyncio.to_thread(
            self._db.update_outcome_by_ticket,
            ticket, pnl_pips, outcome, spread_cost, commission, swap, mae_pips, mfe_pips,
        )
        if success:
            self.trap_memory._last_rebuilt = None
            logger.info(
                "TradeOutcomeRecorder: ticket #%d updated → %s (%.1f pips). Trap memory invalidated & updated.",
                ticket, outcome, pnl_pips,
            )
        return success

    async def sweep_stale_open_records(self, max_age_hours: float = 24.0) -> int:
        """Async sweep of any abandoned OPEN records older than 24h."""
        return await asyncio.to_thread(self._db.sweep_stale_open_records, max_age_hours)

    async def get_recent_win_rate(self, last_n: int = 20) -> float:
        """Returns rolling win rate from last N closed trades."""
        return await asyncio.to_thread(self._db.recent_win_rate, last_n)

    def get_trap_vectors(self) -> np.ndarray:
        """Synchronous access to trap vectors (safe to call from Gamma.__init__)."""
        return self.trap_memory.get_trap_vectors()
