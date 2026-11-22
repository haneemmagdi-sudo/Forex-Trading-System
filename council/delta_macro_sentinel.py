"""
agents/delta_macro_sentinel.py
==============================
Agent Delta: Macro & News Calendar Sentinel

Mandate: Protect the 4-Agent Council from entering positions during or
immediately before high-impact economic events (NFP, FOMC, CPI, ECB, etc.).

Architecture Law (.antigravityrules §2):
  - Computation is pure Python/NumPy — no LLM involvement.
  - Sentinel acts as a HARD GATE upstream of Agent Beta.
  - Returns a structured MacroRiskAssessment (Pydantic v2).

Data Source:
  Forex Factory JSON feed (free, cached 30 min, retried after 2 min on failure,
  last good copy served for up to 6 h). There is NO fallback schedule: with no
  trustworthy calendar the sentinel reports BLACKOUT (fail-closed) rather than
  guessing that no news is due.

Shadow Mode: always active — logs every embargo decision to DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger("MacroSentinel")


# ---------------------------------------------------------------------------
# Enums & Pydantic Contracts
# ---------------------------------------------------------------------------

class NewsRiskLevel(str, Enum):
    CLEAR       = "CLEAR"       # No event within 60 min → full trading allowed
    CAUTION     = "CAUTION"     # Medium-impact event 15-60 min → reduce risk 30%
    HIGH_IMPACT = "HIGH_IMPACT" # High-impact event 30-60 min → reduce risk 60%
    BLACKOUT    = "BLACKOUT"    # Any event < 15 min → hard veto, no trading


class MacroRiskAssessment(BaseModel):
    """
    Strict Pydantic output of MacroSentinelAgent.
    Consumed by MultiAgentOrchestrator before invoking Agent Beta.
    """
    timestamp_utc: str
    symbol: str
    risk_level: NewsRiskLevel
    news_embargo_active: bool = Field(
        ...,
        description="True if risk_level is HIGH_IMPACT or BLACKOUT.",
    )
    minutes_to_next_event: Optional[float] = Field(
        None,
        description="Minutes to closest upcoming high-impact event. None if no event found.",
    )
    next_event_name: Optional[str] = None
    next_event_impact: Optional[str] = None
    risk_percent_multiplier: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Multiplier applied to Omega's risk_percent output. "
            "1.0=full, 0.7=caution, 0.4=high-impact, 0.0=blackout."
        ),
    )
    data_source: str


# ---------------------------------------------------------------------------
# Currency → Affected pairs mapping
# ---------------------------------------------------------------------------

_CURRENCY_TO_PAIRS: Dict[str, List[str]] = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "XAUUSD", "XAGUSD"],
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD"],
    "GBP": ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY"],
    "AUD": ["AUDUSD", "EURAUD", "GBPAUD", "AUDJPY", "AUDCAD", "AUDNZD"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "CADJPY", "AUDCAD", "NZDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF"],
    "NZD": ["NZDUSD", "EURNZD", "GBPNZD", "NZDJPY", "AUDNZD", "NZDCAD"],
    "XAU": ["XAUUSD"],
    "XAG": ["XAGUSD"],
}

_HIGH_IMPACT_KEYWORDS: List[str] = [
    "Non-Farm Payrolls", "NFP",
    "FOMC", "Federal Funds Rate", "Fed Rate",
    "CPI", "Consumer Price Index",
    "ECB", "European Central Bank",
    "BoE", "Bank of England Rate",
    "BoJ", "Bank of Japan Rate",
    "BoC", "Bank of Canada Rate",
    "RBA", "Reserve Bank of Australia",
    "GDP", "Gross Domestic Product",
    "PPI", "Producer Price Index",
    "Retail Sales",
    "ISM Manufacturing", "ISM Services",
    "ADP Employment",
    "Unemployment Rate",
    "PCE", "Personal Consumption",
    "Initial Jobless Claims",
    "Flash PMI", "Manufacturing PMI", "Services PMI",
]

_MEDIUM_IMPACT_KEYWORDS: List[str] = [
    "PMI", "Building Permits", "Housing Starts",
    "Trade Balance", "Current Account",
    "Industrial Production", "Factory Orders",
    "Consumer Confidence", "Consumer Sentiment",
    "JOLTS", "Job Openings",
    "Durable Goods",
]


def _classify_event_impact(event_name: str) -> str:
    """Classifies a calendar event as High | Medium | Low impact."""
    name_upper = event_name.upper()
    for kw in _HIGH_IMPACT_KEYWORDS:
        if kw.upper() in name_upper:
            return "High"
    for kw in _MEDIUM_IMPACT_KEYWORDS:
        if kw.upper() in name_upper:
            return "Medium"
    return "Low"


def _symbol_to_currencies(symbol: str) -> List[str]:
    """Extracts the two base currencies from a forex symbol string."""
    symbol = symbol.upper().replace("/", "").replace("_", "")
    if len(symbol) == 6:
        return [symbol[:3], symbol[3:]]
    if symbol.startswith("XAU"):
        return ["XAU", "USD"]
    if symbol.startswith("XAG"):
        return ["XAG", "USD"]
    return ["USD"]


# ---------------------------------------------------------------------------
# Live Forex Factory feed parser (lightweight, zero external dependencies)
# ---------------------------------------------------------------------------

_FF_CALENDAR_URL = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
)
_FF_CACHE: Dict[str, Any] = {"data": None, "fetched_at": None, "next_attempt": None}
_FF_CACHE_TTL_MINUTES = 30      # خلاصة ناجحة تُعاد من الذاكرة هذه المدة
_FF_RETRY_AFTER_SECONDS = 120   # بعد فشل الجلب لا نعيد المحاولة قبل مرور هذه المدة
_FF_STALE_MAX_HOURS = 6         # عند فشل الجلب نخدم آخر خلاصة ناجحة ما دامت أحدث من هذا
_FF_LOCK = threading.Lock()     # رموز عدة تُقيَّم بخيوط متوازية: طلب واحد لا عاصفة طلبات


def _try_fetch_forex_factory(utc_now: datetime) -> Optional[List[Dict[str, Any]]]:
    """
    يجلب تقويم Forex Factory (JSON) ويعيد قائمة الأحداث، أو None إن لم تتوفر خلاصة موثوقة.

    - ناجحة: تُخزَّن 30 دقيقة.
    - فاشلة: لا إعادة محاولة قبل دقيقتين، وخلال ذلك (وبعد انتهاء الـ30 دقيقة) تُخدَم آخر
      خلاصة ناجحة إن كانت أحدث من 6 ساعات، وإلا None — والمُستدعي يعتبر None "لا تقويم" فيحظر.
    - MACRO_OFFLINE=1: None دون أي طلب شبكة.
    """
    if os.environ.get("MACRO_OFFLINE", "0") == "1":
        return None

    def _age(cache: Dict[str, Any]) -> Optional[float]:
        fetched = cache["fetched_at"]
        return None if fetched is None else (utc_now - fetched).total_seconds()

    def _stale_or_none(cache: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        age = _age(cache)
        if cache["data"] is not None and age is not None and age <= _FF_STALE_MAX_HOURS * 3600:
            return cache["data"]  # type: ignore[return-value]
        return None

    with _FF_LOCK:
        cache = _FF_CACHE
        age = _age(cache)
        if cache["data"] is not None and age is not None and age < _FF_CACHE_TTL_MINUTES * 60:
            return cache["data"]  # type: ignore[return-value]
        if cache["next_attempt"] is not None and utc_now < cache["next_attempt"]:
            return _stale_or_none(cache)

        try:
            req = urllib.request.Request(
                _FF_CALENDAR_URL,
                headers={"User-Agent": "QuantMAS/1.0 (institutional-trading-system)"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            cache.update(data=raw, fetched_at=utc_now, next_attempt=None)
            return raw
        except Exception as exc:
            cache["next_attempt"] = utc_now + timedelta(seconds=_FF_RETRY_AFTER_SECONDS)
            stale = _stale_or_none(cache)
            logger.warning(
                "Forex Factory calendar fetch failed: %s — %s.",
                exc, "serving last good feed" if stale is not None else "no usable calendar (fail-closed)",
            )
            return stale


def _us_eastern_offset_hours(naive_et: datetime) -> int:
    """
    إزاحة نيويورك عن UTC (بالساعات) لوقت محلي بلا منطقة زمنية: 5 شتاءً (EST)
    و4 صيفاً (EDT). قاعدة أمريكا: من الأحد الثاني من مارس 02:00 إلى الأحد
    الأول من نوفمبر 02:00. مكتوبة يدوياً لأن zoneinfo على ويندوز يحتاج حزمة
    tzdata غير مضمونة.
    """
    def _sunday(month: int, nth: int) -> datetime:
        first = datetime(naive_et.year, month, 1)
        day = 1 + (6 - first.weekday()) % 7 + 7 * (nth - 1)
        return datetime(naive_et.year, month, day, 2, 0)

    return 4 if _sunday(3, 2) <= naive_et < _sunday(11, 1) else 5


def _ff_event_utc(ev: Dict[str, Any]) -> Optional[datetime]:
    """
    يحوّل حدث Forex Factory إلى UTC، أو None إن تعذّر (لا نخمّن وقتاً).
    الصيغتان المدعومتان:
      1. date يحمل إزاحة ("2026-07-15T08:30:00-04:00"): يُحوَّل مباشرة، مرة واحدة.
      2. date بلا إزاحة + time ("8:30am"): توقيت نيويورك بإزاحة EST/EDT الصحيحة.
    """
    date_str = str(ev.get("date", "")).strip()
    time_str = str(ev.get("time", "")).strip()
    if not date_str:
        return None
    try:
        aware = datetime.fromisoformat(date_str)
    except ValueError:
        aware = None
    if aware is not None and aware.tzinfo is not None:
        return aware.astimezone(timezone.utc)
    if time_str.lower() in ("", "all day", "tentative"):
        return None
    try:
        naive_et = datetime.strptime(f"{date_str[:10]} {time_str}", "%Y-%m-%d %I:%M%p")
    except ValueError:
        return None
    return (naive_et + timedelta(hours=_us_eastern_offset_hours(naive_et))).replace(tzinfo=timezone.utc)


def _parse_ff_events(
    ff_data: List[Dict[str, Any]],
    utc_now: datetime,
    lookahead_minutes: int = 120,
) -> List[Dict[str, Any]]:
    """Parses FF JSON list into normalised upcoming-event dicts."""
    upcoming: List[Dict[str, Any]] = []
    for ev in ff_data:
        try:
            title = str(ev.get("title", ""))
            currency = str(ev.get("country", "USD")).upper()[:3]
            impact_raw = str(ev.get("impact", "Low")).strip()
            ev_utc = _ff_event_utc(ev)
            if ev_utc is None:
                continue

            delta_min = (ev_utc - utc_now).total_seconds() / 60.0
            # IMPROVEMENT_PLAN §0: نشمل الأحداث الماضية بـ 15 دقيقة (ما بعد الخبر)
            # delta_min سالبة = خبر مضى. نشمله إن كان في نافذة ما بعد الخبر
            if not (-15.0 <= delta_min <= lookahead_minutes):
                continue

            # Map FF impact label
            if impact_raw.lower() in ("high", "red"):
                mapped_impact = "High"
            elif impact_raw.lower() in ("medium", "orange"):
                mapped_impact = "Medium"
            else:
                mapped_impact = "Low"

            upcoming.append({
                "name": title,
                "currency": currency,
                "impact": mapped_impact,
                "minutes_away": round(delta_min, 1),
                "event_utc": ev_utc.isoformat(),
            })
        except Exception:
            continue

    return sorted(upcoming, key=lambda x: x["minutes_away"])


# ---------------------------------------------------------------------------
# MacroSentinelAgent — public class
# ---------------------------------------------------------------------------

class MacroSentinelAgent:
    """
    Agent Delta: Macro & Economic Calendar Sentinel.

    Checks incoming events and returns a MacroRiskAssessment that the
    orchestrator uses to:
      1. Veto the entire cycle (BLACKOUT / HIGH_IMPACT with embargo_active=True)
      2. Scale down risk_percent via risk_percent_multiplier
      3. Log the decision to the trade journal

    Embargo windows (before event):
      BLACKOUT    : event within 0-15 min  → hard veto
      HIGH_IMPACT : event within 15-30 min → 40% risk cap
      CAUTION     : event within 30-60 min → 70% risk cap
      CLEAR       : event > 60 min away    → normal operation

    IMPROVEMENT_PLAN §0: إضافة حظر ما بعد الخبر (post-event embargo):
      بعد الإفراج عن خبر High Impact نضيف حظراً لمدة 15 دقيقة
      لتجنب التداول خلال التقلب الحاد الذي يعقب الخبر مباشرة.
    """

    BLACKOUT_WINDOW_MIN:     float = 15.0
    HIGH_IMPACT_WINDOW_MIN:  float = 30.0
    CAUTION_WINDOW_MIN:      float = 60.0
    POST_EVENT_EMBARGO_MIN:  float = 15.0  # حظر ما بعد الخبر (جديد)

    def _assess_sync(
        self,
        symbol: str,
        utc_now: datetime,
    ) -> MacroRiskAssessment:
        symbol_currencies = _symbol_to_currencies(symbol)

        now_iso = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")

        ff_raw = _try_fetch_forex_factory(utc_now)
        # خلاصة بلا حدث واحد قابل للقراءة = تغيّر صيغة أو خطأ، لا "لا أخبار".
        if ff_raw is not None and not (
            isinstance(ff_raw, list)
            and any(_ff_event_utc(e) for e in ff_raw if isinstance(e, dict))
        ):
            logger.warning("Forex Factory feed has no parseable events (format change?) — treating as unavailable.")
            ff_raw = None
        if ff_raw is None:
            # لا تقويم موثوق: لا نخمّن (لا جدول احتياطي) — حظر كامل حتى يعود
            return MacroRiskAssessment(
                timestamp_utc=now_iso,
                symbol=symbol,
                risk_level=NewsRiskLevel.BLACKOUT,
                news_embargo_active=True,
                minutes_to_next_event=None,
                next_event_name=None,
                next_event_impact=None,
                risk_percent_multiplier=0.0,
                data_source="NO_CALENDAR_FEED",
            )

        # نجلب الأحداث للساعتين الماضيتين أيضاً للحظر ما بعد الخبر
        events_ahead = _parse_ff_events(ff_raw, utc_now, lookahead_minutes=int(self.CAUTION_WINDOW_MIN))
        data_source = "FOREX_FACTORY_LIVE"

        # Filter to events affecting this symbol's currencies
        relevant = [
            ev for ev in events_ahead
            if ev["currency"] in symbol_currencies
            and ev["impact"] in ("High", "Medium")
            # حدث مضى يهمّ فقط إن كان High (حظر ما بعد الخبر)؛ Medium مضى كان
            # يُصنَّف BLACKOUT ويحجب أي خبر قادم.
            and (ev["minutes_away"] >= 0 or ev["impact"] == "High")
        ]

        if not relevant:
            return MacroRiskAssessment(
                timestamp_utc=now_iso,
                symbol=symbol,
                risk_level=NewsRiskLevel.CLEAR,
                news_embargo_active=False,
                minutes_to_next_event=None,
                next_event_name=None,
                next_event_impact=None,
                risk_percent_multiplier=1.0,
                data_source=data_source,
            )

        closest = relevant[0]
        mins_away = closest["minutes_away"]
        impact = closest["impact"]

        # IMPROVEMENT_PLAN §0: حظر ما بعد الخبر — الحدث مضى (mins_away سالبة)
        # خبر High Impact مضى منذ أقل من 15 دقيقة → حظر مؤقت (سوق متقلب)
        if mins_away < 0 and impact == "High" and abs(mins_away) <= self.POST_EVENT_EMBARGO_MIN:
            return MacroRiskAssessment(
                timestamp_utc=now_iso,
                symbol=symbol,
                risk_level=NewsRiskLevel.BLACKOUT,
                news_embargo_active=True,
                minutes_to_next_event=mins_away,
                next_event_name=closest["name"],
                next_event_impact=impact,
                risk_percent_multiplier=0.0,
                data_source=data_source + "_POST_EVENT",
            )

        if mins_away <= self.BLACKOUT_WINDOW_MIN:
            risk_level = NewsRiskLevel.BLACKOUT
            multiplier = 0.0
            embargo = True
        elif impact == "High" and mins_away <= self.HIGH_IMPACT_WINDOW_MIN:
            risk_level = NewsRiskLevel.HIGH_IMPACT
            multiplier = 0.4
            embargo = True
        elif impact == "High" and mins_away <= self.CAUTION_WINDOW_MIN:
            risk_level = NewsRiskLevel.CAUTION
            multiplier = 0.7
            embargo = False
        elif impact == "Medium" and mins_away <= self.BLACKOUT_WINDOW_MIN:
            risk_level = NewsRiskLevel.HIGH_IMPACT
            multiplier = 0.4
            embargo = True
        else:
            risk_level = NewsRiskLevel.CAUTION
            multiplier = 0.7
            embargo = False

        return MacroRiskAssessment(
            timestamp_utc=now_iso,
            symbol=symbol,
            risk_level=risk_level,
            news_embargo_active=embargo,
            minutes_to_next_event=mins_away,
            next_event_name=closest["name"],
            next_event_impact=impact,
            risk_percent_multiplier=round(multiplier, 2),
            data_source=data_source,
        )

    async def assess(
        self,
        symbol: str,
        utc_now: Optional[datetime] = None,
    ) -> MacroRiskAssessment:
        """
        Async public API. Returns MacroRiskAssessment for the given symbol.
        Network I/O (Forex Factory fetch) is offloaded to a thread pool.
        """
        if utc_now is None:
            utc_now = datetime.now(timezone.utc)
        return await asyncio.to_thread(self._assess_sync, symbol, utc_now)
