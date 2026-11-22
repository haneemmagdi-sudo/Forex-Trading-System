"""
=============================================================================
quant_core/activation_gate.py — بوابة تفعيل الاحتمال المعاير (P3)
=============================================================================
القاعدة (AGENTS.md + IMPROVEMENT_PLAN §3): لا يُفعَّل أي مكوّن يؤثر في القرار
(هنا: تحجيم الصفقة بالاحتمال المعاير) قبل ظهور قيمة موجبة **خارج العيّنة**.

تُقيَّم البوابة على تنبؤات OOS الحقيقية الناتجة من Purged K-Fold (لا على
التدريب)، وتشترط معاً:
  1) عدد عيّنات OOS ≥ min_oos_samples.
  2) الحدّ الأدنى لفترة ثقة AUC > min_auc_lower (فترة لا تشمل 0.5).
     الفترة بـ bootstrap بالكتل (moving-block) لأن الصفقات المتتالية مترابطة.
     الثقة الافتراضية 99% (لا 95%): القياس بمحاكاة 60 حالة ضجيج (n=500) أعطى فتحاً خاطئاً 1/60 عند 95%
     و0/60 عند 99% — والنموذج يُعاد تدريبه كل ساعة فتتعدد «النظرات» وترتفع احتمالية الفتح بالصدفة.
  3) Brier Skill > min_brier_skill مقابل المتنبّئ الثابت (نسبة الفوز الأساسية):
         BSS = 1 − Brier_model / Brier_base ،  Brier_base = p̄(1 − p̄)

لا أرقام افتراضية مُلفّقة: أي مدخلات ناقصة أو فئة واحدة ← البوابة مغلقة مع السبب.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score


@dataclass(frozen=True)
class GateDecision:
    active: bool
    reasons: Tuple[str, ...]
    n_oos: int = 0
    auc: float = float("nan")
    auc_ci_low: float = float("nan")
    brier: float = float("nan")
    brier_baseline: float = float("nan")
    brier_skill: float = float("nan")

    def summary(self) -> str:
        state = "ACTIVE" if self.active else "INACTIVE"
        why = "ok" if self.active else "; ".join(self.reasons)
        return (
            f"MetaGate[{state}] n_oos={self.n_oos} auc={self.auc:.3f} "
            f"auc_ci_low={self.auc_ci_low:.3f} brier_skill={self.brier_skill:.3f} ({why})"
        )


def _closed(reason: str, n: int = 0) -> GateDecision:
    return GateDecision(active=False, reasons=(reason,), n_oos=n)


class MetaActivationGate:
    def __init__(
        self,
        min_oos_samples: int = 200,
        min_auc_lower: float = 0.50,
        min_brier_skill: float = 0.0,
        n_bootstrap: int = 1000,
        confidence: float = 0.99,
        block_size: int = 10,
        seed: int = 42,
    ):
        if not (0.5 < confidence < 1.0):
            raise ValueError("confidence must be in (0.5, 1.0)")
        if n_bootstrap < 100:
            raise ValueError("n_bootstrap must be >= 100")
        if block_size < 1:
            raise ValueError("block_size must be >= 1")
        self.min_oos_samples = int(min_oos_samples)
        self.min_auc_lower = float(min_auc_lower)
        self.min_brier_skill = float(min_brier_skill)
        self.n_bootstrap = int(n_bootstrap)
        self.confidence = float(confidence)
        self.block_size = int(block_size)
        self.seed = int(seed)

    # ── bootstrap بالكتل لفترة ثقة AUC ─────────────────────────────────
    def _auc_ci_low(self, y: np.ndarray, p: np.ndarray) -> Optional[float]:
        n = len(y)
        rng = np.random.default_rng(self.seed)
        b = min(self.block_size, n)
        n_blocks = int(np.ceil(n / b))
        aucs = []
        for _ in range(self.n_bootstrap):
            starts = rng.integers(0, n - b + 1, size=n_blocks)
            idx = np.concatenate([np.arange(s, s + b) for s in starts])[:n]
            yy = y[idx]
            if yy.min() == yy.max():
                continue  # عيّنة بفئة واحدة: AUC غير معرّف
            aucs.append(roc_auc_score(yy, p[idx]))
        if len(aucs) < max(50, self.n_bootstrap // 5):
            return None
        alpha = (1.0 - self.confidence) / 2.0
        return float(np.percentile(aucs, alpha * 100.0))

    def evaluate(self, y_true: Optional[Sequence[int]], p_oos: Optional[Sequence[float]]) -> GateDecision:
        if y_true is None or p_oos is None:
            return _closed("no_oos_predictions")
        y = np.asarray(y_true, dtype=int)
        p = np.asarray(p_oos, dtype=float)
        if y.ndim != 1 or p.ndim != 1 or len(y) != len(p):
            return _closed("oos_shape_mismatch")
        mask = ~np.isnan(p)
        y, p = y[mask], np.clip(p[mask], 1e-6, 1.0 - 1e-6)
        n = len(y)

        reasons = []
        if n < self.min_oos_samples:
            reasons.append(f"n_oos {n} < min_oos_samples {self.min_oos_samples}")
            return GateDecision(active=False, reasons=tuple(reasons), n_oos=n)
        if y.min() == y.max():
            return GateDecision(active=False, reasons=("single_class_labels",), n_oos=n)

        auc = float(roc_auc_score(y, p))
        brier = float(brier_score_loss(y, p))
        base_rate = float(np.mean(y))
        brier_base = base_rate * (1.0 - base_rate)
        skill = 1.0 - brier / brier_base if brier_base > 1e-12 else float("nan")
        ci_low = self._auc_ci_low(y, p)

        if ci_low is None:
            reasons.append("auc_ci_unavailable")
            ci_low_val = float("nan")
        else:
            ci_low_val = ci_low
            if not ci_low > self.min_auc_lower:
                reasons.append(f"auc_ci_low {ci_low:.3f} <= {self.min_auc_lower:.3f}")
        if not (skill > self.min_brier_skill):
            reasons.append(f"brier_skill {skill:.3f} <= {self.min_brier_skill:.3f}")

        return GateDecision(
            active=len(reasons) == 0,
            reasons=tuple(reasons),
            n_oos=n,
            auc=auc,
            auc_ci_low=ci_low_val,
            brier=brier,
            brier_baseline=brier_base,
            brier_skill=skill,
        )
