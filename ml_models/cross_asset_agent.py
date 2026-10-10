"""
==============================================================================
ml_models/cross_asset_agent.py — Institutional Cross-Asset Flow Agent
==============================================================================
Module  : Cross-Asset Liquidity & Intermarket Flow Matrix
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Monitors global capital rotation across:
  - US 10-Year Treasury Yields (US10Y / TNX)
  - US Dollar Index (DXY)
  - Volatility Index (VIX)
  - Gold (XAUUSD)
  - Major FX Pairs (EURUSD, USDJPY, GBPUSD)

Calculates intermarket capital flow alignment to assign a macro weighted
multiplier to trade signals, preventing traders from going long a currency
when institutional macro yields and dollar flows are aggressively withdrawing liquidity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("institutional_mas.cross_asset")


@dataclass
class MacroFlowMetrics:
    dxy_drift: float           # Positive = USD strength, Negative = USD weakness
    us10y_drift: float         # Positive = yield expansion, Negative = contraction
    vix_level: float           # > 20 is elevated risk-off, < 15 is risk-on complacency
    gold_drift: float          # Safe-haven flow proxy
    market_sentiment_regime: str # "RISK_ON", "RISK_OFF", "USD_EXPANSION", "NEUTRAL"


@dataclass
class CrossAssetValidationResult:
    target_symbol: str
    proposed_direction: str
    macro_alignment_score: float   # 0.0 to 1.0 (multiplier for conviction)
    macro_flow_summary: str
    is_macro_aligned: bool
    veto_recommended: bool
    rationale: str


class CrossAssetGraphAgent:
    """
    Evaluates global intermarket relationships and provides capital-flow
    verification for FX pairs.
    """

    def __init__(self, risk_off_vix_threshold: float = 24.0):
        self.risk_off_vix_threshold = risk_off_vix_threshold

    def evaluate_intermarket_state(
        self,
        dxy_change_pct: float,
        us10y_change_pct: float,
        vix_level: float,
        gold_change_pct: float,
    ) -> MacroFlowMetrics:
        """Determines global liquidity regime from cross-asset signals."""
        if vix_level >= self.risk_off_vix_threshold:
            regime = "RISK_OFF"
        elif dxy_change_pct > 0.003 and us10y_change_pct > 0.01:
            regime = "USD_EXPANSION"
        elif dxy_change_pct < -0.003 and us10y_change_pct < -0.01:
            regime = "RISK_ON"
        else:
            regime = "NEUTRAL"

        return MacroFlowMetrics(
            dxy_drift=round(dxy_change_pct, 4),
            us10y_drift=round(us10y_change_pct, 4),
            vix_level=round(vix_level, 2),
            gold_drift=round(gold_change_pct, 4),
            market_sentiment_regime=regime,
        )

    def validate_pair_alignment(
        self,
        symbol: str,
        proposed_action: str,  # "BUY" or "SELL"
        macro: MacroFlowMetrics,
    ) -> CrossAssetValidationResult:
        """
        Validates whether the proposed FX trade is supported by macro flows.
        """
        symbol_clean = symbol.replace("/", "").upper()
        alignment_score = 0.5  # Neutral starting point
        rationale_items = []
        veto = False

        is_usd_counter = symbol_clean in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
        is_usd_base = symbol_clean in ("USDJPY", "USDCAD", "USDCHF")

        # 1. DXY Alignment
        if is_usd_counter:
            # If buying EURUSD, we need DXY weakness or neutral
            if proposed_action == "BUY":
                if macro.dxy_drift < 0:
                    alignment_score += 0.25
                    rationale_items.append("Supported by Dollar Index (DXY) contraction")
                elif macro.dxy_drift > 0.004:
                    alignment_score -= 0.35
                    rationale_items.append("Opposed by surging DXY Dollar strength")
                    if macro.dxy_drift > 0.008:
                        veto = True
            elif proposed_action == "SELL":
                if macro.dxy_drift > 0:
                    alignment_score += 0.25
                    rationale_items.append("Supported by Dollar Index (DXY) expansion")
                elif macro.dxy_drift < -0.004:
                    alignment_score -= 0.35
                    rationale_items.append("Opposed by falling DXY Dollar strength")

        elif is_usd_base:
            # If buying USDJPY, we need DXY strength
            if proposed_action == "BUY":
                if macro.dxy_drift > 0:
                    alignment_score += 0.25
                    rationale_items.append("Supported by DXY Dollar strength")
                elif macro.dxy_drift < -0.004:
                    alignment_score -= 0.35
                    rationale_items.append("Opposed by falling DXY")
            elif proposed_action == "SELL":
                if macro.dxy_drift < 0:
                    alignment_score += 0.25
                    rationale_items.append("Supported by DXY weakness")

        # 2. VIX Risk Regime
        if macro.market_sentiment_regime == "RISK_OFF":
            # Risk-off favors JPY and CHF longs, hurts AUD and NZD
            if "JPY" in symbol_clean or "CHF" in symbol_clean:
                if (is_usd_base and proposed_action == "SELL") or (not is_usd_base and "JPY" in symbol_clean[-3:] and proposed_action == "SELL"):
                    alignment_score += 0.15
                    rationale_items.append("Elevated VIX confirms safe-haven flow")
            elif "AUD" in symbol_clean or "NZD" in symbol_clean:
                if proposed_action == "BUY":
                    alignment_score -= 0.20
                    rationale_items.append("Risk-off regime penalizes commodity currencies")

        alignment_score = max(0.0, min(1.0, alignment_score))
        is_aligned = alignment_score >= 0.45 and not veto

        return CrossAssetValidationResult(
            target_symbol=symbol,
            proposed_direction=proposed_action,
            macro_alignment_score=round(alignment_score, 2),
            macro_flow_summary=macro.market_sentiment_regime,
            is_macro_aligned=is_aligned,
            veto_recommended=veto,
            rationale="; ".join(rationale_items) if rationale_items else "Neutral macro correlation.",
        )
