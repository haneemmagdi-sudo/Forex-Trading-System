"""
==============================================================================
agents/consensus_engine.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Mathematical Consensus Engine
Author : Principal AI Systems Architect
Version: 4.2.0

Overview
--------
Implements the ``ConsensusEngine`` — the mathematical aggregation layer that
converts four independent, often-conflicting sub-model predictions into a
single, unified, actionable execution mandate.

Mathematical Framework
----------------------
The consensus algorithm applies a **Weighted Aggregated Score** formula:

    Score = Σ  (Direction_i × Confidence_i × Weight_i)
           i∈{timesfm, dqn, random_forest, sentiment}

Where:
    Direction_i  ∈ {+1.0 (BUY), 0.0 (HOLD), -1.0 (SELL)}
    Confidence_i ∈ [0.0, 1.0]
    Weight_i     ∈ (0.0, 1.0),  Σ Weight_i = 1.0

The resulting Score is bounded by [-1.0, +1.0] and maps to a final
execution directive via a **Threshold Gate**:

    Score ≥ +0.75  →  BUY  (strong bullish consensus)
    Score ≤ -0.75  →  SELL (strong bearish consensus)
    otherwise      →  HOLD (insufficient conviction — capital preserved)

Weight Allocation Matrix
------------------------
    ┌──────────────────────────┬────────┬──────────────────────────────┐
    │ Agent                    │ Weight │ Rationale                    │
    ├──────────────────────────┼────────┼──────────────────────────────┤
    │ Google TimesFM           │  35%   │ Price trend direction leader  │
    │ Deep Q-Network (DQN)     │  30%   │ Value/Policy action strength  │
    │ Random Forest            │  20%   │ Technical indicator signal    │
    │ Sentiment NLP            │  15%   │ Real-time news polarity       │
    └──────────────────────────┴────────┴──────────────────────────────┘

Design Notes
------------
- The engine is **stateless** with respect to market data.  Each call to
  ``evaluate()`` is fully atomic and independent of prior calls.
- Weight configuration is injected at construction and can be overridden
  per-symbol or per-timeframe without modifying the class.
- The engine operates on a snapshot from the Blackboard — it does NOT
  acquire or hold the Blackboard lock.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Final, List, Optional, Tuple

from agents.blackboard import QuantumBlackboard, SignalDirection, SignalPayload

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.consensus_engine")


# ===========================================================================
# Constants & Default Configuration
# ===========================================================================

# Default weight allocation matrix — must sum to exactly 1.0
_DEFAULT_WEIGHTS: Final[Dict[str, float]] = {
    "timesfm":      0.35,   # 35% — Google TimesFM price trend direction
    "dqn":          0.30,   # 30% — Deep Q-Network value/policy component
    "random_forest": 0.20,  # 20% — Random Forest technical indicator
    "sentiment":    0.15,   # 15% — Sentiment NLP real-time news component
}

# Threshold boundaries for BUY / HOLD / SELL verdict
_BUY_THRESHOLD:  Final[float] = +0.75
_SELL_THRESHOLD: Final[float] = -0.75

# Minimum number of ACTIVE agents required to compute a consensus.
# If fewer agents have posted, the engine forces HOLD (insufficient quorum).
_MINIMUM_QUORUM: Final[int] = 2


# ===========================================================================
# Output Data Structures
# ===========================================================================

class ConsensusAction(str, Enum):
    """
    Unified execution mandate produced by the Consensus Engine.

    Values
    ------
    BUY  : Strong bullish consensus; open or extend long positions.
    SELL : Strong bearish consensus; open or extend short positions.
    HOLD : Insufficient conviction; preserve capital, no new trades.
    """
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class AgentContribution:
    """
    Per-agent breakdown of the consensus calculation.

    Attributes
    ----------
    agent_id : str
        Identifier of the contributing agent.
    direction_label : str
        Human-readable direction: "BUY", "SELL", or "HOLD".
    numerical_direction : float
        Signed float (+1.0, 0.0, -1.0) derived from the direction label.
    confidence_score : float
        Agent's raw confidence in [0.0, 1.0].
    weight : float
        Assigned consensus weight for this agent.
    weighted_contribution : float
        ``numerical_direction × confidence_score × weight`` — this agent's
        net contribution to the aggregated score.
    """
    agent_id: str
    direction_label: str
    numerical_direction: float
    confidence_score: float
    weight: float
    weighted_contribution: float


@dataclass(frozen=True)
class ConsensusResult:
    """
    Immutable output payload from a single ``ConsensusEngine.evaluate()`` call.

    Attributes
    ----------
    action : ConsensusAction
        The unified execution directive: BUY, SELL, or HOLD.
    aggregated_score : float
        The raw weighted sum in [-1.0, +1.0].  The further this is from
        zero, the stronger the consensus.
    buy_threshold : float
        The minimum score required to emit a BUY signal (default +0.75).
    sell_threshold : float
        The maximum score that triggers a SELL signal (default -0.75).
    agent_contributions : List[AgentContribution]
        Per-agent breakdown of directional scores and weighted contributions.
    active_agent_count : int
        Number of agents whose signals were included in the calculation.
    missing_agents : List[str]
        Agent IDs that were absent or stale and therefore excluded.
    timestamp : float
        UNIX epoch seconds when this consensus was computed.
    is_partial_quorum : bool
        True if the result is based on fewer than 4 active agents.

    Properties
    ----------
    is_actionable : bool
        True if the action is BUY or SELL (capital will be deployed).
    consensus_strength_pct : float
        The absolute magnitude of ``aggregated_score`` expressed as a
        percentage of the threshold distance, ranging from 0.0 to 100.0+.
        Values above 100.0 indicate strong over-threshold conviction.
    """
    action: ConsensusAction
    aggregated_score: float
    buy_threshold: float
    sell_threshold: float
    agent_contributions: List[AgentContribution]
    active_agent_count: int
    missing_agents: List[str]
    timestamp: float = field(default_factory=time.time)
    is_partial_quorum: bool = False

    @property
    def is_actionable(self) -> bool:
        """True if the action is BUY or SELL (a trade will be opened)."""
        return self.action != ConsensusAction.HOLD

    @property
    def consensus_strength_pct(self) -> float:
        """
        Express how far the aggregated score is from zero relative to the
        threshold, as a percentage.

        Returns
        -------
        float
            0.0 when all agents agree on HOLD (score = 0).
            100.0 when score exactly equals the relevant threshold.
            > 100.0 when the score exceeds the threshold with margin.
        """
        threshold = self.buy_threshold if self.aggregated_score >= 0 else abs(self.sell_threshold)
        if threshold == 0.0:
            return 0.0
        return round(abs(self.aggregated_score) / threshold * 100.0, 2)

    def summary(self) -> str:
        """Return a compact human-readable summary of this consensus result."""
        quorum_flag = " [PARTIAL QUORUM]" if self.is_partial_quorum else ""
        actionable_flag = "🟢 EXECUTE" if self.is_actionable else "🔒 HOLD"
        return (
            f"[{actionable_flag}] {self.action.value} | "
            f"Score={self.aggregated_score:+.4f} | "
            f"Strength={self.consensus_strength_pct:.1f}% | "
            f"Agents={self.active_agent_count}/4"
            f"{quorum_flag}"
        )

    def to_dict(self) -> Dict:
        """Return a JSON-serializable plain dictionary representation."""
        return {
            "action":                self.action.value,
            "aggregated_score":      round(self.aggregated_score, 6),
            "buy_threshold":         self.buy_threshold,
            "sell_threshold":        self.sell_threshold,
            "consensus_strength_pct":self.consensus_strength_pct,
            "is_actionable":         self.is_actionable,
            "active_agent_count":    self.active_agent_count,
            "missing_agents":        self.missing_agents,
            "is_partial_quorum":     self.is_partial_quorum,
            "timestamp":             self.timestamp,
            "agent_contributions": [
                {
                    "agent_id":              c.agent_id,
                    "direction":             c.direction_label,
                    "numerical_direction":   c.numerical_direction,
                    "confidence_score":      round(c.confidence_score, 6),
                    "weight":                c.weight,
                    "weighted_contribution": round(c.weighted_contribution, 6),
                }
                for c in self.agent_contributions
            ],
        }


# ===========================================================================
# ConsensusEngine — Mathematical Aggregation Layer
# ===========================================================================

class ConsensusEngine:
    """
    Evaluates the Blackboard state using a Weighted Aggregated Score formula
    and emits a unified execution mandate for the Planner Agent.

    The engine is **stateless** — each ``evaluate()`` call is independent.
    Multiple concurrent calls from different threads are safe because the
    method only reads from an immutable Blackboard snapshot.

    Parameters
    ----------
    weights : Dict[str, float], optional
        Custom weight allocation matrix.  If not provided, the default
        matrix is used:
            timesfm=0.35, dqn=0.30, random_forest=0.20, sentiment=0.15
        Custom weights MUST sum to 1.0 (±1e-6 tolerance).
    buy_threshold : float, optional
        Minimum aggregated score to emit BUY.  Default: +0.75.
    sell_threshold : float, optional
        Maximum aggregated score to emit SELL.  Default: -0.75.
    minimum_quorum : int, optional
        Minimum number of active agent signals required for a non-HOLD
        result.  Default: 2.  If fewer signals are present, the engine
        forces HOLD regardless of scores.

    Raises
    ------
    ValueError
        On invalid weight configuration (wrong sum or negative values).

    Examples
    --------
    >>> bb = QuantumBlackboard()
    >>> # ... agents post their signals to the board ...
    >>> engine = ConsensusEngine()
    >>> result = engine.evaluate(bb)
    >>> print(result.summary())
    [🟢 EXECUTE] BUY | Score=+0.8105 | Strength=108.1% | Agents=4/4
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        buy_threshold: float = _BUY_THRESHOLD,
        sell_threshold: float = _SELL_THRESHOLD,
        minimum_quorum: int = _MINIMUM_QUORUM,
    ) -> None:
        """
        Initialize the ConsensusEngine with an optional custom weight matrix.

        Parameters
        ----------
        weights : dict, optional
            Agent weight mapping.  Must sum to 1.0 (±1e-6 tolerance).
        buy_threshold : float
            Minimum score to trigger BUY.  Must be in (0, 1].
        sell_threshold : float
            Maximum score to trigger SELL.  Must be in [-1, 0).
        minimum_quorum : int
            Minimum active agents for a non-HOLD result.  Must be ≥ 1.
        """
        self._weights: Dict[str, float] = self._validate_weights(
            weights if weights is not None else dict(_DEFAULT_WEIGHTS)
        )
        self._buy_threshold: float = self._validate_threshold(
            buy_threshold, "buy_threshold", expected_sign="positive"
        )
        self._sell_threshold: float = self._validate_threshold(
            sell_threshold, "sell_threshold", expected_sign="negative"
        )
        self._minimum_quorum: int = self._validate_quorum(minimum_quorum)

        logger.info(
            "[ConsensusEngine] Initialized | "
            "Weights=%s | BUY_threshold=%.4f | SELL_threshold=%.4f | "
            "Min_quorum=%d",
            {k: f"{v:.0%}" for k, v in self._weights.items()},
            self._buy_threshold,
            self._sell_threshold,
            self._minimum_quorum,
        )

    # -------------------------------------------------------------------
    # Primary Evaluation Interface
    # -------------------------------------------------------------------

    def evaluate(self, blackboard: QuantumBlackboard) -> ConsensusResult:
        """
        Evaluate the current Blackboard state and produce a consensus verdict.

        Algorithm Steps
        ---------------
        1. Extract all ACTIVE signals from the Blackboard via
           ``get_all_active_signals()`` (snapshot, lock is released
           immediately after).
        2. Check quorum.  If fewer agents than ``_minimum_quorum`` have
           posted, emit HOLD to avoid acting on sparse data.
        3. For each active agent signal, compute:
               contribution_i = Direction_i × Confidence_i × Weight_i
           using the numerical mapping BUY=+1, SELL=-1, HOLD=0.
        4. Sum all contributions to produce the ``aggregated_score``.
        5. Apply the threshold gate:
               score ≥ +buy_threshold  →  BUY
               score ≤ -sell_threshold →  SELL
               otherwise               →  HOLD

        Parameters
        ----------
        blackboard : QuantumBlackboard
            The live Blackboard instance to read signals from.  Must not
            be None.

        Returns
        -------
        ConsensusResult
            An immutable, fully-populated consensus verdict with per-agent
            contribution breakdown.

        Raises
        ------
        TypeError
            If ``blackboard`` is not a ``QuantumBlackboard`` instance.

        Examples
        --------
        >>> engine = ConsensusEngine()
        >>> result = engine.evaluate(bb)
        >>> if result.is_actionable:
        ...     execute_trade(result.action, risk_params)
        """
        if not isinstance(blackboard, QuantumBlackboard):
            raise TypeError(
                f"evaluate() expects a QuantumBlackboard instance; "
                f"received {type(blackboard).__name__}."
            )

        evaluation_ts = time.time()

        # Step 1: Snapshot all active signals (atomic read)
        active_signals: Dict[str, SignalPayload] = blackboard.get_all_active_signals()

        # Step 2: Quorum check
        active_count = len(active_signals)
        all_registered = list(QuantumBlackboard.REGISTERED_AGENTS)
        missing = sorted(set(all_registered) - set(active_signals.keys()))
        is_partial = active_count < len(QuantumBlackboard.REGISTERED_AGENTS)

        if active_count < self._minimum_quorum:
            logger.warning(
                "[ConsensusEngine] ⚠️ QUORUM FAILURE — only %d/%d agents active "
                "(minimum required: %d).  Missing: %s.  Forcing HOLD.",
                active_count,
                len(QuantumBlackboard.REGISTERED_AGENTS),
                self._minimum_quorum,
                missing,
            )
            return ConsensusResult(
                action=ConsensusAction.HOLD,
                aggregated_score=0.0,
                buy_threshold=self._buy_threshold,
                sell_threshold=self._sell_threshold,
                agent_contributions=[],
                active_agent_count=active_count,
                missing_agents=missing,
                timestamp=evaluation_ts,
                is_partial_quorum=True,
            )

        # Step 3 & 4: Compute weighted aggregated score
        contributions: List[AgentContribution] = []
        aggregated_score: float = 0.0
        active_weight: float = 0.0

        for agent_id, payload in active_signals.items():
            weight: float = self._weights.get(agent_id, 0.0)

            if weight == 0.0:
                logger.warning(
                    "[ConsensusEngine] Agent %r has no weight allocation — "
                    "contribution will be zero.  Add to weight matrix.",
                    agent_id,
                )

            # Map direction enum to signed numeric value
            numerical_dir: float = payload.numerical_direction()

            # Core formula: contribution_i = direction_i × confidence_i × weight_i
            contribution: float = numerical_dir * payload.confidence_score * weight
            aggregated_score += contribution
            active_weight += weight

            agent_contrib = AgentContribution(
                agent_id=agent_id,
                direction_label=payload.signal_direction.value,
                numerical_direction=numerical_dir,
                confidence_score=payload.confidence_score,
                weight=weight,
                weighted_contribution=round(contribution, 8),
            )
            contributions.append(agent_contrib)

            logger.debug(
                "[ConsensusEngine] %s | dir=%s(%.1f) × conf=%.4f × w=%.2f "
                "= contribution=%.6f",
                agent_id,
                payload.signal_direction.value,
                numerical_dir,
                payload.confidence_score,
                weight,
                contribution,
            )

        # التطبيع بمجموع أوزان الوكلاء النشطين فقط:
        # يجعل العتبة ±0.75 تعني «اتفاق مرجّح ≥ 75%» بدل «مجموع مرجّح»، فيبقى
        # الحكم قابلاً للعبور عند غياب مُنتِج (لا أوزان مُدرَّبة لـ timesfm/dqn)
        # بدل أن يستحيل رياضياً. وعند اكتمال المنتجين الأربعة يكون المجموع 1.0
        # فالتطبيع بلا أي أثر على السلوك الأصلي.
        if active_weight > 0:
            aggregated_score = aggregated_score / active_weight

        # Clamp to [-1.0, +1.0] to handle floating-point edge cases
        aggregated_score = max(-1.0, min(1.0, aggregated_score))

        # Step 5: Threshold gate decision
        action, gate_reason = self._apply_threshold_gate(aggregated_score)

        # Sort contributions by absolute contribution magnitude (descending)
        contributions.sort(
            key=lambda c: abs(c.weighted_contribution), reverse=True
        )

        result = ConsensusResult(
            action=action,
            aggregated_score=round(aggregated_score, 8),
            buy_threshold=self._buy_threshold,
            sell_threshold=self._sell_threshold,
            agent_contributions=contributions,
            active_agent_count=active_count,
            missing_agents=missing,
            timestamp=evaluation_ts,
            is_partial_quorum=is_partial,
        )

        logger.info(
            "[ConsensusEngine] %s | score=%+.4f | gate=%s | "
            "active_agents=%d/4 | missing=%s",
            result.summary(),
            aggregated_score,
            gate_reason,
            active_count,
            missing if missing else "none",
        )

        return result

    # -------------------------------------------------------------------
    # Score → Action Gate Logic
    # -------------------------------------------------------------------

    def _apply_threshold_gate(
        self, score: float
    ) -> Tuple[ConsensusAction, str]:
        """
        Apply the threshold gate to map the aggregated score to a final
        ``ConsensusAction``.

        Parameters
        ----------
        score : float
            The weighted aggregated score in [-1.0, +1.0].

        Returns
        -------
        Tuple[ConsensusAction, str]
            The resolved action and a human-readable gate description string
            for logging.

        Decision Table
        --------------
        score ≥ +0.75  →  BUY  (strong bullish multi-model consensus)
        score ≤ -0.75  →  SELL (strong bearish multi-model consensus)
        -0.75 < s < +0.75 → HOLD (ambiguous signal — capital preserved)
        """
        if score >= self._buy_threshold:
            return (
                ConsensusAction.BUY,
                f"score={score:+.4f} >= BUY_threshold={self._buy_threshold:+.4f}",
            )
        elif score <= self._sell_threshold:
            return (
                ConsensusAction.SELL,
                f"score={score:+.4f} <= SELL_threshold={self._sell_threshold:+.4f}",
            )
        else:
            return (
                ConsensusAction.HOLD,
                f"score={score:+.4f} in ambiguous zone "
                f"[{self._sell_threshold:+.4f}, {self._buy_threshold:+.4f}]",
            )

    # -------------------------------------------------------------------
    # Configuration Accessors
    # -------------------------------------------------------------------

    @property
    def weights(self) -> Dict[str, float]:
        """Return a copy of the current weight allocation matrix."""
        return dict(self._weights)

    @property
    def buy_threshold(self) -> float:
        """Return the minimum aggregated score required to emit BUY."""
        return self._buy_threshold

    @property
    def sell_threshold(self) -> float:
        """Return the maximum aggregated score that triggers SELL."""
        return self._sell_threshold

    def get_configuration(self) -> Dict:
        """
        Return the complete engine configuration as a plain dictionary.

        Useful for logging, REST API endpoints, and dashboard displays.

        Returns
        -------
        dict
            Keys: ``"weights"``, ``"buy_threshold"``, ``"sell_threshold"``,
            ``"minimum_quorum"``.
        """
        return {
            "weights": dict(self._weights),
            "buy_threshold":  self._buy_threshold,
            "sell_threshold": self._sell_threshold,
            "minimum_quorum": self._minimum_quorum,
        }

    # -------------------------------------------------------------------
    # Scenario Simulation (for backtesting / unit testing)
    # -------------------------------------------------------------------

    def evaluate_from_dict(
        self,
        signals: Dict[str, Dict],
    ) -> ConsensusResult:
        """
        Evaluate a hypothetical signal scenario provided as a plain dictionary,
        bypassing the Blackboard entirely.

        This method is designed for **backtesting, unit testing, and
        parameter tuning** — it allows the engine to be exercised without
        a live Blackboard or market data feed.

        Parameters
        ----------
        signals : Dict[str, Dict]
            A dictionary mapping ``agent_id`` to a sub-dict with keys:
                ``"signal_direction"`` : str ("BUY", "SELL", or "HOLD")
                ``"confidence_score"`` : float in [0.0, 1.0]

        Returns
        -------
        ConsensusResult
            Consensus result computed from the provided hypothetical signals.

        Raises
        ------
        ValueError
            If any signal entry is malformed (missing keys or invalid values).

        Examples
        --------
        >>> engine = ConsensusEngine()
        >>> result = engine.evaluate_from_dict({
        ...     "timesfm":       {"signal_direction": "SELL", "confidence_score": 0.91},
        ...     "dqn":           {"signal_direction": "HOLD", "confidence_score": 0.60},
        ...     "random_forest": {"signal_direction": "BUY",  "confidence_score": 0.74},
        ...     "sentiment":     {"signal_direction": "SELL", "confidence_score": 0.55},
        ... })
        >>> print(result.action.value, result.aggregated_score)
        SELL -0.4985
        """
        evaluation_ts = time.time()

        _direction_map: Dict[str, float] = {
            "BUY":  +1.0,
            "SELL": -1.0,
            "HOLD":  0.0,
        }

        contributions: List[AgentContribution] = []
        aggregated_score: float = 0.0
        valid_agents: List[str] = []

        for agent_id, signal_data in signals.items():
            # Validate required keys
            if "signal_direction" not in signal_data:
                raise ValueError(
                    f"Signal for agent_id={agent_id!r} is missing "
                    f"'signal_direction' key."
                )
            if "confidence_score" not in signal_data:
                raise ValueError(
                    f"Signal for agent_id={agent_id!r} is missing "
                    f"'confidence_score' key."
                )

            direction_str = str(signal_data["signal_direction"]).upper()
            if direction_str not in _direction_map:
                raise ValueError(
                    f"Invalid signal_direction={direction_str!r} for "
                    f"agent_id={agent_id!r}.  Must be BUY, SELL, or HOLD."
                )

            conf = float(signal_data["confidence_score"])
            if not (0.0 <= conf <= 1.0):
                raise ValueError(
                    f"confidence_score={conf} for agent_id={agent_id!r} "
                    f"must be in [0.0, 1.0]."
                )

            numerical_dir = _direction_map[direction_str]
            weight = self._weights.get(agent_id, 0.0)
            contribution = numerical_dir * conf * weight
            aggregated_score += contribution
            valid_agents.append(agent_id)

            contributions.append(AgentContribution(
                agent_id=agent_id,
                direction_label=direction_str,
                numerical_direction=numerical_dir,
                confidence_score=round(conf, 6),
                weight=weight,
                weighted_contribution=round(contribution, 8),
            ))

        aggregated_score = max(-1.0, min(1.0, aggregated_score))
        all_registered = list(QuantumBlackboard.REGISTERED_AGENTS)
        missing = sorted(set(all_registered) - set(valid_agents))
        active_count = len(valid_agents)

        if active_count < self._minimum_quorum:
            return ConsensusResult(
                action=ConsensusAction.HOLD,
                aggregated_score=0.0,
                buy_threshold=self._buy_threshold,
                sell_threshold=self._sell_threshold,
                agent_contributions=[],
                active_agent_count=active_count,
                missing_agents=missing,
                timestamp=evaluation_ts,
                is_partial_quorum=True,
            )

        action, _ = self._apply_threshold_gate(aggregated_score)
        contributions.sort(
            key=lambda c: abs(c.weighted_contribution), reverse=True
        )

        return ConsensusResult(
            action=action,
            aggregated_score=round(aggregated_score, 8),
            buy_threshold=self._buy_threshold,
            sell_threshold=self._sell_threshold,
            agent_contributions=contributions,
            active_agent_count=active_count,
            missing_agents=missing,
            timestamp=evaluation_ts,
            is_partial_quorum=len(missing) > 0,
        )

    # -------------------------------------------------------------------
    # Internal Validation Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
        """
        Validate that the provided weight dictionary is internally consistent.

        Checks performed:
        - All values are non-negative floats.
        - The values sum to 1.0 within a 1e-6 tolerance.

        Parameters
        ----------
        weights : dict
            Agent_id → weight mapping to validate.

        Returns
        -------
        Dict[str, float]
            The validated (and normalised if within tolerance) weight dict.

        Raises
        ------
        ValueError
            If any weight is negative or the sum deviates from 1.0 by
            more than 1e-6.
        """
        for agent_id, w in weights.items():
            if w < 0.0:
                raise ValueError(
                    f"Weight for agent_id={agent_id!r} must be non-negative; "
                    f"received {w}."
                )

        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0 (received sum={total:.8f}).  "
                f"Adjust your weight allocation matrix."
            )

        return {k: round(v, 8) for k, v in weights.items()}

    @staticmethod
    def _validate_threshold(
        value: float, name: str, expected_sign: str
    ) -> float:
        """
        Validate that a threshold value has the correct sign and magnitude.

        Parameters
        ----------
        value : float
            The threshold value to validate.
        name : str
            Name of the parameter (used in error messages).
        expected_sign : str
            Either "positive" (for buy_threshold) or "negative" (for
            sell_threshold).

        Returns
        -------
        float
            The validated threshold value.

        Raises
        ------
        ValueError
            If the value has the wrong sign or is out of range.
        """
        if expected_sign == "positive" and value <= 0:
            raise ValueError(
                f"{name}={value} must be strictly positive (e.g., +0.75)."
            )
        if expected_sign == "negative" and value >= 0:
            raise ValueError(
                f"{name}={value} must be strictly negative (e.g., -0.75)."
            )
        if not (-1.0 <= value <= 1.0):
            raise ValueError(
                f"{name}={value} must be in the range [-1.0, +1.0]."
            )
        return value

    @staticmethod
    def _validate_quorum(minimum_quorum: int) -> int:
        """
        Validate the minimum quorum requirement.

        Parameters
        ----------
        minimum_quorum : int
            Minimum number of active agents.

        Returns
        -------
        int
            The validated quorum value.

        Raises
        ------
        ValueError
            If quorum is not a positive integer or exceeds 4.
        """
        if not isinstance(minimum_quorum, int) or minimum_quorum < 1:
            raise ValueError(
                f"minimum_quorum must be a positive integer; "
                f"received {minimum_quorum!r}."
            )
        if minimum_quorum > 4:
            raise ValueError(
                f"minimum_quorum={minimum_quorum} cannot exceed the total "
                f"number of registered agents (4)."
            )
        return minimum_quorum

    def __repr__(self) -> str:
        weight_str = ", ".join(
            f"{k}={v:.0%}" for k, v in self._weights.items()
        )
        return (
            f"ConsensusEngine("
            f"weights=[{weight_str}], "
            f"buy_threshold={self._buy_threshold:+.2f}, "
            f"sell_threshold={self._sell_threshold:+.2f})"
        )
