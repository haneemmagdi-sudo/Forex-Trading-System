"""
backend/order_flow_calibration.py — معايرة طبقة Order Flow بالبيانات.

السؤال: عتبة طبقة التدفق (min_order_flow_confidence = 65) ترفض ~91% من الإشارات.
هل هذا الرفض يحمل معلومة (يفصل الرابح عن الخاسر)، أم أنه ضجيج؟

المنهج (يقاوم الإفراط في التوفيق):
  1. تشغيل الطبقة الحقيقية على كل صفقة تاريخية مربوطة بنتيجة معروفة.
  2. توزيع أسباب الرفض + قياس القدرة التميّيزية (نسبة الفوز ومتوسط الربح لكل شريحة).
  3. منحنى عتبات كامل: ماذا لو كانت العتبة س؟ (صافي ربح الصفقات التي كانت ستُقبل)
  4. اختيار العتبة على **نصف التدريب** ثم قياسها على **نصف الاختبار** (تقسيم زمني).

قراءة فقط: لا يكتب في قاعدة البيانات.

    python order_flow_calibration.py [--limit 1000]
"""

from __future__ import annotations

import argparse
import bisect
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                                    # noqa: E402
from models.database import SessionLocal                       # noqa: E402
from core.agent_council import ShadowCouncil                   # noqa: E402
from institutional.order_flow_agent import OrderFlowMicrostructureAgent  # noqa: E402

SQL = """
    SELECT s.symbol, s.direction, s.created_at,
           t.profit_usd
    FROM signals s
    JOIN trades t ON t.ticket = s.trade_ticket
    WHERE s.executed = 1 AND s.trade_ticket IS NOT NULL
      AND t.status = 'CLOSED' AND t.profit_usd IS NOT NULL
    ORDER BY s.created_at
    LIMIT :lim
"""

DEFAULT_THRESHOLD = 65.0


def _as_utc(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def slice_series(df, when, bars):
    stamps = list(df.index.view("int64") // 1_000_000_000)
    position = bisect.bisect_right(stamps, int(when.timestamp()))
    if position < bars:
        return None
    window = df.iloc[position - bars:position]
    return {
        "opens": window["open"].tolist(), "highs": window["high"].tolist(),
        "lows": window["low"].tolist(), "closes": window["close"].tolist(),
        "volumes": window["volume"].tolist(),
    }


def load_history(symbols):
    import yfinance as yf
    histories = {}
    for index, symbol in enumerate(sorted(symbols), start=1):
        try:
            df = yf.Ticker(f"{(symbol or '').upper()}=X").history(
                period="8mo", interval="1h", auto_adjust=False)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
        df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
        histories[symbol] = df
        print(f"  [{index}/{len(symbols)}] {symbol}: {len(df)} bars")
    return histories


def stats(rows):
    if not rows:
        return None
    pnl = [r["pnl"] for r in rows]
    wins = [p for p in pnl if p > 0]
    return {
        "n": len(rows),
        "win_rate": 100.0 * len(wins) / len(rows),
        "net": sum(pnl),
        "avg": sum(pnl) / len(rows),
    }


def line(label, s):
    if s is None:
        print(f"    {label:<26} —")
        return
    print(f"    {label:<26} n={s['n']:>4}  win={s['win_rate']:5.1f}%  "
          f"net={s['net']:+8.2f}$  avg={s['avg']:+.3f}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = [dict(r._mapping) for r in db.execute(text(SQL), {"lim": args.limit}).fetchall()]
    finally:
        db.close()
    if not rows:
        print("No linked closed trades — nothing to calibrate.")
        return 1

    print(f"Linked closed trades: {len(rows)}")
    histories = load_history({r["symbol"] for r in rows if r["symbol"]})

    agent = OrderFlowMicrostructureAgent()
    samples = []
    for row in rows:
        df = histories.get(row["symbol"])
        when = _as_utc(row["created_at"])
        if df is None or when is None:
            continue
        series = slice_series(df, when, 60)
        if series is None:
            continue
        series = ShadowCouncil.sanitize_series(series)
        action = row["direction"].value if hasattr(row["direction"], "value") else str(row["direction"])
        try:
            result = agent.validate_setup(
                symbol=row["symbol"], proposed_action=action,
                closes=series["closes"], opens=series["opens"],
                highs=series["highs"], lows=series["lows"], volumes=series["volumes"],
            )
        except Exception:
            continue
        samples.append({
            "when": when,
            "pnl": float(row["profit_usd"] or 0.0),
            "confidence": result.order_flow_confidence,
            "valid": result.is_valid_entry,
            "divergence": result.cvd_divergence,
            "absorption": result.absorption_detected.value,
            "sweep": result.sweep_direction,
            "action": action,
        })

    print(f"Evaluated: {len(samples)}\n")
    baseline = stats(samples)
    print("=== BASELINE (no veto at all) ===")
    line("all trades", baseline)

    print("\n=== rejection breakdown at the current threshold ===")
    rejected = [s for s in samples if not s["valid"]]
    print(f"    rejected: {len(rejected)}/{len(samples)} "
          f"({100.0*len(rejected)/len(samples):.1f}%)")
    reasons = defaultdict(int)
    for s in rejected:
        if s["action"] == "BUY" and s["sweep"] == "HIGH_SWEEP":
            reasons["trap: BUY into HIGH_SWEEP"] += 1
        elif s["action"] == "SELL" and s["sweep"] == "LOW_SWEEP":
            reasons["trap: SELL into LOW_SWEEP"] += 1
        else:
            reasons[f"confidence < {DEFAULT_THRESHOLD:.0f}"] += 1
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    {reason:<34} {count}")

    print("\n=== discriminative power: outcome by order-flow confidence bucket ===")
    buckets = [(0, 55), (55, 60), (60, 65), (65, 70), (70, 100)]
    for low, high in buckets:
        line(f"conf {low}-{high}", stats([s for s in samples if low <= s["confidence"] < high]))

    print("\n=== outcome by divergence / sweep / absorption ===")
    for key, values in (("divergence", {"CONVERGENT", "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NONE"}),
                        ("sweep", {"HIGH_SWEEP", "LOW_SWEEP", None}),
                        ("absorption", {"BULLISH_ABSORPTION", "BEARISH_ABSORPTION", "NONE"})):
        print(f"  by {key}:")
        for value in values:
            line(str(value), stats([s for s in samples if s[key] == value]))

    print("\n=== sweep x action (the trap rule only fires on one combination) ===")
    for sweep_value in ("LOW_SWEEP", "HIGH_SWEEP", None):
        for action in ("BUY", "SELL"):
            line(f"{sweep_value} + {action}",
                 stats([s for s in samples if s["sweep"] == sweep_value and s["action"] == action]))

    print("\n=== EXACT cohorts the current rules would veto ===")
    trap_sell = [s for s in samples if s["action"] == "SELL" and s["sweep"] == "LOW_SWEEP"]
    trap_buy = [s for s in samples if s["action"] == "BUY" and s["sweep"] == "HIGH_SWEEP"]
    below = [s for s in samples if s["confidence"] < DEFAULT_THRESHOLD
             and not (s["action"] == "SELL" and s["sweep"] == "LOW_SWEEP")
             and not (s["action"] == "BUY" and s["sweep"] == "HIGH_SWEEP")]
    line("trap: SELL into LOW_SWEEP", stats(trap_sell))
    line("trap: BUY into HIGH_SWEEP", stats(trap_buy))
    line("threshold: conf < 65", stats(below))
    vetoed_pnl = [s["pnl"] for s in samples if not s["valid"]]
    if vetoed_pnl:
        print(f"    ALL vetoed together: n={len(vetoed_pnl)} "
              f"net={sum(vetoed_pnl):+.2f}$  (what the veto actually removes)")

    print("\n=== threshold curve: if the veto were set at X ===")
    print("    (kept = trades that would pass; cost = net change vs no-veto baseline)")
    curve = []
    for threshold in range(50, 96, 5):
        kept = [s for s in samples if s["confidence"] >= threshold]
        s = stats(kept)
        if s is None:
            continue
        curve.append((threshold, s))
        print(f"    threshold>={threshold:<3} kept={s['n']:>4}  win={s['win_rate']:5.1f}%  "
              f"net={s['net']:+8.2f}$  vs baseline={s['net']-baseline['net']:+8.2f}$")

    print("\n=== out-of-sample check (time split 60% / 40%) ===")
    ordered = sorted(samples, key=lambda s: s["when"])
    cut = int(len(ordered) * 0.6)
    train, test = ordered[:cut], ordered[cut:]
    print(f"  train n={len(train)}  test n={len(test)}")
    base_train, base_test = stats(train), stats(test)
    line("train baseline", base_train)
    line("test  baseline", base_test)
    best = None
    for threshold in range(50, 96, 5):
        s_train = stats([s for s in train if s["confidence"] >= threshold])
        if s_train and (best is None or s_train["net"] > best[1]["net"]):
            best = (threshold, s_train)
    if best:
        threshold, s_train = best
        s_test = stats([s for s in test if s["confidence"] >= threshold])
        print(f"\n  best threshold on TRAIN = {threshold} "
              f"(net {s_train['net']:+.2f}$ vs baseline {base_train['net']:+.2f}$)")
        print(f"  same threshold on TEST:")
        line(f"  kept @ >={threshold}", s_test)
        print(f"    holdout gain vs test baseline: "
              f"{(s_test['net'] - base_test['net']) if s_test else 0:+.2f}$")

    print("\n  READING: if no bucket separates winners from losers, and the best")
    print("  threshold sits at the bottom of the ladder, the stage carries no")
    print("  information and must not hold veto power as currently defined.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
