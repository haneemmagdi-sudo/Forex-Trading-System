"""
core/mt5_broker.py — Broker Interface for MT5 Order Execution.
Bridges agent order requests to the underlying MT5Connector and broker API.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("core.mt5_broker")


class MT5Broker:
    """Unified Broker execution gateway."""

    def __init__(self):
        self._connector = None

    @property
    def connector(self):
        if self._connector is None:
            try:
                from backend.core.mt5_connector import MT5Connector
                self._connector = MT5Connector()
            except Exception as e:
                logger.warning(f"Could not initialize MT5Connector: {e}")
        return self._connector

    def execute_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        deviation: int = 20,
        comment: str = "Quantum AI",
    ) -> Dict[str, Any]:
        """
        Execute an order via MT5Connector or return simulated execution receipt.
        """
        conn = self.connector
        if conn and getattr(conn, "connected", False):
            try:
                return conn.send_order(
                    symbol=symbol,
                    order_type=action,
                    volume=quantity,
                    sl=sl_price,
                    tp=tp_price,
                    comment=comment
                )
            except Exception as exc:
                logger.error(f"[MT5Broker] Live order failed: {exc}")

        # Fallback simulated order execution
        return {
            "status": "SUCCESS",
            "simulated": True,
            "order_id": 999001,
            "symbol": symbol,
            "action": action,
            "volume": quantity,
            "sl": sl_price,
            "tp": tp_price,
            "retcode": 10009,
            "comment": comment,
        }


_broker_instance: Optional[MT5Broker] = None


def get_broker() -> MT5Broker:
    """Return singleton MT5Broker instance."""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = MT5Broker()
    return _broker_instance
