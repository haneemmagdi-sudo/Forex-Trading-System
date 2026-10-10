"""
mcp_server/__init__.py — Quantum FSM Pro V4.2 Elite MCP Server Package.

Sub-modules
-----------
quantum_server : QuantumMCPServer — centralized async MCP server
exceptions     : JSON-RPC 2.0 exception hierarchy and error middleware
"""

from mcp_server.exceptions import (
    JsonRpcCode,
    QuantumMCPBaseError,
    ParseError,
    InvalidRequestError,
    MethodNotFoundError,
    InvalidParamsError,
    InternalError,
    MT5DisconnectedError,
    HyperliquidTimeoutError,
    OpenBBProviderError,
    OrderRejectedError,
    InsufficientMarginError,
    SymbolNotFoundError,
    StaleDataError,
    mcp_error_interceptor,
    tool_error_guard,
)
from mcp_server.quantum_server import QuantumMCPServer

__all__ = [
    # Exception hierarchy
    "JsonRpcCode",
    "QuantumMCPBaseError",
    "ParseError",
    "InvalidRequestError",
    "MethodNotFoundError",
    "InvalidParamsError",
    "InternalError",
    "MT5DisconnectedError",
    "HyperliquidTimeoutError",
    "OpenBBProviderError",
    "OrderRejectedError",
    "InsufficientMarginError",
    "SymbolNotFoundError",
    "StaleDataError",
    # Middleware
    "mcp_error_interceptor",
    "tool_error_guard",
    # Server
    "QuantumMCPServer",
]
