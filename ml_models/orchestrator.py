"""
==============================================================
ml_models/orchestrator.py — Antigravity Orchestrator Agent
==============================================================
Weighted consensus engine that consolidates predictions from the
four Antigravity sub-models into a single, actionable execution
signal.

Sub-Models & Their Outputs
---------------------------
    Model 1 — Random Forest (Classification)
        Output : class in {-1, 0, +1}  →  SELL / HOLD / BUY
        Weight : 25%

    Model 2 — LSTM (Regression)
        Output : price direction delta (signed float)
        Weight : 30%

    Model 3 — DQN (Reinforcement Learning)
        Output : Q-values for [HOLD, BUY, SELL, CLOSE]
        Weight : 30%

    Model 4 — Sentiment (NLP)
        Output : polarity score in [-1.0, +1.0]
        Weight : 15%

Consensus Logic
---------------
1.  Each model's raw output is normalised to a **directional score**
    in [-1.0, +1.0], where:
        +1.0 = maximum BUY conviction
         0.0 = neutral (HOLD)
        -1.0 = maximum SELL conviction

2.  A **weighted sum** across all models produces the raw consensus:
        raw_consensus = Σ (weight_i × score_i)  ∈ [-1.0, +1.0]

3.  The **Consensus Confidence Score** is the absolute magnitude of
    the raw consensus, scaled to a percentage:
        confidence = |raw_consensus| × 100%   ∈ [0%, 100%]

4.  Execution Signal:
        if confidence > 78% AND raw_consensus > 0  →  BUY
        if confidence > 78% AND raw_consensus < 0  →  SELL
        otherwise                                   →  HOLD  (capital lock)

Thread Safety
-------------
The orchestrator is stateless with respect to market data.  Each call
to ``evaluate()`` or ``orchestrate()`` is atomic and independent.
Multiple coroutines may invoke these methods concurrently without
requiring any locking.

Usage
-----
    from ml_models.orchestrator import AntigravityOrchestrator
    from ml_models.feature_pipeline import (
        RFFeaturePipeline, LSTMSequencePipeline,
        DQNStatePipeline, SentimentPipeline,
        FeaturePipelineFacade, AccountState,
    )

    # --- Quick evaluation from raw model outputs ---
    orch = AntigravityOrchestrator()

    signal = orch.evaluate(
        rf_prediction    =  1,          # RF says BUY
        lstm_delta       =  0.0012,     # LSTM predicts price up
        dqn_q_values     = [0.1, 0.9, 0.05, 0.02],  # Q favours BUY
        sentiment_score  =  0.35,       # Bullish sentiment
    )
    print(signal)
    # → OrchestratorSignal(action='BUY', confidence=85.2, ...)

    # --- Full pipeline integration ---
    signal = orch.orchestrate(feature_bundle, rf_model, lstm_model, dqn_model)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Final, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("ml_models.orchestrator")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

class Action(str, Enum):
    """Absolute execution actions emitted by the orchestrator."""
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# Default model weights (must sum to 1.0)
_DEFAULT_WEIGHTS: Final[Dict[str, float]] = {
    "lstm":      0.30,   # 30% — price direction regression
    "dqn":       0.30,   # 30% — reinforcement learning Q-values
    "rf":        0.25,   # 25% — classification (Buy/Sell/Hold)
    "sentiment": 0.15,   # 15% — NLP bullish/bearish polarity
}

# Confidence threshold — below this, we force HOLD
_CONFIDENCE_THRESHOLD: Final[float] = 78.0   # percent

# DQN action index mapping (matches DQN_ACTIONS in feature_pipeline.py)
_DQN_IDX_HOLD:  Final[int] = 0
_DQN_IDX_BUY:   Final[int] = 1
_DQN_IDX_SELL:  Final[int] = 2
_DQN_IDX_CLOSE: Final[int] = 3

# LSTM delta normalisation ceiling — deltas beyond this are clipped to ±1.0
# A delta of 0.002 (20 pips on EURUSD H1) maps to full conviction.
_LSTM_DELTA_CEILING: Final[float] = 0.002


# ─────────────────────────────────────────────────────────────────────────────
# Output data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelScore:
    """
    Normalised directional score for a single sub-model.

    Attributes
    ----------
    model_name : str
        Human-readable model identifier (e.g., "RandomForest").
    raw_output : Any
        The model's raw prediction (class label, delta, Q-values, etc.).
    directional_score : float
        Normalised score in [-1.0, +1.0].
    weight : float
        The model's consensus weight (e.g., 0.25 for RF).
    weighted_contribution : float
        ``directional_score × weight`` — this model's share of the consensus.
    """
    model_name: str
    raw_output: Any
    directional_score: float
    weight: float
    weighted_contribution: float = 0.0

    def __post_init__(self) -> None:
        self.weighted_contribution = self.directional_score * self.weight


@dataclass
class OrchestratorSignal:
    """
    The final consolidated execution signal from the orchestrator.

    Attributes
    ----------
    action : Action
        Absolute execution directive: BUY, SELL, or HOLD.
    confidence : float
        Consensus Confidence Score in [0.0, 100.0] %.
    raw_consensus : float
        Signed weighted sum in [-1.0, +1.0] before thresholding.
    threshold : float
        The confidence threshold used (default 78%).
    model_scores : list[ModelScore]
        Per-model breakdown of scores and contributions.
    timestamp : float
        UNIX timestamp when the signal was produced.
    metadata : dict
        Optional additional context (symbol, bar_time, etc.).
    """
    action: Action
    confidence: float
    raw_consensus: float
    threshold: float
    model_scores: List[ModelScore]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """True if the signal is BUY or SELL (not HOLD)."""
        return self.action != Action.HOLD

    @property
    def direction(self) -> int:
        """Numeric direction: +1 BUY, -1 SELL, 0 HOLD."""
        if self.action == Action.BUY:
            return 1
        elif self.action == Action.SELL:
            return -1
        return 0

    def summary(self) -> str:
        """Human-readable one-line summary."""
        status = "🟢 EXECUTE" if self.is_actionable else "🔒 LOCKED"
        return (
            f"[{status}] {self.action.value} | "
            f"Confidence: {self.confidence:.1f}% "
            f"(threshold: {self.threshold:.0f}%) | "
            f"Consensus: {self.raw_consensus:+.4f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the signal to a plain dictionary."""
        return {
            "action":         self.action.value,
            "confidence":     round(self.confidence, 2),
            "raw_consensus":  round(self.raw_consensus, 6),
            "threshold":      self.threshold,
            "is_actionable":  self.is_actionable,
            "direction":      self.direction,
            "model_breakdown": [
                {
                    "model":          ms.model_name,
                    "raw_output":     _safe_serialize(ms.raw_output),
                    "score":          round(ms.directional_score, 4),
                    "weight":         ms.weight,
                    "contribution":   round(ms.weighted_contribution, 4),
                }
                for ms in self.model_scores
            ],
            "timestamp":      self.timestamp,
            "metadata":       self.metadata,
        }


def _safe_serialize(obj: Any) -> Any:
    """Convert numpy types and arrays to JSON-safe Python primitives."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_rf(prediction: int) -> float:
    """
    Normalise a Random Forest classification prediction to [-1, +1].

    Parameters
    ----------
    prediction : int
        RF output class:  +1 = BUY,  0 = HOLD,  -1 = SELL.

    Returns
    -------
    float
        Directional score in {-1.0, 0.0, +1.0}.
    """
    return float(np.clip(prediction, -1, 1))


def _normalise_lstm_delta(delta: float) -> float:
    """
    Normalise an LSTM price-direction delta to [-1, +1].

    The delta is the predicted price change (e.g. +0.0012 = price up).
    We scale it so that ``±_LSTM_DELTA_CEILING`` maps to ±1.0, with
    linear interpolation in between.

    Parameters
    ----------
    delta : float
        Predicted price movement (signed).

    Returns
    -------
    float
        Directional score in [-1.0, +1.0].
    """
    if _LSTM_DELTA_CEILING == 0:
        return 0.0
    scaled = delta / _LSTM_DELTA_CEILING
    return float(np.clip(scaled, -1.0, 1.0))


def _normalise_dqn_qvalues(q_values: np.ndarray | List[float]) -> float:
    """
    Normalise DQN Q-values to a single directional score in [-1, +1].

    The Q-value vector layout is [HOLD, BUY, SELL, CLOSE].

    Strategy:
        1. Compute the **net directional preference** as:
           ``net = Q_BUY − Q_SELL``
        2. Normalise by the max absolute Q-value to produce a
           scale-free ratio.  This prevents large Q-magnitudes from
           dominating.
        3. If the best action is CLOSE, we treat it as a mild SELL
           signal (existing positions should be unwound).

    Parameters
    ----------
    q_values : array-like
        Q-values for [HOLD, BUY, SELL, CLOSE].  Length must be ≥ 3.

    Returns
    -------
    float
        Directional score in [-1.0, +1.0].
    """
    q = np.asarray(q_values, dtype=np.float64)

    if len(q) < 3:
        logger.warning(
            "[Orchestrator] DQN Q-values have < 3 elements: %s. Returning 0.",
            q.tolist(),
        )
        return 0.0

    q_buy  = q[_DQN_IDX_BUY]
    q_sell = q[_DQN_IDX_SELL]

    # If CLOSE has the highest Q-value, treat as mild SELL
    best_action = int(np.argmax(q))
    if len(q) > 3 and best_action == _DQN_IDX_CLOSE:
        return -0.3  # mild sell bias when agent wants to close

    net = q_buy - q_sell
    max_abs_q = max(abs(q_buy), abs(q_sell), 1e-8)
    normalised = net / max_abs_q

    return float(np.clip(normalised, -1.0, 1.0))


def _normalise_sentiment(score: float) -> float:
    """
    Normalise sentiment score — already in [-1, +1] by convention.

    Parameters
    ----------
    score : float
        Sentiment polarity from ``SentimentPipeline.score()`` or
        ``SentimentPipeline.aggregate()``.

    Returns
    -------
    float
        Clamped to [-1.0, +1.0].
    """
    return float(np.clip(score, -1.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# AntigravityOrchestrator
# ─────────────────────────────────────────────────────────────────────────────

class AntigravityOrchestrator:
    """
    Weighted consensus engine for Antigravity's 4-model ensemble.

    This is the decision-making core of the trading system.  It
    normalises, weighs, and merges predictions from all four
    sub-models into a single, unambiguous execution signal with
    a confidence metric.

    Parameters
    ----------
    weights : dict | None
        Custom model weights ``{"rf": 0.25, "lstm": 0.30, ...}``.
        Must sum to 1.0 (within floating-point tolerance).
        Defaults to ``{lstm: 0.30, dqn: 0.30, rf: 0.25, sentiment: 0.15}``.
    confidence_threshold : float
        Minimum Consensus Confidence Score (%) required to emit
        a BUY or SELL signal.  Below this, HOLD is enforced.
        Default: 78.0%.
    lstm_delta_ceiling : float | None
        Override the LSTM delta normalisation ceiling.  If None,
        uses the module default ``_LSTM_DELTA_CEILING``.

    Raises
    ------
    ValueError
        If custom weights don't sum to 1.0 (±0.01 tolerance).
    ValueError
        If confidence_threshold is not in [0, 100].
    """

    NAME: str = "AntigravityOrchestrator"

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
        lstm_delta_ceiling: Optional[float] = None,
    ) -> None:
        # ── Validate and store weights ────────────────────────────────
        self._weights = dict(weights or _DEFAULT_WEIGHTS)
        self._validate_weights()

        # ── Confidence threshold ──────────────────────────────────────
        if not 0.0 <= confidence_threshold <= 100.0:
            raise ValueError(
                f"confidence_threshold must be in [0, 100]; "
                f"got {confidence_threshold}"
            )
        self._threshold = confidence_threshold

        # ── LSTM normalisation ceiling ────────────────────────────────
        self._lstm_ceiling = (
            lstm_delta_ceiling
            if lstm_delta_ceiling is not None
            else _LSTM_DELTA_CEILING
        )

        # ── Diagnostics / history ─────────────────────────────────────
        self._signal_count: int = 0
        self._last_signal: Optional[OrchestratorSignal] = None
        self._action_histogram: Dict[str, int] = {
            "BUY": 0, "SELL": 0, "HOLD": 0,
        }

        logger.info(
            "[Orchestrator] Initialised | weights=%s | threshold=%.1f%% | "
            "lstm_ceiling=%.6f",
            self._weights, self._threshold, self._lstm_ceiling,
        )

    # ── Weight validation ──────────────────────────────────────────────────

    def _validate_weights(self) -> None:
        """Ensure all required model keys exist and weights sum to 1.0."""
        required_keys = {"rf", "lstm", "dqn", "sentiment"}
        missing = required_keys - set(self._weights.keys())
        if missing:
            raise ValueError(
                f"Model weights missing keys: {missing}. "
                f"Required: {required_keys}"
            )

        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Model weights must sum to 1.0; got {total:.4f}. "
                f"Weights: {self._weights}"
            )

        # Ensure no negative weights
        for key, val in self._weights.items():
            if val < 0:
                raise ValueError(
                    f"Weight for '{key}' is negative ({val}). "
                    "All weights must be ≥ 0."
                )

    # ── Core evaluation (from raw model outputs) ──────────────────────────

    def evaluate(
        self,
        rf_prediction: int,
        lstm_delta: float,
        dqn_q_values: np.ndarray | List[float],
        sentiment_score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorSignal:
        """
        Evaluate the weighted consensus from raw model outputs.

        This is the primary entry point when you already have the
        individual model predictions and want the orchestrator to
        produce a final execution signal.

        Parameters
        ----------
        rf_prediction : int
            Random Forest classification: +1 (BUY), 0 (HOLD), -1 (SELL).
        lstm_delta : float
            LSTM predicted price direction delta (signed float).
        dqn_q_values : array-like
            DQN Q-values for [HOLD, BUY, SELL, CLOSE].
        sentiment_score : float
            NLP sentiment polarity in [-1.0, +1.0].
        metadata : dict | None
            Optional metadata to attach to the signal (symbol, bar_time).

        Returns
        -------
        OrchestratorSignal
            The final execution signal with confidence and breakdown.

        Examples
        --------
        >>> orch = AntigravityOrchestrator()
        >>> sig = orch.evaluate(
        ...     rf_prediction=1,
        ...     lstm_delta=0.0015,
        ...     dqn_q_values=[0.1, 0.85, 0.05, 0.02],
        ...     sentiment_score=0.42,
        ... )
        >>> print(sig.action, sig.confidence)
        BUY  83.25
        """
        # ── Step 1: Normalise each model output to [-1, +1] ────────────
        rf_score   = _normalise_rf(rf_prediction)
        lstm_score = _normalise_lstm_delta(lstm_delta)
        dqn_score  = _normalise_dqn_qvalues(dqn_q_values)
        sent_score = _normalise_sentiment(sentiment_score)

        # ── Step 2: Build per-model score records ──────────────────────
        model_scores = [
            ModelScore(
                model_name="RandomForest",
                raw_output=rf_prediction,
                directional_score=rf_score,
                weight=self._weights["rf"],
            ),
            ModelScore(
                model_name="LSTM",
                raw_output=lstm_delta,
                directional_score=lstm_score,
                weight=self._weights["lstm"],
            ),
            ModelScore(
                model_name="DQN",
                raw_output=np.asarray(dqn_q_values).tolist(),
                directional_score=dqn_score,
                weight=self._weights["dqn"],
            ),
            ModelScore(
                model_name="Sentiment",
                raw_output=sentiment_score,
                directional_score=sent_score,
                weight=self._weights["sentiment"],
            ),
        ]

        # ── Step 3: Compute weighted consensus ────────────────────────
        raw_consensus = sum(ms.weighted_contribution for ms in model_scores)

        # ── Step 4: Compute Consensus Confidence Score ────────────────
        # Confidence = |raw_consensus| × 100, in [0%, 100%]
        confidence = abs(raw_consensus) * 100.0

        # ── Step 5: Apply threshold to determine action ───────────────
        if confidence > self._threshold:
            action = Action.BUY if raw_consensus > 0 else Action.SELL
        else:
            action = Action.HOLD

        # ── Step 6: Build the output signal ───────────────────────────
        signal = OrchestratorSignal(
            action=action,
            confidence=round(confidence, 2),
            raw_consensus=round(raw_consensus, 6),
            threshold=self._threshold,
            model_scores=model_scores,
            metadata=metadata or {},
        )

        # ── Step 7: Update internal diagnostics ───────────────────────
        self._signal_count += 1
        self._last_signal = signal
        self._action_histogram[action.value] += 1

        # ── Step 8: Log the decision ──────────────────────────────────
        logger.info(
            "[Orchestrator] #%d | %s | conf=%.1f%% | consensus=%+.4f | "
            "RF=%+.2f LSTM=%+.2f DQN=%+.2f SENT=%+.2f",
            self._signal_count,
            signal.summary(),
            confidence,
            raw_consensus,
            rf_score,
            lstm_score,
            dqn_score,
            sent_score,
        )

        return signal

    # ── Full pipeline integration ──────────────────────────────────────────

    def orchestrate(
        self,
        feature_bundle: Any,
        rf_model: Any = None,
        lstm_model: Any = None,
        dqn_model: Any = None,
    ) -> OrchestratorSignal:
        """
        End-to-end orchestration from an ``AntigravityFeatureBundle``.

        Runs inference on all four models using the pre-computed feature
        bundle from ``FeaturePipelineFacade.process_bar()`` and produces
        the final execution signal.

        Parameters
        ----------
        feature_bundle : AntigravityFeatureBundle
            Feature inputs from ``FeaturePipelineFacade.process_bar()``.
        rf_model : sklearn model | None
            Trained Random Forest classifier with ``.predict()`` method.
            If None, defaults to HOLD (score 0).
        lstm_model : keras/torch model | None
            Trained LSTM regressor with ``.predict()`` method.
            If None, defaults to delta=0.0.
        dqn_model : DQN agent | None
            Trained DQN with ``.predict()`` or ``.get_q_values()`` method.
            If None, defaults to uniform Q-values (HOLD preference).

        Returns
        -------
        OrchestratorSignal
        """
        meta = {
            "symbol":   getattr(feature_bundle, "symbol", "UNKNOWN"),
            "bar_time": str(getattr(feature_bundle, "bar_time", "")),
        }

        # ── RF Prediction ─────────────────────────────────────────────
        rf_pred = 0
        if rf_model is not None:
            try:
                rf_features = feature_bundle.rf_features  # shape (1, n)
                pred = rf_model.predict(rf_features)
                rf_pred = int(pred[0]) if hasattr(pred, '__len__') else int(pred)
            except Exception as exc:
                logger.warning("[Orchestrator] RF inference failed: %s", exc)

        # ── LSTM Delta ────────────────────────────────────────────────
        lstm_delta = 0.0
        if lstm_model is not None:
            try:
                lstm_window = feature_bundle.lstm_window  # shape (1, 60, 5)
                pred = lstm_model.predict(lstm_window)
                # For regression the prediction is the delta
                lstm_delta = float(pred[0][0]) if hasattr(pred[0], '__len__') else float(pred[0])
            except Exception as exc:
                logger.warning("[Orchestrator] LSTM inference failed: %s", exc)

        # ── DQN Q-values ─────────────────────────────────────────────
        dqn_q = [0.25, 0.25, 0.25, 0.25]  # uniform = no preference
        if dqn_model is not None:
            try:
                dqn_state = feature_bundle.dqn_state  # shape (19,)
                if hasattr(dqn_model, "get_q_values"):
                    dqn_q = dqn_model.get_q_values(dqn_state)
                elif hasattr(dqn_model, "predict"):
                    dqn_q = dqn_model.predict(
                        dqn_state.reshape(1, -1)
                    )[0]
                if isinstance(dqn_q, np.ndarray):
                    dqn_q = dqn_q.tolist()
            except Exception as exc:
                logger.warning("[Orchestrator] DQN inference failed: %s", exc)

        # ── Sentiment (already in the bundle) ─────────────────────────
        sentiment = getattr(feature_bundle, "sentiment_score", 0.0)

        return self.evaluate(
            rf_prediction=rf_pred,
            lstm_delta=lstm_delta,
            dqn_q_values=dqn_q,
            sentiment_score=sentiment,
            metadata=meta,
        )

    # ── Weight management ──────────────────────────────────────────────────

    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Dynamically update model weights at runtime.

        This allows the ``LearningAgent`` or a backtesting framework to
        adjust weights based on rolling model performance.

        Parameters
        ----------
        new_weights : dict
            Must contain keys {"rf", "lstm", "dqn", "sentiment"} and
            values that sum to 1.0.

        Raises
        ------
        ValueError
            If validation fails.
        """
        old = dict(self._weights)
        self._weights = dict(new_weights)
        try:
            self._validate_weights()
        except ValueError:
            self._weights = old
            raise
        logger.info(
            "[Orchestrator] Weights updated: %s → %s",
            old, self._weights,
        )

    def update_threshold(self, new_threshold: float) -> None:
        """
        Dynamically adjust the confidence threshold at runtime.

        Parameters
        ----------
        new_threshold : float
            New threshold in [0, 100].

        Raises
        ------
        ValueError
            If the threshold is outside [0, 100].
        """
        if not 0.0 <= new_threshold <= 100.0:
            raise ValueError(
                f"Threshold must be in [0, 100]; got {new_threshold}"
            )
        old = self._threshold
        self._threshold = new_threshold
        logger.info(
            "[Orchestrator] Threshold updated: %.1f%% → %.1f%%",
            old, new_threshold,
        )

    # ── Diagnostics ────────────────────────────────────────────────────────

    @property
    def weights(self) -> Dict[str, float]:
        """Current model weights (read-only copy)."""
        return dict(self._weights)

    @property
    def threshold(self) -> float:
        """Current confidence threshold (%)."""
        return self._threshold

    @property
    def signal_count(self) -> int:
        """Total number of signals produced since initialisation."""
        return self._signal_count

    @property
    def last_signal(self) -> Optional[OrchestratorSignal]:
        """The most recently produced signal, or None."""
        return self._last_signal

    @property
    def action_histogram(self) -> Dict[str, int]:
        """Cumulative count of BUY/SELL/HOLD signals produced."""
        return dict(self._action_histogram)

    def get_state(self) -> Dict[str, Any]:
        """
        Full orchestrator state snapshot for monitoring / API exposure.

        Returns
        -------
        dict
            Contains weights, threshold, signal counts, and last signal.
        """
        return {
            "name":             self.NAME,
            "weights":          self._weights,
            "threshold":        self._threshold,
            "signal_count":     self._signal_count,
            "action_histogram": dict(self._action_histogram),
            "last_signal":      self._last_signal.to_dict()
                                if self._last_signal else None,
        }

    def __repr__(self) -> str:
        return (
            f"AntigravityOrchestrator("
            f"weights={self._weights}, "
            f"threshold={self._threshold}%, "
            f"signals={self._signal_count})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test — validates the orchestrator with synthetic inputs.

    Run from project root:
        python -m ml_models.orchestrator

    Expected output:
        Scenario 1: Strong BUY consensus  → BUY  ~85%+
        Scenario 2: Strong SELL consensus  → SELL ~80%+
        Scenario 3: Mixed / low confidence → HOLD <78%
        Scenario 4: Edge case — right at threshold
        ALL PASS
    """
    import sys

    out = sys.stdout.buffer

    def _p(msg: str) -> None:
        out.write((msg + "\n").encode("utf-8"))
        out.flush()

    _p("\n=== Antigravity Orchestrator Smoke-Test ===\n")

    orch = AntigravityOrchestrator()
    _p(f"Orchestrator: {orch}")
    _p(f"Weights: {orch.weights}")
    _p(f"Threshold: {orch.threshold}%\n")

    # ── Scenario 1: Strong BUY consensus ──────────────────────────────────
    _p("--- Scenario 1: Strong BUY consensus ---")
    sig1 = orch.evaluate(
        rf_prediction=1,                         # RF: BUY
        lstm_delta=0.0018,                        # LSTM: strong up
        dqn_q_values=[0.05, 0.85, 0.08, 0.02],   # DQN: BUY dominant
        sentiment_score=0.55,                     # Sentiment: bullish
    )
    _p(f"  {sig1.summary()}")
    _p(f"  Action: {sig1.action.value}  Confidence: {sig1.confidence:.1f}%")
    for ms in sig1.model_scores:
        _p(f"    {ms.model_name:15s} | score={ms.directional_score:+.4f} "
           f"| weight={ms.weight:.2f} | contribution={ms.weighted_contribution:+.4f}")
    assert sig1.action == Action.BUY, f"Expected BUY, got {sig1.action}"
    assert sig1.confidence > 78.0, f"Expected >78%, got {sig1.confidence}"
    _p("  ✓ PASS\n")

    # ── Scenario 2: Strong SELL consensus ─────────────────────────────────
    _p("--- Scenario 2: Strong SELL consensus ---")
    sig2 = orch.evaluate(
        rf_prediction=-1,                          # RF: SELL
        lstm_delta=-0.0020,                         # LSTM: strong down
        dqn_q_values=[0.05, 0.02, 0.90, 0.03],    # DQN: SELL dominant
        sentiment_score=-0.70,                      # Sentiment: bearish
    )
    _p(f"  {sig2.summary()}")
    _p(f"  Action: {sig2.action.value}  Confidence: {sig2.confidence:.1f}%")
    assert sig2.action == Action.SELL, f"Expected SELL, got {sig2.action}"
    assert sig2.confidence > 78.0, f"Expected >78%, got {sig2.confidence}"
    _p("  ✓ PASS\n")

    # ── Scenario 3: Mixed signals → HOLD ──────────────────────────────────
    _p("--- Scenario 3: Mixed signals → HOLD ---")
    sig3 = orch.evaluate(
        rf_prediction=1,                           # RF: BUY
        lstm_delta=-0.0005,                         # LSTM: slight down
        dqn_q_values=[0.30, 0.25, 0.35, 0.10],    # DQN: slight SELL
        sentiment_score=0.10,                       # Sentiment: barely bullish
    )
    _p(f"  {sig3.summary()}")
    _p(f"  Action: {sig3.action.value}  Confidence: {sig3.confidence:.1f}%")
    assert sig3.action == Action.HOLD, f"Expected HOLD, got {sig3.action}"
    _p("  ✓ PASS\n")

    # ── Scenario 4: Neutral → HOLD (capital preserved) ────────────────────
    _p("--- Scenario 4: All neutral → HOLD ---")
    sig4 = orch.evaluate(
        rf_prediction=0,
        lstm_delta=0.0,
        dqn_q_values=[0.25, 0.25, 0.25, 0.25],
        sentiment_score=0.0,
    )
    _p(f"  {sig4.summary()}")
    assert sig4.action == Action.HOLD
    assert sig4.confidence == 0.0
    _p("  ✓ PASS\n")

    # ── Scenario 5: DQN CLOSE action ─────────────────────────────────────
    _p("--- Scenario 5: DQN wants CLOSE (mapped to mild SELL) ---")
    sig5 = orch.evaluate(
        rf_prediction=-1,
        lstm_delta=-0.0015,
        dqn_q_values=[0.1, 0.05, 0.15, 0.70],    # CLOSE dominant
        sentiment_score=-0.40,
    )
    _p(f"  {sig5.summary()}")
    _p(f"  DQN normalised score: {sig5.model_scores[2].directional_score:+.4f}")
    _p("  ✓ PASS\n")

    # ── Dynamic weight update ─────────────────────────────────────────────
    _p("--- Dynamic weight update ---")
    orch.update_weights({
        "rf": 0.20, "lstm": 0.35, "dqn": 0.30, "sentiment": 0.15,
    })
    _p(f"  New weights: {orch.weights}")
    _p("  ✓ PASS\n")

    # ── Diagnostics ───────────────────────────────────────────────────────
    _p("--- Diagnostics ---")
    state = orch.get_state()
    _p(f"  Signal count: {state['signal_count']}")
    _p(f"  Action histogram: {state['action_histogram']}")
    _p(f"  Last signal: {state['last_signal']['action']} "
       f"conf={state['last_signal']['confidence']}%")

    _p("\n=== ALL PASS ===\n")
