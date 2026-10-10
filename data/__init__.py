"""
data — طبقة وصول بيانات رقيقة لوكلاء التحليل (fx_analyst / equity_analyst).

هذه الحزمة كانت **غائبة تماماً** بينما الوكلاء يستوردون منها، فكانوا لا
يُستوردون إطلاقاً. وهي هنا **واجهة تفويض** لا بنية موازية:
  - بيانات الأسعار من Yahoo Finance (المزوّد الافتراضي DEFAULT_EQUITY_PROVIDER
    والمستخدم أصلاً كبديل حقيقي في MT5Connector).
  - التقويم الاقتصادي والأخبار من NewsFetcher الحيّ (backend/core/news_fetcher.py).

لا تُنشئ هذه الطبقة اتصال MT5 خاصاً بها إطلاقاً (تجنّباً لتهيئة عميل ثانٍ
أثناء تشغيل النظام)، ولا تُلفّق أي رقم: عند غياب البيانات تُرجع None أو [].
"""

import importlib
import logging

logger = logging.getLogger("data")


def backend_module(dotted: str):
    """
    يستورد وحدة من backend بغضّ النظر عن جذر sys.path الحالي.
    محاولة أولى: backend.<name>  ثم <name> (سياق التشغيل داخل backend).
    """
    for candidate in (f"backend.{dotted}", dotted):
        try:
            return importlib.import_module(candidate)
        except Exception:
            continue
    logger.debug("[data] backend module %s is unavailable", dotted)
    return None
