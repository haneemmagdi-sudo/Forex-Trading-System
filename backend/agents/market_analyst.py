"""
============================================================
market_analyst.py — الوكيل 1: محلل السوق
============================================================
يراقب السوق كل 5 ثوانٍ، يحلل 9 مؤشرات، يصوت عبر FSM
يستجيب لأخبار السوق من NewsAgent
عند توافر الشروط → يُرسل إشارة لـ Execution Agent
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
from loguru import logger

from agents.base_agent import BaseAgent
from core.mt5_connector import MT5Connector
from core.indicators import TechnicalIndicators, IndicatorValues
from core.fsm_engine import FSMEngine, FSMResult
from core.voting_engine import VotingEngine, VotingResult
from core.signal_bus import BusMessage
from models.database import SessionLocal, Signal as SignalModel, SignalDirection, FSMRegime
import config as _cfg
from config import SYMBOLS, STRATEGY, AGENTS
from core.reflection_memory import ReflectionMemoryReader
LEARNING_UPGRADES_2026 = getattr(_cfg, 'LEARNING_UPGRADES_2026', {})
COMM_REFLECTION_2026   = getattr(_cfg, 'COMMUNICATION_REFLECTION_2026', {})
FOUNDATION_MODELS_2026 = getattr(_cfg, 'FOUNDATION_MODELS_2026', {})


class MarketAnalystAgent(BaseAgent):
    """
    الوكيل الأول — محلل السوق
    ─────────────────────────────────────────
    ✅ يقرأ بيانات OHLCV من MT5 لكل زوج
    ✅ يحسب 9 مؤشرات فنية
    ✅ يشغّل محرك FSM لتحديد الـ Regime
    ✅ يشغّل مجلس التصويت
    ✅ عند إشارة قوية → يُرسل للـ Bus
    """

    def __init__(self, mt5: MT5Connector):
        super().__init__("MarketAnalyst", interval_sec=AGENTS["analyst_interval_sec"])
        self.mt5       = mt5
        self.indicators= TechnicalIndicators()
        self.fsm       = FSMEngine()
        self.voting    = VotingEngine()

        # آخر تحليل لكل زوج (للـ API)
        self.latest: Dict[str, dict] = {s: {} for s in SYMBOLS}

        # إحصائيات
        self.stats.update({
            "signals_generated": 0,
            "last_signal":       None,
            "current_regimes":   {},
            "data_source":       mt5.data_source if hasattr(mt5, 'data_source') else 'UNKNOWN',
            "news_blackouts":    0,
            "council_vetoes":    0,
        })

        # ضد التكرار: آخر إشارة لكل زوج
        self._last_signal_dir: Dict[str, str] = {}
        self._signal_cooldown: Dict[str, float] = {}

        # بيانات الأخبار من NewsAgent
        self._news_blackout_symbols: set = set()  # أزواج في فترة حظر الأخبار
        self._market_sentiment: Dict[str, str] = {}  # اتجاه السوق من الأخبار
        self._market_sentiment_scores: Dict[str, float] = {}  # درجات FinBERT/Gemma المستمرة [-1..+1]
        self._timesfm_service = self._init_timesfm_service()
        self._learning_insights: dict = {}  # نتائج التعلم من LearningAgent
        self._regime_confidence_boost: Dict[str, float] = {}  # تعديلات الثقة التكيفية
        self._recent_trade_history: list = []  # ذاكرة الصفقات الأخيرة
        self.reflection_reader = ReflectionMemoryReader(
            lookback_days=COMM_REFLECTION_2026.get('reflection_lookback_days', 14),
            min_samples=COMM_REFLECTION_2026.get('reflection_min_samples', 4),
            cooldown_consecutive_losses=COMM_REFLECTION_2026.get('reflection_cooldown_consecutive_losses', 4),
            max_conf_penalty=COMM_REFLECTION_2026.get('reflection_max_conf_penalty', 15.0),
            max_omega_penalty=COMM_REFLECTION_2026.get('reflection_max_omega_penalty', 0.08),
            cache_ttl_sec=COMM_REFLECTION_2026.get('reflection_cache_ttl_sec', 30.0),
        )

        # الاشتراك في أحداث الأخبار والتعلم والتواصل البيني
        self.bus.subscribe("news_alert",          self._on_news_alert)
        self.bus.subscribe("news_update",         self._on_news_update)
        self.bus.subscribe("learning_update",     self._on_learning_update)
        self.bus.subscribe("meta_learning_update",self._on_meta_learning_update)
        self.bus.subscribe("trade_closed",        self._on_trade_closed)
        self.bus.subscribe("champion_rollback",   self._on_champion_rollback)

    async def run_cycle(self):
        """دورة التحليل — تُشغَّل كل N ثانية"""
        for symbol in SYMBOLS:
            try:
                await self._analyze_symbol(symbol)
            except Exception as e:
                await self.log("ERROR", f"خطأ في تحليل {symbol}: {e}")
            await asyncio.sleep(0.3)  # فترة بسيطة بين الأزواج

    async def _on_news_alert(self, msg):
        """استلام تنبيه خبر مهم من NewsAgent"""
        data = msg.data
        symbols = data.get("related_symbols", [])
        impact  = data.get("impact", "LOW")
        recommendation = data.get("recommendation", "")

        if impact == "HIGH" and recommendation == "AVOID_NEW_TRADES":
            affected = set(symbols)
            # تأمين USD-related symbols
            if not symbols or "USD" in [s[:3] for s in symbols]:
                affected.update(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])
            self._news_blackout_symbols.update(affected)

            self.stats["news_blackouts"] += 1
            await self.log("WARNING",
                f"🔇 حظر إشارات بسبب خبر HIGH: {data.get('headline','')[:50]} | "
                f"المتأثر: {sorted(affected)}")

            # رفع الحظر عن جميع الأزواج المتأثرة بعد 30 دقيقة تلقائياً (P0 fix)
            asyncio.get_event_loop().call_later(
                1800, lambda s=affected: self._news_blackout_symbols.difference_update(s)
            )

    @staticmethod
    def _init_timesfm_service():
        try:
            root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if root_path not in sys.path:
                sys.path.append(root_path)
            from ml_models.timesfm_extractor import CachedTimesFMService
            return CachedTimesFMService(
                repo_id=FOUNDATION_MODELS_2026.get("timesfm_repo_id", "google/timesfm-2.5-200m-pytorch"),
                cache_ttl_sec=FOUNDATION_MODELS_2026.get("timesfm_cache_ttl_sec", 300.0),
                enabled=FOUNDATION_MODELS_2026.get("timesfm_enabled", True),
                allow_non_commercial=FOUNDATION_MODELS_2026.get("timesfm_allow_non_commercial", False),
            )
        except Exception:
            return None

    async def _on_news_update(self, msg):
        """استلام تحديث أخبار من NewsAgent (يشمل درجات FinBERT/Gemma المستمرة)"""
        data = msg.data
        self._market_sentiment = data.get("sentiment", {})
        if "sentiment_scores" in data:
            self._market_sentiment_scores = dict(data.get("sentiment_scores") or {})

    async def _on_learning_update(self, msg):
        """استلام نتائج التعلم من LearningAgent — تعديل سلوك التحليل"""
        data = msg.data
        self._learning_insights = data
        self.stats["data_source"] = self.mt5.data_source if hasattr(self.mt5, 'data_source') else 'UNKNOWN'
        await self.log("INFO",
            f"🎓 استلام نتائج تعلم: WinRate={data.get('win_rate', 0):.1f}% | "
            f"Best={data.get('best_regime')}")

    async def _on_meta_learning_update(self, msg):
        """استلام توجيهات التحسين الذاتي والتعديل الفوري للأوزان والعتبات"""
        data = msg.data
        threshold_shifts = data.get("regime_threshold_shifts", {})
        if threshold_shifts:
            self._regime_confidence_boost.update(threshold_shifts)
            await self.log("INFO", f"⚙️ تعديل عتبات الثقة التكيفية حسب الـ Regimes: {self._regime_confidence_boost}")

    async def _on_trade_closed(self, msg):
        """استلام تقرير إغلاق صفقة من MonitorAgent للتغذية الراجعة الفورية"""
        trade_data = msg.data
        self._recent_trade_history.append(trade_data)
        if len(self._recent_trade_history) > 20:
            self._recent_trade_history.pop(0)
        self.reflection_reader.invalidate()

    async def _on_champion_rollback(self, msg):
        """استلام إشعار تراجع تلقائي للأوزان من LearningAgent"""
        data = msg.data
        await self.log(
            "WARNING",
            f"⏪ إشعار تراجع تلقائي للأوزان إلى Champion v{data.get('version')}: {data.get('reason')}",
        )

    async def _analyze_symbol(self, symbol: str):
        # 1. قراءة البيانات
        df = self.mt5.get_ohlcv(symbol, bars=200)
        if df is None or len(df) < 60:
            return

        tick = self.mt5.get_tick(symbol)
        spread = tick["spread"] if tick else 99

        # 2. حساب المؤشرات
        iv: IndicatorValues = self.indicators.calculate(df, spread)
        if not iv.is_valid():
            return

        # 3. FSM Regime
        fsm: FSMResult = self.fsm.detect(iv)

        # 4. التصويت
        voting: VotingResult = self.voting.vote(iv, fsm)

        # 4b. استخراج ميزات TimesFM 2.5 من الكاش غير المعطّل (Zero-Latency Guard)
        timesfm_feats = (
            self._timesfm_service.get_features(symbol, df)
            if self._timesfm_service is not None
            else {"timesfm_alpha_delta": 0.0, "forecast_momentum_slope": 0.0, "forecast_variance_risk": 0.0, "is_valid": False}
        )
        news_sent_score = float(self._market_sentiment_scores.get(symbol, 0.0) or 0.0)

        # 5. حفظ التحليل الحالي
        analysis = {
            "timesfm": timesfm_feats,
            "news_sentiment_score": news_sent_score,
            "symbol":    symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "price":     iv.close,
            "spread":    spread,
            "fsm":       fsm.to_dict(),
            "voting":    voting.to_dict(),
            "indicators": {
                "ema":      round(iv.ema, 5),
                "rsi":      round(iv.rsi, 2),
                "macd":     round(iv.macd, 6),
                "adx":      round(iv.adx, 2),
                "atr":      round(iv.atr, 5),
                "stoch_k":  round(iv.stoch_k, 2),
                "bb_upper": round(iv.bb_upper, 5),
                "bb_lower": round(iv.bb_lower, 5),
                "ha_bull":  iv.ha_bullish,
                "tenkan":   round(iv.tenkan, 5),
                "kijun":    round(iv.kijun, 5),
            },
        }
        self.latest[symbol] = analysis
        self.stats["current_regimes"][symbol] = fsm.regime.value

        # 6. نشر التحليل للـ Dashboard
        await self.bus.publish(BusMessage(
            topic  = "analysis",
            sender = self.name,
            data   = analysis,
        ))

        # 7. هل يجب إرسال إشارة؟ (مع تأكيد متعدد الأطر الزمنية)
        if voting.signal_strong and fsm.trade_allowed:
            # فحص حظر الأخبار (مع تسجيل الإشارة المرفوضة في DB للقياس)
            if symbol in self._news_blackout_symbols:
                self._save_signal_to_db(symbol, voting.direction, voting, fsm, iv, rejection_reason="NEWS_BLACKOUT")
                await self.log("INFO",
                    f"🔇 {symbol} في فترة حظر أخبار — تخطى الإشارة (سُجلت كـ NEWS_BLACKOUT)")
                return

            # تعديل الثقة بناءً على اتجاه السوق من الأخبار
            news_sentiment = self._market_sentiment.get(symbol, "NEUTRAL")
            if (voting.direction == "BUY" and news_sentiment == "BEARISH") or \
               (voting.direction == "SELL" and news_sentiment == "BULLISH"):
                # الأخبار تعاكس الإشارة — رفع عتبة الثقة
                if voting.confidence < 80:
                    self._save_signal_to_db(symbol, voting.direction, voting, fsm, iv, rejection_reason=f"NEWS_CONTRADICTION_{news_sentiment}")
                    await self.log("INFO",
                        f"📰 {symbol} إشارة تعاكس الأخبار ({news_sentiment}) — ثقة منخفضة {voting.confidence:.1f}%")
                    return

            # 2026 Batch 2: استشارة ذاكرة التأمّل (AgentReflection) + التشديد التكيفي من LearningAgent
            refl_adv = self.reflection_reader.evaluate_pair_regime(symbol, fsm.regime.value)
            if refl_adv.temporary_cooldown:
                self._save_signal_to_db(
                    symbol, voting.direction, voting, fsm, iv,
                    rejection_reason="REFLECTION_COOLDOWN",
                )
                await self.log(
                    "WARNING",
                    f"🧠⛔ {symbol} ({fsm.regime.value}) محجوب بتبريد ذاكرة التأمّل: {refl_adv.summary}",
                )
                return

            regime_boost = float(self._regime_confidence_boost.get(fsm.regime.value, 0.0) or 0.0)
            timesfm_unc_pen = (
                5.0 if (timesfm_feats.get('is_valid') and float(timesfm_feats.get('forecast_variance_risk', 0.0)) > float(FOUNDATION_MODELS_2026.get('timesfm_high_uncertainty_var', 5e-5))) else 0.0
            )
            total_boost = regime_boost + float(refl_adv.confidence_penalty or 0.0) + timesfm_unc_pen
            if total_boost > 0.0:
                base_min_conf = float(LEARNING_UPGRADES_2026.get("min_signal_confidence", 55.0))
                effective_min_conf = base_min_conf + total_boost
                if voting.confidence < effective_min_conf:
                    self._save_signal_to_db(
                        symbol, voting.direction, voting, fsm, iv,
                        rejection_reason=f"ADAPTIVE_CONFIDENCE_FILTER_{effective_min_conf:.0f}",
                    )
                    await self.log(
                        "INFO",
                        f"🛡️ {symbol} مفلترة بالتشديد التكيفي/التأمّل ({fsm.regime.value}): "
                        f"ثقة {voting.confidence:.1f}% < {effective_min_conf:.1f}% ({refl_adv.summary})",
                    )
                    return

            # تأكيد الإطار الزمني الأطول (H4)
            mtf_ok = await self._check_higher_timeframe(symbol, voting.direction)
            if mtf_ok:
                await self._maybe_emit_signal(symbol, voting, fsm, iv, df)
            else:
                self._save_signal_to_db(symbol, voting.direction, voting, fsm, iv, rejection_reason="H4_COUNTER_TREND")
                await self.log(
                    "INFO",
                    f"⏸ إشارة {voting.direction} {symbol} مفلترة — الإطار H4 معاكس (سُجلت كـ H4_COUNTER_TREND)"
                )

    async def _check_higher_timeframe(self, symbol: str, direction: str) -> bool:
        """
        تأكيد بسيط من الإطار الزمني الأطول (H4)
        يتحقق من اتجاه EMA على 50 شمعة H4

        IMPROVEMENT_PLAN §0: البوابات الحامية fail-closed.
        عند غياب البيانات أو حدوث استثناء، يُرفض الأمر لحماية رأس المال بدلاً من التمرير.
        """
        try:
            # وضع yfinance: نتحقق من اتجاه الإطار الأكبر عبر البيانات المتاحة
            if getattr(self.mt5, '_use_yfinance', False):
                df = self.mt5.get_ohlcv(symbol, bars=200)
                if df is None or len(df) < 50:
                    await self.log("WARNING", f"⚠️ H4 check failed for {symbol}: insufficient data (fail-closed)")
                    return False
                iv = self.indicators.calculate(df, 0)
                if not iv.is_valid():
                    return False
                if direction == "BUY" and iv.close > iv.ema:
                    return True
                if direction == "SELL" and iv.close < iv.ema:
                    return True
                return False

            import MetaTrader5 as mt5_lib
            df4h = self.mt5.get_ohlcv(symbol, timeframe=mt5_lib.TIMEFRAME_H4, bars=60)
            if df4h is None or len(df4h) < 55:
                await self.log("WARNING", f"⚠️ H4 filter fail-closed for {symbol}: insufficient bars ({0 if df4h is None else len(df4h)} < 55)")
                return False
            iv4h = self.indicators.calculate(df4h, 0)
            if not iv4h.is_valid():
                await self.log("WARNING", f"⚠️ H4 filter fail-closed for {symbol}: invalid indicator values")
                return False
            if direction == "BUY"  and iv4h.close > iv4h.ema:
                return True
            if direction == "SELL" and iv4h.close < iv4h.ema:
                return True
            return False
        except Exception as exc:
            await self.log("ERROR", f"❌ H4 filter exception for {symbol} (fail-closed): {exc}")
            return False

    async def _maybe_emit_signal(self, symbol: str, voting: VotingResult,
                                  fsm: FSMResult, iv: IndicatorValues, df=None):
        """إرسال إشارة مع منع التكرار"""
        direction = voting.direction

        # تجاهل WEAK و NO_TRADE
        if direction not in ("BUY", "SELL"):
            return

        # منع الإشارة المكررة في 60 ثانية
        now = datetime.utcnow().timestamp()
        last_time = self._signal_cooldown.get(symbol, 0)
        last_dir  = self._last_signal_dir.get(symbol, "")
        if direction == last_dir and (now - last_time) < 60:
            return

        # التحقق من السبريد (بحد مخصص لكل رمز)
        if not self._check_spread(iv.spread, symbol):
            self._save_signal_to_db(symbol, direction, voting, fsm, iv, rejection_reason=f"SPREAD_TOO_HIGH_{iv.spread:.1f}")
            await self.log("WARNING", f"⚠️ سبريد مرتفع {symbol}: {iv.spread:.1f} نقطة — إلغاء الإشارة (سُجلت كـ SPREAD_TOO_HIGH)")
            return

        # تحديث التتبع
        self._signal_cooldown[symbol] = now
        self._last_signal_dir[symbol] = direction

        # حفظ في DB (نحتاج المعرّف لربط حكم المجلس بالصفقة ونتيجتها لاحقاً)
        signal_id = self._save_signal_to_db(symbol, direction, voting, fsm, iv)

        # ── مجلس الوكلاء في وضع الظل: يحكم ويُسجَّل ولا ينفّذ ─────────
        news_text  = self._market_sentiment.get(symbol, "NEUTRAL")
        news_score = float(self._market_sentiment_scores.get(symbol, {"BULLISH": 0.6, "BEARISH": -0.6}.get(news_text, 0.0)))
        shadow     = self._run_shadow_council(
            symbol=symbol, direction=direction, voting=voting, fsm=fsm,
            iv=iv, df=df, news_text=news_text, signal_id=signal_id,
        )

        # ── الفيتو الفعلي: مقفول ببوابة إثبات ولا يعمل في وضع shadow ──
        if shadow.get("council_would_block") and shadow.get("available"):
            from core.agent_council import get_council
            council = get_council()
            if council.filter_enabled():
                self.stats["council_vetoes"] += 1
                try:
                    db = SessionLocal()
                    sig_to_upd = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
                    if sig_to_upd:
                        sig_to_upd.rejection_reason = "COUNCIL_VETO"
                        db.commit()
                    db.close()
                except Exception:
                    pass
                await self.log(
                    "WARNING",
                    f"⛔ فيتو المجلس — رُفضت {direction} {symbol} | "
                    f"({council.gate_reason()}) | "
                    f"bridge={shadow.get('bridge_stage') or 'approved'}",
                )
                return

        # ── حساب التلاقي المؤسسي والسيولة ─────────────────────────────
        confluence = self._calculate_confluence_metrics(symbol, iv, direction, df)

        # نشر الإشارة مع مصفوفة التلاقي ومعرّف الإشارة signal_id
        await self.bus.emit_signal(
            sender         = self.name,
            symbol         = symbol,
            direction      = direction,
            voting_result  = voting.to_dict(),
            fsm_result     = fsm.to_dict(),
            news_score     = news_score,
            shadow         = shadow,
            confluence     = confluence,
            signal_id      = signal_id,
        )

        self.stats["signals_generated"] += 1
        self.stats["last_signal"] = {
            "symbol": symbol, "direction": direction,
            "time": datetime.utcnow().isoformat(),
            "confidence": voting.confidence,
            "confluence_score": confluence.get("confluence_score", 0),
        }

        await self.log(
            "INFO",
            f"📡 إشارة قوية: {direction} {symbol} | "
            f"Regime:{fsm.regime.value} | Score:{voting.buy_score:.2f}/{voting.sell_score:.2f} | "
            f"Confidence:{voting.confidence:.1f}%",
        )

    def _run_shadow_council(self, symbol: str, direction: str, voting: VotingResult,
                             fsm: FSMResult, iv: IndicatorValues, df, news_text: str,
                             signal_id) -> dict:
        """
        يشغّل مجلس الوكلاء (لوحة + إجماع + HMM/OrderFlow/MAD) على إشارة مرشّحة.
        وضع الظل: النتيجة تُسجَّل وتُرفق بالحمولة للقياس فقط — لا تؤثر على التنفيذ.
        """
        try:
            from core.agent_council import get_council

            if df is None or len(df) < 30:
                return {"available": False, "reason": "insufficient price history"}

            # P3: نفس متجه الخصائص (ترتيب التدريب في LearningAgent) يُرفق بالنتيجة ليستعمله مسار التنفيذ
            ml_features = [
                voting.buy_score, voting.sell_score, voting.confidence,
                iv.ema, iv.rsi, iv.macd, iv.adx, iv.atr,
            ]
            verdict = get_council().evaluate(
                symbol=symbol,
                direction=direction,
                vote_confidence=voting.confidence,
                fsm_regime=fsm.regime.value,
                features=ml_features,
                price_series={
                    "opens":   df["open"].tolist(),
                    "highs":   df["high"].tolist(),
                    "lows":    df["low"].tolist(),
                    "closes":  df["close"].tolist(),
                    "volumes": df["volume"].tolist() if "volume" in df.columns else [100.0] * len(df),
                },
                technical_indicators={
                    "ema": iv.ema, "rsi": iv.rsi, "macd": iv.macd,
                    "adx": iv.adx, "atr": iv.atr, "spread": iv.spread,
                },
                news_sentiment=news_text,
                signal_id=signal_id,
            )
            verdict["ml_features"] = ml_features

            if verdict.get("council_would_block"):
                logger.info(
                    f"[ShadowCouncil] {symbol} {direction}: المجلس كان سيمنع "
                    f"(consensus={verdict.get('consensus_action')} "
                    f"score={verdict.get('consensus_score')} "
                    f"bridge={verdict.get('bridge_stage') or 'approved'}) — تسجيل فقط"
                )
            return verdict
        except Exception as exc:
            # المجلس لا يجوز أن يؤثر على التداول بأي حال
            logger.warning(f"[ShadowCouncil] تعذّر تقييم {symbol}: {exc}")
            return {"available": False, "error": str(exc)}

    def _calculate_confluence_metrics(self, symbol: str, iv: IndicatorValues, direction: str, df) -> dict:
        """
        حساب مصفوفة التلاقي المؤسسي متعددة العوامل:
        1. اتساق الاتجاه (EMA, Heikin-Ashi, Tenkan/Kijun)
        2. الزخم (RSI corridor, MACD)
        3. هيكل السوق والسيولة (SMC FVG & Order Blocks)
        4. نسبة تمدد التقلب (ATR Expansion)
        """
        score = 50.0  # Base
        factors = []

        # 1. اتجاه السعر وهيكل SMC
        if direction == "BUY":
            if iv.close > iv.ema:
                score += 10.0; factors.append("Price > 50-EMA")
            if iv.ha_bullish:
                score += 10.0; factors.append("Heikin-Ashi Bullish")
            if iv.tenkan > iv.kijun:
                score += 10.0; factors.append("Tenkan > Kijun Cross")
            if getattr(iv, 'smc_bullish_ob', False):
                score += 10.0; factors.append("Bullish Order Block")
            if getattr(iv, 'smc_bullish_fvg', False):
                score += 10.0; factors.append("Bullish FVG")
        else:
            if iv.close < iv.ema:
                score += 10.0; factors.append("Price < 50-EMA")
            if not iv.ha_bullish:
                score += 10.0; factors.append("Heikin-Ashi Bearish")
            if iv.tenkan < iv.kijun:
                score += 10.0; factors.append("Tenkan < Kijun Cross")
            if getattr(iv, 'smc_bearish_ob', False):
                score += 10.0; factors.append("Bearish Order Block")
            if getattr(iv, 'smc_bearish_fvg', False):
                score += 10.0; factors.append("Bearish FVG")

        # 2. الزخم
        if direction == "BUY" and (45.0 <= iv.rsi <= 68.0):
            score += 10.0; factors.append("RSI in Bullish Expansion Corridor")
        elif direction == "SELL" and (32.0 <= iv.rsi <= 55.0):
            score += 10.0; factors.append("RSI in Bearish Momentum Corridor")

        # 3. تمدد التقلب
        # IMPROVEMENT_PLAN §0: عتبات ATR المطلقة (0.0020/0.0006) خاطئة لأزواج الين وXAUUSD.
        # الحل: نسبة ATR/Price (نسبية) كمقياس موحد عبر كل الرموز.
        vol_regime = "NORMAL"
        atr_ratio = (iv.atr / iv.close) if iv.close > 0 else 0.0
        if atr_ratio > 0.0012:    # > 0.12% من السعر → تقلب مرتفع (يعمل لكل الرموز)
            vol_regime = "EXPANSION"
        elif atr_ratio < 0.0003:  # < 0.03% من السعر → تقلب منخفض جداً
            vol_regime = "COMPRESSION"

        confluence_score = round(max(0.0, min(100.0, score)), 1)
        return {
            "confluence_score": confluence_score,
            "volatility_regime": vol_regime,
            "supporting_factors": factors,
            "smc": {
                "bull_ob": getattr(iv, 'smc_bullish_ob', False),
                "bear_ob": getattr(iv, 'smc_bearish_ob', False),
                "bull_fvg": getattr(iv, 'smc_bullish_fvg', False),
                "bear_fvg": getattr(iv, 'smc_bearish_fvg', False),
            }
        }

    def _check_spread(self, spread: float, symbol: str = "") -> bool:
        """
        IMPROVEMENT_PLAN §0: فحص السبريد لكل رمز بحد مخصص.
        بدلاً من حد عالمي 25 نقطة (متساهل جداً) نستخدم جدول لكل رمز.
        """
        symbol_limits = STRATEGY.get("symbol_spread_limits", {})
        max_spread = symbol_limits.get(symbol, STRATEGY.get("max_spread_pips", 4.0))
        return spread <= max_spread

    def _save_signal_to_db(self, symbol: str, direction: str,
                            voting: VotingResult, fsm: FSMResult, iv: IndicatorValues,
                            rejection_reason: str = None):
        """
        يحفظ الإشارة ويُرجع معرّفها (لربطها بحكم المجلس والصفقة).
        IMPROVEMENT_PLAN §2: تسجيل كل إشارة مرشّحة، المنفَّذة والمرفوضة، مع خصائصها كاملة.
        """
        db = None
        try:
            db = SessionLocal()
            sig = SignalModel(
                symbol      = symbol,
                direction   = SignalDirection(direction),
                fsm_regime  = FSMRegime(fsm.regime.value),
                buy_score   = voting.buy_score,
                sell_score  = voting.sell_score,
                total_weight= voting.total_weight,
                confidence  = voting.confidence,
                rejection_reason = rejection_reason,
                ema_value   = iv.ema,
                rsi_value   = iv.rsi,
                macd_value  = iv.macd,
                adx_value   = iv.adx,
                atr_value   = iv.atr,
                price       = iv.close,
            )
            db.add(sig)
            db.commit()
            return sig.id
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الإشارة: {e}")
            return None
        finally:
            if db:
                db.close()
