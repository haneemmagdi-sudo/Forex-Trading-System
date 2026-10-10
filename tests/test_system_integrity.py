"""
============================================================
test_system_integrity.py — وحدة الاختبارات الشاملة للنظام
============================================================
تختبر:
1. معادلات المؤشرات الفنية (RSI, ATR, SMC Order Blocks, FVG)
2. مدير المخاطر وتصفية اللوت والـ Drawdown
3. مجلس التصويت (Voting Engine) ودمج الإشارات
4. الربط والاستدعاءات بين المكونات
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np

# إدراج مسار backend وجذر المشروع
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from backend.core.indicators import TechnicalIndicators, IndicatorValues
from backend.core.risk_manager import RiskManager
from backend.core.voting_engine import VotingEngine
from backend.core.fsm_engine import FSMResult, Regime


class TestSystemIntegrity(unittest.TestCase):

    def setUp(self):
        self.indicators = TechnicalIndicators()
        self.risk_manager = RiskManager()
        self.voting_engine = VotingEngine()

        # إنشاء بيانات OHLCV وهمية لاختبار المؤشرات (100 شمعة)
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100, freq="1h")
        base_price = 1.0850 + np.cumsum(np.random.randn(100) * 0.0005)
        highs = base_price + np.random.rand(100) * 0.0010
        lows = base_price - np.random.rand(100) * 0.0010
        opens = base_price + (np.random.rand(100) - 0.5) * 0.0005
        closes = base_price + (np.random.rand(100) - 0.5) * 0.0005

        self.df = pd.DataFrame({
            "time": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": np.random.randint(100, 1000, 100)
        })

    def test_technical_indicators_calculation(self):
        """اختبار حساب جميع المؤشرات الفنية ببيانات صحيحة"""
        iv = self.indicators.calculate(self.df, spread=1.2)

        self.assertTrue(iv.is_valid(), "المؤشرات الفنية يجب أن تكون صالحة")
        self.assertGreater(iv.close, 0)
        self.assertGreater(iv.atr, 0)
        self.assertGreaterEqual(iv.rsi, 0)
        self.assertLessEqual(iv.rsi, 100)
        self.assertIsNotNone(iv.ema)
        self.assertIsNotNone(iv.macd)

    def test_smc_detection(self):
        """اختبار رصد Order Blocks و Fair Value Gaps"""
        iv = self.indicators.calculate(self.df, spread=1.0)
        self.assertIsInstance(iv.smc_bullish_ob, bool)
        self.assertIsInstance(iv.smc_bearish_ob, bool)
        self.assertIsInstance(iv.smc_bullish_fvg, bool)
        self.assertIsInstance(iv.smc_bearish_fvg, bool)

    def test_risk_manager_lot_calculation_eurusd(self):
        """اختبار حساب اللوت والـ SL/TP لزوج EURUSD (5 أرقام)"""
        trade_params = self.risk_manager.calc_trade_params(
            symbol="EURUSD",
            direction="BUY",
            entry=1.0850,
            atr=0.0015,
            balance=10000.0,
            pip_value=10.0,
            digits=5
        )

        self.assertTrue(trade_params.valid)
        self.assertGreater(trade_params.lot_size, 0)
        self.assertGreater(trade_params.sl_pips, 0)
        self.assertGreater(trade_params.tp_pips, 0)
        
        # إذا كان use_dynamic_sl مفعل تكون أسعار SL/TP أكبر من 0
        if self.risk_manager.cfg.get("use_dynamic_sl", True):
            self.assertLess(trade_params.sl_price, trade_params.entry_price)
            self.assertGreater(trade_params.tp_price, trade_params.entry_price)

    def test_risk_manager_lot_calculation_usdjpy(self):
        """اختبار حساب اللوت والـ SL/TP لزوج USDJPY (3 أرقام)"""
        trade_params = self.risk_manager.calc_trade_params(
            symbol="USDJPY",
            direction="SELL",
            entry=155.20,
            atr=0.25,
            balance=10000.0,
            pip_value=6.7,
            digits=3
        )

        self.assertTrue(trade_params.valid)
        self.assertGreater(trade_params.lot_size, 0)
        self.assertGreater(trade_params.sl_pips, 0)
        self.assertGreater(trade_params.tp_pips, 0)

        if self.risk_manager.cfg.get("use_dynamic_sl", True):
            self.assertGreater(trade_params.sl_price, trade_params.entry_price)
            self.assertLess(trade_params.tp_price, trade_params.entry_price)

    def test_drawdown_protection(self):
        """اختبار حماية الـ Drawdown عند انخفاض Equity"""
        # حالة طبيعية
        norm = self.risk_manager.check_dd_protection(balance=10000, equity=9800)
        self.assertTrue(norm["ok"])
        self.assertEqual(norm["mode"], "NORMAL")

        # حالة إيقاف طوارئ (تجاوز 10% هبوط)
        emergency = self.risk_manager.check_dd_protection(balance=10000, equity=8800)
        self.assertFalse(emergency["ok"])
        self.assertEqual(emergency["mode"], "EMERGENCY_STOP")

    def test_voting_engine_evaluation(self):
        """اختبار محرك التصويت للأصوات الـ 9"""
        iv = self.indicators.calculate(self.df, spread=1.0)
        dummy_fsm = FSMResult(
            regime=Regime.STRONG_TREND,
            label="STRONG TREND",
            adx=30.0,
            atr=0.0015,
            atr_normalized=0.15,
            is_trending=True,
            is_ranging=False,
            is_chaos=False,
            trade_allowed=True,
            vote_weights={}
        )
        res = self.voting_engine.vote(iv, dummy_fsm)

        self.assertIn(res.direction, ["BUY", "SELL", "NO_TRADE", "WEAK_BUY", "WEAK_SELL"])
        self.assertGreaterEqual(res.confidence, 0.0)
        self.assertIn("smc", res.votes)
        self.assertIn("rsi", res.votes)
        self.assertIn("ema", res.votes)


if __name__ == "__main__":
    unittest.main()
