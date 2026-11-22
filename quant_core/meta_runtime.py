"""
=============================================================================
quant_core/meta_runtime.py — مزوّد الاحتمال المعاير لمسار التنفيذ الحي (P3)
=============================================================================
يقرأ نموذج Meta-Labeling المحفوظ (meta_model.pkl) ويُرجع P(Win) المعاير **فقط**
إذا اجتاز النموذج بوابة التفعيل (OOS). غير ذلك يُرجع None — ولا يُختلق احتمال
ولا يُستخدم أي نموذج غير معاير.

يعيد التحميل تلقائياً عند تغيّر وقت تعديل الملف (أي بعد إعادة تدريب LearningAgent).
=============================================================================
"""
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Union

from quant_core.activation_gate import GateDecision, MetaActivationGate


class MetaProbabilityProvider:
    def __init__(self, model_path: str, gate: Optional[MetaActivationGate] = None):
        self.model_path = model_path
        self.gate = gate or MetaActivationGate()
        self._model = None
        self._decision = GateDecision(active=False, reasons=("model_not_loaded",))
        self._mtime: Optional[float] = None
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        try:
            mtime = os.path.getmtime(self.model_path)
        except OSError:
            self._model, self._mtime = None, None
            self._decision = GateDecision(active=False, reasons=("model_file_missing",))
            return
        if mtime == self._mtime:
            return
        from quant_core.meta_model import MetaLabelingClassifier
        try:
            model = MetaLabelingClassifier.load(self.model_path)
        except Exception as exc:  # ملف تالف: بوابة مغلقة وليس استثناء في مسار التنفيذ
            self._model, self._mtime = None, mtime
            self._decision = GateDecision(active=False, reasons=(f"model_load_failed: {type(exc).__name__}",))
            return
        self._model, self._mtime = model, mtime
        self._decision = model.activation_decision(self.gate)

    def decision(self) -> GateDecision:
        with self._lock:
            self._refresh()
            return self._decision

    def probability(self, features: Union[List[float], Dict[str, float], None]) -> Optional[float]:
        if features is None:
            return None
        with self._lock:
            self._refresh()
            if not self._decision.active or self._model is None:
                return None
            return self._model.predict_calibrated(features)
