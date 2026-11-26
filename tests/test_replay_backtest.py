"""
tests/test_replay_backtest.py — اختبارات أداة إعادة التشغيل (بيانات اصطناعية، بلا MT5 ولا إنترنت)
==========================================================================================
الأرقام: EURUSD، سبريد 1 بيب، لوت 0.01 (بيب = 0.10$)، ATR = 10 بيب → وقف السلة 25 بيب وهدفها 25 بيب (2.5$).
التشغيل: PYTHONPATH=. python -m unittest tests.test_replay_backtest -v
"""
import asyncio
import os
import random
import sys
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.fsm_engine import Regime  # noqa: E402
from backtest import replay_backtest as rb  # noqa: E402

PIP = 0.0001
ATR = 0.0010


def _args(**kw):
    base = dict(balance=1000.0, commission_per_lot=0.0, legacy_basket=False, oos_fraction=0.0, warmup=0,
                date_from=None, date_to=None, overrides={}, signal_mode="real", seed=1, regimes=None,
                path_order="ohlc", cache_dir=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _frame(bars, start="2026-01-05 00:00"):
    """bars: [(o, h, l, c)] أو (o,h,l,c,spread_pips)."""
    idx = pd.date_range(start, periods=len(bars), freq="h")
    rows = [{"open": b[0], "high": b[1], "low": b[2], "close": b[3], "volume": 100,
             "spread_pips": b[4] if len(b) > 4 else 1.0} for b in bars]
    return pd.DataFrame(rows, index=idx)


FLAT = (1.1000, 1.1002, 1.0998, 1.1000)


def _run(data, signals, **kw):
    """signals: {(symbol, bar_index): 'BUY'|'SELL'} → تدخل عند افتتاح الشمعة التالية."""
    def fn(sym, i):
        d = signals.get((sym, i))
        return None if d is None else {"symbol": sym, "direction": d, "atr": ATR, "regime": Regime.SLOW_TREND, "confidence": 70}
    rp = rb.Replay(data, _args(**kw), signal_fn=fn)
    rep = asyncio.run(rp.run(progress=False))
    return rp, rep


class TestSimBroker(unittest.TestCase):
    def _broker(self, **kw):
        b = rb.SimBroker(1000.0, **kw)
        b.set_price("EURUSD", 1.1000, 1.0)
        return b

    def test_spread_is_paid_on_round_trip(self):
        b = self._broker()
        t = b.open_position("EURUSD", "BUY", 0.01, 0.0, 0.0, 112345)
        self.assertAlmostEqual(b.positions[t]["open_price"], 1.1001, 6)          # الشراء عند ask
        b.close_position(t, "x")
        self.assertAlmostEqual(b.closed[0]["net"], -0.10, 4)                      # -1 بيب × 0.10$

    def test_sell_profits_when_ask_falls(self):
        b = self._broker()
        t = b.open_position("EURUSD", "SELL", 0.01, 0.0, 0.0, 112345)
        b.set_price("EURUSD", 1.0975, 1.0)                                         # ask = 1.0976 → +24 بيب
        self.assertAlmostEqual(b.positions[t]["profit"], 2.40, 3)

    def test_usdjpy_and_cross_pip_value(self):
        self.assertAlmostEqual(rb.pip_value_usd("USDJPY", 150.0, {}), 1000 / 150.0, 6)
        self.assertAlmostEqual(rb.pip_value_usd("EURJPY", 160.0, {"USDJPY": 150.0}), 1000 / 150.0, 6)
        self.assertAlmostEqual(rb.pip_value_usd("EURGBP", 0.85, {"GBPUSD": 1.25}), 12.5, 6)

    def test_commission_reduces_net_not_gross(self):
        b = self._broker(commission_per_lot=7.0)
        t = b.open_position("EURUSD", "BUY", 0.01, 0.0, 0.0, 1)
        b.set_price("EURUSD", 1.1031, 1.0)                                         # +30 بيب من ask
        b.close_position(t, "x")
        r = b.closed[0]
        self.assertAlmostEqual(r["gross"], 3.0, 3)
        self.assertAlmostEqual(r["net"], 3.0 - 0.07, 3)
        self.assertAlmostEqual(b.balance, 1000 + r["net"], 6)

    def test_broker_sl_fills_at_sl_and_at_open_on_gap(self):
        b = self._broker()
        t = b.open_position("EURUSD", "BUY", 0.01, 1.0950, 0.0, 1)
        b.set_price("EURUSD", 1.0940, 1.0)
        b.apply_broker_stops("EURUSD")                                             # عبور داخل الشمعة → التعبئة عند الـSL
        self.assertAlmostEqual(b.closed[-1]["exit"], 1.0950, 6)
        t2 = b.open_position("EURUSD", "BUY", 0.01, 1.0950, 0.0, 1)
        b.set_price("EURUSD", 1.0900, 1.0)
        b.apply_broker_stops("EURUSD", gap=True)                                   # فجوة → التعبئة عند السعر الفعلي
        self.assertAlmostEqual(b.closed[-1]["exit"], 1.0900, 6)

    def test_bar_path_order(self):
        self.assertEqual(rb.bar_path(1.10, 1.12, 1.09, 1.11), [1.10, 1.09, 1.12, 1.11])   # صاعدة: L ثم H
        self.assertEqual(rb.bar_path(1.10, 1.12, 1.09, 1.09), [1.10, 1.12, 1.09, 1.09])   # هابطة: H ثم L


class TestReplayMechanics(unittest.TestCase):
    def test_basket_target_fills_at_exact_25_pips(self):
        bars = [FLAT, FLAT, (1.1000, 1.1050, 1.0995, 1.1040), FLAT, FLAT]
        rp, rep = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"})
        t = rp.broker.closed[0]
        self.assertEqual(t["reason"], "Target_Reached")
        self.assertAlmostEqual(t["exit"] - t["entry"], 25 * PIP, 6)
        self.assertAlmostEqual(t["net"], 2.5, 3)

    def test_basket_stop_fills_at_exact_minus_25_pips(self):
        bars = [FLAT, FLAT, (1.1000, 1.1002, 1.0960, 1.0970), FLAT, FLAT]
        rp, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"})
        t = rp.broker.closed[0]
        self.assertEqual(t["reason"], "Basket_SL_Hit")
        self.assertAlmostEqual(t["net"], -2.5, 3)

    def test_intrabar_order_decides_stop_vs_target(self):
        """نفس المدى (يلمس -31 و+49 بيب): الشمعة الصاعدة تضرب الوقف أولاً، الهابطة تضرب الهدف أولاً."""
        up = [FLAT, FLAT, (1.1000, 1.1050, 1.0970, 1.1040), FLAT]
        down = [FLAT, FLAT, (1.1000, 1.1050, 1.0970, 1.0980), FLAT]
        rp_up, _ = _run({"EURUSD": _frame(up)}, {("EURUSD", 1): "BUY"})
        rp_dn, _ = _run({"EURUSD": _frame(down)}, {("EURUSD", 1): "BUY"})
        self.assertEqual(rp_up.broker.closed[0]["reason"], "Basket_SL_Hit")
        self.assertEqual(rp_dn.broker.closed[0]["reason"], "Target_Reached")

    def test_symbols_are_independent(self):
        eur = [FLAT, FLAT, (1.1000, 1.1035, 1.0999, 1.1030), FLAT]
        gbp_flat = (1.2700, 1.2702, 1.2698, 1.2700)
        gbp = [gbp_flat, gbp_flat, (1.2700, 1.2705, 1.2695, 1.2700), gbp_flat]
        rp, _ = _run({"EURUSD": _frame(eur), "GBPUSD": _frame(gbp)},
                     {("EURUSD", 1): "BUY", ("GBPUSD", 1): "BUY"})
        by = {t["symbol"]: t["reason"] for t in rp.broker.closed}
        self.assertEqual(by["EURUSD"], "Target_Reached")
        self.assertEqual(by["GBPUSD"], "End_Of_Data")          # بقيت مفتوحة حتى نهاية البيانات

    def test_legacy_basket_uses_two_dollar_target(self):
        bars = [FLAT, FLAT, (1.1000, 1.1050, 1.0995, 1.1040), FLAT]
        rp, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"}, legacy_basket=True)
        t = rp.broker.closed[0]
        self.assertEqual(t["reason"], "Target_Reached")
        self.assertAlmostEqual(t["net"], 2.0, 2)               # 20 بيب لا 25

    def test_high_spread_blocks_entry(self):
        bars = [FLAT, FLAT, (1.1000, 1.1050, 1.0995, 1.1040, 9.0), FLAT]   # 9 بيب > 1.4 × حد EURUSD
        rp, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"})
        self.assertEqual(rp.broker.closed, [])
        self.assertEqual(rp.rejects.get("flash_spread"), 1)

    def test_grid_rule_blocks_second_entry_within_25_pips(self):
        bars = [FLAT, FLAT, (1.1000, 1.1010, 1.0995, 1.1005), (1.1005, 1.1008, 1.1000, 1.1004), FLAT]
        rp, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY", ("EURUSD", 2): "BUY"})
        self.assertEqual(rp.rejects.get("grid_distance_not_reached"), 1)
        self.assertEqual(len(rp.broker.closed), 1)             # صفقة واحدة فقط (End_Of_Data)

    def test_balance_equals_initial_plus_net(self):
        bars = [FLAT, FLAT, (1.1000, 1.1050, 1.0995, 1.1040), FLAT]
        rp, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"}, commission_per_lot=7.0)
        self.assertAlmostEqual(rp.broker.balance, 1000 + sum(t["net"] for t in rp.broker.closed), 6)


class TestMetrics(unittest.TestCase):
    def _t(self, net, reason="Target_Reached", symbol="EURUSD", ts="2026-01-01T10:00:00", regime="SLOW_TREND"):
        return {"net": net, "reason": reason, "symbol": symbol, "close_time": ts, "open_time": ts, "regime": regime}

    def test_core_stats(self):
        trades = [self._t(x, ts=f"2026-01-0{i+1}") for i, x in enumerate([2.5, 2.5, -2.5, 2.5, -2.5])]
        m = rb.compute_metrics(trades, 1000.0)["baskets"]
        self.assertEqual((m["n"], m["wins"]), (5, 3))
        self.assertAlmostEqual(m["win_rate"], 0.6)
        self.assertAlmostEqual(m["payoff_ratio"], 1.0)
        self.assertAlmostEqual(m["expectancy"], 0.5)
        self.assertAlmostEqual(m["profit_factor"], 1.5)
        self.assertAlmostEqual(m["breakeven_win_rate"], 0.5)
        lo, hi = m["win_rate_ci95"]
        self.assertTrue(0.22 < lo < 0.24 and 0.87 < hi < 0.90)   # Wilson لـ 3/5

    def test_layers_of_one_basket_count_once(self):
        same = dict(ts="2026-01-02T09:00:00")
        trades = [self._t(1.0, **same), self._t(1.5, **same), self._t(-2.0, reason="Broker_SL", ts="2026-01-03")]
        m = rb.compute_metrics(trades, 1000.0)
        self.assertEqual(m["positions"]["n"], 3)
        self.assertEqual(m["baskets"]["n"], 2)
        self.assertAlmostEqual(m["baskets"]["net"], 0.5)

    def test_end_of_data_is_excluded_from_stats(self):
        m = rb.compute_metrics([self._t(2.5), self._t(-9.0, reason="End_Of_Data")], 1000.0)
        self.assertEqual(m["baskets"]["n"], 1)
        self.assertEqual(m["open_at_end_count"], 1)

    def test_max_drawdown_from_equity_curve(self):
        eq = [(0, 1000.0), (1, 1100.0), (2, 990.0), (3, 1050.0)]
        self.assertAlmostEqual(rb.compute_metrics([self._t(1.0)], 1000.0, eq)["max_equity_drawdown_pct"], 10.0)


class TestRealPipelineSmoke(unittest.TestCase):
    def test_real_indicators_fsm_voting_run_end_to_end(self):
        rng = np.random.default_rng(7)
        n = 520
        steps = rng.normal(0, 0.0006, n) + 0.00004 * np.sin(np.arange(n) / 40.0)
        close = 1.10 + np.cumsum(steps)
        op = np.r_[close[0], close[:-1]]
        hi = np.maximum(op, close) + np.abs(rng.normal(0, 0.0003, n))
        lo = np.minimum(op, close) - np.abs(rng.normal(0, 0.0003, n))
        df = _frame([(a, b, c, d, 0.8) for a, b, c, d in zip(op, hi, lo, close)])
        rp = rb.Replay({"EURUSD": df}, _args(warmup=200))
        rep = asyncio.run(rp.run(progress=False))
        for key in ("all", "assumptions", "entry_rejections", "signals_passing_pipeline"):
            self.assertIn(key, rep)
        self.assertEqual(rp.broker.positions, {})
        self.assertAlmostEqual(rp.broker.balance, 1000 + sum(t["net"] for t in rp.broker.closed), 6)


class TestExperimentOptions(unittest.TestCase):
    def test_bar_path_adverse_and_favorable_follow_position_direction(self):
        o, h, l, c = 1.10, 1.12, 1.09, 1.09            # شمعة هابطة (الافتراضي: H ثم L)
        self.assertEqual(rb.bar_path(o, h, l, c, "adverse", True), [o, l, h, c])    # الشراء: القاع أولاً
        self.assertEqual(rb.bar_path(o, h, l, c, "adverse", False), [o, h, l, c])   # البيع: القمة أولاً
        self.assertEqual(rb.bar_path(o, h, l, c, "favorable", True), [o, h, l, c])
        self.assertEqual(rb.bar_path(o, h, l, c, "favorable", False), [o, l, h, c])
        self.assertEqual(rb.bar_path(o, h, l, c, "adverse", None), [o, h, l, c])    # بلا صفقات → الافتراضي

    def test_adverse_path_turns_a_target_into_a_stop(self):
        bars = [FLAT, FLAT, (1.1000, 1.1050, 1.0970, 1.0980), FLAT]       # هابطة: الافتراضي يبلغ الهدف أولاً
        rp0, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"})
        rp1, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"}, path_order="adverse")
        rp2, _ = _run({"EURUSD": _frame(bars)}, {("EURUSD", 1): "BUY"}, path_order="favorable")
        self.assertEqual(rp0.broker.closed[0]["reason"], "Target_Reached")
        self.assertEqual(rp1.broker.closed[0]["reason"], "Basket_SL_Hit")
        self.assertEqual(rp2.broker.closed[0]["reason"], "Target_Reached")

    def _replay_with_store(self, **kw):
        rp = rb.Replay({"EURUSD": _frame([FLAT] * 40)}, _args(**kw), signal_fn=lambda s, i: None)
        passed = {str(i): {"symbol": "EURUSD", "direction": "BUY", "atr": ATR, "regime": "STRONG_TREND", "confidence": 70}
                  for i in range(1, 31)}
        passed["30"]["regime"] = "LOW_VOL_RANGE"
        rp._sig_store["EURUSD"] = {"passed": passed, "rejected": {"31": "h4_counter_trend"}}
        return rp

    def test_signal_modes_keep_timing_and_change_only_direction(self):
        real = self._replay_with_store()
        inv = self._replay_with_store(signal_mode="invert")
        rnd = self._replay_with_store(signal_mode="random", seed=3)
        rnd2 = self._replay_with_store(signal_mode="random", seed=3)
        idx = range(1, 30)          # (30 نظامها LOW_VOL_RANGE، لا يدخل هنا)
        self.assertEqual({real._real_signal("EURUSD", i)["direction"] for i in idx}, {"BUY"})
        self.assertEqual({inv._real_signal("EURUSD", i)["direction"] for i in idx}, {"SELL"})
        d1 = [rnd._real_signal("EURUSD", i)["direction"] for i in idx]
        d2 = [rnd2._real_signal("EURUSD", i)["direction"] for i in idx]
        self.assertEqual(d1, d2)                                   # نفس البذرة → نفس السلسلة
        self.assertEqual(set(d1), {"BUY", "SELL"})
        self.assertIsNone(real._real_signal("EURUSD", 0))          # لا إشارة → لا إشارة في كل الأنماط
        self.assertIsNone(real._real_signal("EURUSD", 31))
        self.assertEqual(real.rejects, {"h4_counter_trend": 1})

    def test_regime_filter(self):
        rp = self._replay_with_store(regimes=["STRONG_TREND"])
        self.assertIsNotNone(rp._real_signal("EURUSD", 5))
        self.assertIsNone(rp._real_signal("EURUSD", 30))
        self.assertEqual(rp.rejects, {"regime_filtered": 1})

    def test_signal_cache_roundtrip_and_key(self):
        import tempfile
        from unittest import mock
        from config import STRATEGY
        rng = np.random.default_rng(11)
        n = 330
        close = 1.10 + np.cumsum(rng.normal(0, 0.0006, n))
        op = np.r_[close[0], close[:-1]]
        df = _frame([(a, max(a, d) + 0.0003, min(a, d) - 0.0003, d, 0.8) for a, d in zip(op, close)])
        with tempfile.TemporaryDirectory() as tmp:
            first = rb.Replay({"EURUSD": df}, _args(warmup=200, cache_dir=tmp))
            rep1 = asyncio.run(first.run(progress=False))
            self.assertEqual(len([f for f in os.listdir(tmp) if f.startswith("signals_EURUSD_")]), 1)
            second = rb.Replay({"EURUSD": df}, _args(warmup=200, cache_dir=tmp))
            with mock.patch.object(rb.Replay, "_pipeline", side_effect=AssertionError("cache not used")):
                rep2 = asyncio.run(second.run(progress=False))
            self.assertEqual(rep1["all"], rep2["all"])
            self.assertEqual(rep1["entry_rejections"], rep2["entry_rejections"])
            base = second._cache_path("EURUSD")
            with mock.patch.dict(STRATEGY, {"grid_distance_pips": 99999, "basket_rr": 3.0}):
                self.assertEqual(second._cache_path("EURUSD"), base)       # معاملات الخروج لا تُبطل الكاش
            with mock.patch.dict(STRATEGY, {"min_vote_score": 9.9}):
                self.assertNotEqual(second._cache_path("EURUSD"), base)    # معاملات الإشارة تُبطله


if __name__ == "__main__":
    unittest.main(verbosity=2)
