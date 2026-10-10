"""
data/economic_calendar.py — واجهة التقويم الاقتصادي لوكلاء التحليل.

تُفوّض بالكامل إلى NewsFetcher الحيّ (backend/core/news_fetcher.py) ولا تجلب
من أي مصدر جديد. تُوحّد اسم المفتاح إلى ``event_name`` كما يتوقّعه الوكيل.

ملاحظة تزامن: دوال NewsFetcher غير متزامنة (async) بينما يسميها الوكيل
بشكل متزامن، لذا تُنفَّذ عبر خيط منفصل بحلقة أحداث خاصة (آمنة داخل حلقة
الأحداث العاملة، بخلاف asyncio.run).
"""

from __future__ import annotations

import asyncio
import logging
import concurrent.futures
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data import backend_module

logger = logging.getLogger("data.economic_calendar")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="econ-cal")
_PRIORITY_IMPACT = "HIGH"
_SHIELD_BUFFER_MINUTES = 15


def _run_sync(coro) -> Any:
    """تشغيل coroutine من سياق متزامن حتى داخل حلقة أحداث عاملة."""
    return _executor.submit(asyncio.run, coro).result()


def _fetcher():
    module = backend_module("core.news_fetcher")
    if module is None:
        return None
    try:
        return module.get_news_fetcher()
    except Exception as exc:
        logger.warning("[econ_calendar] news fetcher unavailable: %s", exc)
        return None


def _parse_time(value: Any) -> Optional[datetime]:
    """قراءة وقت الحدث بتسامح: epoch رقمي أو نص ISO أو صيغ شائعة."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    for parser in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"),
        lambda t: datetime.strptime(t, "%Y-%m-%dT%H:%M:%S"),
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
    ):
        try:
            parsed = parser(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _normalise(event: Dict[str, Any]) -> Dict[str, Any]:
    """توحيد مفاتيح حدث التقويم القادم من NewsFetcher."""
    normalised = dict(event or {})
    normalised["event_name"] = (
        normalised.get("event_name")
        or normalised.get("event")
        or normalised.get("title")
        or "UNKNOWN"
    )
    normalised["importance"] = str(normalised.get("importance", "")).upper()
    # يُخزَّن الوقت داخلياً كنص ISO لا ككائن datetime: وكيل التحليل يُسلسل هذه
    # الأحداث إلى JSON لبناء الطلب، وكائن datetime غير قابل للتسلسل.
    parsed = _parse_time(normalised.get("time") or normalised.get("date"))
    normalised["_time"] = parsed.isoformat() if parsed else None
    return normalised


def _event_time(event: Dict[str, Any]) -> Optional[datetime]:
    """قراءة وقت الحدث من المفتاح الداخلي (نص ISO) أو من المصدر الأصلي."""
    return _parse_time(event.get("_time") or event.get("time") or event.get("date"))


def fetch_economic_events(days_ahead: int = 1) -> List[Dict[str, Any]]:
    """
    لقطة من التقويم الاقتصادي الحقيقي.
    ``days_ahead`` مقبول للتوافق مع نداء الوكيل؛ النافذة الزمنية يأتي بها
    المزوّد نفسه، فلا نُفلتر هنا (ولا نختلق أحداثاً عند الفشل — نُرجع []).
    """
    fetcher = _fetcher()
    if fetcher is None:
        return []
    try:
        raw = _run_sync(fetcher.fetch_economic_calendar())
    except Exception as exc:
        logger.warning("[econ_calendar] fetch failed: %s", exc)
        return []
    return [_normalise(event) for event in (raw or [])]


def get_high_impact_events_within(minutes_ahead: int, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """الأحداث عالية التأثير الواقعة خلال النافذة الزمنية القادمة."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(minutes=float(minutes_ahead or 0))
    selected: List[Dict[str, Any]] = []
    for event in events or []:
        normalised = event if "event_name" in event else _normalise(event)
        if normalised.get("importance") != _PRIORITY_IMPACT:
            continue
        when = _event_time(normalised)
        if when is None:
            # وقت غير قابل للقراءة: نُبقيه (التحوّط خير من التداول في خبر مجهول الوقت)
            selected.append(normalised)
        elif now - timedelta(minutes=_SHIELD_BUFFER_MINUTES) <= when <= horizon:
            selected.append(normalised)
    return selected


def get_shield_expiry(events: List[Dict[str, Any]]) -> Optional[datetime]:
    """نهاية فترة حظر الأخبار: أبعد وقت حدث + هامش تحوّط."""
    times = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        when = _event_time(event)
        if when:
            times.append(when)
    if not times:
        return None
    return max(times) + timedelta(minutes=_SHIELD_BUFFER_MINUTES)


def should_activate_news_shield(events: List[Dict[str, Any]]) -> bool:
    """هل توجد أحداث عالية التأثير تستوجب تفعيل الحظر؟"""
    for event in events or []:
        if not isinstance(event, dict):
            continue
        normalised = event if "importance" in event else _normalise(event)
        if str(normalised.get("importance", "")).upper() == _PRIORITY_IMPACT:
            return True
    return False
