"""
============================================================
news_fetcher.py — جلب أخبار السوق الحقيقية (محسّن)
============================================================
مصادر الأخبار:
1. Finnhub API              (مفتاحه في .env)
2. Alpha Vantage News       (مجاني بدون مفتاح)
3. ForexFactory RSS         (تقويم اقتصادي حقيقي)
4. FXStreet RSS             (أخبار فوركس)
5. Investing.com RSS        (أخبار اقتصادية)
"""
import os
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from loguru import logger
import json

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser غير متوفر — pip install feedparser")


FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ── خريطة الكلمات المفتاحية للعملات ──────────────────────────────────
CURRENCY_KEYWORDS = {
    "EURUSD": ["EUR", "Euro", "ECB", "European Central Bank", "Eurozone", "euro zone"],
    "GBPUSD": ["GBP", "Pound", "BOE", "Bank of England", "Sterling", "Brexit", "Britain"],
    "USDJPY": ["JPY", "Yen", "BOJ", "Bank of Japan", "Japanese", "Japan"],
    "AUDUSD": ["AUD", "Australian", "RBA", "Reserve Bank of Australia"],
    "USDCAD": ["CAD", "Canadian", "BOC", "Bank of Canada", "Oil", "crude"],
    "USDCHF": ["CHF", "Swiss", "SNB", "Swiss National Bank", "Franc"],
    "NZDUSD": ["NZD", "RBNZ", "New Zealand"],
    "XAUUSD": ["Gold", "XAU", "Safe haven", "bullion"],
    "USD":    ["Fed", "Federal Reserve", "Dollar", "FOMC", "Powell", "CPI", "NFP",
               "GDP", "inflation", "rate hike", "rate cut", "jobs report"],
}

HIGH_IMPACT_KEYWORDS = [
    "interest rate", "rate decision", "rate hike", "rate cut",
    "inflation", "CPI", "GDP", "NFP", "non-farm payroll",
    "central bank", "monetary policy", "emergency", "crisis",
    "recession", "default", "war", "sanctions", "FOMC",
    "Powell", "Lagarde", "Bailey", "Kuroda", "Ueda",
    "سعر الفائدة", "تضخم", "ناتج محلي", "بنك مركزي",
]

MEDIUM_IMPACT_KEYWORDS = [
    "employment", "unemployment", "retail sales", "PMI",
    "trade balance", "current account", "housing",
    "consumer confidence", "manufacturing", "services",
    "jobless claims", "ADP", "ISM", "durable goods",
]

# ── مصادر RSS ─────────────────────────────────────────────────────────
RSS_FEEDS = {
    "FXStreet":     "https://www.fxstreet.com/rss/news",
    "ForexLive":    "https://www.forexlive.com/feed/news",
    "DailyFX":      "https://www.dailyfx.com/feeds/all",
    "Investing":    "https://www.investing.com/rss/news_25.rss",
}


class NewsItem:
    """خبر واحد"""
    def __init__(self, headline: str, summary: str, source: str,
                 datetime_str: str, url: str = "",
                 impact: str = "LOW", related_symbols: List[str] = None):
        self.headline = headline
        self.headline_ar = headline  # Default to original English headline
        self.summary = summary
        self.source = source
        self.datetime_str = datetime_str
        self.url = url
        self.impact = impact          # HIGH / MEDIUM / LOW
        self.related_symbols = related_symbols or []
        self.sentiment = "NEUTRAL"   # POSITIVE / NEGATIVE / NEUTRAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline":        self.headline,
            "headline_ar":     self.headline_ar,
            "summary":         self.summary,
            "source":          self.source,
            "datetime":        self.datetime_str,
            "url":             self.url,
            "impact":          self.impact,
            "related_symbols": self.related_symbols,
            "sentiment":       self.sentiment,
        }


class NewsFetcher:
    """
    محرك جلب الأخبار الحقيقية — محسّن
    ─────────────────────────────────────────────
    ✅ Finnhub API
    ✅ Alpha Vantage News
    ✅ RSS: FXStreet / ForexLive / DailyFX / Investing.com
    ✅ تحليل التأثير: HIGH / MEDIUM / LOW
    ✅ تحديد الأزواج المتأثرة
    ✅ تحليل المشاعر
    """

    def __init__(self):
        self.api_key = FINNHUB_API_KEY
        self._cache: List[NewsItem] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl_minutes = 5
        self._translation_cache: Dict[str, str] = {}
        self._calendar_cache = None
        self._last_calendar_fetch = None
        logger.info(
            f"NewsFetcher v2 | Finnhub: {'✅' if self.api_key else '❌'} | "
            f"RSS: {'✅' if FEEDPARSER_AVAILABLE else '❌'}"
        )

    async def translate_headline(self, text: str) -> str:
        """ترجمة عنوان الخبر المالي إلى العربية باستخدام Gemini API (مع السقوط التلقائي لـ Groq)"""
        if not text or not text.strip():
            return ""
        if text in self._translation_cache:
            return self._translation_cache[text]

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        github_key = os.getenv("GITHUB_MODELS_TOKEN", "")
        github_model = os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini")
        groq_key = os.getenv("GROQ_API_KEY", "")
        groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

        # 1. Try Gemini first
        if gemini_key and not gemini_key.startswith("your_"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={gemini_key}"
                payload = {
                    "model": gemini_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional financial translator. Translate the given English forex/financial news headline into clear, natural, and concise Arabic. Output ONLY the translated headline, nothing else."},
                        {"role": "user", "content": f"Headline: {text}"}
                    ],
                    "temperature": 0.3
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {gemini_key}"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            translated = data["choices"][0]["message"]["content"].strip()
                            if translated.startswith('"') and translated.endswith('"'):
                                translated = translated[1:-1]
                            self._translation_cache[text] = translated
                            return translated
                        else:
                            logger.warning(f"⚠️ Gemini Translation HTTP {resp.status} - falling back to Groq")
            except Exception as e:
                logger.warning(f"❌ Gemini Translation error: {e} - falling back to Groq")

        # 2. Try Groq next (ultra-fast active fallback)
        if groq_key and not groq_key.startswith("your_"):
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = {
                    "model": groq_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional financial translator. Translate the given English forex/financial news headline into clear, natural, and concise Arabic. Output ONLY the translated headline, nothing else."},
                        {"role": "user", "content": f"Headline: {text}"}
                    ],
                    "temperature": 0.3
                }
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            translated = data["choices"][0]["message"]["content"].strip()
                            if translated.startswith('"') and translated.endswith('"'):
                                translated = translated[1:-1]
                            self._translation_cache[text] = translated
                            return translated
                        else:
                            logger.warning(f"⚠️ Groq Translation HTTP {resp.status}")
            except Exception as e:
                logger.warning(f"❌ Groq Translation error: {e}")

        # 3. Fallback to GitHub Models (if accessible)
        if github_key and not github_key.startswith("your_"):
            try:
                url = "https://models.inference.ai.azure.com/chat/completions"
                payload = {
                    "model": github_model,
                    "messages": [
                        {"role": "system", "content": "You are a professional financial translator. Translate the given English forex/financial news headline into clear, natural, and concise Arabic. Output ONLY the translated headline, nothing else."},
                        {"role": "user", "content": f"Headline: {text}"}
                    ],
                    "temperature": 0.3
                }
                headers = {
                    "Authorization": f"Bearer {github_key}",
                    "Content-Type": "application/json"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            translated = data["choices"][0]["message"]["content"].strip()
                            if translated.startswith('"') and translated.endswith('"'):
                                translated = translated[1:-1]
                            self._translation_cache[text] = translated
                            return translated
                        else:
                            logger.warning(f"⚠️ GitHub Models Translation HTTP {resp.status}")
            except Exception as e:
                logger.debug(f"GitHub Models Translation error: {e}")

        return text

    async def fetch_forex_news(self, force: bool = False) -> List[NewsItem]:
        """جلب أخبار الفوركس الحقيقية من جميع المصادر"""
        now = datetime.now(timezone.utc)
        if (not force and self._last_fetch and
                (now - self._last_fetch).total_seconds() < self._cache_ttl_minutes * 60):
            return self._cache

        news_items: List[NewsItem] = []

        # تشغيل جميع المصادر بالتوازي
        tasks = []

        if self.api_key:
            tasks.append(self._fetch_finnhub_news())

        tasks.append(self._fetch_alphavantage_news())

        if FEEDPARSER_AVAILABLE:
            for feed_name, feed_url in RSS_FEEDS.items():
                tasks.append(self._fetch_rss_feed(feed_name, feed_url))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                news_items.extend(r)
            elif isinstance(r, Exception):
                logger.warning(f"⚠️ خطأ في مصدر أخبار: {r}")

        # إزالة المكررات
        seen = set()
        unique_news = []
        for item in news_items:
            key = item.headline[:60].lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique_news.append(item)

        # ترتيب: HIGH أولاً ثم MEDIUM ثم الأحدث
        unique_news.sort(key=lambda x: (
            0 if x.impact == "HIGH" else
            1 if x.impact == "MEDIUM" else 2
        ))

        # ترجمة عناوين أهم 20 خبرًا بالتوازي لتجنب استهلاك موارد مفرط
        top_to_translate = unique_news[:20]
        translation_tasks = [self.translate_headline(item.headline) for item in top_to_translate]
        
        if translation_tasks:
            translated_headlines = await asyncio.gather(*translation_tasks, return_exceptions=True)
            for item, tr_headline in zip(top_to_translate, translated_headlines):
                if isinstance(tr_headline, str) and tr_headline.strip():
                    item.headline_ar = tr_headline
                else:
                    item.headline_ar = item.headline

        self._cache = unique_news[:100]   # احتفظ بآخر 100 خبر
        self._last_fetch = now

        high_count   = sum(1 for n in self._cache if n.impact == "HIGH")
        medium_count = sum(1 for n in self._cache if n.impact == "MEDIUM")
        logger.info(
            f"📰 أخبار حقيقية: {len(self._cache)} | "
            f"HIGH:{high_count} MEDIUM:{medium_count}"
        )
        return self._cache

    # ── Finnhub ────────────────────────────────────────────────────────
    async def _fetch_finnhub_news(self) -> List[NewsItem]:
        items = []
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {"category": "forex", "token": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for article in data[:40]:
                            headline = article.get("headline", "").strip()
                            summary  = article.get("summary", "")
                            if not headline:
                                continue
                            dt = article.get("datetime", 0)
                            dt_str = (
                                datetime.fromtimestamp(dt, tz=timezone.utc).isoformat()
                                if dt else datetime.now(timezone.utc).isoformat()
                            )
                            item = NewsItem(
                                headline    = headline,
                                summary     = summary[:400] if summary else "",
                                source      = article.get("source", "Finnhub"),
                                datetime_str= dt_str,
                                url         = article.get("url", ""),
                            )
                            text = headline + " " + summary
                            item.impact          = self._analyze_impact(text)
                            item.related_symbols = self._find_related_symbols(text)
                            item.sentiment       = self._analyze_sentiment(text)
                            items.append(item)
                    else:
                        logger.warning(f"⚠️ Finnhub HTTP {resp.status}")
        except Exception as e:
            logger.error(f"❌ Finnhub: {e}")
        return items

    # ── Alpha Vantage ──────────────────────────────────────────────────
    async def _fetch_alphavantage_news(self) -> List[NewsItem]:
        items = []
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "topics":   "forex",
                "sort":     "LATEST",
                "limit":    "25",
                "apikey":   os.getenv("ALPHA_VANTAGE_KEY", "demo"),
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for article in data.get("feed", [])[:25]:
                            headline = article.get("title", "").strip()
                            if not headline:
                                continue
                            summary  = article.get("summary", "")
                            dt_str   = article.get("time_published", "")
                            try:
                                dt_obj = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
                                dt_iso = dt_obj.replace(tzinfo=timezone.utc).isoformat()
                            except Exception:
                                dt_iso = datetime.now(timezone.utc).isoformat()

                            overall = article.get("overall_sentiment_label", "Neutral")
                            sentiment = (
                                "POSITIVE" if "Bullish" in overall else
                                "NEGATIVE" if "Bearish" in overall else "NEUTRAL"
                            )
                            text = headline + " " + summary
                            item = NewsItem(
                                headline    = headline,
                                summary     = summary[:400],
                                source      = article.get("source", "Alpha Vantage"),
                                datetime_str= dt_iso,
                                url         = article.get("url", ""),
                            )
                            item.impact          = self._analyze_impact(text)
                            item.related_symbols = self._find_related_symbols(text)
                            item.sentiment       = sentiment
                            items.append(item)
        except Exception as e:
            logger.warning(f"⚠️ Alpha Vantage: {e}")
        return items

    # ── RSS Feeds ──────────────────────────────────────────────────────
    async def _fetch_rss_feed(self, feed_name: str, feed_url: str) -> List[NewsItem]:
        """جلب من RSS feed في thread منفصل (feedparser ليس async)"""
        if not FEEDPARSER_AVAILABLE:
            return []
        items = []
        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

            for entry in feed.entries[:20]:
                headline = entry.get("title", "").strip()
                if not headline:
                    continue
                summary = entry.get("summary", "") or entry.get("description", "")
                url_link = entry.get("link", "")

                # تاريخ النشر
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    try:
                        from time import mktime
                        dt_iso = datetime.fromtimestamp(
                            mktime(published), tz=timezone.utc
                        ).isoformat()
                    except Exception:
                        dt_iso = datetime.now(timezone.utc).isoformat()
                else:
                    dt_iso = datetime.now(timezone.utc).isoformat()

                # تجاهل الأخبار الأقدم من 24 ساعة
                try:
                    news_time = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - news_time).total_seconds() > 86400:
                        continue
                except Exception:
                    pass

                text = headline + " " + (summary or "")
                item = NewsItem(
                    headline    = headline,
                    summary     = (summary or "")[:400],
                    source      = feed_name,
                    datetime_str= dt_iso,
                    url         = url_link,
                )
                item.impact          = self._analyze_impact(text)
                item.related_symbols = self._find_related_symbols(text)
                item.sentiment       = self._analyze_sentiment(text)
                items.append(item)

            logger.debug(f"📡 RSS {feed_name}: {len(items)} أخبار")
        except Exception as e:
            logger.warning(f"⚠️ RSS {feed_name}: {e}")
        return items

    # ── تحليل النص ────────────────────────────────────────────────────
    def _analyze_impact(self, text: str) -> str:
        text_lower = text.lower()
        for kw in HIGH_IMPACT_KEYWORDS:
            if kw.lower() in text_lower:
                return "HIGH"
        for kw in MEDIUM_IMPACT_KEYWORDS:
            if kw.lower() in text_lower:
                return "MEDIUM"
        return "LOW"

    def _find_related_symbols(self, text: str) -> List[str]:
        related = []
        text_upper = text.upper()
        for symbol, keywords in CURRENCY_KEYWORDS.items():
            for kw in keywords:
                if kw.upper() in text_upper:
                    if symbol not in related:
                        related.append(symbol)
                    break
        return related

    def _analyze_sentiment(self, text: str) -> str:
        positive_words = [
            "rise", "gain", "surge", "up", "strong", "beat", "better",
            "growth", "recovery", "bullish", "positive", "boost", "rally",
            "ارتفع", "نما", "تحسن", "قوي",
        ]
        negative_words = [
            "fall", "drop", "decline", "weak", "miss", "worse",
            "recession", "crisis", "bearish", "negative", "cut", "slump",
            "انخفض", "تراجع", "أزمة", "ضعيف",
        ]
        text_lower = text.lower()
        pos = sum(1 for w in positive_words if w in text_lower)
        neg = sum(1 for w in negative_words if w in text_lower)
        if pos > neg:
            return "POSITIVE"
        elif neg > pos:
            return "NEGATIVE"
        return "NEUTRAL"

    # ── Helpers ────────────────────────────────────────────────────────
    def get_cached_news(self) -> List[Dict]:
        return [n.to_dict() for n in self._cache]

    def has_high_impact_upcoming(self, symbol: str, minutes_ahead: int = 30) -> bool:
        now = datetime.now(timezone.utc)
        for news in self._cache:
            if news.impact != "HIGH":
                continue
            if symbol not in news.related_symbols and "USD" not in news.related_symbols:
                continue
            try:
                news_time = datetime.fromisoformat(
                    news.datetime_str.replace("Z", "+00:00")
                )
                diff = (news_time - now).total_seconds() / 60
                if -5 <= diff <= minutes_ahead:
                    return True
            except Exception:
                pass
        return False

    def get_market_sentiment(self) -> Dict[str, str]:
        sentiment_counts: Dict[str, Dict[str, int]] = {}
        for news in self._cache[-30:]:
            for symbol in news.related_symbols:
                if symbol not in sentiment_counts:
                    sentiment_counts[symbol] = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
                sentiment_counts[symbol][news.sentiment] = (
                    sentiment_counts[symbol].get(news.sentiment, 0) + 1
                )
        result = {}
        for symbol, counts in sentiment_counts.items():
            pos = counts.get("POSITIVE", 0)
            neg = counts.get("NEGATIVE", 0)
            if pos > neg * 1.5:
                result[symbol] = "BULLISH"
            elif neg > pos * 1.5:
                result[symbol] = "BEARISH"
            else:
                result[symbol] = "NEUTRAL"
        return result

    async def translate_headlines_batch(self, texts: List[str]) -> List[str]:
        if not texts:
            return []
            
        results = []
        to_translate = []
        to_translate_indices = []
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                results.append("")
            elif text in self._translation_cache:
                results.append(self._translation_cache[text])
            else:
                results.append(None)
                to_translate.append(text)
                to_translate_indices.append(i)
                
        if not to_translate:
            return results
            
        batch_size = 25
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        
        for start_idx in range(0, len(to_translate), batch_size):
            chunk = to_translate[start_idx:start_idx + batch_size]
            chunk_indices = to_translate_indices[start_idx:start_idx + batch_size]
            
            prompt_lines = [f"{idx}. {text}" for idx, text in enumerate(chunk)]
            prompt = "Translate the following list of economic/financial events into clear, concise financial Arabic. Return a JSON list of strings representing the translations, in the exact same order as input. Do not output markdown code blocks or anything other than the JSON array of strings.\n\nInput:\n" + "\n".join(prompt_lines)
            
            translated_chunk = None
            if gemini_key and not gemini_key.startswith("your_"):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={gemini_key}"
                    payload = {
                        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                        "messages": [
                            {"role": "system", "content": "You are a professional financial translator. Translate the given list of economic indicators/events into Arabic. Return ONLY a valid JSON list of translated strings matching the input length. No formatting, no markdown, just JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2
                    }
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {gemini_key}"
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                content = data["choices"][0]["message"]["content"].strip()
                                if "```json" in content:
                                    content = content.split("```json")[1].split("```")[0].strip()
                                elif "```" in content:
                                    content = content.split("```")[1].split("```")[0].strip()
                                
                                parsed = json.loads(content)
                                if isinstance(parsed, list) and len(parsed) == len(chunk):
                                    translated_chunk = parsed
                except Exception as e:
                    logger.warning(f"Batch translation error with Gemini: {e}")
                    
            if not translated_chunk:
                translated_chunk = list(chunk)
            
            for idx, trans_val in zip(chunk_indices, translated_chunk):
                results[idx] = trans_val
                original_text = texts[idx]
                self._translation_cache[original_text] = trans_val
                
        return results

    async def fetch_economic_calendar(self, force: bool = False) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if not force and self._calendar_cache is not None and self._last_calendar_fetch is not None:
            if (now - self._last_calendar_fetch).total_seconds() < 15 * 60:
                logger.info("CACHE HIT | fetch_economic_calendar")
                return self._calendar_cache

        url = "https://economic-calendar.tradingview.com/events"
        start_date = (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
        end_date = (now + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59.000Z")
        
        params = {
            "from": start_date,
            "to": end_date
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/"
        }
        
        logger.info(f"API CALL  | fetch_economic_calendar from {start_date} to {end_date}")
        raw_events = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=12) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        raw_events = res_json.get("result", [])
                    else:
                        logger.warning(f"⚠️ TradingView Calendar HTTP {resp.status}")
        except Exception as e:
            logger.error(f"❌ Error fetching TradingView calendar: {e}")

        if not raw_events:
            return self._calendar_cache or []

        processed = []
        major_currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU"}
        
        raw_events.sort(key=lambda x: x.get("date", ""))

        events_to_process = []
        for item in raw_events:
            curr = item.get("currency")
            importance = item.get("importance", -1)
            
            if importance < 0 or not curr or curr not in major_currencies:
                continue
            events_to_process.append(item)

        titles_to_translate = [e.get("title", "") for e in events_to_process]
        translated_titles = await self.translate_headlines_batch(titles_to_translate)

        for i, item in enumerate(events_to_process):
            title_ar = translated_titles[i] if i < len(translated_titles) else item.get("title", "")
            
            actual = item.get("actual")
            forecast = item.get("forecast")
            previous = item.get("previous")
            unit = item.get("unit", "")
            
            def format_val(val):
                if val is None:
                    return "—"
                if isinstance(val, (int, float)):
                    val_str = f"{val:.4g}".rstrip('0').rstrip('.') if '.' in f"{val:.4g}" else f"{val}"
                    return f"{val_str}{unit}"
                return f"{val}{unit}"

            imp_str = "HIGH" if item.get("importance") == 1 else "MEDIUM"
            impact_direction = self._determine_calendar_impact(item.get("title", ""), actual, forecast, previous)
            
            processed.append({
                "id": item.get("id"),
                "time": item.get("date"),
                "event": title_ar,
                "importance": imp_str,
                "forecast": format_val(forecast),
                "previous": format_val(previous),
                "actual": format_val(actual),
                "impact": impact_direction,
                "date": item.get("date"),
                "country": item.get("country"),
                "currency": item.get("currency")
            })

        self._calendar_cache = processed
        self._last_calendar_fetch = now
        logger.info(f"✅ Formatted and cached {len(processed)} economic calendar events.")
        return processed

    def _determine_calendar_impact(self, title: str, actual, forecast, previous) -> str:
        if actual is None:
            return "NEUTRAL"
        try:
            act_val = float(actual)
            fc_val = float(forecast) if forecast is not None else None
            prev_val = float(previous) if previous is not None else None
        except (ValueError, TypeError):
            return "NEUTRAL"

        compare_val = fc_val if fc_val is not None else prev_val
        if compare_val is None:
            return "NEUTRAL"

        diff = act_val - compare_val
        if abs(diff) < 1e-6:
            return "NEUTRAL"

        bearish_if_higher = [
            "unemployment", "jobless claims", "inventories", "claims", "بثقة المستهلك",
            "بطالة", "شكاوى البطالة", "مخزونات"
        ]
        title_lower = title.lower()
        is_bearish_if_higher = any(kw in title_lower for kw in bearish_if_higher)

        if diff > 0:
            return "BEARISH" if is_bearish_if_higher else "BULLISH"
        else:
            return "BULLISH" if is_bearish_if_higher else "BEARISH"


# ── Singleton ──────────────────────────────────────────────────────────
_news_fetcher_instance: Optional[NewsFetcher] = None

def get_news_fetcher() -> NewsFetcher:
    global _news_fetcher_instance
    if _news_fetcher_instance is None:
        _news_fetcher_instance = NewsFetcher()
    return _news_fetcher_instance
