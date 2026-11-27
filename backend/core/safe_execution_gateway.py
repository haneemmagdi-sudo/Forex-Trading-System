"""
============================================================
safe_execution_gateway.py — بوابة التنفيذ الآمن
============================================================
بوابة متكاملة تربط الـ Orchestrator بالتنفيذ الفعلي في MT5 مع تطبيق صمام أمان متعدد الطبقات.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from loguru import logger

from core.mt5_connector import MT5Connector
from core.risk_manager import RiskManager, TradeParams
from core.signal_bus import get_bus, BusMessage
from config import MAGIC_NUMBERS
from ml_models.orchestrator import AntigravityOrchestrator, OrchestratorSignal, Action
from models.database import SessionLocal, Trade, TradeType, TradeStatus, FSMRegime

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("⚠️ MetaTrader5 library is not available in current python context.")


class SafeExecutionGateway:
    """
    SafeExecutionGateway — بوابة التنفيذ الآمن
    ────────────────────────────────────────────────────
    ✅ ترتبط بالـ Orchestrator لدمج قرار الـ 4 نماذج
    ✅ Risk Validation: حجم اللوت الديناميكي (أقصى مخاطرة 1.5% من Equity) مع فحص DD و Margin
    ✅ Slippage Check: فحص سبريد MT5 مباشرة (بدون Hyperliquid — إصلاح IMPROVEMENT_PLAN §0)
    ✅ Order Routing: إرسال الصفقات الحقيقية عبر MetaTrader5.order_send مع SL/TP ديناميكي
    ✅ Monitoring: مراقبة حالة الصفقة والـ Unrealized P&L وتحديث MonitorAgent
    """

    def __init__(self, mt5_connector: MT5Connector, orchestrator: AntigravityOrchestrator = None, risk_manager: RiskManager = None):
        self.mt5 = mt5_connector
        self.orchestrator = orchestrator or AntigravityOrchestrator()
        self.risk = risk_manager or RiskManager()
        self.bus = get_bus()
        self._active_tasks: Dict[int, asyncio.Task] = {}

    async def execute_signal(
        self,
        symbol: str,
        rf_prediction: int,
        lstm_delta: float,
        dqn_q_values: list,
        sentiment_score: float,
        fsm_regime: str = "LOW_VOL_RANGE",
        direction: str = None,
        vote_confidence: float = None,
        signal_id: int = None,
        meta_probability: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        max_lot: Optional[float] = None,
        source: Optional[str] = None,
    ) -> dict:
        """
        تقييم الإشارة عبر الـ Orchestrator وتمريرها للتنفيذ الآمن

        لا تُمرَّر تنبؤات نماذج مُختلقة: تقييم الـ ensemble يُنفَّذ فقط عند
        توفّر مخرجات حقيقية للنماذج الأربعة. وإلا تُتخطى البوابة ويُستخدم
        الاتجاه القادم من تصويت المحلل مع تسجيل ثقته الحقيقية.
        (سابقاً كانت تُمرَّر قيم ثابتة فتُنتج ثقة وهمية 82.49% دائماً.)

        للأوامر اليدوية التي وافق عليها المستخدم:
        stop_loss / take_profit تحلّ محل المستويات المحسوبة بعد التحقق من جهتها،
        وmax_lot سقف لا يتجاوزه اللوت المحسوب، وsource يميّز مصدر الأمر.
        """
        ensemble_available = all(
            value is not None
            for value in (rf_prediction, lstm_delta, dqn_q_values, sentiment_score)
        )

        if ensemble_available:
            # ── 1. تقييم الإشارة بالـ Orchestrator ──
            signal: OrchestratorSignal = self.orchestrator.evaluate(
                rf_prediction=rf_prediction,
                lstm_delta=lstm_delta,
                dqn_q_values=dqn_q_values,
                sentiment_score=sentiment_score,
                metadata={"symbol": symbol}
            )

            if not signal.is_actionable:
                logger.info(f"[SafeExecutionGateway] Signal for {symbol} is HOLD ({signal.confidence:.1f}%). Execution locked.")
                return {"success": False, "reason": f"HOLD state enforced ({signal.summary()})"}

            direction = signal.action.value  # "BUY" or "SELL"
            consensus_confidence = float(signal.confidence)
            consensus_summary = signal.summary()
            logger.info(f"[SafeExecutionGateway] Activating execution for {direction} {symbol} | Confidence: {consensus_confidence:.1f}%")
        else:
            # لا توجد نماذج مُدرَّبة: لا نختلق تنبؤات ولا ثقة، نعتمد قرار التحليل
            if direction not in ("BUY", "SELL"):
                return {
                    "success": False,
                    "reason": "No direction supplied and no trained model outputs are available",
                }
            consensus_confidence = vote_confidence
            consensus_summary = None
            logger.info(
                f"[SafeExecutionGateway] Ensemble gate SKIPPED for {symbol} "
                f"(no trained model outputs) | direction from vote: {direction} | "
                f"vote confidence: {vote_confidence}"
            )

        # ── 2. Risk Validation ──
        account = self.mt5.get_account()
        if not account or "equity" not in account:
            return {"success": False, "reason": "Could not fetch MT5 account info"}

        balance = account.get("balance", 0.0)
        equity = account.get("equity", 0.0)
        free_margin = account.get("free_margin", 0.0)

        # 2.1 Max Drawdown Check
        dd_check = self.risk.check_dd_protection(balance, equity)
        if not dd_check["ok"]:
            if dd_check.get("mode") == "EMERGENCY_STOP":
                self.mt5.close_all_positions(reason="Gateway_Emergency_Stop")
            return {"success": False, "reason": f"Emergency Stop! Drawdown limit reached: {dd_check['dd_pct']:.2f}%"}

        # 2.2 Slippage Check via Hyperliquid
        slippage_ok, slip_msg = await self._check_slippage(symbol, direction)
        if not slippage_ok:
            return {"success": False, "reason": f"Slippage validation failed: {slip_msg}"}

        # 2.3 Calculate Dynamic Lot Size & Volatility-based SL/TP
        tick = self.mt5.get_tick(symbol)
        if not tick:
            return {"success": False, "reason": f"Failed to get current tick for {symbol}"}
        entry_price = tick["ask"] if direction == "BUY" else tick["bid"]

        # Fetch H1 OHLCV to compute ATR
        df = self.mt5.get_ohlcv(symbol, bars=100)
        if df is None or df.empty:
            return {"success": False, "reason": f"Failed to fetch OHLCV bars for {symbol}"}

        from core.indicators import TechnicalIndicators
        ind_calc = TechnicalIndicators()
        iv = ind_calc.calculate(df, tick.get("spread", 0))
        atr = iv.atr if (iv and iv.is_valid()) else 0.0

        if atr <= 0:
            # Fallback based on typical price fraction
            atr = entry_price * 0.0015

        digits = self.mt5.get_digits(symbol)
        pip_value = self.mt5.get_pip_value(symbol)
        
        params = self.risk.calc_trade_params(
            symbol=symbol,
            direction=direction,
            entry=entry_price,
            atr=atr,
            balance=balance,
            pip_value=pip_value,
            digits=digits
        )

        if not params.valid:
            return {"success": False, "reason": f"Risk params calculation failed: {params.reason}"}

        # أمر يدوي: مستويات المستخدم، بشرط أن تقع في الجهة الصحيحة من السعر الحالي
        if stop_loss is not None:
            sign = 1 if direction == "BUY" else -1
            if (entry_price - stop_loss) * sign <= 0:
                return {"success": False, "reason": f"Stop loss {stop_loss} is on the wrong side of the current price {entry_price} for {direction}"}
            if take_profit and (take_profit - entry_price) * sign <= 0:
                return {"success": False, "reason": f"Take profit {take_profit} is on the wrong side of the current price {entry_price} for {direction}"}
            pip_size = MT5Connector.get_pip_size(symbol, digits=digits)
            params.sl_price = round(stop_loss, digits)
            params.tp_price = round(take_profit, digits) if take_profit else 0.0
            params.sl_pips = round(abs(entry_price - stop_loss) / pip_size, 1)
            params.tp_pips = round(abs(take_profit - entry_price) / pip_size, 1) if take_profit else 0.0

        lot_size = params.lot_size

        # P2 fix: Apply Calibrated Kelly Sizing ONLY when a genuine calibrated meta_probability is available
        # (Never feed raw uncalibrated voting percentage into CalibratedKellySizer)
        if not self.risk.cfg.get("manual_lot_enabled", False) and meta_probability is not None:
            try:
                from quant_core.meta_model import CalibratedKellySizer
                sizer = CalibratedKellySizer()
                p_win = float(np.clip(meta_probability, 0.01, 0.99))
                rr = (params.tp_pips / params.sl_pips) if params.sl_pips > 0 else 1.33
                kelly_mult = sizer.compute_size_multiplier(p_win, rr)
                lot_size = lot_size * kelly_mult
                logger.info(
                    f"[SafeExecutionGateway] Calibrated Kelly sizing applied (Meta-Model): "
                    f"P(Win)={p_win:.3f}, Mult={kelly_mult:.2f}x -> Lot(pre-cap)={lot_size:.2f}"
                )
            except Exception as k_err:
                logger.debug(f"[SafeExecutionGateway] Kelly multiplier skipped: {k_err}")

        # Hard 1.5% Equity Risk Cap enforced AFTER Kelly scaling so risk never exceeds 1.5%
        if not self.risk.cfg.get("manual_lot_enabled", False):
            max_risk_usd = equity * 0.015
            if params.sl_pips > 0 and pip_value > 0:
                equity_cap_lot = max_risk_usd / (params.sl_pips * pip_value)
                lot_size = min(lot_size, equity_cap_lot)

        lot_size = round(max(0.01, min(lot_size, 100.0)), 2)
        if max_lot is not None:
            lot_size = max(0.01, min(lot_size, int(max_lot * 100 + 1e-9) / 100))

        # 2.4 Available Margin Check
        margin_required = self._calculate_required_margin(symbol, lot_size, entry_price, direction, account)
        if margin_required > free_margin:
            return {
                "success": False,
                "reason": f"Insufficient margin. Required: ${margin_required:.2f}, Available: ${free_margin:.2f}"
            }

        # ── 3. Order Routing via MetaTrader5 ──
        comment = f"SG_{direction}_{signal_id}" if signal_id else f"SG_{direction}"
        if source:
            comment = f"{source}_{direction}"
        result = self._route_order(symbol, direction, lot_size, params.sl_price, params.tp_price, entry_price, digits, comment=comment)
        if not result["success"]:
            return {"success": False, "reason": f"Routing failed: {result.get('error')}"}

        ticket = result["ticket"]

        # Save trade to database
        self._save_trade_to_db(ticket, symbol, direction, lot_size, entry_price, params.sl_price, params.tp_price, fsm_regime, consensus_confidence, comment=comment)
        # P1 fix: insert OPEN trade vector with ticket so LearningAgent.update_outcome_by_ticket() closes the RAG loop
        # الأوامر اليدوية لا تدخل ذاكرة محرك التصويت: لا regime ولا ثقة مقيسة لها
        if not source:
            self._record_trade_vector(
                ticket=ticket, symbol=symbol, direction=direction, fsm_regime=fsm_regime,
                confidence=consensus_confidence, sl_pips=params.sl_pips, tp1_pips=params.tp_pips,
                spread_pips=tick.get("spread", 0.0), atr=atr, entry_price=entry_price,
                mode=result.get("mode", "LIVE"),
            )

        # Emit trade_opened event
        await self.bus.emit_trade_opened(
            sender="SafeExecutionGateway",
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            lot=lot_size,
            entry=entry_price,
            sl=params.sl_price,
            tp=params.tp_price
        )

        # ── 4. Monitoring (Trace loop) ──
        mode = result.get("mode", "LIVE")
        task = asyncio.create_task(self._trace_position_loop(ticket, symbol, direction, entry_price, params.sl_price, params.tp_price, lot_size, mode))
        self._active_tasks[ticket] = task

        return {
            "success": True,
            "ticket": ticket,
            "price": entry_price,
            "lot": lot_size,
            "sl": params.sl_price,
            "tp": params.tp_price,
            "mode": mode,
            "consensus": consensus_summary,
            "confidence": consensus_confidence,
            "ensemble": "available" if ensemble_available else "skipped",
        }

    async def _check_slippage(self, symbol: str, direction: str) -> Tuple[bool, str]:
        """
        فحص السبريد المحلي من MT5 فقط — بدون استدعاء Hyperliquid.

        IMPROVEMENT_PLAN §0: إزالة فحص Hyperliquid لأزواج الفوركس.
        Hyperliquid منصة كريبتو ولا تتطابق أسعارها مع أسعار الفوركس،
        مما كان يتسبب في رفض صفقات بذريعة «انزلاق» وهمي.

        الآن: نفحص السبريد الحالي من MT5 مباشرة ونقارنه بحد الرمز.
        """
        try:
            tick = self.mt5.get_tick(symbol)
            if not tick:
                # fail-closed: إذا فشل جلب السعر نرفض الصفقة
                logger.warning(f"[SafeExecutionGateway] Cannot fetch tick for {symbol} — slippage check FAIL-CLOSED")
                return False, f"Cannot fetch tick for {symbol}"

            spread = tick.get("spread", 0.0)
            # حد السبريد لكل رمز من المصدر الموحد config.STRATEGY
            spread_limits = self.risk.cfg.get("symbol_spread_limits", {})
            max_spread = spread_limits.get(symbol, self.risk.cfg.get("max_spread_pips", 4.0))
            if spread > max_spread:
                return False, f"Spread too wide for {symbol}: {spread:.1f} pts (max: {max_spread})"

            logger.debug(f"[SafeExecutionGateway] Spread OK for {symbol}: {spread:.1f} pts (max: {max_spread})")
            return True, "Spread within limits"

        except Exception as e:
            logger.error(f"[SafeExecutionGateway] Slippage check exception for {symbol}: {e}")
            # fail-closed: كل استثناء يوقف الصفقة
            return False, f"Slippage check exception: {e}"

    def _calculate_required_margin(self, symbol: str, lot_size: float, entry_price: float, direction: str, account: dict) -> float:
        """
        Calculate required margin for the trade
        """
        if not self.mt5._use_yfinance and MT5_AVAILABLE and self.mt5.connected:
            order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
            margin = mt5.order_calc_margin(order_type, symbol, lot_size, entry_price)
            if margin is not None:
                return float(margin)

        # Fallback estimation
        leverage = account.get("leverage", 100)
        contract_size = 100000.0  # Default Forex standard lot
        if "BTC" in symbol:
            contract_size = 1.0
        elif "ETH" in symbol:
            contract_size = 1.0
        
        return (lot_size * contract_size * entry_price) / leverage

    def _route_order(self, symbol: str, direction: str, lot: float, sl: float, tp: float, entry_price: float, digits: int, comment: str = None) -> dict:
        """
        Use MetaTrader5.order_send to route the atomic execution payload
        """
        trade_comment = comment or f"SG_{direction}"
        if self.mt5._use_yfinance:
            import random
            ticket = random.randint(1000000, 9999999)
            return {
                "success": True,
                "ticket": ticket,
                "price": entry_price,
                "mode": "PAPER"
            }

        if not MT5_AVAILABLE or not self.mt5.connected:
            return {"success": False, "error": "MT5 is not connected"}

        blocked = self.mt5.entry_block_reason()
        if blocked:
            return {"success": False, "error": blocked}

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return {"success": False, "error": f"Symbol {symbol} not found"}

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        filling_mode = sym_info.filling_mode
        if filling_mode & 1:
            filling = mt5.ORDER_FILLING_FOK
        elif filling_mode & 2:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot,
            "type":         order_type,
            "price":        entry_price,
            "sl":           round(sl, digits),
            "tp":           round(tp, digits),
            "deviation":    10,
            "magic":        MAGIC_NUMBERS.get("live_engine", 112345),
            "comment":      trade_comment,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            return {"success": False, "error": f"order_send failed: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": f"order_send rejected: {result.retcode} - {result.comment}"}

        logger.success(f"[SafeExecutionGateway] Live Order Sent successfully | Ticket: {result.order}")
        return {"success": True, "ticket": result.order, "price": result.price, "mode": "LIVE"}

    def _record_trade_vector(
        self, ticket: int, symbol: str, direction: str, fsm_regime: str,
        confidence: Optional[float], sl_pips: float, tp1_pips: float,
        spread_pips: float, atr: float, entry_price: float, mode: str,
    ) -> None:
        """P1 fix: records OPEN live/paper trade with MT5 ticket into trade_vectors."""
        try:
            from memory_rag.adaptive_trade_journal import TradeJournalDB, TradeVectorRecord
            pip_size = MT5Connector.get_pip_size(symbol)
            atr_pips = max(atr / max(pip_size, 1e-9), 1.0)
            spread_ratio = min(1.0, max(0.0, float(spread_pips) / atr_pips))
            conf_norm = float(confidence) / 100.0 if (confidence is not None and confidence > 1.0) else float(confidence or 0.5)
            conf_norm = max(0.0, min(1.0, conf_norm))
            rec = TradeVectorRecord(
                timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                symbol=symbol,
                ticket=int(ticket),
                regime_state=str(fsm_regime or "UNKNOWN"),
                setup_type="LIVE_VOTING_ENGINE",
                hurst=0.5,
                atr_ratio=round(atr / max(entry_price * 0.0015, 1e-9), 4),
                z_score=0.0,
                ofi_z=0.0,
                spread_ratio=round(spread_ratio, 4),
                proposed_action=direction,
                final_action=direction,
                signal_confidence=round(conf_norm, 4),
                net_score=round(conf_norm, 4),
                sl_pips=round(float(sl_pips or 0.0), 1),
                tp1_pips=round(float(tp1_pips or 0.0), 1),
                risk_percent=float(self.risk.cfg.get("risk_percent", 1.0)),
                outcome="OPEN",
                execution_mode="LIVE" if mode == "LIVE" else "SHADOW",
                spread_cost=round(float(spread_pips or 0.0), 2),
            )
            journal = TradeJournalDB()
            try:
                journal.insert_record(rec)
            finally:
                journal.close()
        except Exception as exc:
            logger.debug(f"[SafeExecutionGateway] trade_vectors insert skipped: {exc}")

    def _save_trade_to_db(self, ticket: int, symbol: str, direction: str, lot: float, entry: float, sl: float, tp: float, regime: str, confidence: float, comment: str = None):
        try:
            db = SessionLocal()
            trade = Trade(
                ticket=ticket,
                symbol=symbol,
                type=TradeType(direction),
                status=TradeStatus.OPEN,
                lot_size=lot,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp,
                fsm_regime=FSMRegime(regime) if regime else None,
                confidence=confidence,
                comment=comment or f"SG_{direction}"
            )
            db.add(trade)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"[SafeExecutionGateway] DB save failed: {e}")

    async def _trace_position_loop(self, ticket: int, symbol: str, direction: str, entry: float, sl: float, tp: float, lot: float, mode: str):
        """
        Async monitoring loop for unrealized P&L
        """
        pip_size = MT5Connector.get_pip_size(symbol)
        logger.info(f"[SafeExecutionGateway] Started monitoring loop for ticket #{ticket}")

        while True:
            await asyncio.sleep(2.0)
            try:
                if mode == "PAPER":
                    # Paper simulated close/p&l checks
                    tick = self.mt5.get_tick(symbol)
                    if not tick:
                        continue
                    curr_price = tick["ask"] if direction == "BUY" else tick["bid"]
                    
                    hit_sl = (sl > 0) and ((direction == "BUY" and curr_price <= sl) or (direction == "SELL" and curr_price >= sl))
                    hit_tp = (tp > 0) and ((direction == "BUY" and curr_price >= tp) or (direction == "SELL" and curr_price <= tp))
                    
                    # Estimate profit
                    pip_value = self.mt5.get_pip_value(symbol)
                    pips = (curr_price - entry) / pip_size if direction == "BUY" else (entry - curr_price) / pip_size
                    unrealized_pnl = pips * pip_value * lot  # P0 fix: removed erroneous 10x multiplier

                    if hit_sl or hit_tp:
                        close_reason = "SL_HIT" if hit_sl else "TP_HIT"
                        logger.info(f"[SafeExecutionGateway] Paper trade #{ticket} closed due to {close_reason} at {curr_price:.5f}")
                        
                        db = SessionLocal()
                        db_trade = db.query(Trade).filter(Trade.ticket == ticket).first()
                        if db_trade:
                            db_trade.status = TradeStatus.CLOSED
                            db_trade.close_price = curr_price
                            db_trade.profit_usd = unrealized_pnl
                            db_trade.closed_at = datetime.utcnow()
                            db.commit()
                        db.close()

                        await self.bus.emit_trade_closed(
                            sender="SafeExecutionGateway",
                            ticket=ticket,
                            symbol=symbol,
                            profit=unrealized_pnl
                        )
                        break
                else:
                    # Live MT5 monitoring
                    positions = self.mt5.get_open_positions()
                    matching = [pos for pos in positions if pos["ticket"] == ticket]
                    if not matching:
                        logger.info(f"[SafeExecutionGateway] Live trade #{ticket} closed")
                        break
                    
                    pos = matching[0]
                    unrealized_pnl = pos["profit"]
                    curr_price = pos["current_price"]

                # Emit unrealized update to signal bus
                await self.bus.publish(BusMessage(
                    topic="unrealized_pnl_update",
                    sender="SafeExecutionGateway",
                    data={
                        "ticket": ticket,
                        "symbol": symbol,
                        "unrealized_pnl": unrealized_pnl,
                        "current_price": curr_price,
                        "time": datetime.utcnow().isoformat()
                    }
                ))

            except Exception as e:
                logger.error(f"[SafeExecutionGateway] Error tracing position #{ticket}: {e}")
                
        # Clean up task reference
        self._active_tasks.pop(ticket, None)
