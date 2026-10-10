"""
FX Data Analyst Agent â€” fetches Forex market data, computes
pip-based indicators, detects active sessions, monitors
the economic calendar, and activates the news shield when
HIGH-IMPACT events are imminent.
Uses yfinance (free) + Finnhub (free tier).
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone, timedelta

from agents.llm_agent_base import BaseAgent
from data.fx_data import build_fx_report
from data.economic_calendar import (
    fetch_economic_events,
    should_activate_news_shield,
    get_shield_expiry,
    get_high_impact_events_within,
)
from schemas.forex import get_active_forex_session, display_pair
import config as cfg

logger = logging.getLogger("fx_analyst")


class FXAnalystAgent(BaseAgent):
    name = "fx_analyst"
    role_description = "Senior Forex Analyst specializing in currency markets, macro events, and FX technicals"

    SYSTEM_PROMPT_EXTENSION = """
YOUR ROLE: You are a Senior Hedge Fund FX Analyst. You do NOT use basic retail technical analysis. 
You use Institutional Trading logic to identify high-probability setups with maximum confluence.

CORE ANALYSIS FRAMEWORK:
1. SMART MONEY CONCEPTS (SMC): Look for "Order Blocks," "Fair Value Gaps" (FVG), and "Liquidity Sweeps."
2. LIQUIDITY ANALYSIS: Identify where retail stop-losses likely reside (Equal Highs/Lows). 
3. MULTI-TIMEFRAME CONFLUENCE: Ensure the intra-day setup aligns with the Weekly/Monthly trend.
4. SESSION MOMENTUM: Prioritize setups during high-liquidity overlaps (London/New York).

TRADING REQUIREMENTS:
- Signal BULLISH only if price is reacting off a Bullish Order Block or clearing a Liquidity Pool.
- Signal BEARISH only if price is reacting off a Bearish Supply Zone or after a Stop Run.
- NEUTRAL if market is ranging or showing no clear institutional footprint.

You MUST return a JSON object with:
{
  "pair": "EUR/USD",
  "yf_pair": "EURUSD=X",
  "overall_signal": "BULLISH | BEARISH | NEUTRAL | AVOID_PRE_NEWS",
  "institutional_context": "Explain the SMC/Liquidity setup here",
  "key_levels": {"support": 0.0, "resistance": 0.0, "order_block": 0.0},
  "confluence_factors": ["Factor 1", "Factor 2", "Factor 3"],
  "pip_target": 0,
  "confidence_level": 0.0,
  "recommended_action": "WATCH | CONSIDER_LONG | CONSIDER_SHORT | AVOID"
}
"""

    async def analyze(self, cycle_id: str = "") -> list[dict]:
        """
        Analyze all FX pairs in the watchlist.
        Returns list of FX market reports + economic events context.
        Always runs (Forex is 24/5).
        """
        # Fetch economic calendar once for all pairs
        economic_events = fetch_economic_events(days_ahead=1)
        high_impact_soon = get_high_impact_events_within(cfg.NEWS_SHIELD_MINUTES, economic_events)
        shield_needed = len(high_impact_soon) > 0

        if shield_needed:
            logger.warning(
                f"[FX_ANALYST] âš ï¸  NEWS SHIELD REQUIRED: "
                f"{[e['event_name'] for e in high_impact_soon]}"
            )
            # Activate shield in DB
            if self.db:
                expiry = get_shield_expiry(economic_events)
                if expiry:
                    await self.db.activate_news_shield("ALL", high_impact_soon[0]["event_name"], expiry)
                    await self.db.deactivate_expired_shields()

        reports = []
        for pair in cfg.FX_WATCHLIST:
            report = await self._analyze_pair(pair, economic_events, shield_needed, cycle_id)
            if report:
                reports.append(report)

        logger.info(f"[FX_ANALYST] Produced {len(reports)} FX reports. Shield: {shield_needed}")
        return reports

    async def _analyze_pair(
        self, pair: str, economic_events: list, shield_needed: bool, cycle_id: str
    ) -> dict | None:
        """Analyze a single FX pair."""
        raw_report = build_fx_report(pair)
        if raw_report is None:
            logger.warning(f"[FX_ANALYST] Could not fetch data for {pair}")
            return None

        raw_report["economic_events_today"] = economic_events[:5]
        raw_report["news_shield_active"] = shield_needed
        raw_report["trading_recommendation"] = "AVOID_PRE_NEWS" if shield_needed else "ACTIVE"

        # Get current session
        now_utc = datetime.now(timezone.utc)
        session = get_active_forex_session(now_utc.hour)
        raw_report["active_session"] = session.value if hasattr(session, "value") else str(session)

        user_prompt = f"""
Analyze the following Forex market data for {display_pair(pair)}:

CURRENT RATE: {raw_report['rate']}
ACTIVE SESSION: {raw_report['active_session']}
DAILY CHANGE: {raw_report['daily_change_pips']} pips
WEEKLY TREND: {raw_report['weekly_trend']}
SPREAD ESTIMATE: {raw_report['spread_pips']} pips

TECHNICAL INDICATORS:
{json.dumps(raw_report['indicators'], indent=2)}

CURRENCY STRENGTH:
{json.dumps(raw_report.get('currency_strength', {}), indent=2)}

UPCOMING ECONOMIC EVENTS:
{json.dumps(economic_events[:3], indent=2)}

NEWS SHIELD ACTIVE: {shield_needed}
{"âš ï¸  HIGH-IMPACT EVENT APPROACHING â€” Recommend AVOID or CAUTION" if shield_needed else "No immediate news risk"}

Provide your structured Forex analysis.
"""
        llm_output = await self.think(user_prompt, cycle_id=cycle_id)

        if llm_output:
            raw_report["overall_signal"] = llm_output.get("overall_signal", "NEUTRAL")
            raw_report["analyst_commentary"] = llm_output.get("analyst_commentary", "")
            raw_report["key_observations"] = llm_output.get("key_observations", [])
            raw_report["support_level"] = llm_output.get("support_level")
            raw_report["resistance_level"] = llm_output.get("resistance_level")
            raw_report["pip_target"] = llm_output.get("pip_target", 30)
            raw_report["recommended_action"] = llm_output.get("recommended_action", "WATCH")
            raw_report["session_quality"] = llm_output.get("session_quality", "FAIR")
            raw_report["confidence_level"] = llm_output.get("confidence_level",
                                                              raw_report.get("confidence_level", 0.5))
            raw_report["llm_provider"] = self.last_provider

        return raw_report
