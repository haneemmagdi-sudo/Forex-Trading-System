"""
tests/test_basket_per_symbol_atr.py — سلة لكل رمز، وقف ATR، هدف 1:1
====================================================================
مثال الأرقام: EURUSD وATR لحظة الدخول = 0.0010 (10 بيب) → وقف 2.5×ATR = 25 بيب، هدف = 1.0×الوقف = 25 بيب.
التشغيل: PYTHONPATH=. python -m unittest tests.test_basket_per_symbol_atr -v
"""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import MAGIC_NUMBERS, STRATEGY  # noqa: E402
import agents.monitor_agent as mon  # noqa: E402
from tests.test_basket_magic_filter import FakeMagicMT5, _FakeSession  # noqa: E402

MAGIC = MAGIC_NUMBERS["live_engine"]
PIP = 0.0001
ATR = 0.0010


class _SigQuery:
    def __init__(self, atr): self.atr = atr
    def filter(self, *a, **k): return self
    def first(self): return None if self.atr is None else SimpleNamespace(atr_value=self.atr)


class _SigSession(_FakeSession):
    calls = 0
    def __init__(self, atr): self.atr = atr
    def query(self, model, *a, **k):
        type(self).calls += 1
        return _SigQuery(self.atr)


def _p(ticket, symbol="EURUSD", direction="BUY", entry=1.1000, pips=0.0, profit=0.0, volume=0.01, magic=MAGIC):
    sign = 1 if direction == "BUY" else -1
    return {
        "ticket": ticket, "symbol": symbol, "type": direction, "volume": volume,
        "open_price": entry, "current_price": round(entry + sign * pips * PIP, 5),
        "sl": 0.0, "tp": 0.0, "profit": profit, "magic": magic,
        "open_time": f"2026-11-24T10:00:{ticket % 60:02d}+00:00",
    }


class TestBasketPerSymbolAtr(unittest.TestCase):
    def _cycle(self, positions, atr=ATR, **cfg):
        patcher = mock.patch.object(mon, "SessionLocal", lambda: _SigSession(atr))
        patcher.start()
        self.addCleanup(patcher.stop)
        m = FakeMagicMT5(positions)
        agent = mon.MonitorAgent(m)
        agent._get_db_trade = lambda t: None
        with mock.patch.dict(STRATEGY, cfg):
            asyncio.run(agent.run_cycle())
        return agent, m

    def _closed(self, m):
        return {t for t, _ in m.closed_tickets}

    # ── لكل رمز ───────────────────────────────────────────────────────
    def test_winning_symbol_closes_alone_and_losing_symbol_stays_open(self):
        _, m = self._cycle([
            _p(1, "EURUSD", pips=25, profit=2.5),
            _p(2, "GBPUSD", pips=-5, profit=-0.5),
        ])
        self.assertEqual(self._closed(m), {1})
        self.assertEqual([c[0] for c in m.close_all_calls], ["EURUSD"])

    def test_losing_symbol_no_longer_blocks_the_winner(self):
        """القديم: مجموع الرموز = 3.0 - 15 = -12 فلا يُغلق شيء. الآن EURUSD يُغلق على هدفه."""
        _, m = self._cycle([
            _p(1, "EURUSD", pips=30, profit=3.0),
            _p(2, "GBPUSD", pips=-10, profit=-15.0),
        ])
        self.assertEqual(self._closed(m), {1})

    def test_each_symbol_can_close_in_the_same_cycle(self):
        _, m = self._cycle([
            _p(1, "EURUSD", pips=25, profit=2.5),
            _p(2, "GBPUSD", pips=-25, profit=-2.5),
        ])
        self.assertEqual(self._closed(m), {1, 2})
        reasons = {s: r for s, r, _ in m.close_all_calls}
        self.assertEqual(reasons, {"EURUSD": "Target_Reached", "GBPUSD": "Basket_SL_Hit"})

    # ── ATR 1:1 ───────────────────────────────────────────────────────
    def test_target_is_one_to_one_with_stop_not_two_dollars(self):
        _, m = self._cycle([_p(1, pips=24, profit=2.4)])      # القديم كان يُغلق عند 2$
        self.assertEqual(self._closed(m), set())
        _, m = self._cycle([_p(1, pips=25, profit=2.5)])
        self.assertEqual(self._closed(m), {1})

    def test_stop_is_atr_based_not_twenty_dollars(self):
        _, m = self._cycle([_p(1, pips=-24, profit=-2.4)])
        self.assertEqual(self._closed(m), set())
        _, m = self._cycle([_p(1, pips=-25, profit=-2.5)])    # أقل بكثير من سقف 20$
        self.assertEqual(self._closed(m), {1})
        self.assertEqual(m.close_all_calls[0][1], "Basket_SL_Hit")

    def test_sell_basket_is_symmetric(self):
        _, m = self._cycle([_p(1, direction="SELL", pips=25, profit=2.5)])
        self.assertEqual((self._closed(m), m.close_all_calls[0][1]), ({1}, "Target_Reached"))
        _, m = self._cycle([_p(1, direction="SELL", pips=-25, profit=-2.5)])
        self.assertEqual((self._closed(m), m.close_all_calls[0][1]), ({1}, "Basket_SL_Hit"))

    def test_grid_layers_use_volume_weighted_average_entry(self):
        # طبقتان شراء 1.1000 و1.0975 → المتوسط 1.09875؛ السعر 1.1013 = +25.5 بيب من المتوسط
        a = _p(1, entry=1.1000, volume=0.01, profit=0.0)
        b = _p(2, entry=1.0975, volume=0.01, profit=0.0)
        for pos in (a, b):
            pos["current_price"] = 1.1013
        a["profit"], b["profit"] = 1.3, 3.8
        _, m = self._cycle([a, b])
        self.assertEqual(self._closed(m), {1, 2})
        self.assertEqual(m.close_all_calls[0][1], "Target_Reached")

    def test_target_needs_positive_net_profit(self):
        """الحركة بلغت الهدف لكن الربح الصافي سالب (تكاليف) → لا إغلاق على «هدف»."""
        _, m = self._cycle([_p(1, pips=25, profit=-0.1)])
        self.assertEqual(self._closed(m), set())

    def test_dollar_ceiling_still_protects_when_atr_stop_is_far(self):
        _, m = self._cycle([_p(1, pips=-10, profit=-25.0)], atr=0.0100)   # وقف ATR = 250 بيب
        self.assertEqual(self._closed(m), {1})
        self.assertEqual(m.close_all_calls[0][1], "Basket_SL_Hit")

    def test_multipliers_come_from_config(self):
        _, m = self._cycle([_p(1, pips=25, profit=2.5)], basket_rr=2.0)   # الهدف صار 50 بيب
        self.assertEqual(self._closed(m), set())
        _, m = self._cycle([_p(1, pips=-25, profit=-2.5)], basket_sl_atr_mult=4.0)  # الوقف 40 بيب
        self.assertEqual(self._closed(m), set())

    # ── المسار الاحتياطي ──────────────────────────────────────────────
    def test_unknown_atr_falls_back_to_legacy_usd_target_per_symbol(self):
        _, m = self._cycle([
            _p(1, "EURUSD", pips=3, profit=2.5),
            _p(2, "GBPUSD", pips=-3, profit=-10.0),
        ], atr=None)
        self.assertEqual(self._closed(m), {1})

    def test_hedged_two_direction_basket_uses_legacy_path_without_crashing(self):
        _, m = self._cycle([
            _p(1, direction="BUY", pips=10, profit=2.0),
            _p(2, direction="SELL", pips=-10, profit=0.6),
        ])
        self.assertEqual(self._closed(m), {1, 2})
        self.assertEqual(m.close_all_calls[0][1], "Target_Reached")

    # ── مصدر ATR ──────────────────────────────────────────────────────
    def test_atr_is_read_once_from_signal_and_none_is_not_cached(self):
        agent = mon.MonitorAgent(FakeMagicMT5([]))
        pos = [_p(7)]
        with mock.patch.object(mon, "SessionLocal", lambda: _SigSession(None)):
            self.assertIsNone(agent._basket_entry_atr(pos))
        self.assertNotIn(7, agent._basket_atr_cache)               # ربط الإشارة قد يصل متأخراً
        _SigSession.calls = 0
        with mock.patch.object(mon, "SessionLocal", lambda: _SigSession(0.0012)):
            self.assertEqual(agent._basket_entry_atr(pos), 0.0012)
            self.assertEqual(agent._basket_entry_atr(pos), 0.0012)
        self.assertEqual(_SigSession.calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
