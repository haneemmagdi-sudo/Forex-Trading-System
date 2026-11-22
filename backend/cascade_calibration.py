"""
backend/cascade_calibration.py — معايرة السلسلة المؤسسية كاملة على بيانات حقيقية.

يقيس كل مرحلة **على حدة** (لا النتيجة النهائية فقط):
  STAGE_1 النظام السوقي (HMM)  |  STAGE_2 التدفق (معاير مسبقاً)  |  STAGE_4 المناظرة (MAD)

لكل مرحلة: نسبة الرفض، وأداء المجموعة التي كان سيرفضها، والقدرة التميّيزية،
ثم مسح عتبات ثنائي الأبعاد للمناظرة (الهامش × الثقة) مع تقسيم زمني
تدريب/اختبار لتفادي الإفراط في التوفيق.

قراءة فقط.    python cascade_calibration.py [--limit 500]
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

from sqlalchemy import text                                       # noqa: E402
from models.database import SessionLocal                          # noqa: E402
from core.agent_council import ShadowCouncil                      # noqa: E402
from institutional.order_flow_agent import OrderFlowMicrostructureAgent  # noqa: E402
from institutional.market_regime_hmm import MarketRegimeAgent            # noqa: E402
from institutional.multi_agent_debate import MultiAgentDebateEngine      # noqa: E402

SQL = """
    SELECT s.symbol, s.direction, s.created_at,
           s.ema_value, s.rsi_value, s.adx_value, s.atr_value,
           t.profit_usd
    FROM signals s
    JOIN trades t ON t.ticket = s.trade_ticket
    WHERE s.executed = 1 AND s.trade_ticket IS NOT NULL
      AND t.status = 'CLOSED' AND t.profit_usd IS NOT NULL
    ORDER BY s.created_at
    LIMIT :lim
"""


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
    w = df.iloc[position - bars:position]
    return {"opens": w["open"].tolist(), "highs": w["high"].tolist(),
            "lows": w["low"].tolist(), "closes": w["close"].tolist(),
            "volumes": w["volume"].tolist()}


def load_history(symbols):
    import yfinance as yf
    out = {}
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
        out[symbol] = df
        print(f"  [{index}/{len(symbols)}] {symbol}: {len(df)} bars")
    return out


def stats(rows):
    if not rows:
        return None
    pnl = [r["pnl"] for r in rows]
    wins = [p for p in pnl if p > 0]
    return {"n": len(rows), "win": 100.0 * len(wins) / len(rows),
            "net": sum(pnl), "avg": sum(pnl) / len(rows)}


def line(label, s):
    if s is None:
        print(f"    {label:<34} —")
        return
    print(f"    {label:<34} n={s['n']:>4}  win={s['win']:5.1f}%  "
          f"net={s['net']:+8.2f}$  avg={s['avg']:+.3f}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = [dict(r._mapping) for r in db.execute(text(SQL), {"lim": args.limit}).fetchall()]
    finally:
        db.close()
    if not rows:
        print("No linked closed trades.")
        return 1

    print(f"Linked closed trades: {len(rows)}")
    histories = load_history({r["symbol"] for r in rows if r["symbol"]})

    of_agent = OrderFlowMicrostructureAgent()          # معاير: لا فيتو
    regime_agent = MarketRegimeAgent()
    debate = MultiAgentDebateEngine()                   # العتبات الحالية 75/20

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
        atr = float(row["atr_value"] or 0.0015)
        ema = float(row["ema_value"] or series["closes"][-1])
        rsi = float(row["rsi_value"] or 50.0)

        try:
            regime = regime_agent.classify(
                symbol=row["symbol"], closes=series["closes"], highs=series["highs"],
                lows=series["lows"], atr_current=atr, atr_baseline=0.0015)
            regime_vetoed, _ = regime_agent.evaluate_macro_veto(row["symbol"], action, regime)

            of_result = of_agent.validate_setup(
                symbol=row["symbol"], proposed_action=action,
                closes=series["closes"], opens=series["opens"], highs=series["highs"],
                lows=series["lows"], volumes=series["volumes"])

            debate_result = debate.conduct_debate(row["symbol"], {
                "close": series["closes"][-1], "ema": ema, "rsi": rsi, "atr": atr,
                "regime": regime.state.value,
                "absorption_detected": of_result.absorption_detected.value,
                "sweep_direction": of_result.sweep_direction,
                "spread": 10.0,
            })
        except Exception:
            continue

        samples.append({
            "when": when, "pnl": float(row["profit_usd"] or 0.0), "action": action,
            "regime_state": regime.state.value, "regime_allowed": regime.allowed_directions,
            "regime_vetoed": bool(regime_vetoed),
            "of_confidence": of_result.order_flow_confidence,
            "bull": debate_result.bullish_argument.conviction_score,
            "bear": debate_result.bearish_argument.conviction_score,
            "margin": debate_result.margin_of_dominance,
            "debate_permitted": debate_result.execution_permitted,
            "debate_verdict": debate_result.verdict.value,
        })

    print(f"Evaluated: {len(samples)}\n")
    baseline = stats(samples)
    print("=== BASELINE (no gates at all) ===")
    line("all trades", baseline)

    print("\n=== STAGE_1: market regime (HMM) ===")
    vetoed = [s for s in samples if s["regime_vetoed"]]
    print(f"    would veto: {len(vetoed)}/{len(samples)}")
    line("regime-vetoed cohort", stats(vetoed))
    by_state = defaultdict(list)
    for s in samples:
        by_state[s["regime_state"]].append(s)
    for state, items in sorted(by_state.items(), key=lambda kv: -len(kv[1])):
        line(f"state {state}", stats(items))

    print("\n=== STAGE_4: debate verdict at the CURRENT thresholds (margin>=20, conf>=75) ===")
    rejected = [s for s in samples if not s["debate_permitted"]]
    print(f"    would reject: {len(rejected)}/{len(samples)} "
          f"({100.0*len(rejected)/len(samples):.1f}%)")
    line("debate-rejected cohort", stats(rejected))
    line("debate-permitted cohort", stats([s for s in samples if s["debate_permitted"]]))

    print("\n  conviction scale actually produced (why conf>=75 almost never fires):")
    for label, key in (("bull conviction", "bull"), ("bear conviction", "bear")):
        values = sorted(s[key] for s in samples)
        if values:
            print(f"    {label:<18} min={values[0]:5.1f}  median={values[len(values)//2]:5.1f}  "
                  f"p90={values[int(len(values)*0.9)]:5.1f}  max={values[-1]:5.1f}")
    print(f"    {'|margin|':<18} max={max(abs(s['margin']) for s in samples):5.1f}")

    print("\n  discriminative power of the margin (the part that could carry information):")
    for low, high in ((0, 5), (5, 15), (15, 25), (25, 100)):
        line(f"|margin| {low}-{high}",
             stats([s for s in samples if low <= abs(s["margin"]) < high]))

    print("\n=== debate gate sweep (train 60% / test 40%, time-ordered) ===")
    ordered = sorted(samples, key=lambda s: s["when"])
    cut = int(len(ordered) * 0.6)
    train, test = ordered[:cut], ordered[cut:]
    base_train, base_test = stats(train), stats(test)
    line("train baseline", base_train)
    line("test  baseline", base_test)

    best = None
    for margin in (0, 5, 10, 15, 20, 25, 30):
        for conf in (40, 45, 50, 55, 60, 65, 70, 75):
            kept_train = [s for s in train
                          if abs(s["margin"]) >= margin
                          and max(s["bull"], s["bear"]) >= conf
                          and (s["bull"] >= s["bear"]) == (s["action"] == "BUY")]
            s_tr = stats(kept_train)
            if s_tr is None or s_tr["n"] < 20:
                continue
            if best is None or s_tr["net"] > best[2]["net"]:
                best = (margin, conf, s_tr)
    if best:
        margin, conf, s_tr = best
        kept_test = [s for s in test
                     if abs(s["margin"]) >= margin
                     and max(s["bull"], s["bear"]) >= conf
                     and (s["bull"] >= s["bear"]) == (s["action"] == "BUY")]
        s_te = stats(kept_test)
        print(f"\n  best on TRAIN: margin>={margin}, conf>={conf} -> "
              f"n={s_tr['n']} net={s_tr['net']:+.2f}$ (baseline {base_train['net']:+.2f}$)")
        line(f"  same rule on TEST", s_te)
        gain = (s_te["net"] - base_test["net"]) if s_te else 0.0
        print(f"    holdout gain vs test baseline: {gain:+.2f}$  "
              f"({'VALUABLE' if gain > 0 else 'DESTROYS VALUE'})")
    else:
        print("  no threshold pair kept enough trades to evaluate")

    print("\n=== note: the bridge ignores WHICH side the debate approved ===")
    mismatch = [s for s in samples if (s["bull"] >= s["bear"]) != (s["action"] == "BUY")]
    print(f"    debate's dominant side contradicts the executed direction in "
          f"{len(mismatch)}/{len(samples)} cases — the permit flag alone is checked.")
    line("contradicted-direction cohort", stats(mismatch))

    print("\n  READING: a gate is only worth keeping if the cohort it would reject")
    print("  performs clearly WORSE (on the holdout) than the cohort it keeps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
