"""
============================================================
fsm_engine.py — محرك الحالات المحدودة (Finite State Machine)
============================================================
4 حالات: LOW_VOL | HIGH_VOL | SLOW_TREND | STRONG_TREND | CHAOS
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dataclasses import dataclass
from enum import Enum
from core.indicators import IndicatorValues
from config import INDICATORS as IND_CFG


class Regime(str, Enum):
    LOW_VOL_RANGE  = "LOW_VOL_RANGE"
    HIGH_VOL_RANGE = "HIGH_VOL_RANGE"
    SLOW_TREND     = "SLOW_TREND"
    STRONG_TREND   = "STRONG_TREND"
    CHAOS          = "CHAOS"


REGIME_LABELS = {
    Regime.LOW_VOL_RANGE:  "🟡 LOW VOL",
    Regime.HIGH_VOL_RANGE: "⚠️ HIGH VOL",
    Regime.SLOW_TREND:     "🔵 SLOW TREND",
    Regime.STRONG_TREND:   "🚀 STRONG TREND",
    Regime.CHAOS:          "🔴 CHAOS",
}

# أوزان الـ Voting لكل حالة FSM
REGIME_VOTE_WEIGHTS = {
    Regime.LOW_VOL_RANGE: {
        "ema":1.0,"ha":1.5,"macd":0.5,"rsi":1.3,"adx":0.4,
        "ichi":0.8,"smc":1.0,"momentum":0.5,"st":1.0
    },
    Regime.HIGH_VOL_RANGE:{
        "ema":1.0,"ha":2.0,"macd":0.6,"rsi":0.5,"adx":1.4,
        "ichi":0.8,"smc":1.0,"momentum":0.7,"st":1.0
    },
    Regime.SLOW_TREND:    {
        "ema":1.3,"ha":2.0,"macd":0.9,"rsi":0.8,"adx":0.7,
        "ichi":1.2,"smc":1.0,"momentum":0.5,"st":1.0
    },
    Regime.STRONG_TREND:  {
        "ema":1.6,"ha":2.5,"macd":0.6,"rsi":0.4,"adx":0.7,
        "ichi":1.0,"smc":1.0,"momentum":0.9,"st":1.0
    },
    Regime.CHAOS:         {
        "ema":0.4,"ha":1.0,"macd":0.2,"rsi":0.3,"adx":0.3,
        "ichi":0.8,"smc":1.0,"momentum":0.2,"st":1.0
    },
}


@dataclass
class FSMResult:
    regime: Regime
    label:  str
    adx:    float
    atr:    float
    atr_normalized: float  # ATR / EMA * 100
    is_trending:   bool
    is_ranging:    bool
    is_chaos:      bool
    trade_allowed: bool    # هل مسموح بالتداول في هذا الـ Regime؟
    vote_weights:  dict

    def to_dict(self):
        return {
            "regime":        self.regime.value,
            "label":         self.label,
            "adx":           round(self.adx, 2),
            "atr":           round(self.atr, 5),
            "atr_normalized":round(self.atr_normalized, 4),
            "is_trending":   self.is_trending,
            "is_ranging":    self.is_ranging,
            "is_chaos":      self.is_chaos,
            "trade_allowed": self.trade_allowed,
        }


class FSMEngine:
    """
    محرك FSM يحدد حالة السوق بناءً على ADX و ATR و EMA
    ثم يُرجع أوزان التصويت المناسبة
    """

    def __init__(self):
        self.adx_threshold    = IND_CFG["adx_threshold"]  # 25
        self.adx_strong       = 40.0   # ترند قوي
        self.atr_low_mult     = 0.004  # ATR/Price < هذا → تذبذب بطيء
        self.atr_high_mult    = 0.008  # ATR/Price > هذا → تذبذب عالٍ
        self._prev_regime     = None

    def detect(self, iv: IndicatorValues) -> FSMResult:
        """تحديد حالة السوق الحالية"""
        adx = iv.adx
        atr = iv.atr
        ema = iv.ema or iv.close or 1.0

        # نسبة ATR إلى السعر (مؤشر التقلب النسبي)
        atr_norm = (atr / ema) * 100 if ema > 0 else 0.0

        # ── قواعد FSM ──────────────────────────────────────────────
        # CHAOS: ADX مرتفع جداً مع ATR مرتفع (سوق فوضوي)
        if adx > 60 and atr_norm > self.atr_high_mult * 100:
            regime = Regime.CHAOS

        # STRONG_TREND: ADX قوي + اتجاه EMA واضح
        elif adx >= self.adx_strong and abs(iv.ema_angle) > 10:
            regime = Regime.STRONG_TREND

        # SLOW_TREND: ADX فوق المعدل لكن اتجاه بطيء
        elif adx >= self.adx_threshold:
            regime = Regime.SLOW_TREND

        # HIGH_VOL_RANGE: تذبذب مع ATR مرتفع
        elif atr_norm > self.atr_high_mult * 100:
            regime = Regime.HIGH_VOL_RANGE

        # LOW_VOL_RANGE: تذبذب بطيء وهادئ
        else:
            regime = Regime.LOW_VOL_RANGE

        # حالات مسموح بتداولها
        TRADEABLE = {
            Regime.LOW_VOL_RANGE,
            Regime.SLOW_TREND,
            Regime.STRONG_TREND,
        }

        result = FSMResult(
            regime         = regime,
            label          = REGIME_LABELS[regime],
            adx            = adx,
            atr            = atr,
            atr_normalized = atr_norm,
            is_trending    = regime in (Regime.SLOW_TREND, Regime.STRONG_TREND),
            is_ranging     = regime in (Regime.LOW_VOL_RANGE, Regime.HIGH_VOL_RANGE),
            is_chaos       = regime == Regime.CHAOS,
            trade_allowed  = regime in TRADEABLE,
            vote_weights   = REGIME_VOTE_WEIGHTS[regime],
        )

        self._prev_regime = regime
        return result
