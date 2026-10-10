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
from config import SYMBOLS, STRATEGY, AGENTS


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
        self._learning_insights: dict = {}  # نتائج التعلم من LearningAgent

        # الاشتراك في أحداث الأخبار والتعلم
        self.bus.subscribe("news_alert",     self._on_news_alert)
        self.bus.subscribe("news_update",    self._on_news_update)
        self.bus.subscribe("learning_update",self._on_learning_update)

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
            for sym in symbols:
                self._news_blackout_symbols.add(sym)
            # تأمين USD-related symbols
            if not symbols or "USD" in [s[:3] for s in symbols]:
                self._news_blackout_symbols.update(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])

            self.stats["news_blackouts"] += 1
            await self.log("WARNING",
                f"🔇 حظر إشارات بسبب خبر HIGH: {data.get('headline','')[:50]} | "
                f"المتأثر: {symbols}")

            # رفع الحظر بعد 30 دقيقة تلقائياً
            asyncio.get_event_loop().call_later(
                1800, lambda: self._news_blackout_symbols.difference_update(symbols)
            )

    async def _on_news_update(self, msg):
        """استلام تحديث أخبار من NewsAgent"""
        data = msg.data
        self._market_sentiment = data.get("sentiment", {})

    async def _on_learning_update(self, msg):
        """استلام نتائج التعلم من LearningAgent — تعديل سلوك التحليل"""
        data = msg.data
        self._learning_insights = data
        # تحديث مصدر البيانات
        self.stats["data_source"] = self.mt5.data_source if hasattr(self.mt5, 'data_source') else 'UNKNOWN'
        await self.log("INFO",
            f"🎓 استلام نتائج تعلم: WinRate={data.get('win_rate', 0):.1f}% | "
            f"Best={data.get('best_regime')}")

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

        # 5. حفظ التحليل الحالي
        analysis = {
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
            # فحص حظر الأخبار
            if symbol in self._news_blackout_symbols:
                await self.log("INFO",
                    f"🔇 {symbol} في فترة حظر أخبار — تخطى الإشارة")
                return

            # تعديل الثقة بناءً على اتجاه السوق من الأخبار
            news_sentiment = self._market_sentiment.get(symbol, "NEUTRAL")
            if (voting.direction == "BUY" and news_sentiment == "BEARISH") or \
               (voting.direction == "SELL" and news_sentiment == "BULLISH"):
                # الأخبار تعاكس الإشارة — رفع عتبة الثقة
                if voting.confidence < 80:
                    await self.log("INFO",
                        f"📰 {symbol} إشارة تعاكس الأخبار ({news_sentiment}) — ثقة منخفضة {voting.confidence:.1f}%")
                    return

            # تأكيد الإطار الزمني الأطول (H4)
            mtf_ok = await self._check_higher_timeframe(symbol, voting.direction)
            if mtf_ok:
                await self._maybe_emit_signal(symbol, voting, fsm, iv, df)
            else:
                await self.log(
                    "INFO",
                    f"⏸ إشارة {voting.direction} {symbol} مفلترة — الإطار H4 معاكس"
                )

    async def _check_higher_timeframe(self, symbol: str, direction: str) -> bool:
        """
        تأكيد بسيط من الإطار الزمني الأطول (H4)
        يتحقق من اتجاه EMA على 50 شمعة H4
        """
        try:
            # نقبل الإشارة في وضع yfinance (لا H4 تفصيلي)
            if getattr(self.mt5, '_use_yfinance', False):
                return True
            if getattr(self.mt5, '_simulation_mode', False):
                return True

            import MetaTrader5 as mt5_lib
            df4h = self.mt5.get_ohlcv(symbol, timeframe=mt5_lib.TIMEFRAME_H4, bars=60)
            if df4h is None or len(df4h) < 55:
                return True
            iv4h = self.indicators.calculate(df4h, 0)
            if not iv4h.is_valid():
                return True
            if direction == "BUY"  and iv4h.close > iv4h.ema:
                return True
            if direction == "SELL" and iv4h.close < iv4h.ema:
                return True
            return False
        except Exception:
            return True

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

        # التحقق من السبريد
        if not self._check_spread(iv.spread):
            await self.log("WARNING", f"⚠️ سبريد مرتفع {symbol}: {iv.spread:.1f} نقطة — إلغاء الإشارة")
            return

        # تحديث التتبع
        self._signal_cooldown[symbol] = now
        self._last_signal_dir[symbol] = direction

        # حفظ في DB (نحتاج المعرّف لربط حكم المجلس بالصفقة ونتيجتها لاحقاً)
        signal_id = self._save_signal_to_db(symbol, direction, voting, fsm, iv)

        # ── مجلس الوكلاء في وضع الظل: يحكم ويُسجَّل ولا ينفّذ ─────────
        news_text  = self._market_sentiment.get(symbol, "NEUTRAL")
        news_score = {"BULLISH": 0.6, "BEARISH": -0.6}.get(news_text, 0.0)
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
                await self.log(
                    "WARNING",
                    f"⛔ فيتو المجلس — رُفضت {direction} {symbol} | "
                    f"({council.gate_reason()}) | "
                    f"bridge={shadow.get('bridge_stage') or 'approved'}",
                )
                return

        # نشر الإشارة
        await self.bus.emit_signal(
            sender         = self.name,
            symbol         = symbol,
            direction      = direction,
            voting_result  = voting.to_dict(),
            fsm_result     = fsm.to_dict(),
            news_score     = news_score,
            shadow         = shadow,
        )

        self.stats["signals_generated"] += 1
        self.stats["last_signal"] = {
            "symbol": symbol, "direction": direction,
            "time": datetime.utcnow().isoformat(),
            "confidence": voting.confidence,
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

            verdict = get_council().evaluate(
                symbol=symbol,
                direction=direction,
                vote_confidence=voting.confidence,
                fsm_regime=fsm.regime.value,
                features=[
                    voting.buy_score, voting.sell_score, voting.confidence,
                    iv.ema, iv.rsi, iv.macd, iv.adx, iv.atr,
                ],
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

    def _check_spread(self, spread: float) -> bool:
        return spread <= STRATEGY["max_spread_pips"]

    def _save_signal_to_db(self, symbol: str, direction: str,
                            voting: VotingResult, fsm: FSMResult, iv: IndicatorValues):
        """يحفظ الإشارة ويُرجع معرّفها (لربطها بحكم المجلس والصفقة)"""
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
