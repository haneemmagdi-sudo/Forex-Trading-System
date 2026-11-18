"""
============================================================
execution_agent.py — الوكيل 2: منفذ الصفقات
============================================================
يستلم الإشارات من الـ Bus → يتحقق من الشروط → يفتح الصفقات
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from loguru import logger

from agents.base_agent import BaseAgent
from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.safe_execution_gateway import SafeExecutionGateway
from core.signal_bus import BusMessage
from models.database import SessionLocal, Trade, TradeType, TradeStatus, FSMRegime
from config import STRATEGY, AGENTS


class ExecutionAgent(BaseAgent):
    """
    الوكيل الثاني — منفذ الصفقات
    ────────────────────────────────────────────────────
    ✅ يستمع لإشارات الوكيل الأول عبر Signal Bus
    ✅ يتحقق من: DD، عدد الصفقات، السبريد، الجلسة
    ✅ يحسب ويفتح الصفقة بسلام عبر SafeExecutionGateway
    ✅ ينشر حدث trade_opened ويقوم بالمراقبة التلقائية
    """

    def __init__(self, mt5: MT5Connector):
        super().__init__("ExecutionAgent", interval_sec=1.0)
        self.mt5          = mt5
        self.risk         = RiskManager()
        self.gateway      = SafeExecutionGateway(self.mt5, risk_manager=self.risk)
        self._pending_signals = []

        # حماية Cascade
        self._consecutive_losses = 0
        self._cascade_blocked_until = None

        self.stats.update({
            "trades_opened":     0,
            "trades_rejected":   0,
            "last_trade":        None,
        })

        # الاشتراك في الإشارات
        self.bus.subscribe("signal", self._on_signal)
        self.bus.subscribe("trade_closed", self._on_trade_closed)
        self.bus.subscribe("dd_alert", self._on_dd_alert)

    async def run_cycle(self):
        """معالجة الإشارات المعلقة"""
        while self._pending_signals:
            sig = self._pending_signals.pop(0)
            await self._process_signal(sig)

    async def _on_signal(self, msg: BusMessage):
        """استلام إشارة من Analyst"""
        self._pending_signals.append(msg.data)

    async def _on_trade_closed(self, msg: BusMessage):
        """تتبع الخسائر المتتالية للـ Cascade"""
        profit = msg.data.get("profit", 0)
        if profit < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        if self._consecutive_losses >= STRATEGY["cascade_max_losses"]:
            import asyncio
            cooldown_sec = STRATEGY["cascade_cooldown_min"] * 60
            self._cascade_blocked_until = datetime.utcnow().timestamp() + cooldown_sec
            await self.log("WARNING",
                f"🛑 Cascade Protection! {self._consecutive_losses} خسائر متتالية. "
                f"إيقاف {STRATEGY['cascade_cooldown_min']} دقيقة")

    async def _on_dd_alert(self, msg: BusMessage):
        mode = msg.data.get("mode", "")
        if mode == "EMERGENCY_STOP":
            await self.log("ERROR", "🆘 إيقاف طوارئ بسبب DD — إلغاء جميع الإشارات")
            self._pending_signals.clear()

    @staticmethod
    def _pip_size(symbol: str) -> float:
        """حجم البيب: 0.01 للين و0.1 للذهب و0.0001 للباقي (اتفاقية مجلس الوكلاء نفسها).
        كان الذهب يُحسب بـ0.0001 فتصير مسافة الشبكة 25 بيب = 0.0025$ وتُفتح الطبقات فوراً."""
        return 0.01 if "JPY" in symbol else (0.1 if "XAU" in symbol else 0.0001)

    async def _process_signal(self, signal_data: dict):
        """معالجة إشارة واحدة"""
        symbol    = signal_data.get("symbol")
        direction = signal_data.get("direction")
        voting    = signal_data.get("voting", {})
        fsm       = signal_data.get("fsm", {})

        if not symbol or direction not in ("BUY", "SELL"):
            return

        # ── فحوصات قبل الفتح ─────────────────────────────────────────

        # 1. Cascade Protection
        if self._cascade_blocked_until:
            if datetime.utcnow().timestamp() < self._cascade_blocked_until:
                await self.log("WARNING", f"⏳ Cascade Block فعّال — رُفضت إشارة {symbol}")
                self.stats["trades_rejected"] += 1
                return
            else:
                self._cascade_blocked_until = None
                self._consecutive_losses = 0

        # 2. DD Protection
        account = self.mt5.get_account()
        dd_check = self.risk.check_dd_protection(account["balance"], account["equity"])
        if not dd_check["ok"]:
            await self.log("ERROR", f"🆘 Emergency Stop! DD={dd_check['dd_pct']:.1f}%")
            self.mt5.close_all_positions(reason="Emergency_Stop")
            self.stats["trades_rejected"] += 1
            return

        # 3. عدد الصفقات المفتوحة
        open_positions = self.mt5.get_open_positions(symbol)
        total_open = len(self.mt5.get_open_positions())
        if total_open >= STRATEGY["max_open_trades"]:
            await self.log("WARNING", f"⚠️ أقصى عدد صفقات مفتوحة ({STRATEGY['max_open_trades']})")
            self.stats["trades_rejected"] += 1
            return

        # 4. هل هناك صفقة مفتوحة على نفس الزوج والاتجاه؟ (الشبكة الذكية)
        # جلب السعر الحالي مبكراً (مطلوب للشبكة الذكية)
        tick_early = self.mt5.get_tick(symbol)
        if not tick_early:
            return
        current_price = tick_early["ask"] if direction == "BUY" else tick_early["bid"]

        same_dir_positions = [pos for pos in open_positions if pos["type"] == direction]
        if same_dir_positions:
            max_trades = STRATEGY.get("max_open_trades", 5)
            if len(same_dir_positions) >= max_trades:
                await self.log("WARNING", f"⚠️ أقصى عدد صفقات في نفس الاتجاه للشبكة ({max_trades}) قد تم الوصول إليه")
                self.stats["trades_rejected"] += 1
                return

            # جلب آخر صفقة تم فتحها (الأحدث)
            same_dir_positions.sort(key=lambda x: x.get("open_time", ""), reverse=True)
            latest_pos = same_dir_positions[0]
            latest_entry = latest_pos["open_price"]

            # حساب المسافة بالنقاط
            pip_size = self._pip_size(symbol)
            grid_dist_pips = STRATEGY.get("grid_distance_pips", 25)
            grid_dist_price = grid_dist_pips * pip_size

            if direction == "BUY":
                # تراجع في الشراء يعني أن السعر الحالي أقل من سعر الدخول السابق
                distance_moved = latest_entry - current_price
            else:
                # تراجع في البيع يعني أن السعر الحالي أعلى من سعر الدخول السابق
                distance_moved = current_price - latest_entry

            if distance_moved < grid_dist_price:
                await self.log("INFO", 
                    f"ℹ️ تفعيل الشبكة الذكية: السعر لم يتراجع بالقدر الكافي للدخول الإضافي. "
                    f"تراجع الحالي: {distance_moved/pip_size:.1f} Pips < المطلوب: {grid_dist_pips} Pips")
                self.stats["trades_rejected"] += 1
                return
            
            await self.log("INFO", f"🚀 تفعيل الشبكة الذكية! دخول الصفقة الإضافية رقم {len(same_dir_positions) + 1} بناءً على تراجع السعر ({distance_moved/pip_size:.1f} Pips) وتصويت المجلس.")

        # تحديث سعر الدخول من البيانات المجلوبة مسبقاً
        tick  = tick_early
        spread = tick["spread"]
        entry  = tick["ask"] if direction == "BUY" else tick["bid"]

        # ── 4.5 فحص تمدد السبريد المفاجئ عند لحظة التنفيذ (Flash Spread Protection) ──
        max_allowed_spread = STRATEGY.get("max_spread_pips", 4.0)
        if spread > max_allowed_spread * 1.4:
            await self.log("WARNING", f"⚠️ قفزة سبريد مفاجئة عند التنفيذ على {symbol}: {spread:.1f} > {max_allowed_spread * 1.4:.1f} Pips — إلغاء الأمر لحماية الحساب")
            self.stats["trades_rejected"] += 1
            return

        # ── 5. تنفيذ الصفقة الآمن عبر بوابة التنفيذ SafeExecutionGateway ──
        start_exec_ts = datetime.utcnow().timestamp()
        vote_confidence = voting.get("confidence")
        signal_id = signal_data.get("signal_id")
        res = await self.gateway.execute_signal(
            symbol=symbol,
            rf_prediction=None,
            lstm_delta=None,
            dqn_q_values=None,
            sentiment_score=signal_data.get("news_score"),
            fsm_regime=fsm.get("regime", "LOW_VOL_RANGE"),
            direction=direction,
            vote_confidence=vote_confidence,
            signal_id=signal_id,
        )

        exec_latency_ms = round((datetime.utcnow().timestamp() - start_exec_ts) * 1000.0, 1)

        if not res["success"]:
            await self.log("WARNING", f"❌ فشل فتح الصفقة عبر البوابة الآمنة: {res.get('reason')} (استغرق {exec_latency_ms}ms)")
            self.stats["trades_rejected"] += 1
            return

        ticket = res["ticket"]
        lot = res["lot"]
        sl = res["sl"]
        tp = res["tp"]

        # IMPROVEMENT_PLAN §1: ربط مباشر 100% بين تذكرة الصفقة ومعرّف الإشارة
        if ticket and signal_id:
            try:
                from models.database import SessionLocal, Signal as SignalModel
                db = SessionLocal()
                sig = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
                if sig:
                    sig.executed = True
                    sig.trade_ticket = ticket
                    db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Error linking signal {signal_id} to ticket {ticket}: {e}")

        self.stats["trades_opened"] += 1
        self.stats["last_trade"] = {
            "ticket": ticket, "symbol": symbol, "direction": direction,
            "lot": lot, "entry": entry,
            "sl": sl, "tp": tp,
            "consensus": res.get("consensus"),
            "latency_ms": exec_latency_ms,
            "time": datetime.utcnow().isoformat(),
        }

        # نشر تقرير جودة التنفيذ للوكلاء الآخرين عبر Bus
        await self.bus.publish(BusMessage(
            topic  = "execution_telemetry",
            sender = self.name,
            data   = {
                "ticket": ticket, "symbol": symbol, "direction": direction,
                "latency_ms": exec_latency_ms, "spread_pips": spread,
                "fsm_regime": fsm.get("regime"), "confidence": vote_confidence,
            }
        ))

        await self.log(
            "INFO",
            f"✅ صفقة مفتوحة بسلام عبر البوابة | #{ticket} {direction} {symbol} "
            f"| Lot:{lot} | Entry:{entry:.5f} "
            f"| SL:{sl:.5f} | TP:{tp:.5f} "
            f"| Vote:{vote_confidence} | Latency:{exec_latency_ms}ms",
        )
