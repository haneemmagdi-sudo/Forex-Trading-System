"""
==============================================================================
agents/planner_agent.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Master Planner Agent Orchestrator
Author : Principal AI Systems Architect
Version: 4.2.0

Overview
--------
Implements the ``QuantumPlannerAgent`` — the master orchestrator that runs at
the close of every price bar and translates the Consensus Engine's unified
verdict into a fully risk-validated, immutable execution mandate.

Decision Pipeline
-----------------
::

    ┌─────────────────────┐
    │   QuantumBlackboard  │  ← All 4 sub-models post signals here
    │  (shared memory)     │
    └─────────┬───────────┘
              │ get_all_active_signals()
    ┌─────────▼───────────┐
    │   ConsensusEngine   │  ← Computes weighted score → BUY/SELL/HOLD
    └─────────┬───────────┘
              │ ConsensusResult
    ┌─────────▼───────────┐
    │  QuantumPlannerAgent │  ← THIS MODULE
    │  1. Quorum check     │
    │  2. MT5 pre-flight   │
    │     risk validation  │
    │     a. DD check      │
    │     b. Free margin   │
    │  3. Grid spacing calc│
    │  4. Emit mandate     │
    └─────────┬───────────┘
              │ ExecutionMandate (immutable)
    ┌─────────▼───────────┐
    │  Execution Layer     │  ← Safe-execution gateway / MT5 broker
    └─────────────────────┘

MT5 Pre-Flight Risk Rules
-------------------------
The Planner performs two hard-stop checks before forwarding any BUY/SELL
mandate to the execution layer:

    Rule 1 — Drawdown Guard
        unrealized_drawdown% = (balance - equity) / balance × 100
        If unrealized_drawdown% > 5.0% → override to SAFETY_HOLD

    Rule 2 — Free Margin Guard
        If free_margin < required_margin_per_lot × min_lot_size → SAFETY_HOLD

    Any HOLD consensus from the engine also passes through the pipeline
    unchanged — no execution risk is incurred.

Grid Pro Spacing Metrics (Dynamic)
-----------------------------------
For BUY/SELL mandates that pass the risk gate, the Planner calculates
dynamic grid spacing bounds for the Grid Pro subsystem:

    base_spacing_pips : float
        ATR-derived base spacing (default: ATR × 1.5 in pips, minimum 15 pips)
    min_spacing_pips  : float
        50% of base spacing
    max_spacing_pips  : float
        200% of base spacing
    lot_size          : float
        Risk-adjusted lot size based on account balance and drawdown
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Internal project imports
# ---------------------------------------------------------------------------
from agents.blackboard import QuantumBlackboard, SignalPayload
from agents.consensus_engine import ConsensusAction, ConsensusEngine, ConsensusResult

# ---------------------------------------------------------------------------
# Conditional MT5 import — falls back gracefully when not installed
# ---------------------------------------------------------------------------
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE: bool = True
except ImportError:
    mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE: bool = False

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.planner_agent")


# ===========================================================================
# Constants
# ===========================================================================

# Maximum allowed unrealized drawdown before the safety hold is triggered
_MAX_DRAWDOWN_PCT: float = 5.0

# Minimum free margin threshold as a multiple of the required margin for
# a 0.01 lot trade. If free_margin < this ratio × margin_per_lot, halt.
_MIN_FREE_MARGIN_RATIO: float = 2.0

# ATR multiplier used to derive the grid base spacing in pips
_GRID_ATR_MULTIPLIER: float = 1.5

# Absolute minimum grid spacing in pips (floor regardless of ATR)
_GRID_MIN_SPACING_PIPS: float = 15.0

# Pip value in price units for 5-digit pairs (e.g., EURUSD)
_PIP_SIZE: float = 0.0001


# ===========================================================================
# Output Data Structures
# ===========================================================================

class MandateAction(str, Enum):
    """
    Final verified action embedded in the ``ExecutionMandate``.

    Values
    ------
    BUY          : Execute a long entry order.
    SELL         : Execute a short entry order.
    HOLD         : No new trade; preserve capital.
    SAFETY_HOLD  : Override due to MT5 risk pre-flight failure (DD or margin).
    """
    BUY         = "BUY"
    SELL        = "SELL"
    HOLD        = "HOLD"
    SAFETY_HOLD = "SAFETY_HOLD"


class OverrideReason(str, Enum):
    """
    Enumeration of possible override reasons logged in the mandate.

    Values
    ------
    NONE               : No override; the consensus action is transmitted as-is.
    DRAWDOWN_EXCEEDED  : Account unrealized DD > 5% — safety hold triggered.
    INSUFFICIENT_MARGIN: Free margin < minimum required — safety hold triggered.
    QUORUM_NOT_REACHED : Fewer than the minimum required agents have posted.
    MT5_UNAVAILABLE    : MetaTrader 5 could not be queried; safety hold applied.
    MT5_ACCOUNT_ERROR  : MT5 returned invalid account data (equity=0 or similar).
    """
    NONE                = "NONE"
    DRAWDOWN_EXCEEDED   = "DRAWDOWN_EXCEEDED"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    QUORUM_NOT_REACHED  = "QUORUM_NOT_REACHED"
    MT5_UNAVAILABLE     = "MT5_UNAVAILABLE"
    MT5_ACCOUNT_ERROR   = "MT5_ACCOUNT_ERROR"


@dataclass(frozen=True)
class GridSpacingParams:
    """
    Dynamic spacing metrics for the Grid Pro sub-system.

    Attributes
    ----------
    base_spacing_pips : float
        ATR-derived base distance between grid levels (in pips).
    min_spacing_pips  : float
        Lower bound for grid level spacing = base × 0.5.
    max_spacing_pips  : float
        Upper bound for grid level spacing = base × 2.0.
    lot_size          : float
        Risk-adjusted lot size per grid level.
    atr_pips          : float
        Raw ATR value in pips that was used for the calculation.
    """
    base_spacing_pips: float
    min_spacing_pips: float
    max_spacing_pips: float
    lot_size: float
    atr_pips: float


@dataclass(frozen=True)
class AccountSnapshot:
    """
    Frozen snapshot of the MT5 account state at the time of pre-flight.

    Attributes
    ----------
    balance          : float  Account balance in account currency.
    equity           : float  Floating equity (balance + unrealized P&L).
    free_margin      : float  Margin available for new positions.
    margin_used      : float  Margin currently in use.
    drawdown_pct     : float  Unrealized drawdown percentage.
    leverage         : int    Account leverage ratio (e.g., 500 for 1:500).
    timestamp        : float  UNIX epoch when snapshot was taken.
    source           : str    "mt5_live", "mt5_simulated", or "fallback".
    """
    balance: float
    equity: float
    free_margin: float
    margin_used: float
    drawdown_pct: float
    leverage: int
    timestamp: float
    source: str


@dataclass(frozen=True)
class ExecutionMandate:
    """
    Immutable, fully risk-validated execution mandate produced by the
    ``QuantumPlannerAgent`` at bar-close.

    This object is the sole legal entry point into the execution layer.
    No trade should be opened without a valid ``ExecutionMandate`` with
    ``action`` equal to BUY or SELL.

    Attributes
    ----------
    action : MandateAction
        The final verified action: BUY, SELL, HOLD, or SAFETY_HOLD.
    symbol : str
        The target trading instrument (e.g., "EURUSD").
    bar_timestamp : float
        UNIX epoch of the bar close that triggered this mandate.
    consensus : ConsensusResult
        The full consensus result from the engine (includes per-agent
        contribution breakdown and the aggregated score).
    account_snapshot : AccountSnapshot
        MT5 account state at the time of the pre-flight risk check.
    grid_params : GridSpacingParams or None
        Dynamic grid spacing parameters.  None when action is HOLD or
        SAFETY_HOLD (no new grid levels should be placed).
    override_applied : bool
        True if the consensus action was overridden to SAFETY_HOLD by
        the pre-flight risk gate.
    override_reason : OverrideReason
        Enumerated reason for the override.  NONE if no override occurred.
    planner_notes : str
        Human-readable explanation of the mandate decision for audit logs.
    mandate_id : str
        Unique 16-character hexadecimal mandate identifier.
    issued_at : float
        UNIX epoch when the mandate was created.

    Properties
    ----------
    is_executable : bool
        True if action is BUY or SELL (a real trade will be submitted).
    is_blocked : bool
        True if action is HOLD or SAFETY_HOLD (no trade submitted).
    """
    action: MandateAction
    symbol: str
    bar_timestamp: float
    consensus: ConsensusResult
    account_snapshot: AccountSnapshot
    grid_params: Optional[GridSpacingParams]
    override_applied: bool
    override_reason: OverrideReason
    planner_notes: str
    mandate_id: str
    issued_at: float = field(default_factory=time.time)

    @property
    def is_executable(self) -> bool:
        """True if action is BUY or SELL — a trade order will be submitted."""
        return self.action in (MandateAction.BUY, MandateAction.SELL)

    @property
    def is_blocked(self) -> bool:
        """True if action is HOLD or SAFETY_HOLD — no trade will be submitted."""
        return not self.is_executable

    def to_dict(self) -> Dict[str, Any]:
        """Return a fully JSON-serializable representation of this mandate."""
        return {
            "mandate_id":       self.mandate_id,
            "action":           self.action.value,
            "symbol":           self.symbol,
            "is_executable":    self.is_executable,
            "bar_timestamp":    self.bar_timestamp,
            "issued_at":        self.issued_at,
            "override_applied": self.override_applied,
            "override_reason":  self.override_reason.value,
            "planner_notes":    self.planner_notes,
            "consensus":        self.consensus.to_dict(),
            "account_snapshot": {
                "balance":      round(self.account_snapshot.balance, 2),
                "equity":       round(self.account_snapshot.equity, 2),
                "free_margin":  round(self.account_snapshot.free_margin, 2),
                "margin_used":  round(self.account_snapshot.margin_used, 2),
                "drawdown_pct": round(self.account_snapshot.drawdown_pct, 4),
                "leverage":     self.account_snapshot.leverage,
                "source":       self.account_snapshot.source,
                "timestamp":    self.account_snapshot.timestamp,
            },
            "grid_params": (
                {
                    "base_spacing_pips": round(self.grid_params.base_spacing_pips, 2),
                    "min_spacing_pips":  round(self.grid_params.min_spacing_pips, 2),
                    "max_spacing_pips":  round(self.grid_params.max_spacing_pips, 2),
                    "lot_size":          round(self.grid_params.lot_size, 2),
                    "atr_pips":          round(self.grid_params.atr_pips, 2),
                }
                if self.grid_params is not None
                else None
            ),
        }

    def __repr__(self) -> str:
        override_str = f" [OVERRIDE: {self.override_reason.value}]" if self.override_applied else ""
        return (
            f"ExecutionMandate("
            f"id={self.mandate_id}, "
            f"action={self.action.value}{override_str}, "
            f"symbol={self.symbol!r}, "
            f"score={self.consensus.aggregated_score:+.4f})"
        )


# ===========================================================================
# QuantumPlannerAgent — Master Planner Orchestrator
# ===========================================================================

class QuantumPlannerAgent:
    """
    Master Planner Agent that executes the bar-close decision loop for the
    Quantum FSM Pro V4.2 Elite multi-agent trading system.

    The Planner is the **single authority** that converts the mathematical
    consensus from the engine into a legally valid execution mandate,
    after performing MT5-level account risk validation.

    Lifecycle
    ---------
    1. Called once per bar close (e.g., triggered by an MT5 ``OnNewBar``
       event or a Python ``schedule``/``threading.Timer`` loop).
    2. Reads the Blackboard, checks quorum, evaluates consensus.
    3. Performs MT5 pre-flight risk checks (DD and free margin).
    4. Computes dynamic grid spacing parameters.
    5. Emits an immutable ``ExecutionMandate``.

    Parameters
    ----------
    blackboard : QuantumBlackboard
        The shared memory board that all sub-model agents write to.
    consensus_engine : ConsensusEngine
        The mathematical aggregation engine to evaluate the board state.
    symbol : str
        The primary trading symbol this Planner manages.
    max_drawdown_pct : float, optional
        Account drawdown hard-stop percentage.  Default: 5.0%.
    min_free_margin_ratio : float, optional
        Multiple of per-lot margin that must remain available.  Default: 2.0.
    stale_signal_max_age : int, optional
        Maximum signal age in seconds before it is considered stale.
        Default: 300 (5 minutes, one M5 bar).

    Examples
    --------
    >>> bb = QuantumBlackboard(name="EURUSD_H1")
    >>> engine = ConsensusEngine()
    >>> planner = QuantumPlannerAgent(bb, engine, symbol="EURUSD")
    >>> mandate = planner.run_bar_close_cycle(bar_timestamp=time.time(), atr_pips=28.5)
    >>> print(mandate)
    ExecutionMandate(id=a3f7..., action=BUY, symbol='EURUSD', score=+0.8105)
    """

    def __init__(
        self,
        blackboard: QuantumBlackboard,
        consensus_engine: ConsensusEngine,
        symbol: str = "EURUSD",
        max_drawdown_pct: float = _MAX_DRAWDOWN_PCT,
        min_free_margin_ratio: float = _MIN_FREE_MARGIN_RATIO,
        stale_signal_max_age: int = 300,
    ) -> None:
        """
        Initialize the QuantumPlannerAgent.

        Parameters
        ----------
        blackboard : QuantumBlackboard
            Shared memory board populated by all sub-model agents.
        consensus_engine : ConsensusEngine
            Engine that computes the weighted aggregated score.
        symbol : str
            Primary trading symbol (e.g., "EURUSD", "GBPUSD").
        max_drawdown_pct : float
            Hard-stop drawdown percentage.  Exceeding this triggers SAFETY_HOLD.
        min_free_margin_ratio : float
            Minimum free margin as a multiple of per-lot margin requirement.
        stale_signal_max_age : int
            Maximum signal age (seconds) before automatic invalidation.
        """
        if not isinstance(blackboard, QuantumBlackboard):
            raise TypeError(
                f"blackboard must be a QuantumBlackboard; "
                f"received {type(blackboard).__name__}."
            )
        if not isinstance(consensus_engine, ConsensusEngine):
            raise TypeError(
                f"consensus_engine must be a ConsensusEngine; "
                f"received {type(consensus_engine).__name__}."
            )
        if not symbol.strip():
            raise ValueError("symbol must be a non-empty string.")
        if max_drawdown_pct <= 0 or max_drawdown_pct >= 100:
            raise ValueError(
                f"max_drawdown_pct must be in (0, 100); received {max_drawdown_pct}."
            )
        if min_free_margin_ratio < 1.0:
            raise ValueError(
                f"min_free_margin_ratio must be >= 1.0; "
                f"received {min_free_margin_ratio}."
            )

        self._blackboard: QuantumBlackboard = blackboard
        self._engine: ConsensusEngine = consensus_engine
        self.symbol: str = symbol.strip().upper()
        self._max_dd_pct: float = max_drawdown_pct
        self._min_margin_ratio: float = min_free_margin_ratio
        self._stale_max_age: int = stale_signal_max_age

        # Monotonic bar cycle counter for mandate ID generation
        self._cycle_count: int = 0

        if not _MT5_AVAILABLE:
            logger.warning(
                "[QuantumPlannerAgent] MetaTrader5 library not installed.  "
                "Pre-flight risk checks will use a simulated fallback account.  "
                "Install with: pip install MetaTrader5"
            )

        logger.info(
            "[QuantumPlannerAgent] Initialized | symbol=%r | "
            "max_dd=%.1f%% | min_margin_ratio=%.1fx | "
            "stale_age=%ds | MT5=%s",
            self.symbol,
            self._max_dd_pct,
            self._min_margin_ratio,
            self._stale_max_age,
            "available" if _MT5_AVAILABLE else "unavailable",
        )

    # -------------------------------------------------------------------
    # Primary Bar-Close Decision Loop
    # -------------------------------------------------------------------

    def run_bar_close_cycle(
        self,
        bar_timestamp: float,
        atr_pips: float = 25.0,
    ) -> ExecutionMandate:
        """
        Execute the full bar-close decision loop and return a verified mandate.

        This is the single entry point called once per bar close.  It
        orchestrates the entire pipeline: staleness sweep → consensus
        evaluation → MT5 pre-flight → grid parameter calculation →
        mandate emission.

        Parameters
        ----------
        bar_timestamp : float
            UNIX epoch timestamp of the bar that just closed.  Used in the
            mandate for traceability back to the specific market data event.
        atr_pips : float, optional
            Current Average True Range in pips for the symbol.  Used to
            compute dynamic grid spacing.  Default: 25.0 pips.

        Returns
        -------
        ExecutionMandate
            An immutable, risk-validated execution mandate.  The action field
            is one of: BUY, SELL, HOLD, SAFETY_HOLD.

        Examples
        --------
        >>> mandate = planner.run_bar_close_cycle(
        ...     bar_timestamp=time.time(),
        ...     atr_pips=28.5,
        ... )
        >>> if mandate.is_executable:
        ...     gateway.submit(mandate)
        """
        self._cycle_count += 1
        mandate_id: str = self._generate_mandate_id()
        cycle_start_ts: float = time.time()

        logger.info(
            "[QuantumPlannerAgent] ══════════════════════════════════════",
        )
        logger.info(
            "[QuantumPlannerAgent] Bar-close cycle #%d | symbol=%r | "
            "mandate_id=%s | bar_ts=%.2f | ATR=%.2f pips",
            self._cycle_count,
            self.symbol,
            mandate_id,
            bar_timestamp,
            atr_pips,
        )

        # ── Step 1: Purge stale signals ──────────────────────────────────
        n_stale = self._blackboard.invalidate_stale_signals(self._stale_max_age)
        if n_stale:
            logger.warning(
                "[QuantumPlannerAgent] %d stale signal(s) purged before "
                "consensus evaluation.",
                n_stale,
            )

        # ── Step 2: Quorum check ─────────────────────────────────────────
        if not self._blackboard.is_quorum_reached():
            missing = self._blackboard.missing_agents()
            logger.warning(
                "[QuantumPlannerAgent] ⚠️ QUORUM NOT REACHED — missing agents: %s.  "
                "Forcing HOLD to prevent partial-information execution.",
                missing,
            )
            account_snap = self._fetch_account_snapshot()
            note = (
                f"HOLD (quorum failure): agents {missing} have not posted "
                f"active signals. Awaiting full 4/4 quorum before trade execution."
            )
            return self._build_mandate(
                action=MandateAction.HOLD,
                symbol=self.symbol,
                bar_timestamp=bar_timestamp,
                consensus=self._engine.evaluate(self._blackboard),
                account_snap=account_snap,
                grid_params=None,
                override=True,
                override_reason=OverrideReason.QUORUM_NOT_REACHED,
                notes=note,
                mandate_id=mandate_id,
            )

        # ── Step 3: Consensus evaluation ─────────────────────────────────
        consensus: ConsensusResult = self._engine.evaluate(self._blackboard)
        logger.info(
            "[QuantumPlannerAgent] Consensus result: %s",
            consensus.summary(),
        )

        # ── Step 4: MT5 pre-flight risk check ────────────────────────────
        account_snap: AccountSnapshot = self._fetch_account_snapshot()
        risk_ok, override_reason, risk_note = self._preflight_risk_check(
            account_snap, consensus.action
        )

        if not risk_ok:
            logger.warning(
                "[QuantumPlannerAgent] 🛑 PRE-FLIGHT FAILURE — %s | "
                "Overriding %s → SAFETY_HOLD.",
                risk_note,
                consensus.action.value,
            )
            return self._build_mandate(
                action=MandateAction.SAFETY_HOLD,
                symbol=self.symbol,
                bar_timestamp=bar_timestamp,
                consensus=consensus,
                account_snap=account_snap,
                grid_params=None,
                override=True,
                override_reason=override_reason,
                notes=risk_note,
                mandate_id=mandate_id,
            )

        # ── Step 5: HOLD / SAFETY_HOLD — no grid params needed ───────────
        final_action = MandateAction(consensus.action.value)

        if not consensus.is_actionable:
            hold_note = (
                f"HOLD by consensus: score={consensus.aggregated_score:+.4f} "
                f"is within ambiguous zone "
                f"[{consensus.sell_threshold:+.4f}, {consensus.buy_threshold:+.4f}]. "
                f"Capital preserved."
            )
            logger.info("[QuantumPlannerAgent] 🔒 %s", hold_note)
            return self._build_mandate(
                action=MandateAction.HOLD,
                symbol=self.symbol,
                bar_timestamp=bar_timestamp,
                consensus=consensus,
                account_snap=account_snap,
                grid_params=None,
                override=False,
                override_reason=OverrideReason.NONE,
                notes=hold_note,
                mandate_id=mandate_id,
            )

        # ── Step 6: Compute grid spacing params for BUY/SELL ─────────────
        grid_params = self._compute_grid_spacing(
            atr_pips=atr_pips,
            balance=account_snap.balance,
            drawdown_pct=account_snap.drawdown_pct,
            leverage=account_snap.leverage,
        )

        action_note = (
            f"{final_action.value} — consensus score={consensus.aggregated_score:+.4f} "
            f"({consensus.consensus_strength_pct:.1f}% strength), "
            f"all pre-flight checks passed. "
            f"Grid: base={grid_params.base_spacing_pips:.1f}p, "
            f"lot={grid_params.lot_size:.2f}"
        )
        logger.info(
            "[QuantumPlannerAgent] ✅ MANDATE ISSUED: %s | %s",
            final_action.value,
            action_note,
        )

        elapsed_ms = (time.time() - cycle_start_ts) * 1000
        logger.info(
            "[QuantumPlannerAgent] Cycle #%d completed in %.2f ms.",
            self._cycle_count,
            elapsed_ms,
        )

        return self._build_mandate(
            action=final_action,
            symbol=self.symbol,
            bar_timestamp=bar_timestamp,
            consensus=consensus,
            account_snap=account_snap,
            grid_params=grid_params,
            override=False,
            override_reason=OverrideReason.NONE,
            notes=action_note,
            mandate_id=mandate_id,
        )

    # -------------------------------------------------------------------
    # MT5 Pre-Flight Risk Check
    # -------------------------------------------------------------------

    def _preflight_risk_check(
        self,
        account: AccountSnapshot,
        proposed_action: ConsensusAction,
    ) -> Tuple[bool, OverrideReason, str]:
        """
        Perform the MT5-sourced account risk validation before any BUY/SELL
        mandate is transmitted to the execution layer.

        The check is only applied when the proposed action is BUY or SELL.
        HOLD consensus passes through this check unchanged.

        Parameters
        ----------
        account : AccountSnapshot
            The frozen snapshot of the current MT5 account metrics.
        proposed_action : ConsensusAction
            The action the engine wishes to execute.

        Returns
        -------
        Tuple[bool, OverrideReason, str]
            - bool: True if the action is safe to proceed.
            - OverrideReason: The reason code if blocked, else NONE.
            - str: A detailed human-readable risk check note for audit logs.

        Risk Rules Applied
        ------------------
        Rule 1 — Drawdown Guard:
            If (balance - equity) / balance × 100 > max_drawdown_pct (5%):
                → Block with DRAWDOWN_EXCEEDED

        Rule 2 — Free Margin Guard:
            required_margin = (100_000 × 0.01) / leverage
                (margin needed for one 0.01 lot standard contract)
            If free_margin < required_margin × min_free_margin_ratio:
                → Block with INSUFFICIENT_MARGIN

        Rule 3 — Data Integrity Guard:
            If balance == 0 or source == "fallback" with MT5 available:
                → Block with MT5_ACCOUNT_ERROR
        """
        # HOLD consensus never requires a risk check — capital is not deployed
        if proposed_action == ConsensusAction.HOLD:
            return True, OverrideReason.NONE, "HOLD consensus — no pre-flight required."

        # Rule 3 — Data integrity: refuse to trade on zero-balance snapshots
        if account.balance <= 0:
            note = (
                f"MT5 account error: balance={account.balance:.2f}.  "
                f"Cannot compute risk parameters on zero balance."
            )
            return False, OverrideReason.MT5_ACCOUNT_ERROR, note

        if account.source == "fallback" and _MT5_AVAILABLE:
            note = (
                "MT5 is installed but account snapshot used fallback values.  "
                "Possible MT5 connection failure — refusing to trade."
            )
            return False, OverrideReason.MT5_UNAVAILABLE, note

        # Rule 1 — Drawdown guard
        if account.drawdown_pct > self._max_dd_pct:
            note = (
                f"Drawdown guard triggered: current unrealized drawdown "
                f"= {account.drawdown_pct:.2f}% > limit = {self._max_dd_pct:.1f}%.  "
                f"Account equity = {account.equity:.2f}, "
                f"balance = {account.balance:.2f}.  "
                f"Halting all new entries to protect capital."
            )
            return False, OverrideReason.DRAWDOWN_EXCEEDED, note

        # Rule 2 — Free margin guard
        # Margin required for 1 standard lot (100,000 units) at 0.01 lot size:
        #   margin_per_micro_lot = (100_000 × 0.01) / leverage
        leverage = max(account.leverage, 1)  # Guard against division by zero
        margin_per_micro_lot: float = (100_000 * 0.01) / leverage
        required_free_margin: float = (
            margin_per_micro_lot * self._min_margin_ratio
        )

        if account.free_margin < required_free_margin:
            note = (
                f"Margin guard triggered: free_margin={account.free_margin:.2f} "
                f"< required={required_free_margin:.2f} "
                f"(margin_per_0.01lot={margin_per_micro_lot:.2f} × "
                f"ratio={self._min_margin_ratio:.1f}).  "
                f"Halting new entries to prevent margin call."
            )
            return False, OverrideReason.INSUFFICIENT_MARGIN, note

        # All checks passed
        check_note = (
            f"Pre-flight PASSED — "
            f"DD={account.drawdown_pct:.2f}% (limit={self._max_dd_pct:.1f}%), "
            f"free_margin={account.free_margin:.2f} "
            f"(required≥{required_free_margin:.2f})."
        )
        logger.debug("[QuantumPlannerAgent] %s", check_note)
        return True, OverrideReason.NONE, check_note

    # -------------------------------------------------------------------
    # MT5 Account Data Fetcher
    # -------------------------------------------------------------------

    def _fetch_account_snapshot(self) -> AccountSnapshot:
        """
        Fetch live account metrics from MetaTrader 5 and return a frozen
        ``AccountSnapshot``.

        If MT5 is unavailable or returns an error, a conservative fallback
        snapshot is returned with zero equity/margin values that will
        trigger the safety hold in the pre-flight check.

        Returns
        -------
        AccountSnapshot
            Frozen account data snapshot used for pre-flight risk checks.

        MT5 Fields Used
        ---------------
        - ``account_info().balance``      : Current account balance
        - ``account_info().equity``       : Current floating equity
        - ``account_info().margin_free``  : Available free margin
        - ``account_info().margin``       : Margin currently in use
        - ``account_info().leverage``     : Account leverage (e.g., 500)
        """
        ts = time.time()

        if not _MT5_AVAILABLE:
            logger.debug(
                "[QuantumPlannerAgent] MT5 not installed — using fallback account."
            )
            return AccountSnapshot(
                balance=10_000.0,
                equity=10_000.0,
                free_margin=10_000.0,
                margin_used=0.0,
                drawdown_pct=0.0,
                leverage=500,
                timestamp=ts,
                source="fallback",
            )

        # Attempt live MT5 account query
        try:
            account_info = mt5.account_info()

            if account_info is None:
                last_error = mt5.last_error()
                logger.error(
                    "[QuantumPlannerAgent] mt5.account_info() returned None.  "
                    "MT5 error: %s",
                    last_error,
                )
                return self._fallback_account_snapshot(ts, reason="mt5_account_info_none")

            balance: float = float(account_info.balance)
            equity: float = float(account_info.equity)
            free_margin: float = float(account_info.margin_free)
            margin_used: float = float(account_info.margin)
            leverage: int = int(account_info.leverage)

            # Compute unrealized drawdown percentage
            if balance > 0:
                drawdown_pct = max(0.0, (balance - equity) / balance * 100.0)
            else:
                drawdown_pct = 0.0

            logger.debug(
                "[QuantumPlannerAgent] MT5 account | balance=%.2f | "
                "equity=%.2f | free_margin=%.2f | DD=%.2f%%",
                balance,
                equity,
                free_margin,
                drawdown_pct,
            )

            return AccountSnapshot(
                balance=balance,
                equity=equity,
                free_margin=free_margin,
                margin_used=margin_used,
                drawdown_pct=drawdown_pct,
                leverage=leverage,
                timestamp=ts,
                source="mt5_live",
            )

        except Exception as exc:
            logger.error(
                "[QuantumPlannerAgent] Exception while fetching MT5 account: %s",
                exc,
                exc_info=True,
            )
            return self._fallback_account_snapshot(ts, reason="mt5_exception")

    def _fallback_account_snapshot(
        self, ts: float, reason: str = "unknown"
    ) -> AccountSnapshot:
        """
        Return a conservative zero-equity fallback snapshot that will
        trigger the MT5_UNAVAILABLE safety hold in the pre-flight check.

        Parameters
        ----------
        ts : float
            UNIX epoch timestamp to embed in the snapshot.
        reason : str
            Short description of why the fallback was triggered (for logs).

        Returns
        -------
        AccountSnapshot
            Zero-balance snapshot that forces SAFETY_HOLD.
        """
        logger.warning(
            "[QuantumPlannerAgent] Using fallback account snapshot "
            "(reason=%r).  All BUY/SELL mandates will be blocked.",
            reason,
        )
        return AccountSnapshot(
            balance=0.0,
            equity=0.0,
            free_margin=0.0,
            margin_used=0.0,
            drawdown_pct=0.0,
            leverage=1,
            timestamp=ts,
            source="fallback",
        )

    # -------------------------------------------------------------------
    # Dynamic Grid Spacing Calculator
    # -------------------------------------------------------------------

    def _compute_grid_spacing(
        self,
        atr_pips: float,
        balance: float,
        drawdown_pct: float,
        leverage: int,
    ) -> GridSpacingParams:
        """
        Compute dynamic grid spacing parameters for the Grid Pro sub-system.

        The base spacing is derived from the ATR, ensuring grid levels adapt
        to current market volatility.  A drawdown-scaled lot size reduces
        position sizes as account stress increases.

        Parameters
        ----------
        atr_pips : float
            Current ATR value in pips.  Used to scale grid spacing.
        balance : float
            Current account balance in account currency.
        drawdown_pct : float
            Current unrealized drawdown percentage (used for lot scaling).
        leverage : int
            Account leverage ratio.

        Returns
        -------
        GridSpacingParams
            Immutable parameter bundle for the Grid Pro sub-system.

        Grid Spacing Formula
        --------------------
        base_spacing = max(ATR × 1.5, 15.0)  [pips]
        min_spacing  = base_spacing × 0.5
        max_spacing  = base_spacing × 2.0

        Lot Size Formula
        ----------------
        risk_usd    = balance × 0.01  (1% risk per grid level)
        pip_value   = 10.0            (standard 1-pip value for 1 lot)
        raw_lot     = risk_usd / (base_spacing_pips × pip_value)
        dd_scale    = max(0.3, 1.0 - drawdown_pct / 100.0)
        lot_size    = clip(raw_lot × dd_scale, 0.01, 10.0)
        """
        # ── Base spacing: ATR-derived, floored at minimum ─────────────────
        base_spacing: float = max(
            atr_pips * _GRID_ATR_MULTIPLIER,
            _GRID_MIN_SPACING_PIPS,
        )
        min_spacing: float = round(base_spacing * 0.5, 2)
        max_spacing: float = round(base_spacing * 2.0, 2)

        # ── Lot size: 1% risk, scaled down by drawdown ────────────────────
        risk_usd: float = balance * 0.01  # 1% risk per grid level
        pip_value: float = 10.0           # USD value of 1 pip for 1 full lot

        if base_spacing > 0 and pip_value > 0:
            raw_lot: float = risk_usd / (base_spacing * pip_value)
        else:
            raw_lot = 0.01

        # Drawdown scalar: reduces lot size as drawdown approaches max_dd
        dd_scale: float = max(0.30, 1.0 - drawdown_pct / 100.0)
        lot_size: float = max(0.01, min(10.0, round(raw_lot * dd_scale, 2)))

        logger.debug(
            "[QuantumPlannerAgent] Grid params | "
            "ATR=%.2fp | base=%.2fp | lot=%.2f (dd_scale=%.2f, risk_usd=%.2f)",
            atr_pips,
            base_spacing,
            lot_size,
            dd_scale,
            risk_usd,
        )

        return GridSpacingParams(
            base_spacing_pips=round(base_spacing, 2),
            min_spacing_pips=min_spacing,
            max_spacing_pips=max_spacing,
            lot_size=lot_size,
            atr_pips=round(atr_pips, 2),
        )

    # -------------------------------------------------------------------
    # Mandate Builder
    # -------------------------------------------------------------------

    @staticmethod
    def _build_mandate(
        action: MandateAction,
        symbol: str,
        bar_timestamp: float,
        consensus: ConsensusResult,
        account_snap: AccountSnapshot,
        grid_params: Optional[GridSpacingParams],
        override: bool,
        override_reason: OverrideReason,
        notes: str,
        mandate_id: str,
    ) -> ExecutionMandate:
        """
        Construct the immutable ``ExecutionMandate`` from its components.

        Parameters
        ----------
        action : MandateAction
            Final verified action.
        symbol : str
            Target trading symbol.
        bar_timestamp : float
            UNIX timestamp of the originating bar close.
        consensus : ConsensusResult
            Full consensus evaluation result.
        account_snap : AccountSnapshot
            MT5 account state at time of issuance.
        grid_params : GridSpacingParams or None
            Grid spacing metrics; None for HOLD / SAFETY_HOLD.
        override : bool
            Whether the consensus was overridden by the risk gate.
        override_reason : OverrideReason
            Enumerated override reason code.
        notes : str
            Human-readable explanation of the mandate decision.
        mandate_id : str
            Unique identifier for this mandate.

        Returns
        -------
        ExecutionMandate
        """
        return ExecutionMandate(
            action=action,
            symbol=symbol,
            bar_timestamp=bar_timestamp,
            consensus=consensus,
            account_snapshot=account_snap,
            grid_params=grid_params,
            override_applied=override,
            override_reason=override_reason,
            planner_notes=notes,
            mandate_id=mandate_id,
            issued_at=time.time(),
        )

    # -------------------------------------------------------------------
    # Mandate ID Generator
    # -------------------------------------------------------------------

    def _generate_mandate_id(self) -> str:
        """
        Generate a unique 16-character hexadecimal mandate identifier.

        The ID is constructed from the cycle counter, current timestamp,
        and symbol characters to provide both uniqueness and traceability.

        Returns
        -------
        str
            A 16-character uppercase hexadecimal string (e.g., "A3F7B2C1D9E04F85").
        """
        import hashlib
        raw = f"{self.symbol}-{self._cycle_count}-{time.time()}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return digest[:16].upper()

    # -------------------------------------------------------------------
    # Convenience Accessors
    # -------------------------------------------------------------------

    @property
    def blackboard(self) -> QuantumBlackboard:
        """Return the Blackboard instance this Planner manages."""
        return self._blackboard

    @property
    def engine(self) -> ConsensusEngine:
        """Return the ConsensusEngine instance this Planner uses."""
        return self._engine

    @property
    def cycle_count(self) -> int:
        """Return the total number of bar-close cycles executed so far."""
        return self._cycle_count

    def __repr__(self) -> str:
        return (
            f"QuantumPlannerAgent("
            f"symbol={self.symbol!r}, "
            f"max_dd={self._max_dd_pct:.1f}%, "
            f"cycles={self._cycle_count}, "
            f"MT5={'✓' if _MT5_AVAILABLE else '✗'})"
        )
