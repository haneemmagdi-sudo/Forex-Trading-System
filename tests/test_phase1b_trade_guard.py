"""
tests/test_phase1b_trade_guard.py — حارس فتح الصفقات والتنفيذ اليدوي
=================================================================
1. الحساب غير التجريبي لا تُفتح عليه صفقة إلا مع LIVE_TRADING_ENABLED=true، والإغلاق لا يُمنع.
2. التنفيذ اليدوي لا يقبل إلا تحليلاً حديثاً محفوظاً يطابق الرمز والاتجاه.
3. التنفيذ اليدوي يخضع لحظر الخسائر المتتالية ولمسافة الشبكة مثل التنفيذ الآلي.
لا شبكة ولا MT5: كل الأطراف الخارجية مُحاكاة.
"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from fastapi.testclient import TestClient

from backend.main import app, tradingagents_bridge
from agents.execution_agent import ExecutionAgent
from agents.monitor_agent import MonitorAgent
from config import STRATEGY
from core import mt5_connector, safe_execution_gateway
from core.safe_execution_gateway import SafeExecutionGateway

DEMO, CONTEST, REAL = 0, 1, 2
DONE = 10009


def fake_mt5(trade_mode):
    """واجهة MetaTrader5 مُحاكاة؛ trade_mode=None يعني تعذّر قراءة الحساب."""
    fake = MagicMock()
    fake.ACCOUNT_TRADE_MODE_DEMO = DEMO
    fake.TRADE_RETCODE_DONE = DONE
    fake.account_info.return_value = None if trade_mode is None else SimpleNamespace(trade_mode=trade_mode)
    fake.symbol_info.return_value = SimpleNamespace(visible=True, filling_mode=1, digits=5, volume_min=0.01, volume_step=0.01)
    fake.symbol_info_tick.return_value = SimpleNamespace(ask=1.1002, bid=1.1000)
    fake.positions_get.return_value = [SimpleNamespace(ticket=1, symbol="EURUSD", type=0, volume=0.10, tp=0.0)]
    fake.order_send.return_value = SimpleNamespace(retcode=DONE, order=555, price=1.1002, comment="ok")
    return fake


class LiveConnectorCase(unittest.TestCase):

    def live(self, trade_mode, enabled=False):
        """موصّل في وضع MT5 الحي فوق واجهة مُحاكاة."""
        fake = fake_mt5(trade_mode)
        for patcher in (
            patch.object(mt5_connector, "mt5", fake, create=True),
            patch.object(mt5_connector, "MT5_AVAILABLE", True),
            patch.object(mt5_connector, "LIVE_TRADING_ENABLED", enabled),
            patch.object(safe_execution_gateway, "mt5", fake, create=True),
            patch.object(safe_execution_gateway, "MT5_AVAILABLE", True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        connector = mt5_connector.MT5Connector()
        connector.connected = True
        connector._use_yfinance = False
        return connector, fake

    def open_both_ways(self, connector):
        """المنفذان الوحيدان لفتح صفقة: الموصّل (التحوط) وبوابة التنفيذ (الآلي واليدوي)."""
        gateway = SafeExecutionGateway(connector, orchestrator=MagicMock())
        return (
            connector.open_trade("EURUSD", "BUY", 0.01, sl=1.09, tp=1.12),
            gateway._route_order("EURUSD", "BUY", 0.01, 1.09, 1.12, 1.1002, 5),
        )


class TestLiveTradingSwitch(LiveConnectorCase):

    def test_non_demo_or_unknown_account_is_blocked_when_switch_off(self):
        for trade_mode in (REAL, CONTEST, None):
            with self.subTest(trade_mode=trade_mode):
                connector, fake = self.live(trade_mode)
                for result in self.open_both_ways(connector):
                    self.assertFalse(result["success"], result)
                    self.assertIn("LIVE_TRADING_ENABLED", result["error"])
                fake.order_send.assert_not_called()

    def test_demo_account_trades_with_switch_off(self):
        connector, fake = self.live(DEMO)
        for result in self.open_both_ways(connector):
            self.assertTrue(result["success"], result)
        self.assertEqual(fake.order_send.call_count, 2)

    def test_real_account_trades_only_with_switch_on(self):
        connector, fake = self.live(REAL, enabled=True)
        for result in self.open_both_ways(connector):
            self.assertTrue(result["success"], result)
        self.assertEqual(fake.order_send.call_count, 2)

    def test_account_type_is_read_on_every_order(self):
        connector, fake = self.live(DEMO)
        self.assertTrue(connector.open_trade("EURUSD", "BUY", 0.01, sl=1.09, tp=1.12)["success"])
        fake.account_info.return_value = SimpleNamespace(trade_mode=REAL)  # بُدّل الحساب من داخل الطرفية
        self.assertFalse(connector.open_trade("EURUSD", "BUY", 0.01, sl=1.09, tp=1.12)["success"])
        self.assertEqual(fake.order_send.call_count, 1)

    def test_closing_and_protecting_stay_allowed_on_real_account(self):
        connector, fake = self.live(REAL)
        self.assertTrue(connector.close_position(1))
        self.assertTrue(connector.partial_close(1, 0.5))
        self.assertTrue(connector.modify_sl(1, 1.095))
        self.assertEqual(fake.order_send.call_count, 3)

    def test_paper_mode_is_not_affected(self):
        connector = mt5_connector.MT5Connector()
        connector._use_yfinance = True
        with patch.object(mt5_connector, "LIVE_TRADING_ENABLED", False):
            self.assertIsNone(connector.entry_block_reason())

    def test_blocked_hedge_is_not_logged_as_opened(self):
        mt5 = MagicMock()
        mt5.get_open_positions.return_value = [{"profit": -50.0, "volume": 0.1, "type": "BUY", "symbol": "EURUSD"}]
        mt5.get_tick.return_value = {"ask": 1.1002, "bid": 1.1000}
        mt5.get_digits.return_value = 5
        mt5.open_trade.return_value = {"success": False, "error": "BLOCKED"}
        agent = MonitorAgent.__new__(MonitorAgent)
        agent.mt5 = mt5
        agent.log = AsyncMock()
        asyncio.run(agent._activate_hedge({}))
        messages = [call.args[1] for call in agent.log.await_args_list]
        self.assertEqual(len(messages), 1)
        self.assertIn("BLOCKED", messages[0])

    def test_replay_broker_keeps_the_open_trade_contract(self):
        """وكيل المراقبة يقرأ نتيجة open_trade كقاموس، ووسيط المحاكاة التاريخية يجب أن يعيدها كذلك."""
        path = os.path.join(root_dir, "backtest", "replay_backtest.py")
        spec = importlib.util.spec_from_file_location("replay_backtest_contract", path)
        replay = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = replay
        self.addCleanup(sys.modules.pop, spec.name)
        spec.loader.exec_module(replay)
        broker = replay.SimBroker.__new__(replay.SimBroker)
        broker.magic = 1
        broker.open_position = MagicMock(return_value=7)
        self.assertEqual(broker.open_trade("EURUSD", "BUY", 0.01), {"success": True, "ticket": 7})


def saved_run(**changes):
    run = {
        "run_id": "ta_20260101_120000_EURUSD",
        "mt5_symbol": "EURUSD",
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
        "data_available": True,
        "current_price": 1.08,
        "decision": {"action": "BUY"},
        "created_at_epoch": time.time(),
    }
    run.update(changes)
    return run


class ManualExecutionCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runs = Path(tmp.name)
        self.positions = []

        # ExecutionAgent الحقيقي بقواعده، وبوابة مُحاكاة
        self.executor = ExecutionAgent.__new__(ExecutionAgent)
        self.executor._cascade_blocked_until = None
        self.executor._consecutive_losses = 0
        self.executor.gateway = MagicMock()
        self.executor.gateway.execute_signal = AsyncMock(return_value={
            "success": True, "ticket": 1, "price": 1.08, "lot": 0.01, "sl": 1.07, "tp": 1.10, "mode": "PAPER",
        })
        for patcher in (
            patch.dict(os.environ, {"API_TOKEN": "t"}),
            patch.dict("backend.main.FEATURES", {"tradingagents_execution": True}),
            patch("backend.main.executor", self.executor),
            patch.object(tradingagents_bridge, "runs_dir", self.runs),
            patch("backend.main.mt5.get_open_positions", side_effect=lambda symbol=None: list(self.positions)),
            patch("backend.main.mt5.get_tick", return_value={"ask": 1.0800, "bid": 1.0798, "spread": 0.2}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app, headers={"X-API-Token": "t"})

    def post(self, run=None, **changes):
        run = saved_run() if run is None else run
        (self.runs / f"{run['run_id']}.json").write_text(json.dumps(run), encoding="utf-8")
        body = {"symbol": "EURUSD", "direction": "BUY", "lot_size": 0.01, "sl": 1.07, "tp": 1.10,
                "user_confirmed": True, "run_id": run["run_id"], **changes}
        return self.client.post("/api/tradingagents/execute", json=body)

    def assert_refused(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["success"], response.json())
        self.executor.gateway.execute_signal.assert_not_awaited()

    def assert_sent(self, response):
        self.assertTrue(response.json()["success"], response.json())
        self.executor.gateway.execute_signal.assert_awaited_once()


class TestAnalysisFreshness(ManualExecutionCase):

    def test_fresh_matching_analysis_is_executed(self):
        self.assert_sent(self.post())

    def test_run_id_is_required(self):
        for run_id in (None, ""):
            with self.subTest(run_id=run_id):
                self.assertEqual(self.post(run_id=run_id).status_code, 400)
        self.executor.gateway.execute_signal.assert_not_awaited()

    def test_unknown_or_unsafe_run_id_refused(self):
        outside = self.runs.parent / f"{self.runs.name}_outside.json"
        outside.write_text(json.dumps(saved_run()), encoding="utf-8")
        self.addCleanup(outside.unlink)
        for run_id in ("ta_missing", f"../{outside.stem}", str(outside.with_suffix(""))):
            with self.subTest(run_id=run_id):
                self.assert_refused(self.post(run_id=run_id))

    def test_old_analysis_refused(self):
        self.assert_refused(self.post(run=saved_run(created_at_epoch=time.time() - 16 * 60)))

    def test_age_limit_comes_from_configuration(self):
        with patch("backend.main.TRADINGAGENTS_MAX_ANALYSIS_AGE_MINUTES", 30):
            self.assert_sent(self.post(run=saved_run(created_at_epoch=time.time() - 16 * 60)))

    def test_untrustworthy_creation_time_refused(self):
        for created in (None, "now", time.time() + 3600):
            with self.subTest(created=created):
                self.assert_refused(self.post(run=saved_run(created_at_epoch=created)))

    def test_mismatch_or_unusable_analysis_refused(self):
        # يومان: أقدم من تاريخ اليوم المحلي وتاريخ UTC في أي منطقة زمنية
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        cases = {
            "other symbol": saved_run(mt5_symbol="GBPUSD"),
            "other direction": saved_run(decision={"action": "SELL"}),
            "hold": saved_run(decision={"action": "HOLD"}),
            "no data": saved_run(data_available=False),
            "zero price": saved_run(current_price=0),
            "past trade date": saved_run(trade_date=two_days_ago),
        }
        for name, run in cases.items():
            with self.subTest(name):
                self.assert_refused(self.post(run=run))

    def test_utc_date_accepted_when_local_date_is_ahead(self):
        """بعد منتصف الليل شرق غرينتش يكون تاريخ UTC الذي ترسله الواجهة هو «أمس» محلياً."""
        class LocalClockAhead(datetime):
            @classmethod
            def fromtimestamp(cls, ts, tz=None):
                if tz is None:  # الساعة المحلية متقدمة يوماً كاملاً على UTC
                    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None) + timedelta(days=1)
                return datetime.fromtimestamp(ts, tz)

        utc_today = datetime.now(timezone.utc).date()
        bridge_module = sys.modules[type(tradingagents_bridge).__module__]
        with patch.object(bridge_module, "datetime", LocalClockAhead):
            self.assert_refused(self.post(run=saved_run(trade_date=str(utc_today - timedelta(days=1)))))
            self.assert_sent(self.post(run=saved_run(trade_date=str(utc_today))))

    def test_bridge_stamps_creation_time(self):
        with patch.object(tradingagents_bridge, "_fetch_technical_snapshot", return_value={"price": 0.0, "data_points": 0}):
            result = tradingagents_bridge.analyze_deterministic_or_simulated("EURUSD")
        stored = tradingagents_bridge.get_run(result["run_id"])
        self.assertAlmostEqual(stored["created_at_epoch"], time.time(), delta=10)


class TestManualExecutionRiskRules(ManualExecutionCase):

    def position(self, entry, side="BUY"):
        return {"type": side, "open_price": entry, "open_time": "2026-01-01T00:00:00", "symbol": "EURUSD"}

    def test_consecutive_loss_block_applies(self):
        for _ in range(STRATEGY["cascade_max_losses"]):
            asyncio.run(self.lose())
        self.assert_refused(self.post())

    async def lose(self):
        self.executor.log = AsyncMock()
        await self.executor._on_trade_closed(SimpleNamespace(data={"profit": -1.0}))

    def test_expired_block_is_cleared(self):
        self.executor._cascade_blocked_until = datetime.utcnow().timestamp() - 1
        self.executor._consecutive_losses = 3
        self.assert_sent(self.post())
        self.assertEqual(self.executor._consecutive_losses, 0)

    def test_grid_distance_not_reached_refused(self):
        self.positions = [self.position(1.0810)]  # تراجع 10 نقاط فقط
        self.assert_refused(self.post())

    def test_grid_entry_allowed_after_enough_pullback(self):
        self.positions = [self.position(1.0830)]  # تراجع 30 نقطة
        self.assert_sent(self.post())

    def test_opposite_direction_not_subject_to_grid(self):
        self.positions = [self.position(1.0800, side="SELL")]
        self.assert_sent(self.post())

    def test_refused_when_price_unavailable(self):
        with patch("backend.main.mt5.get_tick", return_value=None):
            self.assert_refused(self.post())


if __name__ == "__main__":
    unittest.main()
