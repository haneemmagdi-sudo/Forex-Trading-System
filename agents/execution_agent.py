"""
Execution Agent — the only agent that actually executes trades.
ONLY receives orders that have passed the Risk Manager's veto AND
the MessageBus infrastructure check.
No LLM calls needed — pure deterministic logic.
"""

from __future__ import annotations
import logging
import random
import uuid
from datetime import datetime, timezone

from schemas.agents import StrategyProposal, ExecutionReceipt
from schemas.forex import calculate_margin_required, price_to_pips, pips_to_usd
import config as cfg
# Real Broker Integration
from core.mt5_broker import get_broker

logger = logging.getLogger("execution_agent")


class ExecutionAgent:
    """
    Trade executor — receives approved strategies and simulates
    realistic execution with slippage and spread modeling.
    Does NOT use LLM (saves free quota).
    """

    def __init__(self, ledger=None, db=None):
        self.ledger = ledger
        self.db = db

    # ── Execute a strategy ────────────────────────────────────

    async def execute(self, strategy: StrategyProposal) -> ExecutionReceipt:
        """Execute an approved trading strategy."""
        if strategy.asset_class == "EQUITY":
            return await self._execute_equity(strategy)
        else:
            return await self._execute_forex(strategy)

    # ── Equity execution ──────────────────────────────────────

    async def _execute_equity(self, strategy: StrategyProposal) -> ExecutionReceipt:
        """Simulate equity trade execution with realistic slippage."""
        slippage = self._simulate_slippage(strategy.entry_price, asset_class="EQUITY")

        if strategy.action in ("BUY", "LONG"):
            executed_price = strategy.entry_price + slippage
        else:
            executed_price = strategy.entry_price - slippage

        executed_price = round(executed_price, 4)
        total_cost = round(executed_price * strategy.quantity, 2)
        trade_id = f"TRD-EQ-{uuid.uuid4().hex[:10].upper()}"

        receipt = ExecutionReceipt(
            trade_id=trade_id,
            strategy_id=strategy.strategy_id,
            asset_class="EQUITY",
            symbol=strategy.symbol,
            action=strategy.action,
            quantity=strategy.quantity,
            requested_price=strategy.entry_price,
            executed_price=executed_price,
            slippage=round(slippage, 4),
            total_cost=total_cost,
            status="EXECUTED",
        )

        # Update portfolio ledger
        if self.ledger:
            await self.ledger.open_trade({
                "trade_id": trade_id,
                "strategy_id": strategy.strategy_id,
                "asset_class": "EQUITY",
                "symbol": strategy.symbol,
                "action": strategy.action,
                "quantity": strategy.quantity,
                "executed_price": executed_price,
                "stop_loss_price": strategy.stop_loss,
                "take_profit_price": strategy.take_profit,
                "llm_provider": strategy.llm_provider,
            })

        logger.info(
            f"[EXECUTOR] ✅ EQUITY EXECUTED: {strategy.action} {strategy.quantity}x "
            f"{strategy.symbol} @ ${executed_price:.4f} (slippage: ${slippage:.4f})"
        )
        return receipt

    # ── Forex execution ───────────────────────────────────────

    async def _execute_forex(self, strategy: StrategyProposal) -> ExecutionReceipt:
        """Simulate Forex trade execution with spread and slippage."""
        slippage = self._simulate_slippage(strategy.entry_price, asset_class="FOREX")
        spread_pips = self._get_spread_pips(strategy.symbol)

        if strategy.action == "BUY":
            # Buyer pays spread on entry
            executed_price = strategy.entry_price + slippage
        else:
            # Seller gets less on entry
            executed_price = strategy.entry_price - slippage

        executed_price = round(executed_price, 5)
        margin = calculate_margin_required(
            strategy.symbol, strategy.quantity, executed_price, cfg.MAX_FOREX_LEVERAGE
        )
        trade_id = f"TRD-FX-{uuid.uuid4().hex[:10].upper()}"

        # ── LIVE EXECUTION ─────────────────────────────────────
        if cfg.LIVE_TRADING_ENABLED:
            broker = get_broker()
            mt5_res = broker.execute_order(
                symbol=strategy.symbol,
                action=strategy.action,
                quantity=strategy.quantity,
                sl_price=strategy.stop_loss,
                tp_price=strategy.take_profit
            )
            
            if mt5_res["status"] == "SUCCESS":
                trade_id = f"MT5-{mt5_res['trade_id']}"
                executed_price = mt5_res["executed_price"]
                # Use real commission cost
                margin = calculate_margin_required(
                    strategy.symbol, strategy.quantity, executed_price, cfg.MAX_FOREX_LEVERAGE
                )
            else:
                logger.error("❌ MT5: Execution failed: %s", mt5_res["error"])
                return ExecutionReceipt(
                    strategy_id=strategy.strategy_id,
                    asset_class="FOREX",
                    symbol=strategy.symbol,
                    action=strategy.action,
                    quantity=strategy.quantity,
                    requested_price=strategy.entry_price,
                    executed_price=0.0,
                    status="FAILED",
                    failure_reason=mt5_res["error"]
                )

        receipt = ExecutionReceipt(
            trade_id=trade_id,
            strategy_id=strategy.strategy_id,
            asset_class="FOREX",
            symbol=strategy.symbol,
            action=strategy.action,
            quantity=strategy.quantity,
            requested_price=strategy.entry_price,
            executed_price=executed_price,
            slippage=round(abs(executed_price - strategy.entry_price), 5) if not cfg.LIVE_TRADING_ENABLED else 0.0,
            spread_paid_pips=spread_pips,
            margin_used=margin,
            total_cost=margin,
            status="EXECUTED",
        )

        if self.ledger:
            await self.ledger.open_trade({
                "trade_id": trade_id,
                "strategy_id": strategy.strategy_id,
                "asset_class": "FOREX",
                "symbol": strategy.symbol,
                "action": strategy.action,
                "quantity": strategy.quantity,
                "executed_price": executed_price,
                "stop_loss_price": strategy.stop_loss,
                "take_profit_price": strategy.take_profit,
                "spread_paid_pips": spread_pips,
                "margin_used": margin,
                "llm_provider": strategy.llm_provider,
            })

        logger.info(
            f"[EXECUTOR] ✅ {'LIVE' if cfg.LIVE_TRADING_ENABLED else 'SIM'} FOREX EXECUTED: "
            f"{strategy.action} {strategy.quantity} lots {strategy.symbol} @ {executed_price:.5f}"
        )
        return receipt

    # ── Close a position ──────────────────────────────────────

    async def close_position(
        self, trade_id: str, symbol: str, asset_class: str,
        exit_price: float, reason: str = "SL_TP"
    ) -> dict:
        """Close an open position."""
        # ── LIVE CLOSURE ─────────────────────────────────────
        if cfg.LIVE_TRADING_ENABLED and "MT5-" in trade_id:
            ticket = int(trade_id.replace("MT5-", ""))
            broker = get_broker()
            success = broker.close_position(ticket)
            if not success:
                return {"trade_id": trade_id, "status": "ERROR", "error": "MT5 Close Failed"}

        closed_trade = None
        if self.ledger:
            closed_trade = await self.ledger.close_trade(trade_id, exit_price, reason)

        if closed_trade:
            pnl = closed_trade.pnl_usd
            logger.info(
                f"[EXECUTOR] 🔒 CLOSED {asset_class} {symbol} {trade_id} "
                f"@ {exit_price:.5f} | P&L: ${pnl:+.2f} [{reason}]"
            )
            return {
                "trade_id": trade_id,
                "symbol": symbol,
                "exit_price": exit_price,
                "pnl_usd": pnl,
                "close_reason": reason,
                "status": "CLOSED",
            }
        return {"trade_id": trade_id, "status": "ERROR", "error": "Trade not found"}

    # ── Slippage model ────────────────────────────────────────

    def _simulate_slippage(self, price: float, asset_class: str = "EQUITY") -> float:
        """
        Simulate realistic market slippage.
        Equity: 0.05% - 0.15% of price
        Forex: 0.5 - 2.0 pips approximately
        """
        if asset_class == "EQUITY":
            slippage_pct = random.uniform(0.0005, 0.0015)
            return price * slippage_pct
        else:
            # Forex: small random pip slippage
            pip_slippage = random.uniform(0.2, 1.0)
            return pip_slippage * 0.0001  # 1 pip = 0.0001

    def _get_spread_pips(self, pair: str) -> float:
        """Return typical spread in pips for a Forex pair."""
        spreads = {
            "EURUSD=X": random.uniform(0.8, 1.5),
            "GBPUSD=X": random.uniform(1.0, 2.0),
            "USDJPY=X": random.uniform(0.8, 1.5),
            "AUDUSD=X": random.uniform(1.2, 2.0),
            "USDCHF=X": random.uniform(1.2, 2.0),
            "XAUUSD=X": random.uniform(20.0, 35.0),
        }
        return round(spreads.get(pair, random.uniform(1.5, 3.0)), 2)
