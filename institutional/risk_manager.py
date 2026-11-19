"""
Risk Manager Agent â€” Dual-layer validation.
Updated: Uses Live MT5 Balance instead of STARTING_CAPITAL.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime

from institutional.base_agent import BaseAgent
from schemas.agents import RiskVerdict, StrategyProposal
from schemas.forex import price_to_pips
import config as cfg

logger = logging.getLogger("risk_manager")


class RiskManagerAgent(BaseAgent):
    name = "risk_manager"
    role_description = "Chief Risk Manager with absolute veto power"
    preferred_llm_provider = "groq"

    async def evaluate(self, strategy: StrategyProposal, portfolio_summary: dict, cycle_id: str = "") -> RiskVerdict:
        hard_violations, soft_warnings, hard_veto = self._check_hard_rules(strategy, portfolio_summary)

        if hard_veto:
            verdict = RiskVerdict(
                strategy_id=strategy.strategy_id,
                asset_class=strategy.asset_class,
                verdict="VETOED",
                rule_violations=hard_violations,
                risk_score=10.0,
                veto_reason=f"HARD RULE VIOLATION: {'; '.join(hard_violations)}",
                llm_provider="hard_rules"
            )
            if self.db:
                await self.db.save_risk_verdict(
                    strategy.strategy_id, strategy.asset_class, "VETOED",
                    hard_violations, 10.0, verdict.veto_reason, "hard_rules"
                )
            return verdict

        # Ø£Ø±Ø³Ù„ Ø§Ù„ØªØ­Ø°ÙŠØ±Ø§Øª Ø§Ù„Ø¨Ø³ÙŠØ·Ø© Ù„Ù„Ù€ LLM Ù„Ù„ØªØ­Ù„ÙŠÙ„ ÙˆÙ„ÙŠØ³ Ù„Ù„Ø±ÙØ¶ Ø§Ù„ÙÙˆØ±ÙŠ
        llm_result = await self._llm_risk_analysis(
            strategy, portfolio_summary, soft_warnings, cycle_id
        )
        verdict = self._build_verdict(strategy, hard_violations, soft_warnings, llm_result)

        if self.db:
            await self.db.save_risk_verdict(
                strategy.strategy_id, strategy.asset_class,
                verdict.verdict, verdict.rule_violations,
                verdict.risk_score, verdict.veto_reason, verdict.llm_provider
            )

        if verdict.verdict == "VETOED":
            logger.warning(f"[RISK] VETOED {strategy.strategy_id}: {verdict.veto_reason}")
        else:
            logger.info(f"[RISK] APPROVED {strategy.strategy_id} (risk_score={verdict.risk_score:.1f})")
        return verdict

    def _check_hard_rules(self, strategy: StrategyProposal, portfolio: dict) -> tuple[list[str], list[str], bool]:
        """Returns (hard_violations, soft_warnings, is_hard_vetoed).
        
        HARD violations = immediate veto (critical risk rules).
        SOFT warnings = passed to LLM for consideration (not automatic veto).
        """
        hard_violations = []
        soft_warnings = []

        # Ø§Ù„Ø±ØµÙŠØ¯ Ø§Ù„Ø­ÙŠ Ù…Ù† MT5
        total_balance = portfolio.get("balance", 0)
        if total_balance == 0:
            total_balance = cfg.STARTING_CAPITAL
        open_positions = portfolio.get("open_positions", 0)

        max_risk_usd = total_balance * cfg.MAX_SINGLE_TRADE_RISK_PCT
        actual_risk = strategy.max_capital_at_risk or strategy.max_loss_usd or 0

        # â”€â”€ Ù‚ÙˆØ§Ø¹Ø¯ HARD (Ø±ÙØ¶ ÙÙˆØ±ÙŠ) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # ØªØ¬Ø§ÙˆØ² Ù…Ø®Ø§Ø·Ø±Ø© Ø§Ù„ØµÙÙ‚Ø© Ø¨Ø£ÙƒØ«Ø± Ù…Ù† 2Ã— Ø§Ù„Ø­Ø¯ Ø§Ù„Ù…Ø³Ù…ÙˆØ­
        if actual_risk > max_risk_usd * 2.0:
            hard_violations.append(
                f"Trade risk ${actual_risk:.2f} is 2x the max ${max_risk_usd:.2f} ("
                f"{cfg.MAX_SINGLE_TRADE_RISK_PCT*100:.0f}%) â€” CRITICAL OVER-RISK"
            )
        elif actual_risk > max_risk_usd:
            soft_warnings.append(f"Trade risk ${actual_risk:.2f} slightly exceeds max ${max_risk_usd:.2f}")

        # Ø­Ø¯ Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ù…ÙØªÙˆØ­Ø© Ø§Ù„Ø¥Ø¬Ù…Ø§Ù„ÙŠ
        if open_positions >= cfg.MAX_TOTAL_OPEN_POSITIONS:
            hard_violations.append(
                f"Open positions ({open_positions}) at hard max ({cfg.MAX_TOTAL_OPEN_POSITIONS})"
            )

        # ØªØ¯Ø§ÙˆÙ„ Ù…ÙˆÙ‚ÙˆÙ
        if portfolio.get("trading_halted", False):
            hard_violations.append(f"TRADING HALTED: {portfolio.get('halt_reason', '')}")

        # â”€â”€ Ù‚ÙˆØ§Ø¹Ø¯ SOFT (ØªØ­Ø°ÙŠØ± ÙÙ‚Ø·) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # R:R Ù…Ù†Ø®ÙØ¶
        if strategy.risk_reward_ratio > 0 and strategy.risk_reward_ratio < cfg.MIN_RISK_REWARD_RATIO:
            soft_warnings.append(
                f"R:R {strategy.risk_reward_ratio:.2f} below preferred {cfg.MIN_RISK_REWARD_RATIO} "
                f"(still acceptable if setup is strong)"
            )

        if strategy.asset_class == "EQUITY":
            equity_available = portfolio.get("equity_book", {}).get(
                "available_capital", total_balance * cfg.EQUITY_ALLOCATION_PCT
            )
            max_position_usd = equity_available * cfg.MAX_EQUITY_POSITION_PCT
            position_value = strategy.entry_price * strategy.quantity
            if position_value > max_position_usd * 1.5:  # HARD: > 1.5Ã— Ø§Ù„Ø­Ø¯
                hard_violations.append(f"Position size ${position_value:.2f} far exceeds max ${max_position_usd:.2f}")
            elif position_value > max_position_usd:
                soft_warnings.append(f"Position size ${position_value:.2f} slightly exceeds max ${max_position_usd:.2f}")

            if strategy.stop_loss > 0 and strategy.entry_price > 0:
                stop_pct = abs(strategy.entry_price - strategy.stop_loss) / strategy.entry_price
                if stop_pct > cfg.EQUITY_VOLATILITY_ATR_FILTER * 2:  # HARD: > 2Ã—
                    hard_violations.append(f"SL distance {stop_pct*100:.1f}% far exceeds ATR filter")
                elif stop_pct > cfg.EQUITY_VOLATILITY_ATR_FILTER:
                    soft_warnings.append(f"SL distance {stop_pct*100:.1f}% exceeds ATR filter")

            if portfolio.get("equity_positions", 0) >= cfg.MAX_EQUITY_OPEN_POSITIONS:
                hard_violations.append("Equity positions at hard max")

        elif strategy.asset_class == "FOREX":
            if strategy.quantity > cfg.MAX_LOT_SIZE * 1.5:  # HARD: > 1.5Ã— Ø§Ù„Ø­Ø¯
                hard_violations.append(f"Lot size {strategy.quantity} far exceeds max {cfg.MAX_LOT_SIZE}")
            elif strategy.quantity > cfg.MAX_LOT_SIZE:
                soft_warnings.append(f"Lot size {strategy.quantity} slightly exceeds max {cfg.MAX_LOT_SIZE}")

            if strategy.stop_loss_pips > cfg.MAX_PIP_STOP_LOSS * 1.5:  # HARD
                hard_violations.append(f"SL {strategy.stop_loss_pips:.0f} pips far exceeds max")
            elif strategy.stop_loss_pips > cfg.MAX_PIP_STOP_LOSS:
                soft_warnings.append(f"SL {strategy.stop_loss_pips:.0f} pips exceeds preferred max")

            # News shield: SOFT ÙˆÙ„ÙŠØ³ HARD (ØªØ­Ø°ÙŠØ± ÙÙ‚Ø·)
            if not strategy.pre_news_clearance:
                soft_warnings.append("FX trade near news window â€” proceed with caution")

            if portfolio.get("forex_positions", 0) >= cfg.MAX_FOREX_OPEN_POSITIONS:
                hard_violations.append("Forex positions at hard max")

        is_hard_vetoed = len(hard_violations) > 0
        return hard_violations, soft_warnings, is_hard_vetoed

    async def _llm_risk_analysis(self, strategy: StrategyProposal, portfolio: dict, existing_violations: list, cycle_id: str) -> dict:
        user_prompt = f"""
You are the Chief Risk Manager. Evaluate this trading strategy.
STRATEGY: {strategy.asset_class} {strategy.action} {strategy.symbol}
Qty: {strategy.quantity} | Entry: {strategy.entry_price} | SL: {strategy.stop_loss} | TP: {strategy.take_profit}
R:R: {strategy.risk_reward_ratio} | Max Risk: ${strategy.max_capital_at_risk:.2f}
PORTFOLIO: Balance: ${portfolio.get('balance', 0):.2f} | Open: {portfolio.get('open_positions', 0)}
Return ONLY valid JSON:
{{"verdict": "APPROVED or VETOED", "risk_score": <0.0-10.0>, "risk_concerns": [], "veto_reason": "", "max_allowable_quantity": <float>, "risk_manager_commentary": ""}}
"""
        result = await self.think(user_prompt, cycle_id=cycle_id)
        return result or {}

    def _build_verdict(self, strategy: StrategyProposal, hard_violations: list, soft_warnings: list, llm_result: dict) -> RiskVerdict:
        llm_verdict = llm_result.get("verdict", "APPROVED")
        risk_score = float(llm_result.get("risk_score", 4.0))  # Ø®ÙÙÙÙ‘Ø¶ Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠ Ù…Ù† 5.0 â†’ 4.0
        all_violations = hard_violations + soft_warnings + llm_result.get("risk_concerns", [])
        # Ø§Ù„Ø±ÙØ¶ ÙÙ‚Ø· Ø¹Ù†Ø¯: Ø§Ù†ØªÙ‡Ø§ÙƒØ§Øª HARD Ø£Ùˆ Ø¹Ù†Ø¯Ù…Ø§ ÙŠØ±ÙØ¶ LLM Ø¨Ø§Ù„ØªØ£ÙƒÙŠØ¯ (risk_score >= 8)
        final_verdict = "VETOED" if (
            hard_violations or (llm_verdict == "VETOED" and risk_score >= 7.5)
        ) else "APPROVED"

        return RiskVerdict(
            strategy_id=strategy.strategy_id,
            asset_class=strategy.asset_class,
            verdict=final_verdict,
            rule_violations=all_violations,
            risk_score=risk_score,
            veto_reason=llm_result.get("veto_reason", "; ".join(hard_violations)) if final_verdict == "VETOED" else "",
            max_allowable_quantity=float(llm_result.get("max_allowable_quantity", strategy.quantity)),
            risk_manager_commentary=llm_result.get("risk_manager_commentary", ""),
            llm_provider=self.last_provider
        )