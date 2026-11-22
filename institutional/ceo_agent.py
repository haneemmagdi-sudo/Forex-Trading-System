"""
CEO Agent â€” strategic overseer of AlphaEdge Capital AI.
Reviews strategy proposals, manages cross-market capital allocation,
approves/rejects/requests revisions on strategies.

HARD CONSTRAINT: CEO CANNOT override the Risk Manager's veto.
This is enforced both via LLM system prompt AND at the MessageBus level.
"""

from __future__ import annotations
import logging
from datetime import datetime

from institutional.base_agent import BaseAgent
from schemas.agents import CEODecision, StrategyProposal
import config as cfg

logger = logging.getLogger("ceo_agent")


class CEOAgent(BaseAgent):
    name = "ceo_agent"
    role_description = (
        "Chief Investment Officer (CIO) of AlphaEdge Capital. "
        "Your mandate is capital preservation and consistent risk-adjusted returns. "
        "You supervise elite analysts and strategists, providing final executive oversight. "
        "You are high-stakes, data-driven, and prioritize institutional-grade reasoning."
    )

    async def review_strategy(
        self,
        strategy: StrategyProposal,
        analyst_reports: list[dict],
        portfolio_summary: dict,
        cycle_id: str = "",
        revision_round: int = 0,
    ) -> CEODecision:
        """
        Review a strategy proposal and make an executive decision.
        Returns: CEODecision with APPROVED, REJECTED, or REVISION_REQUESTED.
        """
        # Build analyst context
        relevant_reports = [
            r for r in analyst_reports
            if r.get("symbol") == strategy.symbol or r.get("pair") == strategy.symbol
        ]
        analyst_context = relevant_reports[0] if relevant_reports else {}

        user_prompt = f"""
You are the CIO of AlphaEdge Capital. Review this high-precision strategy and issue an executive decision.

STRATEGY PROPOSAL:
{strategy.symbol}: {strategy.action} {strategy.quantity} @ {strategy.entry_price}
SL: {strategy.stop_loss} | TP: {strategy.take_profit} | R:R: {strategy.risk_reward_ratio}
Rationale: {strategy.rationale}

MARKET CONTEXT:
Signal: {analyst_context.get('overall_signal', 'N/A')}
Institutional Context: {analyst_context.get('institutional_context', 'N/A')}

PORTFOLIO & RISK:
Balance: ${portfolio_summary.get('balance', 0):.2f} | Drawdown: {portfolio_summary.get('drawdown', 0):.1f}%
Open Count: {portfolio_summary.get('open_positions', 0)}

EXECUTIVE MANDATE:
- Does this setup show reasonable market confluence?
- Is the R:R acceptable for a professional fund? (minimum {cfg.MIN_RISK_REWARD_RATIO})
- APPROVE if the reasoning is logical and data-backed, even if not perfect.
- Only REJECT if there is a fundamental flaw in the setup or market conditions are clearly hostile.
- Request REVISION only if a specific improvement would make the trade significantly better.
- Do NOT over-filter. Consistent trade flow is essential for performance.

Return ONLY valid JSON:
{{
  "decision": "APPROVED or REJECTED or REVISION_REQUESTED",
  "market": "{strategy.asset_class}",
  "reasoning": "Detailed executive reasoning (2-3 sentences)",
  "instructions_to_planner": "<specific guidance if revision needed, else empty>",
  "capital_allocation": {{"equity_pct": 60.0, "forex_pct": 40.0}},
  "confidence_in_strategy": <0.0-1.0>,
  "ceo_notes": "Internal executive notes"
}}
"""
        llm_output = await self.think(user_prompt, cycle_id=cycle_id)

        if llm_output is None:
            # LLM ØºÙŠØ± Ù…ØªØ§Ø­ â€” Ù†ÙˆØ§ÙÙ‚ Ø¨Ø«Ù‚Ø© Ù…Ù†Ø®ÙØ¶Ø© Ø¨Ø¯Ù„ Ù…Ù† Ø§Ù„Ø±ÙØ¶ Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ
            return CEODecision(
                decision="APPROVED",
                market=strategy.asset_class,
                reasoning="LLM unavailable â€” approving with low confidence. Risk Manager is the final guard.",
                revision_round=revision_round,
            )

        decision_str = llm_output.get("decision", "REJECTED")
        if decision_str not in ("APPROVED", "REJECTED", "REVISION_REQUESTED"):
            decision_str = "REJECTED"

        allocation = llm_output.get("capital_allocation", {
            "equity_pct": cfg.EQUITY_ALLOCATION_PCT * 100,
            "forex_pct": cfg.FOREX_ALLOCATION_PCT * 100,
        })

        decision = CEODecision(
            decision=decision_str,
            market=strategy.asset_class,
            reasoning=llm_output.get("reasoning", ""),
            instructions_to_planner=llm_output.get("instructions_to_planner", ""),
            capital_allocation=allocation,
            revision_round=revision_round,
            llm_provider=self.last_provider,
        )

        logger.info(
            f"[CEO] {decision.decision} for {strategy.strategy_id} "
            f"({strategy.asset_class} {strategy.symbol}) "
            f"via {self.last_provider}"
        )
        return decision

    async def review_performance(
        self, portfolio_summary: dict, recent_trades: list[dict], cycle_id: str = ""
    ) -> dict:
        """Periodic CEO performance review â€” adjusts capital allocation strategy."""
        user_prompt = f"""
As CEO, review the company's recent trading performance and provide strategic guidance.

PORTFOLIO SUMMARY:
{portfolio_summary}

RECENT TRADES:
{recent_trades[:5]}

Provide strategic direction:
Return ONLY valid JSON:
{{
  "performance_assessment": "STRONG | ACCEPTABLE | CONCERNING | CRITICAL",
  "recommended_equity_allocation_pct": <float>,
  "recommended_forex_allocation_pct": <float>,
  "strategic_notes": "<2-3 sentence assessment>",
  "action_required": "<any immediate actions needed>"
}}
"""
        result = await self.think(user_prompt, cycle_id=cycle_id)
        return result or {}
