"""
backend/agents/analyst_cycle_agent.py — دورة فريق المحللين المجدولة.

يربط الوحدات الأربع التي كانت يتيمة (fx_analyst / equity_analyst /
strategy_planner / risk_manager + ceo_agent) في دورة واحدة مجدولة، ويُسجّل
مخرجاتها في جدول analyst_cycles **للقياس فقط**.

لماذا خيط منفصل: وحدات التحليل تجلب بيانات من الشبكة (Yahoo Finance) بحجب
متزامن، وتشغيلها داخل حلقة الأحداث سيُجمّد حلقة التداول نفسها. لذلك تُنفَّذ
الدورة كاملة في خيط عامل عبر asyncio.to_thread.

ما لا تفعله هذه الدورة: لا تُنفّذ أي صفقة ولا تُعدّل أي إشارة حيّة.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from agents.base_agent import BaseAgent
from config import AGENTS


class AnalystCycleAgent(BaseAgent):
    """دورة مجدولة لفريق المحللين — تسجيل وقياس بلا تنفيذ."""

    def __init__(self, mt5=None):
        super().__init__(
            "AnalystCycle",
            interval_sec=AGENTS.get("analyst_team_interval_min", 60) * 60,
        )
        self.mt5 = mt5
        self.stats.update({
            "cycles": 0,
            "cycles_with_proposal": 0,
            "cycles_failed": 0,
            "last_cycle_id": None,
            "last_proposal": None,
            "last_error": None,
        })

    # ── الدورة ───────────────────────────────────────────────────────

    async def run_cycle(self):
        """تشغيل دورة واحدة في خيط منفصل (لأن جلب البيانات يحجب)."""
        started = time.perf_counter()
        cycle_id = f"CYCLE-{uuid.uuid4().hex[:8]}"
        self.stats["last_cycle_id"] = cycle_id

        try:
            result = await asyncio.to_thread(self._run_cycle_blocking, cycle_id)
        except Exception as exc:
            self.stats["cycles_failed"] += 1
            self.stats["last_error"] = f"{type(exc).__name__}: {exc}"
            logger.error(f"[AnalystCycle] {cycle_id} فشل: {exc}")
            self._persist({"cycle_id": cycle_id, "error": f"{type(exc).__name__}: {exc}"})
            return

        result["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        self.stats["cycles"] += 1
        if result.get("proposal_symbol"):
            self.stats["cycles_with_proposal"] += 1
            self.stats["last_proposal"] = {
                "symbol": result["proposal_symbol"],
                "action": result["proposal_action"],
                "confidence": result["proposal_confidence"],
            }

        logger.info(
            f"[AnalystCycle] {cycle_id} | تقارير FX:{result.get('fx_reports', 0)} "
            f"أسهم:{result.get('equity_reports', 0)} | "
            f"مقترح:{result.get('proposal_symbol') or 'لا شيء'} | "
            f"CEO:{result.get('ceo_decision') or '-'} | "
            f"مخاطر:{result.get('risk_verdict') or '-'} | "
            f"{result['duration_ms']}ms"
        )
        self._persist(result)

    # ── التنفيذ المتزامن (داخل الخيط) ────────────────────────────────

    def _run_cycle_blocking(self, cycle_id: str) -> Dict[str, Any]:
        """
        سلسلة الفريق كما صُمّمت:
        تقارير FX/أسهم → المخطط (مقترح) → المدير التنفيذي (قرار) → المخاطر (حكم).
        """
        result: Dict[str, Any] = {
            "cycle_id": cycle_id,
            "fx_reports": 0,
            "equity_reports": 0,
            "error": None,
        }

        from core.llm_router import LLMRouter
        from institutional.fx_analyst import FXAnalystAgent
        from institutional.equity_analyst import EquityAnalystAgent
        from institutional.strategy_planner import StrategyPlannerAgent
        from institutional.ceo_agent import CEOAgent
        from institutional.risk_manager import RiskManagerAgent

        router = LLMRouter()
        portfolio = self._portfolio_summary()
        provider = "none"

        async def chain():
            nonlocal provider

            fx_agent = FXAnalystAgent(router)
            fx_reports = await fx_agent.analyze(cycle_id=cycle_id)
            result["fx_reports"] = len(fx_reports or [])
            provider = getattr(fx_agent, "last_provider", "none")

            equity_reports = []
            try:
                equity_reports = await EquityAnalystAgent(router).analyze(cycle_id=cycle_id)
            except Exception as exc:
                logger.warning(f"[AnalystCycle] قسم الأسهم تخطّى: {exc}")
            result["equity_reports"] = len(equity_reports or [])
            result["equity_reports_data"] = equity_reports or []

            if not fx_reports and not equity_reports:
                result["note"] = "لا تقارير محللين صالحة في هذه الدورة"
                return

            planner = StrategyPlannerAgent(router)
            proposal = None
            if fx_reports:
                proposal = await planner.generate_forex_strategy(
                    fx_reports, portfolio, cycle_id=cycle_id
                )
            elif equity_reports:
                proposal = await planner.generate_equity_strategy(
                    equity_reports, portfolio, cycle_id=cycle_id
                )

            # لا مقترح = لا قرار (غياب مزوّد LLM أو HOLD) — نُسجّل ولا نختلق
            if proposal is None:
                result["note"] = (
                    "لا مقترح: المخطط يتطلّب مزوّد LLM متاحاً "
                    "(التقارير التحليلية الحتمية مسجَّلة أعلاه)"
                )
                return

            result.update({
                "proposal_symbol":     proposal.symbol,
                "proposal_action":     str(proposal.action),
                "proposal_confidence": float(proposal.confidence or 0.0),
                "proposal_entry":      float(proposal.entry_price or 0.0),
                "proposal_sl":         float(proposal.stop_loss) if proposal.stop_loss else None,
                "proposal_tp":         float(proposal.take_profit) if proposal.take_profit else None,
                "proposal_lot_type":   proposal.lot_type,
            })

            reports = fx_reports or equity_reports
            decision = await CEOAgent(router).review_strategy(
                proposal, reports, portfolio, cycle_id=cycle_id
            )
            result.update({
                "ceo_decision":  decision.decision,
                "ceo_reasoning": (decision.reasoning or "")[:2000],
                "ceo_provider":  decision.llm_provider,
            })

            # مدير المخاطر هو الحارس النهائي (لا يتجاوزه المدير التنفيذي)
            verdict = await RiskManagerAgent(router).evaluate(proposal, portfolio, cycle_id=cycle_id)
            result.update({
                "risk_verdict":    verdict.verdict,
                "risk_score":      float(verdict.risk_score or 0.0),
                "risk_violations": "; ".join(verdict.rule_violations or []),
            })

        try:
            asyncio.run(chain())
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            logger.error(f"[AnalystCycle] سلسلة الفريق فشلت: {exc}")

        result["llm_provider"] = provider
        return result

    def _portfolio_summary(self) -> Dict[str, Any]:
        """ملخّص المحفظة الحقيقي من MT5 مع قيم افتراضية آمنة."""
        summary: Dict[str, Any] = {
            "balance": 0.0,
            "equity": 0.0,
            "open_positions": 0,
            "drawdown": 0.0,
            "free_margin": 0.0,
        }
        if self.mt5 is None:
            return summary
        try:
            account = self.mt5.get_account() or {}
            summary.update({
                "balance": float(account.get("balance") or 0.0),
                "equity": float(account.get("equity") or 0.0),
                "free_margin": float(account.get("free_margin") or 0.0),
            })
            positions = self.mt5.get_open_positions() or []
            summary["open_positions"] = len(positions)
        except Exception as exc:
            logger.warning(f"[AnalystCycle] تعذّر قراءة حالة الحساب: {exc}")
        return summary

    # ── التسجيل (لا يُسقط الدورة عند الفشل) ──────────────────────────

    def _persist(self, result: Dict[str, Any]) -> None:
        try:
            from models.database import SessionLocal, AnalystCycle

            db = SessionLocal()
            try:
                db.add(AnalystCycle(
                    cycle_id=result.get("cycle_id"),
                    fx_reports=result.get("fx_reports", 0),
                    equity_reports=result.get("equity_reports", 0),
                    duration_ms=result.get("duration_ms"),
                    proposal_symbol=result.get("proposal_symbol"),
                    proposal_action=result.get("proposal_action"),
                    proposal_confidence=result.get("proposal_confidence"),
                    proposal_entry=result.get("proposal_entry"),
                    proposal_sl=result.get("proposal_sl"),
                    proposal_tp=result.get("proposal_tp"),
                    proposal_lot_type=result.get("proposal_lot_type"),
                    ceo_decision=result.get("ceo_decision"),
                    ceo_reasoning=result.get("ceo_reasoning") or result.get("note"),
                    ceo_provider=result.get("ceo_provider"),
                    risk_verdict=result.get("risk_verdict"),
                    risk_score=result.get("risk_score"),
                    risk_violations=result.get("risk_violations"),
                    llm_provider=result.get("llm_provider"),
                    error=result.get("error"),
                    created_at=datetime.utcnow(),
                ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning(f"[AnalystCycle] تعذّر تسجيل الدورة: {exc}")
