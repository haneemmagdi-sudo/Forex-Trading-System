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
    ✅ Slippage Check: مقارنة سبريد وأسعار Hyperliquid لضمان عدم وجود انزلاق ضار
    ✅ Order Routing: إرسال الصفقات الحقيقية عبر MetaTrader5.order_send مع SL/TP ديناميكي
    ✅ Monitoring: مراقبة حالة الصفقة والـ Unrealized P&L وتحديث MonitorAgent
    """

    def __init__(self, mt5_connector: MT5Connector, orchestrator: AntigravityOrchestrator = None, risk_manager: RiskManager = None):
        self.mt5 = mt5_connector
        self.orchestrator = orchestrator or AntigravityOrchestrator()
        self.risk = risk_manager or RiskManager()
        self.bus = get_bus()
        
        # استيراد Client و Synchroniser للتحقق من Hyperliquid
        from core.live_pipeline import HyperliquidClient
        from core.symbol_sync import get_synchroniser
        
        self.hl_client = HyperliquidClient()
        self.syncer = get_synchroniser()
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
    ) -> dict:
        """
        تقييم الإشارة عبر الـ Orchestrator وتمريرها للتنفيذ الآمن

        لا تُمرَّر تنبؤات نماذج مُختلقة: تقييم الـ ensemble يُنفَّذ فقط عند
        توفّر مخرجات حقيقية للنماذج الأربعة. وإلا تُتخطى البوابة ويُستخدم
        الاتجاه القادم من تصويت المحلل مع تسجيل ثقته الحقيقية.
        (سابقاً كانت تُمرَّر قيم ثابتة فتُنتج ثقة وهمية 82.49% دائماً.)
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

        if self.risk.cfg.get("manual_lot_enabled", False):
            lot_size = params.lot_size
        else:
            # Use RiskManager calculated lot size, capped at maximum 1.5% Equity risk
            max_risk_usd = equity * 0.015
            if params.sl_pips > 0 and pip_value > 0:
                equity_cap_lot = max_risk_usd / (params.sl_pips * pip_value)
                lot_size = min(params.lot_size, equity_cap_lot)
            else:
                lot_size = params.lot_size

        lot_size = round(max(0.01, min(lot_size, 100.0)), 2)

        # 2.4 Available Margin Check
        margin_required = self._calculate_required_margin(symbol, lot_size, entry_price, direction, account)
        if margin_required > free_margin:
            return {
                "success": False,
                "reason": f"Insufficient margin. Required: ${margin_required:.2f}, Available: ${free_margin:.2f}"
            }

        # ── 3. Order Routing via MetaTrader5 ──
        result = self._route_order(symbol, direction, lot_size, params.sl_price, params.tp_price, entry_price, digits)
        if not result["success"]:
            return {"success": False, "reason": f"Routing failed: {result.get('error')}"}

        ticket = result["ticket"]

        # Save trade to database
        self._save_trade_to_db(ticket, symbol, direction, lot_size, entry_price, params.sl_price, params.tp_price, fsm_regime, consensus_confidence)

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
        Query Hyperliquid live spread and validate slippage
        """
        hl_coin = self.syncer.resolve_hl(symbol)
        if not hl_coin:
            logger.warning(f"[SafeExecutionGateway] Symbol {symbol} not supported on Hyperliquid. Skipping HL slippage check.")
            return True, "No HL asset mapped"

        try:
            # Query L2 order book
            bid, ask = self.hl_client.get_l2_book(hl_coin)
            if np.isnan(bid) or np.isnan(ask) or bid <= 0:
                logger.warning(f"[SafeExecutionGateway] Hyperliquid L2 book returned invalid data for {hl_coin}. Proceeding with caution.")
                return True, "HL book data unavailable"

            hl_mid = (bid + ask) / 2.0
            tick = self.mt5.get_tick(symbol)
            if not tick:
                return False, "Failed to get current tick for slippage check"
            mt5_price = tick["ask"] if direction == "BUY" else tick["bid"]

            # Calculate price deviation (slippage) as percentage
            slippage_pct = abs(mt5_price - hl_mid) / hl_mid * 100
            spread_bps = (ask - bid) / hl_mid * 10000

            max_slip_pct = 0.5  # maximum 0.5% deviation
            max_hl_spread = 50.0 # maximum 50 basis points spread

            if slippage_pct > max_slip_pct:
                return False, f"Price deviation too high: {slippage_pct:.3f}% (max: {max_slip_pct}%)"

            if spread_bps > max_hl_spread:
                return False, f"Hyperliquid spread too wide: {spread_bps:.1f} bps (max: {max_hl_spread} bps)"

            logger.info(f"[SafeExecutionGateway] Slippage Check Passed: HL Mid={hl_mid:.5f}, Spread={spread_bps:.1f} bps, Slippage={slippage_pct:.3f}%")
            return True, "Success"

        except Exception as e:
            logger.error(f"[SafeExecutionGateway] Slippage Check exception: {e}")
            return True, f"HL check exception: {e}"

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

    def _route_order(self, symbol: str, direction: str, lot: float, sl: float, tp: float, entry_price: float, digits: int) -> dict:
        """
        Use MetaTrader5.order_send to route the atomic execution payload
        """
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
            "magic":        112345,
            "comment":      f"SG_{direction}",
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

    def _save_trade_to_db(self, ticket: int, symbol: str, direction: str, lot: float, entry: float, sl: float, tp: float, regime: str, confidence: float):
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
                fsm_regime=FSMRegime(regime),
                confidence=confidence,
                comment=f"SG_{direction}"
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
        pip_size = 0.0001 if "JPY" not in symbol else 0.01
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
                    unrealized_pnl = pips * pip_value * lot * 10

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
