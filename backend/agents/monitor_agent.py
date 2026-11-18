"""
============================================================
monitor_agent.py — الوكيل 3: مراقب الصفقات
============================================================
يراقب الصفقات المفتوحة كل ثانية → Break-even / Trail / Partial
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from agents.base_agent import BaseAgent
from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager
from core.signal_bus import BusMessage
from models.database import SessionLocal, Trade, TradeStatus
from config import AGENTS, STRATEGY


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
        self._news_high_impact: bool = False  # حالة أخبار عالية التأثير
        self._atr_cache: dict = {}  # رمز → (وقت الجلب، ATR أو None) لوقف السلة بالـATR

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


    async def run_cycle(self):
        """فحص جميع الصفقات المفتوحة"""
        self.stats["last_check"] = datetime.utcnow().isoformat()

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
        total_profit = sum(pos.get("profit", 0.0) for pos in positions)
        target_usd = STRATEGY.get("base_target_usd", 2.0)
        basket_max_loss_usd = STRATEGY.get("basket_max_loss_usd", 20.0)

        if len(positions) > 0:
            if total_profit >= target_usd:
                await self.log("SUCCESS", f"🏆 Target Reached! Basket Profit: ${total_profit:.2f} >= ${target_usd:.2f}. Closing all...")
                self.mt5.close_all_positions(reason="Target_Reached")
                await self._sync_closed_trades([])
                return
            elif total_profit <= -abs(basket_max_loss_usd):
                await self.log("WARNING", f"🛑 Basket Stop Loss Hit! Loss: ${total_profit:.2f} <= -${basket_max_loss_usd:.2f}. Closing all...")
                self.mt5.close_all_positions(reason="Basket_SL_Hit")
                await self._sync_closed_trades([])
                return

            # IMPROVEMENT_PLAN §0: وقف السلة بالـATR (يعمل إلى جانب وقف الدولار أعلاه)
            if await self._check_basket_atr_stop(positions):
                return

        # ── مراقبة كل صفقة ───────────────────────────────────────────
        positions = self.mt5.get_open_positions()
        for pos in positions:
            try:
                await self._manage_position(pos)
            except Exception as e:
                await self.log("ERROR", f"خطأ في مراقبة {pos.get('ticket')}: {e}")

        # ── تحديث الصفقات المغلقة في DB ─────────────────────────────
        await self._sync_closed_trades(positions)

    # ── وقف خسارة السلة بالـATR (IMPROVEMENT_PLAN §0) ────────────────
    # الوقف لكل (رمز، اتجاه) = أعمق طبقة في الشبكة ∓ ATR × المضاعِف. ATR = متوسط المدى
    # الحقيقي لآخر 14 شمعة M15 مغلقة (نفس تعريف ATR في مجلس الوكلاء). أقصى خسارة عند الوقف
    # = Σ حجم_الطبقة × |دخولها − الوقف| × قيمة وحدة السعر (من symbol_info) وتُسجَّل عند الإغلاق.
    # إن تعذّر حساب ATR يبقى وقف الدولار (basket_max_loss_usd) هو الحماية الوحيدة لتلك الدورة.
    BASKET_ATR_PERIOD    = 14
    BASKET_ATR_CACHE_SEC = 60.0
    BASKET_ATR_DEFAULT_K = 2.5

    @staticmethod
    def _pip_size(symbol: str) -> float:
        """حجم البيب: 0.01 للين و0.1 للذهب و0.0001 للباقي (اتفاقية مجلس الوكلاء نفسها)."""
        return 0.01 if "JPY" in symbol else (0.1 if "XAU" in symbol else 0.0001)

    @staticmethod
    def _atr_from_rates(rates, period: int) -> Optional[float]:
        """ATR بسيط (متوسط المدى الحقيقي) على آخر period شمعة؛ None إن لم تكفِ البيانات."""
        if rates is None or len(rates) < period + 1:
            return None
        highs  = [float(r["high"])  for r in rates]
        lows   = [float(r["low"])   for r in rates]
        closes = [float(r["close"]) for r in rates]
        if not all(math.isfinite(v) for v in highs + lows + closes):
            return None  # NaN داخل max() يُتجاهَل بصمت فيُخرج ATR يبدو سليماً
        true_ranges = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            for i in range(1, len(closes))
        ][-period:]
        if len(true_ranges) < period:
            return None
        atr = sum(true_ranges) / period
        return atr if math.isfinite(atr) and atr > 0 else None

    def _basket_atr(self, symbol: str) -> Optional[float]:
        """ATR(M15) للرمز على شموع مغلقة، مخزَّن 60 ثانية (النتيجة الفاشلة تُخزَّن أيضاً)."""
        now = time.monotonic()
        hit = self._atr_cache.get(symbol)
        if hit is not None and now - hit[0] < self.BASKET_ATR_CACHE_SEC:
            return hit[1]
        atr = None
        try:
            import MetaTrader5 as mt5_api
            rates = mt5_api.copy_rates_from_pos(
                symbol, mt5_api.TIMEFRAME_M15, 1, self.BASKET_ATR_PERIOD + 1
            )
            atr = self._atr_from_rates(rates, self.BASKET_ATR_PERIOD)
        except Exception as e:
            logger.warning(f"⚠️ تعذّر جلب شموع M15 لـ{symbol}: {e}")
        if atr is None:
            logger.warning(f"⚠️ ATR غير متاح لـ{symbol} — وقف السلة بالـATR معطَّل لهذه الدورة (وقف الدولار فعّال)")
        self._atr_cache[symbol] = (now, atr)
        return atr

    @staticmethod
    def _value_per_price_unit(symbol: str) -> Optional[float]:
        """قيمة تحرك السعر بوحدة واحدة للوت الواحد بالدولار (من symbol_info)، أو None."""
        try:
            import MetaTrader5 as mt5_api
            info = mt5_api.symbol_info(symbol)
            if info is not None and info.trade_tick_size > 0 and info.trade_tick_value > 0:
                return float(info.trade_tick_value) / float(info.trade_tick_size)
        except Exception as e:
            logger.warning(f"⚠️ تعذّر قراءة symbol_info لـ{symbol}: {e}")
        return None

    @staticmethod
    def _basket_atr_stop(positions: list, atr: float, k: float) -> dict:
        """وقف سلة رمز واحد واتجاه واحد: أعمق طبقة ∓ k × ATR. (الأعمق = الأدنى للشراء، الأعلى للبيع)"""
        buy     = positions[0]["type"] == "BUY"
        entries = [float(p["open_price"]) for p in positions]
        dist    = k * atr
        if buy:
            stop     = min(entries) - dist
            price    = min(float(p["current_price"]) for p in positions)
            breached = price <= stop
        else:
            stop     = max(entries) + dist
            price    = max(float(p["current_price"]) for p in positions)
            breached = price >= stop
        lot_distance = sum(float(p["volume"]) * abs(float(p["open_price"]) - stop) for p in positions)
        return {"stop": stop, "price": price, "breached": breached,
                "layers": len(positions), "lot_distance": lot_distance}

    async def _check_basket_atr_stop(self, positions: list) -> bool:
        """يغلق كل الصفقات إن اخترقت سلة (رمز، اتجاه) وقفها بالـATR. يعيد True عند الإغلاق."""
        k = STRATEGY.get("basket_sl_atr_multiplier", self.BASKET_ATR_DEFAULT_K)
        if isinstance(k, bool) or not isinstance(k, (int, float)) or not k > 0:
            k = self.BASKET_ATR_DEFAULT_K  # الوقف لا يُعطَّل بقيمة غير صالحة

        groups: dict = {}
        for pos in positions:
            groups.setdefault((pos["symbol"], pos["type"]), []).append(pos)

        for (symbol, direction), group in groups.items():
            atr = self._basket_atr(symbol)
            if atr is None:
                continue
            res = self._basket_atr_stop(group, atr, k)
            if not res["breached"]:
                continue
            value = self._value_per_price_unit(symbol)
            loss_txt = f"${res['lot_distance'] * value:.2f}" if value else "n/a"
            await self.log("WARNING",
                f"🛑 Basket ATR Stop Hit! {symbol} {direction} ×{res['layers']} | "
                f"السعر {res['price']:.5f} تجاوز الوقف {res['stop']:.5f} (ATR {atr:.5f} × {k}) | "
                f"أقصى خسارة عند الوقف ≈ {loss_txt}. Closing all...")
            self.mt5.close_all_positions(reason="Basket_ATR_SL_Hit")
            await self._sync_closed_trades([])
            return True
        return False

    async def _manage_position(self, pos: dict):
        """إدارة صفقة واحدة مفتوحة"""
        ticket    = pos["ticket"]
        symbol    = pos["symbol"]
        direction = pos["type"]
        entry     = pos["open_price"]
        current   = pos["current_price"]
        sl        = pos["sl"]
        profit    = pos["profit"]

        # حجم النقطة
        pip_size = self._pip_size(symbol)

        # الحصول على بيانات DB
        db_trade = self._get_db_trade(ticket)
        if db_trade is None:
            return

        if not STRATEGY.get("use_dynamic_sl", True):
            # صفقات بدون استوب وهدف — تخطي التعديلات الفردية للصفقة
            return

        modified = False

        # ── 1. Break-even ─────────────────────────────────────────────
        if not db_trade.breakeven_done and self.risk.should_breakeven(direction, entry, current, pip_size):
            be_sl = entry + pip_size * 2 if direction == "BUY" else entry - pip_size * 2
            if (direction == "BUY" and be_sl > sl) or (direction == "SELL" and be_sl < sl):
                if self.mt5.modify_sl(ticket, be_sl):
                    db_trade.breakeven_done = True
                    modified = True
                    self.stats["modifications"] += 1
                    await self.log("INFO", f"🎯 Break-even | #{ticket} {symbol} SL → {be_sl:.5f}")

        # ── 2. Partial Close Level 1 ──────────────────────────────────
        if not db_trade.partial_l1_done and self.risk.should_partial_close(1, direction, entry, current, pip_size):
            ratio = self.risk.partial_close_ratio(1)
            if self.mt5.partial_close(ticket, ratio):
                db_trade.partial_l1_done = True
                modified = True
                self.stats["partial_closes"] += 1
                await self.log("INFO", f"📊 Partial L1 (30%) | #{ticket} {symbol}")

        # ── 3. Partial Close Level 2 ──────────────────────────────────
        if (db_trade.partial_l1_done and not db_trade.partial_l2_done and
                self.risk.should_partial_close(2, direction, entry, current, pip_size)):
            ratio = self.risk.partial_close_ratio(2)
            if self.mt5.partial_close(ticket, ratio):
                db_trade.partial_l2_done = True
                modified = True
                self.stats["partial_closes"] += 1
                await self.log("INFO", f"📊 Partial L2 (50%) | #{ticket} {symbol}")

        # ── 4. Partial Close Level 3 ──────────────────────────────────
        if (db_trade.partial_l2_done and not db_trade.partial_l3_done and
                self.risk.should_partial_close(3, direction, entry, current, pip_size)):
            ratio = self.risk.partial_close_ratio(3)
            if self.mt5.partial_close(ticket, ratio):
                db_trade.partial_l3_done = True
                modified = True
                self.stats["partial_closes"] += 1
                await self.log("INFO", f"📊 Partial L3 (70%) | #{ticket} {symbol}")

        # ── 5. Regime-Adaptive Trailing Stop ─────────────────────────
        profit_pips = ((current - entry) / pip_size if direction == "BUY"
                       else (entry - current) / pip_size)

        regime_val = db_trade.fsm_regime.value if db_trade.fsm_regime else "UNKNOWN"
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

        if profit_pips >= trail_threshold:
            db_trade.trailing_active = True

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

        # ── حفظ التعديلات في DB ───────────────────────────────────────
        if modified:
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
                db.close()

    async def _sync_closed_trades(self, open_positions: list):
        """تحديث الصفقات المغلقة في DB ونشر تقرير الإغلاق المفصل"""
        open_tickets = {p["ticket"] for p in open_positions}
        try:
            db = SessionLocal()
            open_in_db = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            from datetime import timedelta
            for trade in open_in_db:
                if trade.ticket not in open_tickets:
                    trade.status   = TradeStatus.CLOSED
                    trade.closed_at = datetime.utcnow()
                    
                    # Fetch profit & close price for live trades from MT5 history
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
                                total_profit = sum(d.profit for d in deals)
                                exit_price = deals[-1].price
                                
                                trade.profit_usd = total_profit
                                trade.close_price = exit_price
                                await self.log("INFO", f"Synced closed trade #{trade.ticket} profit from MT5: {total_profit:.2f}$")
                            else:
                                logger.warning(f"No history deals found in MT5 for ticket #{trade.ticket}")
                        except Exception as history_err:
                            logger.error(f"Error querying MT5 deal history for ticket #{trade.ticket}: {history_err}")

                    db.commit()

                    pnl = float(trade.profit_usd or 0.0)
                    duration_sec = (trade.closed_at - trade.opened_at).total_seconds() if trade.opened_at else 0
                    regime_str = trade.fsm_regime.value if trade.fsm_regime else "UNKNOWN"

                    # نشر حدث إغلاق الصفقة الغني بالبيانات للـ LearningAgent
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
                            "entry_price": trade.open_price,
                            "close_price": trade.close_price,
                        }
                    ))
                    await self.log("INFO", f"🔒 صفقة مغلقة | #{trade.ticket} {trade.symbol} ({regime_str}) | Profit: {pnl:+.2f}$ ({duration_sec:.0f}s)")
                    # مسح من الـ cache
                    self._db_trade_cache.pop(trade.ticket, None)
        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة DB: {e}")
        finally:
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
                    self.mt5.open_trade(
                        symbol  = pos["symbol"],
                        direction = opp_dir,
                        lot     = hedge_lot,
                        sl      = 0.0,
                        tp      = 0.0,
                        comment = "AI_Hedge",
                    )
                    await self.log("WARNING",
                        f"🛡️ Smart Hedge | {opp_dir} {pos['symbol']} Lot:{hedge_lot}")
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
