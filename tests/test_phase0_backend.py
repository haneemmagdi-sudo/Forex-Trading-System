"""
tests/test_phase0_backend.py — اختبارات المرحلة 0 للمحرك الحي (backend/)
=========================================================================
تغطّي:
  0.1  LearningAgent._compute_weight_adjustments: المضاعِف المحايد 1.0 والاتجاه الصحيح
  0.2  MonitorAgent: وقف خسارة السلة بالـATR (يعمل إلى جانب وقف الدولار الأصلي)
  0.3  ExecutionAgent: مسافة الشبكة بحجم بيب صحيح لكل رمز (XAUUSD / USDJPY / EURUSD)
  0.4  البوابات fail-closed: سبريد غير معروف يُرفض ولا يُعامَل كصفر
  0.5  حد السبريد لكل رمز من مصدر واحد (config.max_spread_for) تستعمله كل البوابات
  الصدق: LearningAgent لا يدّعي دقة نموذج لم تُقَس؛ أرباح التداول الورقي بلا مضاعِف ×10

⚠️ شغّله **في عملية منفصلة** عن tests/test_phase0_council.py:
   حزمة `agents` اسم لحزمتين (جذر المشروع و backend/) — هذا الملف يُقدِّم backend/.

التشغيل (من جذر المشروع):
    python tests/test_phase0_backend.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
os.chdir(BACKEND)                  # قاعدة البيانات مسار نسبي (AGENTS.md — الفخ الثالث)
sys.path.insert(0, str(BACKEND))   # backend/agents و backend/config قبل حزم الجذر

import agents.execution_agent as ex          # noqa: E402
import agents.learning_agent as la           # noqa: E402
import agents.monitor_agent as mon           # noqa: E402
import agents.market_analyst as ma           # noqa: E402
import config                                # noqa: E402
import core.safe_execution_gateway as gwmod  # noqa: E402
from core.mt5_connector import MT5Connector  # noqa: E402

LearningAgent = la.LearningAgent
ExecutionAgent = ex.ExecutionAgent
MonitorAgent = mon.MonitorAgent


# ---------------------------------------------------------------------------
# 0.1 — مضاعِفات التعلّم
# ---------------------------------------------------------------------------

def _adjust(regimes=None, overall_wr=60.0, high_conf_wr=60.0) -> dict:
    agent = LearningAgent.__new__(LearningAgent)   # الدالة لا تستعمل حالة الوكيل
    analysis = {
        "regime_stats": {r: {"win_rate": wr} for r, wr in (regimes or {"OTHER": 55.0}).items()},
        "overall_win_rate": overall_wr,
        "high_conf_wr": high_conf_wr,
    }
    return agent._compute_weight_adjustments(analysis)


def _approx(got: float, want: float) -> bool:
    return abs(got - want) < 1e-9


def test_neutral_analysis_changes_nothing():
    assert _adjust() == {}
    assert LearningAgent.__new__(LearningAgent)._compute_weight_adjustments({"regime_stats": {}}) == {}


def test_winning_strong_trend_raises_multipliers_from_neutral_one():
    adj = _adjust({"STRONG_TREND": 70.0})
    assert _approx(adj["ema"], 1.15) and _approx(adj["momentum"], 1.10) and _approx(adj["ha"], 1.10), adj


def test_winning_slow_trend_raises_ichimoku_and_macd():
    adj = _adjust({"SLOW_TREND": 70.0})
    assert _approx(adj["ichi"], 1.10) and _approx(adj["macd"], 1.10), adj


def test_losing_regimes_lower_multipliers():
    adj = _adjust({"HIGH_VOL_RANGE": 30.0, "CHAOS": 30.0})
    assert _approx(adj["rsi"], 0.85), adj
    assert _approx(adj["ema"], 0.85) and _approx(adj["momentum"], 0.90), adj


def test_overall_win_rate_adjustments():
    low = _adjust(overall_wr=40.0)
    assert _approx(low["ha"], 1.20) and _approx(low["macd"], 0.90), low
    high = _adjust(overall_wr=80.0, high_conf_wr=85.0)
    assert _approx(high["ha"], 1.10) and _approx(high["rsi"], 1.05) and _approx(high["adx"], 1.10), high


def test_multipliers_never_reach_base_weight_scale():
    # أسوأ تراكم ممكن: كل الشروط معاً. الخطأ القديم كان يعطي ha ≈ 2.1+ (الوزن الأساسي 2.0 + التعديل).
    adj = _adjust({"STRONG_TREND": 70.0, "SLOW_TREND": 70.0, "HIGH_VOL_RANGE": 30.0, "CHAOS": 30.0},
                  overall_wr=40.0, high_conf_wr=85.0)
    assert adj["ha"] < 1.5, adj
    assert all(0.3 <= v <= 3.0 for v in adj.values()), adj


# ---------------------------------------------------------------------------
# الصدق — لا دقة مفترضة لنموذج محمَّل
# ---------------------------------------------------------------------------

def test_loaded_model_does_not_claim_made_up_accuracy():
    import joblib
    tmp = tempfile.mkdtemp()
    model_path, scaler_path = os.path.join(tmp, "m.pkl"), os.path.join(tmp, "s.pkl")
    joblib.dump({"dummy": 1}, model_path)
    joblib.dump({"dummy": 2}, scaler_path)
    old = (la.MODEL_PATH, la.SCALER_PATH)
    la.MODEL_PATH, la.SCALER_PATH = model_path, scaler_path
    try:
        agent = LearningAgent.__new__(LearningAgent)
        agent._model, agent._scaler, agent._model_accuracy = None, None, 0.0
        agent._load_model()
        assert agent._model is not None
        assert agent._model_accuracy == 0.0, agent._model_accuracy
    finally:
        la.MODEL_PATH, la.SCALER_PATH = old


def test_learning_pip_size_per_symbol():
    for symbol, want in (("EURUSD", 0.0001), ("USDJPY", 0.01), ("GBPJPY", 0.01), ("XAUUSD", 0.1)):
        assert LearningAgent._pip_size(symbol) == want, symbol


# ---------------------------------------------------------------------------
# 0.3 — مسافة الشبكة بحجم بيب صحيح
# ---------------------------------------------------------------------------

class _FakeMT5:
    def __init__(self, positions, tick):
        self.positions, self.tick = positions, tick

    def get_account(self):
        return {"balance": 10000.0, "equity": 10000.0}

    def get_open_positions(self, symbol=None):
        return [p for p in self.positions if symbol is None or p["symbol"] == symbol]

    def get_tick(self, symbol):
        return self.tick


class _FakeRisk:
    def check_dd_protection(self, balance, equity):
        return {"ok": True, "dd_pct": 0.0}


class _FakeGateway:
    def __init__(self):
        self.calls = 0

    async def execute_signal(self, **kwargs):
        self.calls += 1
        return {"success": False, "reason": "test stop — لا صفقة حقيقية"}


def _grid_adds_layer(symbol: str, entry: float, ask: float) -> bool:
    """هل تقرّر الشبكة فتح طبقة جديدة (BUY) عندما يكون السعر الحالي ask وآخر دخول entry؟"""
    agent = ExecutionAgent.__new__(ExecutionAgent)
    gateway = _FakeGateway()
    agent.mt5 = _FakeMT5(
        [{"symbol": symbol, "type": "BUY", "open_price": entry, "open_time": "2026-11-17T10:00:00"}],
        {"ask": ask, "bid": ask - 0.00001, "spread": 2.0},
    )
    agent.risk, agent.gateway = _FakeRisk(), gateway
    agent._cascade_blocked_until = None
    agent._consecutive_losses = 0
    agent.stats = {"trades_rejected": 0}

    async def _noop_log(*args, **kwargs):
        return None

    agent.log = _noop_log
    old = ex.STRATEGY
    ex.STRATEGY = {"max_open_trades": 10, "grid_distance_pips": 25, "max_spread_pips": 100.0}
    try:
        asyncio.run(agent._process_signal({
            "symbol": symbol, "direction": "BUY",
            "voting": {"confidence": 80}, "fsm": {"regime": "STRONG_TREND"},
        }))
    finally:
        ex.STRATEGY = old
    return gateway.calls == 1


def test_grid_distance_for_gold_is_25_pips_of_ten_cents():
    assert not _grid_adds_layer("XAUUSD", 2000.00, 1999.50)   # 5 بيب فقط (كان يفتح فوراً)
    assert not _grid_adds_layer("XAUUSD", 2000.00, 1997.60)   # 24 بيب
    assert _grid_adds_layer("XAUUSD", 2000.00, 1997.40)       # 26 بيب


def test_grid_distance_for_jpy_and_eur_pairs():
    assert not _grid_adds_layer("USDJPY", 150.000, 149.800)   # 20 بيب
    assert _grid_adds_layer("USDJPY", 150.000, 149.700)       # 30 بيب
    assert not _grid_adds_layer("EURUSD", 1.10000, 1.09800)   # 20 بيب
    assert _grid_adds_layer("EURUSD", 1.10000, 1.09740)       # 26 بيب


def test_execution_pip_size_per_symbol():
    for symbol, want in (("EURUSD", 0.0001), ("USDJPY", 0.01), ("XAUUSD", 0.1)):
        assert ExecutionAgent._pip_size(symbol) == want, symbol


# ---------------------------------------------------------------------------
# 0.2 — وقف خسارة السلة بالـATR
# ---------------------------------------------------------------------------

_BASE_STRATEGY = {"base_target_usd": 2.0, "basket_max_loss_usd": 20.0,
                  "use_dynamic_sl": False, "basket_sl_atr_multiplier": 2.5}
_EUR_INFO = SimpleNamespace(trade_tick_value=1.0, trade_tick_size=0.00001)   # 100000$ لكل 1.0 سعر/لوت


def _bars(n: int = 15, close: float = 1.1, half_range: float = 0.0004) -> list:
    return [{"open": close, "high": close + half_range, "low": close - half_range, "close": close}
            for _ in range(n)]


class _FakeMT5Module:
    """بديل لحزمة MetaTrader5: شموع M15 لكل رمز + symbol_info."""
    TIMEFRAME_M15 = 15

    def __init__(self, rates_by_symbol, info_by_symbol=None):
        self.rates_by_symbol, self.info_by_symbol, self.rate_calls = rates_by_symbol, info_by_symbol or {}, 0

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.rate_calls += 1
        # شموع مغلقة فقط (start=1) و14+1 شمعة لحساب 14 مدى حقيقياً
        assert (timeframe, start, count) == (self.TIMEFRAME_M15, 1, 15), (timeframe, start, count)
        return self.rates_by_symbol.get(symbol)

    def symbol_info(self, symbol):
        return self.info_by_symbol.get(symbol)


class _patched_mt5:
    def __init__(self, fake):
        self.fake = fake

    def __enter__(self):
        self.old = sys.modules.get("MetaTrader5")
        sys.modules["MetaTrader5"] = self.fake
        return self.fake

    def __exit__(self, *exc):
        if self.old is None:
            sys.modules.pop("MetaTrader5", None)
        else:
            sys.modules["MetaTrader5"] = self.old


class _MonitorMT5:
    def __init__(self, positions, failing_tickets=()):
        self.positions, self.closed, self.closed_tickets = positions, [], []
        self.failing_tickets = set(failing_tickets)

    def get_account(self):
        return {"balance": 10000.0, "equity": 10000.0}

    def get_open_positions(self, symbol=None):
        return list(self.positions)

    def close_all_positions(self, symbol=None, reason=""):
        self.closed.append(reason)

    def close_position(self, ticket, comment=""):
        if ticket in self.failing_tickets:
            return False
        self.closed_tickets.append((ticket, comment))
        self.positions = [p for p in self.positions if p["ticket"] != ticket]
        return True


class _OkRisk:
    def check_dd_protection(self, balance, equity):
        return {"ok": True, "mode": "NORMAL", "dd_pct": 0.0}


def _pos(symbol, direction, entry, current, volume=0.01, profit=0.0, ticket=1):
    return {"ticket": ticket, "symbol": symbol, "type": direction, "open_price": entry,
            "current_price": current, "volume": volume, "profit": profit, "sl": 0.0}


def _eur_buy_grid(current: float) -> list:
    """ثلاث طبقات شراء EURUSD بمسافة 25 بيب: أعمقها 1.0950 ← وقف ATR=0.0008 × 2.5 عند 1.0930."""
    return [_pos("EURUSD", "BUY", e, current, ticket=i) for i, e in enumerate((1.1000, 1.0975, 1.0950), 1)]


def _make_monitor(positions, failing_tickets=()):
    agent = MonitorAgent.__new__(MonitorAgent)
    agent.mt5, agent.risk = _MonitorMT5(positions, failing_tickets), _OkRisk()
    agent._atr_cache, agent._db_trade_cache, agent._news_high_impact = {}, {}, False
    agent.stats = {"last_check": None, "emergency_closes": 0, "modifications": 0, "partial_closes": 0}
    agent.logs = []

    async def _log(level, msg):
        agent.logs.append((level, msg))

    async def _noop(*args, **kwargs):
        return None

    agent.log, agent._sync_closed_trades, agent._manage_position = _log, _noop, _noop
    return agent


def _with_strategy(strategy, coro_factory):
    old = mon.STRATEGY
    mon.STRATEGY = strategy
    try:
        return asyncio.run(coro_factory())
    finally:
        mon.STRATEGY = old


def _closed(agent) -> list:
    return sorted(t for t, _ in agent.mt5.closed_tickets)


def _check(agent, strategy=None):
    return _with_strategy(dict(strategy or _BASE_STRATEGY),
                          lambda: agent._check_basket_atr_stop(agent.mt5.get_open_positions()))


def test_atr_from_rates_is_mean_true_range():
    f = MonitorAgent._atr_from_rates
    assert abs(f(_bars(15), 14) - 0.0008) < 1e-12
    gap = _bars(15)
    gap[-1] = {"open": 1.1, "high": 1.11, "low": 1.109, "close": 1.1095}   # فجوة: TR = |1.11 - 1.1| = 0.01
    assert abs(f(gap, 14) - ((13 * 0.0008 + 0.01) / 14)) < 1e-12


def test_atr_from_rates_rejects_unusable_data():
    f = MonitorAgent._atr_from_rates
    assert f(None, 14) is None
    assert f([], 14) is None
    assert f(_bars(14), 14) is None                       # 14 شمعة = 13 مدى فقط
    assert f(_bars(15, half_range=0.0), 14) is None       # ATR = 0 لا يصلح وقفاً
    for field in ("high", "low", "close"):
        bad = _bars(15)
        bad[7][field] = float("nan")                      # NaN في أي حقل لا يُبتلع داخل max()
        assert f(bad, 14) is None, field


def test_basket_stop_buy_is_below_deepest_layer():
    group = _eur_buy_grid(1.0940)
    res = MonitorAgent._basket_atr_stop(group, atr=0.0008, k=2.5)
    assert abs(res["stop"] - 1.0930) < 1e-9 and res["layers"] == 3 and not res["breached"], res
    assert abs(res["lot_distance"] - 0.000135) < 1e-12, res          # 0.01 × (0.0070 + 0.0045 + 0.0020)
    assert MonitorAgent._basket_atr_stop(_eur_buy_grid(1.0929), 0.0008, 2.5)["breached"]


def test_basket_stop_sell_is_above_highest_layer():
    group = [_pos("EURUSD", "SELL", e, 1.1060, ticket=i) for i, e in enumerate((1.1000, 1.1025, 1.1050), 1)]
    res = MonitorAgent._basket_atr_stop(group, atr=0.0008, k=2.5)
    assert abs(res["stop"] - 1.1070) < 1e-9 and not res["breached"], res
    assert abs(res["lot_distance"] - 0.000135) < 1e-12, res
    for p in group:
        p["current_price"] = 1.1075
    assert MonitorAgent._basket_atr_stop(group, 0.0008, 2.5)["breached"]


def test_atr_stop_closes_basket_and_logs_max_loss():
    fake = _FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})
    agent = _make_monitor(_eur_buy_grid(1.0929))
    with _patched_mt5(fake):
        assert _check(agent) is True
    assert agent.mt5.closed_tickets == [(1, "Basket_ATR_SL_Hit"), (2, "Basket_ATR_SL_Hit"), (3, "Basket_ATR_SL_Hit")]
    assert agent.mt5.closed == []                                       # لا إغلاق شامل للحساب
    assert any("$13.50" in msg for _, msg in agent.logs), agent.logs   # 0.000135 × 100000


def test_atr_stop_does_not_close_inside_the_stop():
    agent = _make_monitor(_eur_buy_grid(1.0940))
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        assert _check(agent) is False
    assert agent.mt5.closed_tickets == []


def test_custom_multiplier_is_honoured():
    agent = _make_monitor(_eur_buy_grid(1.0941))              # بين وقف k=1 (1.0942) ووقف k=2.5 (1.0930)
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        assert _check(agent, {**_BASE_STRATEGY, "basket_sl_atr_multiplier": 1.0}) is True
    agent = _make_monitor(_eur_buy_grid(1.0941))
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        assert _check(agent) is False


def test_invalid_multiplier_falls_back_to_default_instead_of_disabling():
    for bad in (0, -1, "x", None, True):
        agent = _make_monitor(_eur_buy_grid(1.0929))
        with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
            assert _check(agent, {**_BASE_STRATEGY, "basket_sl_atr_multiplier": bad}) is True, bad


def test_atr_unavailable_leaves_basket_to_usd_stop_and_failure_is_cached():
    fake = _FakeMT5Module({"EURUSD": None})
    agent = _make_monitor(_eur_buy_grid(1.0929))
    with _patched_mt5(fake):
        assert _check(agent) is False
        assert _check(agent) is False
    assert fake.rate_calls == 1 and agent.mt5.closed_tickets == []


def test_atr_is_cached_between_checks():
    fake = _FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})
    agent = _make_monitor(_eur_buy_grid(1.0940))
    with _patched_mt5(fake):
        _check(agent)
        _check(agent)
    assert fake.rate_calls == 1


def test_symbol_without_atr_does_not_block_another_symbol():
    fake = _FakeMT5Module({"GBPUSD": None, "EURUSD": _bars()}, {"EURUSD": _EUR_INFO})
    positions = [_pos("GBPUSD", "BUY", 1.30, 1.20, ticket=9)] + _eur_buy_grid(1.0929)
    agent = _make_monitor(positions)
    with _patched_mt5(fake):
        assert _check(agent) is True
    assert _closed(agent) == [1, 2, 3]                       # GBPUSD (ticket 9) بلا ATR يبقى مفتوحاً
    assert [p["ticket"] for p in agent.mt5.positions] == [9]


def test_baskets_are_evaluated_per_direction():
    fake = _FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})
    healthy_buy = _eur_buy_grid(1.0940)
    sells = [_pos("EURUSD", "SELL", e, 1.1100, ticket=10 + i) for i, e in enumerate((1.1000, 1.1025))]
    agent = _make_monitor(healthy_buy + sells)               # وقف البيع = 1.1025 + 0.002 = 1.1045 < 1.1100
    with _patched_mt5(fake):
        assert _check(agent) is True
    assert any("SELL" in msg for _, msg in agent.logs), agent.logs
    assert _closed(agent) == [10, 11]                        # سلة البيع فقط؛ سلة الشراء السليمة تبقى
    agent = _make_monitor(healthy_buy)
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        assert _check(agent) is False


def test_missing_symbol_info_still_closes_and_reports_na():
    agent = _make_monitor(_eur_buy_grid(1.0929))
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {})):
        assert _check(agent) is True
    assert any("n/a" in msg for _, msg in agent.logs), agent.logs


def test_run_cycle_original_usd_stop_runs_first():
    fake = _FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})
    agent = _make_monitor([_pos("EURUSD", "BUY", 1.1, 1.0999, profit=-25.0)])
    with _patched_mt5(fake):
        _with_strategy(dict(_BASE_STRATEGY), agent.run_cycle)
    assert agent.mt5.closed == ["Basket_SL_Hit"] and fake.rate_calls == 0


def test_run_cycle_atr_stop_triggers_when_usd_stop_is_not_reached():
    agent = _make_monitor([{**p, "profit": -1.0} for p in _eur_buy_grid(1.0929)])
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        _with_strategy(dict(_BASE_STRATEGY), agent.run_cycle)
    assert _closed(agent) == [1, 2, 3] and agent.mt5.closed == []


def test_run_cycle_healthy_basket_is_untouched():
    agent = _make_monitor(_eur_buy_grid(1.0940))
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        _with_strategy(dict(_BASE_STRATEGY), agent.run_cycle)
    assert agent.mt5.closed == [] and agent.mt5.closed_tickets == []


def test_two_breached_baskets_are_both_closed_and_healthy_symbol_is_kept():
    fake = _FakeMT5Module({"EURUSD": _bars(), "GBPUSD": _bars(), "AUDUSD": _bars()},
                          {s: _EUR_INFO for s in ("EURUSD", "GBPUSD", "AUDUSD")})
    gbp = [_pos("GBPUSD", "BUY", e, 1.0929, ticket=20 + i) for i, e in enumerate((1.1000, 1.0975, 1.0950))]
    aud = [_pos("AUDUSD", "BUY", e, 1.0940, ticket=30 + i) for i, e in enumerate((1.1000, 1.0975, 1.0950))]
    agent = _make_monitor(_eur_buy_grid(1.0929) + gbp + aud)
    with _patched_mt5(fake):
        assert _check(agent) is True
    assert _closed(agent) == [1, 2, 3, 20, 21, 22]
    assert sorted(p["ticket"] for p in agent.mt5.positions) == [30, 31, 32]


def test_failed_close_is_reported_and_does_not_stop_the_rest():
    agent = _make_monitor(_eur_buy_grid(1.0929), failing_tickets={2})
    with _patched_mt5(_FakeMT5Module({"EURUSD": _bars()}, {"EURUSD": _EUR_INFO})):
        assert _check(agent) is True
    assert _closed(agent) == [1, 3]
    errors = [msg for level, msg in agent.logs if level == "ERROR"]
    assert len(errors) == 1 and "#2" in errors[0], agent.logs


def test_run_cycle_keeps_managing_other_symbols_after_an_atr_close():
    managed = []
    fake = _FakeMT5Module({"EURUSD": _bars(), "GBPUSD": _bars()}, {s: _EUR_INFO for s in ("EURUSD", "GBPUSD")})
    gbp = [_pos("GBPUSD", "BUY", e, 1.0940, ticket=20 + i) for i, e in enumerate((1.1000, 1.0975, 1.0950))]
    agent = _make_monitor([{**p, "profit": -1.0} for p in _eur_buy_grid(1.0929) + gbp])

    async def _record(pos):
        managed.append(pos["ticket"])

    agent._manage_position = _record
    with _patched_mt5(fake):
        _with_strategy(dict(_BASE_STRATEGY), agent.run_cycle)
    assert _closed(agent) == [1, 2, 3]
    assert managed == [20, 21, 22], managed


def test_monitor_pip_size_per_symbol():
    for symbol, want in (("EURUSD", 0.0001), ("USDJPY", 0.01), ("XAUUSD", 0.1)):
        assert MonitorAgent._pip_size(symbol) == want, symbol


# ---------------------------------------------------------------------------
# 0.5 / 0.4 — حد السبريد لكل رمز من مصدر واحد، وfail-closed
# ---------------------------------------------------------------------------

class _patched_strategy:
    """يبدّل قيماً في config.STRATEGY مؤقتاً (القاموس نفسه، فيراه كل من استورده)."""
    def __init__(self, **changes):
        self.changes = changes

    def __enter__(self):
        self.old = {k: config.STRATEGY.get(k) for k in self.changes}
        config.STRATEGY.update(self.changes)

    def __exit__(self, *exc):
        config.STRATEGY.update(self.old)


def test_max_spread_for_uses_symbol_limit_then_default():
    assert config.max_spread_for("EURUSD") == 3.0
    assert config.max_spread_for("GBPJPY") == 7.0
    assert config.max_spread_for("XAUUSD") == 40.0
    assert config.max_spread_for("NZDCHF") == config.STRATEGY["max_spread_pips"] == 4.0


def test_max_spread_for_ignores_unusable_limits():
    bad = {"EURUSD": 0, "GBPUSD": -2.0, "USDJPY": "x", "AUDUSD": True, "USDCAD": float("nan"), "USDCHF": None}
    with _patched_strategy(symbol_spread_limits=bad):
        for symbol in bad:
            assert config.max_spread_for(symbol) == 4.0, symbol        # الحد لا يُعطَّل بقيمة سيئة


def _slippage(symbol, tick):
    gw = gwmod.SafeExecutionGateway.__new__(gwmod.SafeExecutionGateway)
    gw.mt5 = SimpleNamespace(get_tick=lambda s: tick)
    return asyncio.run(gw._check_slippage(symbol, "BUY"))


def test_gateway_spread_limit_comes_from_config():
    assert _slippage("EURUSD", {"spread": 3.0})[0] is True
    assert _slippage("EURUSD", {"spread": 3.1})[0] is False
    assert _slippage("GBPJPY", {"spread": 7.0})[0] is True
    assert _slippage("NZDCHF", {"spread": 3.9})[0] is True              # رمز غير مُدرَج → الحد الافتراضي 4.0
    assert _slippage("NZDCHF", {"spread": 4.1})[0] is False             # كان الافتراضي المنسوخ 8 يقبلها


def test_gateway_spread_follows_config_changes():
    with _patched_strategy(symbol_spread_limits={"EURUSD": 1.0}):
        assert _slippage("EURUSD", {"spread": 2.0})[0] is False
    assert _slippage("EURUSD", {"spread": 2.0})[0] is True


def test_gateway_unknown_spread_is_rejected_not_treated_as_zero():
    for tick in (None, {}, {"spread": None}, {"spread": float("nan")}, {"spread": "wide"}, {"spread": -1.0}):
        ok, msg = _slippage("EURUSD", tick)
        assert ok is False, (tick, msg)


def test_market_analyst_spread_gate_is_per_symbol_and_fail_closed():
    analyst = ma.MarketAnalystAgent.__new__(ma.MarketAnalystAgent)
    assert analyst._check_spread(3.0, "EURUSD") is True
    assert analyst._check_spread(3.5, "EURUSD") is False
    assert analyst._check_spread(6.5, "GBPJPY") is True                  # كان الحد الموحَّد 4.0 يرفضها
    assert analyst._check_spread(float("nan"), "EURUSD") is False


# ---------------------------------------------------------------------------
# 0.4 — أرباح التداول الورقي: لا مضاعِف ×10 مخفي
# ---------------------------------------------------------------------------

def _paper_connector():
    conn = MT5Connector.__new__(MT5Connector)
    conn._use_yfinance = True          # get_pip_value يرجع لجدول القيم الثابتة
    return conn


def test_paper_pnl_matches_pip_value_without_hidden_multiplier():
    conn = _paper_connector()
    assert abs(conn.paper_pnl_usd("EURUSD", "BUY", 1.1000, 1.1010, 1.0) - 100.0) < 1e-6    # 10 بيب × 10$
    assert abs(conn.paper_pnl_usd("EURUSD", "SELL", 1.1000, 1.1010, 1.0) + 100.0) < 1e-6
    assert abs(conn.paper_pnl_usd("EURUSD", "BUY", 1.1000, 1.1010, 0.01) - 1.0) < 1e-6
    assert abs(conn.paper_pnl_usd("USDJPY", "BUY", 150.00, 150.10, 0.1) - 6.7) < 1e-6      # 10 بيب × 6.7$ × 0.1


def test_gateway_paper_trace_closes_with_the_same_pnl():
    conn = _paper_connector()
    conn.get_tick = lambda s: {"ask": 1.1010, "bid": 1.1010, "spread": 1.0}
    trade = SimpleNamespace(status=None, close_price=None, profit_usd=None, closed_at=None)
    emitted = []

    class _Query:
        def filter(self, *a):
            return self

        def first(self):
            return trade

    class _Session:
        def query(self, *a):
            return _Query()

        def commit(self):
            pass

        def close(self):
            pass

    async def _emit(**kw):
        emitted.append(kw)

    async def _no_sleep(_):
        return None

    gw = gwmod.SafeExecutionGateway.__new__(gwmod.SafeExecutionGateway)
    gw.mt5, gw._active_tasks = conn, {}
    gw.bus = SimpleNamespace(emit_trade_closed=_emit)
    old_sleep, old_session = asyncio.sleep, gwmod.SessionLocal
    asyncio.sleep, gwmod.SessionLocal = _no_sleep, _Session
    try:
        asyncio.run(gw._trace_position_loop(7, "EURUSD", "BUY", 1.1000, 0.0, 1.1010, 1.0, "PAPER"))
    finally:
        asyncio.sleep, gwmod.SessionLocal = old_sleep, old_session
    assert abs(trade.profit_usd - 100.0) < 1e-6, trade.profit_usd
    assert emitted and abs(emitted[0]["profit"] - 100.0) < 1e-6, emitted


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
