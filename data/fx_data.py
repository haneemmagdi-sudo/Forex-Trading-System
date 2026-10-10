"""
data/fx_data.py — تقرير زوج فوركس لوكلاء التحليل.

المصدر: Yahoo Finance (نفس المزوّد الذي يستخدمه MT5Connector كبيانات حقيقية
عند تعذّر MT5). لا يُنشئ هذا الملف اتصال MT5 خاصاً به.

تقرير صادق: كل رقم محسوب من الشموع الفعلية، والمفاتيح التي لا نحسبها
(مثل currency_strength) تُحذف بدل تلفيق قيم صفرية مضلِّلة.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from schemas.forex import get_pip_size

logger = logging.getLogger("data.fx_data")

_BARS = 200


def _yf_symbol(pair: str) -> str:
    """EURUSD / EUR/USD / EURUSD=X -> EURUSD=X"""
    clean = (pair or "").upper().replace("/", "").replace("-", "").replace("=X", "").strip()
    return f"{clean}=X" if len(clean) == 6 else (pair or "").upper()


def _rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    last_loss = float(loss.iloc[-1])
    if last_loss == 0:
        return 100.0
    rs = float(gain.iloc[-1]) / last_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(df) < period + 1:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def build_fx_report(pair: str) -> Optional[dict]:
    """
    تقرير زوج فوركس. يُرجع None عند غياب البيانات (فيتخطاه الوكيل بتحذير).
    """
    if not pair:
        return None

    try:
        import yfinance as yf
    except Exception as exc:
        logger.warning("[fx_data] yfinance unavailable: %s", exc)
        return None

    symbol = _yf_symbol(pair)
    try:
        df = yf.Ticker(symbol).history(period="3mo", interval="1h", auto_adjust=False)
    except Exception as exc:
        logger.warning("[fx_data] history fetch failed for %s: %s", symbol, exc)
        return None

    if df is None or df.empty or len(df) < 60:
        logger.warning("[fx_data] insufficient history for %s", symbol)
        return None

    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    closes = df["close"]
    pip = get_pip_size(pair)
    rate = float(closes.iloc[-1])

    daily_change_pips = round((rate - float(closes.iloc[-24])) / pip, 1) if len(closes) >= 24 else None
    weekly_trend = None
    if len(closes) >= 120:
        weekly_trend = "UP" if rate > float(closes.iloc[-120]) else "DOWN"

    rsi = _rsi(closes)
    atr = _atr(df)
    atr_pips = round(atr / pip, 1) if atr else None

    # درجة ثقة شفافة مشتقة من المؤشرات فقط (ليست نموذجاً مُتعلَّماً) — موثّقة صراحة
    score = 0.3
    if weekly_trend == "UP":
        score += 0.2
    if rsi is not None and 45 <= rsi <= 65:
        score += 0.2
    if atr_pips is not None and atr_pips > 0:
        score += 0.1
    confidence_level = round(min(0.9, score), 2)

    return {
        "pair": pair,
        "symbol": symbol,
        "rate": rate,
        "daily_change_pips": daily_change_pips,
        "weekly_trend": weekly_trend,
        "spread_pips": None,          # لا نملك سبريد حقيقي من Yahoo — لا نلفّق رقماً
        "indicators": {
            "RSI_14": rsi,
            "ATR_14_pips": atr_pips,
        },
        "confidence_level": confidence_level,
        "confidence_source": "indicator_heuristic",
        "data_source": "yfinance",
    }
