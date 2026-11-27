"""
============================================================
monitor_agent.py — الوكيل 3: مراقب الصفقات
============================================================
يراقب الصفقات المفتوحة كل ثانية → Break-even / Trail / Partial
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone
from loguru import logger

from agents.base_agent import BaseAgent
from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.signal_bus import BusMessage
from core.runtime_resilience import get_runtime_watchdog
from models.database import SessionLocal, Signal, Trade, TradeStatus
from config import AGENTS, STRATEGY, MAGIC_NUMBERS


class MonitorAgent(BaseAgent):
    """
    الوكيل الثالث — مراقب الصفقات المفتوحة
    ────────────────────────────────────────────────────
    ✅ يتحقق من جميع الصفقات المفتوحة كل ثانية
    ✅ Break-even عند ربح ≥ N نقطة
    ✅ Trailing Stop عند ربح ≥ N نقطة
    ✅ Partial Close عند المستويات 1/2/3
    ✅ إغلاق كامل عند Signal عكسي قوي
    ✅ تشغيل Smart Hedge عند DD > %
    ✅ إرسال تحذيرات DD لـ Bus
    """

    def __init__(self, mt5: MT5Connector):
        super().__init__("MonitorAgent", interval_sec=AGENTS["monitor_interval_sec"])
        self.mt5  = mt5
        self.risk = RiskManager()
        self._db_trade_cache: dict = {}
        self._basket_atr_cache: dict = {}
        self._untracked_state: dict = {}      # P5: حالة ذاكرية لصفقات النظام بلا سجل DB
        self._logged_once: set = set()        # P5: مفاتيح سجلات لمرة واحدة
        self._excursion_tracker: dict = {}    # P1 fix: تتبع MAE/MFE بالنقاط لكل تذكرة مفتوحة
        self._news_high_impact: bool = False  # حالة أخبار عالية التأثير
        self._stalled_reported: set = set()   # وكلاء أُبلغ عن توقف نبضاتهم (لتجنب تكرار السجل)

        self.stats.update({
            "modifications":   0,
            "partial_closes":  0,
            "emergency_closes":0,
            "last_check":      None,
            "unrealized_pnl":  {}
        })

        # الاشتراك في التنبيهات والتحديثات
        self.bus.subscribe("news_alert", self._on_news_alert)
        self.bus.subscribe("unrealized_pnl_update", self._on_unrealized_pnl_update)

    async def _on_unrealized_pnl_update(self, msg: BusMessage):
        """تحديث Unrealized P&L للصفقة المفتوحة"""
        data = msg.data
        ticket = data.get("ticket")
        pnl = data.get("unrealized_pnl")
        if ticket is not None and pnl is not None:
            self.stats["unrealized_pnl"][str(ticket)] = round(pnl, 2)

    async def _on_news_alert(self, msg):
        """استلام تنبيه خبر مهم — قرار إغلاق أو الاستمرار"""
        data   = msg.data
        impact = data.get("impact", "LOW")
        rec    = data.get("recommendation", "")
        if impact == "HIGH" and rec == "AVOID_NEW_TRADES":
            self._news_high_impact = True
            await self.log("WARNING",
                f"📰 خبر HIGH IMPACT — مراقبة مشددة للصفقات المفتوحة | "
                f"{data.get('headline','')[:50]}")
            # رفع التنبيه بعد 30 دقيقة
            import asyncio
            asyncio.get_event_loop().call_later(1800, lambda: setattr(self, '_news_high_impact', False))


    def _report_stalled_agents(self):
        """يسجّل الوكلاء الذين توقفت نبضاتهم (قراءة فقط — لا تأثير على التداول). مرة واحدة لكل توقف."""
        stalled = set(get_runtime_watchdog().check_stalled_agents()) - {self.name}
        for name in sorted(stalled - self._stalled_reported):
            logger.error(f"🧟 [Watchdog] الوكيل [{name}] متوقف: نبضاته تجاوزت الحد المسموح")
        for name in sorted(self._stalled_reported - stalled):
            logger.info(f"✅ [Watchdog] الوكيل [{name}] استأنف النبض")
        self._stalled_reported = stalled

    def _recover_mt5_if_needed(self):
        """يفحص اتصال MT5 الحي ويعيده ضمن قاطع الدائرة (حد المحاولات + التهدئة). لا أثر في وضع yfinance."""
        if not hasattr(self.mt5, "refresh_connection_state"):
            return  # موصل بلا دعم الاستعادة (غير MT5Connector)
        self.mt5.refresh_connection_state()
        result = get_runtime_watchdog().check_and_recover_mt5(self.mt5)
        if result["status"] not in ("HEALTHY", "COOLDOWN"):
            logger.warning(f"🔌 [Watchdog] MT5 recovery: {result}")

    async def run_cycle(self):
        """فحص جميع الصفقات المفتوحة"""
        self.stats["last_check"] = datetime.utcnow().isoformat()
        self._report_stalled_agents()
        self._recover_mt5_if_needed()

        # ── فحص DD ───────────────────────────────────────────────────
        account = self.mt5.get_account()
        dd_check = self.risk.check_dd_protection(account["balance"], account["equity"])

        if not dd_check["ok"]:
            await self.bus.emit_dd_alert(self.name, dd_check["dd_pct"], dd_check["mode"])
            self.mt5.close_all_positions(reason="Emergency_DD")
            self.stats["emergency_closes"] += 1
            await self.log("ERROR",
                f"🆘 EMERGENCY STOP! DD={dd_check['dd_pct']:.2f}% — جميع الصفقات مغلقة")
            return

        elif dd_check["mode"] in ("SOFT_STOP", "HEDGE_MODE"):
            await self.bus.emit_dd_alert(self.name, dd_check["dd_pct"], dd_check["mode"])
            if dd_check["mode"] == "HEDGE_MODE":
                await self._activate_hedge(account)

        # ── فحص هدف الربح الكلي ووقف الخسارة للسلة (Basket Profit / Stop Loss) ──
        positions = self.mt5.get_open_positions()
        filter_by_magic = STRATEGY.get("basket_filter_by_magic", True)
        system_magics = set(MAGIC_NUMBERS.values()) if filter_by_magic else None
        if system_magics is not None:
            basket_positions = [p for p in positions if p.get("magic") in system_magics]
            other_positions = [p for p in positions if p.get("magic") not in system_magics]
        else:
            basket_positions = list(positions)
            other_positions = []

        # سلة لكل رمز: هدف/وقف رمز لا يُغلق رموزاً أخرى ولا يتأثر بربحها أو خسارتها
        by_symbol: dict = {}
        for pos in basket_positions:
            by_symbol.setdefault(pos.get("symbol"), []).append(pos)

        closed_any = False
        for symbol in sorted(by_symbol, key=str):
            verdict = self._evaluate_symbol_basket(symbol, by_symbol[symbol])
            if verdict is None:
                continue
            reason, level, text = verdict
            await self.log(level, text)
            self._close_basket_positions(reason=reason, magic_numbers=system_magics, symbol=symbol)
            closed_any = True
        if closed_any:
            await self._sync_closed_trades(other_positions)
            return

        # ── مراقبة كل صفقة ───────────────────────────────────────────
        positions = self.mt5.get_open_positions()
        managed = skipped = 0
        for pos in positions:
            try:
                if await self._manage_position(pos):
                    managed += 1
                else:
                    skipped += 1
            except Exception as e:
                skipped += 1
                await self.log("ERROR", f"خطأ في مراقبة {pos.get('ticket')}: {e}")
        # تنظيف حالات الصفقات التي أُغلقت (لا تسرّب ذاكرة)
        live = {p["ticket"] for p in positions}
        for t in [t for t in self._untracked_state if t not in live]:
            self._untracked_state.pop(t, None)
        self._logged_once = {k for k in self._logged_once if k[0] in live}
        await self._heartbeat(positions, managed, skipped)

        # ── تحديث الصفقات المغلقة في DB ─────────────────────────────
        await self._sync_closed_trades(positions)

    def _close_basket_positions(self, reason: str, magic_numbers=None, symbol=None):
        """إغلاق صفقات سلة النظام (لرمز واحد) مع توافق عكسي إن كان الموصّل لا يقبل magic_numbers."""
        if magic_numbers is not None:
            try:
                self.mt5.close_all_positions(symbol=symbol, reason=reason, magic_numbers=magic_numbers)
                return
            except TypeError:
                pass
        self.mt5.close_all_positions(symbol=symbol, reason=reason)

    def _basket_entry_atr(self, positions: list):
        """ATR لحظة الدخول (سعر) من إشارة أقدم صفقة في السلة. مجمَّد عند الدخول فلا يتسع الوقف
        بتقلّب لاحق. None إن تعذّر (صفقة بلا ربط إشارة): تُستخدم العتبات القديمة بالدولار."""
        for pos in sorted(positions, key=lambda p: p.get("open_time", "")):
            ticket = pos["ticket"]
            if ticket in self._basket_atr_cache:
                return self._basket_atr_cache[ticket]
            db = None
            try:
                db = SessionLocal()
                sig = db.query(Signal).filter(Signal.trade_ticket == ticket).first()
                atr = float(sig.atr_value) if sig is not None and sig.atr_value else None
            except Exception:
                atr = None
            finally:
                if db is not None:
                    try:
                        db.close()
                    except Exception:
                        pass
            if atr and atr > 0:
                self._basket_atr_cache[ticket] = atr  # لا نخزّن None: ربط الإشارة قد يصل بعد فتح الصفقة
                return atr
        return None

    def _evaluate_symbol_basket(self, symbol, positions: list):
        """يقرّر هدف/وقف سلة رمز واحد. يُرجع (reason, log_level, text) أو None.

        مسار ATR (سلة باتجاه واحد وATR معروف): الحركة تُقاس من متوسط الدخول المرجَّح بالحجم،
          وقف = basket_sl_atr_mult × ATR، هدف = basket_rr × الوقف. وبما أن المسافتين من نفس نقطة الأساس
          والحجم نفسه، فالنسبة بالدولار = basket_rr بغضّ النظر عن عدد طبقات الشبكة.
          الهدف يتطلب أيضاً ربحاً صافياً > 0 (يشمل السبريد/السواب).
        المسار القديم (ATR مجهول أو سلة متحوِّطة باتجاهين): base_target_usd للهدف.
        سقف الدولار basket_max_loss_usd يسري دائماً كشبكة أمان أخيرة."""
        total_profit = sum(p.get("profit", 0.0) for p in positions)
        cap = abs(STRATEGY.get("basket_max_loss_usd", 20.0))
        n = len(positions)

        atr = self._basket_entry_atr(positions)
        directions = {p.get("type") for p in positions}
        if atr and len(directions) == 1:
            vol = sum(p.get("volume", 0.0) for p in positions)
            if vol > 0:
                avg_entry = sum(p["open_price"] * p.get("volume", 0.0) for p in positions) / vol
                sign = 1.0 if directions == {"BUY"} else -1.0
                move = (positions[0]["current_price"] - avg_entry) * sign
                sl_dist = STRATEGY.get("basket_sl_atr_mult", 2.5) * atr
                tp_dist = STRATEGY.get("basket_rr", 1.0) * sl_dist
                pip = MT5Connector.get_pip_size(symbol)
                eps = pip * 1e-6  # تفادي خطأ الفاصلة العائمة عند الحد بالضبط
                if move + eps >= tp_dist and total_profit > 0:
                    return ("Target_Reached", "SUCCESS",
                            f"🏆 Basket Target [ATR] {symbol} ({n} trades): +{move / pip:.1f} pips >= "
                            f"{tp_dist / pip:.1f} pips | ${total_profit:.2f}. Closing {symbol} basket...")
                if move - eps <= -sl_dist:
                    return ("Basket_SL_Hit", "WARNING",
                            f"🛑 Basket Stop [ATR] {symbol} ({n} trades): {move / pip:.1f} pips <= "
                            f"-{sl_dist / pip:.1f} pips | ${total_profit:.2f}. Closing {symbol} basket...")
        else:
            target_usd = STRATEGY.get("base_target_usd", 2.0)
            if total_profit >= target_usd:
                return ("Target_Reached", "SUCCESS",
                        f"🏆 Target Reached! {symbol} basket ({n} system trades): "
                        f"${total_profit:.2f} >= ${target_usd:.2f}. Closing {symbol} basket...")

        if total_profit <= -cap:
            return ("Basket_SL_Hit", "WARNING",
                    f"🛑 Basket Stop Loss Hit! {symbol} ({n} system trades): "
                    f"${total_profit:.2f} <= -${cap:.2f}. Closing {symbol} basket...")
        return None

    # ── P5: أدوات مساعدة (حالة الصفقة، تسجيل مرة واحدة، نبضة الحالة) ─────────
    class _State:
        """حالة إدارة صفقة (نسخة من DB أو ذاكرية للصفقات بلا سجل)."""
        breakeven_done = False
        partial_l1_done = False
        partial_l2_done = False
        partial_l3_done = False
        trailing_active = False
        fsm_regime = None

    def _log_once(self, key, level: str, text: str):
        """سجل لمرة واحدة لكل (تذكرة، سبب) — لا إغراق للسجل كل ثانية. يعيد coroutine أول مرة (يُنتظر) وإلا None."""
        if key in self._logged_once:
            return None
        self._logged_once.add(key)
        return self.log(level, text)

    def _resolve_state(self, pos: dict):
        """حالة الصفقة: من DB إن وُجدت، وإلا حالة ذاكرية إن كان magic لنظامنا، وإلا None."""
        ticket = pos["ticket"]
        st = self._get_db_trade(ticket)
        if st is not None:
            return st, "db"
        if ticket in self._untracked_state:
            return self._untracked_state[ticket], "memory"
        if STRATEGY.get("monitor_manage_untracked", True):
            own = set(MAGIC_NUMBERS.values())
            if pos.get("magic") in own:
                st = self._State()
                self._untracked_state[ticket] = st
                return st, "memory"
        return None, "none"

    async def _heartbeat(self, positions: list, managed: int, skipped: int):
        n = int(STRATEGY.get("monitor_heartbeat_cycles", 60) or 0)
        self.stats["positions_seen"] = len(positions)
        self.stats["positions_managed"] = managed
        self.stats["positions_skipped"] = skipped
        if n > 0 and self.iteration % n == 0:
            floating = sum(p.get("profit", 0.0) for p in positions)
            await self.log(
                "INFO",
                f"👁️ Monitor | مفتوحة={len(positions)} مُدارة={managed} مُتخطّاة={skipped} "
                f"عائم={floating:+.2f}$ | تعديلات={self.stats['modifications']} جزئي={self.stats['partial_closes']}",
            )

    async def _manage_position(self, pos: dict) -> bool:
        """إدارة صفقة واحدة مفتوحة. يعيد True إن أُدير (وُجدت حالة)، False إن تُخطّيت."""
        ticket    = pos["ticket"]
        symbol    = pos["symbol"]
        direction = pos["type"]
        entry     = pos["open_price"]
        current   = pos["current_price"]
        sl        = pos["sl"]
        profit    = pos["profit"]

        # حجم النقطة (P0 fix: دالة موحّدة تدعم XAUUSD وJPY)
        pip_size = MT5Connector.get_pip_size(symbol)

        # P1 fix: تحديث MAE / MFE اللحظي للصفقة المفتوحة
        cur_pips = ((current - entry) / pip_size if direction == "BUY" else (entry - current) / pip_size)
        exc = self._excursion_tracker.setdefault(ticket, {"mae_pips": 0.0, "mfe_pips": 0.0})
        if cur_pips < exc["mae_pips"]:
            exc["mae_pips"] = round(cur_pips, 2)
        if cur_pips > exc["mfe_pips"]:
            exc["mfe_pips"] = round(cur_pips, 2)

        # P5: كانت الصفقة بلا سجل DB تُهمَل بصمت، وuse_dynamic_sl=False يُوقف كل الإدارة بصمت.
        db_trade, source = self._resolve_state(pos)
        if db_trade is None:
            coro = self._log_once(
                (ticket, "untracked"), "WARNING",
                f"⚠️ صفقة #{ticket} {symbol} بلا سجل DB وmagic={pos.get('magic')} خارج MAGIC_NUMBERS — لا إدارة لها",
            )
            if coro:
                await coro
            return False

        be_on = bool(STRATEGY.get("monitor_breakeven_enabled", True))
        tr_on = bool(STRATEGY.get("monitor_trailing_enabled", True))
        pt_on = bool(STRATEGY.get("monitor_partial_enabled", False))
        if not (be_on or tr_on or pt_on):
            return True

        modified = False
        min_lot = float(STRATEGY.get("min_lot_size", 0.01))

        # ── 1. Break-even ─────────────────────────────────────────────
        if be_on and not db_trade.breakeven_done and self.risk.should_breakeven(direction, entry, current, pip_size):
            be_sl = entry + pip_size * 2 if direction == "BUY" else entry - pip_size * 2
            better = (be_sl > sl) if direction == "BUY" else (sl == 0 or be_sl < sl)  # P5: SELL بلا SL كان لا يُنقل أبداً
            if better:
                if self.mt5.modify_sl(ticket, be_sl):
                    db_trade.breakeven_done = True
                    modified = True
                    self.stats["modifications"] += 1
                    await self.log("INFO", f"🎯 Break-even | #{ticket} {symbol} SL → {be_sl:.5f}")
            else:
                db_trade.breakeven_done = True  # SL أفضل من التعادل أصلاً — لا إعادة محاولة كل ثانية
                modified = True

        # ── 2..4. Partial Close (L1/L2/L3) ────────────────────────────
        if pt_on:
            for level, label in ((1, "30%"), (2, "50%"), (3, "70%")):
                done_attr = f"partial_l{level}_done"
                prev_ok = level == 1 or getattr(db_trade, f"partial_l{level - 1}_done")
                if getattr(db_trade, done_attr) or not prev_ok:
                    continue
                if not self.risk.should_partial_close(level, direction, entry, current, pip_size):
                    continue
                ratio = self.risk.partial_close_ratio(level)
                if MT5Connector.compute_partial_volume(pos.get("volume", 0.0), ratio, min_lot, 0.01) is None:
                    coro = self._log_once(
                        (ticket, f"nosplit{level}"), "INFO",
                        f"⏭️ Partial L{level} متخطّى | #{ticket} {symbol} حجم {pos.get('volume')} لا يُقسَّم",
                    )
                    if coro:
                        await coro
                    continue
                if self.mt5.partial_close(ticket, ratio):
                    setattr(db_trade, done_attr, True)
                    modified = True
                    self.stats["partial_closes"] += 1
                    await self.log("INFO", f"📊 Partial L{level} ({label}) | #{ticket} {symbol}")

        # ── 5. Regime-Adaptive Trailing Stop ─────────────────────────
        if tr_on:
            profit_pips = cur_pips
            regime_val = db_trade.fsm_regime.value if getattr(db_trade, "fsm_regime", None) else "UNKNOWN"
            # تكييف عتبة ومسافة الـ Trailing حسب نظام السوق
            if regime_val == "STRONG_TREND":
                trail_threshold = STRATEGY.get("trail_activate_pips", 20) * 1.2
                trail_step = pip_size * 25
            elif regime_val in ("HIGH_VOL_RANGE", "CHAOS"):
                trail_threshold = STRATEGY.get("trail_activate_pips", 20) * 0.7  # حجز سريع للأرباح
                trail_step = pip_size * 12
            else:
                trail_threshold = STRATEGY.get("trail_activate_pips", 20)
                trail_step = pip_size * 18

            if profit_pips >= trail_threshold and not db_trade.trailing_active:
                db_trade.trailing_active = True
                modified = True

            if db_trade.trailing_active:
                new_trail_sl = self.risk.calc_trailing_sl(direction, current, trail_step, pip_size)
                # فقط نحرك SL في الاتجاه المربح
                if direction == "BUY" and new_trail_sl > sl + pip_size:
                    if self.mt5.modify_sl(ticket, new_trail_sl):
                        modified = True
                        self.stats["modifications"] += 1
                        await self.log("INFO", f"📈 Adaptive Trail | #{ticket} {symbol} ({regime_val}) SL → {new_trail_sl:.5f}")
                elif direction == "SELL" and (sl == 0 or new_trail_sl < sl - pip_size):
                    if self.mt5.modify_sl(ticket, new_trail_sl):
                        modified = True
                        self.stats["modifications"] += 1
                        await self.log("INFO", f"📉 Adaptive Trail | #{ticket} {symbol} ({regime_val}) SL → {new_trail_sl:.5f}")

        # ── حفظ التعديلات في DB (للصفقات ذات السجل فقط) ───────────────
        if modified and source == "db":
            db = None
            try:
                db = SessionLocal()
                db_obj = db.query(Trade).filter(Trade.ticket == ticket).first()
                if db_obj:
                    db_obj.partial_l1_done = db_trade.partial_l1_done
                    db_obj.partial_l2_done = db_trade.partial_l2_done
                    db_obj.partial_l3_done = db_trade.partial_l3_done
                    db_obj.breakeven_done  = db_trade.breakeven_done
                    db_obj.trailing_active = db_trade.trailing_active
                    db.commit()
            except Exception as e:
                logger.error(f"❌ خطأ في تحديث DB: {e}")
            finally:
                if db is not None:
                    db.close()
        return True

    async def _sync_closed_trades(self, open_positions: list):
        """تحديث الصفقات المغلقة في DB ونشر تقرير الإغلاق المفصل"""
        open_tickets = {p["ticket"] for p in open_positions}
        db = None
        try:
            db = SessionLocal()
            open_in_db = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            from datetime import timedelta
            for trade in open_in_db:
                if trade.ticket not in open_tickets:
                    trade.status   = TradeStatus.CLOSED
                    trade.closed_at = datetime.utcnow()
                    
                    deal_commission = 0.0
                    deal_swap = 0.0
                    # Fetch profit, commission, swap & close price for live trades from MT5 history
                    if not self.mt5._use_yfinance and self.mt5.connected:
                        try:
                            import MetaTrader5 as mt5_api
                            deals = mt5_api.history_deals_get(position=trade.ticket)
                            if not deals:
                                from_time = trade.opened_at - timedelta(hours=2)
                                to_time = datetime.utcnow() + timedelta(hours=2)
                                deals = mt5_api.history_deals_get(from_time, to_time)
                                if deals:
                                    deals = [d for d in deals if d.position == trade.ticket or d.ticket == trade.ticket]
                            
                            if deals:
                                deals = sorted(deals, key=lambda d: d.time)
                                deal_commission = float(sum(getattr(d, "commission", 0.0) for d in deals))
                                deal_swap = float(sum(getattr(d, "swap", 0.0) for d in deals))
                                total_profit = float(sum(d.profit for d in deals)) + deal_commission + deal_swap
                                exit_price = deals[-1].price
                                
                                trade.profit_usd = total_profit
                                trade.close_price = exit_price
                                await self.log("INFO", f"Synced closed trade #{trade.ticket} net profit from MT5: {total_profit:.2f}$ (comm={deal_commission:.2f}, swap={deal_swap:.2f})")
                            else:
                                logger.warning(f"No history deals found in MT5 for ticket #{trade.ticket}")
                        except Exception as history_err:
                            logger.error(f"Error querying MT5 deal history for ticket #{trade.ticket}: {history_err}")

                    db.commit()

                    pnl = float(trade.profit_usd or 0.0)
                    duration_sec = (trade.closed_at - trade.opened_at).total_seconds() if trade.opened_at else 0
                    regime_str = trade.fsm_regime.value if trade.fsm_regime else "UNKNOWN"
                    exc_stats = self._excursion_tracker.pop(trade.ticket, {"mae_pips": 0.0, "mfe_pips": 0.0})
                    tick_now = self.mt5.get_tick(trade.symbol)
                    spread_cost = float(tick_now.get("spread", 0.0)) if tick_now else 0.0

                    # نشر حدث إغلاق الصفقة الغني بالتكاليف وMAE/MFE للـ LearningAgent (P1 fix)
                    await self.bus.publish(BusMessage(
                        topic    = "trade_closed",
                        sender   = self.name,
                        priority = 1,
                        data     = {
                            "ticket": trade.ticket,
                            "symbol": trade.symbol,
                            "profit": pnl,
                            "direction": trade.type.value if trade.type else "BUY",
                            "regime": regime_str,
                            "confidence": trade.confidence,
                            "duration_sec": duration_sec,
                            "entry_price": getattr(trade, "entry_price", None),
                            "close_price": trade.close_price,
                            "commission": deal_commission,
                            "swap": deal_swap,
                            "spread_cost": spread_cost,
                            "mae_pips": exc_stats["mae_pips"],
                            "mfe_pips": exc_stats["mfe_pips"],
                        }
                    ))
                    await self.log("INFO", f"🔒 صفقة مغلقة | #{trade.ticket} {trade.symbol} ({regime_str}) | Profit: {pnl:+.2f}$ | MAE:{exc_stats['mae_pips']} MFE:{exc_stats['mfe_pips']} ({duration_sec:.0f}s)")
                    # مسح من الـ cache
                    self._db_trade_cache.pop(trade.ticket, None)
                    self._untracked_state.pop(trade.ticket, None)
        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة DB: {e}")
        finally:
            if db is not None:
                db.close()

    async def _activate_hedge(self, account: dict):
        """تفعيل Smart Hedge عند DD > hedge_dd_percent"""
        positions = self.mt5.get_open_positions()
        for pos in positions:
            if pos["profit"] < 0:
                # فتح صفقة معاكسة بحجم أصغر للتحوط
                hedge_lot = round(pos["volume"] * STRATEGY.get("hedge_lot_factor", 0.7), 2)
                opp_dir   = "SELL" if pos["type"] == "BUY" else "BUY"
                tick = self.mt5.get_tick(pos["symbol"])
                if tick and hedge_lot >= 0.01:
                    entry = tick["ask"] if opp_dir == "BUY" else tick["bid"]
                    # P1 fix: protect hedge with emergency server-side SL instead of sl=0.0
                    pip_size = MT5Connector.get_pip_size(pos["symbol"])
                    digits = self.mt5.get_digits(pos["symbol"])
                    sl_dist = pip_size * 50.0
                    hedge_sl = round(entry - sl_dist, digits) if opp_dir == "BUY" else round(entry + sl_dist, digits)
                    result = self.mt5.open_trade(
                        symbol  = pos["symbol"],
                        direction = opp_dir,
                        lot     = hedge_lot,
                        sl      = hedge_sl,
                        tp      = 0.0,
                        comment = "AI_Hedge",
                    )
                    if result.get("success"):
                        await self.log("WARNING",
                            f"🛡️ Smart Hedge | {opp_dir} {pos['symbol']} Lot:{hedge_lot}")
                    else:
                        await self.log("ERROR",
                            f"❌ لم يُفتح التحوط {opp_dir} {pos['symbol']}: {result.get('error')}")
                    break  # تحوط واحد فقط

    def _get_db_trade(self, ticket: int):
        """قراءة بيانات الصفقة من DB (مع كاش)"""
        if ticket in self._db_trade_cache:
            return self._db_trade_cache[ticket]
        db = None
        try:
            db = SessionLocal()
            trade = db.query(Trade).filter(Trade.ticket == ticket).first()
            if trade:
                # نسخ القيم قبل إغلاق الجلسة
                class TradeState:
                    pass
                ts = TradeState()
                ts.breakeven_done  = trade.breakeven_done  or False
                ts.partial_l1_done = trade.partial_l1_done or False
                ts.partial_l2_done = trade.partial_l2_done or False
                ts.partial_l3_done = trade.partial_l3_done or False
                ts.trailing_active = trade.trailing_active or False
                self._db_trade_cache[ticket] = ts
                return ts
        except Exception as e:
            logger.error(f"❌ خطأ في قراءة DB: {e}")
        finally:
            if db:
                db.close()
        return None
