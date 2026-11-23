"""
============================================================
learning_agent.py — الوكيل 4: التعلم المستمر (محسّن v2)
============================================================
يحلل سجل الصفقات → يكتشف الأنماط → يحسّن الأوزان
يدرب GradientBoosting + RandomForest → يحفظ النموذج على القرص
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger

from agents.base_agent import BaseAgent
from core.signal_bus import BusMessage
from models.database import (
    SessionLocal, Trade, Signal as SignalModel, TradeStatus, LearningLog,
    AgentReflection, ShadowDecision,
)
import config as _cfg
from config import AGENTS, META_MODEL_PATH, META_GATE
from core.champion_challenger import ChampionChallengerManager, ExponentialAttributionBandit
LEARNING_UPGRADES_2026 = getattr(_cfg, 'LEARNING_UPGRADES_2026', {})

# مسار حفظ النموذج
MODEL_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH      = os.path.join(MODEL_DIR, "ml_model.pkl")
SCALER_PATH     = os.path.join(MODEL_DIR, "ml_scaler.pkl")
# META_MODEL_PATH: المصدر الوحيد الآن backend/config.py (P3)
os.makedirs(MODEL_DIR, exist_ok=True)


class LearningAgent(BaseAgent):
    """
    الوكيل الرابع — التعلم المستمر من الأخطاء (v2)
    ────────────────────────────────────────────────────
    ✅ يحلل سجل الصفقات كل 60 دقيقة
    ✅ يكتشف أي Regime أعطى أفضل نتائج
    ✅ يعدّل أوزان الـ Voting تلقائياً
    ✅ يدرّب GradientBoosting + RandomForest على البيانات الحقيقية
    ✅ يحفظ النموذج المدرب على القرص (يبقى بين إعادات التشغيل)
    ✅ يحفظ تقرير كامل في DB
    ✅ ينشر نتائج التعلم عبر Signal Bus
    ✅ يبدأ بـ 5 صفقات فقط (بدل 20)
    """

    def __init__(self, voting_engine=None):
        super().__init__(
            "LearningAgent",
            interval_sec=AGENTS["learning_interval_min"] * 60
        )
        self.voting_engine   = voting_engine
        self.iteration_count = 0
        self.min_trades      = max(5, AGENTS.get("min_trades_to_learn", 5))  # بدأ بـ 5
        self._model          = None
        self._scaler         = None
        self._meta_model     = None
        self._model_accuracy = 0.0

        # حوكمة الأوزان والسلوك: Champion vs Challenger مع تراجع تلقائي (2026)
        self.champion_manager = ChampionChallengerManager(
            state_path=os.path.join(MODEL_DIR, "champion_weights_state.json"),
            probation_trades=LEARNING_UPGRADES_2026.get("probation_trades", 10),
            max_consecutive_losses=LEARNING_UPGRADES_2026.get("max_consecutive_losses_rollback", 4),
            max_weight_step=LEARNING_UPGRADES_2026.get("max_weight_step", 0.25),
            rollback_cooldown_trades=LEARNING_UPGRADES_2026.get("rollback_cooldown_trades", 5),
            wr_tolerance=LEARNING_UPGRADES_2026.get("wr_tolerance", 0.05),
        )
        if self.voting_engine is not None:
            self.voting_engine.update_weights(self.champion_manager.active_weights)

        # محاولة تحميل نموذج محفوظ
        self._load_model()

        self.stats.update({
            "iterations":            0,
            "last_analysis":         None,
            "total_trades_analyzed": 0,
            "best_regime":           None,
            "worst_regime":          None,
            "current_win_rate":      None,
            "weight_updates":        0,
            "last_weights":          {},
            "model_accuracy":        self._model_accuracy,
            "model_trained":         self._model is not None,
            "model_path":            MODEL_PATH,
            "online_reflections":    0,
            "regime_streaks":        {},
            "champion_version":      self.champion_manager.champion.version,
            "rollbacks_count":       self.champion_manager.rollbacks_count,
            "promotions_count":      self.champion_manager.promotions_count,
        })

        # الاشتراك في أحداث التنفيذ والإغلاق للتعلم اللحظي (Online Meta-Learning)
        self.bus.subscribe("trade_closed",        self._on_trade_closed_event)
        self.bus.subscribe("execution_telemetry", self._on_execution_telemetry)

    async def _on_trade_closed_event(self, msg: BusMessage):
        """تغذية راجعة فورية عند إغلاق كل صفقة: كتابة درس + تحديث ديناميكي للمحددات"""
        data = msg.data
        ticket = data.get("ticket")
        profit = float(data.get("profit", 0.0))
        regime = data.get("regime", "UNKNOWN")
        symbol = data.get("symbol", "UNKNOWN")

        # 1. كتابة التأمل الفوري في قاعدة البيانات
        new_reflections = self._write_reflections()
        if new_reflections:
            self.stats["online_reflections"] = self.stats.get("online_reflections", 0) + new_reflections

        # 2. تحليل سبب النتيجة الحتمي
        cause = self._classify_outcome_cause(data)
        await self.log("INFO", f"🔬 تحليل نتيجة #{ticket} {symbol} ({profit:+.2f}$): {cause}")

        # 3. تتبع المتتاليات للـ Regimes لتعديل العتبات تلقائياً (Self-Adapting Gates)
        streaks = self.stats.setdefault("regime_streaks", {})
        current_streak = streaks.get(regime, 0)
        if profit > 0:
            streaks[regime] = max(1, current_streak + 1 if current_streak > 0 else 1)
        else:
            streaks[regime] = min(-1, current_streak - 1 if current_streak < 0 else -1)

        # إذا خسرت صفقتان متتاليتان في نفس الـ Regime، نرفع عتبة الثقة فوراً لحماية رأس المال
        threshold_shifts = {}
        if streaks[regime] <= -2:
            threshold_shifts[regime] = 5.0  # رفع عتبة الثقة 5% في هذا النظام
            await self.log("WARNING", f"🛡️ حماية تكيفية: تكرار الخسائر في {regime} ({streaks[regime]}) → رفع عتبة الثقة +5%")
        elif streaks[regime] >= 2:
            threshold_shifts[regime] = 0.0  # إعادة العتبة لطبيعتها عند استقرار الأرباح

        # 3b. تقييم Champion/Challenger وتفعيل التراجع التلقائي (Auto-Rollback) عند تدهور الأداء
        cc_res = self.champion_manager.record_trade_outcome(profit)
        self.stats["champion_version"] = self.champion_manager.champion.version
        self.stats["rollbacks_count"]  = self.champion_manager.rollbacks_count
        self.stats["promotions_count"] = self.champion_manager.promotions_count
        if cc_res["action"] == "AUTO_ROLLBACK":
            if self.voting_engine is not None:
                self.voting_engine.update_weights(cc_res["weights"])
            await self.log(
                "WARNING",
                f"⏪ تراجع تلقائي لأوزان Champion v{cc_res['version']}: {cc_res['reason']}",
            )
            await self.bus.publish(BusMessage(
                topic="champion_rollback",
                sender=self.name,
                priority=1,
                data={
                    "version": cc_res["version"],
                    "reason": cc_res["reason"],
                    "weights": cc_res["weights"],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            ))
        elif cc_res["action"] == "PROMOTED":
            await self.log(
                "SUCCESS",
                f"🏆 ترقية أوزان Challenger إلى Champion v{cc_res['version']}: {cc_res['reason']}",
            )

        # 4. بث تحديث التعلم الفوقي (Meta-Learning) لباقي الوكلاء
        await self.bus.publish(BusMessage(
            topic  = "meta_learning_update",
            sender = self.name,
            data   = {
                "last_closed_ticket": ticket,
                "profit": profit,
                "regime": regime,
                "outcome_cause": cause,
                "regime_threshold_shifts": threshold_shifts,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ))

        # 5. تحديث ذاكرة RAG التكيفية للمجلس المؤسسي وإغلاق حلقة التعلم (IMPROVEMENT_PLAN §1)
        if ticket:
            try:
                import sys, os
                root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                if root_path not in sys.path:
                    sys.path.append(root_path)
                from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
                recorder = TradeOutcomeRecorder()
                outcome_label = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "BE")
                from core.mt5_connector import MT5Connector
                pip_size = MT5Connector.get_pip_size(symbol)
                entry_p = float(data.get("entry_price") or 0.0)
                close_p = float(data.get("close_price") or 0.0)
                direction = data.get("direction", "BUY")
                if entry_p > 0 and close_p > 0:
                    pnl_pips = (close_p - entry_p) / pip_size if direction == "BUY" else (entry_p - close_p) / pip_size
                else:
                    pnl_pips = profit / 10.0
                await recorder.update_outcome_by_ticket(
                    ticket=ticket,
                    pnl_pips=round(pnl_pips, 2),
                    outcome=outcome_label,
                    spread_cost=float(data.get("spread_cost") or 0.0),
                    commission=float(data.get("commission") or 0.0),
                    swap=float(data.get("swap") or 0.0),
                    mae_pips=float(data.get("mae_pips") or 0.0),
                    mfe_pips=float(data.get("mfe_pips") or 0.0),
                )
            except Exception as e:
                logger.debug(f"Note updating adaptive trade journal: {e}")

    async def _on_execution_telemetry(self, msg: BusMessage):
        """مراقبة كفاءة التنفيذ وسرعة البوابة من ExecutionAgent"""
        data = msg.data
        latency = data.get("latency_ms", 0)
        if latency > 1500:
            await self.log("WARNING", f"⏱️ تنبيه زمن التنفيذ: {data.get('symbol')} استغرق {latency}ms")

    def _classify_outcome_cause(self, trade_data: dict) -> str:
        """تشخيص سببي مؤسسي لنتيجة الصفقة (Win/Loss Attribution)"""
        profit = float(trade_data.get("profit", 0.0))
        duration = float(trade_data.get("duration_sec", 0.0))
        regime = trade_data.get("regime", "UNKNOWN")

        if profit > 0:
            if duration > 3600:
                return "MOMENTUM_EXPANSION_TARGET_REACHED (ربح زخم ممتد)"
            return "TACTICAL_PROFIT_TAKE (حجز أرباح تكتيكي سريع)"
        else:
            if duration < 120 and abs(profit) < 2.0:
                return "SPREAD_SLIPPAGE_DRAG (تراجع مبكر بفعل السبريد)"
            if regime in ("CHAOS", "HIGH_VOL_RANGE"):
                return "VOLATILITY_CHURN_IN_RANGE (تذبذب عشوائي في نطاق متقلب)"
            return "STRUCTURAL_REVERSAL_STOP_HIT (ضرب وقف الخسارة عند انعكاس الهيكل)"
    async def run_cycle(self):
        """دورة التعلم الكاملة"""
        await self.log("INFO", "🧠 بدء دورة التعلم من البيانات الحقيقية...")
        try:
            analysis = self._analyze_history()
            if analysis is None:
                await self.log("INFO", f"📊 خطأ في تحليل التاريخ")
                return

            new_weights = {}

            if analysis["total_trades"] >= self.min_trades:
                # تحديث الأوزان عبر بوابة Champion/Challenger (مع سقف خطوة وتراجع تلقائي)
                candidate_weights = self._compute_weight_adjustments(analysis)
                if candidate_weights and self.voting_engine:
                    cur_exp = (analysis.get("total_profit", 0.0) / max(1, analysis["total_trades"]))
                    accepted, cc_reason, applied_weights = self.champion_manager.propose_challenger(
                        candidate_weights,
                        current_win_rate=analysis.get("overall_win_rate"),
                        current_expectancy=cur_exp,
                    )
                    new_weights = applied_weights
                    if accepted:
                        self.voting_engine.update_weights(applied_weights)
                        self.stats["weight_updates"] += 1
                        self.stats["last_weights"]    = applied_weights
                        await self.log("INFO", f"⚖️ بدء اختبار أوزان Challenger ({cc_reason}): {applied_weights}")
                    else:
                        await self.log("INFO", f"🛡️ إبقاء أوزان Champion v{self.champion_manager.champion.version} ({cc_reason})")

                # تدريب النموذج
                accuracy = await self._train_model()
                if accuracy > 0:
                    self._model_accuracy = accuracy
                    self.stats["model_accuracy"] = accuracy
                    self.stats["model_trained"]  = True

                # حفظ تقرير التعلم
                self._save_learning_log(analysis, new_weights)

            else:
                await self.log(
                    "INFO",
                    f"📊 بيانات غير كافية: {analysis['total_trades']}/{self.min_trades} صفقة"
                )

            # تحديث الإحصائيات دائماً
            self.stats["iterations"]            += 1
            self.stats["last_analysis"]          = datetime.utcnow().isoformat()
            self.stats["total_trades_analyzed"]  = analysis["total_trades"]
            self.stats["best_regime"]            = analysis.get("best_regime")
            self.stats["worst_regime"]           = analysis.get("worst_regime")
            self.stats["current_win_rate"]       = analysis.get("overall_win_rate")

            await self.log(
                "INFO",
                f"✅ تعلم مكتمل | "
                f"Win Rate:{analysis.get('overall_win_rate', 0):.1f}% | "
                f"Best Regime:{analysis.get('best_regime')} | "
                f"Model Acc:{self._model_accuracy:.1f}% | "
                f"Trades:{analysis['total_trades']} | "
                f"مستبعد(بلا نتيجة):{analysis.get('excluded_unknown', 0)}"
            )

            # P1 fix: تنظيف أي سجلات OPEN عالقة لأكثر من 24 ساعة في trade_vectors
            try:
                root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                if root_path not in sys.path:
                    sys.path.append(root_path)
                from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder
                swept = await TradeOutcomeRecorder().sweep_stale_open_records(max_age_hours=24.0)
                if swept:
                    await self.log("INFO", f"🧹 تنظيف {swept} سجل OPEN عالق (>24 ساعة) في trade_vectors")
            except Exception as sweep_err:
                logger.debug(f"Stale sweep note: {sweep_err}")

            # ذاكرة التأمّل: درس لكل صفقة مغلقة نتيجتها معروفة
            reflections = self._write_reflections()
            if reflections:
                self.stats["reflections_written"] = self.stats.get("reflections_written", 0) + reflections
                await self.log("INFO", f"🧠 ذاكرة التأمّل: كُتب {reflections} درساً جديداً")

            # نشر نتائج التعلم
            await self.bus.publish(BusMessage(
                topic  = "learning_update",
                sender = self.name,
                data   = {
                    "win_rate":       analysis.get("overall_win_rate"),
                    "best_regime":    analysis.get("best_regime"),
                    "worst_regime":   analysis.get("worst_regime"),
                    "regimes":        analysis.get("regime_stats", {}),
                    "weights":        new_weights,
                    "total_trades":   analysis["total_trades"],
                    "total_profit":   analysis.get("total_profit", 0),
                    "high_conf_wr":   analysis.get("high_conf_wr", 0),
                    "model_accuracy": self._model_accuracy,
                },
            ))

        except Exception as e:
            await self.log("ERROR", f"❌ خطأ في التعلم: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # ── ذاكرة التأمّل: حالة → قرار → نتيجة → درس ─────────────────────
    def _write_reflections(self) -> int:
        """
        يبني صفوف تأمّل للصفقات المغلقة التي نتيجتها معروفة ولم يُسجَّل لها
        درس بعد، ويربطها بحكم مجلس الظل عبر trade_ticket → signal_id.
        الدرس بقواعد حتمية (بلا LLM) حتى لا يعتمد على مزوّد خارجي.
        """
        db = None
        written = 0
        try:
            db = SessionLocal()
            existing = {row[0] for row in db.query(AgentReflection.trade_ticket).all()}

            trades = db.query(Trade).filter(
                Trade.status     == TradeStatus.CLOSED,
                Trade.profit_usd.isnot(None),
            ).order_by(Trade.closed_at.desc()).limit(500).all()

            for trade in trades:
                if trade.ticket in existing:
                    continue

                sig = db.query(SignalModel).filter(
                    SignalModel.trade_ticket == trade.ticket
                ).first()
                shadow = None
                if sig is not None:
                    shadow = db.query(ShadowDecision).filter(
                        ShadowDecision.signal_id == sig.id
                    ).order_by(ShadowDecision.id.desc()).first()

                pnl        = float(trade.profit_usd or 0.0)
                outcome    = "WIN" if pnl > 0 else "LOSS"
                regime     = trade.fsm_regime.value if trade.fsm_regime else "UNKNOWN"
                aligned    = shadow.council_aligned if shadow else None
                would_block= shadow.council_would_block if shadow else None

                db.add(AgentReflection(
                    trade_ticket        = trade.ticket,
                    signal_id           = sig.id if sig else None,
                    symbol              = trade.symbol,
                    fsm_regime          = regime,
                    confidence          = trade.confidence,
                    ml_prob             = shadow.ml_prob if shadow else None,
                    council_aligned     = aligned,
                    council_would_block = would_block,
                    outcome_pnl         = round(pnl, 2),
                    outcome             = outcome,
                    lesson              = self._build_lesson(
                        regime, trade.confidence, outcome, pnl, aligned, would_block, shadow
                    ),
                ))
                written += 1

            if written:
                db.commit()
        except Exception as e:
            logger.error(f"❌ خطأ في كتابة التأمّلات: {e}")
        finally:
            if db:
                db.close()
        return written

    @staticmethod
    def _build_lesson(regime, confidence, outcome, pnl, aligned, would_block, shadow) -> str:
        """درس حتمي قابل للتنفيذ — لا عبارات عامة."""
        conf_txt = f"{confidence:.0f}%" if confidence is not None else "?"

        if would_block:
            stage = (shadow.bridge_stage if shadow else None) or (
                f"consensus:{shadow.consensus_action}" if shadow else "council"
            )
            if outcome == "LOSS":
                return (f"{regime} | ثقة {conf_txt} → خسارة {pnl:+.2f}$ كان المجلس سيمنعها "
                        f"({stage}). المرجّح: تمكين الفيتو في هذا الـ regime.")
            return (f"{regime} | ثقة {conf_txt} → ربح {pnl:+.2f}$ كان المجلس سيمنعه ({stage}). "
                    f"الفيتو كان سيكلّف هذا المقدار.")

        if aligned:
            if outcome == "LOSS":
                return (f"{regime} | ثقة {conf_txt} → خسارة {pnl:+.2f}$ رغم اتفاق المجلس. "
                        f"الخلل محتمل في التنفيذ/المخارج لا في الدخول.")
            return f"{regime} | ثقة {conf_txt} → ربح {pnl:+.2f}$ متوافق مع المجلس."

        return (f"{regime} | ثقة {conf_txt} → {outcome} {pnl:+.2f}$ بلا حكم مجلس مسجَّل "
                f"(الإشارة غير مربوطة).")

    # ── تحليل السجل التاريخي ─────────────────────────────────────────
    def _analyze_history(self) -> Optional[dict]:
        """تحليل سجل الصفقات المغلقة — آخر 60 يوم"""
        db = None
        try:
            db = SessionLocal()
            since  = datetime.utcnow() - timedelta(days=60)
            trades = db.query(Trade).filter(
                Trade.status    == TradeStatus.CLOSED,
                Trade.closed_at >= since,
            ).all()

            # الصفقات التي لم تُسجَّل نتيجتها (profit_usd = NULL) تُستبعد تماماً:
            # كانت تُحسب خسائر (None or 0 = 0) فتُفسد نسبة الفوز وتعديلات الأوزان
            unknown = [t for t in trades if t.profit_usd is None]
            trades  = [t for t in trades if t.profit_usd is not None]

            total = len(trades)
            if total < 1:
                return {"total_trades": 0, "overall_win_rate": 0,
                        "total_profit": 0, "regime_stats": {}, "best_regime": None,
                        "worst_regime": None, "high_conf_wr": 0, "avg_confidence": 0,
                        "excluded_unknown": len(unknown)}

            wins   = [t for t in trades if t.profit_usd > 0]
            losses = [t for t in trades if t.profit_usd <= 0]
            wr     = len(wins) / total * 100

            # تحليل حسب Regime
            regime_stats: Dict[str, dict] = {}
            for trade in trades:
                regime = trade.fsm_regime.value if trade.fsm_regime else "UNKNOWN"
                if regime not in regime_stats:
                    regime_stats[regime] = {"trades":0,"wins":0,"losses":0,"profit":0.0}
                rs = regime_stats[regime]
                rs["trades"] += 1
                p = trade.profit_usd or 0
                rs["profit"] += p
                if p > 0:
                    rs["wins"] += 1
                else:
                    rs["losses"] += 1

            for rs in regime_stats.values():
                rs["win_rate"] = (rs["wins"] / rs["trades"] * 100) if rs["trades"] > 0 else 0

            eligible     = [(r, s) for r, s in regime_stats.items() if s["trades"] >= 2]
            best_regime  = max(eligible, key=lambda x: x[1]["win_rate"], default=("UNKNOWN", {}))[0]
            worst_regime = min(eligible, key=lambda x: x[1]["win_rate"], default=("UNKNOWN", {}))[0]

            high_conf  = [t for t in trades if (t.confidence or 0) >= 75]
            hcwr       = (
                len([t for t in high_conf if (t.profit_usd or 0) > 0]) /
                len(high_conf) * 100
            ) if high_conf else 0

            return {
                "total_trades":     total,
                "total_wins":       len(wins),
                "total_losses":     len(losses),
                "overall_win_rate": wr,
                "total_profit":     sum((t.profit_usd or 0) for t in trades),
                "regime_stats":     regime_stats,
                "best_regime":      best_regime,
                "worst_regime":     worst_regime,
                "high_conf_wr":     hcwr,
                "avg_confidence":   sum((t.confidence or 0) for t in trades) / total,
                "excluded_unknown": len(unknown),
            }
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل التاريخ: {e}")
            return None
        finally:
            if db:
                db.close()

    # ── حساب تعديلات الأوزان ─────────────────────────────────────────
    def _compute_weight_adjustments(self, analysis: dict) -> Dict[str, float]:
        """
        حساب تعديلات المضاعِفات بشكل صحيح.

        ⚠️ إصلاح حرج (IMPROVEMENT_PLAN §0 + 2026 Upgrades):
        - المضاعِف المحايد هو 1.0 لكل الأوزان.
        - يستخدم ExponentialAttributionBandit مع Empirical Bayes shrinkage عند توفر إحصاءات الصفقات.
        - يتراجع إلى القواعد المحايدة المعايرة (Phase 0) عند غياب تفاصيل الصفقات.
        """
        regime_stats = (analysis.get("regime_stats", {}) or {}) if analysis else {}
        has_trade_counts = any(int(st.get("trades", 0) or 0) > 0 for st in regime_stats.values()) if regime_stats else False

        if has_trade_counts:
            res = ExponentialAttributionBandit.compute_multipliers(analysis)
            if res:
                return res

        adjustments: Dict[str, float] = {}
        if not regime_stats:
            return {}

        def clamp(val: float, lo=0.3, hi=3.0) -> float:
            return max(lo, min(hi, val))

        winning_regimes = [r for r, s in regime_stats.items() if s.get("win_rate", 0) > 65]
        losing_regimes  = [r for r, s in regime_stats.items() if s.get("win_rate", 0) < 45]

        if "STRONG_TREND" in winning_regimes:
            adjustments["ema"]      = clamp(adjustments.get("ema",      1.0) + 0.15)
            adjustments["momentum"] = clamp(adjustments.get("momentum", 1.0) + 0.10)
            adjustments["ha"]       = clamp(adjustments.get("ha",       1.0) + 0.10)

        if "SLOW_TREND" in winning_regimes:
            adjustments["ichi"] = clamp(adjustments.get("ichi", 1.0) + 0.10)
            adjustments["macd"] = clamp(adjustments.get("macd", 1.0) + 0.10)

        if "HIGH_VOL_RANGE" in losing_regimes:
            adjustments["rsi"] = clamp(adjustments.get("rsi", 1.0) - 0.15)

        if "CHAOS" in losing_regimes:
            adjustments["ema"] = clamp(adjustments.get("ema", 1.0) - 0.15)
            adjustments["adx"] = clamp(adjustments.get("adx", 1.0) + 0.10)

        return adjustments

    @staticmethod
    def build_stationary_feature_vector(
        buy_score: float,
        sell_score: float,
        confidence: float,
        price: Optional[float],
        ema_value: float,
        rsi_value: float,
        macd_value: float,
        adx_value: float,
        atr_value: float,
    ) -> list:
        """
        يبني متجه الميزات الثماني المستقر عبر الأزواج:
        يستبدل السعر الخام (ema_value) بالمسافة المطبّعة عن EMA بوحدات ATR:
          ema_dist_atr = clip((price - ema) / max(atr, 1e-6), -5.0, 5.0)
        والميزة الثامنة atr_pct = ATR/السعر×100 (مقيّدة [0, 5]) بدل ATR الخام.
        ويحافظ على طول المتجه 8 للتوافق التام مع MetaLabelingClassifier و meta_runtime.
        """
        if price is not None and price > 0 and ema_value and atr_value and atr_value > 1e-8:
            ema_dist_atr = max(-5.0, min(5.0, (float(price) - float(ema_value)) / float(atr_value)))
        else:
            ema_dist_atr = 0.0
        # تطبيع MACD نسبياً على ATR إن أمكن ليصبح غير معتمد على مقياس الزوج
        macd_norm = (
            max(-5.0, min(5.0, float(macd_value) / float(atr_value)))
            if (atr_value and atr_value > 1e-8) else float(macd_value or 0.0)
        )
        # ATR كنسبة مئوية من السعر (EURUSD ≈ 0.07%، XAUUSD ≈ 0.7%) بدل ATR الخام (0.0008 مقابل 15)
        atr_pct = (
            max(0.0, min(5.0, float(atr_value) / float(price) * 100.0))
            if (price is not None and price > 0 and atr_value and atr_value > 1e-8) else 0.0
        )
        return [
            float(buy_score or 0.0),
            float(sell_score or 0.0),
            float(confidence or 0.0),
            round(ema_dist_atr, 5),
            float(rsi_value if rsi_value is not None else 50.0),
            round(macd_norm, 5),
            float(adx_value or 0.0),
            round(atr_pct, 5),
        ]

    @staticmethod
    def _purged_time_series_cv_accuracy(model_proto, X, y, n_splits: int = 4, embargo: int = 2) -> float:
        """
        تقييم تسلسلي زمني محصّن ضد التسرّب (Purged Walk-Forward CV):
        يدرّب Scaler والنموذج داخل كل Fold على الماضي فقط مع فجوة حظر (Embargo) قبل الاختبار.
        """
        import numpy as np
        from sklearn.base import clone
        from sklearn.preprocessing import StandardScaler

        n = len(X)
        if n < 8 or n_splits < 2:
            return 0.0
        fold_size = max(2, n // (n_splits + 1))
        scores = []
        for split in range(1, n_splits + 1):
            train_end = split * fold_size
            test_start = train_end + max(0, embargo)
            test_end = min(n, test_start + fold_size)
            if train_end < 4 or test_start >= test_end:
                continue
            y_tr = y[:train_end]
            if len(set(y_tr)) < 2:
                continue
            sc = StandardScaler()
            X_tr = sc.fit_transform(X[:train_end])
            X_te = sc.transform(X[test_start:test_end])
            clf = clone(model_proto)
            clf.fit(X_tr, y_tr)
            scores.append(float(clf.score(X_te, y[test_start:test_end])))
        return round(float(np.mean(scores) * 100.0), 2) if scores else 0.0

    # ── تدريب النموذج ML ─────────────────────────────────────────────
    async def _train_model(self) -> float:
        """تدريب GradientBoosting + RandomForest على البيانات الحقيقية"""
        db = None
        accuracy = 0.0
        try:
            from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import cross_val_score
            import numpy as np
            import joblib

            db = SessionLocal()

            # 1. ربط الصفقات الكلاسيكية بالإشارات في قاعدة البيانات تلقائياً
            # نجد الصفقات التي لا تحتوي إشارتها على تذكرة الصفقة
            unlinked_trades = db.query(Trade).all()
            for trade in unlinked_trades:
                sig_dir = "BUY" if trade.type.value == "BUY" else "SELL"
                # نبحث عن إشارة تم إنشاؤها في نافذة 90 ثانية قبل فتح الصفقة
                sig = db.query(SignalModel).filter(
                    SignalModel.symbol == trade.symbol,
                    SignalModel.direction == sig_dir,
                    SignalModel.trade_ticket == None,
                    SignalModel.created_at <= trade.opened_at + timedelta(seconds=15),
                    SignalModel.created_at >= trade.opened_at - timedelta(seconds=90)
                ).order_by(SignalModel.created_at.desc()).first()

                if sig:
                    sig.executed = True
                    sig.trade_ticket = trade.ticket
            
            db.commit()

            # جلب الإشارات مرتّبة زمنياً (شرط أساسي لمنع التسرّب الزمني في Time-Series CV)
            signals = db.query(SignalModel).filter(
                SignalModel.executed == True,
                SignalModel.trade_ticket != None
            ).order_by(SignalModel.created_at.asc()).all()

            # إنشاء خارطة تذاكر الصفقات المغلقة إلى الأرباح.
            # الصفقات بلا نتيجة مسجّلة تُستبعد من التدريب بدل وسمها خاسرة (label=0)
            closed_trades = db.query(Trade).filter(
                Trade.status     == TradeStatus.CLOSED,
                Trade.profit_usd.isnot(None),
            ).all()
            ticket_to_profit = {t.ticket: t.profit_usd for t in closed_trades}

            db.close()
            db = None

            # بناء مصفوفة الميزات والأهداف
            X, y = [], []
            for sig in signals:
                if sig.trade_ticket not in ticket_to_profit:
                    continue  # تخطي الإشارات التي صفقاتها لا تزال مفتوحة
                
                # 2026 Upgrade: ميزة مستقرة ومطبّعة (المسافة النسبية عن EMA مقسومة على ATR بدل السعر الخام)
                features = self.build_stationary_feature_vector(
                    buy_score=sig.buy_score or 0.0,
                    sell_score=sig.sell_score or 0.0,
                    confidence=sig.confidence or 0.0,
                    price=getattr(sig, "price", None),
                    ema_value=sig.ema_value or 0.0,
                    rsi_value=sig.rsi_value if sig.rsi_value is not None else 50.0,
                    macd_value=sig.macd_value or 0.0,
                    adx_value=sig.adx_value or 0.0,
                    atr_value=sig.atr_value or 0.0,
                )
                
                # الهدف: 1 إذا كانت الصفقة رابحة (> 0 دولار)، 0 خلاف ذلك
                profit = ticket_to_profit[sig.trade_ticket]
                label = 1 if profit > 0.0 else 0
                
                X.append(features)
                y.append(label)

            if len(X) < 5:
                logger.info(f"📊 بيانات ML غير كافية: {len(X)} إشارة مكتملة (مطلوب 5)")
                return 0.0

            X = np.array(X, dtype=float)
            y = np.array(y)

            if len(set(y)) < 2:
                logger.warning("⚠️ بيانات ML: تحتوي على فئة واحدة فقط (كل الصفقات رابحة أو خاسرة) — تخطي التدريب")
                return 0.0

            scaler   = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # نموذجان: GradientBoosting (أعمق) + RandomForest (أسرع)
            gb_model = GradientBoostingClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
            )
            rf_model = RandomForestClassifier(
                n_estimators=100, max_depth=5, random_state=42
            )

            if len(X) >= 10:
                # 2026 Upgrade: Purged Time-Series CV مع Embargo (لا تسرّب مستقبلي إطلاقاً)
                embargo = int(LEARNING_UPGRADES_2026.get("cv_embargo_bars", 2))
                accuracy = self._purged_time_series_cv_accuracy(gb_model, X, y, n_splits=min(5, max(2, len(X) // 4)), embargo=embargo)
                gb_model.fit(X_scaled, y)
            else:
                gb_model.fit(X_scaled, y)
                accuracy = float(gb_model.score(X_scaled, y) * 100)

            rf_model.fit(X_scaled, y)

            # تدريب نموذج Meta-Labeling المعاير مع Purged K-Fold (المرحلة 3)
            try:
                from quant_core.meta_model import MetaLabelingClassifier
                meta_clf = MetaLabelingClassifier(calibration_method="sigmoid", n_splits=min(4, max(2, len(X) // 3)))
                meta_metrics = meta_clf.fit(X, y)
                self._meta_model = meta_clf
                if meta_clf.is_fitted:
                    meta_clf.save(META_MODEL_PATH)
                logger.info(
                    f"🎯 نموذج Meta-Labeling المعاير (OOS): Brier={meta_metrics.brier_score:.3f} | "
                    f"AUC={meta_metrics.roc_auc:.3f} | OOS_Acc={meta_metrics.out_of_sample_accuracy:.1f}% | "
                    f"Saved={META_MODEL_PATH}"
                )
                # P3: بوابة التفعيل — الاحتمال لا يصل إلى التحجيم قبل اجتياز شروط OOS
                logger.info(self._meta_gate_decision().summary())
            except Exception as meta_err:
                logger.warning(f"⚠️ تعذر تدريب نموذج Meta-Labeling المعاير: {meta_err}")

            self._model  = gb_model  # النموذج الرئيسي
            self._rf_model = rf_model
            self._scaler = scaler

            # حفظ على القرص للاستمرارية
            joblib.dump(gb_model, MODEL_PATH)
            joblib.dump(scaler, SCALER_PATH)

            logger.info(
                f"🤖 نموذج ML مُدرَّب بنجاح: {len(X)} إشارة حقيقية | "
                f"دقة النموذج: {accuracy:.1f}% | "
                f"محفوظ في {MODEL_PATH}"
            )
            return accuracy

        except ImportError as e:
            logger.warning(f"⚠️ مكتبة ML غير متوفرة: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"❌ خطأ في تدريب ML: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0.0
        finally:
            if db:
                db.close()

    def _load_model(self):
        """تحميل النماذج المحفوظة من القرص (P2 fix: تحميل MetaLabelingClassifier وإزالة رقم 70.0% المُلفق)"""
        try:
            import joblib
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
                self._model  = joblib.load(MODEL_PATH)
                self._scaler = joblib.load(SCALER_PATH)
                # P2 fix: لا أرقام مُلفقة (AGENTS.md) — تبقى 0.0 حتى تُقاس في أول دورة تدريب
                self._model_accuracy = 0.0
                logger.success(f"✅ نموذج ML محمّل من {MODEL_PATH}")
            if os.path.exists(META_MODEL_PATH):
                from quant_core.meta_model import MetaLabelingClassifier
                self._meta_model = MetaLabelingClassifier.load(META_MODEL_PATH)
                logger.success(f"✅ نموذج Meta-Labeling المعاير محمّل من {META_MODEL_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ لم يُحمل النموذج: {e}")

    def _meta_gate_decision(self):
        """P3: قرار بوابة التفعيل للنموذج المعاير الحالي (مغلقة إن لم يوجد نموذج)."""
        from quant_core.activation_gate import MetaActivationGate, GateDecision
        if not self._meta_model or not getattr(self._meta_model, "is_fitted", False):
            return GateDecision(active=False, reasons=("not_fitted",))
        return self._meta_model.activation_decision(MetaActivationGate(**META_GATE))

    def predict_calibrated(self, signal_features: list) -> Optional[float]:
        """
        P3: الاحتمال المعاير الحقيقي P(Win) **أو None**.
        None إذا: لا نموذج معاير، أو لم يجتز بوابة التفعيل (OOS)، أو الخصائص غير مطابقة.
        لا يسقط إلى GBM غير المعاير ولا يُختلق 0.5. هذا هو المسار الوحيد المسموح لتحجيم الصفقات.
        """
        if not self._meta_model or not getattr(self._meta_model, "is_fitted", False):
            return None
        if not self._meta_gate_decision().active:
            return None
        return self._meta_model.predict_calibrated(signal_features)

    def predict(self, signal_features: list) -> float:
        """
        تنبؤ بجودة الإشارة (0.0 → 1.0) — **للمجلس الظلّي والقياس فقط، وليس للتحجيم أو القرار**.
        ⚠️ P3: قد يسقط إلى GBM غير المعاير أو يرجع 0.5 (لا نموذج). استخدم predict_calibrated للتحجيم.
        """
        # إذا كان نموذج Meta-Labeling المعاير جاهزاً، استخدمه أولاً
        if self._meta_model and getattr(self._meta_model, "is_fitted", False):
            try:
                prob = self._meta_model.predict_probability(signal_features)
                return float(prob)
            except Exception:
                pass

        if self._model is None or self._scaler is None:
            return 0.5
        try:
            import numpy as np
            X = np.array([signal_features], dtype=float)
            X_scaled = self._scaler.transform(X)
            prob = self._model.predict_proba(X_scaled)[0][1]
            return float(prob)
        except Exception:
            return 0.5

    def _save_learning_log(self, analysis: dict, weights: dict):
        db = None
        try:
            db = SessionLocal()
            log = LearningLog(
                iteration         = self.stats.get("iterations", 0) + 1,
                trades_analyzed   = analysis["total_trades"],
                win_rate          = analysis["overall_win_rate"],
                best_regime       = analysis.get("best_regime"),
                worst_regime      = analysis.get("worst_regime"),
                weight_adjustments= json.dumps(weights),
                notes = (
                    f"Confidence avg: {analysis.get('avg_confidence', 0):.1f}% | "
                    f"High-conf WR: {analysis.get('high_conf_wr', 0):.1f}% | "
                    f"Total Profit: ${analysis.get('total_profit', 0):.2f} | "
                    f"Model Acc: {self._model_accuracy:.1f}%"
                ),
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ سجل التعلم: {e}")
        finally:
            if db:
                db.close()
