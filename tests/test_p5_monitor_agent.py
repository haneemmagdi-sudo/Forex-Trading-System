"""
tests/test_p5_monitor_agent.py — اختبارات سلوكية للوكيل المراقب (P5)
====================================================================
MT5 وهمي يسجّل الاستدعاءات؛ لا اختبارات نصية. يغطي السبب الجذري للشكوى
«الوكيل المراقب لا يفعل شيئاً مع العقود المفتوحة»:
  • use_dynamic_sl=False (الإعداد الفعلي) كان يُوقف break-even/trailing/partial بصمت.
  • صفقة بلا سجل DB كانت تُهمَل بصمت.
  • الإغلاق الجزئي للوت 0.01 كان يُغلق الصفقة كلها.
التشغيل: PYTHONPATH=. python -m unittest tests/test_p5_monitor_agent.py -v
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

SYS_MAGIC = MAGIC_NUMBERS["live_engine"]


class _FakeQuery:
    def filter(self, *a, **k): return self
    def all(self): return []
    def first(self): return None


class _FakeSession:
    def query(self, *a, **k): return _FakeQuery()
    def commit(self): pass
    def close(self): pass


class FakeMT5:
    _use_yfinance = True
    connected = False

    def __init__(self, positions):
        self.positions = positions
        self.sl_calls, self.partial_calls, self.closed = [], [], []

    def get_account(self): return {"balance": 1000.0, "equity": 1000.0}
    def get_open_positions(self, symbol=None): return list(self.positions)
    def get_tick(self, symbol): return {"bid": 1.0, "ask": 1.0, "spread": 0.0}
    def close_all_positions(self, symbol=None, reason=""): self.closed.append(reason)

    def modify_sl(self, ticket, new_sl):
        self.sl_calls.append((ticket, new_sl))
        for p in self.positions:
            if p["ticket"] == ticket:
                p["sl"] = new_sl
        return True

    def partial_close(self, ticket, pct):
        self.partial_calls.append((ticket, pct))
        return True


def _pos(direction="BUY", pips=25.0, sl=1.0900, volume=0.01, magic=SYS_MAGIC, ticket=1001, profit=1.0):
    entry = 1.1000
    cur = entry + pips * 0.0001 if direction == "BUY" else entry - pips * 0.0001
    return {"ticket": ticket, "symbol": "EURUSD", "type": direction, "volume": volume,
            "open_price": entry, "current_price": round(cur, 5), "sl": sl, "tp": 0.0,
            "profit": profit, "magic": magic}


class _State:
    breakeven_done = partial_l1_done = partial_l2_done = partial_l3_done = trailing_active = False
    fsm_regime = None


def _make(positions, tracked=True):
    m = FakeMT5(positions)
    agent = mon.MonitorAgent(m)
    agent._get_db_trade = (lambda t: agent._db_trade_cache.setdefault(t, _State())) if tracked else (lambda t: None)
    return agent, m


def run(coro):
    return asyncio.run(coro)


class MonitorBase(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(mon, "SessionLocal", lambda: _FakeSession())
        p.start()
        self.addCleanup(p.stop)

    def cycle(self, agent, **cfg):
        with mock.patch.dict(STRATEGY, cfg):
            run(agent.run_cycle())


class TestRootCause(MonitorBase):
    def test_default_config_has_dynamic_sl_off_and_monitor_still_acts(self):
        """الإعداد الفعلي use_dynamic_sl=False: يجب أن يُنقل SL إلى التعادل (كان لا يحدث شيء)."""
        self.assertFalse(STRATEGY["use_dynamic_sl"])
        agent, m = _make([_pos("BUY", pips=25)])
        self.cycle(agent)
        self.assertEqual(len(m.sl_calls), 1)
        self.assertAlmostEqual(m.sl_calls[0][1], 1.1002, places=5)  # entry + 2 pips
        self.assertEqual(agent.stats["modifications"], 1)

    def test_trailing_moves_sl_in_profit_direction_only(self):
        agent, m = _make([_pos("BUY", pips=45, sl=1.0900)])
        self.cycle(agent)
        self.assertTrue(m.sl_calls)
        self.assertGreater(m.sl_calls[-1][1], 1.0900)
        # ثاني دورة بنفس السعر: لا تراجع بـ SL
        last = m.sl_calls[-1][1]
        self.cycle(agent)
        self.assertGreaterEqual(m.positions[0]["sl"], last)

    def test_sell_without_sl_gets_breakeven(self):
        agent, m = _make([_pos("SELL", pips=25, sl=0.0)])
        self.cycle(agent, monitor_trailing_enabled=False)
        self.assertEqual(len(m.sl_calls), 1)
        self.assertAlmostEqual(m.sl_calls[0][1], 1.0998, places=5)

    def test_no_action_below_thresholds(self):
        agent, m = _make([_pos("BUY", pips=5)])
        self.cycle(agent)
        self.assertEqual(m.sl_calls, [])

    def test_switches_off_means_no_modification(self):
        agent, m = _make([_pos("BUY", pips=45)])
        self.cycle(agent, monitor_breakeven_enabled=False, monitor_trailing_enabled=False,
                   monitor_partial_enabled=False)
        self.assertEqual(m.sl_calls, [])
        self.assertEqual(m.partial_calls, [])


class TestPartialClose(MonitorBase):
    def test_partial_disabled_by_default(self):
        agent, m = _make([_pos("BUY", pips=40, volume=0.10)])
        self.cycle(agent)
        self.assertEqual(m.partial_calls, [])

    def test_min_lot_never_partially_closed_when_enabled(self):
        agent, m = _make([_pos("BUY", pips=40, volume=0.01)])
        self.cycle(agent, monitor_partial_enabled=True)
        self.assertEqual(m.partial_calls, [])  # 0.01 لا يُقسَّم ⇒ لا إغلاق كلي مقنّع

    def test_splittable_volume_is_partially_closed_in_order(self):
        agent, m = _make([_pos("BUY", pips=12, volume=0.10)])
        self.cycle(agent, monitor_partial_enabled=True)
        self.assertEqual(m.partial_calls, [(1001, 0.30)])
        self.cycle(agent, monitor_partial_enabled=True)  # لا تكرار لنفس المستوى
        self.assertEqual(len(m.partial_calls), 1)

    def test_compute_partial_volume(self):
        f = MT5Connector.compute_partial_volume
        self.assertIsNone(f(0.01, 0.3))
        self.assertIsNone(f(0.01, 0.5))
        self.assertIsNone(f(0.03, 0.3))   # 0.009 → 0 < min
        self.assertEqual(f(0.10, 0.3), 0.03)
        self.assertEqual(f(0.10, 0.7), 0.07)
        self.assertEqual(f(0.02, 0.5), 0.01)
        self.assertEqual(f(0.02, 0.7), 0.01)   # يُغلق 0.01 ويبقى 0.01 → صالح
        self.assertIsNone(f(0, 0.3))
        self.assertIsNone(f(0.1, 1.0))


class TestUntrackedAndVisibility(MonitorBase):
    def test_untracked_system_magic_is_managed(self):
        agent, m = _make([_pos("BUY", pips=25, magic=SYS_MAGIC)], tracked=False)
        self.cycle(agent)
        self.assertEqual(len(m.sl_calls), 1)
        self.assertEqual(agent.stats["positions_managed"], 1)

    def test_untracked_system_magic_off_switch(self):
        agent, m = _make([_pos("BUY", pips=25, magic=SYS_MAGIC)], tracked=False)
        self.cycle(agent, monitor_manage_untracked=False)
        self.assertEqual(m.sl_calls, [])
        self.assertEqual(agent.stats["positions_skipped"], 1)

    def test_foreign_magic_skipped_and_reported_once(self):
        agent, m = _make([_pos("BUY", pips=25, magic=999)], tracked=False)
        logs = []
        orig = agent.log

        async def spy(level, text):
            logs.append(text)
            return await orig(level, text)
        agent.log = spy
        self.cycle(agent)
        self.cycle(agent)
        self.assertEqual(m.sl_calls, [])
        self.assertEqual(agent.stats["positions_skipped"], 1)
        self.assertEqual(sum("لا إدارة لها" in t for t in logs), 1)  # مرة واحدة لا كل ثانية

    def test_heartbeat_logged_and_state_pruned(self):
        agent, m = _make([_pos("BUY", pips=5, magic=SYS_MAGIC)], tracked=False)
        logs = []
        orig = agent.log

        async def spy(level, text):
            logs.append(text)
            return await orig(level, text)
        agent.log = spy
        agent.iteration = 60
        self.cycle(agent, monitor_heartbeat_cycles=60)
        self.assertTrue(any("Monitor |" in t for t in logs))
        self.assertIn(1001, agent._untracked_state)
        m.positions.clear()
        self.cycle(agent)
        self.assertNotIn(1001, agent._untracked_state)

    def test_basket_target_still_closes_all(self):
        """الميزة الموجودة لم تُحذف: هدف السلة 2$ يغلق كل شيء."""
        agent, m = _make([_pos("BUY", pips=5, profit=2.5)])
        self.cycle(agent)
        self.assertEqual(m.closed, ["Target_Reached"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
