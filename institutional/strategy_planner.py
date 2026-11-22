"""
Strategy Planner Agent â€” autonomously generates trading strategies.
Updated: Dynamic lot sizing based on Live MT5 Equity + Aggressive Prompts.
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime

from institutional.base_agent import BaseAgent
from schemas.agents import StrategyProposal
from schemas.forex import lot_type_from_size, price_to_pips, pips_to_usd, calculate_margin_required, display_pair
import config as cfg

logger = logging.getLogger("strategy_planner")


class StrategyPlannerAgent(BaseAgent):
    name = "strategy_planner"
    role_description = "Aggressive Quantitative Strategy Planner actively seeking market opportunities"

    async def generate_equity_strategy(self, equity_reports: list[dict], portfolio_summary: dict, cycle_id: str = "", revision_round: int = 0, ceo_instructions: str = "") -> StrategyProposal | None:
        candidates = [r for r in equity_reports if r.get("recommended_action") in ("CONSIDER_LONG", "CONSIDER_SHORT")]
        if not candidates: candidates = [r for r in equity_reports if r.get("overall_signal") != "NEUTRAL"]
        if not candidates: candidates = equity_reports

        candidates.sort(key=lambda r: r.get("confidence_level", 0), reverse=True)
        best_report = candidates[0] if candidates else None
        if not best_report: return None

        symbol = best_report["symbol"]
        current_price = best_report["price_action"]["current_price"]

        # ðŸ”´ Ø§Ø³ØªØ®Ø¯Ø§Ù… Ø§Ù„Ø±ØµÙŠØ¯ Ø§Ù„Ø­ÙŠ Ù…Ù† MT5 Ø¨Ø¯Ù„Ø§Ù‹ Ù…Ù† Ø§Ù„Ø«Ø§Ø¨Øª
        live_balance = portfolio_summary.get("balance", cfg.STARTING_CAPITAL)
        equity_capital = portfolio_summary.get("equity_book", {}).get("available_capital", live_balance * cfg.EQUITY_ALLOCATION_PCT)

        user_prompt = f"""
You are an ACTIVE Lead Quantitative Strategist. Your goal is to find profitable trades, not sit on the sidelines.
Analyze the data for {symbol} and design a trading strategy. DO NOT default to HOLD unless the market is completely dead.

MARKET DATA FOR {symbol}:
Signal: {best_report.get('overall_signal')} | Regime: {best_report.get('market_regime')}
Price: ${current_price} | RSI: {best_report.get('indicators', {}).get('RSI_14')}
ATR: {best_report.get('indicators', {}).get('ATR_14')}
Analyst Notes: {best_report.get('analyst_commentary', '')}

PORTFOLIO CONTEXT (LIVE BALANCE):
Available Capital: ${equity_capital:.2f} | Max Risk: {cfg.MAX_SINGLE_TRADE_RISK_PCT * 100:.0f}% (${equity_capital*cfg.MAX_SINGLE_TRADE_RISK_PCT:.2f})

{f"CEO REVISION (Round {revision_round}): {ceo_instructions}" if ceo_instructions else ""}

STRATEGY REQUIREMENTS:
- Minimum Risk-to-Reward (R:R): {cfg.MIN_RISK_REWARD_RATIO}. Accept B+ setups, not just A+.
- Precise Stop Loss: Set at a logical invalidation point.
- Quantity: Calculate shares based on the $ risk amount. Do not over-leverage.

Return ONLY valid JSON:
{{"action": "BUY or SELL", "quantity": <integer>, "entry_price": <float>, "stop_loss": <float>, "take_profit": <float>, "strategy_type": "<Name>", "rationale": "2-3 sentences", "confidence_score": <0.0-1.0>, "risk_reward_ratio": <float>, "max_capital_at_risk": <float>}}
"""
        llm_output = await self.think(user_prompt, cycle_id=cycle_id)
        if not llm_output or llm_output.get("action") == "HOLD": return None

        action = llm_output.get("action", "BUY")
        quantity = int(llm_output.get("quantity", 1))
        entry = float(llm_output.get("entry_price", current_price))
        sl = float(llm_output.get("stop_loss", entry * 0.97))
        tp = float(llm_output.get("take_profit", entry * 1.06))
        rr = round(abs(tp - entry) / max(abs(entry - sl), 0.01), 2)
        max_risk = round(abs(entry - sl) * quantity, 2)

        return StrategyProposal(strategy_id=f"STR-EQ-{uuid.uuid4().hex[:8].upper()}", asset_class="EQUITY", symbol=symbol, action=action, quantity=quantity, entry_price=entry, stop_loss=sl, take_profit=tp, strategy_type=llm_output.get("strategy_type", ""), rationale=llm_output.get("rationale", ""), confidence_score=float(llm_output.get("confidence_score", 0.5)), risk_reward_ratio=rr, max_capital_at_risk=max_risk, revision_round=revision_round, llm_provider=self.last_provider)

    def build_tactical_scenario_matrix(
        self,
        symbol: str,
        action: str,
        entry: float,
        atr_pips: float,
        session: str = "UNKNOWN",
    ) -> dict:
        """
        Builds a 3-tier tactical scenario planning matrix:
        - Scenario A: Primary Expansion (1.5x - 3.0x ATR)
        - Scenario B: Retracement / Discount Entry
        - Scenario C: Structural Invalidation & Capital Defense
        """
        is_jpy = "JPY" in symbol
        pip_unit = 0.01 if is_jpy else 0.0001
        atr_distance = max(10.0, float(atr_pips or 25.0)) * pip_unit

        if action == "BUY":
            tp1 = round(entry + 1.2 * atr_distance, 5 if not is_jpy else 3)
            tp2 = round(entry + 2.2 * atr_distance, 5 if not is_jpy else 3)
            tp3 = round(entry + 3.5 * atr_distance, 5 if not is_jpy else 3)
            sl  = round(entry - 1.0 * atr_distance, 5 if not is_jpy else 3)
            discount_entry = round(entry - 0.4 * atr_distance, 5 if not is_jpy else 3)
        else:
            tp1 = round(entry - 1.2 * atr_distance, 5 if not is_jpy else 3)
            tp2 = round(entry - 2.2 * atr_distance, 5 if not is_jpy else 3)
            tp3 = round(entry - 3.5 * atr_distance, 5 if not is_jpy else 3)
            sl  = round(entry + 1.0 * atr_distance, 5 if not is_jpy else 3)
            discount_entry = round(entry + 0.4 * atr_distance, 5 if not is_jpy else 3)

        return {
            "scenario_a_primary": {
                "name": "Immediate Momentum Infiltration",
                "trigger": entry,
                "targets": [tp1, tp2, tp3],
                "invalidation": sl,
            },
            "scenario_b_pullback": {
                "name": "Deep Liquidity Sweep Retracement",
                "optimal_entry": discount_entry,
                "invalidation": sl,
            },
            "scenario_c_contingency": {
                "name": "Volatility Spike Capital Preservation",
                "max_adverse_tolerance_pips": round(float(atr_pips or 25.0) * 1.5, 1),
            },
            "session_context": session,
        }

    async def generate_forex_strategy(self, fx_reports: list[dict], portfolio_summary: dict, cycle_id: str = "", revision_round: int = 0, ceo_instructions: str = "") -> StrategyProposal | None:
        # Ø§Ù„Ø£ÙˆÙ„ÙˆÙŠØ©: Ø£Ø²ÙˆØ§Ø¬ Ù„ÙŠØ³ ÙÙŠÙ‡Ø§ news_shield + ØªÙˆØµÙŠØ© Ù†Ø´Ø·Ø©
        candidates = [r for r in fx_reports if not r.get("news_shield_active", False)
                      and r.get("recommended_action") in ("CONSIDER_LONG", "CONSIDER_SHORT")]

        # Ø§Ù„Ù…Ø±Ø­Ù„Ø© 2: Ø£ÙŠ Ø²ÙˆØ¬ Ø¨Ø¯ÙˆÙ† news_shield
        if not candidates:
            candidates = [r for r in fx_reports if not r.get("news_shield_active", False)]

        # Ø§Ù„Ù…Ø±Ø­Ù„Ø© 3 (Ø¬Ø¯ÙŠØ¯): Ø¥Ø°Ø§ ÙƒÙ„ Ø§Ù„Ø£Ø²ÙˆØ§Ø¬ Ø¨Ù‡Ø§ news_shield, Ù†Ø®ØªØ§Ø± Ø§Ù„Ø£ÙØ¶Ù„ Ù…Ø¹ ØªØ­Ø°ÙŠØ±
        if not candidates:
            candidates = sorted(fx_reports, key=lambda r: r.get("confidence_level", 0), reverse=True)
            logger.warning("[PLANNER] All pairs have news_shield â€” proceeding with best available pair")

        candidates.sort(key=lambda r: r.get("confidence_level", 0), reverse=True)
        if not candidates:
            # Ù„Ø§ ØªÙ‚Ø§Ø±ÙŠØ± ÙÙˆØ±ÙƒØ³ ØµØ§Ù„Ø­Ø© (ÙØ´Ù„ Ø¬Ù„Ø¨ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø£Ùˆ Ù‚Ø§Ø¦Ù…Ø© ÙØ§Ø±ØºØ©)
            logger.warning("[PLANNER] Ù„Ø§ ØªÙˆØ¬Ø¯ ØªÙ‚Ø§Ø±ÙŠØ± ÙÙˆØ±ÙƒØ³ ØµØ§Ù„Ø­Ø© â€” Ù„Ø§ Ù…Ù‚ØªØ±Ø­ ÙÙŠ Ù‡Ø°Ù‡ Ø§Ù„Ø¯ÙˆØ±Ø©")
            return None
        best = candidates[0]

        pair = best["pair"]
        rate = best["rate"]
        session = best.get("active_session", "UNKNOWN")
        
        # ðŸ”´ Ø§Ø³ØªØ®Ø¯Ø§Ù… Ø§Ù„Ø±ØµÙŠØ¯ Ø§Ù„Ø­ÙŠ Ù…Ù† MT5 Ø¨Ø¯Ù„Ø§Ù‹ Ù…Ù† Ø§Ù„Ø«Ø§Ø¨Øª
        live_balance = portfolio_summary.get("balance", cfg.STARTING_CAPITAL)
        fx_capital = portfolio_summary.get("forex_book", {}).get("available_capital", live_balance * cfg.FOREX_ALLOCATION_PCT)

        if cfg.MANUAL_LOT_SIZE_ENABLED:
            max_lot = cfg.FIXED_LOT_SIZE
        else:
            max_lot = min(cfg.MAX_LOT_SIZE, fx_capital / (rate * 100_000 / cfg.MAX_FOREX_LEVERAGE))
            max_lot = round(max(0.01, max_lot), 2)

        user_prompt = f"""
You are an ACTIVE Senior Quantitative Forex Strategist. Your job is to find high-probability FX setups.
Do not hesitate to take a trade if confluence exists. Design an institutional-grade FX setup for {display_pair(pair)}.

CURRENCY PAIR: {display_pair(pair)} | RATE: {rate} | SESSION: {session}
Indicators: RSI: {best.get('indicators', {}).get('RSI_14')} | ATR(Pips): {best.get('indicators', {}).get('ATR_14_pips')}
Analyst Vision: {best.get('analyst_commentary', '')}

LIVE PORTFOLIO CONSTRAINTS:
- Max lot size: {max_lot} | Max SL: {cfg.MAX_PIP_STOP_LOSS} pips
- MIN Risk-to-Reward (R:R): {cfg.MIN_RISK_REWARD_RATIO}

{f"CEO REVISION (Round {revision_round}): {ceo_instructions}" if ceo_instructions else ""}

PLANNING REQUIREMENTS:
- Identify the Order Block or FVG.
- Position sizing MUST respect the ${fx_capital * cfg.MAX_SINGLE_TRADE_RISK_PCT:.2f} risk cap based on the LIVE balance.

Return ONLY valid JSON:
{{"action": "BUY or SELL", "lot_size": <float>, "entry_price": <float>, "stop_loss_price": <float>, "take_profit_price": <float>, "stop_loss_pips": <float>, "take_profit_pips": <float>, "strategy_type": "Name", "rationale": "2-3 sentences", "confidence_score": <0.0-1.0>, "risk_reward_ratio": <float>}}
"""
        llm_output = await self.think(user_prompt, cycle_id=cycle_id)
        if not llm_output: return None

        action = llm_output.get("action", "BUY")
        if cfg.MANUAL_LOT_SIZE_ENABLED:
            lot_size = cfg.FIXED_LOT_SIZE
        else:
            lot_size = min(float(llm_output.get("lot_size", 0.01)), max_lot)
            lot_size = max(0.01, lot_size)
        entry = float(llm_output.get("entry_price", rate))
        sl_price = float(llm_output.get("stop_loss_price", 0))
        tp_price = float(llm_output.get("take_profit_price", 0))
        sl_pips = float(llm_output.get("stop_loss_pips", price_to_pips(pair, abs(entry - sl_price))))
        tp_pips = float(llm_output.get("take_profit_pips", price_to_pips(pair, abs(tp_price - entry))))

        lot_type = lot_type_from_size(lot_size)
        max_loss = pips_to_usd(pair, sl_pips, lot_size)
        max_profit = pips_to_usd(pair, tp_pips, lot_size)
        rr = round(tp_pips / max(sl_pips, 0.1), 2)
        margin = calculate_margin_required(pair, lot_size, entry, cfg.MAX_FOREX_LEVERAGE)

        atr_pips = best.get("indicators", {}).get("ATR_14_pips", 20.0)
        scenarios = self.build_tactical_scenario_matrix(pair, action, entry, atr_pips, session)
        base_rat = llm_output.get("rationale", "")
        enriched_rat = f"{base_rat} | Scenarios: [A: Mom TP1={scenarios['scenario_a_primary']['targets'][0]}], [B: Pullback={scenarios['scenario_b_pullback']['optimal_entry']}]"

        return StrategyProposal(
            strategy_id=f"STR-FX-{uuid.uuid4().hex[:8].upper()}",
            asset_class="FOREX",
            symbol=pair,
            action=action,
            quantity=lot_size,
            entry_price=entry,
            stop_loss=sl_price,
            take_profit=tp_price,
            stop_loss_pips=sl_pips,
            take_profit_pips=tp_pips,
            lot_type=lot_type.value,
            strategy_type=llm_output.get("strategy_type", "Tactical_Confluence"),
            rationale=enriched_rat,
            confidence_score=float(llm_output.get("confidence_score", 0.5)),
            risk_reward_ratio=rr,
            max_capital_at_risk=max_loss,
            max_loss_usd=max_loss,
            max_profit_usd=max_profit,
            pre_news_clearance=not best.get("news_shield_active", False),
            session=session,
            revision_round=revision_round,
            llm_provider=self.last_provider,
        )