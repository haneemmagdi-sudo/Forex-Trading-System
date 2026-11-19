"""
tests/test_phase0_council.py — اختبارات المرحلة 0 (الأمان والصدق) لمجلس الوكلاء الخماسي
=======================================================================================
تغطّي بنود IMPROVEMENT_PLAN §المرحلة 0 الخاصة بملفات:
  agents/delta_macro_sentinel.py · agents/alpha_regime_agent.py ·
  agents/beta_orderflow_agent.py · main_orchestrator.py ·
  autonomous_master_orchestrator.py

التشغيل (من جذر المشروع):
    PYTHONPATH=. python tests/test_phase0_council.py
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

import agents.delta_macro_sentinel as delta
from agents.alpha_regime_agent import AlphaRegimeAgent, RegimeOutput, RegimeState
from agents.beta_orderflow_agent import BetaOrderFlowAgent

UTC = timezone.utc
NOW = datetime(2026, 11, 17, 13, 0, tzinfo=UTC)          # الثلاثاء — توقيت نيويورك EST (UTC-5)
SATURDAY = datetime(2026, 11, 14, 13, 0, tzinfo=UTC)     # عطلة الأسبوع


# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------

def _ff_event(title: str, currency: str, impact: str, when_utc: datetime) -> dict:
    """حدث بصيغة FF القديمة: date + time بتوقيت نيويورك (EST في نوفمبر)."""
    et = when_utc.astimezone(timezone(timedelta(hours=-5)))
    return {
        "title": title,
        "country": currency,
        "impact": impact,
        "date": et.strftime("%Y-%m-%d"),
        "time": et.strftime("%I:%M%p").lower(),
    }


def _assess(events, utc_now: datetime, symbol: str = "EURUSD"):
    original = delta._try_fetch_forex_factory
    delta._try_fetch_forex_factory = lambda now: events
    try:
        return asyncio.run(delta.MacroSentinelAgent().assess(symbol, utc_now))
    finally:
        delta._try_fetch_forex_factory = original


def _ohlc(n: int, base: float, vol: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = base + np.cumsum(rng.normal(0.0, vol, n))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return pd.DataFrame({
        "open": open_,
        "high": np.maximum(open_, close) + vol * 0.5,
        "low": np.minimum(open_, close) - vol * 0.5,
        "close": close,
        "tick_volume": np.full(n, 500.0),
    })


# ---------------------------------------------------------------------------
# 0.6 — توقيت Forex Factory
# ---------------------------------------------------------------------------

def test_ff_naive_eastern_time_uses_correct_dst_offset():
    cases = {
        "2026-01-14": datetime(2026, 1, 14, 13, 30, tzinfo=UTC),   # EST: +5
        "2026-03-06": datetime(2026, 3, 6, 13, 30, tzinfo=UTC),    # قبل بدء DST (8 مارس)
        "2026-03-09": datetime(2026, 3, 9, 12, 30, tzinfo=UTC),    # بعد بدء DST: +4
        "2026-07-15": datetime(2026, 7, 15, 12, 30, tzinfo=UTC),   # EDT: +4
        "2026-10-30": datetime(2026, 10, 30, 12, 30, tzinfo=UTC),  # قبل نهاية DST (1 نوفمبر)
        "2026-11-02": datetime(2026, 11, 2, 13, 30, tzinfo=UTC),   # بعد نهاية DST: +5
    }
    for date, expected in cases.items():
        got = delta._ff_event_utc({"date": date, "time": "8:30am"})
        assert got == expected, f"{date}: expected {expected}, got {got}"


def test_ff_time_with_embedded_offset_is_converted_once():
    expected = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
    assert delta._ff_event_utc({"date": "2026-07-15T08:30:00-04:00"}) == expected
    assert delta._ff_event_utc({"date": "2026-07-15T12:30:00Z"}) == expected
    # نفس اللحظة بالصيغتين (بلا منطقة / مع منطقة) تعطي نفس UTC
    naive = delta._ff_event_utc({"date": "2026-07-15", "time": "8:30am"})
    aware = delta._ff_event_utc({"date": "2026-07-15T08:30:00-04:00"})
    assert naive == aware == expected


def test_ff_unparseable_event_returns_none():
    for ev in ({}, {"date": "garbage", "time": "8:30am"},
               {"date": "2026-07-15", "time": "All Day"},
               {"date": "2026-07-15", "time": "Tentative"},
               {"date": "2026-07-15"}):
        assert delta._ff_event_utc(ev) is None, ev


def test_post_event_embargo_blocks_high_impact_for_15_minutes():
    ev = _ff_event("Non-Farm Payrolls", "USD", "High", NOW - timedelta(minutes=10))
    res = _assess([ev], NOW)
    assert res.risk_level == delta.NewsRiskLevel.BLACKOUT
    assert res.news_embargo_active is True
    assert res.risk_percent_multiplier == 0.0


def test_post_event_embargo_expires_after_15_minutes():
    ev = _ff_event("Non-Farm Payrolls", "USD", "High", NOW - timedelta(minutes=20))
    res = _assess([ev], NOW)
    assert res.risk_level == delta.NewsRiskLevel.CLEAR


def test_past_medium_event_does_not_trigger_blackout():
    ev = _ff_event("Trade Balance", "USD", "Medium", NOW - timedelta(minutes=10))
    res = _assess([ev], NOW)
    assert res.risk_level == delta.NewsRiskLevel.CLEAR, res.risk_level


def test_past_medium_event_does_not_mask_upcoming_high_event():
    past_medium = _ff_event("Trade Balance", "USD", "Medium", NOW - timedelta(minutes=10))
    upcoming_high = _ff_event("CPI m/m", "USD", "High", NOW + timedelta(minutes=25))
    res = _assess([past_medium, upcoming_high], NOW)
    assert res.risk_level == delta.NewsRiskLevel.HIGH_IMPACT, res.risk_level
    assert res.risk_percent_multiplier == 0.4
    assert res.next_event_name == "CPI m/m"


def test_pre_event_levels_unchanged():
    expected = {10: ("BLACKOUT", 0.0, True), 25: ("HIGH_IMPACT", 0.4, True),
                45: ("CAUTION", 0.7, False), 90: ("CLEAR", 1.0, False)}
    for minutes, (level, mult, embargo) in expected.items():
        res = _assess([_ff_event("CPI m/m", "USD", "High", NOW + timedelta(minutes=minutes))], NOW)
        assert (res.risk_level.value, res.risk_percent_multiplier, res.news_embargo_active) == \
            (level, mult, embargo), (minutes, res)


def test_missing_or_unreadable_feed_is_blackout_not_clear():
    # لا جدول احتياطي: غياب تقويم موثوق = لا نعرف إن كان هناك خبر = حظر كامل (fail-closed).
    # خلاصة فيها أحداث لكن لا يُقرأ وقت أي منها = تغيّر صيغة، لا "لا أخبار".
    bad_feed = [{"title": "CPI", "country": "USD", "impact": "High", "date": "???"}]
    for when in (NOW, SATURDAY):
        for feed in (None, bad_feed, [], {"error": "rate limited"}):
            res = _assess(feed, when)
            assert res.risk_level.value == "BLACKOUT", (feed, res)
            assert res.news_embargo_active is True and res.risk_percent_multiplier == 0.0, (feed, res)
            assert res.data_source == "NO_CALENDAR_FEED", (feed, res.data_source)
            assert res.next_event_name is None and res.minutes_to_next_event is None, res


def test_invented_weekly_schedule_is_removed():
    assert not hasattr(delta, "_WEEKLY_RECURRING_EVENTS")
    assert not hasattr(delta, "_get_fallback_upcoming_events")


def test_live_feed_data_source_is_unchanged():
    res = _assess([_ff_event("CPI m/m", "USD", "High", NOW + timedelta(minutes=90))], NOW)
    assert res.data_source == "FOREX_FACTORY_LIVE" and res.risk_level.value == "CLEAR", res


# ---------------------------------------------------------------------------
# ذاكرة الخلاصة: إعادة محاولة بعد دقيقتين، وبيانات قديمة ≤ 6 ساعات عند الفشل
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402
import os as _os      # noqa: E402

_FEED = [{"title": "CPI m/m", "country": "USD", "impact": "High", "date": "2026-11-17T08:30:00-05:00"}]


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return _json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeNet:
    """يستبدل urllib.request.urlopen: نتائج متتابعة (قائمة/خطأ) ويعدّ الطلبات."""
    def __init__(self, *results):
        self.results, self.calls = list(results), 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        result = self.results.pop(0) if self.results else OSError("no more results")
        if isinstance(result, Exception):
            raise result
        return _Resp(result)


def _with_net(net, fn, offline=None):
    old_open, old_env = delta.urllib.request.urlopen, _os.environ.get("MACRO_OFFLINE")
    delta.urllib.request.urlopen = net
    delta._FF_CACHE.update(data=None, fetched_at=None, next_attempt=None)
    if offline is None:
        _os.environ.pop("MACRO_OFFLINE", None)
    else:
        _os.environ["MACRO_OFFLINE"] = offline
    try:
        return fn()
    finally:
        delta.urllib.request.urlopen = old_open
        delta._FF_CACHE.update(data=None, fetched_at=None, next_attempt=None)
        if old_env is None:
            _os.environ.pop("MACRO_OFFLINE", None)
        else:
            _os.environ["MACRO_OFFLINE"] = old_env


def test_feed_is_cached_for_30_minutes():
    net = _FakeNet(_FEED, _FEED)

    def run():
        assert delta._try_fetch_forex_factory(NOW) == _FEED
        assert delta._try_fetch_forex_factory(NOW + timedelta(minutes=29)) == _FEED
        assert net.calls == 1
        assert delta._try_fetch_forex_factory(NOW + timedelta(minutes=31)) == _FEED
        assert net.calls == 2
    _with_net(net, run)


def test_failed_fetch_is_retried_after_two_minutes_not_thirty():
    net = _FakeNet(OSError("down"), _FEED)

    def run():
        assert delta._try_fetch_forex_factory(NOW) is None
        assert delta._try_fetch_forex_factory(NOW + timedelta(seconds=90)) is None      # ما زلنا في فترة الانتظار
        assert net.calls == 1
        assert delta._try_fetch_forex_factory(NOW + timedelta(minutes=2, seconds=1)) == _FEED
        assert net.calls == 2
    _with_net(net, run)


def test_stale_feed_is_served_for_six_hours_after_a_failure_then_dropped():
    net = _FakeNet(_FEED, OSError("down"), OSError("down"), OSError("down"))

    def run():
        assert delta._try_fetch_forex_factory(NOW) == _FEED
        assert delta._try_fetch_forex_factory(NOW + timedelta(minutes=31)) == _FEED            # فشل → قديمة (31 د)
        assert delta._try_fetch_forex_factory(NOW + timedelta(hours=5, minutes=59)) == _FEED   # ≤ 6 س
        assert delta._try_fetch_forex_factory(NOW + timedelta(hours=6, minutes=1)) is None     # أقدم من 6 س
    _with_net(net, run)


def test_macro_offline_flag_returns_none_without_network():
    net = _FakeNet(_FEED)
    _with_net(net, lambda: (_check_none(delta._try_fetch_forex_factory(NOW)), _check_calls(net, 0)), offline="1")


def _check_none(value):
    assert value is None, value


def _check_calls(net, n):
    assert net.calls == n, net.calls


# ---------------------------------------------------------------------------
# 0.3 — قيمة النقطة لكل رمز
# ---------------------------------------------------------------------------

def test_alpha_point_value_override_scales_atr_points():
    df_m5 = _ohlc(160, 2000.0, 0.8, seed=1)
    df_h1 = _ohlc(100, 2000.0, 3.0, seed=2)
    agent = AlphaRegimeAgent()  # الافتراضي 0.00001 (5 خانات)
    default = asyncio.run(agent.analyze("XAUUSD", df_m5, df_h1))
    gold = asyncio.run(agent.analyze("XAUUSD", df_m5, df_h1, point_value=0.01))
    assert abs(default.atr_points / gold.atr_points - 1000.0) < 1.0, (default.atr_points, gold.atr_points)
    jpy = asyncio.run(agent.analyze("USDJPY", df_m5, df_h1, point_value=0.001))
    assert abs(default.atr_points / jpy.atr_points - 100.0) < 0.5


def test_alpha_rejects_non_positive_point_value():
    df_m5 = _ohlc(160, 2000.0, 0.8, seed=1)
    df_h1 = _ohlc(100, 2000.0, 3.0, seed=2)
    for bad in (0.0, -0.01):
        try:
            asyncio.run(AlphaRegimeAgent().analyze("XAUUSD", df_m5, df_h1, point_value=bad))
        except ValueError:
            continue
        raise AssertionError(f"point_value={bad} must raise ValueError")


def test_beta_stop_distance_uses_symbol_point_value():
    beta = BetaOrderFlowAgent.__new__(BetaOrderFlowAgent)   # بلا محرك OFI حقيقي
    beta.point_value = 0.00001
    beta._ofi_engine = None
    df = pd.DataFrame({"open": 2000.0, "high": 2000.1, "low": 1999.9,
                       "close": 2000.0, "tick_volume": 500.0}, index=range(30))
    df.loc[27, "high"] = 2000.2          # شمعة 1 للفجوة
    df.loc[29, ["low", "high", "close"]] = [2001.0, 2001.3, 2001.1]   # شمعة 3: low > high الأولى
    regime = RegimeOutput(
        symbol="XAUUSD", regime_state=RegimeState.TRENDING_LOW_VOL, regime_confidence=0.9,
        hurst_exponent=0.6, atr_points=100.0, atr_ratio=1.0, rolling_z_score=0.0,
        directional_bias="BULLISH", diagnostics={},
    )
    ofi = SimpleNamespace(ofi_z_score=0.5, buy_volume_pct=0.6, source="SIMULATED")
    now = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
    prop = beta._propose_sync("XAUUSD", df, regime, now, ofi, point_value=0.01)
    # atr_price = 100 نقطة × 0.01 = 1.0 ؛ SL = أسفل الفجوة (2000.2) - 1.1 × 1.0
    assert prop.proposed_action == "LIMIT_BUY"
    assert abs(prop.stop_loss - 1999.1) < 1e-6, prop.stop_loss


# ---------------------------------------------------------------------------
# 0.4 — البوابات تمنع عند الخطأ (fail-closed)
# ---------------------------------------------------------------------------

class _FakeMT5:
    TIMEFRAME_M5 = 5
    TIMEFRAME_H1 = 60
    TIMEFRAME_M1 = 1

    def __init__(self, rates, info):
        self._rates, self._info = rates, info

    def copy_rates_from_pos(self, symbol, timeframe, pos, count):
        return self._rates

    def symbol_info(self, symbol):
        return self._info


def _with_fake_mt5(fake, fn):
    import main_orchestrator as mo
    had = hasattr(mo, "mt5")
    old = getattr(mo, "mt5", None)
    mo.mt5 = fake
    try:
        return fn(mo)
    finally:
        if had:
            mo.mt5 = old
        else:
            del mo.mt5


def test_live_snapshot_fails_closed_when_bars_missing():
    bars = [{"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "tick_volume": 10}] * 3
    for rates in (None, []):
        fake = _FakeMT5(rates, SimpleNamespace(spread=12, point=0.01))

        def run(mo):
            p = mo.MarketDataProvider(use_live_mt5=False)
            try:
                p._fetch_mt5_live("XAUUSD")
            except mo.MarketDataUnavailable:
                return True
            return False
        assert _with_fake_mt5(fake, run), f"rates={rates!r} must raise MarketDataUnavailable"
    assert bars  # (يمنع تحذير المتغير غير المستخدم)


def test_live_snapshot_fails_closed_when_symbol_info_missing():
    bars = [{"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "tick_volume": 10}] * 3
    for info in (None, SimpleNamespace(spread=12, point=0.0)):
        fake = _FakeMT5(bars, info)

        def run(mo):
            p = mo.MarketDataProvider(use_live_mt5=False)
            try:
                p._fetch_mt5_live("XAUUSD")
            except mo.MarketDataUnavailable:
                return True
            return False
        assert _with_fake_mt5(fake, run), f"symbol_info={info!r} must raise MarketDataUnavailable"


def test_live_snapshot_returns_spread_and_point_value_from_symbol_info():
    bars = [{"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "tick_volume": 10}] * 3
    fake = _FakeMT5(bars, SimpleNamespace(spread=23, point=0.01))
    snap = _with_fake_mt5(fake, lambda mo: mo.MarketDataProvider(use_live_mt5=False)._fetch_mt5_live("XAUUSD"))
    assert snap["spread_points"] == 23.0
    assert snap["point_value"] == 0.01


def test_simulated_snapshot_declares_its_point_value():
    import main_orchestrator as mo
    snap = mo.MarketDataProvider._generate_institutional_snapshot("EURUSD")
    assert snap["point_value"] == 0.00001


def test_failed_symbol_is_skipped_without_aborting_cycle():
    import main_orchestrator as mo
    orch = mo.MultiAgentOrchestrator.__new__(mo.MultiAgentOrchestrator)

    async def fake_eval(symbol, **kwargs):
        if symbol == "XAUUSD":
            raise RuntimeError("market data unavailable")
        return SimpleNamespace(symbol=symbol)

    orch.evaluate_symbol = fake_eval
    res = asyncio.run(orch.run_parallel_cycle(["EURUSD", "XAUUSD", "GBPUSD"]))
    assert set(res) == {"EURUSD", "GBPUSD"}, set(res)


def test_master_cycle_skips_failed_symbol():
    import autonomous_master_orchestrator as amo
    orch = amo.AutonomousMasterOrchestrator.__new__(amo.AutonomousMasterOrchestrator)
    orch.feedback = SimpleNamespace(inspect_and_sync_closed_deals=lambda hours_back=12: [])
    orch.watchdog = SimpleNamespace(audit_and_verify=lambda: {"all_valid": True})

    async def fake_eval(symbol, **kwargs):
        if symbol == "XAUUSD":
            raise RuntimeError("market data unavailable")
        return SimpleNamespace(symbol=symbol)

    orch.evaluate_symbol_autonomous = fake_eval
    res = asyncio.run(orch.run_master_cycle(["EURUSD", "XAUUSD", "GBPUSD"]))
    assert set(res) == {"EURUSD", "GBPUSD"}, set(res)


# ---------------------------------------------------------------------------
# 0.3 — نقاط الربح لكل رمز في تغذية الصفقات المغلقة
# ---------------------------------------------------------------------------

def test_pnl_pips_per_symbol():
    import autonomous_master_orchestrator as amo
    f = amo.MT5ClosedDealFeedback._pips_from_profit
    # EURUSD: pip=0.0001، tick 0.00001 بقيمة 1$ → 10$/pip/lot
    assert abs(f("EURUSD", 20.0, 0.2, 1.0, 0.00001) - 10.0) < 1e-6
    # XAUUSD: pip=0.1، tick 0.01 بقيمة 1$ → 10$/pip/lot
    assert abs(f("XAUUSD", 50.0, 0.05, 1.0, 0.01) - 100.0) < 1e-6
    # USDJPY: pip=0.01، tick 0.001 بقيمة 0.6667$ → 6.667$/pip/lot
    assert abs(f("USDJPY", 13.334, 0.02, 0.6667, 0.001) - 100.0) < 0.05
    # بيانات غير صالحة → None وليس رقماً مفترضاً
    for args in (("XAUUSD", 50.0, 0.0, 1.0, 0.01), ("XAUUSD", 50.0, 0.05, 0.0, 0.01),
                 ("XAUUSD", 50.0, 0.05, 1.0, 0.0)):
        assert f(*args) is None, args


# ---------------------------------------------------------------------------

def main() -> int:
    tests = [(n, fn) for n, fn in sorted(globals().items()) if n.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc(limit=2, file=sys.stdout)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
