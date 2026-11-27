"""
tests/test_phase1_security.py — المرحلة 1: الأمان ومسار التنفيذ
=============================================================
1. كل عملية تغيّر شيئاً تتطلب API_TOKEN (HTTP و WebSocket) وتفشل مغلقة.
2. الويب هوك مرفوض دون سر.
3. التنفيذ اليدوي: مطفأ افتراضياً، لا يمر دون وقف خسارة، ويمر عبر SafeExecutionGateway.
4. تحليل بلا بيانات سوق يعيد HOLD بلا أسعار.
لا شبكة ولا MT5 ولا استدعاء LLM: كل الأطراف الخارجية مُحاكاة.
"""
import asyncio
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.agents.tradingagents_bridge import TradingAgentsBridge
from core.safe_execution_gateway import SafeExecutionGateway
from models.database import Base, Trade

TOKEN = "test-token"
SECRET = "test-webhook-secret"
AUTH = {"X-API-Token": TOKEN}
PROTECTED = [
    ("/api/agents/chat", {"agent": "MarketAnalyst", "message": "x"}),
    ("/api/ml/train-now", None),
    ("/api/tradingagents/analyze", {"symbol": "EURUSD"}),
    ("/api/tradingagents/execute", {"symbol": "EURUSD", "direction": "BUY", "sl": 1.07, "user_confirmed": True}),
]
ORDER = {"symbol": "EURUSD", "direction": "BUY", "lot_size": 0.02, "sl": 1.07, "tp": 1.10, "user_confirmed": True}


def env(**values):
    return patch.dict(os.environ, values)


class TestApiToken(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_protected_endpoints_reject_missing_and_wrong_token(self):
        with env(API_TOKEN=TOKEN):
            for url, body in PROTECTED:
                for headers in ({}, {"X-API-Token": "wrong"}):
                    with self.subTest(url=url, headers=headers):
                        self.assertEqual(self.client.post(url, json=body, headers=headers).status_code, 401)

    def test_protected_endpoints_disabled_without_configured_token(self):
        for configured in ("", "your_api_token_here"):
            with env(API_TOKEN=configured):
                for url, body in PROTECTED:
                    with self.subTest(url=url, configured=configured):
                        response = self.client.post(url, json=body, headers={"X-API-Token": configured or "x"})
                        self.assertEqual(response.status_code, 503)

    def test_websocket_command_without_token_is_rejected(self):
        agent = MagicMock()
        agent.pause = AsyncMock()
        agent.get_state.return_value = {"status": "RUNNING"}
        with env(API_TOKEN=TOKEN), patch("backend.main.analyst", agent):
            with self.client.websocket_connect("/ws") as ws:
                self.assertEqual(ws.receive_json()["topic"], "system_status")
                ws.send_json({"action": "pause", "agent": "MarketAnalyst"})
                self.assertEqual(ws.receive_json()["topic"], "command_rejected")
                agent.pause.assert_not_awaited()

                ws.send_json({"action": "pause", "agent": "MarketAnalyst", "token": TOKEN})
                self.assertEqual(ws.receive_json()["topic"], "system_status")
                agent.pause.assert_awaited_once()


class TestWebhookSecret(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def post(self, **payload):
        return self.client.post("/api/webhook/tradingview", json={"symbol": "EURUSD", "action": "BUY", **payload})

    def test_disabled_without_configured_secret(self):
        for configured in ("", "your_webhook_secret_here"):
            with env(WEBHOOK_SECRET=configured):
                self.assertEqual(self.post(secret=configured).status_code, 503)

    def test_missing_or_wrong_secret_rejected_before_any_market_access(self):
        with env(WEBHOOK_SECRET=SECRET), patch("backend.main.mt5.get_ohlcv") as ohlcv:
            for payload in ({}, {"secret": ""}, {"secret": "wrong"}, {"secret": 123}):
                with self.subTest(payload=payload):
                    self.assertEqual(self.post(**payload).status_code, 401)
            ohlcv.assert_not_called()

    def test_correct_secret_reaches_validation(self):
        with env(WEBHOOK_SECRET=SECRET), \
             patch("backend.main.inst_bridge", MagicMock()), \
             patch("backend.main.mt5.get_ohlcv", return_value=None):
            response = self.post(secret=SECRET)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "REJECTED")


class TestManualExecutionEndpoint(unittest.TestCase):

    def setUp(self):
        self.executor = MagicMock()
        self.executor.gateway.execute_signal = AsyncMock(return_value={"success": False, "reason": "Spread too wide"})
        for patcher in (
            env(API_TOKEN=TOKEN),
            patch("backend.main.executor", self.executor),
            patch("backend.main.mt5.get_open_positions", return_value=[]),
            patch("backend.main.mt5.open_trade"),
        ):
            mocked = patcher.start()
            self.addCleanup(patcher.stop)
        self.open_trade = mocked
        self.client = TestClient(app, headers=AUTH)

    def post(self, enabled=True, **changes):
        with patch.dict("backend.main.FEATURES", {"tradingagents_execution": enabled}):
            return self.client.post("/api/tradingagents/execute", json={**ORDER, **changes})

    def test_switch_off_blocks_execution(self):
        self.assertEqual(self.post(enabled=False).status_code, 403)
        self.executor.gateway.execute_signal.assert_not_awaited()

    def test_order_without_stop_loss_rejected(self):
        for sl in (None, 0, -1.0):
            with self.subTest(sl=sl):
                self.assertEqual(self.post(sl=sl).status_code, 400)
        self.executor.gateway.execute_signal.assert_not_awaited()

    def test_order_goes_through_gateway_only(self):
        data = self.post().json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Spread too wide")
        kwargs = self.executor.gateway.execute_signal.await_args.kwargs
        self.assertEqual(
            (kwargs["symbol"], kwargs["direction"], kwargs["stop_loss"], kwargs["take_profit"], kwargs["max_lot"]),
            ("EURUSD", "BUY", 1.07, 1.10, 0.02),
        )
        self.open_trade.assert_not_called()

    def test_max_open_trades_enforced(self):
        with patch("backend.main.mt5.get_open_positions", return_value=[{}] * 100):
            self.assertFalse(self.post().json()["success"])
        self.executor.gateway.execute_signal.assert_not_awaited()


class TestGatewayManualOrder(unittest.TestCase):
    """البوابة الحقيقية فوق موصّل مُحاكى وقاعدة بيانات في الذاكرة."""

    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        patcher = patch("core.safe_execution_gateway.SessionLocal", self.Session)
        patcher.start()
        self.addCleanup(patcher.stop)

        bars = pd.DataFrame({
            "open": [1.08] * 100, "high": [1.081] * 100, "low": [1.079] * 100,
            "close": [1.08] * 100, "volume": [100.0] * 100,
        })
        self.mt5 = MagicMock()
        self.mt5._use_yfinance = True
        self.mt5.get_account.return_value = {"balance": 10000.0, "equity": 10000.0, "free_margin": 10000.0, "leverage": 100}
        self.mt5.get_tick.return_value = {"ask": 1.0800, "bid": 1.0798, "spread": 0.2}
        self.mt5.get_ohlcv.return_value = bars
        self.mt5.get_digits.return_value = 5
        self.mt5.get_pip_value.return_value = 10.0

        self.gateway = SafeExecutionGateway(self.mt5, orchestrator=MagicMock())
        self.gateway.bus = MagicMock()
        self.gateway.bus.emit_trade_opened = AsyncMock()
        self.gateway._trace_position_loop = AsyncMock()
        self.gateway._record_trade_vector = MagicMock()

    def run_order(self, **kwargs):
        return asyncio.run(self.gateway.execute_signal(
            symbol="EURUSD", rf_prediction=None, lstm_delta=None, dqn_q_values=None,
            sentiment_score=None, fsm_regime=None, source="TA_MANUAL", **kwargs,
        ))

    def test_user_levels_applied_lot_capped_and_trade_saved(self):
        with patch.dict(self.gateway.risk.cfg, {"manual_lot_enabled": False, "risk_percent": 1.0}):
            res = self.run_order(direction="BUY", stop_loss=1.0750, take_profit=1.0900, max_lot=0.02)
        self.assertTrue(res["success"], res)
        self.assertEqual((res["sl"], res["tp"], res["lot"], res["mode"]), (1.0750, 1.0900, 0.02, "PAPER"))
        trade = self.Session().query(Trade).one()
        self.assertEqual((trade.sl_price, trade.lot_size, trade.comment), (1.0750, 0.02, "TA_MANUAL_BUY"))
        self.assertIsNone(trade.fsm_regime)
        self.gateway._record_trade_vector.assert_not_called()

    def test_wrong_side_stop_loss_or_take_profit_never_routed(self):
        self.gateway._route_order = MagicMock()
        cases = [
            dict(direction="BUY", stop_loss=1.0900),
            dict(direction="SELL", stop_loss=1.0700),
            dict(direction="BUY", stop_loss=1.0750, take_profit=1.0700),
            dict(direction="SELL", stop_loss=1.0850, take_profit=1.0900),
        ]
        for case in cases:
            with self.subTest(**case):
                self.assertFalse(self.run_order(**case)["success"])
        self.gateway._route_order.assert_not_called()


class TestNoMarketData(unittest.TestCase):

    NO_DATA = {"price": 0.0, "rsi": 50.0, "macd": 0.0, "macd_signal": 0.0, "sma20": 0.0,
               "sma50": 0.0, "atr": 0.0, "trend": "-", "data_points": 0, "data_available": False}

    def test_analysis_without_data_is_hold_without_prices(self):
        bridge = TradingAgentsBridge()
        today = datetime.now().strftime("%Y-%m-%d")
        with patch.object(bridge, "_fetch_technical_snapshot", return_value=self.NO_DATA), \
             patch.object(bridge, "_save_run"), \
             env(GEMINI_API_KEY="fake-key", TRADINGAGENTS_FORCE_SIMULATOR="false"), \
             patch.dict(sys.modules, {"tradingagents.graph.trading_graph": MagicMock()}) as modules:
            result = bridge.analyze("EURUSD", today)
            modules["tradingagents.graph.trading_graph"].TradingAgentsGraph.assert_not_called()
        self.assertFalse(result["data_available"])
        self.assertIsNone(result["current_price"])
        decision = result["decision"]
        self.assertEqual((decision["action"], decision["conviction"]), ("HOLD", 0))
        self.assertIsNone(decision["suggested_sl"])
        self.assertIsNone(decision["suggested_tp"])


if __name__ == "__main__":
    unittest.main()
