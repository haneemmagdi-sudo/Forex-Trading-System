"""
==============================================================================
ml_models/rf_classifier.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Random Forest Ensemble Classifier
Author : Principal Quantitative Research Engineer
Version: 4.2.0

Overview
--------
Production-grade, Pydantic-validated Random Forest ensemble classifier that
consumes the 14-dimensional fused feature vector from ``QuantumFeaturePipeline``
and outputs a directional signal (BUY / SELL / HOLD) with a full probability
distribution array — formatted as a ``SignalPayload`` JSON ready for direct
posting to the ``QuantumBlackboard`` shared memory system.

Model Specification
-------------------
::

    RandomForestClassifier(
        n_estimators  = 500,    # 500 trees — reduces variance, improves stability
        max_depth     = 12,     # deep enough to capture non-linear market regimes
        min_samples_split = 5,  # prevents over-fitting on sparse training rows
        class_weight  = "balanced",  # corrects class imbalance (HOLD is rare)
        random_state  = 42,
        n_jobs        = -1,     # use all CPU cores for parallel training
        oob_score     = True,   # out-of-bag score as training health signal
    )

Target Formulation (Binary Direction)
--------------------------------------
The predictive target $y$ is defined as:

    $y_t = 1$ if ``Close[t+5] > Close[t]``   → BUY class
    $y_t = 0$ if ``Close[t+5] ≤ Close[t]``   → SELL class

A 5-bar forward return is used (not 1-bar) to:
    1. Filter out micro-noise and tick-level spread events.
    2. Align with the structural conviction of the TimesFM 10-bar horizon.
    3. Produce class-balanced targets that are stable over time.

HOLD class assignment:
    During inference, the RF emits ``predict_proba`` (probability of BUY=1).
    If the max probability < ``HOLD_THRESHOLD`` (default: 0.55), the classifier
    defers to HOLD — signalling to the Planner that conviction is below the
    edge threshold for execution.

Probability to Confidence Mapping
-----------------------------------
The classifier's ``predict_proba`` output is mapped to the Blackboard's
``confidence_score`` [0.0, 1.0] as follows:

    max_prob = max(P(BUY), P(SELL))   ∈ [0.5, 1.0] by construction
    confidence = 2 × (max_prob − 0.5)  → maps [0.5, 1.0] → [0.0, 1.0]

This ensures:
    - A coin-flip (50/50) maps to confidence = 0.0
    - Perfect certainty (100% one class) maps to confidence = 1.0

Blackboard Integration
-----------------------
``predict_live_direction`` returns a dict formatted for direct posting to the
``QuantumBlackboard`` via ``blackboard.post_signal(SignalPayload(**rf_output))``:

    {
      "agent_id":         "random_forest",
      "signal_direction": "BUY" | "SELL" | "HOLD",
      "confidence_score": float in [0.0, 1.0],
      "timestamp":        float (UNIX epoch),
      "metadata": {
        "proba_buy":       float,
        "proba_sell":      float,
        "raw_class":       int (0 or 1),
        "feature_vector":  list[float] (14 values),
        "oob_score":       float | null,
        "n_estimators":    500,
        "model_version":   str,
        "inference_ms":    float,
      }
    }

Usage
-----
    from ml_models.rf_classifier import QuantumRFClassifier
    from ml_models.feature_fusion import QuantumFeaturePipeline

    # Training
    rf = QuantumRFClassifier()
    pipeline = QuantumFeaturePipeline()
    X_df, _ = pipeline.build_training_matrix(hist_df)
    rf.fit(X_df, hist_df["close"])

    # Live inference → Blackboard payload
    live_X    = pipeline.transform_live_row(live_df, smc_params)
    bb_payload = rf.predict_live_direction(live_X)
    blackboard.post_signal(SignalPayload(**{k: bb_payload[k] for k in
                           ["agent_id", "signal_direction", "confidence_score"]}))
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    accuracy_score,
)

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from ml_models.feature_fusion import FEATURE_NAMES, _N_FEATURES

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger: logging.Logger = logging.getLogger("ml_models.rf_classifier")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Unique agent identifier — matches the Blackboard agent registry key.
_AGENT_ID: Final[str] = "random_forest"

#: Number of forward bars used to define the directional target.
#: y_t = 1 if Close[t+5] > Close[t]; else 0
_TARGET_FORWARD_BARS: Final[int] = 5

#: Minimum training samples required before fitting is attempted.
_MIN_TRAINING_SAMPLES: Final[int] = 200

#: Probability threshold below which the classifier outputs HOLD.
#: Prevents marginal-confidence trades from reaching execution.
_HOLD_THRESHOLD: Final[float] = 0.55

#: Model persistence directory (relative to project root).
_MODEL_DIR: Final[Path] = Path(__file__).resolve().parent / "scalers"
_MODEL_DIR.mkdir(parents=True, exist_ok=True)

#: Default model save/load filename.
_MODEL_FILENAME: Final[str] = "quantum_rf_v4.2.joblib"

#: Model version string embedded in every output payload.
_MODEL_VERSION: Final[str] = "4.2.0"

#: Class labels: 0 = SELL, 1 = BUY
_CLASS_SELL: Final[int] = 0
_CLASS_BUY:  Final[int] = 1


# ===========================================================================
# Pydantic v2 Input Validation — Live Feature Vector
# ===========================================================================

class LiveFeatureVectorSchema(BaseModel):
    """
    Pydantic v2 schema that validates the live feature vector passed to
    ``predict_live_direction`` before any inference is performed.

    Attributes
    ----------
    feature_values : List[float]
        A list of exactly ``_N_FEATURES`` (14) numerical values.
        No NaN or infinite values are permitted.
    n_features : int
        Must equal ``_N_FEATURES`` (14).
    has_nan : bool
        Must be False — NaN values in the feature vector are a
        data-pipeline error that must not reach the model.
    has_inf : bool
        Must be False — infinite values indicate overflow somewhere upstream.
    """
    model_config = {"frozen": True}

    feature_values: List[float] = Field(
        ...,
        min_length=_N_FEATURES,
        max_length=_N_FEATURES,
        description=f"Exactly {_N_FEATURES} numerical feature values.",
    )
    n_features: int = Field(
        ...,
        ge=_N_FEATURES,
        le=_N_FEATURES,
        description=f"Must equal {_N_FEATURES}.",
    )
    has_nan: bool = Field(
        ...,
        description="Must be False — no NaN allowed in feature vector.",
    )
    has_inf: bool = Field(
        ...,
        description="Must be False — no infinite values allowed.",
    )

    @field_validator("has_nan")
    @classmethod
    def _no_nan(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "Feature vector contains NaN values. "
                "Check the upstream QuantumFeaturePipeline for data gaps."
            )
        return v

    @field_validator("has_inf")
    @classmethod
    def _no_inf(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "Feature vector contains infinite values. "
                "Check the upstream ATR / return calculations for division errors."
            )
        return v


def _validate_feature_vector(
    feature_vector: np.ndarray,
) -> Tuple[bool, Optional[np.ndarray]]:
    """
    Validate and flatten an incoming feature vector before inference.

    Parameters
    ----------
    feature_vector : np.ndarray
        Input array of shape (1, 14) or (14,).

    Returns
    -------
    Tuple[bool, Optional[np.ndarray]]
        (True, cleaned_1d_array) on success; (False, None) on failure.
    """
    if not isinstance(feature_vector, np.ndarray):
        try:
            feature_vector = np.array(feature_vector, dtype=np.float64)
        except Exception as exc:
            logger.error(
                "[QuantumRFClassifier] Cannot convert feature_vector to numpy: %s", exc
            )
            return False, None

    # Flatten to 1D if shape is (1, N)
    if feature_vector.ndim == 2:
        if feature_vector.shape[0] != 1:
            logger.error(
                "[QuantumRFClassifier] Expected shape (1, %d) or (%d,); "
                "got %s.", _N_FEATURES, _N_FEATURES, feature_vector.shape,
            )
            return False, None
        feature_vector = feature_vector.flatten()

    flat: np.ndarray = feature_vector.astype(np.float64)

    # Pydantic validation
    try:
        LiveFeatureVectorSchema(
            feature_values=flat.tolist(),
            n_features=len(flat),
            has_nan=bool(np.isnan(flat).any()),
            has_inf=bool(np.isinf(flat).any()),
        )
    except Exception as exc:
        logger.error(
            "[QuantumRFClassifier] Feature vector validation failed: %s", exc
        )
        return False, None

    return True, flat


# ===========================================================================
# Target Label Generator
# ===========================================================================

def build_directional_target(
    close_series: pd.Series,
    forward_bars: int = _TARGET_FORWARD_BARS,
) -> pd.Series:
    """
    Construct the directional binary classification target vector.

    Formula
    -------
        y_t = 1 if Close[t + forward_bars] > Close[t]   → BUY class
        y_t = 0 if Close[t + forward_bars] ≤ Close[t]   → SELL class

    The last ``forward_bars`` rows of the target are NaN (no future
    labels available) — these rows are dropped during training.

    Parameters
    ----------
    close_series : pd.Series
        Chronological closing price series.
    forward_bars : int
        Number of bars ahead to define the directional outcome.
        Default: 5 (aligns with the TimesFM 10-bar horizon midpoint).

    Returns
    -------
    pd.Series
        Binary integer target series (0 or 1), same index as ``close_series``.
        The last ``forward_bars`` values are NaN.

    Examples
    --------
    >>> close = pd.Series([1.08, 1.082, 1.079, 1.085, 1.090, 1.088])
    >>> y = build_directional_target(close, forward_bars=5)
    >>> y.dropna().values
    array([1])   # only bar 0 has a label: Close[5]=1.088 > Close[0]=1.08
    """
    if len(close_series) <= forward_bars:
        raise ValueError(
            f"close_series must have > {forward_bars} bars; "
            f"received {len(close_series)}."
        )

    future_close: pd.Series = close_series.shift(-forward_bars)
    target: pd.Series = (future_close > close_series).astype(float)
    # Mask the last forward_bars rows (no valid label available)
    target.iloc[-forward_bars:] = np.nan
    return target


# ===========================================================================
# QuantumRFClassifier
# ===========================================================================

class QuantumRFClassifier:
    """
    Highly calibrated Random Forest ensemble classifier for the Quantum FSM
    Pro V4.2 Elite multi-agent trading system.

    Consumes 14-dimensional scaled feature vectors from ``QuantumFeaturePipeline``
    and outputs structured Blackboard-ready prediction payloads.

    Model Hyperparameters (fixed by architectural directive)
    ---------------------------------------------------------
    ::

        n_estimators  = 500    (ensemble size — reduces variance)
        max_depth     = 12     (complexity cap — prevents overfitting)
        min_samples_split = 5  (prevents fitting on tiny market micro-regimes)
        class_weight  = "balanced"  (handles BUY/SELL class imbalance)
        random_state  = 42
        n_jobs        = -1     (full CPU parallelism during training)
        oob_score     = True   (Out-of-bag cross-validation diagnostic)

    Parameters
    ----------
    hold_threshold : float
        Minimum probability required to emit BUY or SELL.
        If max(P(BUY), P(SELL)) < hold_threshold → HOLD.
        Default: 0.55 (5% edge over random chance).
    model_path : str or Path, optional
        Path to a pre-trained model checkpoint to load at construction.
        If None (default), a new untrained model is created.

    Attributes
    ----------
    _model : RandomForestClassifier
        The underlying scikit-learn model instance.
    _is_fitted : bool
        True after a successful ``fit()`` call.
    _oob_score : float or None
        Out-of-bag score from training (diagnostic, not used in inference).
    _training_ts : float or None
        UNIX timestamp when the model was last trained.
    _predict_count : int
        Monotonic count of successful ``predict_live_direction`` calls.
    """

    def __init__(
        self,
        hold_threshold: float = _HOLD_THRESHOLD,
        model_path:     Optional[str] = None,
    ) -> None:
        if not (0.5 < hold_threshold <= 1.0):
            raise ValueError(
                f"hold_threshold must be in (0.5, 1.0]; received {hold_threshold}."
            )

        self._hold_threshold:  float = hold_threshold
        self._is_fitted:       bool  = False
        self._oob_score:       Optional[float] = None
        self._training_ts:     Optional[float] = None
        self._predict_count:   int   = 0
        self._feature_importances: Optional[np.ndarray] = None

        # Instantiate the Random Forest with the specified hyperparameters
        self._model: RandomForestClassifier = RandomForestClassifier(
            n_estimators=500,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features="sqrt",        # standard for classification forests
            class_weight="balanced",    # corrects BUY/SELL class imbalance
            random_state=42,
            n_jobs=-1,
            oob_score=True,
            verbose=0,
        )

        # Load pre-trained weights if a model path is supplied
        if model_path is not None:
            self.load(model_path)
        else:
            logger.info(
                "[QuantumRFClassifier] New model initialized | "
                "n_estimators=500 | max_depth=12 | hold_threshold=%.2f",
                self._hold_threshold,
            )

    # -------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------

    def fit(
        self,
        feature_matrix:  pd.DataFrame,
        close_series:    pd.Series,
        forward_bars:    int = _TARGET_FORWARD_BARS,
        cv_folds:        int = 5,
        verbose:         bool = True,
    ) -> Dict[str, Any]:
        """
        Train the Random Forest ensemble on a historical feature matrix and
        the corresponding 5-bar directional target.

        Training Pipeline
        -----------------
        1. Generate the binary target vector $y$ using ``build_directional_target``.
        2. Align feature matrix rows with valid target rows (drop NaN tail).
        3. Validate minimum sample count (≥ 200 samples required).
        4. Fit the ``RandomForestClassifier`` on the full training set.
        5. Extract the out-of-bag score as a training diagnostic.
        6. Run a 5-fold stratified cross-validation to estimate generalization.
        7. Log the feature importance ranking by Gini impurity decrease.
        8. Return a structured training report dictionary.

        Parameters
        ----------
        feature_matrix : pd.DataFrame
            Historical feature matrix from ``QuantumFeaturePipeline.build_training_matrix``.
            Shape: (n_bars, 14).
        close_series : pd.Series
            Chronological closing price series aligned to ``feature_matrix``.
        forward_bars : int
            Forward look-ahead for target definition.  Default: 5.
        cv_folds : int
            Number of stratified cross-validation folds.  Default: 5.
        verbose : bool
            If True, log detailed training diagnostics.  Default: True.

        Returns
        -------
        Dict[str, Any]
            Training report with keys:
            ``oob_score``, ``cv_roc_auc_mean``, ``cv_roc_auc_std``,
            ``train_accuracy``, ``n_samples_train``, ``n_features``,
            ``class_distribution``, ``feature_importances``,
            ``training_timestamp``, ``model_version``.

        Raises
        ------
        ValueError
            If the training set has fewer than ``_MIN_TRAINING_SAMPLES`` samples
            or if the feature matrix and close series have mismatched lengths.
        """
        if len(feature_matrix) != len(close_series):
            raise ValueError(
                f"feature_matrix ({len(feature_matrix)} rows) and "
                f"close_series ({len(close_series)} rows) must have the same length."
            )

        logger.info(
            "[QuantumRFClassifier] Starting training | "
            "n_bars=%d | forward_bars=%d | cv_folds=%d",
            len(feature_matrix), forward_bars, cv_folds,
        )

        # ── Step 1: Generate binary directional target ───────────────────
        try:
            y_full: pd.Series = build_directional_target(close_series, forward_bars)
        except ValueError as exc:
            logger.error("[QuantumRFClassifier] Target generation failed: %s", exc)
            raise

        # ── Step 2: Align features with valid targets ────────────────────
        valid_mask: pd.Series  = y_full.notna()
        X_aligned: pd.DataFrame = feature_matrix.loc[valid_mask].copy()
        y_aligned: pd.Series    = y_full.loc[valid_mask].astype(int)

        # Replace any remaining NaN in features with column medians
        for col in X_aligned.columns:
            n_nan = X_aligned[col].isna().sum()
            if n_nan > 0:
                median_val = X_aligned[col].median()
                X_aligned[col] = X_aligned[col].fillna(median_val)
                logger.warning(
                    "[QuantumRFClassifier] Filled %d NaN(s) in '%s' with median=%.6f.",
                    n_nan, col, median_val,
                )

        X_np: np.ndarray = X_aligned.values.astype(np.float64)
        y_np: np.ndarray = y_aligned.values.astype(int)

        n_samples: int = len(X_np)
        if n_samples < _MIN_TRAINING_SAMPLES:
            raise ValueError(
                f"Training requires ≥ {_MIN_TRAINING_SAMPLES} samples after target "
                f"alignment; got {n_samples}. Provide more historical data."
            )

        # ── Step 3: Class distribution analysis ─────────────────────────
        n_buy:  int = int((y_np == _CLASS_BUY).sum())
        n_sell: int = int((y_np == _CLASS_SELL).sum())
        buy_pct: float = n_buy / n_samples * 100.0
        sell_pct: float = n_sell / n_samples * 100.0

        logger.info(
            "[QuantumRFClassifier] Class distribution | "
            "BUY(1): %d (%.1f%%) | SELL(0): %d (%.1f%%)",
            n_buy, buy_pct, n_sell, sell_pct,
        )

        # ── Step 4: Fit the Random Forest ────────────────────────────────
        t_fit_start = time.time()
        self._model.fit(X_np, y_np)
        fit_elapsed: float = time.time() - t_fit_start

        self._is_fitted   = True
        self._training_ts = time.time()
        self._oob_score   = float(self._model.oob_score_)
        self._feature_importances = self._model.feature_importances_

        logger.info(
            "[QuantumRFClassifier] Training complete | "
            "elapsed=%.1fs | n_samples=%d | OOB_score=%.4f",
            fit_elapsed, n_samples, self._oob_score,
        )

        # ── Step 5: Stratified cross-validation ─────────────────────────
        cv_auc_scores: np.ndarray = np.zeros(cv_folds)
        cv_success: bool = True
        try:
            skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
            cv_auc_scores = cross_val_score(
                estimator=self._model,
                X=X_np,
                y=y_np,
                cv=skf,
                scoring="roc_auc",
                n_jobs=-1,
            )
            logger.info(
                "[QuantumRFClassifier] CV ROC-AUC | "
                "folds=%d | mean=%.4f ± %.4f | scores=%s",
                cv_folds,
                float(np.mean(cv_auc_scores)),
                float(np.std(cv_auc_scores)),
                [round(s, 4) for s in cv_auc_scores],
            )
        except Exception as exc:
            logger.warning(
                "[QuantumRFClassifier] Cross-validation failed (non-fatal): %s", exc
            )
            cv_success = False

        # ── Step 6: In-sample metrics ────────────────────────────────────
        y_train_pred: np.ndarray = self._model.predict(X_np)
        train_accuracy: float    = float(accuracy_score(y_np, y_train_pred))

        if verbose:
            logger.info(
                "[QuantumRFClassifier] In-sample accuracy: %.4f", train_accuracy
            )
            report_str = classification_report(
                y_np,
                y_train_pred,
                target_names=["SELL(0)", "BUY(1)"],
                digits=4,
            )
            logger.info(
                "[QuantumRFClassifier] Classification report:\n%s", report_str
            )

        # ── Step 7: Feature importance ranking ───────────────────────────
        importances: np.ndarray = self._model.feature_importances_
        importance_ranking: List[Dict[str, Any]] = sorted(
            [
                {
                    "rank":       i + 1,
                    "feature":    FEATURE_NAMES[i],
                    "importance": round(float(importances[i]), 6),
                }
                for i in range(len(FEATURE_NAMES))
            ],
            key=lambda x: x["importance"],
            reverse=True,
        )

        if verbose:
            logger.info("[QuantumRFClassifier] Feature importance ranking:")
            for item in importance_ranking[:10]:
                logger.info(
                    "  #%d %-28s %.4f",
                    item["rank"],
                    item["feature"],
                    item["importance"],
                )

        # ── Step 8: Build training report ───────────────────────────────
        training_report: Dict[str, Any] = {
            "oob_score":            round(self._oob_score, 6),
            "cv_roc_auc_mean":      round(float(np.mean(cv_auc_scores)), 6) if cv_success else None,
            "cv_roc_auc_std":       round(float(np.std(cv_auc_scores)),  6) if cv_success else None,
            "train_accuracy":       round(train_accuracy, 6),
            "n_samples_train":      n_samples,
            "n_features":           _N_FEATURES,
            "class_distribution": {
                "buy_count":   n_buy,
                "sell_count":  n_sell,
                "buy_pct":     round(buy_pct, 2),
                "sell_pct":    round(sell_pct, 2),
            },
            "feature_importances":  importance_ranking,
            "training_timestamp":   self._training_ts,
            "fit_elapsed_seconds":  round(fit_elapsed, 2),
            "model_version":        _MODEL_VERSION,
            "forward_bars":         forward_bars,
            "hold_threshold":       self._hold_threshold,
        }

        return training_report

    # -------------------------------------------------------------------
    # Live Inference — Primary Blackboard Output Method
    # -------------------------------------------------------------------

    def predict_live_direction(
        self,
        feature_vector: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Run live inference on a single scaled feature row and return a
        JSON-serializable payload formatted for the ``QuantumBlackboard``.

        This is the primary agent-side inference method.  Every output from
        this function is designed to be passed directly to:
            ``blackboard.post_signal(SignalPayload(**payload))``

        Inference Pipeline
        ------------------
        1. Validate the feature vector via ``LiveFeatureVectorSchema`` (Pydantic v2).
        2. Reshape to (1, 14) for scikit-learn.
        3. Call ``model.predict_proba(X)`` → [P(SELL), P(BUY)].
        4. Apply HOLD threshold: if max(P(BUY), P(SELL)) < hold_threshold → HOLD.
        5. Map BUY/SELL probability to ``confidence_score`` [0.0, 1.0].
        6. Build and return the structured Blackboard payload dict.

        Parameters
        ----------
        feature_vector : np.ndarray
            Single live feature row.  Shape: ``(1, 14)`` or ``(14,)``.
            Must be the output of ``QuantumFeaturePipeline.transform_live_row()``.

        Returns
        -------
        Dict[str, Any]
            Structured Blackboard payload.  Keys:

            ``"agent_id"`` : str
                Always ``"random_forest"``.
            ``"signal_direction"`` : str
                One of ``"BUY"``, ``"SELL"``, ``"HOLD"``.
            ``"confidence_score"`` : float
                Confidence in [0.0, 1.0].  Maps max_prob from [0.5, 1.0]
                → [0.0, 1.0] via ``2 × (max_prob − 0.5)``.
            ``"timestamp"`` : float
                UNIX epoch seconds when this prediction was produced.
            ``"metadata"`` : dict
                Full diagnostic payload including raw probabilities,
                feature vector, OOB score, inference latency.

        Examples
        --------
        >>> live_X = pipeline.transform_live_row(live_df, smc_params)
        >>> payload = rf.predict_live_direction(live_X)
        >>> print(payload["signal_direction"], payload["confidence_score"])
        BUY 0.6823
        >>> # Post to the Blackboard:
        >>> blackboard.post_signal(SignalPayload(
        ...     agent_id=payload["agent_id"],
        ...     signal_direction=payload["signal_direction"],
        ...     confidence_score=payload["confidence_score"],
        ... ))
        """
        t0 = time.perf_counter()

        # ── Guard: model must be fitted ──────────────────────────────────
        if not self._is_fitted:
            logger.error(
                "[QuantumRFClassifier] predict_live_direction called before fit(). "
                "Train or load a model first. Returning HOLD with confidence=0."
            )
            return self._build_hold_payload(
                feature_flat=np.zeros(_N_FEATURES),
                proba_buy=0.5,
                proba_sell=0.5,
                reason="model_not_fitted",
                inference_ms=0.0,
            )

        # ── Step 1: Validate feature vector ─────────────────────────────
        valid, feature_flat = _validate_feature_vector(feature_vector)
        if not valid or feature_flat is None:
            return self._build_hold_payload(
                feature_flat=np.zeros(_N_FEATURES),
                proba_buy=0.5,
                proba_sell=0.5,
                reason="invalid_feature_vector",
                inference_ms=0.0,
            )

        # ── Step 2: Reshape for scikit-learn ─────────────────────────────
        X_inference: np.ndarray = feature_flat.reshape(1, -1)

        # ── Step 3: predict_proba → [P(SELL=0), P(BUY=1)] ───────────────
        try:
            proba: np.ndarray = self._model.predict_proba(X_inference)[0]
        except Exception as exc:
            logger.error(
                "[QuantumRFClassifier] predict_proba failed: %s\n%s",
                exc, traceback.format_exc(),
            )
            return self._build_hold_payload(
                feature_flat=feature_flat,
                proba_buy=0.5,
                proba_sell=0.5,
                reason="inference_exception",
                inference_ms=(time.perf_counter() - t0) * 1000.0,
            )

        # Safely extract class probabilities by class index
        # model.classes_ order is [0, 1] = [SELL, BUY]
        classes: np.ndarray = self._model.classes_
        proba_sell: float = 0.5
        proba_buy:  float = 0.5

        for i, cls in enumerate(classes):
            if cls == _CLASS_SELL:
                proba_sell = float(proba[i])
            elif cls == _CLASS_BUY:
                proba_buy = float(proba[i])

        # ── Step 4: HOLD threshold check ─────────────────────────────────
        max_prob: float = max(proba_buy, proba_sell)

        if max_prob < self._hold_threshold:
            # Conviction below threshold → emit HOLD, capital lock
            payload = self._build_hold_payload(
                feature_flat=feature_flat,
                proba_buy=proba_buy,
                proba_sell=proba_sell,
                reason="below_hold_threshold",
                inference_ms=(time.perf_counter() - t0) * 1000.0,
            )
            self._predict_count += 1
            return payload

        # ── Step 5: Map probability → confidence score ────────────────────
        # Formula: confidence = 2 × (max_prob − 0.5)
        # Maps [0.5, 1.0] → [0.0, 1.0]  (50% chance → 0 confidence)
        confidence: float = float(np.clip(2.0 * (max_prob - 0.5), 0.0, 1.0))

        # ── Step 6: Determine direction ───────────────────────────────────
        if proba_buy >= proba_sell:
            signal_direction: str = "BUY"
            raw_class:        int = _CLASS_BUY
        else:
            signal_direction = "SELL"
            raw_class        = _CLASS_SELL

        inference_ms: float = (time.perf_counter() - t0) * 1000.0
        self._predict_count += 1

        # ── Step 7: Build Blackboard payload ─────────────────────────────
        payload: Dict[str, Any] = {
            "agent_id":         _AGENT_ID,
            "signal_direction": signal_direction,
            "confidence_score": round(confidence, 6),
            "timestamp":        time.time(),
            "metadata": {
                "proba_buy":       round(proba_buy,       6),
                "proba_sell":      round(proba_sell,      6),
                "max_prob":        round(max_prob,        6),
                "raw_class":       raw_class,
                "hold_threshold":  self._hold_threshold,
                "feature_vector":  [round(v, 8) for v in feature_flat.tolist()],
                "feature_names":   FEATURE_NAMES,
                "oob_score":       round(self._oob_score, 6) if self._oob_score else None,
                "n_estimators":    500,
                "max_depth":       12,
                "model_version":   _MODEL_VERSION,
                "inference_ms":    round(inference_ms, 3),
                "predict_count":   self._predict_count,
                "training_timestamp": self._training_ts,
            },
        }

        logger.info(
            "[QuantumRFClassifier] #%d | %s | confidence=%.4f | "
            "P(BUY)=%.4f | P(SELL)=%.4f | elapsed=%.2fms",
            self._predict_count,
            signal_direction,
            confidence,
            proba_buy,
            proba_sell,
            inference_ms,
        )

        return payload

    def predict_proba_only(
        self,
        feature_vector: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Return the raw (P(SELL), P(BUY)) probability pair without building
        the full payload dict.

        Useful for batch back-testing where only probabilities are needed
        and the full Blackboard payload structure is overhead.

        Parameters
        ----------
        feature_vector : np.ndarray
            Single scaled feature row. Shape: (1, 14) or (14,).

        Returns
        -------
        Tuple[float, float]
            (proba_sell, proba_buy)
            Both values are in [0.0, 1.0] and sum to 1.0.
        """
        if not self._is_fitted:
            return 0.5, 0.5

        valid, flat = _validate_feature_vector(feature_vector)
        if not valid or flat is None:
            return 0.5, 0.5

        try:
            proba: np.ndarray = self._model.predict_proba(flat.reshape(1, -1))[0]
            classes = self._model.classes_
            p_sell, p_buy = 0.5, 0.5
            for i, cls in enumerate(classes):
                if cls == _CLASS_SELL:
                    p_sell = float(proba[i])
                elif cls == _CLASS_BUY:
                    p_buy = float(proba[i])
            return p_sell, p_buy
        except Exception as exc:
            logger.error("[QuantumRFClassifier] predict_proba_only failed: %s", exc)
            return 0.5, 0.5

    # -------------------------------------------------------------------
    # Model Persistence
    # -------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> str:
        """
        Persist the fitted model to disk using ``joblib``.

        Parameters
        ----------
        path : str, optional
            Full path to save the model checkpoint.
            If None, uses ``_MODEL_DIR / _MODEL_FILENAME``.

        Returns
        -------
        str
            The absolute path where the model was saved.

        Raises
        ------
        RuntimeError
            If the model has not been fitted before calling save.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "Cannot save an unfitted model. Call fit() first."
            )

        save_path: Path = Path(path) if path else (_MODEL_DIR / _MODEL_FILENAME)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint: Dict[str, Any] = {
            "model":            self._model,
            "hold_threshold":   self._hold_threshold,
            "oob_score":        self._oob_score,
            "training_ts":      self._training_ts,
            "predict_count":    self._predict_count,
            "model_version":    _MODEL_VERSION,
        }

        joblib.dump(checkpoint, save_path)
        logger.info(
            "[QuantumRFClassifier] Model saved to '%s' | "
            "OOB=%.4f | version=%s",
            save_path,
            self._oob_score or 0.0,
            _MODEL_VERSION,
        )
        return str(save_path)

    def load(self, path: Optional[str] = None) -> bool:
        """
        Load a previously saved model checkpoint from disk.

        Parameters
        ----------
        path : str, optional
            Full path to the model checkpoint.
            If None, uses ``_MODEL_DIR / _MODEL_FILENAME``.

        Returns
        -------
        bool
            True if loaded successfully; False otherwise.
        """
        load_path: Path = Path(path) if path else (_MODEL_DIR / _MODEL_FILENAME)

        if not load_path.exists():
            logger.warning(
                "[QuantumRFClassifier] Model file not found at '%s'. "
                "Initialize a new model and call fit().",
                load_path,
            )
            return False

        try:
            checkpoint: Dict[str, Any] = joblib.load(load_path)
            self._model           = checkpoint["model"]
            self._hold_threshold  = checkpoint.get("hold_threshold", _HOLD_THRESHOLD)
            self._oob_score       = checkpoint.get("oob_score")
            self._training_ts     = checkpoint.get("training_ts")
            self._predict_count   = checkpoint.get("predict_count", 0)
            self._is_fitted       = True
            self._feature_importances = self._model.feature_importances_

            logger.info(
                "[QuantumRFClassifier] Model loaded from '%s' | "
                "OOB=%.4f | version=%s | prior_predictions=%d",
                load_path,
                self._oob_score or 0.0,
                checkpoint.get("model_version", "unknown"),
                self._predict_count,
            )
            return True

        except Exception as exc:
            logger.error(
                "[QuantumRFClassifier] Model load failed: %s\n%s",
                exc, traceback.format_exc(),
            )
            return False

    # -------------------------------------------------------------------
    # Feature Importance Report
    # -------------------------------------------------------------------

    def get_feature_importance_report(self) -> List[Dict[str, Any]]:
        """
        Return a sorted feature importance table (descending by importance).

        Only available after a successful ``fit()`` or ``load()`` call.

        Returns
        -------
        List[Dict[str, Any]]
            Each entry: ``{"rank": int, "feature": str, "importance": float}``.
            Returns an empty list if the model has not been fitted.
        """
        if not self._is_fitted or self._feature_importances is None:
            logger.warning(
                "[QuantumRFClassifier] Feature importances unavailable: "
                "model not fitted."
            )
            return []

        ranked: List[Dict[str, Any]] = sorted(
            [
                {
                    "rank":       i + 1,
                    "feature":    FEATURE_NAMES[i],
                    "importance": round(float(self._feature_importances[i]), 6),
                }
                for i in range(len(FEATURE_NAMES))
            ],
            key=lambda x: x["importance"],
            reverse=True,
        )
        # Re-assign rank after sort
        for rank_idx, item in enumerate(ranked, start=1):
            item["rank"] = rank_idx

        return ranked

    # -------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------

    def _build_hold_payload(
        self,
        feature_flat: np.ndarray,
        proba_buy:    float,
        proba_sell:   float,
        reason:       str,
        inference_ms: float,
    ) -> Dict[str, Any]:
        """
        Build a HOLD signal payload for cases where conviction is insufficient
        or the model is in a degraded state.

        Parameters
        ----------
        feature_flat : np.ndarray
            1-D feature array (for diagnostic metadata).
        proba_buy : float
            P(BUY) from the model (or 0.5 for degraded fallback).
        proba_sell : float
            P(SELL) from the model.
        reason : str
            Short identifier explaining why HOLD was emitted.
        inference_ms : float
            Time elapsed in milliseconds.

        Returns
        -------
        Dict[str, Any]
            Standard Blackboard payload with ``signal_direction="HOLD"``.
        """
        return {
            "agent_id":         _AGENT_ID,
            "signal_direction": "HOLD",
            "confidence_score": 0.0,
            "timestamp":        time.time(),
            "metadata": {
                "proba_buy":       round(proba_buy,  6),
                "proba_sell":      round(proba_sell, 6),
                "max_prob":        round(max(proba_buy, proba_sell), 6),
                "raw_class":       None,
                "hold_threshold":  self._hold_threshold,
                "hold_reason":     reason,
                "feature_vector":  [round(v, 8) for v in feature_flat.tolist()],
                "feature_names":   FEATURE_NAMES,
                "oob_score":       round(self._oob_score, 6) if self._oob_score else None,
                "n_estimators":    500,
                "max_depth":       12,
                "model_version":   _MODEL_VERSION,
                "inference_ms":    round(inference_ms, 3),
                "predict_count":   self._predict_count,
                "training_timestamp": self._training_ts,
            },
        }

    # -------------------------------------------------------------------
    # Properties & Diagnostics
    # -------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        """True if the model has been successfully trained or loaded."""
        return self._is_fitted

    @property
    def oob_score(self) -> Optional[float]:
        """Out-of-bag accuracy score from the last training run."""
        return self._oob_score

    @property
    def predict_count(self) -> int:
        """Total successful ``predict_live_direction`` calls."""
        return self._predict_count

    def status_dict(self) -> Dict[str, Any]:
        """
        Return a structured health-check and configuration dictionary.

        Returns
        -------
        dict
            Keys: ``is_fitted``, ``oob_score``, ``n_estimators``,
            ``max_depth``, ``hold_threshold``, ``predict_count``,
            ``training_timestamp``, ``model_version``.
        """
        return {
            "is_fitted":          self._is_fitted,
            "oob_score":          round(self._oob_score, 6) if self._oob_score else None,
            "n_estimators":       500,
            "max_depth":          12,
            "min_samples_split":  5,
            "class_weight":       "balanced",
            "hold_threshold":     self._hold_threshold,
            "predict_count":      self._predict_count,
            "training_timestamp": self._training_ts,
            "model_version":      _MODEL_VERSION,
            "n_features":         _N_FEATURES,
            "feature_names":      FEATURE_NAMES,
        }

    def __repr__(self) -> str:
        status = "FITTED" if self._is_fitted else "UNFITTED"
        return (
            f"QuantumRFClassifier("
            f"status={status}, "
            f"oob={self._oob_score:.4f if self._oob_score else 'N/A'}, "
            f"hold_threshold={self._hold_threshold:.2f}, "
            f"predictions={self._predict_count})"
        )
