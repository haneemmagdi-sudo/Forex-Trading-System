"""
tests/test_basket_magic_filter.py — اختبارات فلتر MAGIC_NUMBERS لهدف ووقف السلة
================================================================================
يتحقق من أن حساب الربح/الخسارة وإغلاق السلة في MonitorAgent و MT5Connector.close_all_positions
يقتصران على صفقات النظام (MAGIC_NUMBERS) ولا يمسّان الصفقات اليدوية (magic=0) أو الخارجية.
التشغيل: PYTHONPATH=. python -m unittest tests/test_basket_magic_filter.py -v
"""
import asyncio
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import STRATEGY, MAGIC_NUMBERS  # noqa: E402
import agents.monitor_agent as mon  # noqa: E402
from core.mt5_connector import MT5Connector  # noqa: E402

LIVE_MAGIC = MAGIC_NUMBERS["live_engine"]
GRID_MAGIC = MAGIC_NUMBERS["grid_engine"]
SHADOW_MAGIC = MAGIC_NUMBERS["shadow_council"]
SYSTEM_MAGICS = set(MAGIC_NUMBERS.values())


class _FakeQuery:
    def filter(self, *a, **k): return self
    def all(self): return []
    def first(self): return None


class _FakeSession:
    def query(self, *a, **k): return _FakeQuery()
    def commit(self): pass
    def close(self): pass


class FakeMagicMT5:
    _use_yfinance = True
    connected = False

    def __init__(self, positions):
        self.positions = list(positions)
        self.closed_tickets = []
        self.close_all_calls = []
        self.sl_calls = []
        self.partial_calls = []

    def get_account(self):
        return {"balance": 1000.0, "equity": 1000.0}

    def get_open_positions(self, symbol=None):
        if symbol:
            return [p for p in self.positions if p["symbol"] == symbol]
        return list(self.positions)

    def get_tick(self, symbol):
        return {"bid": 1.1000, "ask": 1.1000, "spread": 0.0}

    def close_position(self, ticket, comment=""):
        self.closed_tickets.append((ticket, comment))
        self.positions = [p for p in self.positions if p["ticket"] != ticket]
        return True

    def close_all_positions(self, symbol=None, reason="AI_Emergency", magic_numbers=None):
        self.close_all_calls.append((symbol, reason, set(magic_numbers) if magic_numbers is not None else None))
        targets = self.get_open_positions(symbol)
        if magic_numbers is not None:
            allowed = set(magic_numbers)
            targets = [p for p in targets if p.get("magic") in allowed]
        for pos in targets:
            self.close_position(pos["ticket"], comment=reason)

    def modify_sl(self, ticket, new_sl):
        self.sl_calls.append((ticket, new_sl))
        return True

    def partial_close(self, ticket, pct):
        self.partial_calls.append((ticket, pct))
        return True


def _pos(ticket, magic, profit, symbol="EURUSD", direction="BUY", pips=5.0, sl=1.0900):
    entry = 1.1000
    cur = entry + pips * 0.0001 if direction == "BUY" else entry - pips * 0.0001
    return {
        "ticket": ticket, "symbol": symbol, "type": direction, "volume": 0.01,
        "open_price": entry, "current_price": round(cur, 5), "sl": sl, "tp": 0.0,
        "profit": profit, "magic": magic,
    }


class TestBasketMagicFilter(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(mon, "SessionLocal", lambda: _FakeSession())
        p.start()
        self.addCleanup(p.stop)

    def _run_cycle(self, positions, **cfg):
        m = FakeMagicMT5(positions)
        agent = mon.MonitorAgent(m)
        agent._get_db_trade = lambda t: None
        with mock.patch.dict(STRATEGY, cfg):
            asyncio.run(agent.run_cycle())
        return agent, m

    def test_manual_profit_does_not_trigger_basket_target(self):
        """صفقة يدوية رابحة +50$ لا تُطلق هدف السلة (2$) ولا تُغلق."""
        _, m = self._run_cycle([_pos(101, magic=0, profit=50.0)])
        self.assertEqual(m.close_all_calls, [])
        self.assertEqual(m.closed_tickets, [])
        self.assertEqual(len(m.positions), 1)

    def test_manual_loss_does_not_trigger_basket_sl(self):
        """صفقة يدوية خاسرة -50$ لا تُطلق وقف السلة (-20$) ولا تُغلق."""
        _, m = self._run_cycle([_pos(102, magic=0, profit=-50.0)])
        self.assertEqual(m.close_all_calls, [])
        self.assertEqual(m.closed_tickets, [])
        self.assertEqual(len(m.positions), 1)

    def test_manual_profit_cannot_falsely_close_system_trade(self):
        """صفقة يدوية +50$ مع صفقة نظام +0.50$ لا تُطلق هدف السلة 2$."""
        _, m = self._run_cycle([
            _pos(101, magic=0, profit=50.0),
            _pos(201, magic=LIVE_MAGIC, profit=0.50),
        ])
        self.assertEqual(m.close_all_calls, [])
        self.assertEqual(m.closed_tickets, [])
        self.assertEqual(len(m.positions), 2)

    def test_system_basket_target_closes_only_system_trades(self):
        """عند بلوغ صفقات النظام +2.50$ تُغلق صفقات النظام فقط وتبقى اليدوية والخارجية مفتوحة."""
        _, m = self._run_cycle([
            _pos(101, magic=0, profit=-10.0),
            _pos(102, magic=999999, profit=1.0),
            _pos(201, magic=LIVE_MAGIC, profit=1.50),
            _pos(202, magic=GRID_MAGIC, profit=1.20),
        ])
        self.assertEqual(len(m.close_all_calls), 1)
        _, reason, magics = m.close_all_calls[0]
        self.assertEqual(reason, "Target_Reached")
        self.assertEqual(magics, SYSTEM_MAGICS)
        self.assertEqual({t for t, _ in m.closed_tickets}, {201, 202})
        self.assertEqual({p["ticket"] for p in m.positions}, {101, 102})

    def test_system_basket_sl_closes_only_system_trades(self):
        """عند بلوغ خسارة صفقات النظام -25$ تُغلق صفقات النظام فقط وتبقى اليدوية مفتوحة."""
        _, m = self._run_cycle([
            _pos(101, magic=0, profit=15.0),
            _pos(201, magic=LIVE_MAGIC, profit=-12.0),
            _pos(202, magic=SHADOW_MAGIC, profit=-13.0),
        ])
        self.assertEqual(len(m.close_all_calls), 1)
        _, reason, magics = m.close_all_calls[0]
        self.assertEqual(reason, "Basket_SL_Hit")
        self.assertEqual(magics, SYSTEM_MAGICS)
        self.assertEqual({t for t, _ in m.closed_tickets}, {201, 202})
        self.assertEqual({p["ticket"] for p in m.positions}, {101})

    def test_mt5_connector_close_all_positions_magic_filter_and_backward_compat(self):
        """MT5Connector.close_all_positions يفلتر حسب magic_numbers ويحافظ على التوافق عند None."""
        conn = MT5Connector.__new__(MT5Connector)
        sample = [
            _pos(10, magic=0, profit=5.0),
            _pos(20, magic=LIVE_MAGIC, profit=3.0),
            _pos(30, magic=GRID_MAGIC, profit=-1.0),
        ]
        closed = []
        conn.get_open_positions = lambda symbol=None: list(sample)
        conn.close_position = lambda ticket, comment="": closed.append((ticket, comment)) or True

        # مع فلتر MAGIC_NUMBERS
        conn.close_all_positions(reason="Target_Reached", magic_numbers=SYSTEM_MAGICS)
        self.assertEqual(closed, [(20, "Target_Reached"), (30, "Target_Reached")])

        # بدون فلتر (magic_numbers=None) — توافق عكسي كامل
        closed.clear()
        conn.close_all_positions(reason="Emergency_DD")
        self.assertEqual(closed, [(10, "Emergency_DD"), (20, "Emergency_DD"), (30, "Emergency_DD")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
