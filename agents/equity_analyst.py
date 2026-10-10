"""
Equity Data Analyst Agent â€” fetches US stock market data,
computes technical indicators, and produces structured
market intelligence reports for the Strategy Planner.
Uses yfinance (free, unlimited).
"""

from __future__ import annotations
import json
import logging
from datetime import datetime

from agents.llm_agent_base import BaseAgent
from data.equity_data import build_equity_report, is_us_market_open
from data.news_fetcher import fetch_combined_news
import config as cfg

logger = logging.getLogger("equity_analyst")


class EquityAnalystAgent(BaseAgent):
    name = "equity_analyst"
    role_description = "Senior Equity Data Analyst specializing in US stock markets"

    SYSTEM_PROMPT_EXTENSION = """
YOUR JOB:
1. Analyze the provided raw market data for US equities
2. Identify market regime, key support/resistance levels, and trend direction
3. Assess the probability of significant price movement
4. Produce a structured analytical report

You MUST return a JSON object with:
{
  "symbol": "...",
  "overall_signal": "BULLISH | BEARISH | NEUTRAL | CAUTION",
  "market_regime": "...",
  "key_observations": ["...", "..."],
  "support_level": 0.0,
  "resistance_level": 0.0,
  "short_term_bias": "BULLISH | BEARISH | NEUTRAL",
  "risk_factors": ["...", "..."],
  "analyst_commentary": "detailed analysis in 2-3 sentences",
  "confidence_level": 0.0,
  "recommended_action": "WATCH | CONSIDER_LONG | CONSIDER_SHORT | AVOID"
}
"""

    async def analyze(self, cycle_id: str = "") -> list[dict]:
        """
        Analyze all stocks in the watchlist.
        Returns list of market reports (one per symbol).
        """
        if not is_us_market_open():
            logger.info("[EQUITY_ANALYST] US market closed â€” skipping equity cycle")
            return []

        reports = []
        for symbol in cfg.EQUITY_WATCHLIST:
            report = await self._analyze_symbol(symbol, cycle_id)
            if report:
                reports.append(report)

        logger.info(f"[EQUITY_ANALYST] Produced {len(reports)} equity reports")
        return reports

    async def _analyze_symbol(self, symbol: str, cycle_id: str) -> dict | None:
        """Analyze a single equity symbol."""
        raw_report = build_equity_report(symbol)
        if raw_report is None:
            logger.warning(f"[EQUITY_ANALYST] Could not fetch data for {symbol}")
            return None

        # Add news context
        news = fetch_combined_news(symbol, "EQUITY")
        raw_report["recent_news_headlines"] = news[:5]

        user_prompt = f"""
Analyze the following market data for {symbol} and provide your assessment:

PRICE ACTION:
{json.dumps(raw_report['price_action'], indent=2)}

TECHNICAL INDICATORS:
{json.dumps(raw_report['indicators'], indent=2)}

MARKET REGIME: {raw_report['market_regime']}
EARNINGS IN DAYS: {raw_report.get('earnings_in_days', 'Unknown')}

RECENT NEWS HEADLINES:
{chr(10).join(f'- {h}' for h in raw_report['recent_news_headlines'])}

Based on all this data, provide your structured analytical assessment.
"""
        llm_output = await self.think(user_prompt, cycle_id=cycle_id)

        if llm_output:
            raw_report["analyst_commentary"] = llm_output.get("analyst_commentary", "")
            raw_report["overall_signal"] = llm_output.get("overall_signal", "NEUTRAL")
            raw_report["key_observations"] = llm_output.get("key_observations", [])
            raw_report["support_level"] = llm_output.get("support_level")
            raw_report["resistance_level"] = llm_output.get("resistance_level")
            raw_report["recommended_action"] = llm_output.get("recommended_action", "WATCH")
            raw_report["llm_provider"] = self.last_provider
            raw_report["confidence_level"] = llm_output.get("confidence_level",
                                                              raw_report.get("confidence_level", 0.5))

        return raw_report
