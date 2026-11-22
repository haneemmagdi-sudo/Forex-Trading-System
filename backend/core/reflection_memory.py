"""
============================================================
reflection_memory.py — قارئ ذاكرة التأمّل النشط (2026)
============================================================
يحوّل جدول `agent_reflections` من ذاكرة «للكتابة فقط» إلى طبقة قرار نشطة
تُستشار قبل الدخول في كل من:
  - MarketAnalystAgent (تشديد عتبة الثقة أو التبريد المؤقت للزوج/النظام)
  - OmegaRiskGovernor  (رفع عتبة القبول الديناميكية أو حجب مؤقت)

يعمل مباشرة على SQLite (backend/trading.db) بدون اعتماد ثقيل على ORM
مع كاش قصير الأمد (30 ثانية) يُلغى فوراً عند إغلاق أي صفقة جديدة.
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "trading.db"


@dataclass
class ReflectionAdvisory:
    symbol: str
    regime: str
    sample_count: int = 0
    recent_losses: int = 0
    consecutive_losses: int = 0
    win_rate: float = 0.50
    net_pnl: float = 0.0
    veto_saved_losses: int = 0
    confidence_penalty: float = 0.0   # نقاط مئوية تُضاف لعتبة MarketAnalyst (0 -> 15)
    threshold_penalty: float = 0.0    # زيادة تُضاف لعتبة OmegaRiskGovernor (0.0 -> 0.08)
    temporary_cooldown: bool = False  # حظر مؤقت عند نزيف متكرر في نفس (الزوج، النظام)
    summary: str = "no_reflection_penalty"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReflectionMemoryReader:
    """
    يقرأ الدروس المستخلصة من `agent_reflections` ويحوّلها إلى توصية رقمية منضبطة
    لكل ثنائي (symbol, fsm_regime).
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        lookback_days: int = 14,
        min_samples: int = 4,
        cooldown_consecutive_losses: int = 4,
        max_conf_penalty: float = 15.0,
        max_omega_penalty: float = 0.08,
        cache_ttl_sec: float = 30.0,
    ):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.lookback_days = max(1, int(lookback_days))
        self.min_samples = max(2, int(min_samples))
        self.cooldown_consecutive_losses = max(2, int(cooldown_consecutive_losses))
        self.max_conf_penalty = float(max_conf_penalty)
        self.max_omega_penalty = float(max_omega_penalty)
        self.cache_ttl_sec = max(0.0, float(cache_ttl_sec))
        self._cache: Dict[Tuple[str, str], Tuple[float, ReflectionAdvisory]] = {}

    def invalidate(self) -> None:
        """إفراغ الكاش فوراً عند إغلاق صفقة جديدة."""
        self._cache.clear()

    def _fetch_rows(self, symbol: str, regime: str, max_rows: int = 30) -> List[Tuple[Any, ...]]:
        if not self.db_path.exists():
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=2.0)
            cur = conn.execute(
                """
                SELECT outcome, outcome_pnl, council_would_block, created_at
                FROM agent_reflections
                WHERE symbol = ?
                  AND fsm_regime = ?
                  AND (created_at IS NULL OR replace(replace(created_at, 'T', ' '), 'Z', '') >= ?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (symbol, regime, cutoff, int(max_rows)),
            )
            return cur.fetchall()
        except sqlite3.OperationalError:
            # الجدول لم يُنشأ بعد
            return []
        except Exception:
            return []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def _is_within_hours(ts_val: Any, hours: float = 48.0) -> bool:
        if not ts_val:
            return True
        try:
            dt = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() <= (hours * 3600.0)
        except Exception:
            return True

    def evaluate_from_rows(
        self, symbol: str, regime: str, rows: List[Tuple[Any, ...]]
    ) -> ReflectionAdvisory:
        """
        تحليل حتمي لقائمة صفوف (outcome, outcome_pnl, council_would_block, created_at)
        مرتّبة من الأحدث للأقدم.
        """
        if not rows:
            return ReflectionAdvisory(symbol=symbol, regime=regime)

        n = len(rows)
        losses = sum(1 for r in rows if str(r[0]).upper() == "LOSS")
        wins = sum(1 for r in rows if str(r[0]).upper() == "WIN")
        net_pnl = round(sum(float(r[1] or 0.0) for r in rows), 2)
        veto_saved = sum(1 for r in rows if str(r[0]).upper() == "LOSS" and bool(r[2]))
        win_rate = round(wins / n, 4) if n > 0 else 0.5

        # حساب الخسائر المتتالية الأحدث (بدءاً من الصف 0)
        consec_losses = 0
        recent_consec_within_48h = 0
        for r in rows:
            if str(r[0]).upper() == "LOSS":
                consec_losses += 1
                if self._is_within_hours(r[3], hours=48.0):
                    recent_consec_within_48h += 1
            else:
                break

        conf_pen = 0.0
        omega_pen = 0.0
        cooldown = False
        reasons: List[str] = []

        if consec_losses >= self.cooldown_consecutive_losses and recent_consec_within_48h >= self.cooldown_consecutive_losses and net_pnl < 0:
            cooldown = True
            conf_pen = self.max_conf_penalty
            omega_pen = self.max_omega_penalty
            reasons.append(f"COOLDOWN({consec_losses} consecutive losses in 48h, PnL=${net_pnl:+.2f})")
        else:
            if n >= self.min_samples and win_rate < 0.40 and net_pnl < 0:
                conf_pen += 5.0
                omega_pen += 0.03
                reasons.append(f"LOW_WR({win_rate:.0%}/{n})")
            if consec_losses >= 3:
                conf_pen += 6.0
                omega_pen += 0.03
                reasons.append(f"STREAK(-{consec_losses})")
            elif consec_losses == 2:
                conf_pen += 3.0
                omega_pen += 0.015
                reasons.append("STREAK(-2)")
            if veto_saved >= 2:
                conf_pen += 3.0
                omega_pen += 0.02
                reasons.append(f"COUNCIL_WOULD_BLOCK({veto_saved})")

        conf_pen = round(min(self.max_conf_penalty, conf_pen), 2)
        omega_pen = round(min(self.max_omega_penalty, omega_pen), 4)
        summary = " | ".join(reasons) if reasons else "healthy_reflection_history"

        return ReflectionAdvisory(
            symbol=symbol,
            regime=regime,
            sample_count=n,
            recent_losses=losses,
            consecutive_losses=consec_losses,
            win_rate=win_rate,
            net_pnl=net_pnl,
            veto_saved_losses=veto_saved,
            confidence_penalty=conf_pen,
            threshold_penalty=omega_pen,
            temporary_cooldown=cooldown,
            summary=summary,
        )

    def evaluate_pair_regime(self, symbol: str, regime: str, max_rows: int = 30) -> ReflectionAdvisory:
        key = (symbol, regime)
        now = time.monotonic()
        if self.cache_ttl_sec > 0 and key in self._cache:
            ts, cached = self._cache[key]
            if (now - ts) < self.cache_ttl_sec:
                return cached
        rows = self._fetch_rows(symbol, regime, max_rows=max_rows)
        advisory = self.evaluate_from_rows(symbol, regime, rows)
        if self.cache_ttl_sec > 0:
            self._cache[key] = (now, advisory)
        return advisory
