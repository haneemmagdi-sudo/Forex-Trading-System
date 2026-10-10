"""
data/news_fetcher.py — عناوين الأخبار المسطّحة لوكلاء التحليل.

تُفوّض إلى NewsFetcher الحيّ (كاش متزامن عبر get_cached_news) ولا تجلب من
مصدر جديد. تُرجع قائمة نصوص فقط كما يتوقّع الوكيل، و[] عند غياب البيانات.
"""

from __future__ import annotations

import logging
from typing import List

from data import backend_module

logger = logging.getLogger("data.news_fetcher")

_MAX_HEADLINES = 10


def _fetcher():
    module = backend_module("core.news_fetcher")
    if module is None:
        return None
    try:
        return module.get_news_fetcher()
    except Exception as exc:
        logger.warning("[news_fetcher] news fetcher unavailable: %s", exc)
        return None


def fetch_combined_news(symbol: str, asset_class: str = "FOREX") -> List[str]:
    """
    عناوين الأخبار المسطّحة. تُفضّل ما يرتبط بالرمز، وتُكمل بالباقي عند قلّته.
    """
    fetcher = _fetcher()
    if fetcher is None:
        return []

    try:
        items = fetcher.get_cached_news() or []
    except Exception as exc:
        logger.warning("[news_fetcher] cached news unavailable: %s", exc)
        return []

    clean = (symbol or "").upper().replace("=X", "").replace("/", "").strip()
    base = clean[:3]
    related: List[str] = []
    others: List[str] = []

    for item in items:
        headline = item.get("headline") or item.get("title")
        if not headline:
            continue
        headline = str(headline)
        symbols = [str(s).upper().replace("=X", "") for s in (item.get("related_symbols") or [])]
        matches = bool(clean) and any(
            clean in s or (base and base in s) for s in symbols
        )
        (related if matches else others).append(headline)

    return (related + others)[:_MAX_HEADLINES]
