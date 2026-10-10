"""
==============================================================================
agents/multi_agent_debate.py — Institutional Multi-Agent Debate (MAD)
==============================================================================
Module  : Multi-Agent Debate & Statistical Consensus Engine
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Replaces naive single-model or un-debated signals with a dialectical Multi-Agent
Debate (MAD) framework.
A dedicated Bullish Advocate and Bearish Advocate present quantitative,
technical, and microstructure arguments.

The Debate Arbiter weighs both arguments:
  - If the dominant advocate fails to establish a statistical consensus
    exceeding the Confidence Threshold (e.g., >= 75%), the signal is REJECTED.
  - Capital is preserved whenever consensus is ambiguous.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("institutional_mas.debate")


class DebateVerdict(str, Enum):
    APPROVED_BUY  = "APPROVED_BUY"
    APPROVED_SELL = "APPROVED_SELL"
    REJECTED_HOLD = "REJECTED_HOLD"


@dataclass
class AdvocateArgument:
    side: str                          # "BULLISH" or "BEARISH"
    conviction_score: float            # 0.0 to 100.0%
    primary_thesis: str
    supporting_points: List[str]
    identified_risks: List[str]
    quantitative_metrics: Dict[str, float]


@dataclass
class DebateSessionResult:
    symbol: str
    verdict: DebateVerdict
    consensus_confidence: float        # e.g., 78.5%
    threshold_required: float          # e.g., 75.0%
    margin_of_dominance: float         # Bull score - Bear score
    bullish_argument: AdvocateArgument
    bearish_argument: AdvocateArgument
    synthesis_rationale: str
    execution_permitted: bool
    veto_applied: bool = False          # هل مُنع التنفيذ فعلاً (يعتمد على veto_enabled)


class BullishAdvocate:
    """Argues for long positions based on SMC, order flow, momentum, and support."""

    def present_case(self, context: Dict[str, Any]) -> AdvocateArgument:
        points = []
        metrics = {}
        conviction = 40.0  # Base

        # 1. Structure / Trend
        ema = context.get("ema", 0)
        close = context.get("close", 0)
        if close > ema and ema > 0:
            points.append(f"Price ({close:.5f}) trading above 50-EMA ({ema:.5f})")
            conviction += 15.0

        # 2. RSI / Momentum
        rsi = context.get("rsi", 50.0)
        metrics["rsi"] = rsi
        if 40.0 <= rsi <= 65.0:
            points.append(f"RSI in healthy bullish continuation corridor ({rsi:.1f})")
            conviction += 10.0
        elif rsi > 75.0:
            conviction -= 10.0  # Overbought exhaustion

        # 3. Order Flow / Absorption
        absorption = context.get("absorption_detected", "NONE")
        if absorption == "BULLISH_ABSORPTION":
            points.append("Institutional Bullish Absorption detected at key support")
            conviction += 20.0

        # 4. Liquidity Sweep
        sweep = context.get("sweep_direction")
        if sweep == "LOW_SWEEP":
            points.append("Liquidity Sweep of prior swing low confirmed (stop run complete)")
            conviction += 15.0

        # 5. Macro Regime
        regime = context.get("regime", "")
        if regime == "TRENDING_BULLISH":
            points.append("Aligned with macro HMM TRENDING_BULLISH regime")
            conviction += 15.0
        elif regime == "TRENDING_BEARISH":
            conviction -= 30.0

        risks = []
        if rsi > 70.0:
            risks.append("Near-term overbought conditions")
        if context.get("spread", 0) > 20:
            risks.append("Elevated spread may increase slippage")

        conviction = max(0.0, min(100.0, conviction))
        return AdvocateArgument(
            side="BULLISH",
            conviction_score=round(conviction, 1),
            primary_thesis="Long execution favored by structural momentum and liquidity absorption.",
            supporting_points=points,
            identified_risks=risks,
            quantitative_metrics=metrics,
        )


class BearishAdvocate:
    """Argues for short positions or capital preservation based on resistance and downside risks."""

    def present_case(self, context: Dict[str, Any]) -> AdvocateArgument:
        points = []
        metrics = {}
        conviction = 40.0  # Base

        # 1. Structure / Trend
        ema = context.get("ema", 0)
        close = context.get("close", 0)
        if close < ema and ema > 0:
            points.append(f"Price ({close:.5f}) trading below 50-EMA ({ema:.5f})")
            conviction += 15.0

        # 2. RSI / Momentum
        rsi = context.get("rsi", 50.0)
        metrics["rsi"] = rsi
        if 35.0 <= rsi <= 60.0:
            points.append(f"RSI in downward momentum corridor ({rsi:.1f})")
            conviction += 10.0
        elif rsi < 25.0:
            conviction -= 10.0  # Oversold exhaustion

        # 3. Order Flow / Absorption
        absorption = context.get("absorption_detected", "NONE")
        if absorption == "BEARISH_ABSORPTION":
            points.append("Institutional Bearish Absorption detected at supply ceiling")
            conviction += 20.0

        # 4. Liquidity Sweep
        sweep = context.get("sweep_direction")
        if sweep == "HIGH_SWEEP":
            points.append("Liquidity Sweep of prior swing high confirmed (buy stops purged)")
            conviction += 15.0

        # 5. Macro Regime
        regime = context.get("regime", "")
        if regime == "TRENDING_BEARISH":
            points.append("Aligned with macro HMM TRENDING_BEARISH regime")
            conviction += 15.0
        elif regime == "TRENDING_BULLISH":
            conviction -= 30.0

        risks = []
        if rsi < 30.0:
            risks.append("Near-term oversold bounce risk")
        if context.get("atr", 0) > 0.0050:
            risks.append("High volatility expansion")

        conviction = max(0.0, min(100.0, conviction))
        return AdvocateArgument(
            side="BEARISH",
            conviction_score=round(conviction, 1),
            primary_thesis="Short execution or downside preservation favored by structural resistance.",
            supporting_points=points,
            identified_risks=risks,
            quantitative_metrics=metrics,
        )


class MultiAgentDebateEngine:
    """
    Orchestrates the dialectical debate between Bullish and Bearish Advocates,
    calculates consensus margin, and applies statistical confidence gating.
    """

    def __init__(self, confidence_threshold: float = 75.0, min_margin: float = 20.0,
                 veto_enabled: bool = False):
        """
        Parameters
        ----------
        veto_enabled : bool
            حق النقض على التنفيذ. **معطّل افتراضياً عن قصد** بعد معايرة بالبيانات
            (backend/cascade_calibration.py على 500 صفقة حقيقية مربوطة بنتائج):
              • العتبتان الحاليتان (هامش≥20 وثقة≥75) ترفضان 95.6% من الصفقات.
              • المجموعة التي كان يُجيزها أداؤها **أسوأ** من التي يرفضها:
                22 صفقة بنسبة فوز 54.5% مقابل 75.1% للمرفوضة.
              • الثقة 75 فوق المئين 90 للسلّم (الوسيط 45-50 والأقصى 80) — أي
                أنها عتبة لا يبلغها السلّم عملياً.
              • لا زوج عتبات أضاف قيمة خارج العيّنة: أفضل زوج على التدريب
                خسر 83.95$ على الاختبار.
            تبقى المناظرة كاملة (الرأيان، الهامش، الحُكم) كمعلومة تُسجَّل وتُقاس،
            ويسقط حق النقض غير المسنَد.
        """
        self.confidence_threshold = confidence_threshold
        self.min_margin = min_margin
        self.veto_enabled = veto_enabled
        self.bull_advocate = BullishAdvocate()
        self.bear_advocate = BearishAdvocate()

    def conduct_debate(self, symbol: str, context: Dict[str, Any]) -> DebateSessionResult:
        """
        Runs the full debate cycle across both advocates.
        """
        bull_arg = self.bull_advocate.present_case(context)
        bear_arg = self.bear_advocate.present_case(context)

        # Margin of dominance
        dominance = bull_arg.conviction_score - bear_arg.conviction_score

        # Determine dominant side and evaluate against threshold
        if dominance >= self.min_margin and bull_arg.conviction_score >= self.confidence_threshold:
            verdict = DebateVerdict.APPROVED_BUY
            permitted = True
            rationale = (
                f"BULLISH CONSENSUS: Bull advocate dominated (+{dominance:.1f}%) with {bull_arg.conviction_score}% "
                f"conviction exceeding threshold ({self.confidence_threshold}%)."
            )
            confidence = bull_arg.conviction_score

        elif dominance <= -self.min_margin and bear_arg.conviction_score >= self.confidence_threshold:
            verdict = DebateVerdict.APPROVED_SELL
            permitted = True
            rationale = (
                f"BEARISH CONSENSUS: Bear advocate dominated (+{abs(dominance):.1f}%) with {bear_arg.conviction_score}% "
                f"conviction exceeding threshold ({self.confidence_threshold}%)."
            )
            confidence = bear_arg.conviction_score

        else:
            verdict = DebateVerdict.REJECTED_HOLD
            permitted = False
            rationale = (
                f"DEBATE STALEMATE: Insufficient statistical consensus. "
                f"Bull={bull_arg.conviction_score}%, Bear={bear_arg.conviction_score}%, "
                f"Margin={dominance:+.1f}%. Capital locked."
            )
            confidence = max(bull_arg.conviction_score, bear_arg.conviction_score)

        # المعايرة: الحُكم يُحفظ كمعلومة، ويسقط حق النقض إلا إن فُعّل صراحةً
        veto_applied = not permitted
        if not self.veto_enabled:
            permitted = True

        return DebateSessionResult(
            symbol=symbol,
            verdict=verdict,
            consensus_confidence=round(confidence, 1),
            threshold_required=self.confidence_threshold,
            margin_of_dominance=round(dominance, 1),
            bullish_argument=bull_arg,
            bearish_argument=bear_arg,
            synthesis_rationale=rationale,
            execution_permitted=permitted,
            veto_applied=veto_applied,
        )
