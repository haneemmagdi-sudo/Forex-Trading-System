"""
data/equity_data.py — تقرير سهم لوكلاء التحليل + حالة السوق الأمريكي.

المصدر: Yahoo Finance. لا اتصال MT5 (الأسهم ليست على MT5 هنا).
كل رقم محسوب من الشموع الفعلية؛ وعند غياب البيانات نُرجع None/[] بلا تلفيق.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("data.equity_data")

# ساعات السوق الأمريكي بالتوقيت العالمي (09:30–16:00 بتوقيت نيويورك).
# ملاحظة: لا تُراعى هنا فروق التوقيت الصيفي/العطلات الرسمية — تُرجع تقديراً.
_US_OPEN_UTC = time(13, 30)
_US_CLOSE_UTC = time(20, 0)


def is_us_market_open(now: Optional[datetime] = None) -> bool:
    """هل السوق الأمريكي مفتوح الآن (أيام العمل وسط تقدير ساعات التداول)؟"""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    if current.weekday() >= 5:          # السبت والأحد
        return False
    return _US_OPEN_UTC <= current.time() <= _US_CLOSE_UTC


def _rsi(closes, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    last_loss = float(loss.iloc[-1])
    if last_loss == 0:
        return 100.0
    return round(100.0 - (100.0 / (1.0 + float(gain.iloc[-1]) / last_loss)), 2)


def _atr(high, low, close, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    import pandas as pd
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def build_equity_report(symbol: str) -> Optional[Dict[str, Any]]:
    """تقرير سهم: سعر، مؤشرات، نظام سوقي، وتوصية مشتقة شفافة. None عند غياب البيانات."""
    if not symbol:
        return None
    try:
        import yfinance as yf
    except Exception as exc:
        logger.warning("[equity_data] yfinance unavailable: %s", exc)
        return None

    try:
        df = yf.Ticker(symbol).history(period="6mo", interval="1d", auto_adjust=False)
    except Exception as exc:
        logger.warning("[equity_data] history fetch failed for %s: %s", symbol, exc)
        return None

    if df is None or df.empty or len(df) < 30:
        logger.warning("[equity_data] insufficient history for %s", symbol)
        return None

    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    close = df["close"]
    price = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else price
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else sma20
    rsi = _rsi(close)
    atr = _atr(df["high"], df["low"], close)

    if price > sma20 > sma50:
        overall_signal, market_regime = "BULLISH", "UPTREND"
    elif price < sma20 < sma50:
        overall_signal, market_regime = "BEARISH", "DOWNTREND"
    else:
        overall_signal, market_regime = "NEUTRAL", "RANGE"

    if overall_signal == "BULLISH" and (rsi or 50) < 70:
        recommended_action = "BUY"
    elif overall_signal == "BEARISH" and (rsi or 50) > 30:
        recommended_action = "SELL"
    else:
        recommended_action = "HOLD"

    return {
        "symbol": symbol,
        "price_action": {
            "current_price": price,
            "overall_signal": overall_signal,
            "sma_20": round(sma20, 4),
            "sma_50": round(sma50, 4),
        },
        "indicators": {
            "RSI_14": rsi,
            "ATR_14": round(atr, 4) if atr else None,
        },
        "market_regime": market_regime,
        "recommended_action": recommended_action,
        "confidence_level": 0.5,      # محايدة عمداً: لا نموذج مُتعلَّم للأسهم بعد
        "analyst_commentary": (
            f"{symbol}: {market_regime} | RSI={rsi} | السعر مقابل SMA20/50: "
            f"{'أعلى' if price > sma20 else 'أدنى'}"
        ),
        "data_source": "yfinance",
    }
