"""
============================================================
news_sentiment_engine.py — محرك مشاعر الأخبار الهجين (2026)
============================================================
يدمج مسارين متكاملين لتحليل الأخبار الاقتصادية وقرارات البنوك المركزية:
  1. المسار السريع الدائم (FinBERT — ProsusAI/finbert، Apache-2.0):
     تصنيف فوري لكل عنوان خبر إلى (positive / negative / neutral) وتحويله
     إلى درجة رقمية مستمرة `sentiment_score` ضمن [-1.0, +1.0].
  2. المسار العميق للأخبار عالية التأثير (Gemma 3/4 عبر Ollama أو transformers):
     يُستدعى فقط عند الأخبار المصنّفة HIGH (قرارات الفائدة، التضخم، الوظائف)
     لاستخراج نبرة البنك المركزي (HAWKISH / DOVISH / NEUTRAL) وتوصية الحظر.
  3. مسار احتياطي حتمي (Financial Lexicon Fallback):
     يعمل فوراً بدون إنترنت أو GPU إذا لم تكن أوزان FinBERT/Gemma محمّلة بعد.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("NewsSentimentEngine")


@dataclass
class NewsSentimentResult:
    headline: str
    sentiment_label: str = "NEUTRAL"          # BULLISH | BEARISH | NEUTRAL
    sentiment_score: float = 0.0              # [-1.0, +1.0]
    confidence: float = 0.5
    central_bank_tone: str = "NEUTRAL"        # HAWKISH | DOVISH | NEUTRAL
    recommended_action: str = "NORMAL"        # NORMAL | CAUTION | AVOID_NEW_TRADES
    engine_used: str = "LEXICON_FALLBACK"     # FINBERT | FINBERT+GEMMA | LEXICON_FALLBACK
    affected_currencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HybridNewsSentimentEngine:
    """
    محرك تحليل مشاعر الأخبار الهجين (FinBERT للأخبار العامة + Gemma لأخبار HIGH).
    """

    _BULLISH_TERMS = (
        "hawkish", "rate hike", "raises rates", "stronger than expected",
        "beats forecast", "gdp growth", "inflation rises", "cpi rises",
        "hot cpi", "jobs surge", "payroll beat", "tightening", "rally", "surges",
    )
    _BEARISH_TERMS = (
        "dovish", "rate cut", "cuts rates", "weaker than expected",
        "misses forecast", "recession", "contraction", "inflation cools",
        "cpi falls", "unemployment rises", "layoffs", "easing", "plunge", "slump",
    )
    _HAWKISH_TERMS = ("hawkish", "rate hike", "raises rates", "tightening", "higher for longer", "hot cpi")
    _DOVISH_TERMS  = ("dovish", "rate cut", "cuts rates", "easing", "pivot", "cooling inflation")
    _CURRENCIES    = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU")

    def __init__(
        self,
        finbert_model_id: str = "ProsusAI/finbert",
        gemma_model_id: str = "gemma3:4b",
        gemma_ollama_url: str = "http://127.0.0.1:11434",
        use_finbert: bool = True,
        use_gemma_for_high_impact: bool = True,
        finbert_pipeline: Optional[Callable] = None,
        gemma_client: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.finbert_model_id = finbert_model_id
        self.gemma_model_id = gemma_model_id
        self.gemma_ollama_url = gemma_ollama_url.rstrip("/")
        self.use_finbert = bool(use_finbert)
        self.use_gemma_for_high_impact = bool(use_gemma_for_high_impact)

        self._finbert = finbert_pipeline
        self._finbert_load_attempted = finbert_pipeline is not None
        self._gemma_client = gemma_client

    def _ensure_finbert(self):
        if self._finbert is not None or self._finbert_load_attempted or not self.use_finbert:
            return self._finbert
        self._finbert_load_attempted = True
        try:
            from transformers import pipeline
            self._finbert = pipeline(
                "text-classification",
                model=self.finbert_model_id,
                truncation=True,
                max_length=256,
            )
            logger.info("Loaded FinBERT weights: %s", self.finbert_model_id)
        except Exception as exc:
            logger.debug("FinBERT unavailable, using deterministic lexicon fallback: %s", exc)
            self._finbert = None
        return self._finbert

    @classmethod
    def _extract_currencies(cls, text: str) -> List[str]:
        up = (text or "").upper()
        found = [c for c in cls._CURRENCIES if re.search(rf"\b{c}\b", up)]
        if "FED" in up or "FOMC" in up or "POWELL" in up or "NFP" in up:
            if "USD" not in found:
                found.append("USD")
        if "ECB" in up or "LAGARDE" in up:
            if "EUR" not in found:
                found.append("EUR")
        if "BOE" in up or "BAILEY" in up:
            if "GBP" not in found:
                found.append("GBP")
        if "BOJ" in up or "UEDA" in up:
            if "JPY" not in found:
                found.append("JPY")
        return found

    def _lexicon_score(self, text: str) -> Tuple[float, float, str]:
        low = (text or "").lower()
        b_hits = sum(1 for t in self._BULLISH_TERMS if t in low)
        s_hits = sum(1 for t in self._BEARISH_TERMS if t in low)
        total = b_hits + s_hits
        score = 0.0 if total == 0 else max(-1.0, min(1.0, (b_hits - s_hits) / max(2.0, float(total))))
        conf = min(0.85, 0.50 + 0.12 * total)
        tone = "NEUTRAL"
        if any(t in low for t in self._HAWKISH_TERMS):
            tone = "HAWKISH"
        elif any(t in low for t in self._DOVISH_TERMS):
            tone = "DOVISH"
        return round(score, 4), round(conf, 4), tone

    def _score_with_finbert(self, text: str) -> Optional[Tuple[float, float]]:
        pipe = self._ensure_finbert()
        if pipe is None:
            return None
        try:
            out = pipe(text)
            item = out[0] if isinstance(out, list) and out else out
            lbl = str(item.get("label", "neutral")).lower()
            prob = float(item.get("score", 0.5))
            if "pos" in lbl:
                return round(prob, 4), round(prob, 4)
            if "neg" in lbl:
                return round(-prob, 4), round(prob, 4)
            return 0.0, round(prob, 4)
        except Exception as exc:
            logger.debug("FinBERT inference failed: %s", exc)
            return None

    def _query_gemma_high_impact(self, headline: str) -> Optional[Dict[str, Any]]:
        if not self.use_gemma_for_high_impact:
            return None
        if self._gemma_client is not None:
            try:
                return self._gemma_client(headline)
            except Exception as exc:
                logger.debug("Custom Gemma client failed: %s", exc)
                return None
        # Local Ollama HTTP call (strictly localhost, fast 3s timeout)
        prompt = (
            "Classify this Forex macro headline and reply ONLY with valid JSON keys "
            '{"central_bank_tone":"HAWKISH|DOVISH|NEUTRAL","sentiment_score":float(-1..1),'
            '"recommended_action":"NORMAL|CAUTION|AVOID_NEW_TRADES"}. '
            f"Headline: {headline}"
        )
        payload = json.dumps({
            "model": self.gemma_model_id,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.gemma_ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                raw = body.get("response", "{}")
                return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    def analyze_headline(self, headline: str, impact: str = "MEDIUM") -> NewsSentimentResult:
        currencies = self._extract_currencies(headline)
        lex_score, lex_conf, tone = self._lexicon_score(headline)

        fb = self._score_with_finbert(headline)
        if fb is not None:
            score, conf = fb
            engine = "FINBERT"
        else:
            score, conf = lex_score, lex_conf
            engine = "LEXICON_FALLBACK"

        rec_action = "AVOID_NEW_TRADES" if str(impact).upper() == "HIGH" else "NORMAL"

        # Deep path: Gemma 3/4 only for HIGH impact macro events
        if str(impact).upper() == "HIGH":
            gemma_out = self._query_gemma_high_impact(headline)
            if isinstance(gemma_out, dict):
                g_tone = str(gemma_out.get("central_bank_tone", tone)).upper()
                if g_tone in ("HAWKISH", "DOVISH", "NEUTRAL"):
                    tone = g_tone
                if "sentiment_score" in gemma_out:
                    g_score = max(-1.0, min(1.0, float(gemma_out["sentiment_score"])))
                    score = round(0.55 * score + 0.45 * g_score, 4)
                g_act = str(gemma_out.get("recommended_action", rec_action)).upper()
                if g_act in ("NORMAL", "CAUTION", "AVOID_NEW_TRADES"):
                    rec_action = g_act
                engine = f"{engine}+GEMMA"

        label = "BULLISH" if score >= 0.15 else ("BEARISH" if score <= -0.15 else "NEUTRAL")
        return NewsSentimentResult(
            headline=headline,
            sentiment_label=label,
            sentiment_score=round(score, 4),
            confidence=round(conf, 4),
            central_bank_tone=tone,
            recommended_action=rec_action,
            engine_used=engine,
            affected_currencies=currencies,
        )

    def aggregate_symbol_sentiment(
        self,
        news_items: List[Any],
        symbols: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, str]]:
        """
        يجمع نتائج تحليل الأخبار لكل زوج عملات ويعيد:
          - labels: {symbol: "BULLISH"|"BEARISH"|"NEUTRAL"}
          - scores: {symbol: float in [-1.0, +1.0]}
          - tones:  {symbol: "HAWKISH"|"DOVISH"|"NEUTRAL"}
        """
        buckets: Dict[str, List[float]] = {}
        tones: Dict[str, str] = {}
        for item in news_items or []:
            headline = getattr(item, "headline", None) or (item.get("headline", "") if isinstance(item, dict) else str(item))
            impact = getattr(item, "impact", None) or (item.get("impact", "MEDIUM") if isinstance(item, dict) else "MEDIUM")
            rel_syms = getattr(item, "related_symbols", None) or (item.get("related_symbols", []) if isinstance(item, dict) else [])

            res = self.analyze_headline(headline, impact=impact)
            targets = list(rel_syms)
            if not targets and symbols:
                for sym in symbols:
                    if sym[:3] in res.affected_currencies or sym[3:6] in res.affected_currencies:
                        targets.append(sym)
            for sym in targets:
                # إذا كانت العملة المتأثرة هي عملة التسعير (quote) مثل USD في EURUSD نعكس الإشارة
                sign = 1.0
                if len(sym) >= 6 and sym[3:6] in res.affected_currencies and sym[:3] not in res.affected_currencies:
                    sign = -1.0
                buckets.setdefault(sym, []).append(res.sentiment_score * sign)
                if res.central_bank_tone != "NEUTRAL":
                    tones[sym] = res.central_bank_tone

        labels: Dict[str, str] = {}
        scores: Dict[str, float] = {}
        for sym, vals in buckets.items():
            avg = round(sum(vals) / len(vals), 4)
            scores[sym] = avg
            labels[sym] = "BULLISH" if avg >= 0.15 else ("BEARISH" if avg <= -0.15 else "NEUTRAL")
        return labels, scores, tones
