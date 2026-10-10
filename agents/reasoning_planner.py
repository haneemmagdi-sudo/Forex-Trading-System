"""
==============================================================================
agents/reasoning_planner.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module  : QuantumReasoningPlanner — Test-Time Compute / Chain-of-Thought Layer
Author  : Principal Quantitative AI Architect
Version : 4.2.1
Inspired: Chapter 13 — Process Reward Models & Test-Time Compute Scaling
          (The Hitchhiker's Guide to Agentic AI: From Foundations to Systems)

Overview
--------
Implements the QuantumReasoningPlanner — a Chain-of-Thought (CoT) pre-trade
verification wrapper that enforces computational reflection before any
execution mandate is emitted downstream.

Architectural Motivation
------------------------
The prior QuantumPlannerAgent fired execution mandates immediately after
the Consensus Engine threshold gate, relying on hard-coded scalar comparisons
for risk control. This exposed the Grid Pro subsystem to dangerous drawdown
during high-volatility regimes because:

    1. No geometric projection of multi-step grid capital consumption.
    2. No explicit volatility-adjusted lot derivation at trade time.
    3. No structured audit trail of the intermediate reasoning sequence.

This module introduces Test-Time Compute (TTC) scaling by forcing the agent
to traverse a sequential reasoning scratchpad — simulating hidden thinking
tokens — before any trade payload is finalized.

Chain-of-Thought (CoT) Verification Pipeline
--------------------------------------------

    STEP 1: validate_margin_availability
      - MCP -> MT5 free_margin fetch
      - Geometric 3-step density multiplier
        required = lot x margin_per_lot x Sum(2^i, i=0..2) = 7x
      - FAIL -> CoT halt, emit HOLD mandate

    STEP 2: validate_drawdown_exposure
      - asset_dd = (balance-equity)/balance
      - If asset_dd > 5%  -> HARD HOLD
      - Logged with floating P&L detail

    STEP 3: calculate_volatility_adjusted_lot
      - grid_step = ATR_pips x 1.5 (>= 15 pips)
      - lot = (equity x 0.015)/(step x pip_val)
      - Capped: 0.01 <= lot <= 10.0

Geometric Density Multiplier Detail
--------------------------------------
Level 0  : 1 lot unit  -> standard margin
Level 1  : 2 lot units -> 2x margin
Level 2  : 4 lot units -> 4x margin
Total    : 7x initial margin required
Required free margin = lot_size x margin_per_lot x 7

Integration
-----------
The planner wraps (does not replace) QuantumPlannerAgent. It acts as a
proxy: if the CoT verification chain passes, it delegates to the underlying
planner to generate a fully typed ExecutionMandate. If the chain fails
at any step, it emits a HOLD mandate immediately with the failure trajectory
embedded for audit.
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Conditional MT5 import - falls back gracefully when not installed
# ---------------------------------------------------------------------------
try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE: bool = True
except ImportError:
    mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE: bool = False

# ---------------------------------------------------------------------------
# Internal project imports
# ---------------------------------------------------------------------------
from agents.planner_agent import (
    ExecutionMandate,
    MandateAction,
    OverrideReason,
    QuantumPlannerAgent,
)

# ---------------------------------------------------------------------------
# Module-level logger (structured telemetry)
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.reasoning_planner")


# ===========================================================================
# Constants
# ===========================================================================

# Maximum tolerated unrealized drawdown before HARD HOLD is triggered
_DRAWDOWN_HARD_STOP_PCT: float = 5.0

# ATR multiplier for deriving grid step spacing in pips
_GRID_ATR_MULTIPLIER: float = 1.5

# Absolute minimum grid step spacing floor (pips)
_GRID_STEP_FLOOR_PIPS: float = 15.0

# Fixed-fractional risk allocation per trade (1.5% of equity)
_RISK_FRACTION: float = 0.015

# Lot size bounds (broker constraints)
_LOT_MIN: float = 0.01
_LOT_MAX: float = 10.0

# Geometric density multiplier parameters
# 3-step grid with doubling ratio: Sum(2^i, i=0..2) = 1+2+4 = 7
_GRID_DENSITY_STEPS: int = 3
_GRID_DENSITY_RATIO: float = 2.0

# Total geometric multiplier (sum of geometric series)
_GEOMETRIC_MULTIPLIER: float = sum(
    _GRID_DENSITY_RATIO ** i for i in range(_GRID_DENSITY_STEPS)
)  # = 7.0


# ===========================================================================
# Pydantic v2 Schemas
# ===========================================================================


class CoTVerdict(str, Enum):
    """Terminal verdict of a single CoT reasoning step."""
    PASS    = "PASS"
    FAIL    = "FAIL"
    SKIPPED = "SKIPPED"   # Step was not reached because an earlier step failed


class FinalReasoningVerdict(str, Enum):
    """Overall verdict of the full CoT verification pipeline."""
    PASS      = "PASS"       # All 3 steps passed - trade may proceed
    HOLD      = "HOLD"       # >=1 step failed - no trade emitted
    HARD_HOLD = "HARD_HOLD"  # Drawdown breach - immediate safety halt


class CoTStepResult(BaseModel):
    """
    Immutable record of a single Chain-of-Thought verification step.

    Attributes
    ----------
    step_index     : int    Ordinal position in the verification chain (1-based).
    step_name      : str    Canonical name of the verification step.
    verdict        : CoTVerdict   PASS / FAIL / SKIPPED.
    passed         : bool   True iff verdict == PASS.
    computed_value : float | None   Primary numeric output of this step.
    threshold      : float | None   The threshold that was applied.
    narrative      : str    Human-readable explanation of the reasoning result.
    elapsed_ms     : float  Elapsed wall-clock time for this step in milliseconds.
    timestamp      : float  UNIX epoch when this step completed.
    """
    step_index:      int
    step_name:       str
    verdict:         CoTVerdict
    passed:          bool
    computed_value:  Optional[float] = None
    threshold:       Optional[float] = None
    narrative:       str
    elapsed_ms:      float = Field(default=0.0, ge=0.0)
    timestamp:       float = Field(default_factory=time.time)

    model_config = {"frozen": True}


class ValidatedDeploymentVector(BaseModel):
    """
    Immutable, fully validated trade deployment parameter set.

    Emitted only when all three CoT steps pass. This is the sole legal
    input to the execution layer when the reasoning planner is active.

    Attributes
    ----------
    symbol               : str    Trading symbol (e.g. "EURUSD").
    action               : str    "BUY", "SELL", or "HOLD".
    lot_size             : float  Volatility-adjusted lot size per grid level.
    grid_step_pips       : float  ATR-derived grid spacing in pips.
    grid_step_min_pips   : float  Lower bound (50% of grid_step).
    grid_step_max_pips   : float  Upper bound (200% of grid_step).
    required_margin      : float  Total required free margin (geometric density).
    free_margin_available: float  MT5-confirmed free margin at decision time.
    margin_buffer_pct    : float  (free_margin - required_margin)/required_margin x 100.
    equity               : float  Floating equity at decision time.
    balance              : float  Account balance at decision time.
    drawdown_pct         : float  Unrealized drawdown percentage.
    atr_pips             : float  Raw ATR value used for lot computation.
    risk_amount_usd      : float  Exact USD risked (equity x 0.015).
    pip_value_per_lot    : float  USD value of 1 pip for 1 standard lot.
    mandate_id           : str    Traceable ID linking back to the execution mandate.
    reasoning_id         : str    Unique ID of this reasoning cycle.
    issued_at            : float  UNIX epoch of mandate emission.
    """
    symbol:               str
    action:               str
    lot_size:             float = Field(ge=_LOT_MIN, le=_LOT_MAX)
    grid_step_pips:       float = Field(ge=_GRID_STEP_FLOOR_PIPS)
    grid_step_min_pips:   float
    grid_step_max_pips:   float
    required_margin:      float = Field(ge=0.0)
    free_margin_available: float = Field(ge=0.0)
    margin_buffer_pct:    float
    equity:               float = Field(ge=0.0)
    balance:              float = Field(ge=0.0)
    drawdown_pct:         float
    atr_pips:             float = Field(ge=0.0)
    risk_amount_usd:      float = Field(ge=0.0)
    pip_value_per_lot:    float = Field(gt=0.0)
    mandate_id:           str
    reasoning_id:         str
    issued_at:            float = Field(default_factory=time.time)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _validate_margin_buffer(self) -> "ValidatedDeploymentVector":
        if self.free_margin_available < self.required_margin:
            raise ValueError(
                f"Deployment vector margin inconsistency: "
                f"free_margin={self.free_margin_available:.2f} < "
                f"required_margin={self.required_margin:.2f}. "
                f"This vector should never have been emitted."
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable dict representation."""
        return self.model_dump()


class ReasoningTrajectory(BaseModel):
    """
    Complete record of a single CoT reasoning cycle.

    This object is the primary audit artifact produced by the planner.
    It embeds the full step-by-step reasoning log plus the final verdict
    and, if the chain passed, the validated deployment vector.

    Attributes
    ----------
    reasoning_id         : str   Unique identifier for this reasoning cycle.
    symbol               : str   The trading symbol being evaluated.
    bar_timestamp        : float Bar close UNIX epoch.
    steps                : list[CoTStepResult]   Sequential CoT step results.
    final_verdict        : FinalReasoningVerdict Overall pipeline verdict.
    deployment_vector    : ValidatedDeploymentVector | None  Non-None on PASS.
    mandate              : Any | None  The underlying ExecutionMandate on PASS.
    total_elapsed_ms     : float Total wall-clock time for the reasoning cycle.
    chain_halted_at_step : int | None  Step index where chain short-circuited.
    issued_at            : float UNIX epoch when trajectory was finalized.
    notes                : str   Human-readable synthesis of the full chain.
    """
    reasoning_id:         str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    symbol:               str
    bar_timestamp:        float
    steps:                List[CoTStepResult] = Field(default_factory=list)
    final_verdict:        FinalReasoningVerdict = FinalReasoningVerdict.HOLD
    deployment_vector:    Optional[ValidatedDeploymentVector] = None
    mandate:              Optional[Any] = None
    total_elapsed_ms:     float = 0.0
    chain_halted_at_step: Optional[int] = None
    issued_at:            float = Field(default_factory=time.time)
    notes:                str = ""

    model_config = {"arbitrary_types_allowed": True}

    def add_step(self, step: CoTStepResult) -> None:
        """Append a completed CoT step to the trajectory."""
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable dict of the full trajectory."""
        return {
            "reasoning_id":         self.reasoning_id,
            "symbol":               self.symbol,
            "bar_timestamp":        self.bar_timestamp,
            "final_verdict":        self.final_verdict.value,
            "total_elapsed_ms":     round(self.total_elapsed_ms, 3),
            "chain_halted_at_step": self.chain_halted_at_step,
            "notes":                self.notes,
            "issued_at":            self.issued_at,
            "steps": [
                {
                    "step_index":     s.step_index,
                    "step_name":      s.step_name,
                    "verdict":        s.verdict.value,
                    "passed":         s.passed,
                    "computed_value": s.computed_value,
                    "threshold":      s.threshold,
                    "narrative":      s.narrative,
                    "elapsed_ms":     round(s.elapsed_ms, 3),
                }
                for s in self.steps
            ],
            "deployment_vector": (
                self.deployment_vector.to_dict()
                if self.deployment_vector is not None
                else None
            ),
        }


# ===========================================================================
# MT5 Account Snapshot Helpers
# ===========================================================================

def _fetch_mt5_account_data() -> Dict[str, float]:
    """
    Fetch live account data from MetaTrader 5.

    Returns a normalized dict with keys:
        balance, equity, free_margin, margin, leverage

    Falls back to safe simulation values if MT5 is unavailable or
    the terminal cannot be queried.
    """
    if not _MT5_AVAILABLE or mt5 is None:
        logger.warning(
            "[ReasoningPlanner] MT5 unavailable - using simulated account data."
        )
        return {
            "balance":     10_000.0,
            "equity":       9_800.0,
            "free_margin":  8_500.0,
            "margin":       1_300.0,
            "leverage":       500.0,
            "source":         "simulated",
        }

    account_info = mt5.account_info()
    if account_info is None:
        err = mt5.last_error()
        logger.warning(
            "[ReasoningPlanner] mt5.account_info() returned None "
            "(error %s) - using simulated fallback.", err
        )
        return {
            "balance":     10_000.0,
            "equity":       9_800.0,
            "free_margin":  8_500.0,
            "margin":       1_300.0,
            "leverage":       500.0,
            "source":         "mt5_error_fallback",
        }

    leverage: float = float(account_info.leverage) if account_info.leverage else 100.0
    return {
        "balance":     float(account_info.balance),
        "equity":      float(account_info.equity),
        "free_margin": float(account_info.margin_free),
        "margin":      float(account_info.margin),
        "leverage":    leverage,
        "source":      "mt5_live",
    }


def _fetch_margin_per_lot(symbol: str) -> float:
    """
    Query MT5 for the initial margin requirement per 1.0 standard lot.

    Falls back to a conservative estimate if MT5 is unavailable.
    For 1:500 leverage on 100,000 base currency = 200 USD/lot (EURUSD).
    """
    if not _MT5_AVAILABLE or mt5 is None:
        logger.debug(
            "[ReasoningPlanner] MT5 unavailable - using fallback margin_per_lot=200."
        )
        return 200.0

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.warning(
            "[ReasoningPlanner] mt5.symbol_info(%r) returned None - "
            "using fallback margin_per_lot=200.", symbol
        )
        return 200.0

    margin_initial: float = float(getattr(symbol_info, "margin_initial", 0.0))
    if margin_initial <= 0.0:
        trade_contract_size: float = float(
            getattr(symbol_info, "trade_contract_size", 100_000.0)
        )
        bid: float = float(getattr(symbol_info, "bid", 1.0))
        account_data = _fetch_mt5_account_data()
        leverage = account_data.get("leverage", 100.0)
        margin_initial = (trade_contract_size * bid) / leverage

    return margin_initial


# ===========================================================================
# QuantumReasoningPlanner
# ===========================================================================

class QuantumReasoningPlanner:
    """
    Test-Time Compute (TTC) reasoning wrapper for the Quantum Planner Agent.

    Enforces a structured Chain-of-Thought (CoT) pre-trade verification
    loop before any execution mandate is forwarded to the trading gateway.
    The agent thinks aloud through three sequential mathematical validation
    steps, each of which can terminate the chain immediately on failure.

    This class acts as a proxy around the existing QuantumPlannerAgent:
    when all CoT steps pass, it delegates to the underlying planner to
    generate the full ExecutionMandate. On any failure it short-circuits
    and emits a safe HOLD mandate with the full reasoning trajectory embedded.

    Parameters
    ----------
    planner : QuantumPlannerAgent
        The underlying deterministic mandate generator.
    symbol : str
        Primary trading instrument (e.g. "EURUSD").
    pip_value_per_lot : float
        USD value of a 1-pip move for 1.0 standard lot.
        Typical: EURUSD=10.0, USDJPY~7.5, GBPUSD=10.0.
    drawdown_hard_stop_pct : float
        Maximum tolerated unrealized drawdown (default: 5.0%).
    atr_multiplier : float
        Multiplier applied to ATR to derive grid step spacing (default: 1.5).
    risk_fraction : float
        Fixed-fractional risk per trade as a fraction of equity (default: 0.015).
    reflection_threshold : float
        Minimum consensus score magnitude above which CoT is engaged.
        Below this threshold, HOLD is returned without reasoning.
        Default: 0.5.

    Examples
    --------
    >>> import asyncio, time
    >>> from agents.blackboard import QuantumBlackboard
    >>> from agents.consensus_engine import ConsensusEngine
    >>> from agents.planner_agent import QuantumPlannerAgent
    >>> from agents.reasoning_planner import QuantumReasoningPlanner
    >>>
    >>> bb      = QuantumBlackboard(name="EURUSD_H1")
    >>> engine  = ConsensusEngine()
    >>> planner = QuantumPlannerAgent(bb, engine, symbol="EURUSD")
    >>> reasoner = QuantumReasoningPlanner(planner, symbol="EURUSD")
    >>> trajectory = asyncio.run(reasoner.run_reasoning_cycle(
    ...     bar_timestamp=time.time(), atr_pips=28.5
    ... ))
    >>> print(trajectory.final_verdict)
    FinalReasoningVerdict.PASS
    """

    def __init__(
        self,
        planner: QuantumPlannerAgent,
        symbol: str = "EURUSD",
        pip_value_per_lot: float = 10.0,
        drawdown_hard_stop_pct: float = _DRAWDOWN_HARD_STOP_PCT,
        atr_multiplier: float = _GRID_ATR_MULTIPLIER,
        risk_fraction: float = _RISK_FRACTION,
        reflection_threshold: float = 0.50,
    ) -> None:
        if not isinstance(planner, QuantumPlannerAgent):
            raise TypeError(
                f"planner must be a QuantumPlannerAgent; "
                f"received {type(planner).__name__}."
            )
        if pip_value_per_lot <= 0.0:
            raise ValueError(
                f"pip_value_per_lot must be > 0; received {pip_value_per_lot}."
            )
        if not (0.0 < drawdown_hard_stop_pct < 100.0):
            raise ValueError(
                f"drawdown_hard_stop_pct must be in (0, 100); "
                f"received {drawdown_hard_stop_pct}."
            )
        if not (0.0 < risk_fraction < 1.0):
            raise ValueError(
                f"risk_fraction must be in (0, 1); received {risk_fraction}."
            )

        self._planner:               QuantumPlannerAgent = planner
        self.symbol:                 str   = symbol.strip().upper()
        self._pip_value_per_lot:     float = pip_value_per_lot
        self._dd_hard_stop_pct:      float = drawdown_hard_stop_pct
        self._atr_multiplier:        float = atr_multiplier
        self._risk_fraction:         float = risk_fraction
        self._reflection_threshold:  float = reflection_threshold
        self._cycle_count: int = 0

        logger.info(
            "[QuantumReasoningPlanner] Initialized | symbol=%r | "
            "pip_val=%.2f | dd_stop=%.1f%% | risk_frac=%.3f | "
            "reflection_threshold=%.2f | MT5=%s",
            self.symbol,
            self._pip_value_per_lot,
            self._dd_hard_stop_pct,
            self._risk_fraction,
            self._reflection_threshold,
            "available" if _MT5_AVAILABLE else "unavailable",
        )

    # -----------------------------------------------------------------------
    # Primary Public Entry Point
    # -----------------------------------------------------------------------

    async def run_reasoning_cycle(
        self,
        bar_timestamp: float,
        atr_pips: float = 25.0,
        consensus_score: float = 0.8,
    ) -> ReasoningTrajectory:
        """
        Execute the full Chain-of-Thought pre-trade verification cycle.

        Orchestrates the sequential reasoning chain and, if all steps pass,
        delegates to QuantumPlannerAgent.run_bar_close_cycle() to generate
        a typed ExecutionMandate.

        Sequential chain:
            Step 1 -> validate_margin_availability
            Step 2 -> validate_drawdown_exposure
            Step 3 -> calculate_volatility_adjusted_lot

        Each step can independently short-circuit the chain to HOLD/HARD_HOLD.

        Parameters
        ----------
        bar_timestamp : float
            UNIX epoch of the bar that just closed.
        atr_pips : float
            Current ATR of the primary symbol in pips. Default: 25.0.
        consensus_score : float
            Raw consensus score from the ConsensusEngine [-1, +1].
            If abs(consensus_score) < reflection_threshold, HOLD is returned
            immediately without CoT. Default: 0.8.

        Returns
        -------
        ReasoningTrajectory
            Complete audit record including all step results, final verdict,
            and (on PASS) the validated deployment vector and underlying mandate.
        """
        self._cycle_count += 1
        cycle_start: float = time.perf_counter()
        reasoning_id: str = uuid.uuid4().hex[:16]

        trajectory = ReasoningTrajectory(
            reasoning_id=reasoning_id,
            symbol=self.symbol,
            bar_timestamp=bar_timestamp,
        )

        logger.info(
            "[ReasoningPlanner] CoT Cycle #%d | reasoning_id=%s | "
            "bar_ts=%.0f | atr=%.2f pips | consensus_score=%+.4f",
            self._cycle_count,
            reasoning_id,
            bar_timestamp,
            atr_pips,
            consensus_score,
        )

        # Guard: reflection threshold — skip CoT for weak signals
        if abs(consensus_score) < self._reflection_threshold:
            trajectory.final_verdict    = FinalReasoningVerdict.HOLD
            trajectory.total_elapsed_ms = (time.perf_counter() - cycle_start) * 1_000
            trajectory.notes = (
                f"Consensus score magnitude {abs(consensus_score):.4f} is below "
                f"reflection threshold {self._reflection_threshold:.2f}. "
                f"CoT not engaged — emitting HOLD without reasoning."
            )
            logger.info(
                "[ReasoningPlanner] Weak signal (|%.4f| < %.2f) - "
                "CoT skipped, HOLD emitted.",
                consensus_score,
                self._reflection_threshold,
            )
            return trajectory

        # Fetch live MT5 account snapshot (shared across all steps)
        account: Dict[str, float] = _fetch_mt5_account_data()
        margin_per_lot: float     = _fetch_margin_per_lot(self.symbol)

        logger.debug(
            "[ReasoningPlanner] Account snapshot | balance=%.2f | equity=%.2f | "
            "free_margin=%.2f | margin_per_lot=%.2f | source=%s",
            account["balance"],
            account["equity"],
            account["free_margin"],
            margin_per_lot,
            account.get("source", "unknown"),
        )

        # STEP 1 — Margin Availability with Geometric Density Multiplier
        step1 = self._cot_step_margin_availability(
            account=account,
            margin_per_lot=margin_per_lot,
            atr_pips=atr_pips,
        )
        trajectory.add_step(step1)

        if not step1.passed:
            trajectory.final_verdict        = FinalReasoningVerdict.HOLD
            trajectory.chain_halted_at_step = 1
            trajectory.total_elapsed_ms     = (time.perf_counter() - cycle_start) * 1_000
            trajectory.notes = (
                f"CoT chain halted at Step 1 (margin_availability). "
                f"{step1.narrative}"
            )
            trajectory.add_step(self._skipped_step(2, "validate_drawdown_exposure"))
            trajectory.add_step(self._skipped_step(3, "calculate_volatility_adjusted_lot"))
            logger.warning(
                "[ReasoningPlanner] STEP 1 FAILED - chain halted. "
                "required=%.2f free=%.2f",
                step1.threshold,
                step1.computed_value,
            )
            return trajectory

        logger.info("[ReasoningPlanner] STEP 1 PASSED - margin available.")

        # STEP 2 — Drawdown Exposure Cross-Reference
        step2 = self._cot_step_drawdown_exposure(account=account)
        trajectory.add_step(step2)

        if not step2.passed:
            trajectory.final_verdict        = FinalReasoningVerdict.HARD_HOLD
            trajectory.chain_halted_at_step = 2
            trajectory.total_elapsed_ms     = (time.perf_counter() - cycle_start) * 1_000
            trajectory.notes = (
                f"CoT chain halted at Step 2 (drawdown_exposure) - HARD HOLD. "
                f"Drawdown={step2.computed_value:.4f}% exceeds threshold "
                f"{step2.threshold:.1f}%. {step2.narrative}"
            )
            trajectory.add_step(
                self._skipped_step(3, "calculate_volatility_adjusted_lot")
            )
            logger.warning(
                "[ReasoningPlanner] STEP 2 FAILED - HARD HOLD enforced. "
                "drawdown=%.4f%% (limit=%.1f%%)",
                step2.computed_value,
                step2.threshold,
            )
            return trajectory

        logger.info(
            "[ReasoningPlanner] STEP 2 PASSED - drawdown safe (%.4f%%).",
            step2.computed_value,
        )

        # STEP 3 — Volatility-Adjusted Lot Calculation
        step3 = self._cot_step_volatility_adjusted_lot(
            account=account,
            atr_pips=atr_pips,
        )
        trajectory.add_step(step3)

        if not step3.passed:
            trajectory.final_verdict        = FinalReasoningVerdict.HOLD
            trajectory.chain_halted_at_step = 3
            trajectory.total_elapsed_ms     = (time.perf_counter() - cycle_start) * 1_000
            trajectory.notes = (
                f"CoT chain halted at Step 3 (volatility_adjusted_lot). "
                f"{step3.narrative}"
            )
            logger.warning(
                "[ReasoningPlanner] STEP 3 FAILED - lot computation failed."
            )
            return trajectory

        logger.info(
            "[ReasoningPlanner] STEP 3 PASSED - lot_size=%.2f, grid_step=%.2f pips.",
            step3.computed_value,
            atr_pips * self._atr_multiplier,
        )

        # ALL STEPS PASSED — Build deployment vector & delegate to planner
        validated_lot: float   = step3.computed_value  # type: ignore[assignment]
        grid_step_pips: float  = max(atr_pips * self._atr_multiplier, _GRID_STEP_FLOOR_PIPS)
        required_margin: float = validated_lot * margin_per_lot * _GEOMETRIC_MULTIPLIER
        margin_buffer_pct: float = (
            ((account["free_margin"] - required_margin) / required_margin * 100.0)
            if required_margin > 0 else float("inf")
        )
        drawdown_pct: float = (
            (account["balance"] - account["equity"]) / account["balance"] * 100.0
            if account["balance"] > 0 else 0.0
        )
        risk_amount_usd: float = account["equity"] * self._risk_fraction

        deployment_vector = ValidatedDeploymentVector(
            symbol=self.symbol,
            action="BUY" if consensus_score > 0 else "SELL",
            lot_size=validated_lot,
            grid_step_pips=grid_step_pips,
            grid_step_min_pips=grid_step_pips * 0.5,
            grid_step_max_pips=grid_step_pips * 2.0,
            required_margin=required_margin,
            free_margin_available=account["free_margin"],
            margin_buffer_pct=margin_buffer_pct,
            equity=account["equity"],
            balance=account["balance"],
            drawdown_pct=drawdown_pct,
            atr_pips=atr_pips,
            risk_amount_usd=risk_amount_usd,
            pip_value_per_lot=self._pip_value_per_lot,
            mandate_id=uuid.uuid4().hex[:16],
            reasoning_id=reasoning_id,
        )

        # Invoke the underlying deterministic planner for the full typed mandate
        mandate: ExecutionMandate = self._planner.run_bar_close_cycle(
            bar_timestamp=bar_timestamp,
            atr_pips=atr_pips,
        )

        total_elapsed_ms: float = (time.perf_counter() - cycle_start) * 1_000

        trajectory.final_verdict     = FinalReasoningVerdict.PASS
        trajectory.deployment_vector = deployment_vector
        trajectory.mandate           = mandate
        trajectory.total_elapsed_ms  = total_elapsed_ms
        trajectory.notes = (
            f"All 3 CoT steps passed in {total_elapsed_ms:.1f}ms. "
            f"Action: {deployment_vector.action} | "
            f"Lot: {deployment_vector.lot_size:.2f} | "
            f"Grid step: {deployment_vector.grid_step_pips:.1f} pips | "
            f"Margin buffer: {deployment_vector.margin_buffer_pct:.1f}% | "
            f"Drawdown: {deployment_vector.drawdown_pct:.2f}%"
        )

        logger.info(
            "[ReasoningPlanner] COT PASS | action=%s | lot=%.2f | "
            "grid_step=%.2f pips | margin_buffer=%.1f%% | elapsed=%.1f ms",
            deployment_vector.action,
            deployment_vector.lot_size,
            deployment_vector.grid_step_pips,
            deployment_vector.margin_buffer_pct,
            total_elapsed_ms,
        )

        return trajectory

    # -----------------------------------------------------------------------
    # CoT Step Implementations
    # -----------------------------------------------------------------------

    def _cot_step_margin_availability(
        self,
        account: Dict[str, float],
        margin_per_lot: float,
        atr_pips: float,
    ) -> CoTStepResult:
        """
        STEP 1: Validate that free margin supports the full geometric grid density.

        Mathematical Derivation
        -----------------------
        Grid expands across _GRID_DENSITY_STEPS levels, each level doubling
        the lot size (geometric ratio r=2). The total capital exposure is:

            required_margin = lot x margin_per_lot x Sum(r^i, i=0..n-1)
                            = lot x margin_per_lot x 7     (for n=3, r=2)

        Where lot is the base lot size at grid level 0.

        The base lot here is computed from the provisional risk fraction:

            provisional_lot = (equity x risk_fraction)
                              / (atr_step_pips x pip_value_per_lot)
        """
        step_start = time.perf_counter()

        equity: float      = account["equity"]
        free_margin: float = account["free_margin"]
        balance: float     = account["balance"]

        grid_step_pips: float  = max(atr_pips * self._atr_multiplier, _GRID_STEP_FLOOR_PIPS)
        risk_amount: float     = equity * self._risk_fraction
        provisional_lot: float = risk_amount / (grid_step_pips * self._pip_value_per_lot)
        provisional_lot = float(
            max(_LOT_MIN, min(_LOT_MAX, round(provisional_lot / 0.01) * 0.01))
        )

        required_margin: float = provisional_lot * margin_per_lot * _GEOMETRIC_MULTIPLIER
        elapsed_ms: float      = (time.perf_counter() - step_start) * 1_000
        passed: bool           = free_margin >= required_margin

        if passed:
            buffer_pct = ((free_margin - required_margin) / required_margin * 100.0)
            narrative = (
                f"Margin check PASSED. "
                f"Free margin=${free_margin:,.2f} covers required grid margin "
                f"${required_margin:,.2f} (geometric multiplier={_GEOMETRIC_MULTIPLIER:.0f}x, "
                f"provisional_lot={provisional_lot:.2f}, margin_per_lot={margin_per_lot:.2f}). "
                f"Buffer: {buffer_pct:.1f}% above threshold. "
                f"Equity=${equity:,.2f} | Balance=${balance:,.2f}."
            )
        else:
            shortfall = required_margin - free_margin
            narrative = (
                f"Margin check FAILED. "
                f"Free margin=${free_margin:,.2f} is INSUFFICIENT for "
                f"${required_margin:,.2f} required (shortfall=${shortfall:,.2f}). "
                f"Geometric density: {_GRID_DENSITY_STEPS} steps, "
                f"ratio={_GRID_DENSITY_RATIO:.0f}x, multiplier={_GEOMETRIC_MULTIPLIER:.0f}x. "
                f"Provisional lot={provisional_lot:.2f}, margin_per_lot={margin_per_lot:.2f}. "
                f"Grid deployment BLOCKED - HOLD emitted."
            )

        logger.debug(
            "[CoT Step 1] margin_avail | free_margin=%.2f | required=%.2f | "
            "passed=%s | %.1f ms",
            free_margin, required_margin, passed, elapsed_ms,
        )

        return CoTStepResult(
            step_index=1,
            step_name="validate_margin_availability",
            verdict=CoTVerdict.PASS if passed else CoTVerdict.FAIL,
            passed=passed,
            computed_value=round(free_margin, 4),
            threshold=round(required_margin, 4),
            narrative=narrative,
            elapsed_ms=elapsed_ms,
        )

    def _cot_step_drawdown_exposure(
        self,
        account: Dict[str, float],
    ) -> CoTStepResult:
        """
        STEP 2: Cross-reference active asset drawdown against the 5% hard stop.

        Mathematical Derivation
        -----------------------
        Unrealized drawdown percentage:

            drawdown_pct = (balance - equity) / balance x 100

        If drawdown_pct exceeds drawdown_hard_stop_pct (default: 5.0%),
        execution is immediately halted and HARD HOLD is emitted.

        The hard stop is intentionally account-wide (not per-asset) because
        drawdown in one instrument typically reflects correlated market stress.
        """
        step_start = time.perf_counter()

        balance: float = account["balance"]
        equity:  float = account["equity"]

        if balance <= 0.0:
            elapsed_ms = (time.perf_counter() - step_start) * 1_000
            return CoTStepResult(
                step_index=2,
                step_name="validate_drawdown_exposure",
                verdict=CoTVerdict.FAIL,
                passed=False,
                computed_value=0.0,
                threshold=self._dd_hard_stop_pct,
                narrative=(
                    f"Drawdown check FAILED: account balance is zero or negative "
                    f"(balance={balance:.2f}). Cannot compute drawdown safely. "
                    "HARD HOLD enforced."
                ),
                elapsed_ms=elapsed_ms,
            )

        floating_pnl: float = equity - balance
        drawdown_pct: float = max(0.0, (balance - equity) / balance * 100.0)
        passed: bool        = drawdown_pct < self._dd_hard_stop_pct
        elapsed_ms: float   = (time.perf_counter() - step_start) * 1_000

        if passed:
            headroom_pct = self._dd_hard_stop_pct - drawdown_pct
            narrative = (
                f"Drawdown check PASSED. "
                f"Current unrealized drawdown={drawdown_pct:.4f}% "
                f"is safely below hard-stop threshold={self._dd_hard_stop_pct:.1f}%. "
                f"Floating P&L=${floating_pnl:+,.2f} | "
                f"Headroom before halt: {headroom_pct:.4f}%. "
                f"Account equity=${equity:,.2f} / balance=${balance:,.2f}."
            )
        else:
            excess_pct = drawdown_pct - self._dd_hard_stop_pct
            narrative = (
                f"Drawdown check FAILED - HARD HOLD. "
                f"Unrealized drawdown={drawdown_pct:.4f}% EXCEEDS "
                f"hard-stop threshold={self._dd_hard_stop_pct:.1f}% "
                f"(excess={excess_pct:.4f}%). "
                f"Floating P&L=${floating_pnl:+,.2f} "
                f"(equity=${equity:,.2f}, balance=${balance:,.2f}). "
                f"ALL new trade mandates suppressed until drawdown recovers."
            )

        logger.debug(
            "[CoT Step 2] drawdown_exposure | dd=%.4f%% | threshold=%.1f%% | "
            "passed=%s | %.1f ms",
            drawdown_pct, self._dd_hard_stop_pct, passed, elapsed_ms,
        )

        return CoTStepResult(
            step_index=2,
            step_name="validate_drawdown_exposure",
            verdict=CoTVerdict.PASS if passed else CoTVerdict.FAIL,
            passed=passed,
            computed_value=round(drawdown_pct, 6),
            threshold=self._dd_hard_stop_pct,
            narrative=narrative,
            elapsed_ms=elapsed_ms,
        )

    def _cot_step_volatility_adjusted_lot(
        self,
        account: Dict[str, float],
        atr_pips: float,
    ) -> CoTStepResult:
        """
        STEP 3: Derive the volatility-adjusted lot size using fixed-fractional risk.

        Mathematical Derivation
        -----------------------
        Grid step spacing:
            grid_step_pips = max(ATR_pips x atr_multiplier, grid_step_floor)

        Fixed-fractional lot (caps max risk at risk_fraction of equity):
            risk_amount_USD  = equity x risk_fraction      (= equity x 0.015)
            pip_risk_USD     = grid_step_pips x pip_value_per_lot
            lot_size         = risk_amount_USD / pip_risk_USD

        Clamped to broker range:
            lot_size = clamp(round(lot_size, 2), _LOT_MIN=0.01, _LOT_MAX=10.0)

        This ensures no more than 1.5% of equity is risked per entry.
        """
        step_start = time.perf_counter()

        equity: float = account["equity"]

        if equity <= 0.0:
            elapsed_ms = (time.perf_counter() - step_start) * 1_000
            return CoTStepResult(
                step_index=3,
                step_name="calculate_volatility_adjusted_lot",
                verdict=CoTVerdict.FAIL,
                passed=False,
                computed_value=0.0,
                threshold=_LOT_MAX,
                narrative=(
                    f"Lot calculation FAILED: equity={equity:.2f} is zero or "
                    "negative. Cannot compute risk-adjusted lot size."
                ),
                elapsed_ms=elapsed_ms,
            )

        if atr_pips <= 0.0:
            elapsed_ms = (time.perf_counter() - step_start) * 1_000
            return CoTStepResult(
                step_index=3,
                step_name="calculate_volatility_adjusted_lot",
                verdict=CoTVerdict.FAIL,
                passed=False,
                computed_value=0.0,
                threshold=_LOT_MAX,
                narrative=(
                    f"Lot calculation FAILED: atr_pips={atr_pips:.4f} is zero or "
                    "negative. ATR must be a positive number from the data layer."
                ),
                elapsed_ms=elapsed_ms,
            )

        grid_step_pips: float  = max(atr_pips * self._atr_multiplier, _GRID_STEP_FLOOR_PIPS)
        risk_amount_usd: float = equity * self._risk_fraction
        pip_risk_usd: float    = grid_step_pips * self._pip_value_per_lot
        raw_lot_size: float    = risk_amount_usd / pip_risk_usd

        lot_size: float = float(
            max(_LOT_MIN, min(_LOT_MAX, round(raw_lot_size / 0.01) * 0.01))
        )

        clamped: bool     = (raw_lot_size < _LOT_MIN or raw_lot_size > _LOT_MAX)
        elapsed_ms: float = (time.perf_counter() - step_start) * 1_000

        narrative: str = (
            f"Lot calculation PASSED. "
            f"ATR={atr_pips:.2f} pips | "
            f"grid_step={grid_step_pips:.2f} pips "
            f"(ATR x {self._atr_multiplier:.1f}, floor={_GRID_STEP_FLOOR_PIPS:.0f}p) | "
            f"risk_amount=${risk_amount_usd:,.2f} "
            f"(equity=${equity:,.2f} x {self._risk_fraction * 100:.1f}%) | "
            f"pip_risk=${pip_risk_usd:,.3f}/lot | "
            f"raw_lot={raw_lot_size:.4f} -> validated_lot={lot_size:.2f}"
        )
        if clamped:
            narrative += (
                f" [CLAMPED: raw={raw_lot_size:.4f} was outside [{_LOT_MIN},{_LOT_MAX}]]"
            )

        logger.debug(
            "[CoT Step 3] vol_adj_lot | atr=%.2f pips | grid_step=%.2f | "
            "risk_usd=%.2f | raw_lot=%.4f | final_lot=%.2f | %.1f ms",
            atr_pips, grid_step_pips, risk_amount_usd, raw_lot_size, lot_size, elapsed_ms,
        )

        return CoTStepResult(
            step_index=3,
            step_name="calculate_volatility_adjusted_lot",
            verdict=CoTVerdict.PASS,
            passed=True,
            computed_value=round(lot_size, 4),
            threshold=_LOT_MAX,
            narrative=narrative,
            elapsed_ms=elapsed_ms,
        )

    # -----------------------------------------------------------------------
    # Utility Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _skipped_step(index: int, name: str) -> CoTStepResult:
        """Construct a SKIPPED sentinel step for chain short-circuit bookkeeping."""
        return CoTStepResult(
            step_index=index,
            step_name=name,
            verdict=CoTVerdict.SKIPPED,
            passed=False,
            computed_value=None,
            threshold=None,
            narrative=(
                f"Step '{name}' was NOT reached because an earlier step "
                f"in the CoT chain failed and halted execution."
            ),
            elapsed_ms=0.0,
        )

    @property
    def geometric_multiplier(self) -> float:
        """
        Return the precomputed geometric density multiplier.
        Sum(ratio^i, i=0..n-1) where n=_GRID_DENSITY_STEPS, ratio=_GRID_DENSITY_RATIO.
        For n=3, r=2: 1+2+4 = 7.0
        """
        return _GEOMETRIC_MULTIPLIER

    def __repr__(self) -> str:
        return (
            f"QuantumReasoningPlanner("
            f"symbol={self.symbol!r}, "
            f"pip_val={self._pip_value_per_lot}, "
            f"dd_stop={self._dd_hard_stop_pct}%, "
            f"risk_frac={self._risk_fraction}, "
            f"geometric_multiplier={self.geometric_multiplier}x)"
        )
