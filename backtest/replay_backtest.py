#!/usr/bin/env python
"""
backtest/replay_backtest.py — إعادة تشغيل منطق النظام الحقيقي على بيانات MT5 التاريخية
=====================================================================================
يعيد تشغيل نفس الكود الحي (لا نسخة مبسّطة منه):
  TechnicalIndicators → FSMEngine → VotingEngine → بوابة (signal_strong & trade_allowed)
  → تأكيد H4 → حد السبريد → قواعد التنفيذ (cascade / DD / max_open_trades / الشبكة / flash spread)
  → RiskManager.calc_trade_params → MonitorAgent.run_cycle الحقيقي (سلة لكل رمز بوقف ATR 1:1،
  break-even، trailing، حماية DD) على وسيط محاكى SimBroker.

أمران:
  export : MT5 → CSV (يتطلب MetaTrader5 ومحطة مفتوحة؛ قراءة فقط، لا أوامر تداول إطلاقاً)
  run    : CSV → إعادة التشغيل → تقرير (لا يحتاج MT5 ولا إنترنت)

أمثلة:
  python backtest/replay_backtest.py export --days 365
  python backtest/replay_backtest.py run --oos-fraction 0.3
  python backtest/replay_backtest.py run --legacy-basket --out backtest/out_legacy   # مقارنة بالسلة القديمة
  python backtest/replay_backtest.py run --set basket_rr=1.5 --set basket_sl_atr_mult=2.0
  python backtest/replay_backtest.py run --signal-mode random --seed 1      # تحكم: نفس التوقيت، اتجاه عشوائي
  python backtest/replay_backtest.py run --signal-mode invert               # تحكم: عكس الاتجاه
  python backtest/replay_backtest.py run --regimes STRONG_TREND --path-order adverse

افتراضات التقريب موثّقة في backtest/README.md وفي تقرير التشغيل نفسه (قسم assumptions).
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import csv
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "backend"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # طباعة آمنة على كونسول ويندوز
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

TF_HOURS = 1
CONTRACT_SIZE = {"XAU": 100.0, "XAG": 5000.0}          # الافتراضي للفوركس 100000
APPROX_USD_RATES = {"JPY": 1 / 150.0, "GBP": 1.27, "EUR": 1.08, "CHF": 1.12, "CAD": 0.73, "AUD": 0.65, "NZD": 0.60}

ASSUMPTIONS = [
    "Timeframe H1; signals evaluated on CLOSED bars, entry at NEXT bar open (live evaluates continuously on the forming bar).",
    "Intrabar path per bar: O->L->H->C for bullish bars, O->H->L->C for bearish bars (real order is unknowable from OHLC).",
    "Basket target/stop fills at the exact threshold price found by bisection on the REAL MonitorAgent verdict (no slippage).",
    "Broker-side SL fills at the SL price (at the open price on gaps). No slippage, no requotes, no swap/rollover.",
    "Spread: per-bar spread_pips column from MT5 export (falls back to --default-spread-pips). Commission = --commission-per-lot round turn.",
    "NOT replicated: news blackout/sentiment, reflection cooldown, adaptive confidence boost, TimesFM, shadow council, learned vote weights, "
    "SafeExecutionGateway consensus/extra gates, partial closes (disabled in config), margin/stop-out.",
    "Hedge mode (DD>=hedge_dd_percent) is simulated but fires once per monitor cycle (replay has ~4 cycles/bar vs ~3600/hour live).",
    "Cascade protection counts every losing POSITION close (a 3-layer losing basket counts as 3).",
    "H4 filter built by resampling H1 (server-time bins), including the forming H4 bar like live get_ohlcv(pos 0).",
]


# ══════════════════════════════════════════════════════════════════════
# export: MT5 -> CSV
# ══════════════════════════════════════════════════════════════════════
def cmd_export(args) -> int:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 package not installed: pip install MetaTrader5", file=sys.stderr)
        return 2
    import pandas as pd
    from config import SYMBOLS
    from core.mt5_connector import MT5Connector

    path = os.getenv("MT5_TERMINAL_PATH") or None
    ok = mt5.initialize(path=path) if path else mt5.initialize()
    if not ok:
        print(f"mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        return 2
    os.makedirs(args.data_dir, exist_ok=True)
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else list(SYMBOLS)
    date_to = datetime.utcnow()
    date_from = date_to - timedelta(days=args.days)
    written = 0
    try:
        for sym in symbols:
            mt5.symbol_select(sym, True)
            info = mt5.symbol_info(sym)
            rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, date_from, date_to)
            if info is None or rates is None or len(rates) == 0:
                print(f"[skip] {sym}: no data ({mt5.last_error()})")
                continue
            df = pd.DataFrame(rates)
            pip = MT5Connector.get_pip_size(sym, info.digits)
            df["time"] = pd.to_datetime(df["time"], unit="s")  # وقت خادم الوسيط (يطابق ما يراه النظام الحي)
            df["spread_pips"] = (df["spread"] * info.point / pip).round(2)
            df = df.rename(columns={"tick_volume": "volume"})[["time", "open", "high", "low", "close", "volume", "spread_pips"]]
            out = os.path.join(args.data_dir, f"{sym}_H1.csv")
            df.to_csv(out, index=False)
            written += 1
            print(f"[ok] {sym}: {len(df)} bars  {df['time'].iloc[0]} -> {df['time'].iloc[-1]}  median spread {df['spread_pips'].median():.2f} pips  -> {out}")
    finally:
        mt5.shutdown()
    return 0 if written else 1


# ══════════════════════════════════════════════════════════════════════
# SimBroker: وسيط محاكى يطابق واجهة MT5Connector التي يستعملها MonitorAgent
# ══════════════════════════════════════════════════════════════════════
def _pip_size(symbol: str) -> float:
    from core.mt5_connector import MT5Connector
    return MT5Connector.get_pip_size(symbol)


def _digits(symbol: str) -> int:
    s = symbol.upper()
    if "XAU" in s or "XAG" in s:
        return 2
    return 3 if "JPY" in s else 5


def pip_value_usd(symbol: str, price: float, last: Dict[str, float], warned: Optional[set] = None) -> float:
    """قيمة البيب بالدولار للوت القياسي. أزواج التقاطع تُحوَّل بآخر سعر معروف لزوج دولار."""
    sym = symbol.upper()
    pip = _pip_size(sym)
    contract = next((v for k, v in CONTRACT_SIZE.items() if k in sym), 100000.0)
    per_pip_quote = pip * contract
    base, quote = sym[:3], sym[3:6]
    if quote == "USD":
        return per_pip_quote
    if base == "USD":
        return per_pip_quote / price
    if f"{quote}USD" in last:
        return per_pip_quote * last[f"{quote}USD"]
    if f"USD{quote}" in last:
        return per_pip_quote / last[f"USD{quote}"]
    if warned is not None and quote not in warned:
        warned.add(quote)
        print(f"[warn] no {quote}USD/USD{quote} data loaded: approximating pip value for {symbol}", file=sys.stderr)
    return per_pip_quote * APPROX_USD_RATES.get(quote, 1.0)


class SimBroker:
    _use_yfinance = True   # يمنع مسارات MT5 الحية داخل MonitorAgent
    connected = False

    def __init__(self, balance: float, commission_per_lot: float = 0.0, magic: int = 0):
        self.balance = float(balance)
        self.commission_per_lot = float(commission_per_lot)
        self.magic = magic
        self.sim_time = datetime(2000, 1, 1)
        self.positions: Dict[int, dict] = {}
        self.closed: List[dict] = []
        self.bid: Dict[str, float] = {}
        self.spread_price: Dict[str, float] = {}
        self._ticket = 1000
        self.on_close: Optional[Callable[[dict], None]] = None
        self._warned: set = set()
        self.modify_count = 0

    # ── الأسعار ──────────────────────────────────────────────────────
    def set_price(self, symbol: str, bid: float, spread_pips: float):
        self.bid[symbol] = bid
        self.spread_price[symbol] = spread_pips * _pip_size(symbol)
        self._revalue(symbol)

    def ask(self, symbol: str) -> float:
        return self.bid[symbol] + self.spread_price[symbol]

    def _pv(self, symbol: str) -> float:
        return pip_value_usd(symbol, self.bid[symbol], self.bid, self._warned)

    def _price_for(self, pos: dict) -> float:
        s = pos["symbol"]
        return self.bid[s] if pos["type"] == "BUY" else self.ask(s)

    def _pnl(self, pos: dict, price: float) -> float:
        sign = 1.0 if pos["type"] == "BUY" else -1.0
        pips = (price - pos["open_price"]) * sign / _pip_size(pos["symbol"])
        return pips * self._pv(pos["symbol"]) * pos["volume"]

    def _revalue(self, symbol: str):
        for pos in self.positions.values():
            if pos["symbol"] == symbol:
                pos["current_price"] = self._price_for(pos)
                pos["profit"] = self._pnl(pos, pos["current_price"])

    # ── واجهة MT5Connector ────────────────────────────────────────────
    def get_account(self) -> dict:
        floating = sum(p["profit"] for p in self.positions.values())
        return {"balance": self.balance, "equity": self.balance + floating}

    def get_open_positions(self, symbol=None) -> List[dict]:
        return [dict(p) for p in self.positions.values() if symbol is None or p["symbol"] == symbol]

    def get_tick(self, symbol: str):
        if symbol not in self.bid:
            return None
        return {"symbol": symbol, "bid": self.bid[symbol], "ask": self.ask(symbol),
                "spread": round(self.spread_price[symbol] / _pip_size(symbol), 2)}

    def get_digits(self, symbol: str) -> int:
        return _digits(symbol)

    def open_trade(self, symbol, direction, lot, sl=0.0, tp=0.0, comment="", magic=None, **_):
        ticket = self.open_position(symbol, direction, lot, sl, tp, magic if magic is not None else self.magic, comment)
        return {"success": True, "ticket": ticket}

    def open_position(self, symbol, direction, lot, sl, tp, magic, comment="", meta=None) -> int:
        self._ticket += 1
        price = self.ask(symbol) if direction == "BUY" else self.bid[symbol]
        pos = {
            "ticket": self._ticket, "symbol": symbol, "type": direction, "volume": float(lot),
            "open_price": price, "current_price": self._price_for({"symbol": symbol, "type": direction}),
            "sl": float(sl or 0.0), "tp": float(tp or 0.0), "profit": 0.0, "swap": 0.0,
            "comment": comment, "magic": magic, "open_time": self.sim_time.isoformat() + "+00:00",
            "_meta": meta or {}, "_sl_moved": False,
        }
        self.positions[self._ticket] = pos
        self._revalue(symbol)
        return self._ticket

    def modify_sl(self, ticket, new_sl) -> bool:
        pos = self.positions.get(ticket)
        if pos is None:
            return False
        pos["sl"] = float(new_sl)
        pos["_sl_moved"] = True
        self.modify_count += 1
        return True

    def partial_close(self, ticket, pct) -> bool:
        pos = self.positions.get(ticket)
        if pos is None:
            return False
        part = round(pos["volume"] * pct, 2)
        if part < 0.01 or part >= pos["volume"]:
            return False
        self._record_close(pos, self._price_for(pos), "Partial", volume=part)
        pos["volume"] = round(pos["volume"] - part, 2)
        pos["profit"] = self._pnl(pos, pos["current_price"])
        return True

    def close_position(self, ticket, comment="") -> bool:
        pos = self.positions.pop(ticket, None)
        if pos is None:
            return False
        self._record_close(pos, self._price_for(pos), comment or "Closed")
        return True

    def close_all_positions(self, symbol=None, reason="AI_Emergency", magic_numbers=None):
        targets = self.get_open_positions(symbol)
        if magic_numbers is not None:
            allowed = set(magic_numbers)
            targets = [p for p in targets if p.get("magic") in allowed]
        for p in targets:
            self.close_position(p["ticket"], comment=reason)

    def _record_close(self, pos: dict, price: float, reason: str, volume: Optional[float] = None):
        vol = volume if volume is not None else pos["volume"]
        gross = self._pnl({**pos, "volume": vol}, price)
        commission = self.commission_per_lot * vol
        net = gross - commission
        self.balance += net
        rec = {
            "ticket": pos["ticket"], "symbol": pos["symbol"], "direction": pos["type"], "volume": vol,
            "entry": pos["open_price"], "exit": price, "open_time": pos["open_time"],
            "close_time": self.sim_time.isoformat(), "gross": gross, "commission": commission, "net": net,
            "reason": reason, "magic": pos.get("magic"),
            "regime": pos.get("_meta", {}).get("regime", ""), "atr_pips": pos.get("_meta", {}).get("atr_pips", 0.0),
            "sl_moved": pos.get("_sl_moved", False),
        }
        self.closed.append(rec)
        if self.on_close and reason != "Partial":
            self.on_close(rec)

    # ── وقف الوسيط (SL على الخادم) ─────────────────────────────────────
    def apply_broker_stops(self, symbol: str, gap: bool = False) -> int:
        hits = 0
        for pos in list(self.positions.values()):
            if pos["symbol"] != symbol or pos["sl"] <= 0:
                continue
            cur = self._price_for(pos)
            hit = cur <= pos["sl"] if pos["type"] == "BUY" else cur >= pos["sl"]
            if not hit:
                continue
            fill = cur if gap else pos["sl"]
            label = "Broker_SL_Trail" if pos.get("_sl_moved") else "Broker_SL"
            self.positions.pop(pos["ticket"])
            self._record_close(pos, fill, label)
            hits += 1
        return hits

    def sl_breached(self, symbol: str, bid: float) -> bool:
        ask = bid + self.spread_price[symbol]
        for pos in self.positions.values():
            if pos["symbol"] == symbol and pos["sl"] > 0:
                if (pos["type"] == "BUY" and bid <= pos["sl"]) or (pos["type"] == "SELL" and ask >= pos["sl"]):
                    return True
        return False

    def positions_at(self, symbol: str, bid: float) -> List[dict]:
        """نسخ من صفقات الرمز مُقيَّمة عند سعر افتراضي (للبحث عن لحظة بلوغ العتبة دون لمس الحالة)."""
        ask = bid + self.spread_price[symbol]
        out = []
        for pos in self.positions.values():
            if pos["symbol"] != symbol:
                continue
            cur = bid if pos["type"] == "BUY" else ask
            c = dict(pos)
            c["current_price"] = cur
            c["profit"] = self._pnl(pos, cur)
            out.append(c)
        return out


# ══════════════════════════════════════════════════════════════════════
# المقاييس (دوال نقية قابلة للاختبار)
# ══════════════════════════════════════════════════════════════════════
def wilson_interval(wins: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _stats(pnls: List[float]) -> dict:
    n = len(pnls)
    if n == 0:
        return {"n": 0}
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    payoff = avg_win / abs(avg_loss) if avg_loss else float("inf") if avg_win else 0.0
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    mean = sum(pnls) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in pnls) / (n - 1)) if n > 1 else 0.0
    lo, hi = wilson_interval(len(wins), n)
    streak = best = 0
    for x in pnls:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    return {
        "n": n, "wins": len(wins), "win_rate": round(len(wins) / n, 4),
        "win_rate_ci95": [round(lo, 4), round(hi, 4)],
        "avg_win": round(avg_win, 4), "avg_loss": round(avg_loss, 4),
        "payoff_ratio": None if payoff == float("inf") else round(payoff, 3),
        "breakeven_win_rate": None if payoff in (0.0, float("inf")) else round(1 / (1 + payoff), 4),
        "expectancy": round(mean, 4),
        "t_stat": round(mean / (sd / math.sqrt(n)), 2) if sd > 0 else None,
        "profit_factor": None if gross_loss == 0 else round(gross_win / gross_loss, 3),
        "net": round(sum(pnls), 2), "max_losing_streak": best,
    }


def group_baskets(trades: List[dict]) -> List[dict]:
    """يجمع إغلاقات السلة (نفس الرمز والزمن والسبب) في وحدة واحدة؛ وقف الوسيط يبقى لكل صفقة."""
    groups: Dict[tuple, dict] = {}
    out = []
    for t in trades:
        if t["reason"].startswith("Broker_SL") or t["reason"] in ("Partial", "End_Of_Data"):
            out.append(dict(t))
            continue
        key = (t["symbol"], t["close_time"], t["reason"])
        if key not in groups:
            groups[key] = dict(t)
        else:
            groups[key]["net"] += t["net"]
    return out + list(groups.values())


def compute_metrics(trades: List[dict], initial_balance: float, equity: Optional[List[tuple]] = None) -> dict:
    """trades: سجلات الإغلاق (بلا Partial). 'End_Of_Data' تُستبعد من الإحصاءات وتُعدّ منفصلة."""
    real = [t for t in trades if t["reason"] not in ("Partial", "End_Of_Data")]
    ended = [t for t in trades if t["reason"] == "End_Of_Data"]
    baskets = group_baskets(real)
    res = {
        "positions": _stats([t["net"] for t in sorted(real, key=lambda x: x["close_time"])]),
        "baskets": _stats([b["net"] for b in sorted(baskets, key=lambda x: x["close_time"])]),
        "open_at_end_floating_net": round(sum(t["net"] for t in ended), 2),
        "open_at_end_count": len(ended),
    }
    for label, keyf in (("by_symbol", lambda b: b["symbol"]), ("by_exit_reason", lambda b: b["reason"]),
                        ("by_regime", lambda b: b.get("regime") or "UNKNOWN")):
        buckets: Dict[str, List[float]] = {}
        for b in baskets:
            buckets.setdefault(keyf(b), []).append(b["net"])
        res[label] = {k: _stats(v) for k, v in sorted(buckets.items())}
    if equity:
        peak, max_dd = initial_balance, 0.0
        for _, e in equity:
            peak = max(peak, e)
            if peak > 0:
                max_dd = max(max_dd, (peak - e) / peak)
        res["max_equity_drawdown_pct"] = round(max_dd * 100, 2)
        res["final_equity"] = round(equity[-1][1], 2)
        res["return_pct"] = round((equity[-1][1] / initial_balance - 1) * 100, 2)
    return res


# ══════════════════════════════════════════════════════════════════════
# محرك إعادة التشغيل
# ══════════════════════════════════════════════════════════════════════
def bar_path(o: float, h: float, l: float, c: float, order: str = "ohlc", net_long: Optional[bool] = None) -> List[float]:
    """مسار الأسعار داخل الشمعة. ohlc: الصاعدة O,L,H,C والهابطة O,H,L,C.
    adverse/favorable: يعتمدان على اتجاه الصفقات المفتوحة (net_long): الأسوأ/الأفضل أولاً لها (دون صفقات → ohlc)."""
    default = [o, l, h, c] if c >= o else [o, h, l, c]
    if order == "ohlc" or net_long is None:
        return default
    low_first, high_first = [o, l, h, c], [o, h, l, c]
    if order == "adverse":
        return low_first if net_long else high_first
    return high_first if net_long else low_first   # favorable


class Replay:
    def __init__(self, data: Dict[str, "pd.DataFrame"], args, signal_fn: Optional[Callable] = None):
        from config import MAGIC_NUMBERS, STRATEGY
        import agents.monitor_agent as mon
        from core.fsm_engine import FSMEngine
        from core.indicators import TechnicalIndicators
        from core.risk_manager import RiskManager
        from core.voting_engine import VotingEngine

        self.S = STRATEGY
        self.mon = mon
        self.magic = MAGIC_NUMBERS["live_engine"]
        self.data = data
        self.args = args
        self.risk = RiskManager()
        self.ind = TechnicalIndicators()
        self.voting = VotingEngine()
        self.fsm = {s: FSMEngine() for s in data}
        self.signal_fn = signal_fn or self._real_signal
        self.rng = random.Random(getattr(args, "seed", 1))
        self._sig_store: Dict[str, dict] = {}
        self.broker = SimBroker(args.balance, args.commission_per_lot, self.magic)
        self.broker.on_close = self._on_close
        self.agent = None
        self.rejects: Dict[str, int] = {}
        self.signals_seen = 0
        self.equity: List[tuple] = []
        self.consec_losses = 0
        self.blocked_until: Optional[datetime] = None
        self._pos_index = {s: {t: i for i, t in enumerate(df.index)} for s, df in data.items()}
        self._h4 = {s: self._build_h4(df) for s, df in data.items()}

    # ── H4 ───────────────────────────────────────────────────────────
    @staticmethod
    def _build_h4(df):
        h4 = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        bin_of = df.index.floor("4h")
        first_pos = {}
        for i, b in enumerate(bin_of):
            first_pos.setdefault(b, i)
        return {"h4": h4, "bin_of": bin_of, "first_pos": first_pos}

    def _h4_frame(self, sym: str, i: int):
        import pandas as pd
        info, df = self._h4[sym], self.data[sym]
        b = info["bin_of"][i]
        full = info["h4"].loc[info["h4"].index < b]
        part = df.iloc[info["first_pos"][b]: i + 1]
        cur = pd.DataFrame([{"open": part["open"].iloc[0], "high": part["high"].max(), "low": part["low"].min(),
                             "close": part["close"].iloc[-1], "volume": part["volume"].sum()}], index=[b])
        return pd.concat([full.tail(59), cur])

    def _h4_ok(self, sym: str, i: int, direction: str) -> bool:
        f = self._h4_frame(sym, i)
        if len(f) < 55:
            return False
        iv = self.ind.calculate(f, 0)
        if not iv.is_valid():
            return False
        return (direction == "BUY" and iv.close > iv.ema) or (direction == "SELL" and iv.close < iv.ema)

    # ── الإشارة (نفس خط MarketAnalystAgent._analyze_symbol) ───────────────
    def _pipeline(self, sym: str, i: int):
        """يُرجع (إشارة|None, سبب رفض|None). دالة نقية من البيانات فقط، لذلك تُخزَّن مؤقتاً على القرص."""
        df = self.data[sym]
        row = df.iloc[i]
        spread = float(row["spread_pips"])
        win = df.iloc[max(0, i - 199): i + 1][["open", "high", "low", "close", "volume"]]
        iv = self.ind.calculate(win, spread)
        if not iv.is_valid():
            return None, None
        fsm = self.fsm[sym].detect(iv)
        vt = self.voting.vote(iv, fsm)
        if not (vt.signal_strong and fsm.trade_allowed) or vt.direction not in ("BUY", "SELL"):
            return None, None
        if not self._h4_ok(sym, i, vt.direction):
            return None, "h4_counter_trend"
        limit = self.S.get("symbol_spread_limits", {}).get(sym, self.S["max_spread_pips"])
        if spread > limit:
            return None, "signal_spread_too_high"
        return {"symbol": sym, "direction": vt.direction, "atr": iv.atr, "regime": fsm.regime.value,
                "confidence": vt.confidence}, None

    def _cache_path(self, sym: str) -> Optional[str]:
        cdir = getattr(self.args, "cache_dir", None)
        if not cdir or str(cdir).lower() == "none":
            return None
        import pandas as pd
        import config as _cfg
        h = hashlib.sha1()
        h.update(pd.util.hash_pandas_object(self.data[sym], index=True).values.tobytes())
        h.update(json.dumps({"warmup": self.args.warmup, "ind": _cfg.INDICATORS,
                             "entry": getattr(_cfg, "ENTRY_UPGRADES_2026", {}),
                             "strategy": {k: self.S.get(k) for k in ("min_vote_score", "max_spread_pips", "symbol_spread_limits")}},
                            sort_keys=True, default=str).encode())
        for mod in ("indicators.py", "fsm_engine.py", "voting_engine.py"):
            with open(os.path.join(ROOT, "backend", "core", mod), "rb") as fh:
                h.update(fh.read())
        os.makedirs(cdir, exist_ok=True)
        return os.path.join(cdir, f"signals_{sym}_{h.hexdigest()[:16]}.json")

    def _signals_for(self, sym: str) -> dict:
        if sym in self._sig_store:
            return self._sig_store[sym]
        path = self._cache_path(sym)
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                store = json.load(fh)
        else:
            print(f"  computing entry signals for {sym} (one-time, cached to disk)...", flush=True)
            store = {"passed": {}, "rejected": {}}
            for i in range(max(self.args.warmup - 1, 0), len(self.data[sym])):
                sig, why = self._pipeline(sym, i)
                if sig is not None:
                    store["passed"][str(i)] = sig
                elif why:
                    store["rejected"][str(i)] = why
            if path:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(store, fh)
                os.replace(tmp, path)
        self._sig_store[sym] = store
        return store

    def _real_signal(self, sym: str, i: int) -> Optional[dict]:
        from core.fsm_engine import Regime
        store = self._signals_for(sym)
        why = store["rejected"].get(str(i))
        if why:
            self._rej(why)
            return None
        raw = store["passed"].get(str(i))
        if raw is None:
            return None
        sig = dict(raw)
        sig["regime"] = Regime(sig["regime"])
        allowed = getattr(self.args, "regimes", None)
        if allowed and sig["regime"].value not in allowed:
            self._rej("regime_filtered")
            return None
        mode = getattr(self.args, "signal_mode", "real")
        if mode == "random":
            sig["direction"] = self.rng.choice(("BUY", "SELL"))
        elif mode == "invert":
            sig["direction"] = "SELL" if sig["direction"] == "BUY" else "BUY"
        return sig

    def _rej(self, why: str):
        self.rejects[why] = self.rejects.get(why, 0) + 1

    # ── قواعد التنفيذ (ExecutionAgent._process_signal) ────────────────────
    def _on_close(self, rec: dict):
        if rec["net"] < 0:
            self.consec_losses += 1
        else:
            self.consec_losses = 0
        if self.consec_losses >= self.S["cascade_max_losses"]:
            self.blocked_until = self.broker.sim_time + timedelta(minutes=self.S["cascade_cooldown_min"])

    def _try_open(self, sig: dict):
        b, S = self.broker, self.S
        sym, d = sig["symbol"], sig["direction"]
        if self.blocked_until is not None:
            if b.sim_time < self.blocked_until:
                return self._rej("cascade_block")
            self.blocked_until, self.consec_losses = None, 0
        acc = b.get_account()
        if not self.risk.check_dd_protection(acc["balance"], acc["equity"])["ok"]:
            b.close_all_positions(reason="Emergency_Stop")
            return self._rej("dd_emergency")
        if len(b.positions) >= S["max_open_trades"]:
            return self._rej("max_open_trades")
        tick = b.get_tick(sym)
        price = tick["ask"] if d == "BUY" else tick["bid"]
        same = [p for p in b.get_open_positions(sym) if p["type"] == d]
        if same:
            if len(same) >= S.get("max_open_trades", 5):
                return self._rej("max_same_direction")
            latest = sorted(same, key=lambda p: p["open_time"], reverse=True)[0]
            moved = latest["open_price"] - price if d == "BUY" else price - latest["open_price"]
            if moved < S.get("grid_distance_pips", 25) * _pip_size(sym):
                return self._rej("grid_distance_not_reached")
        limit = S.get("symbol_spread_limits", {}).get(sym, S.get("max_spread_pips", 4.0))
        if tick["spread"] > limit * 1.4:
            return self._rej("flash_spread")
        pv = pip_value_usd(sym, b.bid[sym], b.bid, b._warned)
        tp = self.risk.calc_trade_params(sym, d, price, sig["atr"], acc["balance"], pv, _digits(sym))
        if not tp.valid:
            return self._rej("invalid_trade_params")
        regime = sig["regime"]
        ticket = b.open_position(sym, d, tp.lot_size, tp.sl_price, tp.tp_price, self.magic, "replay",
                                 meta={"regime": getattr(regime, "value", str(regime)),
                                       "atr_pips": sig["atr"] / _pip_size(sym)})
        st = self.mon.MonitorAgent._State()
        st.fsm_regime = regime if hasattr(regime, "value") else None
        self.agent._untracked_state[ticket] = st
        if not self.args.legacy_basket:
            self.agent._basket_atr_cache[ticket] = sig["atr"]   # = Signal.atr_value المجمَّد لحظة الدخول

    # ── مراقب حقيقي فوق وسيط محاكى ───────────────────────────────────────
    def _make_agent(self):
        mon = self.mon

        class _Q:
            def filter(self, *a, **k): return self
            def all(self): return []
            def first(self): return None

        class _Sess:
            def query(self, *a, **k): return _Q()
            def commit(self): pass
            def close(self): pass

        self._sess_patch = __import__("unittest.mock", fromlist=["patch"]).patch.object(mon, "SessionLocal", lambda: _Sess())
        self._sess_patch.start()
        agent = mon.MonitorAgent(self.broker)
        agent._get_db_trade = lambda t: None

        async def _quiet_log(level, message, extra=None):
            return None
        agent.log = _quiet_log
        self.agent = agent

    def _set_prices(self, paths: dict, k: int, f: float, t: datetime):
        for s, p in paths.items():
            a, c = p["pts"][k - 1], p["pts"][k]
            self.broker.set_price(s, a + (c - a) * f, p["spread"])
        self.broker.sim_time = t + timedelta(minutes=20 * (k - 1 + f))

    def _event_fraction(self, paths: dict, k: int, lo: float) -> Optional[float]:
        """أبكر نقطة على المقطع تُحدِث فيها عتبة سلة أو SL للوسيط. يستعمل حكم MonitorAgent الحقيقي."""
        b = self.broker
        best = None
        for s in {p["symbol"] for p in b.positions.values()}:
            if s not in paths:
                continue
            a, c = paths[s]["pts"][k - 1], paths[s]["pts"][k]
            def hit(f, s=s, a=a, c=c):
                bid = a + (c - a) * f
                if b.sl_breached(s, bid):
                    return True
                sys_pos = [p for p in b.positions_at(s, bid) if p["magic"] in self.system_magics]
                return bool(sys_pos) and self.agent._evaluate_symbol_basket(s, sys_pos) is not None
            if not hit(1.0):
                continue
            left, right = lo, 1.0
            if hit(left):
                right = left
            else:
                for _ in range(30):
                    mid = (left + right) / 2
                    if hit(mid):
                        right = mid
                    else:
                        left = mid
            best = right if best is None else min(best, right)
        return best

    async def _advance(self, paths: dict, k: int, t: datetime):
        lo, guard = 0.0, 0
        while True:
            f = self._event_fraction(paths, k, lo)
            guard += 1
            if f is None or guard > 60:
                f = 1.0
            self._set_prices(paths, k, f, t)
            for s in paths:
                self.broker.apply_broker_stops(s)
            await self.agent.run_cycle()
            self._rec_equity()
            if f >= 1.0:
                return
            lo = f

    def _rec_equity(self):
        self.equity.append((self.broker.sim_time, self.broker.get_account()["equity"]))

    # ── الحلقة الرئيسية ───────────────────────────────────────────────
    async def run(self, progress: bool = True) -> dict:
        from config import MAGIC_NUMBERS
        self.system_magics = set(MAGIC_NUMBERS.values())
        self._make_agent()
        timeline = sorted(set().union(*[set(df.index) for df in self.data.values()]))
        timeline = [t for t in timeline if (self.args.date_from is None or t >= self.args.date_from)
                    and (self.args.date_to is None or t <= self.args.date_to)]
        pending: Dict[str, dict] = {}
        n = len(timeline)
        try:
            for ti, t in enumerate(timeline):
                bars = {s: df.iloc[self._pos_index[s][t]] for s, df in self.data.items() if t in self._pos_index[s]}
                self.broker.sim_time = t
                spreads = {}
                for s, row in bars.items():
                    spreads[s] = float(row["spread_pips"])
                    self.broker.set_price(s, row["open"], spreads[s])
                    self.broker.apply_broker_stops(s, gap=True)
                for s, sig in pending.items():
                    if s in bars:
                        self._try_open(sig)
                pending = {}
                paths = {}
                for s, row in bars.items():
                    signed = sum(p["volume"] * (1 if p["type"] == "BUY" else -1) for p in self.broker.positions.values() if p["symbol"] == s)
                    net_long = None if signed == 0 else signed > 0
                    paths[s] = {"pts": bar_path(row["open"], row["high"], row["low"], row["close"], self.args.path_order, net_long),
                                "spread": spreads[s]}
                if self.broker.positions:
                    await self.agent.run_cycle()
                for k in (1, 2, 3):
                    if self.broker.positions:
                        await self._advance(paths, k, t)
                    else:
                        self._set_prices(paths, k, 1.0, t)
                self.broker.sim_time = t + timedelta(hours=TF_HOURS)
                self._rec_equity()
                for s, row in bars.items():
                    i = self._pos_index[s][t]
                    if i + 1 < self.args.warmup:
                        continue
                    sig = self.signal_fn(s, i)
                    if sig:
                        self.signals_seen += 1
                        pending[s] = sig
                if progress and ti % 250 == 0:
                    print(f"  ... {ti}/{n}  {t}  equity {self.broker.get_account()['equity']:.2f}  closed {len(self.broker.closed)}", flush=True)
        finally:
            self._sess_patch.stop()
        for pos in list(self.broker.positions.values()):
            self.broker.positions.pop(pos["ticket"])
            self.broker._record_close(pos, self.broker._price_for(pos), "End_Of_Data")
        return self._report(timeline)

    def _report(self, timeline) -> dict:
        trades = self.broker.closed
        rep = {
            "period": [str(timeline[0]), str(timeline[-1])] if timeline else [],
            "symbols": sorted(self.data), "initial_balance": self.args.balance,
            "signals_passing_pipeline": self.signals_seen, "entry_rejections": self.rejects,
            "strategy_overrides": self.args.overrides, "legacy_basket": bool(self.args.legacy_basket),
            "signal_mode": getattr(self.args, "signal_mode", "real"), "seed": getattr(self.args, "seed", 1),
            "regimes": getattr(self.args, "regimes", None), "path_order": getattr(self.args, "path_order", "ohlc"),
            "assumptions": ASSUMPTIONS,
        }
        rep["all"] = compute_metrics(trades, self.args.balance, self.equity)
        if self.args.oos_fraction and timeline:
            cut = timeline[int(len(timeline) * (1 - self.args.oos_fraction))]
            rep["oos_cut"] = str(cut)
            rep["in_sample"] = compute_metrics([t for t in trades if t["open_time"] < cut.isoformat()], self.args.balance)
            rep["out_of_sample"] = compute_metrics([t for t in trades if t["open_time"] >= cut.isoformat()], self.args.balance)
        return rep


# ══════════════════════════════════════════════════════════════════════
# run: CSV -> إعادة التشغيل
# ══════════════════════════════════════════════════════════════════════
def load_data(data_dir: str, symbols: Optional[List[str]], default_spread: float):
    import pandas as pd
    from config import SYMBOLS
    names = symbols or list(SYMBOLS)
    data = {}
    for sym in names:
        path = os.path.join(data_dir, f"{sym}_H1.csv")
        if not os.path.exists(path):
            print(f"[skip] {sym}: {path} not found")
            continue
        df = pd.read_csv(path, parse_dates=["time"]).set_index("time").sort_index()
        df = df[~df.index.duplicated(keep="first")]
        if "spread_pips" not in df.columns:
            df["spread_pips"] = default_spread
        df["spread_pips"] = df["spread_pips"].fillna(default_spread).clip(lower=0.0)
        data[sym] = df[["open", "high", "low", "close", "volume", "spread_pips"]]
    return data


def _parse_overrides(items: List[str]) -> dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        try:
            out[k.strip()] = ast.literal_eval(v.strip())
        except Exception:
            out[k.strip()] = v.strip()
    return out


def format_summary(rep: dict) -> str:
    def line(name, s):
        if not s or s.get("n", 0) == 0:
            return f"  {name:<18} no trades"
        lo, hi = s["win_rate_ci95"]
        return (f"  {name:<18} n={s['n']:<4} win={s['win_rate']*100:5.1f}% (95%CI {lo*100:.0f}-{hi*100:.0f}) "
                f"payoff={s['payoff_ratio']} breakeven_win={'n/a' if s['breakeven_win_rate'] is None else format(s['breakeven_win_rate']*100, '.1f') + '%'} "
                f"expectancy={s['expectancy']:+.3f}$ PF={s['profit_factor']} net={s['net']:+.2f}$ t={s['t_stat']}")
    a = rep["all"]
    out = [f"Period: {rep['period']}  symbols: {', '.join(rep['symbols'])}  legacy_basket={rep['legacy_basket']}  "
           f"signal_mode={rep.get('signal_mode')} seed={rep.get('seed')} regimes={rep.get('regimes')} path_order={rep.get('path_order')}",
           f"Signals passing pipeline: {rep['signals_passing_pipeline']}   entry rejections: {rep['entry_rejections']}",
           line("BASKETS", a["baskets"]), line("POSITIONS", a["positions"]),
           f"  return={a.get('return_pct')}%  maxDD(equity)={a.get('max_equity_drawdown_pct')}%  final_equity={a.get('final_equity')}"
           f"  open_at_end={a['open_at_end_count']} ({a['open_at_end_floating_net']:+.2f}$, excluded from stats)"]
    for title in ("by_symbol", "by_exit_reason", "by_regime"):
        out.append(f" {title}:")
        out += [line(k, v) for k, v in a[title].items()]
    for tag in ("in_sample", "out_of_sample"):
        if tag in rep:
            out.append(f" {tag} (cut {rep['oos_cut']}):")
            out.append(line("BASKETS", rep[tag]["baskets"]))
    n = a["baskets"].get("n", 0)
    if n < 100:
        out.append(f" NOTE: only {n} baskets — statistically inconclusive (need >=100, ideally several hundred).")
    return "\n".join(out)


def cmd_run(args) -> int:
    from config import STRATEGY
    args.overrides = _parse_overrides(args.set)
    args.regimes = [x.strip().upper() for x in args.regimes.split(",") if x.strip()] or None
    STRATEGY.update(args.overrides)
    args.date_from = datetime.fromisoformat(args.date_from) if args.date_from else None
    args.date_to = datetime.fromisoformat(args.date_to) if args.date_to else None
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    data = load_data(args.data_dir, symbols, args.default_spread_pips)
    if not data:
        print(f"No CSV data in {args.data_dir}. Run the export command first.", file=sys.stderr)
        return 2
    rp = Replay(data, args)
    rep = asyncio.run(rp.run())
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, default=str)
    if rp.broker.closed:
        with open(os.path.join(args.out, "trades.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rp.broker.closed[0].keys()))
            w.writeheader()
            w.writerows(rp.broker.closed)
    print(format_summary(rep))
    print(f"\nSaved: {os.path.join(args.out, 'report.json')} (+ trades.csv)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Replay the live system logic on MT5 history (no live orders).")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="MT5 -> CSV (read-only)")
    e.add_argument("--symbols", default="")
    e.add_argument("--days", type=int, default=365)
    e.add_argument("--data-dir", default=os.path.join(ROOT, "data", "replay"))
    r = sub.add_parser("run", help="CSV -> replay -> report")
    r.add_argument("--symbols", default="")
    r.add_argument("--data-dir", default=os.path.join(ROOT, "data", "replay"))
    r.add_argument("--out", default=os.path.join(ROOT, "backtest", "out"))
    r.add_argument("--balance", type=float, default=1000.0)
    r.add_argument("--commission-per-lot", type=float, default=0.0, help="USD round turn per 1.0 lot")
    r.add_argument("--default-spread-pips", type=float, default=1.0)
    r.add_argument("--from", dest="date_from", default=None)
    r.add_argument("--to", dest="date_to", default=None)
    r.add_argument("--oos-fraction", type=float, default=0.0, help="last fraction of the period reported separately")
    r.add_argument("--warmup", type=int, default=200, help="bars before the first signal")
    r.add_argument("--legacy-basket", action="store_true", help="ignore ATR basket: legacy $2 target / $20 stop")
    r.add_argument("--set", action="append", default=[], help="override STRATEGY key, e.g. --set basket_rr=1.5")
    r.add_argument("--signal-mode", choices=["real", "random", "invert"], default="real",
                   help="control experiments: random = same timing/ATR/regime but random direction; invert = flipped direction")
    r.add_argument("--seed", type=int, default=1, help="seed for --signal-mode random")
    r.add_argument("--regimes", default="", help="comma list of FSM regimes allowed to enter, e.g. STRONG_TREND")
    r.add_argument("--path-order", choices=["ohlc", "adverse", "favorable"], default="ohlc",
                   help="intrabar path: ohlc heuristic, or adverse/favorable-first relative to open positions")
    r.add_argument("--cache-dir", default=os.path.join(ROOT, "backtest", "out_cache"),
                   help="entry-signal cache (pure function of data+config); 'none' disables")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return cmd_export(args) if args.cmd == "export" else cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
