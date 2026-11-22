"""
============================================================
champion_challenger.py — حوكمة تعديل السلوك والأوزان (2026)
============================================================
يوفر طبقتين حتميتين لحماية التعلم المستمر من الانجراف والتذبذب:
  1. ExponentialAttributionBandit:
     حساب تعديلات مضاعِفات الأوزان بتقليص إحصائي (Empirical Bayes Shrinkage)
     نحو 1.0 لمنع الإفراط في التخصيص عند قلة العينات.
  2. ChampionChallengerManager:
     يحفظ لقطة الأوزان المستقرة (Champion) ويختبر أي أوزان مقترحة (Challenger)
     خلال نافذة اختبار حية (Probation Window):
       - ترقية تلقائية (PROMOTED) إذا تفوّق أو حافظ على التوقع الإيجابي.
       - تراجع تلقائي فوري (AUTO_ROLLBACK) عند 4 خسائر متتالية أو تدهور الأداء
         في نهاية النافذة، مع فترة تهدئة قبل السماح بأي تعديل جديد.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


DEFAULT_NEUTRAL_WEIGHTS: Dict[str, float] = {
    "ema": 1.0, "ha": 1.0, "macd": 1.0, "rsi": 1.0,
    "adx": 1.0, "ichi": 1.0, "smc": 1.0, "momentum": 1.0, "st": 1.0,
}


@dataclass
class ChampionSnapshot:
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_NEUTRAL_WEIGHTS))
    baseline_win_rate: float = 0.50       # 0.0 -> 1.0
    baseline_expectancy: float = 0.0      # متوسط الربح بالدولار لكل صفقة
    version: int = 1
    activated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ChallengerState:
    weights: Dict[str, float]
    proposed_at_utc: str
    trade_profits: List[float] = field(default_factory=list)
    consecutive_losses: int = 0


class ExponentialAttributionBandit:
    """
    يحسب مضاعِفات أوزان التصويت بسلاسة مع تقليص بايزي (Shrinkage) نحو 1.0
    بحيث لا تتغير الأوزان بعنف عند وجود عدد قليل من الصفقات.
    """

    REGIME_INDICATOR_MAP: Dict[str, Tuple[str, ...]] = {
        "STRONG_TREND":   ("ema", "ha", "adx", "st"),
        "SLOW_TREND":     ("ichi", "macd", "ema"),
        "LOW_VOL_RANGE":  ("smc", "rsi", "momentum"),
        "HIGH_VOL_RANGE": ("smc", "rsi"),
        "CHAOS":          ("adx", "smc"),
    }

    @classmethod
    def compute_multipliers(
        cls,
        analysis: dict,
        prior_strength: float = 8.0,
        learning_rate: float = 0.35,
        lo: float = 0.3,
        hi: float = 3.0,
    ) -> Dict[str, float]:
        """
        يشتق مضاعِفات أوزان منضبطة من إحصاءات الـ Regimes مع تقليص العينة الصغيرة:
        shrunk_wr = (wins + prior_strength * 0.5) / (trades + prior_strength)
        edge = shrunk_wr - 0.5
        """
        regime_stats = analysis.get("regime_stats", {}) or {}
        if not regime_stats:
            return {}

        accum: Dict[str, List[float]] = {k: [] for k in DEFAULT_NEUTRAL_WEIGHTS}
        for regime, st in regime_stats.items():
            trades = int(st.get("trades", 0) or 0)
            if trades <= 0:
                continue
            wins = int(st.get("wins", 0) or 0)
            profit = float(st.get("profit", 0.0) or 0.0)
            # Empirical Bayes shrinkage toward neutral 50% win rate
            shrunk_wr = (wins + prior_strength * 0.5) / (trades + prior_strength)
            edge = shrunk_wr - 0.50
            # إشارة الربح الصافي تخفّف الترقية إن كانت نسبة الفوز عالية لكن الربح سالب
            if profit < 0 and edge > 0:
                edge *= 0.25

            members = cls.REGIME_INDICATOR_MAP.get(regime, ())
            for ind in members:
                accum[ind].append(edge)

        multipliers: Dict[str, float] = {}
        for ind, edges in accum.items():
            if not edges:
                continue
            avg_edge = sum(edges) / len(edges)
            # تحويل أسي منضبط حول 1.0: exp(learning_rate * 4.0 * avg_edge)
            raw_mult = math.exp(learning_rate * 4.0 * avg_edge)
            multipliers[ind] = round(max(lo, min(hi, raw_mult)), 4)

        # تعزيز ADX عند ارتفاع دقة الإشارات عالية الثقة (مع تقليص محافظ)
        hcwr = float(analysis.get("high_conf_wr", 0.0) or 0.0)
        if hcwr > 75.0:
            cur_adx = multipliers.get("adx", 1.0)
            multipliers["adx"] = round(max(lo, min(hi, cur_adx * 1.08)), 4)

        return multipliers


class ChampionChallengerManager:
    """
    يدير دورة حياة الأوزان: Champion مستقر مقابل Challenger تحت الاختبار الحي،
    مع تراجع تلقائي فوري (Auto-Rollback) وحفظ ذري على القرص.
    """

    def __init__(
        self,
        state_path: Optional[str] = None,
        probation_trades: int = 10,
        max_consecutive_losses: int = 4,
        max_weight_step: float = 0.25,
        rollback_cooldown_trades: int = 5,
        wr_tolerance: float = 0.05,
    ):
        self.state_path = state_path
        self.probation_trades = max(3, int(probation_trades))
        self.max_consecutive_losses = max(2, int(max_consecutive_losses))
        self.max_weight_step = max(0.05, float(max_weight_step))
        self.rollback_cooldown_trades = max(0, int(rollback_cooldown_trades))
        self.wr_tolerance = float(wr_tolerance)

        self.champion = ChampionSnapshot()
        self.challenger: Optional[ChallengerState] = None
        self.cooldown_remaining: int = 0
        self.promotions_count: int = 0
        self.rollbacks_count: int = 0
        self.last_event: str = "INIT"

        if self.state_path:
            self._load_state()

    @property
    def active_weights(self) -> Dict[str, float]:
        if self.challenger is not None:
            return dict(self.challenger.weights)
        return dict(self.champion.weights)

    def _clamp_step(self, candidate: Dict[str, float]) -> Dict[str, float]:
        """يقيّد كل تغيير في الوزن بخطوة قصوى max_weight_step حول وزن الـ Champion."""
        bounded = dict(self.champion.weights)
        for k, val in candidate.items():
            base = float(self.champion.weights.get(k, 1.0))
            delta = float(val) - base
            clamped_delta = max(-self.max_weight_step, min(self.max_weight_step, delta))
            bounded[k] = round(max(0.3, min(3.0, base + clamped_delta)), 4)
        return bounded

    def propose_challenger(
        self,
        candidate_weights: Dict[str, float],
        current_win_rate: Optional[float] = None,
        current_expectancy: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, float]]:
        """
        يقترح أوزان Challenger جديدة.
        يعيد (accepted, reason, weights_to_apply).
        """
        if not candidate_weights:
            return False, "empty_candidate", self.active_weights
        if self.challenger is not None:
            return False, "challenger_already_in_probation", self.active_weights
        if self.cooldown_remaining > 0:
            return False, f"rollback_cooldown_active ({self.cooldown_remaining} trades left)", self.active_weights

        # تحديث خط الأساس للـ Champion عند أول قياس حقيقي
        if current_win_rate is not None:
            wr_norm = current_win_rate / 100.0 if current_win_rate > 1.0 else float(current_win_rate)
            self.champion.baseline_win_rate = round(max(0.0, min(1.0, wr_norm)), 4)
        if current_expectancy is not None:
            self.champion.baseline_expectancy = round(float(current_expectancy), 4)

        bounded = self._clamp_step(candidate_weights)
        # لا تفتح فترة اختبار إذا لم يتغير أي وزن فعلياً
        max_diff = max(abs(bounded.get(k, 1.0) - self.champion.weights.get(k, 1.0)) for k in bounded)
        if max_diff < 1e-3:
            return False, "no_material_weight_change", self.active_weights

        self.challenger = ChallengerState(
            weights=bounded,
            proposed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self.last_event = "CHALLENGER_STARTED"
        self._save_state()
        return True, "challenger_activated", dict(bounded)

    def record_trade_outcome(self, profit_usd: float) -> Dict[str, object]:
        """
        يسجّل نتيجة صفقة مغلقة ويقيّم Challenger:
          - action: "NONE" | "PROMOTED" | "AUTO_ROLLBACK"
        """
        profit = float(profit_usd)
        if self.challenger is None:
            if self.cooldown_remaining > 0:
                self.cooldown_remaining -= 1
                self._save_state()
            return {"action": "NONE", "reason": "no_active_challenger", "weights": self.active_weights}

        self.challenger.trade_profits.append(profit)
        if profit <= 0.0:
            self.challenger.consecutive_losses += 1
        else:
            self.challenger.consecutive_losses = 0

        # 1. حارس الإيقاف المبكر عند خسائر متتالية
        if self.challenger.consecutive_losses >= self.max_consecutive_losses:
            return self._trigger_rollback(
                f"early_consecutive_losses ({self.challenger.consecutive_losses}>={self.max_consecutive_losses})"
            )

        # 2. تقييم نهاية فترة الاختبار
        n = len(self.challenger.trade_profits)
        if n < self.probation_trades:
            self._save_state()
            return {
                "action": "NONE",
                "reason": f"probation_progress ({n}/{self.probation_trades})",
                "weights": self.active_weights,
            }

        wins = sum(1 for p in self.challenger.trade_profits if p > 0.0)
        chal_wr = wins / n
        chal_exp = sum(self.challenger.trade_profits) / n

        wr_ok = chal_wr >= (self.champion.baseline_win_rate - self.wr_tolerance)
        if self.champion.baseline_expectancy > 0:
            exp_ok = chal_exp >= (self.champion.baseline_expectancy * 0.90) and chal_exp >= 0.0
        else:
            exp_ok = chal_exp >= self.champion.baseline_expectancy

        if wr_ok and exp_ok:
            # ترقية Challenger ليصبح Champion الجديد
            self.champion = ChampionSnapshot(
                weights=dict(self.challenger.weights),
                baseline_win_rate=round(chal_wr, 4),
                baseline_expectancy=round(chal_exp, 4),
                version=self.champion.version + 1,
                activated_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            self.challenger = None
            self.promotions_count += 1
            self.last_event = f"PROMOTED_V{self.champion.version}"
            self._save_state()
            return {
                "action": "PROMOTED",
                "reason": f"challenger_passed (WR={chal_wr:.2%}, Exp=${chal_exp:+.2f})",
                "version": self.champion.version,
                "weights": dict(self.champion.weights),
            }

        return self._trigger_rollback(
            f"probation_degraded (WR={chal_wr:.2%} vs {self.champion.baseline_win_rate:.2%}, "
            f"Exp=${chal_exp:+.2f} vs ${self.champion.baseline_expectancy:+.2f})"
        )

    def _trigger_rollback(self, reason: str) -> Dict[str, object]:
        self.challenger = None
        self.rollbacks_count += 1
        self.cooldown_remaining = self.rollback_cooldown_trades
        self.last_event = f"AUTO_ROLLBACK:{reason}"
        self._save_state()
        return {
            "action": "AUTO_ROLLBACK",
            "reason": reason,
            "version": self.champion.version,
            "weights": dict(self.champion.weights),
        }

    def status_summary(self) -> Dict[str, object]:
        return {
            "champion_version": self.champion.version,
            "challenger_active": self.challenger is not None,
            "challenger_trades": len(self.challenger.trade_profits) if self.challenger else 0,
            "probation_trades": self.probation_trades,
            "cooldown_remaining": self.cooldown_remaining,
            "promotions_count": self.promotions_count,
            "rollbacks_count": self.rollbacks_count,
            "last_event": self.last_event,
        }

    def _save_state(self) -> None:
        if not self.state_path:
            return
        try:
            parent = os.path.dirname(self.state_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            payload = {
                "champion": asdict(self.champion),
                "challenger": asdict(self.challenger) if self.challenger else None,
                "cooldown_remaining": self.cooldown_remaining,
                "promotions_count": self.promotions_count,
                "rollbacks_count": self.rollbacks_count,
                "last_event": self.last_event,
            }
            fd, tmp_path = tempfile.mkstemp(dir=parent or ".", prefix=".tmp_cc_", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.state_path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception:
            pass

    def _load_state(self) -> None:
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "champion" in data and isinstance(data["champion"], dict):
                self.champion = ChampionSnapshot(**data["champion"])
            if data.get("challenger") and isinstance(data["challenger"], dict):
                self.challenger = ChallengerState(**data["challenger"])
            self.cooldown_remaining = int(data.get("cooldown_remaining", 0))
            self.promotions_count = int(data.get("promotions_count", 0))
            self.rollbacks_count = int(data.get("rollbacks_count", 0))
            self.last_event = str(data.get("last_event", "LOADED"))
        except Exception:
            pass
