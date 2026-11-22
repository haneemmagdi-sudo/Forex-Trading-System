"""
=============================================================================
quant_core/meta_model.py — Institutional Meta-Labeling & Purged Calibration
=============================================================================
Architectural Authority: IMPROVEMENT_PLAN (Phase 3) & .antigravityrules
References:
  - Marcos Lopez de Prado (Advances in Financial Machine Learning, 2018)
    - Chapter 3: Target Engineering & Meta-Labeling
    - Chapter 7: Cross-Validation in Finance (Purged & Embargoed K-Fold)
  - John L. Kelly Jr. (A New Interpretation of Information Rate, 1956)

Design Core:
1. Primary Model: Determines direction (BUY/SELL) from 9-Indicator Voting Engine.
2. Meta-Model: Predicts probability P(Win | Primary Signal, Features) using
   Gradient Boosting with Purged & Embargoed Cross-Validation.
3. Probability Calibration:
   Platt scaling (Sigmoid) or Isotonic Regression via CalibratedClassifierCV.
4. Position Sizing (No Destructive Veto):
   Translates calibrated P(Win) into a fractional Kelly sizing multiplier.
   Does NOT discard trades with a rigid binary cut-off, avoiding edge erosion.
=============================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import BaseCrossValidator


class PurgedKFold(BaseCrossValidator):
    """
    Purged & Embargoed K-Fold Cross-Validator for Financial Time Series.
    Guarantees zero data leakage by:
      1. Purging: Removing training samples whose label horizons overlap test intervals.
      2. Embargoing: Dropping a buffer of samples after each test window to eliminate
         serial correlation leakage.
    """

    def __init__(
        self,
        n_splits: int = 5,
        holding_periods: Optional[np.ndarray] = None,
        pct_embargo: float = 0.02,
    ):
        self.n_splits = n_splits
        self.holding_periods = holding_periods
        self.pct_embargo = pct_embargo

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits

    def split(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        embargo = int(n_samples * self.pct_embargo)
        test_bounds = [(i * n_samples // self.n_splits, (i + 1) * n_samples // self.n_splits)
                       for i in range(self.n_splits)]

        for test_start, test_end in test_bounds:
            test_indices = indices[test_start:test_end]

            # Determine purge bounds
            max_holding = 24
            if self.holding_periods is not None:
                max_holding = int(np.max(self.holding_periods[test_indices]))

            purge_start = max(0, test_start - max_holding)
            embargo_end = min(n_samples, test_end + embargo)

            # Training indices exclude test window, overlapping pre-window, and post-embargo
            train_mask = (indices < purge_start) | (indices >= embargo_end)
            train_indices = indices[train_mask]

            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices


@dataclass
class MetaModelMetrics:
    brier_score: float
    roc_auc: float
    log_loss: float
    in_sample_accuracy: float
    out_of_sample_accuracy: float
    calibrated: bool


class MetaLabelingClassifier:
    """
    Calibrated Meta-Labeling Model.
    Trains on candidate signals to output true, un-snooped winning probabilities P(Win).
    """

    def __init__(
        self,
        calibration_method: str = "sigmoid",
        n_splits: int = 4,
        random_state: int = 42,
    ):
        self.calibration_method = calibration_method
        self.n_splits = n_splits
        self.random_state = random_state
        self.model: Optional[CalibratedClassifierCV] = None
        self.base_estimator: Optional[BaseEstimator] = None
        self.feature_names: List[str] = []
        self.is_fitted = False
        # P3: تنبؤات OOS الحقيقية (Purged K-Fold) بترتيبها الزمني — أساس بوابة التفعيل
        self.oos_labels_: np.ndarray = np.array([], dtype=int)
        self.oos_probs_: np.ndarray = np.array([], dtype=float)

    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        holding_bars: Optional[np.ndarray] = None,
    ) -> MetaModelMetrics:
        """Fits the meta-model using Purged K-Fold Cross-Validation and Platt / Isotonic Calibration."""
        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
            X_mat = X.values
        else:
            X_mat = np.asarray(X, dtype=float)
            self.feature_names = [f"f_{i}" for i in range(X_mat.shape[1])]

        y_vec = np.asarray(y, dtype=int)

        if len(np.unique(y_vec)) < 2:
            # Degenerate case (single class)
            self.is_fitted = False
            self.oos_labels_ = np.array([], dtype=int)
            self.oos_probs_ = np.array([], dtype=float)
            return MetaModelMetrics(1.0, 0.5, 1.0, 0.0, 0.0, False)

        # Base estimator: Modern HistGradientBoosting (fast, robust, non-linear)
        self.base_estimator = HistGradientBoostingClassifier(
            max_iter=30,
            max_leaf_nodes=15,
            min_samples_leaf=5,
            learning_rate=0.08,
            random_state=self.random_state,
        )

        cv = PurgedKFold(n_splits=self.n_splits, holding_periods=holding_bars, pct_embargo=0.02)

        # P1 fix: Compute TRUE Out-of-Sample (OOS) predictions across PurgedKFold splits (zero leakage)
        oos_probs = np.full(len(y_vec), np.nan, dtype=float)
        for train_idx, test_idx in cv.split(X_mat, y_vec):
            if len(np.unique(y_vec[train_idx])) < 2:
                continue
            fold_est = HistGradientBoostingClassifier(
                max_iter=30,
                max_leaf_nodes=15,
                min_samples_leaf=5,
                learning_rate=0.08,
                random_state=self.random_state,
            )
            inner_cv = min(3, max(2, int(np.min(np.bincount(y_vec[train_idx])))))
            if inner_cv >= 2 and len(train_idx) >= 10:
                fold_cal = CalibratedClassifierCV(estimator=fold_est, method=self.calibration_method, cv=inner_cv)
                fold_cal.fit(X_mat[train_idx], y_vec[train_idx])
                oos_probs[test_idx] = fold_cal.predict_proba(X_mat[test_idx])[:, 1]
            else:
                fold_est.fit(X_mat[train_idx], y_vec[train_idx])
                oos_probs[test_idx] = fold_est.predict_proba(X_mat[test_idx])[:, 1]

        # Fit final production calibrated classifier on full dataset via PurgedKFold
        self.model = CalibratedClassifierCV(
            estimator=self.base_estimator,
            method=self.calibration_method,
            cv=cv,
        )
        self.model.fit(X_mat, y_vec)
        self.is_fitted = True

        # In-sample accuracy (for overfitting gap diagnostics)
        is_probs = self.model.predict_proba(X_mat)[:, 1]
        is_acc = float(np.mean((is_probs >= 0.5).astype(int) == y_vec) * 100.0)

        # Strictly Out-of-Sample metrics (Brier, ROC-AUC, LogLoss, OOS Accuracy)
        valid_mask = ~np.isnan(oos_probs)
        self.oos_labels_ = y_vec[valid_mask].astype(int)
        self.oos_probs_ = np.clip(oos_probs[valid_mask], 1e-6, 1.0 - 1e-6)
        if np.sum(valid_mask) >= 5 and len(np.unique(y_vec[valid_mask])) > 1:
            y_oos = y_vec[valid_mask]
            p_oos = np.clip(oos_probs[valid_mask], 1e-6, 1.0 - 1e-6)
            brier = float(brier_score_loss(y_oos, p_oos))
            auc = float(roc_auc_score(y_oos, p_oos))
            ll = float(log_loss(y_oos, p_oos))
            oos_acc = float(np.mean((p_oos >= 0.5).astype(int) == y_oos) * 100.0)
        else:
            brier, auc, ll, oos_acc = 0.25, 0.50, 0.6931, 50.0

        return MetaModelMetrics(
            brier_score=round(brier, 4),
            roc_auc=round(auc, 4),
            log_loss=round(ll, 4),
            in_sample_accuracy=round(is_acc, 2),
            out_of_sample_accuracy=round(oos_acc, 2),
            calibrated=True,
        )

    def predict_probability(self, features: Union[np.ndarray, List[float], Dict[str, float]]) -> float:
        """Returns the calibrated probability of success P(Win) in [0.0, 1.0]."""
        if not self.is_fitted or self.model is None:
            return 0.50  # Neutral fallback

        if isinstance(features, dict):
            feat_vec = [float(features.get(name, 0.0)) for name in self.feature_names]
            X_in = np.array([feat_vec], dtype=float)
        elif isinstance(features, list):
            X_in = np.array([features], dtype=float)
        else:
            X_in = np.asarray(features, dtype=float)
            if X_in.ndim == 1:
                X_in = X_in.reshape(1, -1)

        try:
            prob = self.model.predict_proba(X_in)[0, 1]
            return float(np.clip(prob, 0.01, 0.99))
        except Exception:
            return 0.50

    def predict_calibrated(self, features: Union[np.ndarray, List[float], Dict[str, float]]) -> Optional[float]:
        """
        P3: الاحتمال المعاير الحقيقي أو None — **لا يُختلق 0.50 أبداً**.
        None إذا لم يُدرَّب النموذج، أو عدد/أسماء الخصائص لا تطابق التدريب، أو فشل التنبؤ.
        """
        if not self.is_fitted or self.model is None:
            return None
        if isinstance(features, dict):
            vec = [features.get(n) for n in self.feature_names]
            if any(v is None for v in vec):
                return None
            X_in = np.array([vec], dtype=float)
        else:
            X_in = np.asarray(features, dtype=float)
            if X_in.ndim == 1:
                X_in = X_in.reshape(1, -1)
        if self.feature_names and X_in.shape[1] != len(self.feature_names):
            return None
        if not np.all(np.isfinite(X_in)):
            return None
        try:
            return float(np.clip(self.model.predict_proba(X_in)[0, 1], 0.01, 0.99))
        except Exception:
            return None

    def activation_decision(self, gate=None):
        """P3: قرار بوابة التفعيل على تنبؤات OOS المخزّنة (انظر quant_core/activation_gate.py)."""
        from quant_core.activation_gate import MetaActivationGate, GateDecision
        if not self.is_fitted or self.model is None:
            return GateDecision(active=False, reasons=("not_fitted",))
        gate = gate or MetaActivationGate()
        return gate.evaluate(self.oos_labels_, self.oos_probs_)

    def save(self, filepath: str) -> None:
        """Persists the fitted MetaLabelingClassifier to disk via joblib."""
        import joblib
        joblib.dump({
            "model": self.model,
            "feature_names": self.feature_names,
            "calibration_method": self.calibration_method,
            "is_fitted": self.is_fitted,
            "oos_labels": self.oos_labels_,
            "oos_probs": self.oos_probs_,
        }, filepath)

    @classmethod
    def load(cls, filepath: str) -> "MetaLabelingClassifier":
        """Loads a previously persisted MetaLabelingClassifier from disk."""
        import joblib
        payload = joblib.load(filepath)
        obj = cls(calibration_method=payload.get("calibration_method", "sigmoid"))
        obj.model = payload["model"]
        obj.feature_names = payload.get("feature_names", [])
        obj.is_fitted = bool(payload.get("is_fitted", False))
        # ملفات P1/P2 القديمة بلا OOS ← بوابة مغلقة (no_oos_predictions/n_oos=0) حتى إعادة التدريب
        obj.oos_labels_ = np.asarray(payload.get("oos_labels", []), dtype=int)
        obj.oos_probs_ = np.asarray(payload.get("oos_probs", []), dtype=float)
        return obj


class CalibratedKellySizer:
    """
    Dynamic Position Sizer using Calibrated Meta-Labeling Probability.
    Avoids destructive hard vetoes by continuously scaling position size.
    """

    def __init__(
        self,
        fractional_kelly: float = 0.25,
        min_multiplier: float = 0.25,
        max_multiplier: float = 1.50,
        neutral_prob: float = 0.50,
    ):
        self.fraction = fractional_kelly
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier
        self.neutral_prob = neutral_prob

    def compute_size_multiplier(
        self,
        calibrated_p_win: float,
        reward_to_risk: float = 1.33,
    ) -> float:
        """
        Translates P(Win) into a smooth sizing multiplier centered at 1.0.
        When P(Win) = neutral_prob (0.50), returns 1.0 (baseline risk).
        When P(Win) > 0.50, smoothly scales up to max_multiplier (e.g. 1.50).
        When P(Win) < 0.50, smoothly scales down to min_multiplier (e.g. 0.25).
        """
        b = max(reward_to_risk, 0.5)
        p = float(np.clip(calibrated_p_win, 0.05, 0.95))
        q = 1.0 - p

        # Full Kelly fraction
        full_kelly = (p * b - q) / b

        # Neutral Kelly at p=0.50
        neutral_p = self.neutral_prob
        neutral_kelly = (neutral_p * b - (1.0 - neutral_p)) / b

        if neutral_kelly <= 0:
            neutral_kelly = 0.10

        # Relative Kelly ratio
        scale = 1.0 + self.fraction * ((full_kelly - neutral_kelly) / max(abs(neutral_kelly), 0.10))
        multiplier = float(np.clip(scale, self.min_multiplier, self.max_multiplier))
        return round(multiplier, 2)
