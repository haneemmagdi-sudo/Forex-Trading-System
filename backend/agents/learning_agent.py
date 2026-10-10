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
from config import AGENTS

# مسار حفظ النموذج
MODEL_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "ml_model.pkl")
SCALER_PATH= os.path.join(MODEL_DIR, "ml_scaler.pkl")
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
        self._model_accuracy = 0.0

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
        })

    # ── دورة التعلم الرئيسية ─────────────────────────────────────────
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
                # تحديث الأوزان
                new_weights = self._compute_weight_adjustments(analysis)
                if new_weights and self.voting_engine:
                    self.voting_engine.update_weights(new_weights)
                    self.stats["weight_updates"] += 1
                    self.stats["last_weights"]    = new_weights
                    await self.log("INFO", f"⚖️ أوزان محدَّثة: {new_weights}")

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
        adjustments: Dict[str, float] = {}
        regime_stats = analysis.get("regime_stats", {})
        if not regime_stats:
            return {}

        def clamp(val: float, lo=0.3, hi=3.0) -> float:
            return max(lo, min(hi, val))

        winning_regimes = [r for r, s in regime_stats.items() if s.get("win_rate", 0) > 65]
        losing_regimes  = [r for r, s in regime_stats.items() if s.get("win_rate", 0) < 45]

        if "STRONG_TREND" in winning_regimes:
            adjustments["ema"]      = clamp(adjustments.get("ema", 1.0) + 0.15)
            adjustments["momentum"] = clamp(adjustments.get("momentum", 1.0) + 0.10)
            adjustments["ha"]       = clamp(adjustments.get("ha", 2.0) + 0.10)

        if "SLOW_TREND" in winning_regimes:
            adjustments["ichi"] = clamp(adjustments.get("ichi", 0.8) + 0.10)
            adjustments["macd"] = clamp(adjustments.get("macd", 0.6) + 0.10)

        if "HIGH_VOL_RANGE" in losing_regimes:
            adjustments["rsi"] = clamp(adjustments.get("rsi", 0.8) - 0.15)

        if "CHAOS" in losing_regimes:
            adjustments["ema"]      = clamp(adjustments.get("ema", 1.0) - 0.15)
            adjustments["momentum"] = clamp(adjustments.get("momentum", 0.5) - 0.10)

        wr = analysis.get("overall_win_rate", 65)
        if wr < 50:
            adjustments["ha"]   = clamp(adjustments.get("ha", 2.0) + 0.20)
            adjustments["macd"] = clamp(adjustments.get("macd", 0.6) - 0.10)
        elif wr > 75:
            adjustments["ha"]  = clamp(adjustments.get("ha", 2.0) + 0.10)
            adjustments["rsi"] = clamp(adjustments.get("rsi", 0.8) + 0.05)

        if analysis.get("high_conf_wr", 65) > 80:
            adjustments["adx"] = clamp(adjustments.get("adx", 0.7) + 0.10)

        return adjustments

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

            # جلب الإشارات التي تم ربطها بصفقات مغلقة
            signals = db.query(SignalModel).filter(
                SignalModel.executed == True,
                SignalModel.trade_ticket != None
            ).all()

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
                
                features = [
                    sig.buy_score    or 0,
                    sig.sell_score   or 0,
                    sig.confidence   or 0,
                    sig.ema_value    or 0,
                    sig.rsi_value    or 50,
                    sig.macd_value   or 0,
                    sig.adx_value    or 0,
                    sig.atr_value    or 0,
                ]
                
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
                # Cross-validation لتقييم دقيق
                cv_folds = min(5, len(X) // 2)
                gb_scores = cross_val_score(gb_model, X_scaled, y, cv=cv_folds)
                accuracy  = float(gb_scores.mean() * 100)
                gb_model.fit(X_scaled, y)
            else:
                gb_model.fit(X_scaled, y)
                accuracy = float(gb_model.score(X_scaled, y) * 100)

            rf_model.fit(X_scaled, y)

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
        """تحميل نموذج محفوظ من القرص"""
        try:
            import joblib
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
                self._model  = joblib.load(MODEL_PATH)
                self._scaler = joblib.load(SCALER_PATH)
                # تقدير الدقة
                self._model_accuracy = 70.0  # قيمة افتراضية
                logger.success(f"✅ نموذج ML محمّل من {MODEL_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ لم يُحمل النموذج: {e}")

    def predict(self, signal_features: list) -> float:
        """تنبؤ بجودة الإشارة (0.0 → 1.0)"""
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
