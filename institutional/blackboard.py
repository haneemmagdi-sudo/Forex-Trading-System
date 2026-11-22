"""
==============================================================================
agents/blackboard.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Centralized Shared Memory Layer (Blackboard Architecture)
Author : Principal AI Systems Architect
Version: 4.2.0

Overview
--------
Implements the ``QuantumBlackboard`` — a thread-safe, centralized shared
memory pool that aggregates live prediction signals from all four independent
sub-model agents:

    ┌──────────────────────────────────────────────────────────┐
    │  Random Forest  ──┐                                      │
    │  Sentiment NLP  ──┤──► QuantumBlackboard ──► Consensus  │
    │  Google TimesFM ──┤       (this module)      Engine      │
    │  Deep Q-Network ──┘                                      │
    └──────────────────────────────────────────────────────────┘

Design Principles
-----------------
- Every write to the Blackboard is protected by a ``threading.RLock``
  (re-entrant to support nested acquisition from the same thread).
- Each agent's signal is stored under its ``agent_id`` key.  Posting a
  new signal from the same agent always overwrites the previous entry,
  guaranteeing that only the freshest prediction per agent is visible.
- A background-compatible ``invalidate_stale_signals`` method purges
  signals that exceed the configured staleness window, preventing the
  Consensus Engine from acting on outdated market views.

References
----------
- Engelmore & Morgan, "Blackboard Systems", Addison-Wesley, 1988.
- Agentic AI Frameworks, Chapters 17 & 24 (Blackboard & Multi-Agent
  Coordination Patterns).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.blackboard")


# ===========================================================================
# Enumerations (using str-based enum for JSON serialisation compatibility)
# ===========================================================================

from enum import Enum


class SignalDirection(str, Enum):
    """
    Canonical directional market signal emitted by each sub-model agent.

    Values
    ------
    BUY  : Agent believes price will rise; enter long positions.
    SELL : Agent believes price will fall; enter short positions.
    HOLD : Agent is uncertain or risk/reward is insufficient to act.
    """
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStatus(str, Enum):
    """
    Lifecycle state of a signal resident on the Blackboard.

    Values
    ------
    ACTIVE : Signal is fresh and eligible for consensus evaluation.
    STALE  : Signal has exceeded the maximum age threshold and has been
             invalidated.  It remains on the board for audit purposes but
             is excluded from consensus computation.
    """
    ACTIVE = "ACTIVE"
    STALE  = "STALE"


# ===========================================================================
# Pydantic v2 Signal Schema
# ===========================================================================

class SignalPayload(BaseModel):
    """
    Immutable data schema for a single agent prediction posted to the
    Quantum Blackboard.

    The Pydantic v2 model enforces strict type constraints at construction
    time, making it impossible for agents to post malformed signals.

    Attributes
    ----------
    agent_id : str
        Unique identifier for the originating agent.  Must be a non-empty
        string.  Expected values: ``"timesfm"``, ``"dqn"``,
        ``"random_forest"``, ``"sentiment"``.
    signal_direction : SignalDirection
        The directional market view: BUY, SELL, or HOLD.
    confidence_score : float
        A value in [0.0, 1.0] representing the agent's internal certainty.
        A score of 1.0 means maximum conviction; 0.0 means pure noise.
    timestamp : float
        UNIX epoch seconds at which the signal was produced.  Defaults to
        ``time.time()`` at model construction when not supplied explicitly.
    status : SignalStatus
        Lifecycle state; always ``ACTIVE`` when first posted.

    Examples
    --------
    >>> payload = SignalPayload(
    ...     agent_id="timesfm",
    ...     signal_direction=SignalDirection.BUY,
    ...     confidence_score=0.87,
    ... )
    """

    model_config = {"frozen": True}  # Enforces immutability after construction

    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the originating sub-model agent.",
    )
    signal_direction: SignalDirection = Field(
        ...,
        description="Directional market mandate: BUY, SELL, or HOLD.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent confidence level in [0.0, 1.0].",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="UNIX epoch seconds when the signal was produced.",
    )
    status: SignalStatus = Field(
        default=SignalStatus.ACTIVE,
        description="Lifecycle status of the signal on the Blackboard.",
    )

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, v: str) -> str:
        """Strip surrounding whitespace and enforce non-emptiness."""
        v = v.strip()
        if not v:
            raise ValueError(
                "agent_id must be a non-empty string after stripping whitespace."
            )
        return v

    @field_validator("confidence_score")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        """Clamp floating-point edge cases caused by upstream model rounding."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"confidence_score must be in [0.0, 1.0]; received {v}."
            )
        return round(v, 6)

    @model_validator(mode="after")
    def _validate_timestamp(self) -> "SignalPayload":
        """Guard against far-future or clearly invalid timestamps."""
        now = time.time()
        if self.timestamp > now + 60.0:
            raise ValueError(
                f"timestamp ({self.timestamp:.2f}) is more than 60 seconds in "
                f"the future relative to system clock ({now:.2f}).  "
                "Check agent clock synchronization."
            )
        return self

    # ------------------------------------------------------------------
    # Helper methods (non-mutating — safe on frozen model)
    # ------------------------------------------------------------------

    def age_seconds(self) -> float:
        """Return how many seconds have elapsed since this signal was produced."""
        return time.time() - self.timestamp

    def is_stale(self, max_age_seconds: int) -> bool:
        """Return True if this signal has exceeded its freshness window."""
        return self.age_seconds() > max_age_seconds

    def numerical_direction(self) -> float:
        """
        Map the signal direction to a signed float for arithmetic operations.

        Returns
        -------
        float
            +1.0 for BUY, -1.0 for SELL, 0.0 for HOLD.
        """
        mapping: Dict[SignalDirection, float] = {
            SignalDirection.BUY:  +1.0,
            SignalDirection.SELL: -1.0,
            SignalDirection.HOLD:  0.0,
        }
        return mapping[self.signal_direction]

    def __repr__(self) -> str:
        return (
            f"SignalPayload(agent_id={self.agent_id!r}, "
            f"direction={self.signal_direction.value}, "
            f"confidence={self.confidence_score:.4f}, "
            f"age={self.age_seconds():.1f}s, "
            f"status={self.status.value})"
        )


# ===========================================================================
# QuantumBlackboard — Centralized Shared Memory Layer
# ===========================================================================

class QuantumBlackboard:
    """
    Thread-safe centralized shared memory pool (Blackboard) for the
    Quantum FSM Pro V4.2 Elite multi-agent trading system.

    The Blackboard stores one active ``SignalPayload`` per registered agent.
    All concurrent read and write operations are serialized through a
    ``threading.RLock`` to guarantee consistent state visibility across
    all model threads.

    Internal Storage Structure
    --------------------------
    ::

        _signals: Dict[str, SignalPayload]
        {
            "timesfm":      SignalPayload(direction=SELL, confidence=0.91),
            "dqn":          SignalPayload(direction=HOLD, confidence=0.60),
            "random_forest":SignalPayload(direction=BUY,  confidence=0.74),
            "sentiment":    SignalPayload(direction=SELL, confidence=0.55),
        }

    Thread Safety
    -------------
    ``threading.RLock`` (re-entrant lock) is used rather than a plain Lock
    to allow the same thread to call multiple Blackboard methods within a
    single acquired lock context without deadlocking.

    Parameters
    ----------
    name : str
        Optional human-readable label for this Blackboard instance.
        Useful when running multiple symbols in parallel.

    Examples
    --------
    >>> bb = QuantumBlackboard(name="EURUSD_H1")
    >>> payload = SignalPayload(
    ...     agent_id="timesfm",
    ...     signal_direction=SignalDirection.BUY,
    ...     confidence_score=0.89,
    ... )
    >>> bb.post_signal(payload)
    >>> signals = bb.get_all_active_signals()
    >>> len(signals)
    1
    """

    # Canonical set of registered agent identifiers.
    # Signals from unrecognized IDs are accepted but logged as warnings.
    REGISTERED_AGENTS: frozenset = frozenset({
        "timesfm",
        "dqn",
        "random_forest",
        "sentiment",
    })

    def __init__(self, name: str = "QuantumBlackboard") -> None:
        """
        Initialize an empty Blackboard with a re-entrant lock.

        Parameters
        ----------
        name : str
            Human-readable label for this Blackboard instance.
        """
        self.name: str = name
        self._lock: threading.RLock = threading.RLock()
        self._signals: Dict[str, SignalPayload] = {}
        self._reliability_history: Dict[str, dict] = {}
        self._episodic_insights: Dict[str, dict] = {}
        self._post_count: int = 0           # Total writes ever (diagnostics)
        self._invalidation_count: int = 0   # Total signals marked stale

        logger.info(
            "[%s] QuantumBlackboard initialized | Registered agents: %s",
            self.name,
            sorted(self.REGISTERED_AGENTS),
        )

    # -------------------------------------------------------------------
    # Write Interface
    # -------------------------------------------------------------------

    def post_signal(self, payload: SignalPayload) -> None:
        """
        Ingest a new prediction signal from a sub-model agent.

        This method is the **sole write entry point** into the Blackboard.
        It overwrites any previous signal from the same ``agent_id``,
        ensuring the latest prediction always takes precedence for the
        current bar session.

        The re-entrant lock is acquired for the minimum duration required
        to perform the dictionary update, then released immediately.

        Parameters
        ----------
        payload : SignalPayload
            A validated, immutable signal produced by a sub-model agent.

        Raises
        ------
        TypeError
            If ``payload`` is not an instance of ``SignalPayload``.

        Notes
        -----
        If the ``agent_id`` is not in ``REGISTERED_AGENTS``, a WARNING is
        emitted but the signal is still accepted to tolerate future agent
        additions without requiring Blackboard code changes.

        Examples
        --------
        >>> bb.post_signal(SignalPayload(
        ...     agent_id="dqn",
        ...     signal_direction=SignalDirection.SELL,
        ...     confidence_score=0.77,
        ... ))
        """
        if not isinstance(payload, SignalPayload):
            raise TypeError(
                f"post_signal() expects a SignalPayload instance; "
                f"received {type(payload).__name__}."
            )

        if payload.agent_id not in self.REGISTERED_AGENTS:
            logger.warning(
                "[%s] Signal from unregistered agent_id=%r.  "
                "Accepting signal — verify agent configuration.",
                self.name,
                payload.agent_id,
            )

        with self._lock:
            previous: Optional[SignalPayload] = self._signals.get(payload.agent_id)
            self._signals[payload.agent_id] = payload
            self._post_count += 1

            if previous is not None:
                logger.debug(
                    "[%s] OVERWRITE agent=%r | prev=%s(%.4f) → new=%s(%.4f) "
                    "| delta_t=%.2fs",
                    self.name,
                    payload.agent_id,
                    previous.signal_direction.value,
                    previous.confidence_score,
                    payload.signal_direction.value,
                    payload.confidence_score,
                    time.time() - previous.timestamp,
                )
            else:
                logger.debug(
                    "[%s] NEW SIGNAL agent=%r | dir=%s conf=%.4f",
                    self.name,
                    payload.agent_id,
                    payload.signal_direction.value,
                    payload.confidence_score,
                )

        logger.info(
            "[%s] ✅ Signal posted | agent=%r | %s @ conf=%.4f | "
            "board=%d/4 active",
            self.name,
            payload.agent_id,
            payload.signal_direction.value,
            payload.confidence_score,
            len(self.get_all_active_signals()),
        )

    # -------------------------------------------------------------------
    # Read Interface
    # -------------------------------------------------------------------

    def get_all_active_signals(self) -> Dict[str, SignalPayload]:
        """
        Return a snapshot of all currently registered ACTIVE signals.

        Only signals with ``status == SignalStatus.ACTIVE`` are included.
        Stale signals (marked by ``invalidate_stale_signals``) are
        silently excluded from the returned dictionary.

        The returned dictionary is a **shallow copy** — modifying it does
        not affect the Blackboard's internal state.

        Returns
        -------
        Dict[str, SignalPayload]
            Mapping of ``agent_id → SignalPayload`` for all agents that
            have posted an active (non-stale) signal in the current bar
            session.

        Examples
        --------
        >>> signals = bb.get_all_active_signals()
        >>> for agent_id, payload in signals.items():
        ...     print(agent_id, payload.signal_direction, payload.confidence_score)
        timesfm SELL 0.91
        dqn     HOLD 0.60
        """
        with self._lock:
            return {
                agent_id: payload
                for agent_id, payload in self._signals.items()
                if payload.status == SignalStatus.ACTIVE
            }

    def get_signal(self, agent_id: str) -> Optional[SignalPayload]:
        """
        Return the most recent signal for a specific agent, or None.

        Parameters
        ----------
        agent_id : str
            The agent whose latest signal is requested.

        Returns
        -------
        SignalPayload or None
            The most recent signal from the specified agent, regardless of
            staleness status.  Returns None if no signal has been posted.
        """
        with self._lock:
            return self._signals.get(agent_id)

    def get_signal_count(self) -> Dict[str, int]:
        """
        Return diagnostic counters for Blackboard health monitoring.

        Returns
        -------
        dict
            Keys:
            - ``"active"``: Number of currently ACTIVE signals.
            - ``"stale"``: Number of currently STALE (invalidated) signals.
            - ``"total_registered"``: Total agents with any signal on board.
            - ``"total_posts_ever"``: Cumulative post count since init.
            - ``"total_invalidations_ever"``: Cumulative invalidation count.
        """
        with self._lock:
            active_count = sum(
                1 for p in self._signals.values()
                if p.status == SignalStatus.ACTIVE
            )
            stale_count = len(self._signals) - active_count
            return {
                "active": active_count,
                "stale": stale_count,
                "total_registered": len(self._signals),
                "total_posts_ever": self._post_count,
                "total_invalidations_ever": self._invalidation_count,
            }

    # -------------------------------------------------------------------
    # Inter-Agent Shared Memory & Reliability Pool
    # -------------------------------------------------------------------

    def record_agent_feedback(self, agent_id: str, success: bool, pnl: float = 0.0) -> None:
        """
        Record real-time execution feedback for a sub-model agent.
        Used by the Consensus Engine to dynamically adjust agent reliability weights.
        """
        with self._lock:
            stats = self._reliability_history.setdefault(agent_id, {
                "evaluations": 0, "successes": 0, "failures": 0, "net_pnl": 0.0, "win_rate": 0.5
            })
            stats["evaluations"] += 1
            if success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1
            stats["net_pnl"] += pnl
            stats["win_rate"] = round(stats["successes"] / stats["evaluations"], 4)

    def get_agent_reliability_matrix(self) -> Dict[str, dict]:
        """Return the snapshot of the cross-agent reliability tracking matrix."""
        with self._lock:
            return dict(self._reliability_history)

    def post_episodic_insight(self, key: str, insight: dict) -> None:
        """Post a shared episodic insight or regime discovery to the collective pool."""
        with self._lock:
            self._episodic_insights[key] = {
                "payload": insight,
                "timestamp": time.time(),
            }

    def get_episodic_insight(self, key: str) -> Optional[dict]:
        """Retrieve a shared episodic insight by key."""
        with self._lock:
            entry = self._episodic_insights.get(key)
            return entry["payload"] if entry else None

    # -------------------------------------------------------------------
    # Staleness Management
    # -------------------------------------------------------------------

    def invalidate_stale_signals(self, max_age_seconds: int = 300) -> int:
        """
        Scan the Blackboard and mark outdated signals as STALE.

        Designed to be called periodically by a background maintenance
        thread (e.g., via ``threading.Timer``) or at the start of each
        new bar session.  Stale signals remain on the Blackboard for
        audit logging but are excluded from ``get_all_active_signals()``
        and therefore from all consensus calculations.

        Because ``SignalPayload`` is a frozen Pydantic model, staleness is
        enforced by replacing the stored entry with a new ``SignalPayload``
        instance that carries ``status=STALE``.

        Parameters
        ----------
        max_age_seconds : int
            Maximum allowed signal age in seconds before it is marked STALE.
            Default: 300 s (5 minutes — one M5 bar).

        Returns
        -------
        int
            Number of signals newly invalidated in this call.

        Raises
        ------
        ValueError
            If ``max_age_seconds`` is not a positive integer.

        Examples
        --------
        >>> # Periodic maintenance — called every 60 seconds
        >>> n = bb.invalidate_stale_signals(max_age_seconds=60)
        >>> print(f"{n} stale signals purged.")
        2 stale signals purged.
        """
        if not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
            raise ValueError(
                f"max_age_seconds must be a positive integer; "
                f"received {max_age_seconds!r}."
            )

        invalidated_count: int = 0
        now: float = time.time()
        cutoff_ts: float = now - max_age_seconds

        with self._lock:
            # Collect agents whose signals have expired
            agents_to_invalidate: List[str] = [
                agent_id
                for agent_id, payload in self._signals.items()
                if payload.status == SignalStatus.ACTIVE
                and payload.timestamp < cutoff_ts
            ]

            for agent_id in agents_to_invalidate:
                old_payload: SignalPayload = self._signals[agent_id]
                # model_copy() is the Pydantic v2 way to clone + override fields
                stale_payload: SignalPayload = old_payload.model_copy(
                    update={"status": SignalStatus.STALE}
                )
                self._signals[agent_id] = stale_payload
                invalidated_count += 1
                self._invalidation_count += 1

                logger.warning(
                    "[%s] ⚠️ STALE: agent=%r | dir=%s | conf=%.4f | "
                    "age=%.1fs > max=%ds",
                    self.name,
                    agent_id,
                    old_payload.signal_direction.value,
                    old_payload.confidence_score,
                    now - old_payload.timestamp,
                    max_age_seconds,
                )

        if invalidated_count > 0:
            logger.info(
                "[%s] Staleness sweep: %d/%d signals invalidated "
                "(threshold=%ds).  Remaining active: %d.",
                self.name,
                invalidated_count,
                len(self._signals),
                max_age_seconds,
                len(self.get_all_active_signals()),
            )
        else:
            logger.debug(
                "[%s] Staleness sweep: all %d signals are fresh "
                "(threshold=%ds).",
                self.name,
                len(self._signals),
                max_age_seconds,
            )

        return invalidated_count

    def clear_session(self) -> None:
        """
        Completely wipe all signals from the Blackboard.

        Intended to be called at the start of each new bar session to
        ensure the Consensus Engine operates only on fresh data.
        Cumulative diagnostic counters (``_post_count``,
        ``_invalidation_count``) are preserved for audit purposes.

        Examples
        --------
        >>> bb.clear_session()  # Called at bar-close before new bar opens
        """
        with self._lock:
            cleared = len(self._signals)
            self._signals.clear()

        logger.info(
            "[%s] 🔄 Session cleared — %d signal(s) removed.  "
            "Blackboard is ready for new bar session.",
            self.name,
            cleared,
        )

    # -------------------------------------------------------------------
    # Quorum & Diagnostic Utilities
    # -------------------------------------------------------------------

    def is_quorum_reached(self) -> bool:
        """
        Return True if all four registered agents have posted an ACTIVE signal.

        The Consensus Engine should only be evaluated once a full quorum
        is available to prevent partial-information decisions.

        Returns
        -------
        bool
            True iff all agents in ``REGISTERED_AGENTS`` have an ACTIVE
            signal on the Blackboard.

        Examples
        --------
        >>> if bb.is_quorum_reached():
        ...     mandate = engine.evaluate(bb)
        """
        with self._lock:
            active_agents = {
                agent_id
                for agent_id, payload in self._signals.items()
                if payload.status == SignalStatus.ACTIVE
            }
        return self.REGISTERED_AGENTS.issubset(active_agents)

    def missing_agents(self) -> List[str]:
        """
        Return the list of registered agents that have not yet posted a
        fresh ACTIVE signal in the current bar session.

        Returns
        -------
        list[str]
            Sorted list of agent identifiers whose signals are absent or
            have been marked STALE.

        Examples
        --------
        >>> bb.missing_agents()
        ['dqn', 'timesfm']
        """
        with self._lock:
            posted = {
                agent_id
                for agent_id, payload in self._signals.items()
                if payload.status == SignalStatus.ACTIVE
            }
        return sorted(self.REGISTERED_AGENTS - posted)

    def snapshot(self) -> Dict[str, dict]:
        """
        Return a fully serializable dictionary snapshot of the Blackboard
        state, suitable for logging, debugging, or REST API responses.

        Returns
        -------
        Dict[str, dict]
            Nested dictionary mapping each ``agent_id`` to a plain dict
            representation of its ``SignalPayload``.

        Examples
        --------
        >>> import json
        >>> print(json.dumps(bb.snapshot(), indent=2))
        {
          "timesfm": {
            "agent_id": "timesfm",
            "signal_direction": "SELL",
            ...
          }
        }
        """
        with self._lock:
            return {
                agent_id: payload.model_dump()
                for agent_id, payload in self._signals.items()
            }

    def __repr__(self) -> str:
        counts = self.get_signal_count()
        return (
            f"QuantumBlackboard(name={self.name!r}, "
            f"active={counts['active']}, "
            f"stale={counts['stale']}, "
            f"quorum={self.is_quorum_reached()})"
        )
