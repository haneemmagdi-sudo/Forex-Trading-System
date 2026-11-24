"""
============================================================
news_agent.py — الوكيل الخامس: محلل الأخبار
============================================================
يجلب أخبار السوق الحقيقية كل 5 دقائق
يُحلل تأثيرها على أزواج العملات
يُخطر الوكلاء الآخرين عبر Signal Bus
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger

from agents.base_agent import BaseAgent
from core.news_fetcher import get_news_fetcher, NewsItem
import config as _cfg
from core.signal_bus import BusMessage
from core.news_sentiment_engine import HybridNewsSentimentEngine
FOUNDATION_MODELS_2026 = getattr(_cfg, 'FOUNDATION_MODELS_2026', {})
SYMBOLS = getattr(_cfg, 'SYMBOLS', [])


class NewsAgent(BaseAgent):
    """
    الوكيل الخامس — محلل الأخبار الحقيقية
    ────────────────────────────────────────────────────
    ✅ يجلب أخبار فوركس حقيقية من Finnhub + Alpha Vantage
    ✅ يُحلل التأثير: HIGH / MEDIUM / LOW
    ✅ يُرسل تنبيهات للوكلاء قبل الأخبار الكبرى
    ✅ يُشارك اتجاه السوق مع MarketAnalyst
    ✅ يُوصي بتجنب فتح صفقات قبل أخبار HIGH
    """

    def __init__(self):
        super().__init__("NewsAgent", interval_sec=300)  # كل 5 دقائق
        self.fetcher = get_news_fetcher()
        self._last_high_impact_alert: Dict[str, float] = {}  # منع تكرار التنبيهات
        self._market_sentiment: Dict[str, str] = {}
        self._market_sentiment_scores: Dict[str, float] = {}
        self._central_bank_tones: Dict[str, str] = {}
        self.sentiment_engine = HybridNewsSentimentEngine(
            finbert_model_id=FOUNDATION_MODELS_2026.get('finbert_model_id', 'ProsusAI/finbert'),
            gemma_model_id=FOUNDATION_MODELS_2026.get('gemma_model_id', 'gemma3:4b'),
            gemma_ollama_url=FOUNDATION_MODELS_2026.get('gemma_ollama_url', 'http://127.0.0.1:11434'),
            use_finbert=FOUNDATION_MODELS_2026.get('finbert_enabled', True),
            use_gemma_for_high_impact=FOUNDATION_MODELS_2026.get('gemma_enabled_for_high_impact', True),
        )

        self.stats.update({
            "news_fetched":      0,
            "high_impact_alerts":0,
            "last_news_title":   None,
            "market_sentiment":  {},
        })

    async def run_cycle(self):
        """دورة جلب وتحليل الأخبار"""
        await self.log("INFO", "📰 جلب أخبار السوق الحقيقية...")

        try:
            news_list = await self.fetcher.fetch_forex_news(force=True)

            if not news_list:
                await self.log("WARNING", "⚠️ لم تُجلب أي أخبار — تحقق من API Keys")
                return

            self.stats["news_fetched"] += len(news_list)

            # آخر خبر
            if news_list:
                self.stats["last_news_title"] = news_list[0].headline[:60]

            # 2026 Upgrade: تحليل اتجاه السوق عبر FinBERT + Gemma الهجين مع دمج تصنيف news_fetcher
            base_sentiment = self.fetcher.get_market_sentiment() or {}
            ai_labels, ai_scores, ai_tones = self.sentiment_engine.aggregate_symbol_sentiment(news_list, symbols=SYMBOLS)
            merged_sentiment = dict(base_sentiment)
            merged_sentiment.update(ai_labels)
            self._market_sentiment = merged_sentiment
            self._market_sentiment_scores = ai_scores
            self._central_bank_tones = ai_tones
            self.stats["market_sentiment"] = self._market_sentiment
            self.stats["market_sentiment_scores"] = self._market_sentiment_scores

            # نشر الأخبار الحقيقية والدرجات المستمرة عبر Bus
            await self.bus.publish(BusMessage(
                topic  = "news_update",
                sender = self.name,
                data   = {
                    "news":               [n.to_dict() for n in news_list[:10]],
                    "sentiment":          self._market_sentiment,
                    "sentiment_scores":   self._market_sentiment_scores,
                    "central_bank_tones": self._central_bank_tones,
                    "total":              len(news_list),
                    "timestamp":          datetime.now(timezone.utc).isoformat(),
                }
            ))

            # تنبيهات الأخبار عالية التأثير
            high_impact = [n for n in news_list if n.impact == "HIGH"]
            for news_item in high_impact[:5]:
                await self._maybe_send_alert(news_item)

            await self.log(
                "INFO",
                f"✅ أخبار: {len(news_list)} إجمالي | "
                f"HIGH:{len(high_impact)} | "
                f"اتجاه السوق: {self._market_sentiment}"
            )

        except Exception as e:
            await self.log("ERROR", f"❌ خطأ في جلب الأخبار: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _maybe_send_alert(self, news_item: NewsItem):
        """إرسال تنبيه للأخبار المهمة (مع منع التكرار)"""
        key = news_item.headline[:40]
        now = datetime.now(timezone.utc).timestamp()
        last = self._last_high_impact_alert.get(key, 0)

        if (now - last) < 3600:  # تنبيه واحد كل ساعة لنفس الخبر
            return

        self._last_high_impact_alert[key] = now
        self.stats["high_impact_alerts"] += 1

        await self.bus.dispatch(BusMessage(
            topic    = "news_alert",
            sender   = self.name,
            priority = 2,  # أولوية عالية
            data     = {
                "headline":        news_item.headline,
                "impact":          news_item.impact,
                "sentiment":       news_item.sentiment,
                "related_symbols": news_item.related_symbols,
                "source":          news_item.source,
                "datetime":        news_item.datetime_str,
                "recommendation":  "AVOID_NEW_TRADES" if news_item.impact == "HIGH" else "CAUTION",
            }
        ))

        await self.log(
            "WARNING",
            f"🔔 خبر HIGH IMPACT: {news_item.headline[:60]} | "
            f"المتأثر: {news_item.related_symbols} | "
            f"التوصية: تجنب فتح صفقات جديدة"
        )

    def get_market_sentiment(self) -> Dict[str, str]:
        """الحصول على اتجاه السوق للأزواج"""
        return self._market_sentiment

    def get_cached_news(self) -> List[dict]:
        """آخر الأخبار المُجلبة"""
        return self.fetcher.get_cached_news()

    def get_social_buzz(self) -> List[dict]:
        """
        P2 fix (AGENTS.md): إزالة أرقام وسائل التواصل المُلفقة (24820 + random).
        يُرجع توزيع المشاعر المقيس فعلياً من مصادر الأخبار المتصلة فقط.
        """
        news_list = self.get_cached_news()
        if not news_list:
            return []
        by_source: Dict[str, Dict[str, int]] = {}
        for n in news_list:
            src = n.get("source") or "NewsFeed"
            bucket = by_source.setdefault(src, {"total": 0, "pos": 0, "neg": 0})
            bucket["total"] += 1
            if n.get("sentiment") == "POSITIVE":
                bucket["pos"] += 1
            elif n.get("sentiment") == "NEGATIVE":
                bucket["neg"] += 1
        result = []
        for src, c in by_source.items():
            tot = max(c["total"], 1)
            result.append({
                "platform": src,
                "mentions": c["total"],
                "bullish": round(100.0 * c["pos"] / tot, 1),
                "bearish": round(100.0 * c["neg"] / tot, 1),
                "icon": "📰",
                "measured": True,
            })
        return result

    def is_news_blackout(self, symbol: str) -> bool:
        """هل النظام في فترة تجنب الأخبار لهذا الزوج؟"""
        return self.fetcher.has_high_impact_upcoming(symbol, minutes_ahead=30)
