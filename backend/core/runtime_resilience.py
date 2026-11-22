"""
============================================================
runtime_resilience.py — المرونة الذاتية وكشف انجراف الألفا (2026)
============================================================
يوفر طبقتي الترميم الذاتي الحقيقيتين في التداول المؤسسي (بدون تعديل الكود الحي):
  1. PageHinkleyDriftDetector & AlphaDecayGuard:
     رصد التدهور الهيكلي في توقّع الأرباح (Downward Alpha Decay / Concept Drift)
     وتحويل الاستراتيجية/الزوج تلقائياً إلى وضع الظل (Shadow Demotion).
  2. RuntimeResilienceWatchdog:
     مراقبة نبضات الوكلاء (Heartbeat Stall Detection)، ومراقبة زمن التنفيذ،
     واسترداد اتصال MT5 تلقائياً بقاطع دائرة مضبوط (Circuit-Breaker Reconnect).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DriftStatus:
    key: str
    samples: int
    running_mean: float
    drift_score: float
    threshold: float
    drift_detected: bool
    shadow_demoted: bool
    demoted_at_utc: Optional[str] = None


class PageHinkleyDriftDetector:
    """
    اختبار Page-Hinkley أحادي الاتجاه لرصد الانحدار التراكمي (Downward Drift)
    في أرباح الصفقات (بالدولار أو بالبيب).
    يرصد التدهور عندما يهبط الأداء التراكمي أسفل المتوسط التاريخي بأكثر من `threshold`.
    """

    def __init__(
        self,
        delta: float = 0.05,
        threshold: float = 4.0,
        min_samples: int = 10,
    ):
        self.delta = max(0.0, float(delta))
        self.threshold = max(0.5, float(threshold))
        self.min_samples = max(4, int(min_samples))
        self.reset()

    def reset(self) -> None:
        self.n: int = 0
        self.mean: float = 0.0
        self.cum_sum: float = 0.0
        self.min_cum_sum: float = 0.0
        self.drift_score: float = 0.0
        self.drift_detected: bool = False

    def update(self, value: float) -> bool:
        """
        يدمج نتيجة صفقة جديدة (مثلاً ربح/خسارة معياري أو بالدولار).
        يعيد True عند رصد انجراف هابط (Alpha Decay).
        """
        x = float(value)
        self.n += 1
        self.mean += (x - self.mean) / self.n
        # نراقب الانحراف السلبي: (mean - x - delta) يكون موجباً عندما تتراجع النتائج عن المتوسط
        self.cum_sum += (self.mean - x - self.delta)
        if self.cum_sum < self.min_cum_sum:
            self.min_cum_sum = self.cum_sum
        self.drift_score = round(self.cum_sum - self.min_cum_sum, 4)

        if self.n >= self.min_samples and self.drift_score >= self.threshold:
            self.drift_detected = True
        return self.drift_detected


class AlphaDecayGuard:
    """
    يدير كواشف Page-Hinkley لكل زوج/استراتيجية ويطبّق التحويل التلقائي
    إلى وضع الظل (Shadow Demotion) فور تأكيد انجراف الألفا.
    """

    def __init__(
        self,
        delta: float = 0.05,
        threshold: float = 4.0,
        min_samples: int = 10,
        pnl_scale: float = 10.0,
    ):
        self.delta = float(delta)
        self.threshold = float(threshold)
        self.min_samples = int(min_samples)
        self.pnl_scale = max(1e-6, float(pnl_scale))
        self._detectors: Dict[str, PageHinkleyDriftDetector] = {}
        self._demoted: Dict[str, str] = {}

    def _get(self, key: str) -> PageHinkleyDriftDetector:
        if key not in self._detectors:
            self._detectors[key] = PageHinkleyDriftDetector(
                delta=self.delta, threshold=self.threshold, min_samples=self.min_samples
            )
        return self._detectors[key]

    def record_trade(self, key: str, profit_usd: float) -> DriftStatus:
        """يسجّل نتيجة صفقة مطبّعة على pnl_scale ويُرجع حالة الانجراف والتحويل للظل."""
        det = self._get(key)
        scaled = max(-3.0, min(3.0, float(profit_usd) / self.pnl_scale))
        drifted = det.update(scaled)
        if drifted and key not in self._demoted:
            self._demoted[key] = datetime.now(timezone.utc).isoformat()
        return DriftStatus(
            key=key,
            samples=det.n,
            running_mean=round(det.mean * self.pnl_scale, 3),
            drift_score=det.drift_score,
            threshold=det.threshold,
            drift_detected=det.drift_detected,
            shadow_demoted=key in self._demoted,
            demoted_at_utc=self._demoted.get(key),
        )

    def is_demoted(self, key: str) -> bool:
        return key in self._demoted

    def promote_back(self, key: str) -> None:
        """إعادة التفعيل للوضع الحي بعد مراجعة بشرية أو تحسن موثّق في الظل."""
        self._demoted.pop(key, None)
        if key in self._detectors:
            self._detectors[key].reset()

    def demoted_keys(self) -> List[str]:
        return sorted(self._demoted.keys())


class RuntimeResilienceWatchdog:
    """
    مراقب صحة وقت التشغيل:
      1. كشف توقف نبضات الوكلاء (Heartbeat Stall).
      2. تتبع طفرات زمن التنفيذ (Latency Spikes).
      3. استرداد اتصال MT5 بقاطع دائرة مضبوط (Circuit-Breaker Reconnect).
    """

    def __init__(
        self,
        heartbeat_max_silence_sec: float = 60.0,
        latency_spike_ms: float = 1500.0,
        max_reconnect_attempts: int = 3,
        reconnect_cooldown_sec: float = 30.0,
    ):
        self.heartbeat_max_silence_sec = max(5.0, float(heartbeat_max_silence_sec))
        self.latency_spike_ms = max(100.0, float(latency_spike_ms))
        self.max_reconnect_attempts = max(1, int(max_reconnect_attempts))
        self.reconnect_cooldown_sec = max(0.0, float(reconnect_cooldown_sec))

        self._heartbeats: Dict[str, float] = {}
        self._consecutive_latency_spikes: int = 0
        self._reconnect_attempts: int = 0
        self._last_reconnect_ts: float = 0.0
        self.total_recoveries: int = 0

    def record_heartbeat(self, agent_name: str, now_monotonic: Optional[float] = None) -> None:
        self._heartbeats[str(agent_name)] = time.monotonic() if now_monotonic is None else float(now_monotonic)

    def check_stalled_agents(self, now_monotonic: Optional[float] = None) -> List[str]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        stalled = []
        for name, ts in self._heartbeats.items():
            if (now - ts) > self.heartbeat_max_silence_sec:
                stalled.append(name)
        return sorted(stalled)

    def record_execution_latency(self, latency_ms: float) -> bool:
        """يعيد True إذا تكررت 3 طفرات تأخير متتالية تستوجب فحص الاتصال."""
        if float(latency_ms) > self.latency_spike_ms:
            self._consecutive_latency_spikes += 1
        else:
            self._consecutive_latency_spikes = 0
        return self._consecutive_latency_spikes >= 3

    def check_and_recover_mt5(
        self,
        mt5_connector: Any,
        now_monotonic: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        يفحص حالة اتصال MT5 ويعيد الاتصال ضمن حدود قاطع الدائرة (حد المحاولات + فترة التهدئة).
        """
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        is_connected = bool(getattr(mt5_connector, "connected", False))
        needs_recovery = (not is_connected) or (self._consecutive_latency_spikes >= 3)

        if not needs_recovery:
            self._reconnect_attempts = 0
            return {"status": "HEALTHY", "recovered": False, "attempts": 0}

        if self._reconnect_attempts >= self.max_reconnect_attempts:
            return {
                "status": "CIRCUIT_OPEN",
                "recovered": False,
                "attempts": self._reconnect_attempts,
                "reason": "max_reconnect_attempts_reached",
            }

        if self._last_reconnect_ts > 0 and (now - self._last_reconnect_ts) < self.reconnect_cooldown_sec:
            return {
                "status": "COOLDOWN",
                "recovered": False,
                "attempts": self._reconnect_attempts,
            }

        self._last_reconnect_ts = now
        self._reconnect_attempts += 1

        connect_fn = getattr(mt5_connector, "reconnect", None) or getattr(mt5_connector, "connect", None)
        if connect_fn is None:
            return {"status": "NO_CONNECT_METHOD", "recovered": False, "attempts": self._reconnect_attempts}

        try:
            ok = bool(connect_fn())
            if ok:
                self._reconnect_attempts = 0
                self._consecutive_latency_spikes = 0
                self.total_recoveries += 1
                return {"status": "RECOVERED", "recovered": True, "attempts": 0}
            return {"status": "RECONNECT_FAILED", "recovered": False, "attempts": self._reconnect_attempts}
        except Exception as exc:
            return {
                "status": "RECONNECT_ERROR",
                "recovered": False,
                "attempts": self._reconnect_attempts,
                "error": str(exc),
            }
