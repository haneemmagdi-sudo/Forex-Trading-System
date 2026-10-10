"""
============================================================
risk_manager.py — إدارة المخاطر الكاملة
============================================================
حساب حجم اللوت، SL، TP، حماية DD، Partial Close
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dataclasses import dataclass
from typing import Optional
from loguru import logger
from config import STRATEGY


@dataclass
class TradeParams:
    """معاملات الصفقة المحسوبة"""
    lot_size:   float
    entry_price:float
    sl_price:   float
    tp_price:   float
    sl_pips:    float
    tp_pips:    float
    risk_usd:   float
    rr_ratio:   float
    valid:      bool
    reason:     str = ""


class RiskManager:
    """مدير المخاطر — يحسب اللوت والـ SL/TP بدقة"""

    def __init__(self):
        self.cfg = STRATEGY

    def calc_trade_params(
        self,
        symbol:     str,
        direction:  str,
        entry:      float,
        atr:        float,
        balance:    float,
        pip_value:  float,
        digits:     int = 5,
    ) -> TradeParams:
        """
        حساب كامل معاملات الصفقة:
        - SL = Entry ± ATR × SL_multiplier
        - TP = Entry ± SL_pips × RR_ratio
        - Lot = (Balance × Risk%) / (SL_pips × pip_value)
        """
        if atr <= 0 or balance <= 0 or pip_value <= 0:
            return TradeParams(0, entry, 0, 0, 0, 0, 0, 0, False, "بيانات غير صالحة")

        point     = 0.00001 if digits == 5 else (0.001 if digits == 3 else 0.0001)
        pip_size  = point * 10  # pip = 10 points في الغالب

        sl_distance = atr * self.cfg["sl_atr_multiplier"]
        tp_distance = sl_distance * self.cfg["tp_rr_ratio"]

        if direction == "BUY":
            sl_price = round(entry - sl_distance, digits) if self.cfg.get("use_dynamic_sl", True) else 0.0
            tp_price = round(entry + tp_distance, digits) if self.cfg.get("use_dynamic_sl", True) else 0.0
        else:
            sl_price = round(entry + sl_distance, digits) if self.cfg.get("use_dynamic_sl", True) else 0.0
            tp_price = round(entry - tp_distance, digits) if self.cfg.get("use_dynamic_sl", True) else 0.0

        sl_pips = round(sl_distance / pip_size, 1)
        tp_pips = round(tp_distance / pip_size, 1)

        # حجم اللوت: Risk% من الرصيد / (SL بالنقاط × قيمة النقطة)
        risk_usd = balance * (self.cfg["risk_percent"] / 100)

        # تحديد حجم اللوت (يدوي ثابت أم محسوب بناءً على المخاطرة)
        if self.cfg.get("manual_lot_enabled", False):
            lot_size = self.cfg.get("fixed_lot_size", 0.01)
        else:
            if sl_pips <= 0:
                return TradeParams(0, entry, sl_price, tp_price, sl_pips, tp_pips, 0, 0, False, "SL = 0")
            lot_size = risk_usd / (sl_pips * pip_value)

        # التأكد من أن اللوت لا يقل عن 0.01 (أقل لوت في سوق الفوركس) ولا يتجاوز الحد الأقصى 100.0
        lot_size = round(max(0.01, min(lot_size, 100.0)), 2)
        rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0

        return TradeParams(
            lot_size    = lot_size,
            entry_price = entry,
            sl_price    = sl_price,
            tp_price    = tp_price,
            sl_pips     = sl_pips,
            tp_pips     = tp_pips,
            risk_usd    = round(risk_usd, 2),
            rr_ratio    = round(rr_ratio, 2),
            valid       = True,
        )

    def check_dd_protection(self, balance: float, equity: float) -> dict:
        """
        فحص حماية الـ Drawdown
        يُرجع: {"ok": bool, "mode": str, "dd_pct": float}
        """
        if balance <= 0:
            return {"ok": True, "mode": "NORMAL", "dd_pct": 0.0}

        dd_pct = (balance - equity) / balance * 100
        dd_pct = max(0.0, dd_pct)

        if dd_pct >= self.cfg["max_dd_percent"]:
            return {"ok": False, "mode": "EMERGENCY_STOP", "dd_pct": dd_pct}
        elif dd_pct >= self.cfg["soft_dd_percent"]:
            return {"ok": True, "mode": "SOFT_STOP", "dd_pct": dd_pct}
        elif dd_pct >= self.cfg["hedge_dd_percent"]:
            return {"ok": True, "mode": "HEDGE_MODE", "dd_pct": dd_pct}
        else:
            return {"ok": True, "mode": "NORMAL", "dd_pct": dd_pct}

    def should_breakeven(self, direction: str, entry: float, current: float, pip_size: float) -> bool:
        """هل يجب نقل SL لنقطة التعادل؟"""
        profit_pips = (current - entry) / pip_size if direction == "BUY" else (entry - current) / pip_size
        return profit_pips >= self.cfg["breakeven_pips"]

    def calc_trailing_sl(self, direction: str, current: float, atr: float, pip_size: float) -> float:
        """حساب Trailing Stop"""
        trail_distance = atr * self.cfg["trail_atr_multiplier"]
        if direction == "BUY":
            return round(current - trail_distance, 5)
        else:
            return round(current + trail_distance, 5)

    def should_partial_close(self, level: int, direction: str, entry: float, current: float, pip_size: float) -> bool:
        """هل يجب الإغلاق الجزئي عند مستوى معين؟"""
        profit_pips = (current - entry) / pip_size if direction == "BUY" else (entry - current) / pip_size
        thresholds = {
            1: self.cfg["partial_tp_l1_pips"],
            2: self.cfg["partial_tp_l2_pips"],
            3: self.cfg["partial_tp_l3_pips"],
        }
        return profit_pips >= thresholds.get(level, 999)

    def partial_close_ratio(self, level: int) -> float:
        """نسبة الإغلاق لكل مستوى"""
        return {1: 0.30, 2: 0.50, 3: 0.70}.get(level, 0.30)

    def check_spread(self, spread: float) -> bool:
        """هل السبريد مقبول للتداول؟"""
        return spread <= self.cfg["max_spread_pips"]
