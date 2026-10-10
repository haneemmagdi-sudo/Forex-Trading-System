"""
backend/council_backfill.py — توليد دليل رقمي بأثر رجعي لمجلس الوكلاء.

المشكلة: بوابة تمكين الفلترة تشترط دليلاً من صفقات *ظل*، ولا يوجد أي منها
لأن المجلس أُضيف للتوّ. هذا السكربت يُنتج الدليل من التاريخ بدل الانتظار:
يُعيد تشغيل الجسر المؤسسي (HMM + Order Flow + MAD Debate) على الإشارات
التاريخية المربوطة بصفقات مغلقة نتيجتها معروفة، ويقيس أثر الفيتو المضاد للواقع.

ما يقيسه فعلاً: طبقات الجسر (تتطلب شموعاً حقيقية نجلبها من Yahoo Finance).
ما لا يقيسه: محرّك الإجماع (يحتاج مشاعر أخبار تاريخية غير مخزَّنة) — مُعلَن أدناه.

قراءة فقط: لا يكتب في قاعدة البيانات إطلاقاً.

    python council_backfill.py [--limit 1000] [--bars 60]
"""

from __future__ import annotations

import argparse
import bisect
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

# مسار قاعدة البيانات في هذا المشروع نسبي (sqlite:///./trading.db) فيجب أن
# يكون مجلد العمل هو backend/ — وإلا يُنشئ SQLAlchemy قاعدة بيانات فارغة
# في المجلد الخاطئ.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                                   # noqa: E402
from models.database import SessionLocal                      # noqa: E402
from core.execution_bridge import InstitutionalExecutionBridge  # noqa: E402
from core.agent_council import ShadowCouncil                    # noqa: E402


SQL = """
    SELECT s.symbol, s.direction, s.created_at, s.confidence,
           s.ema_value, s.rsi_value, s.macd_value, s.adx_value, s.atr_value,
           t.ticket, t.profit_usd, t.fsm_regime
    FROM signals s
    JOIN trades t ON t.ticket = s.trade_ticket
    WHERE s.executed = 1
      AND s.trade_ticket IS NOT NULL
      AND t.status = 'CLOSED'
      AND t.profit_usd IS NOT NULL
    ORDER BY s.created_at
    LIMIT :lim
"""


def _yf_symbol(symbol: str) -> str:
    clean = (symbol or "").upper().replace("/", "").replace("=X", "").strip()
    return f"{clean}=X"


def load_history(symbols):
    """يجلب شموع H1 لكل رمز مرة واحدة (المصدر: Yahoo Finance)."""
    import yfinance as yf

    histories = {}
    for index, symbol in enumerate(sorted(symbols), start=1):
        try:
            df = yf.Ticker(_yf_symbol(symbol)).history(period="8mo", interval="1h", auto_adjust=False)
        except Exception as exc:
            print(f"  [{index}/{len(symbols)}] {symbol}: fetch failed ({exc})")
            continue
        if df is None or df.empty:
            print(f"  [{index}/{len(symbols)}] {symbol}: no data")
            continue
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        histories[symbol] = df
        print(f"  [{index}/{len(symbols)}] {symbol}: {len(df)} bars")
    return histories


def slice_series(df, when, bars):
    """شموع ``bars`` المنتهية عند وقت الإشارة (أو None إن لم تكفِ)."""
    stamps = df.index.view("int64") // 1_000_000_000
    position = bisect.bisect_right(list(stamps), int(when.timestamp()))
    if position < bars:
        return None
    window = df.iloc[position - bars:position]
    if len(window) < bars:
        return None
    return {
        "opens":   window["open"].tolist(),
        "highs":   window["high"].tolist(),
        "lows":    window["low"].tolist(),
        "closes":  window["close"].tolist(),
        "volumes": window["volume"].tolist(),
    }


def _as_utc(value):
    """الاستعلام الخام يُرجع الطوابع الزمنية كنصوص — نحوّلها إلى UTC بوعي بالمنطقة."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text_value = str(value).replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text_value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text_value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill council evidence from real trade history")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--bars", type=int, default=60)
    parser.add_argument("--show-reasons", type=int, default=0,
                        help="طباعة أول N من أسباب رفض الجسر (للتشخيص)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = [dict(r._mapping) for r in db.execute(text(SQL), {"lim": args.limit}).fetchall()]
    finally:
        db.close()

    if not rows:
        print("No linked closed trades with a known outcome — nothing to backfill yet.")
        return 1

    print(f"Linked closed trades with known outcome: {len(rows)}")
    symbols = {r["symbol"] for r in rows if r["symbol"]}
    print(f"Fetching H1 history for {len(symbols)} symbols ...")
    histories = load_history(symbols)

    bridge = InstitutionalExecutionBridge()

    approved, vetoed = [], []
    stages = defaultdict(int)
    skipped = 0

    for row in rows:
        df = histories.get(row["symbol"])
        when = _as_utc(row["created_at"])
        if df is None or when is None:
            skipped += 1
            continue

        series = slice_series(df, when, args.bars)
        if series is None:
            skipped += 1
            continue

        try:
            receipt = bridge.process_entry_candidate(
                symbol=row["symbol"],
                proposed_action=row["direction"].value if hasattr(row["direction"], "value") else str(row["direction"]),
                price_series=ShadowCouncil.sanitize_series(series),
                technical_indicators={
                    "ema":  row["ema_value"]  or 0.0,
                    "rsi":  row["rsi_value"]  or 50.0,
                    "macd": row["macd_value"] or 0.0,
                    "adx":  row["adx_value"]  or 0.0,
                    "atr":  row["atr_value"]  or 0.0015,
                },
            )
        except Exception as exc:
            stages[f"ERROR:{type(exc).__name__}"] += 1
            skipped += 1
            continue

        entry = {
            "symbol": row["symbol"],
            "pnl": float(row["profit_usd"] or 0.0),
            "regime": row["fsm_regime"].value if hasattr(row["fsm_regime"], "value") else str(row["fsm_regime"]),
        }
        if receipt.approved:
            approved.append(entry)
        else:
            entry["stage"] = receipt.rejection_stage
            entry["reason"] = receipt.rejection_reason
            entry["details"] = receipt.details
            vetoed.append(entry)
            stages[receipt.rejection_stage or "UNKNOWN"] += 1

    def summarise(items, label):
        if not items:
            print(f"  {label}: none")
            return
        pnl = [i["pnl"] for i in items]
        wins = [p for p in pnl if p > 0]
        print(f"  {label}: n={len(items)} | win_rate={100.0*len(wins)/len(items):.1f}% | "
              f"net={sum(pnl):+.2f}$ | avg={sum(pnl)/len(items):+.3f}$")

    print("\n=== BRIDGE BACKFILL (real bars, read-only) ===")
    print(f"  evaluated={len(approved)+len(vetoed)}  skipped={skipped}")
    summarise(approved, "bridge would APPROVE")
    summarise(vetoed,  "bridge would VETO   ")

    if vetoed:
        veto_pnl = [i["pnl"] for i in vetoed]
        avoided = -sum(p for p in veto_pnl if p < 0)
        missed = sum(p for p in veto_pnl if p > 0)
        print(f"\n  veto counterfactual: avoided losses={avoided:+.2f}$ | "
              f"missed wins={missed:+.2f}$ | NET={avoided - missed:+.2f}$")
        print("  (NET > 0 means the veto would have added value over this sample)")

    print("\n  rejection stages:")
    for stage, count in sorted(stages.items(), key=lambda kv: -kv[1]):
        print(f"    {stage:<28} {count}")

    if args.show_reasons > 0:
        print(f"\n  first {args.show_reasons} rejection reasons (diagnosis):")
        seen = set()
        shown = 0
        for item in vetoed:
            reason = (item.get("reason") or "")[:150]
            key = (item.get("stage"), reason[:60])
            if key in seen:
                continue
            seen.add(key)
            shown += 1
            print(f"    [{item.get('stage')}] pnl={item['pnl']:+.2f}$ :: {reason}")
            if shown >= args.show_reasons:
                break

    print("\n  NOT measured here: the consensus engine (needs historical news sentiment,")
    print("  which is not stored per signal). Only the bridge layers are backfilled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
