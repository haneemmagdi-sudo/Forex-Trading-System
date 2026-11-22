"""
tests/test_tradingagents_bridge.py — اختبارات جسر إطار عمل TradingAgents
التحقق من:
1. تسوية وتطبيع أسماء الأصول (فوركس، كريبتو، أسهم، مؤشرات).
2. حماية Anti-Lookahead ومنع التواريخ المستقبلية.
3. بنية التقارير المستخرجة وضمان عدم التنفيذ التلقائي (Advisory Only).
"""
import unittest
from datetime import datetime, timedelta
import os
import sys

# ضمان مسار الاستيراد
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.agents.tradingagents_bridge import (
    normalize_symbol,
    validate_trade_date,
    TradingAgentsBridge,
)


class TestTradingAgentsBridge(unittest.TestCase):

    def test_symbol_normalization_forex(self):
        yf_sym, mt5_sym, asset = normalize_symbol("EURUSD")
        self.assertEqual(yf_sym, "EURUSD=X")
        self.assertEqual(mt5_sym, "EURUSD")
        self.assertEqual(asset, "forex")

        yf_sym, mt5_sym, asset = normalize_symbol("GBPUSD=X")
        self.assertEqual(yf_sym, "GBPUSD=X")
        self.assertEqual(mt5_sym, "GBPUSD")
        self.assertEqual(asset, "forex")

    def test_symbol_normalization_crypto(self):
        yf_sym, mt5_sym, asset = normalize_symbol("BTCUSD")
        self.assertEqual(yf_sym, "BTC-USD")
        self.assertEqual(mt5_sym, "BTCUSD")
        self.assertEqual(asset, "crypto")

        yf_sym, mt5_sym, asset = normalize_symbol("ETH-USD")
        self.assertEqual(yf_sym, "ETH-USD")
        self.assertEqual(mt5_sym, "ETHUSD")
        self.assertEqual(asset, "crypto")

    def test_symbol_normalization_stock(self):
        yf_sym, mt5_sym, asset = normalize_symbol("AAPL")
        self.assertEqual(yf_sym, "AAPL")
        self.assertEqual(mt5_sym, "AAPL")
        self.assertEqual(asset, "stock")

    def test_symbol_normalization_index(self):
        yf_sym, mt5_sym, asset = normalize_symbol("^GSPC")
        self.assertEqual(yf_sym, "^GSPC")
        self.assertEqual(asset, "index")

        yf_sym, mt5_sym, asset = normalize_symbol("SPY")
        self.assertEqual(yf_sym, "SPY")

    def test_anti_lookahead_validation(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        valid_date = validate_trade_date(today_str)
        self.assertEqual(valid_date, today_str)

        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        self.assertEqual(validate_trade_date(past_date), past_date)

        # منع قراءة التواريخ المستقبلية
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        with self.assertRaises(ValueError):
            validate_trade_date(future_date)

    def test_bridge_analysis_structure_and_no_auto_execution(self):
        bridge = TradingAgentsBridge()
        result = bridge.analyze_deterministic_or_simulated(
            symbol="EURUSD",
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            asset_type="forex"
        )

        self.assertIn("ticker", result)
        self.assertIn("trade_date", result)
        self.assertIn("analyst_reports", result)
        self.assertIn("debate", result)
        self.assertIn("risk_management", result)
        self.assertIn("decision", result)

        decision = result["decision"]
        self.assertIn(decision["action"], ["BUY", "SELL", "HOLD"])
        self.assertIn("conviction", decision)

        # التأكد الصارم من عدم التنفيذ التلقائي
        self.assertEqual(result.get("executed_on_mt5"), False)
        self.assertEqual(result.get("requires_user_approval"), True)
        self.assertEqual(result.get("anti_lookahead_active"), True)


if __name__ == "__main__":
    unittest.main()
