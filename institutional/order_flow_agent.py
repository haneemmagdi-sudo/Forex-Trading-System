"""
==============================================================================
agents/order_flow_agent.py — Microstructure & Order Flow Agent
==============================================================================
Module  : Microstructure, CVD & Liquidity Absorption Agent
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Analyzes Level 2 Market Depth (L2 DOM), Cumulative Volume Delta (CVD),
and institutional liquidity footprints to verify genuine absorption before
triggering an entry order.

Core Capabilities:
1. Cumulative Volume Delta (CVD):
   Measures aggressor buyer vs. aggressor seller delta across candles and ticks.
2. Absorption Detection:
   Identifies large institutional limit orders absorbing market participants
   (e.g., high volume at swing low with zero downward progress).
3. Liquidity Sweep & Stop Hunt Detection:
   Filters out retail stop runs (false breakouts) from true institutional breaks.
4. Order Block Quality Score:
   Scores the institutional validity of SMC order blocks.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("institutional_mas.order_flow")


class AbsorptionType(str, Enum):
    BULLISH_ABSORPTION = "BULLISH_ABSORPTION"  # Aggressive selling absorbed by institutional bids
    BEARISH_ABSORPTION = "BEARISH_ABSORPTION"  # Aggressive buying absorbed by institutional asks
    NONE               = "NONE"


@dataclass
class OrderFlowValidationResult:
    """Output from the Microstructure & Order Flow Agent."""
    symbol: str
    cvd_slope: float                    # Positive = buying delta, Negative = selling delta
    cvd_divergence: str                 # "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "CONVERGENT", "NONE"
    absorption_detected: AbsorptionType
    absorption_strength: float          # 0.0 to 100.0%
    liquidity_sweep: bool               # True if a liquidity pool was purged
    sweep_direction: Optional[str]      # "HIGH_SWEEP" (bearish trap), "LOW_SWEEP" (bullish trap)
    order_block_validated: bool
    order_flow_confidence: float        # 0.0 to 100.0%
    is_valid_entry: bool                # Absolute validation flag
    veto_reason: Optional[str] = None
    score_passed: bool = False          # هل تجاوزت الدرجة العتبة أصلاً
    veto_applied: bool = False          # هل مُنع الدخول فعلاً (يعتمد على veto_enabled)


class OrderFlowMicrostructureAgent:
    """
    Microstructure & Order Flow Agent.
    Validates liquidity quality, absorbs fake breakouts, and calculates CVD.
    """

    def __init__(
        self,
        absorption_volume_factor: float = 1.6,
        min_order_flow_confidence: float = 65.0,
        veto_enabled: bool = False,
    ):
        """
        Parameters
        ----------
        veto_enabled : bool
            حق النقض على الدخول. **معطّل افتراضياً عن قصد** بعد معايرة بالبيانات
            (backend/order_flow_calibration.py على 500 صفقة حقيقية مربوطة بنتائج):
              • الرفض عند العتبة 65 كان يُزيل 421.72$ من أصل 447.55$ ربح (94%).
              • قاعدة «الفخ» (SELL بعد LOW_SWEEP) رفضت أفضل مجموعة في النظام:
                43 صفقة، فوز 74.4%، متوسط +1.891$ مقابل +0.895$ للمتوسط العام.
              • الدرجة معكوسة الاتجاه: شريحة 0-55 متوسطها +1.092$ مقابل +0.833$
                لشريحة 70-100 (ونسبة فوز أدنى 64.5%).
              • لا عتبة أضافت قيمة خارج العيّنة: أفضل عتبة على نصف التدريب
                خسرت 30.46$ على نصف الاختبار.
              • مكوّن الامتصاص لم يُفعَّل إطلاقاً في البيانات (حجم غير حقيقي).
            تبقى الدرجة محسوبة ومُعادة كمعلومة (تشترك في المناظرة والقياس)،
            ويُفعَّل الفيتو صراحةً فقط عند توفّر حجم تدفق حقيقي وبيانات تُظهر
            قدرة تمييزية موجبة.
        """
        self.absorption_volume_factor = absorption_volume_factor
        self.min_order_flow_confidence = min_order_flow_confidence
        self.veto_enabled = veto_enabled

    def calculate_cvd(
        self,
        closes: List[float],
        opens: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
    ) -> Tuple[List[float], float]:
        """
        Estimates Cumulative Volume Delta (CVD) using bar-level tick volume decomposition:
        Delta = Volume * ((Close - Low) - (High - Close)) / (High - Low)
        """
        cvd_series = []
        cumulative_delta = 0.0

        for o, h, l, c, v in zip(opens, highs, lows, closes, volumes):
            spread = max(h - l, 1e-6)
            # Buy volume proxy vs sell volume proxy (close location value)
            clv = ((c - l) - (h - c)) / spread  # Between -1.0 and +1.0
            delta = v * clv
            cumulative_delta += delta
            cvd_series.append(cumulative_delta)

        # Calculate CVD slope over the last 5 bars
        if len(cvd_series) >= 5:
            cvd_slope = cvd_series[-1] - cvd_series[-5]
        else:
            cvd_slope = 0.0

        return cvd_series, cvd_slope

    def detect_absorption(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
    ) -> Tuple[AbsorptionType, float]:
        """
        Detects Institutional Liquidity Absorption:
        Occurs when volume spikes (> 1.6x baseline) but price range is compressed,
        or when price fails to close in the direction of the aggressive volume.
        """
        if len(volumes) < 20:
            return AbsorptionType.NONE, 0.0

        avg_vol = sum(volumes[-20:-1]) / 19.0
        if avg_vol <= 0:
            # لا خط أساس للحجم (مزوّدو البيانات المجانية يعطون حجماً صفرياً
            # لأزواج الفوركس) — لا يمكن حساب الامتصاص، فنُعيد NONE بدل
            # الانقسام على صفر الذي كان يُسقط التقييم بالكامل.
            return AbsorptionType.NONE, 0.0
        last_vol = volumes[-1]
        last_high = highs[-1]
        last_low = lows[-1]
        last_close = closes[-1]
        rng = max(last_high - last_low, 1e-6)

        # Check for volume surge
        if last_vol >= (avg_vol * self.absorption_volume_factor):
            # Check upper/lower wick rejection
            upper_wick = last_high - max(last_close, closes[-2])
            lower_wick = min(last_close, closes[-2]) - last_low

            # Bullish absorption: Huge volume pushed down, but lower wick absorbed it
            if lower_wick >= (0.5 * rng):
                strength = min(100.0, (last_vol / avg_vol) * 45.0)
                return AbsorptionType.BULLISH_ABSORPTION, strength

            # Bearish absorption: Huge volume pushed up, but upper wick rejected it
            if upper_wick >= (0.5 * rng):
                strength = min(100.0, (last_vol / avg_vol) * 45.0)
                return AbsorptionType.BEARISH_ABSORPTION, strength

        return AbsorptionType.NONE, 0.0

    def detect_liquidity_sweep(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        lookback: int = 20,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if previous swing highs/lows were swept (Stop Run / Turtle Soup pattern).
        """
        if len(highs) < lookback + 2:
            return False, None

        prev_swing_high = max(highs[-(lookback + 2) : -2])
        prev_swing_low = min(lows[-(lookback + 2) : -2])

        current_high = highs[-1]
        current_low = lows[-1]
        current_close = closes[-1]

        # High Sweep (Retail breakout buyers trapped)
        if current_high > prev_swing_high and current_close < prev_swing_high:
            return True, "HIGH_SWEEP"

        # Low Sweep (Retail breakdown sellers trapped)
        if current_low < prev_swing_low and current_close > prev_swing_low:
            return True, "LOW_SWEEP"

        return False, None

    def validate_setup(
        self,
        symbol: str,
        proposed_action: str,  # "BUY" or "SELL"
        closes: List[float],
        opens: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        has_order_block: bool = True,
    ) -> OrderFlowValidationResult:
        """
        Cumulative validation of Order Flow, CVD, and Absorption.
        Returns full OrderFlowValidationResult with veto power over fake breakouts.
        """
        cvd_series, cvd_slope = self.calculate_cvd(closes, opens, highs, lows, volumes)
        absorption, abs_strength = self.detect_absorption(closes, highs, lows, volumes)
        sweep_detected, sweep_dir = self.detect_liquidity_sweep(highs, lows, closes)

        # Calculate CVD divergence
        price_slope = closes[-1] - closes[-5] if len(closes) >= 5 else 0.0
        cvd_divergence = "NONE"

        if price_slope < 0 and cvd_slope > 0:
            cvd_divergence = "BULLISH_DIVERGENCE"  # Price falling, but aggressive buying accumulating
        elif price_slope > 0 and cvd_slope < 0:
            cvd_divergence = "BEARISH_DIVERGENCE"  # Price rising, but aggressive selling distributing
        elif (price_slope > 0 and cvd_slope > 0) or (price_slope < 0 and cvd_slope < 0):
            cvd_divergence = "CONVERGENT"

        # Confidence Scoring
        confidence = 50.0  # Base line

        if proposed_action == "BUY":
            if cvd_divergence == "BULLISH_DIVERGENCE":
                confidence += 20.0
            elif cvd_slope > 0:
                confidence += 10.0

            if absorption == AbsorptionType.BULLISH_ABSORPTION:
                confidence += 25.0

            if sweep_detected and sweep_dir == "LOW_SWEEP":
                confidence += 20.0  # Liquidity sweep of lows confirmed

            # Penalties
            if absorption == AbsorptionType.BEARISH_ABSORPTION:
                confidence -= 35.0  # Buying into institutional ceiling
            if sweep_detected and sweep_dir == "HIGH_SWEEP":
                confidence -= 40.0  # Buying into top-wick stop hunt

        elif proposed_action == "SELL":
            if cvd_divergence == "BEARISH_DIVERGENCE":
                confidence += 20.0
            elif cvd_slope < 0:
                confidence += 10.0

            if absorption == AbsorptionType.BEARISH_ABSORPTION:
                confidence += 25.0

            if sweep_detected and sweep_dir == "HIGH_SWEEP":
                confidence += 20.0  # Liquidity sweep of highs confirmed

            # Penalties
            if absorption == AbsorptionType.BULLISH_ABSORPTION:
                confidence -= 35.0  # Selling into institutional floor
            if sweep_detected and sweep_dir == "LOW_SWEEP":
                confidence -= 40.0  # Selling into bottom-wick stop hunt

        confidence = max(0.0, min(100.0, confidence))

        # Check veto condition
        score_passed = confidence >= self.min_order_flow_confidence
        is_valid = score_passed
        veto_reason = None

        if not is_valid:
            if proposed_action == "BUY" and sweep_dir == "HIGH_SWEEP":
                veto_reason = "ORDER FLOW VETO: Trap! Buying into HIGH_SWEEP fakeout."
            elif proposed_action == "SELL" and sweep_dir == "LOW_SWEEP":
                veto_reason = "ORDER FLOW VETO: Trap! Selling into LOW_SWEEP fakeout."
            else:
                veto_reason = (
                    f"ORDER FLOW VETO: Confidence ({confidence:.1f}%) below institutional threshold "
                    f"({self.min_order_flow_confidence:.1f}%). Insufficient order absorption."
                )

        # المعايرة: الدرجة تُحفظ كمعلومة، ولا تُمنع الصفقة إلا إن فُعّل الفيتو صراحةً
        veto_applied = self.veto_enabled and not score_passed
        if not self.veto_enabled:
            is_valid = True
            veto_reason = None

        return OrderFlowValidationResult(
            symbol=symbol,
            cvd_slope=round(cvd_slope, 2),
            cvd_divergence=cvd_divergence,
            absorption_detected=absorption,
            absorption_strength=round(abs_strength, 1),
            liquidity_sweep=sweep_detected,
            sweep_direction=sweep_dir,
            order_block_validated=has_order_block,
            order_flow_confidence=round(confidence, 1),
            is_valid_entry=is_valid,
            veto_reason=veto_reason,
            score_passed=score_passed,
            veto_applied=veto_applied,
        )
