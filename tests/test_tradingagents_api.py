"""
tests/test_tradingagents_api.py — اختبارات نقاط نهاية FastAPI الخاصة بـ TradingAgents وموافقة المستخدم
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import os
import sys

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from fastapi.testclient import TestClient
from backend.main import app


class TestTradingAgentsAPI(unittest.TestCase):

    def setUp(self):
        env = patch.dict(os.environ, {"API_TOKEN": "test-token"})
        env.start()
        self.addCleanup(env.stop)
        switch = patch.dict("backend.main.FEATURES", {"tradingagents_execution": True})
        switch.start()
        self.addCleanup(switch.stop)
        self.client = TestClient(app, headers={"X-API-Token": "test-token"})

    def test_analyze_endpoint(self):
        response = self.client.post("/api/tradingagents/analyze", json={
            "symbol": "EURUSD",
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
            "asset_type": "forex"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        result = data.get("result")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("ticker"), "EURUSD")
        self.assertIn(result.get("decision", {}).get("action"), ["BUY", "SELL", "HOLD"])
        self.assertFalse(result.get("executed_on_mt5"))
        self.assertTrue(result.get("requires_user_approval"))

    def test_history_endpoint(self):
        response = self.client.get("/api/tradingagents/history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("history"), list)

    def test_execute_without_user_confirmation_rejected(self):
        # رفض الأمر إن لم تكن موافقة المستخدم صريحة
        response = self.client.post("/api/tradingagents/execute", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "lot_size": 0.01,
            "user_confirmed": False
        })
        self.assertEqual(response.status_code, 400)

    def test_execute_with_user_confirmation_accepted(self):
        # عند إرسال موافقة المستخدم يمر الأمر عبر بوابة التنفيذ (مُحاكاة هنا)
        executor = MagicMock()
        executor.gateway.execute_signal = AsyncMock(return_value={
            "success": True, "ticket": 9876543, "price": 1.0850,
            "lot": 0.01, "sl": 1.0700, "tp": 1.0950, "mode": "PAPER",
        })
        executor.cascade_block_active.return_value = False
        executor.grid_check.return_value = (True, None, None)
        with patch("backend.main.executor", executor), \
             patch("backend.main.mt5.get_open_positions", return_value=[]), \
             patch("backend.main.mt5.get_tick", return_value={"ask": 1.0850, "bid": 1.0848}), \
             patch("backend.main.tradingagents_bridge.execution_rejection", return_value=None):
            response = self.client.post("/api/tradingagents/execute", json={
                "symbol": "EURUSD",
                "direction": "BUY",
                "lot_size": 0.01,
                "sl": 1.0700,
                "tp": 1.0950,
                "user_confirmed": True,
                "run_id": "ta_test_EURUSD",
            })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("ticket"), 9876543)
        self.assertEqual(data.get("symbol"), "EURUSD")
        self.assertEqual(data.get("mode"), "PAPER")

if __name__ == "__main__":
    unittest.main()
