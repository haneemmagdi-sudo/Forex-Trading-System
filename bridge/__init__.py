"""
=============================================================================
bridge — Low-Latency Python <-> MQL5 Inter-Process Communication (IPC) Layer
=============================================================================
Strict Pydantic contracts and dispatchers for transmitting high-conviction
trade payloads between Python MAS and MetaTrader 5 Expert Advisors.
"""

from bridge.signal_schema import (
    OrderAction,
    OrderType,
    ExecutionMode,
    RegimeClassification,
    AgentCouncilVerdict,
    RiskMetrics,
    SignalPayload,
    AlphaRegimeMessage,
    BetaSetupMessage,
    GammaCriticMessage,
    OmegaGovernorVerdict,
    ExecutionReceipt,
)

__all__ = [
    "OrderAction",
    "OrderType",
    "ExecutionMode",
    "RegimeClassification",
    "AgentCouncilVerdict",
    "RiskMetrics",
    "SignalPayload",
    "AlphaRegimeMessage",
    "BetaSetupMessage",
    "GammaCriticMessage",
    "OmegaGovernorVerdict",
    "ExecutionReceipt",
]
