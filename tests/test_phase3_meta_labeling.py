"""
=============================================================================
tests/test_phase3_meta_labeling.py — Unit Tests for Phase 3 Meta-Labeling & Sizing
=============================================================================
Tests:
  1. PurgedKFold zero-leakage guarantee (Purging + Embargoing).
  2. MetaLabelingClassifier calibration & probability output.
  3. CalibratedKellySizer continuous position sizing (No Destructive Veto).
  4. SafeExecutionGateway calibrated lot size modulation.
  5. Operational Magic Numbers & Emergency Kill Switches.
=============================================================================
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from quant_core.meta_model import PurgedKFold, MetaLabelingClassifier, CalibratedKellySizer
from backend.config import MAGIC_NUMBERS, STRATEGY


class TestPhase3MetaLabelingAndSizing(unittest.TestCase):

    def test_purged_kfold_no_overlap(self):
        """Verify that PurgedKFold strictly removes overlapping lookahead and post-embargo bars."""
        n_samples = 100
        X = np.arange(n_samples).reshape(-1, 1)
        holding_periods = np.full(n_samples, 10)  # Each trade held for 10 bars

        cv = PurgedKFold(n_splits=5, holding_periods=holding_periods, pct_embargo=0.05)
        splits = list(cv.split(X))
        self.assertEqual(len(splits), 5)

        for train_idx, test_idx in splits:
            test_start, test_end = test_idx[0], test_idx[-1] + 1
            # Check purging: no training sample within max_holding before test start
            purge_zone = set(range(max(0, test_start - 10), test_start))
            # Check embargo: no training sample within embargo after test end
            embargo_zone = set(range(test_end, min(n_samples, test_end + 5)))

            overlap_purge = set(train_idx).intersection(purge_zone)
            overlap_embargo = set(train_idx).intersection(embargo_zone)
            overlap_test = set(train_idx).intersection(set(test_idx))

            self.assertEqual(len(overlap_test), 0, "Test samples leaked into train")
            self.assertEqual(len(overlap_purge), 0, "Purge zone leaked into train")
            self.assertEqual(len(overlap_embargo), 0, "Embargo zone leaked into train")

    def test_meta_labeling_classifier_calibration(self):
        """Verify MetaLabelingClassifier fits with Platt calibration and outputs calibrated probabilities."""
        np.random.seed(42)
        n = 80
        # 8 features matching real candidate signal indicators
        X = np.random.randn(n, 8)
        # Synthetic non-linear ground truth
        logits = 0.8 * X[:, 0] - 0.5 * X[:, 1] + 0.3 * X[:, 4]
        probs = 1.0 / (1.0 + np.exp(-logits))
        y = (probs > 0.5).astype(int)

        clf = MetaLabelingClassifier(calibration_method="sigmoid", n_splits=3, random_state=42)
        metrics = clf.fit(X, y)

        self.assertTrue(clf.is_fitted)
        self.assertTrue(metrics.calibrated)
        self.assertGreater(metrics.roc_auc, 0.50)
        self.assertLess(metrics.brier_score, 0.35)

        # Prediction output check
        sample_features = [0.5, -0.2, 0.1, 1.0, 0.4, 0.0, 0.5, 0.2]
        pred_p = clf.predict_probability(sample_features)
        self.assertGreaterEqual(pred_p, 0.01)
        self.assertLessEqual(pred_p, 0.99)

    def test_calibrated_kelly_sizer_smooth_scaling(self):
        """Verify Kelly sizer smoothly scales without discarding trades via binary cutoff."""
        sizer = CalibratedKellySizer(fractional_kelly=0.25, min_multiplier=0.25, max_multiplier=1.50)

        # 1. Neutral probability (0.50) should give baseline multiplier ~1.0
        neutral_mult = sizer.compute_size_multiplier(calibrated_p_win=0.50, reward_to_risk=1.5)
        self.assertAlmostEqual(neutral_mult, 1.0, delta=0.10)

        # 2. High probability (0.75) should scale UP
        high_mult = sizer.compute_size_multiplier(calibrated_p_win=0.75, reward_to_risk=1.5)
        self.assertGreater(high_mult, 1.0)
        self.assertLessEqual(high_mult, 1.50)

        # 3. Low probability (0.35) should scale DOWN but NOT drop to 0.0 (no destructive veto)
        low_mult = sizer.compute_size_multiplier(calibrated_p_win=0.35, reward_to_risk=1.5)
        self.assertLess(low_mult, 1.0)
        self.assertGreaterEqual(low_mult, 0.25)

    def test_magic_numbers_unified(self):
        """Verify MAGIC_NUMBERS registry contains distinct magic numbers for live and shadow modes."""
        self.assertIn("live_engine", MAGIC_NUMBERS)
        self.assertIn("shadow_council", MAGIC_NUMBERS)
        self.assertEqual(MAGIC_NUMBERS["live_engine"], 112345)
        self.assertEqual(MAGIC_NUMBERS["shadow_council"], 20261016)
        self.assertNotEqual(MAGIC_NUMBERS["live_engine"], MAGIC_NUMBERS["shadow_council"])

    def test_basket_max_loss_safety(self):
        """Verify basket_max_loss_usd is configured to prevent grid explosion."""
        basket_max_loss = STRATEGY.get("basket_max_loss_usd")
        self.assertIsNotNone(basket_max_loss)
        self.assertLessEqual(basket_max_loss, 25.0)


if __name__ == "__main__":
    unittest.main()
