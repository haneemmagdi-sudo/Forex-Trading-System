"""
==============================================================================
mcp_server/exceptions.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : MCP/JSON-RPC 2.0 Error Handling & Exception Middleware
Author : Principal Integration Architect
Version: 4.2.0

Overview
--------
Defines the complete custom exception hierarchy for the QuantumMCPServer.
Every internal infrastructure failure (MT5 terminal disconnect, Hyperliquid
network timeout, OpenBB provider error, Pydantic validation failure) is
intercepted and re-mapped to a JSON-RPC 2.0 compliant error object.

JSON-RPC 2.0 Error Code Registry
---------------------------------
::

    ┌─────────┬──────────────────────┬─────────────────────────────────────┐
    │  Code   │  Standard Name       │  Quantum FSM Usage                  │
    ├─────────┼──────────────────────┼─────────────────────────────────────┤
    │ -32700  │  Parse Error         │  Malformed JSON payload received     │
    │ -32600  │  Invalid Request     │  MCP message missing required fields │
    │ -32601  │  Method Not Found    │  Unknown tool name requested         │
    │ -32602  │  Invalid Params      │  Pydantic validation failure         │
    │ -32603  │  Internal Error      │  MT5 crash / network timeout         │
    │ -32001  │  MT5 Disconnected    │  MT5 terminal not running            │
    │ -32002  │  Hyperliquid Timeout │  REST API call exceeded timeout      │
    │ -32003  │  OpenBB Provider Err │  OpenBB platform data fetch failed   │
    │ -32004  │  Order Rejected      │  MT5 order_send retcode != DONE      │
    │ -32005  │  Insufficient Margin │  Account margin below required level │
    │ -32006  │  Symbol Not Found    │  MT5 symbol_info returned None       │
    │ -32007  │  Stale Data          │  Market data exceeded freshness TTL  │
    └─────────┴──────────────────────┴─────────────────────────────────────┘

Design Pattern
--------------
All exceptions carry three fields mandated by the JSON-RPC 2.0 specification:
    - ``code`` (int)  : Numeric error code from the registry above.
    - ``message`` (str): Short, machine-readable error description.
    - ``data`` (dict) : Optional extended diagnostic payload.

The ``MCPErrorInterceptor`` context manager catches any subclass of
``QuantumMCPBaseError`` (or a mapped stdlib/third-party exception) and
re-raises it as a properly formatted JSON-RPC error response dict,
ensuring the multi-agent core loop never crashes from a tool failure.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, Optional, Type

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.mcp.exceptions")


# ===========================================================================
# JSON-RPC 2.0 Error Code Registry
# ===========================================================================

class JsonRpcCode:
    """
    Namespace of all JSON-RPC 2.0 error codes used by the QuantumMCPServer.

    Standard codes (reserved by specification):
        PARSE_ERROR      = -32700
        INVALID_REQUEST  = -32600
        METHOD_NOT_FOUND = -32601
        INVALID_PARAMS   = -32602
        INTERNAL_ERROR   = -32603

    Quantum FSM custom codes (application-level, range -32000 to -32099):
        MT5_DISCONNECTED     = -32001
        HYPERLIQUID_TIMEOUT  = -32002
        OPENBB_PROVIDER_ERR  = -32003
        ORDER_REJECTED       = -32004
        INSUFFICIENT_MARGIN  = -32005
        SYMBOL_NOT_FOUND     = -32006
        STALE_DATA           = -32007
    """
    # ── Standard JSON-RPC 2.0 codes ──────────────────────────────────────
    PARSE_ERROR:      int = -32700
    INVALID_REQUEST:  int = -32600
    METHOD_NOT_FOUND: int = -32601
    INVALID_PARAMS:   int = -32602
    INTERNAL_ERROR:   int = -32603

    # ── Quantum FSM custom application codes ─────────────────────────────
    MT5_DISCONNECTED:    int = -32001
    HYPERLIQUID_TIMEOUT: int = -32002
    OPENBB_PROVIDER_ERR: int = -32003
    ORDER_REJECTED:      int = -32004
    INSUFFICIENT_MARGIN: int = -32005
    SYMBOL_NOT_FOUND:    int = -32006
    STALE_DATA:          int = -32007

    # Reverse lookup: code → human-readable name
    _NAMES: Dict[int, str] = {
        -32700: "Parse Error",
        -32600: "Invalid Request",
        -32601: "Method Not Found",
        -32602: "Invalid Params",
        -32603: "Internal Error",
        -32001: "MT5 Disconnected",
        -32002: "Hyperliquid Timeout",
        -32003: "OpenBB Provider Error",
        -32004: "Order Rejected",
        -32005: "Insufficient Margin",
        -32006: "Symbol Not Found",
        -32007: "Stale Data",
    }

    @classmethod
    def name(cls, code: int) -> str:
        """Return the human-readable name for a given error code."""
        return cls._NAMES.get(code, f"Unknown Error ({code})")


# ===========================================================================
# Base Exception
# ===========================================================================

class QuantumMCPBaseError(Exception):
    """
    Abstract base class for all Quantum FSM MCP exceptions.

    Every concrete subclass carries a ``code``, ``message``, and optional
    ``data`` dict that maps directly to a JSON-RPC 2.0 error object::

        {
            "jsonrpc": "2.0",
            "id": <request_id>,
            "error": {
                "code":    <int>,
                "message": <str>,
                "data":    <dict | null>
            }
        }

    Parameters
    ----------
    message : str
        Short, machine-readable description of the error.
    code : int
        JSON-RPC 2.0 error code from ``JsonRpcCode``.
    data : dict, optional
        Extended diagnostic payload (stack trace, context variables, etc.).
    """

    code: int = JsonRpcCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.code: int = code if code is not None else self.__class__.code
        self.data: Dict[str, Any] = data or {}

    def to_jsonrpc_error(self) -> Dict[str, Any]:
        """
        Serialize this exception to a JSON-RPC 2.0 ``error`` object dict.

        Returns
        -------
        dict
            A mapping with keys ``"code"``, ``"message"``, and ``"data"``.
            The ``"data"`` field is omitted when empty to minimise payload size.

        Examples
        --------
        >>> err = MT5DisconnectedError("Terminal closed unexpectedly")
        >>> err.to_jsonrpc_error()
        {'code': -32001, 'message': 'MT5 Disconnected: Terminal closed unexpectedly', 'data': {}}
        """
        error_obj: Dict[str, Any] = {
            "code":    self.code,
            "message": f"{JsonRpcCode.name(self.code)}: {self.message}",
        }
        if self.data:
            error_obj["data"] = self.data
        return error_obj

    def to_tool_error_string(self) -> str:
        """
        Return a compact, JSON-serializable string representation of this
        error suitable for embedding in a tool's text response when the MCP
        framework requires a string return value even on failure.

        Returns
        -------
        str
            JSON string: ``{"error": {"code": ..., "message": ..., "data": ...}}``.
        """
        import json
        return json.dumps({"error": self.to_jsonrpc_error()}, indent=None)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.code}, "
            f"message={self.message!r})"
        )


# ===========================================================================
# Concrete Exception Classes
# ===========================================================================

class ParseError(QuantumMCPBaseError):
    """
    Raised when the MCP server receives a malformed or unparseable JSON payload.

    JSON-RPC code: -32700
    """
    code = JsonRpcCode.PARSE_ERROR

    def __init__(self, message: str = "Malformed JSON payload received.", data: Optional[Dict] = None) -> None:
        super().__init__(message, self.code, data)


class InvalidRequestError(QuantumMCPBaseError):
    """
    Raised when a JSON-RPC request is structurally invalid (missing ``method``
    field, wrong ``jsonrpc`` version, etc.).

    JSON-RPC code: -32600
    """
    code = JsonRpcCode.INVALID_REQUEST

    def __init__(self, message: str = "Invalid JSON-RPC request structure.", data: Optional[Dict] = None) -> None:
        super().__init__(message, self.code, data)


class MethodNotFoundError(QuantumMCPBaseError):
    """
    Raised when an agent requests a tool name that is not registered on the
    QuantumMCPServer.

    JSON-RPC code: -32601
    """
    code = JsonRpcCode.METHOD_NOT_FOUND

    def __init__(self, tool_name: str, data: Optional[Dict] = None) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not registered on the QuantumMCPServer.",
            self.code,
            data or {"requested_tool": tool_name},
        )


class InvalidParamsError(QuantumMCPBaseError):
    """
    Raised when Pydantic v2 argument validation fails inside a registered tool.

    Captures the Pydantic ``ValidationError`` detail in the ``data`` field so
    downstream agents can identify exactly which parameter was invalid.

    JSON-RPC code: -32602
    """
    code = JsonRpcCode.INVALID_PARAMS

    def __init__(self, message: str, validation_errors: Optional[Any] = None, data: Optional[Dict] = None) -> None:
        extended: Dict[str, Any] = data or {}
        if validation_errors is not None:
            try:
                extended["validation_errors"] = validation_errors.errors()
            except AttributeError:
                extended["validation_errors"] = str(validation_errors)
        super().__init__(message, self.code, extended)


class InternalError(QuantumMCPBaseError):
    """
    Catch-all for unexpected runtime exceptions inside any registered tool.

    Always captures the full traceback string in ``data["traceback"]`` for
    post-incident debugging without exposing it to the calling agent UI.

    JSON-RPC code: -32603
    """
    code = JsonRpcCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        if original_exception is not None:
            extended["exception_type"] = type(original_exception).__name__
            extended["traceback"] = traceback.format_exc()
        super().__init__(message, self.code, extended)


class MT5DisconnectedError(QuantumMCPBaseError):
    """
    Raised when the MetaTrader 5 terminal process is not running, has been
    closed unexpectedly, or ``mt5.account_info()`` returns None.

    JSON-RPC code: -32001

    The Planner Agent must intercept this error and immediately force a
    SAFETY_HOLD state on any pending execution mandates.

    Parameters
    ----------
    message : str
        Human-readable description of the MT5 disconnect condition.
    last_error : tuple, optional
        The result of ``mt5.last_error()`` at the time of failure.
    """
    code = JsonRpcCode.MT5_DISCONNECTED

    def __init__(
        self,
        message: str = "MetaTrader 5 terminal is disconnected or unavailable.",
        last_error: Optional[Any] = None,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        if last_error is not None:
            extended["mt5_last_error"] = str(last_error)
        super().__init__(message, self.code, extended)


class HyperliquidTimeoutError(QuantumMCPBaseError):
    """
    Raised when the Hyperliquid REST API endpoint does not respond within
    the configured timeout window (default: 8 seconds).

    JSON-RPC code: -32002

    Parameters
    ----------
    endpoint : str
        The Hyperliquid API endpoint URL that timed out.
    timeout_seconds : float
        The configured timeout duration that was exceeded.
    """
    code = JsonRpcCode.HYPERLIQUID_TIMEOUT

    def __init__(
        self,
        endpoint: str,
        timeout_seconds: float = 8.0,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        extended.update({"endpoint": endpoint, "timeout_seconds": timeout_seconds})
        super().__init__(
            f"Hyperliquid REST API timed out after {timeout_seconds}s on {endpoint}",
            self.code,
            extended,
        )


class OpenBBProviderError(QuantumMCPBaseError):
    """
    Raised when the OpenBB Platform v4 provider chain exhausts all configured
    data providers without returning a valid result.

    JSON-RPC code: -32003

    Parameters
    ----------
    symbol : str
        The instrument symbol that triggered the provider failure.
    provider_attempted : str
        Name of the OpenBB provider that failed (e.g., ``"yfinance"``, ``"fmp"``).
    original_error : Exception, optional
        The original OpenBB exception for debugging.
    """
    code = JsonRpcCode.OPENBB_PROVIDER_ERR

    def __init__(
        self,
        symbol: str,
        provider_attempted: str = "unknown",
        original_error: Optional[Exception] = None,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        extended.update({
            "symbol": symbol,
            "provider_attempted": provider_attempted,
        })
        if original_error is not None:
            extended["original_error"] = str(original_error)
        super().__init__(
            f"OpenBB provider '{provider_attempted}' failed for symbol '{symbol}'.",
            self.code,
            extended,
        )


class OrderRejectedError(QuantumMCPBaseError):
    """
    Raised when MetaTrader 5's ``order_send()`` returns a non-DONE retcode,
    indicating the broker rejected the trade order.

    JSON-RPC code: -32004

    Parameters
    ----------
    symbol : str
        The instrument for which the order was rejected.
    retcode : int
        The MT5 TRADE_RETCODE value returned by ``order_send()``.
    comment : str
        The broker's rejection reason string from the result object.
    """
    code = JsonRpcCode.ORDER_REJECTED

    def __init__(
        self,
        symbol: str,
        retcode: int,
        comment: str,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        extended.update({
            "symbol":  symbol,
            "retcode": retcode,
            "broker_comment": comment,
        })
        super().__init__(
            f"MT5 order rejected for '{symbol}': retcode={retcode}, comment='{comment}'.",
            self.code,
            extended,
        )


class InsufficientMarginError(QuantumMCPBaseError):
    """
    Raised when the account's free margin is below the minimum required to
    open a new position with the specified lot size.

    JSON-RPC code: -32005

    Parameters
    ----------
    free_margin : float
        Current free margin available in the account.
    required_margin : float
        Margin required to execute the requested trade.
    """
    code = JsonRpcCode.INSUFFICIENT_MARGIN

    def __init__(
        self,
        free_margin: float,
        required_margin: float,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        extended.update({
            "free_margin":     round(free_margin, 2),
            "required_margin": round(required_margin, 2),
            "shortfall":       round(required_margin - free_margin, 2),
        })
        super().__init__(
            f"Insufficient margin: have {free_margin:.2f}, need {required_margin:.2f}.",
            self.code,
            extended,
        )


class SymbolNotFoundError(QuantumMCPBaseError):
    """
    Raised when ``mt5.symbol_info()`` returns None for the requested symbol,
    indicating it is not available on this broker's server.

    JSON-RPC code: -32006

    Parameters
    ----------
    symbol : str
        The instrument symbol that could not be found.
    """
    code = JsonRpcCode.SYMBOL_NOT_FOUND

    def __init__(self, symbol: str, data: Optional[Dict] = None) -> None:
        extended: Dict[str, Any] = data or {"symbol": symbol}
        super().__init__(
            f"Symbol '{symbol}' not found on the MT5 broker server.",
            self.code,
            extended,
        )


class StaleDataError(QuantumMCPBaseError):
    """
    Raised when market data fetched from any provider exceeds the configured
    maximum freshness TTL, making it unsafe to use for execution decisions.

    JSON-RPC code: -32007

    Parameters
    ----------
    data_source : str
        Name of the data source that returned stale data.
    data_age_seconds : float
        How old the data is in seconds.
    max_age_seconds : int
        The maximum allowed age in seconds.
    """
    code = JsonRpcCode.STALE_DATA

    def __init__(
        self,
        data_source: str,
        data_age_seconds: float,
        max_age_seconds: int,
        data: Optional[Dict] = None,
    ) -> None:
        extended: Dict[str, Any] = data or {}
        extended.update({
            "data_source":      data_source,
            "data_age_seconds": round(data_age_seconds, 2),
            "max_age_seconds":  max_age_seconds,
        })
        super().__init__(
            f"Stale data from '{data_source}': age={data_age_seconds:.1f}s > max={max_age_seconds}s.",
            self.code,
            extended,
        )


# ===========================================================================
# Exception → Error Code Mapping Table
# ===========================================================================

#: Maps external exception types to the appropriate QuantumMCPBaseError subclass.
#: Used by the interceptor to auto-classify non-Quantum exceptions.
EXCEPTION_MAP: Dict[Type[Exception], Type[QuantumMCPBaseError]] = {
    asyncio.TimeoutError:    InternalError,
    ConnectionRefusedError:  MT5DisconnectedError,
    ConnectionResetError:    MT5DisconnectedError,
    ConnectionAbortedError:  MT5DisconnectedError,
    OSError:                 InternalError,
    ValueError:              InvalidParamsError,
    TypeError:               InvalidParamsError,
}


# ===========================================================================
# MCPErrorInterceptor — Context Manager Middleware
# ===========================================================================

@asynccontextmanager
async def mcp_error_interceptor(
    tool_name: str,
    request_id: Optional[Any] = None,
) -> AsyncIterator[None]:
    """
    Async context manager that catches any exception raised inside a registered
    MCP tool and re-maps it to a JSON-RPC 2.0 compliant error object.

    This ensures the QuantumMCPServer **never crashes** due to a tool-level
    failure.  Instead, a structured error response is returned to the calling
    agent, which can then implement its own retry or fallback logic.

    Usage
    -----
    ::

        async with mcp_error_interceptor("fetch_market_context"):
            result = await _fetch_openbb_data(symbol)
            return result

    Parameters
    ----------
    tool_name : str
        The name of the MCP tool being executed (for logging context).
    request_id : Any, optional
        The JSON-RPC request ID for correlation in error logs.

    Yields
    ------
    None
        Control is yielded to the caller's ``async with`` body.

    Raises
    ------
    QuantumMCPBaseError
        Re-raises any ``QuantumMCPBaseError`` subclass unchanged.
    InternalError
        Wraps any other unhandled exception as an ``InternalError``.

    Examples
    --------
    >>> async with mcp_error_interceptor("route_execution_order", request_id=42):
    ...     result = await _send_mt5_order(symbol, action, lot, sl, tp)
    """
    try:
        yield
    except QuantumMCPBaseError:
        # Already classified — re-raise as-is, logging at WARNING level
        logger.warning(
            "[MCPErrorInterceptor] Tool=%r | Classified error raised | id=%s",
            tool_name,
            request_id,
        )
        raise
    except Exception as exc:
        # Attempt to map to a known subclass
        mapped_cls: Type[QuantumMCPBaseError] = EXCEPTION_MAP.get(
            type(exc), InternalError
        )
        logger.error(
            "[MCPErrorInterceptor] Tool=%r | Unhandled %s → mapped to %s | id=%s | msg=%s",
            tool_name,
            type(exc).__name__,
            mapped_cls.__name__,
            request_id,
            exc,
            exc_info=True,
        )
        # Wrap with full traceback in data field
        raise InternalError(
            message=f"Unhandled exception in tool '{tool_name}': {exc}",
            original_exception=exc,
        ) from exc


def tool_error_guard(tool_name: str) -> Callable:
    """
    Function decorator that wraps any async MCP tool with ``mcp_error_interceptor``.

    Use this decorator on registered tool functions to eliminate boilerplate
    try/except blocks and guarantee JSON-RPC error compliance.

    Parameters
    ----------
    tool_name : str
        Tool name to embed in error logs (should match the ``@server.tool()`` name).

    Returns
    -------
    Callable
        Decorated async function with automatic error interception.

    Examples
    --------
    >>> @server.tool()
    ... @tool_error_guard("fetch_market_context")
    ... async def fetch_market_context(symbol: str, lookback: int = 64) -> str:
    ...     ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with mcp_error_interceptor(tool_name):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
