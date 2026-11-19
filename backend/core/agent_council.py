"""
backend/core/agent_council.py — Shadow Agent Council (مجلس الوكلاء في وضع الظل)
=============================================================================

يشغّل طبقة الوكلاء المؤسسية على كل إشارة دخول **مرشّحة**، ويسجّل حكمها مقابل
القرار الحي — **بلا أي تأثير على التنفيذ**. الغرض قياس إضافة الوكلاء بالبيانات
قبل السماح لهم بفلترة الصفقات فعلاً.

ما يعمل هنا فعلاً (لا شيء مُلفَّق):
  1. اللوحة المشتركة (QuantumBlackboard) مع منتجين حقيقيين فقط:
       - random_forest : احتمال الربح من النموذج المُدرَّب (ml_model.pkl)
       - sentiment     : مشاعر الأخبار الحقيقية من NewsAgent
     وغيابهما مُعلَن: timesfm و dqn بلا مُنتِج حقيقي (لا أوزان مُدرَّبة)،
     فيظهران في missing ويُحسب النصاب على المتاح فقط.
  2. محرّك الإجماع (ConsensusEngine) يصدر حُكماً مرجّحاً بمجاميع الأوزان.
  3. الجسر المؤسسي (HMM + Order Flow + MAD) يصدر قراراً مستقلاً بمهلة <5ms
     وحسابات محلية بالكامل (لا اتصال شبكي).

أي خطأ داخل المجلس لا يُسمح له بالتأثير على التداول: كل شيء محاط بـ try/except
ويُعاد dict بحالة صريحة.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("core.agent_council")

# استعلام الدليل: صفقات ظل مربوطة بصفقات مغلقة نتيجتها معروفة
_EVIDENCE_SQL = """
    SELECT sd.council_aligned, sd.council_would_block, sd.consensus_action,
           sd.bridge_approved, sd.bridge_stage, sd.ml_prob,
           t.profit_usd, t.symbol, t.fsm_regime
    FROM shadow_decisions sd
    JOIN signals s ON s.id = sd.signal_id
    JOIN trades  t ON t.ticket = s.trade_ticket
    WHERE t.status = 'CLOSED' AND t.profit_usd IS NOT NULL
    ORDER BY sd.id DESC
    LIMIT :lim
"""

_GATE_CACHE_SECONDS = 300.0

# ثقة مشاعر الأخبار: قيمة مسبقة محافظة ومقصودة (ليست مُتعلَّمة).
# التصنيف القادم من NewsAgent اتجاهي فقط (BULLISH/BEARISH/NEUTRAL) بلا قوة،
# فلا يجوز اختراع رقم مضلِّل — نُعلنها كثابت موثّق.
SENTIMENT_CONFIDENCE = 0.6

MAX_SIGNAL_AGE_SECONDS = 120


class ShadowCouncil:
    """مجلس الوكلاء في وضع الظل — يجمع اللوحة والإجماع والجسر المؤسسي."""

    def __init__(self) -> None:
        self._boards: Dict[str, Any] = {}
        self._engine = None
        self._bridge = None
        self._bridge_error: Optional[str] = None
        self._bridge_attempted = False
        self._predictor: Optional[Callable[[List[float]], float]] = None
        self._gate: Tuple[float, bool, str] = (0.0, False, "not evaluated")

        self.stats: Dict[str, Any] = {
            "evaluations": 0,
            "errors": 0,
            "consensus_available": 0,
            "bridge_available": 0,
            "aligned": 0,
            "would_block": 0,
            "last_verdict": None,
            "last_error": None,
        }

    # ── wiring ───────────────────────────────────────────────────────

    def set_predictor(self, predictor: Optional[Callable[[List[float]], float]]) -> None:
        """توصيل دالة تنبؤ النموذج المُدرَّب (LearningAgent.predict)."""
        self._predictor = predictor
        logger.info(
            "[ShadowCouncil] ML predictor %s",
            "wired" if predictor else "NOT wired (random_forest producer will stay silent)",
        )

    def _get_engine(self):
        if self._engine is None:
            from institutional.consensus_engine import ConsensusEngine

            self._engine = ConsensusEngine()
        return self._engine

    def _get_bridge(self):
        """تهيئة كسولة للجسر المؤسسي مع تسجيل سبب الفشل بدل إخفائه."""
        if self._bridge is None and not self._bridge_attempted:
            self._bridge_attempted = True
            try:
                from core.execution_bridge import InstitutionalExecutionBridge

                self._bridge = InstitutionalExecutionBridge()
                logger.info("[ShadowCouncil] Institutional bridge ready (HMM + order flow + MAD)")
            except Exception as exc:
                self._bridge_error = f"{type(exc).__name__}: {exc}"
                logger.warning("[ShadowCouncil] Institutional bridge unavailable: %s", exc)
        return self._bridge

    def _board(self, symbol: str):
        if symbol not in self._boards:
            from institutional.blackboard import QuantumBlackboard

            self._boards[symbol] = QuantumBlackboard(name=f"shadow_{symbol}")
        return self._boards[symbol]

    # ── producers ────────────────────────────────────────────────────

    @staticmethod
    def sanitize_series(price_series: Dict[str, list]) -> Dict[str, list]:
        """
        حماية طبقات الجسر من فجوة الحجم: مزوّدو البيانات المجانية يعطون حجماً
        صفرياً لأزواج الفوركس، فينهار حساب CVD. نستبدل الحجم غير الصالح بوسيط
        ثابت محايد — نفس العُرف المستخدم في مسار الـ webhook
        (volumes=[100.0] * n) — فيبقى قياس الطبقات ممكناً بدل تعطّله.
        """
        series = dict(price_series or {})
        closes = series.get("closes") or []
        volumes = [float(v or 0.0) for v in (series.get("volumes") or [])]
        if not volumes or all(v <= 0 for v in volumes) or len(volumes) != len(closes):
            series["volumes"] = [100.0] * len(closes)
        return series

    def _post_ml_signal(self, board, direction: str, features: List[float]) -> Optional[float]:
        """
        منتج النموذج المُدرَّب: احتمال الربح P(win).
        النموذج لا يعرف الاتجاه، لذا **يؤيّد** اتجاه التصويت فقط عندما يكون
        الاحتمال أعلى من 0.5، وإلا يمتنع (HOLD). لا نختلق اتجاهاً معاكساً.
        """
        if self._predictor is None:
            return None
        try:
            prob = float(self._predictor(features))
        except Exception as exc:
            logger.debug("[ShadowCouncil] ML predictor failed: %s", exc)
            return None

        from institutional.blackboard import SignalDirection, SignalPayload

        if prob >= 0.5:
            board.post_signal(SignalPayload(
                agent_id="random_forest",
                signal_direction=SignalDirection(direction),
                confidence_score=min(1.0, 2.0 * (prob - 0.5)),
            ))
        else:
            board.post_signal(SignalPayload(
                agent_id="random_forest",
                signal_direction=SignalDirection.HOLD,
                confidence_score=0.0,
            ))
        return prob

    def _post_sentiment_signal(self, board, news_sentiment: Optional[str]) -> None:
        """منتج مشاعر الأخبار: اتجاهي فقط، بثقة ثابتة موثّقة."""
        if not news_sentiment:
            return
        text = str(news_sentiment).upper()
        if "BULL" in text:
            mapped, conf = "BUY", SENTIMENT_CONFIDENCE
        elif "BEAR" in text:
            mapped, conf = "SELL", SENTIMENT_CONFIDENCE
        elif "NEUTRAL" in text:
            mapped, conf = "HOLD", 0.0
        else:
            return

        from institutional.blackboard import SignalDirection, SignalPayload

        board.post_signal(SignalPayload(
            agent_id="sentiment",
            signal_direction=SignalDirection(mapped),
            confidence_score=conf,
        ))

    # ── main entry point ─────────────────────────────────────────────

    def evaluate(
        self,
        symbol: str,
        direction: str,
        vote_confidence: Optional[float],
        fsm_regime: Optional[str],
        features: List[float],
        price_series: Dict[str, list],
        technical_indicators: Dict[str, float],
        news_sentiment: Optional[str] = None,
        signal_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        تقييم إشارة مرشّحة. يُرجع دائماً dict (لا يرفع استثناءً أبداً).
        """
        verdict: Dict[str, Any] = {
            "available": False,
            "signal_id": signal_id,
            "symbol": symbol,
            "live_direction": direction,
            "live_confidence": vote_confidence,
            "fsm_regime": fsm_regime,
            "news_sentiment": news_sentiment,
            "ml_prob": None,
            "consensus_action": None,
            "consensus_score": None,
            "consensus_active": None,
            "consensus_missing": None,
            "consensus_partial": None,
            "bridge_approved": None,
            "bridge_stage": None,
            "bridge_confidence": None,
            "bridge_regime": None,
            "bridge_absorption": None,
            "bridge_latency_ms": None,
            "council_aligned": None,
            "council_would_block": None,
            "error": None,
        }

        self.stats["evaluations"] += 1
        try:
            board = self._board(symbol)
            board.invalidate_stale_signals(max_age_seconds=MAX_SIGNAL_AGE_SECONDS)

            verdict["ml_prob"] = self._post_ml_signal(board, direction, features)
            self._post_sentiment_signal(board, news_sentiment)

            # ── محرّك الإجماع ──
            try:
                consensus = self._get_engine().evaluate(board)
                verdict["consensus_action"] = consensus.action.value
                verdict["consensus_score"] = float(consensus.aggregated_score)
                verdict["consensus_active"] = int(consensus.active_agent_count)
                verdict["consensus_missing"] = ",".join(consensus.missing_agents) or None
                verdict["consensus_partial"] = bool(consensus.is_partial_quorum)
                self.stats["consensus_available"] += 1
            except Exception as exc:
                verdict["error"] = f"consensus: {type(exc).__name__}: {exc}"
                logger.warning("[ShadowCouncil] consensus failed for %s: %s", symbol, exc)

            # ── الجسر المؤسسي (HMM + Order Flow + MAD) ──
            bridge = self._get_bridge()
            if bridge is not None:
                try:
                    receipt = bridge.process_entry_candidate(
                        symbol=symbol,
                        proposed_action=direction,
                        price_series=self.sanitize_series(price_series),
                        technical_indicators=technical_indicators,
                    )
                    verdict["bridge_approved"] = bool(receipt.approved)
                    verdict["bridge_stage"] = receipt.rejection_stage
                    verdict["bridge_confidence"] = receipt.consensus_confidence
                    verdict["bridge_latency_ms"] = receipt.latency_ms
                    details = receipt.details or {}
                    verdict["bridge_regime"] = details.get("regime")
                    verdict["bridge_absorption"] = details.get("absorption")
                    self.stats["bridge_available"] += 1
                except Exception as exc:
                    verdict["error"] = (verdict["error"] or "") + f" bridge: {type(exc).__name__}: {exc}"
                    logger.warning("[ShadowCouncil] bridge failed for %s: %s", symbol, exc)

            # ── الخلاصة: هل يؤيّد المجلس هذه الصفقة؟ ──
            if verdict["bridge_approved"] is not None:
                verdict["available"] = True
                aligned = (
                    verdict["consensus_action"] == direction
                    and verdict["bridge_approved"] is True
                )
                verdict["council_aligned"] = aligned
                verdict["council_would_block"] = not aligned
                self.stats["aligned" if aligned else "would_block"] += 1

            self.stats["last_verdict"] = {
                "symbol": symbol,
                "direction": direction,
                "consensus": verdict["consensus_action"],
                "bridge": verdict["bridge_stage"] or "APPROVED",
                "aligned": verdict["council_aligned"],
            }
        except Exception as exc:  # لا يجوز أن يصل أي خطأ لمسار التداول
            self.stats["errors"] += 1
            self.stats["last_error"] = f"{type(exc).__name__}: {exc}"
            verdict["error"] = f"council: {type(exc).__name__}: {exc}"
            logger.error("[ShadowCouncil] evaluation failed for %s: %s", symbol, exc)

        self._persist(verdict)
        return verdict

    # ── persistence (best effort — never blocks trading) ─────────────

    def _persist(self, verdict: Dict[str, Any]) -> None:
        try:
            from models.database import SessionLocal, ShadowDecision

            db = SessionLocal()
            try:
                db.add(ShadowDecision(
                    signal_id=verdict.get("signal_id"),
                    symbol=verdict.get("symbol"),
                    fsm_regime=verdict.get("fsm_regime"),
                    live_direction=verdict.get("live_direction"),
                    live_confidence=verdict.get("live_confidence"),
                    ml_prob=verdict.get("ml_prob"),
                    news_sentiment=verdict.get("news_sentiment"),
                    consensus_action=verdict.get("consensus_action"),
                    consensus_score=verdict.get("consensus_score"),
                    consensus_active=verdict.get("consensus_active"),
                    consensus_missing=verdict.get("consensus_missing"),
                    consensus_partial=verdict.get("consensus_partial"),
                    bridge_approved=verdict.get("bridge_approved"),
                    bridge_stage=verdict.get("bridge_stage"),
                    bridge_confidence=verdict.get("bridge_confidence"),
                    bridge_regime=verdict.get("bridge_regime"),
                    bridge_absorption=verdict.get("bridge_absorption"),
                    bridge_latency_ms=verdict.get("bridge_latency_ms"),
                    council_aligned=verdict.get("council_aligned"),
                    council_would_block=verdict.get("council_would_block"),
                    error=verdict.get("error"),
                    created_at=datetime.utcnow(),
                ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            # فشل التسجيل لا يُسقط القياس كاملاً ولا يمس التداول
            logger.warning("[ShadowCouncil] could not persist verdict: %s", exc)

    # ── evidence: الأساس الرقمي للتقارير ولتمكين الفلترة ─────────────
    @staticmethod
    def collect_evidence(limit: int = 2000) -> Dict[str, Any]:
        """
        الدليل الرقمي من قاعدة البيانات: صفقات ظل مربوطة بنتائج معروفة، مقسّمة
        إلى ما أيّده المجلس وما كان سيمنعه، مع صافي أثر الفيتو.
        يُرجع available=False مع السبب عند تعذّر القراءة (لا يرفع استثناءً).
        """
        try:
            from sqlalchemy import text
            from models.database import SessionLocal

            db = SessionLocal()
            try:
                rows = [
                    dict(row._mapping)
                    for row in db.execute(text(_EVIDENCE_SQL), {"lim": limit}).fetchall()
                ]
            finally:
                db.close()
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

        def cohort(items: List[Dict[str, Any]]) -> Dict[str, Any]:
            if not items:
                return {"trades": 0, "win_rate": None, "net_pnl": 0.0, "avg_pnl": None}
            pnl = [r["profit_usd"] for r in items]
            wins = [p for p in pnl if p > 0]
            return {
                "trades": len(items),
                "win_rate": round(100.0 * len(wins) / len(items), 1),
                "net_pnl": round(sum(pnl), 2),
                "avg_pnl": round(sum(pnl) / len(items), 3),
            }

        blocked = [r for r in rows if r["council_would_block"]]
        endorsed = [r for r in rows if r["council_aligned"]]
        blocked_pnl = [r["profit_usd"] for r in blocked]

        reasons: Dict[str, int] = {}
        for row in blocked:
            key = row["bridge_stage"] or f"consensus:{row['consensus_action']}"
            reasons[key] = reasons.get(key, 0) + 1

        high_ml = [r for r in rows if (r["ml_prob"] or 0) >= 0.5]
        low_ml = [r for r in rows if r["ml_prob"] is not None and r["ml_prob"] < 0.5]

        return {
            "available": True,
            "linked_trades": len(rows),
            "agreement_rate": (round(100.0 * len(endorsed) / len(rows), 1) if rows else None),
            "cohorts": {
                "council_endorsed": cohort(endorsed),
                "council_would_block": cohort(blocked),
            },
            "veto_net_effect_usd": (round(-sum(blocked_pnl), 2) if blocked else None),
            "losses_avoided_usd": round(-sum(p for p in blocked_pnl if p < 0), 2),
            "wins_missed_usd": round(sum(p for p in blocked_pnl if p > 0), 2),
            "block_reasons": reasons,
            "ml_quality": {"ml_prob>=0.5": cohort(high_ml), "ml_prob<0.5": cohort(low_ml)},
        }

    # ── enablement gate: الفلترة لا تُفعَّل بلا دليل ─────────────────
    def _filter_decision(self) -> Tuple[bool, str]:
        """
        بوابة التمكين: (مسموح بالفلترة، السبب).
        لا تُفعَّل الفلترة إلا إذا كان الوضع enforce **وكان الدليل كافياً
        ويُظهر أن الفيتو يضيف قيمة صافية بالموجب. وإلا تبقى shadow.
        """
        from config import COUNCIL

        mode = (os.getenv("COUNCIL_MODE", "") or COUNCIL.get("mode", "shadow")).strip().lower()
        if mode != "enforce":
            return False, f"mode={mode} (الفلترة معطّلة)"

        evidence = self.collect_evidence()
        if not evidence.get("available"):
            return False, f"تعذّر جمع الدليل: {evidence.get('error')}"

        linked = evidence.get("linked_trades") or 0
        required = COUNCIL.get("min_evidence_trades", 40)
        if linked < required:
            return False, f"دليل غير كافٍ: {linked} صفقة مربوطة < {required}"

        edge = evidence.get("veto_net_effect_usd")
        minimum = COUNCIL.get("min_veto_edge_usd", 0.0)
        if edge is None or edge < minimum:
            return False, f"صافي أثر الفيتو {edge} دون الحد {minimum}"

        return True, f"enforce (n={linked}, veto_edge={edge})"

    def filter_enabled(self) -> bool:
        """هل يُسمح للمجلس بمنع صفقة فعلاً؟ (تُخزَّن النتيجة 5 دقائق)"""
        stamp, allowed, reason = self._gate
        if time.time() - stamp > _GATE_CACHE_SECONDS:
            allowed, reason = self._filter_decision()
            self._gate = (time.time(), allowed, reason)
            logger.info("[ShadowCouncil] filter gate: %s", reason)
        return allowed

    def gate_reason(self) -> str:
        """سبب قرار البوابة (للعرض في اللوج وحالة الـ API)."""
        self.filter_enabled()
        return self._gate[2]

    # ── status ───────────────────────────────────────────────────────

    def status(self, probe: bool = False) -> Dict[str, Any]:
        """
        حالة حقيقية للمجلس (بدل ادعاءات ACTIVE الثابتة).
        probe=True يحاول تهيئة الجسر فعلاً، حتى يعكس التقرير **القدرة** لا
        مجرّد الحالة العابرة قبل أول تقييم.
        """
        if probe:
            self._get_engine()
            self._get_bridge()

        producers = {"random_forest": self._predictor is not None, "sentiment": True}
        missing = [aid for aid in ("timesfm", "dqn") if aid not in producers]
        return {
            "mode": "shadow",
            "execution_impact": "none",
            "filter": {
                "enabled": self.filter_enabled(),
                "reason": self._gate[2],
            },
            "producers": producers,
            "producers_missing": missing,
            "missing_reason": "no trained weights (timesfm/dqn have no persisted models)",
            "engine_ready": self._engine is not None,
            "bridge_ready": self._bridge is not None,
            "bridge_error": self._bridge_error,
            "stats": dict(self.stats),
        }


_council: Optional[ShadowCouncil] = None


def get_council() -> ShadowCouncil:
    """المجلس ككائن وحيد على مستوى العملية (نمط get_bus)."""
    global _council
    if _council is None:
        _council = ShadowCouncil()
    return _council
