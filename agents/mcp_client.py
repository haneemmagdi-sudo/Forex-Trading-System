"""
==============================================================================
agents/mcp_client.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Universal Agent-Side MCP Client Router
Author : Principal Integration Architect
Version: 4.2.0

Overview
--------
Implements the ``QuantumMCPClient`` — a reusable, robust async MCP client
that any AI agent (Analyst, Planner, Monitor, RiskManager) can instantiate
to communicate with the ``QuantumMCPServer`` over a stdio transport bridge.

Design Principle
----------------
The client provides a **single, universal tool-invocation gateway**:

    ``await client.call_environmental_tool(tool_name, arguments)``

This eliminates all bespoke connection logic from individual agents. An agent
that previously required 3 separate SDKs (OpenBB, Hyperliquid, MT5) now
only depends on this single client class.

Architecture
------------
::

    AI Agent (e.g., QuantumPlannerAgent)
        │
        │  await call_environmental_tool("fetch_market_context", {...})
        ▼
    QuantumMCPClient (this module)
        │  stdio transport bridge (subprocess stdin/stdout pipe)
        │  JSON-RPC 2.0 protocol messages
        ▼
    QuantumMCPServer (mcp_server/quantum_server.py)
        │
        ├──▶ OpenBB Platform v4     (historical OHLCV)
        ├──▶ Hyperliquid REST API   (orderbook + funding)
        └──▶ MetaTrader 5 Terminal  (portfolio state + execution)

Connection Lifecycle
--------------------
The client manages a complete async lifecycle:

    1. ``__aenter__`` / ``connect()``  — Spawn the server subprocess, establish
       the stdio transport, perform MCP handshake (initialize → initialized).
    2. ``call_environmental_tool()``   — Invoke a tool with full error handling,
       latency monitoring, and automatic retry on transient failures.
    3. ``list_tools()``               — Discover available tools at runtime.
    4. ``__aexit__`` / ``disconnect()`` — Gracefully terminate the subprocess.

Transport Security Note
-----------------------
Stdio transport is used for local IPC (same machine) due to its zero-overhead
process-to-process communication. For remote deployments (cloud agents),
replace the StdioServerParameters with an SSE/WebSocket transport URL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# MCP SDK imports
# ---------------------------------------------------------------------------
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from mcp_server.exceptions import (
    InternalError,
    InvalidParamsError,
    MethodNotFoundError,
    MT5DisconnectedError,
    QuantumMCPBaseError,
    JsonRpcCode,
)

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.mcp.client")

# ---------------------------------------------------------------------------
# Client configuration constants
# ---------------------------------------------------------------------------
_CLIENT_VERSION:          str   = "4.2.0"
_DEFAULT_CALL_TIMEOUT:    float = 30.0     # seconds per tool call
_DEFAULT_CONNECT_TIMEOUT: float = 15.0     # seconds to establish connection
_DEFAULT_MAX_RETRIES:     int   = 3        # retry count for transient failures
_RETRY_BACKOFF_BASE:      float = 1.0      # exponential backoff base (seconds)
_LATENCY_WARN_THRESHOLD:  float = 5.0      # log WARNING if call > 5 seconds


# ===========================================================================
# ToolCallResult — Standardized Return Envelope
# ===========================================================================

class ToolCallResult:
    """
    Standardized, immutable result envelope returned by ``call_environmental_tool``.

    Every tool call — whether successful or failed — returns a ``ToolCallResult``.
    This ensures calling agents never need to branch on exception types; they
    instead check ``result.success`` and branch on the returned data.

    Attributes
    ----------
    success : bool
        True if the tool call completed without errors.
    tool_name : str
        The name of the tool that was invoked.
    data : dict
        The parsed JSON response from the tool.  On success, contains the tool's
        response schema.  On failure, contains the JSON-RPC error object under
        the ``"error"`` key.
    raw_text : str
        The raw text content string returned by the MCP server.
    latency_ms : float
        Wall-clock latency of the tool call in milliseconds.
    retries_used : int
        Number of retry attempts made before this result was received.
    error_code : int or None
        The JSON-RPC error code if ``success=False``; None otherwise.
    error_message : str or None
        Human-readable error description if ``success=False``; None otherwise.

    Examples
    --------
    >>> result = await client.call_environmental_tool(
    ...     "fetch_market_context", {"symbol": "EURUSD", "lookback": 32}
    ... )
    >>> if result.success:
    ...     close = result.data["openbb"]["latest_close"]
    ...     spread = result.data["hyperliquid"]["spread_bps"]
    ... else:
    ...     print(f"Tool failed: {result.error_message} (code={result.error_code})")
    """

    __slots__ = (
        "success", "tool_name", "data", "raw_text",
        "latency_ms", "retries_used", "error_code", "error_message",
    )

    def __init__(
        self,
        success: bool,
        tool_name: str,
        data: Dict[str, Any],
        raw_text: str,
        latency_ms: float,
        retries_used: int = 0,
        error_code: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self.success:       bool            = success
        self.tool_name:     str             = tool_name
        self.data:          Dict[str, Any]  = data
        self.raw_text:      str             = raw_text
        self.latency_ms:    float           = latency_ms
        self.retries_used:  int             = retries_used
        self.error_code:    Optional[int]   = error_code
        self.error_message: Optional[str]   = error_message

    def __repr__(self) -> str:
        status = "OK" if self.success else f"ERR({self.error_code})"
        return (
            f"ToolCallResult(tool={self.tool_name!r}, "
            f"status={status}, "
            f"latency={self.latency_ms:.1f}ms, "
            f"retries={self.retries_used})"
        )


# ===========================================================================
# QuantumMCPClient — Universal Agent-Side MCP Client Router
# ===========================================================================

class QuantumMCPClient:
    """
    Universal MCP client router for the Quantum FSM Pro V4.2 Elite system.

    Any AI agent that needs access to market data, portfolio state, or order
    execution should instantiate this class and use ``call_environmental_tool``
    as its sole gateway to all environmental interactions.

    Parameters
    ----------
    server_script_path : str or Path, optional
        Absolute path to ``mcp_server/quantum_server.py``.
        Defaults to ``<project_root>/mcp_server/quantum_server.py``
        (resolved relative to this file's location).
    python_executable : str, optional
        Python interpreter to use for launching the server subprocess.
        Defaults to ``sys.executable`` (same interpreter as the client).
    call_timeout : float, optional
        Per-tool-call timeout in seconds.  Default: 30.0.
    max_retries : int, optional
        Maximum retry attempts on transient failures (connection resets,
        timeouts).  Default: 3.
    log_latency : bool, optional
        Whether to log latency metrics for every tool call.  Default: True.

    Examples
    --------
    **As an async context manager (recommended):**

    >>> async with QuantumMCPClient() as client:
    ...     result = await client.call_environmental_tool(
    ...         "fetch_market_context",
    ...         {"symbol": "EURUSD", "lookback": 64}
    ...     )
    ...     if result.success:
    ...         print(result.data["openbb"]["latest_close"])

    **Manual lifecycle management:**

    >>> client = QuantumMCPClient(call_timeout=45.0)
    >>> await client.connect()
    >>> result = await client.call_environmental_tool(
    ...     "fetch_mt5_portfolio_state", {}
    ... )
    >>> await client.disconnect()
    """

    def __init__(
        self,
        server_script_path: Optional[str] = None,
        python_executable: str = sys.executable,
        call_timeout: float = _DEFAULT_CALL_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        log_latency: bool = True,
    ) -> None:
        """Initialize the QuantumMCPClient with transport configuration."""
        # Resolve server script path
        if server_script_path is not None:
            self._server_path: Path = Path(server_script_path).resolve()
        else:
            # Default: <project_root>/mcp_server/quantum_server.py
            # This file is at agents/mcp_client.py, so project root is one level up
            self._server_path = (
                Path(__file__).parent.parent / "mcp_server" / "quantum_server.py"
            ).resolve()

        if not self._server_path.exists():
            raise FileNotFoundError(
                f"QuantumMCPServer script not found at: {self._server_path}\n"
                f"Ensure mcp_server/quantum_server.py exists in the project root."
            )

        self._python_executable:  str   = python_executable
        self._call_timeout:       float = call_timeout
        self._max_retries:        int   = max_retries
        self._log_latency:        bool  = log_latency

        # Connection state
        self._session:   Optional[ClientSession] = None
        self._connected: bool = False

        # Async context manager internals
        self._stdio_ctx:    Any = None
        self._session_ctx:  Any = None
        self._read_stream:  Any = None
        self._write_stream: Any = None

        # Performance metrics
        self._total_calls:    int   = 0
        self._failed_calls:   int   = 0
        self._total_latency:  float = 0.0

        logger.info(
            "[QuantumMCPClient] Initialized | server=%s | "
            "timeout=%.1fs | max_retries=%d",
            self._server_path.name,
            self._call_timeout,
            self._max_retries,
        )

    # -------------------------------------------------------------------
    # Async Context Manager Protocol
    # -------------------------------------------------------------------

    async def __aenter__(self) -> "QuantumMCPClient":
        """Enter async context — connect to the MCP server."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context — disconnect from the MCP server."""
        await self.disconnect()

    # -------------------------------------------------------------------
    # Connection Lifecycle
    # -------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Establish the stdio transport bridge to the QuantumMCPServer.

        Spawns the server as a subprocess using the configured Python
        interpreter, then performs the MCP protocol handshake (initialize
        request → initialized notification).

        This method is idempotent — calling it when already connected is
        a no-op.

        Raises
        ------
        ConnectionRefusedError
            If the server subprocess cannot be started.
        asyncio.TimeoutError
            If the handshake does not complete within ``_DEFAULT_CONNECT_TIMEOUT``.

        Examples
        --------
        >>> client = QuantumMCPClient()
        >>> await client.connect()
        >>> print(client.is_connected)
        True
        """
        if self._connected and self._session is not None:
            logger.debug("[QuantumMCPClient] Already connected — skipping.")
            return

        logger.info(
            "[QuantumMCPClient] Connecting to server | path=%s",
            self._server_path,
        )
        connect_start = time.time()

        try:
            server_params = StdioServerParameters(
                command=self._python_executable,
                args=[str(self._server_path)],
                env=None,  # Inherit parent process environment (includes .env vars)
            )

            # Enter the stdio transport context
            self._stdio_ctx = stdio_client(server_params)
            transport = await asyncio.wait_for(
                self._stdio_ctx.__aenter__(),
                timeout=_DEFAULT_CONNECT_TIMEOUT,
            )
            self._read_stream, self._write_stream = transport

            # Create and initialize the MCP session
            self._session_ctx = ClientSession(self._read_stream, self._write_stream)
            self._session = await self._session_ctx.__aenter__()

            # Perform MCP initialize handshake
            init_result = await asyncio.wait_for(
                self._session.initialize(),
                timeout=_DEFAULT_CONNECT_TIMEOUT,
            )

            self._connected = True
            elapsed_ms = (time.time() - connect_start) * 1000

            logger.info(
                "[QuantumMCPClient] Connected | server_name=%s | "
                "server_version=%s | elapsed=%.1fms",
                init_result.serverInfo.name     if init_result.serverInfo else "unknown",
                init_result.serverInfo.version  if init_result.serverInfo else "unknown",
                elapsed_ms,
            )

        except asyncio.TimeoutError:
            logger.error(
                "[QuantumMCPClient] Connection timed out after %.1fs.",
                _DEFAULT_CONNECT_TIMEOUT,
            )
            await self._cleanup_transport()
            raise ConnectionRefusedError(
                f"QuantumMCPServer handshake timed out after "
                f"{_DEFAULT_CONNECT_TIMEOUT}s. Ensure the server script "
                f"at {self._server_path} is valid and executable."
            )
        except Exception as exc:
            logger.error(
                "[QuantumMCPClient] Connection failed: %s", exc, exc_info=True
            )
            await self._cleanup_transport()
            raise ConnectionRefusedError(
                f"Failed to connect to QuantumMCPServer: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """
        Gracefully terminate the stdio transport bridge and shut down the
        server subprocess.

        Logs a session performance summary (total calls, failure rate,
        average latency) on exit.

        This method is idempotent — calling it when already disconnected
        is a no-op.
        """
        if not self._connected:
            return

        logger.info(
            "[QuantumMCPClient] Disconnecting | total_calls=%d | "
            "failed=%d | avg_latency=%.1fms",
            self._total_calls,
            self._failed_calls,
            (self._total_latency / max(self._total_calls, 1)),
        )

        await self._cleanup_transport()
        self._connected = False

    async def _cleanup_transport(self) -> None:
        """
        Internal: safely exit the session and stdio context managers.

        Suppresses all exceptions during teardown to ensure the client
        can always clean up even after a partial initialization failure.
        """
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("[QuantumMCPClient] Session ctx exit error: %s", exc)
            finally:
                self._session_ctx = None
                self._session = None

        if self._stdio_ctx is not None:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("[QuantumMCPClient] Stdio ctx exit error: %s", exc)
            finally:
                self._stdio_ctx = None

    @property
    def is_connected(self) -> bool:
        """Return True if the client has an active session with the server."""
        return self._connected and self._session is not None

    # -------------------------------------------------------------------
    # Core Tool Invocation Middleware
    # -------------------------------------------------------------------

    async def call_environmental_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> ToolCallResult:
        """
        Invoke a registered tool on the QuantumMCPServer and return a
        standardized ``ToolCallResult`` envelope.

        This is the **primary API method** for all agents. It abstracts:
            - JSON-RPC 2.0 protocol encoding/decoding
            - Execution latency measurement and logging
            - Automatic retry with exponential backoff for transient errors
            - Structured error response parsing
            - Auto-reconnection on dropped connections

        Parameters
        ----------
        tool_name : str
            The tool to invoke.  Must be one of:
            ``"fetch_market_context"``, ``"fetch_mt5_portfolio_state"``,
            ``"route_execution_order"``.
        arguments : dict
            Tool-specific argument dictionary.  Values must be JSON-serializable.
            Validated by the server's Pydantic v2 schema before execution.
        timeout : float, optional
            Per-call timeout override in seconds.  Defaults to the client's
            configured ``call_timeout`` value.

        Returns
        -------
        ToolCallResult
            Standardized result envelope.  Always returns (never raises).

        Retry Policy
        ------------
        Transient failures (``ConnectionResetError``, ``asyncio.TimeoutError``,
        ``BrokenPipeError``) are retried up to ``max_retries`` times with
        exponential backoff: wait = backoff_base × 2^(attempt - 1)
            Attempt 1: 0s wait (immediate)
            Attempt 2: 1s wait
            Attempt 3: 2s wait

        Non-transient failures (``InvalidParamsError``, ``MethodNotFoundError``,
        ``OrderRejectedError``) are not retried.

        Examples
        --------
        >>> result = await client.call_environmental_tool(
        ...     "route_execution_order",
        ...     {
        ...         "symbol":   "EURUSD",
        ...         "action":   "BUY",
        ...         "lot_size": 0.10,
        ...         "sl_pips":  30.0,
        ...         "tp_pips":  60.0,
        ...     }
        ... )
        >>> if result.success:
        ...     ticket = result.data["ticket"]
        ...     price  = result.data["entry_price"]
        ... else:
        ...     logger.error(result.error_message)
        """
        if not tool_name.strip():
            return self._make_error_result(
                tool_name=tool_name,
                latency_ms=0.0,
                error_code=JsonRpcCode.INVALID_PARAMS,
                error_message="tool_name must be a non-empty string.",
                retries_used=0,
            )

        effective_timeout = timeout if timeout is not None else self._call_timeout
        self._total_calls += 1
        call_start = time.time()
        retries_used: int = 0

        # Non-transient error codes that should NOT be retried
        _NON_RETRYABLE_CODES: set = {
            JsonRpcCode.INVALID_PARAMS,
            JsonRpcCode.METHOD_NOT_FOUND,
            JsonRpcCode.INVALID_REQUEST,
            JsonRpcCode.ORDER_REJECTED,
            JsonRpcCode.SYMBOL_NOT_FOUND,
            JsonRpcCode.INSUFFICIENT_MARGIN,
        }
        # Exception types that indicate transient network/process failures
        _TRANSIENT_EXCEPTIONS: tuple = (
            ConnectionResetError,
            BrokenPipeError,
            asyncio.TimeoutError,
            ConnectionAbortedError,
            EOFError,
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            # Exponential backoff for retry attempts (skip on first attempt)
            if attempt > 1:
                backoff = _RETRY_BACKOFF_BASE * (2 ** (attempt - 2))
                logger.warning(
                    "[QuantumMCPClient] Retry %d/%d for tool '%s' | "
                    "backoff=%.1fs | last_error=%s",
                    attempt,
                    self._max_retries,
                    tool_name,
                    backoff,
                    last_error,
                )
                await asyncio.sleep(backoff)

                # Attempt to reconnect if the session was dropped
                if not self.is_connected:
                    try:
                        await self.connect()
                    except Exception as conn_exc:
                        logger.error(
                            "[QuantumMCPClient] Reconnect failed: %s", conn_exc
                        )
                        continue

            try:
                # ── Ensure connection is active ───────────────────────────
                if not self.is_connected:
                    await self.connect()

                # ── Execute the tool call via MCP session ─────────────────
                mcp_result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=effective_timeout,
                )

                # ── Parse raw response ────────────────────────────────────
                raw_text: str = ""
                if mcp_result.content:
                    # MCP returns a list of content blocks; join text blocks
                    text_blocks = [
                        block.text
                        for block in mcp_result.content
                        if hasattr(block, "text")
                    ]
                    raw_text = "".join(text_blocks)

                # ── Deserialize JSON response ─────────────────────────────
                latency_ms = (time.time() - call_start) * 1000
                self._total_latency += latency_ms
                retries_used = attempt - 1

                try:
                    parsed_data: Dict[str, Any] = json.loads(raw_text) if raw_text else {}
                except json.JSONDecodeError as jde:
                    logger.warning(
                        "[QuantumMCPClient] JSON decode error for tool '%s': %s",
                        tool_name,
                        jde,
                    )
                    parsed_data = {"raw_text": raw_text}

                # ── Check if the tool returned a JSON-RPC error object ────
                if "error" in parsed_data:
                    err_obj = parsed_data["error"]
                    err_code    = err_obj.get("code",    JsonRpcCode.INTERNAL_ERROR)
                    err_message = err_obj.get("message", "Unknown error from server.")
                    self._failed_calls += 1

                    if self._log_latency:
                        logger.warning(
                            "[QuantumMCPClient] Tool '%s' returned error | "
                            "code=%d | msg=%s | latency=%.1fms | retries=%d",
                            tool_name,
                            err_code,
                            err_message,
                            latency_ms,
                            retries_used,
                        )

                    # Only retry transient error codes
                    if err_code not in _NON_RETRYABLE_CODES and attempt < self._max_retries:
                        last_error = Exception(err_message)
                        continue

                    return self._make_error_result(
                        tool_name=tool_name,
                        latency_ms=latency_ms,
                        error_code=err_code,
                        error_message=err_message,
                        retries_used=retries_used,
                        data=parsed_data,
                    )

                # ── Success path ──────────────────────────────────────────
                if self._log_latency:
                    level = logging.WARNING if latency_ms > _LATENCY_WARN_THRESHOLD * 1000 else logging.DEBUG
                    logger.log(
                        level,
                        "[QuantumMCPClient] Tool '%s' OK | latency=%.1fms | retries=%d",
                        tool_name,
                        latency_ms,
                        retries_used,
                    )

                return ToolCallResult(
                    success=True,
                    tool_name=tool_name,
                    data=parsed_data,
                    raw_text=raw_text,
                    latency_ms=latency_ms,
                    retries_used=retries_used,
                    error_code=None,
                    error_message=None,
                )

            except _TRANSIENT_EXCEPTIONS as exc:
                last_error = exc
                logger.warning(
                    "[QuantumMCPClient] Transient error on attempt %d/%d "
                    "for tool '%s': %s",
                    attempt,
                    self._max_retries,
                    tool_name,
                    exc,
                )
                # Mark connection as dropped so reconnect is attempted next retry
                self._connected = False
                continue

            except Exception as exc:
                # Non-transient — do not retry
                latency_ms = (time.time() - call_start) * 1000
                self._failed_calls += 1
                logger.error(
                    "[QuantumMCPClient] Non-transient error in tool '%s': %s",
                    tool_name,
                    exc,
                    exc_info=True,
                )
                return self._make_error_result(
                    tool_name=tool_name,
                    latency_ms=latency_ms,
                    error_code=JsonRpcCode.INTERNAL_ERROR,
                    error_message=f"Client-side exception: {exc}",
                    retries_used=attempt - 1,
                )

        # All retry attempts exhausted
        latency_ms = (time.time() - call_start) * 1000
        self._failed_calls += 1
        return self._make_error_result(
            tool_name=tool_name,
            latency_ms=latency_ms,
            error_code=JsonRpcCode.INTERNAL_ERROR,
            error_message=(
                f"Tool '{tool_name}' failed after {self._max_retries} attempts. "
                f"Last error: {last_error}"
            ),
            retries_used=self._max_retries,
        )

    # -------------------------------------------------------------------
    # Tool Discovery
    # -------------------------------------------------------------------

    async def list_tools(self) -> List[Tool]:
        """
        Discover all tools registered on the QuantumMCPServer at runtime.

        Returns
        -------
        List[mcp.types.Tool]
            List of Tool descriptor objects, each containing the tool's
            ``name``, ``description``, and ``inputSchema``.

        Raises
        ------
        ConnectionRefusedError
            If the client is not connected to the server.

        Examples
        --------
        >>> tools = await client.list_tools()
        >>> for tool in tools:
        ...     print(f"  {tool.name}: {tool.description[:60]}")
        """
        if not self.is_connected:
            raise ConnectionRefusedError(
                "Cannot list tools: QuantumMCPClient is not connected. "
                "Call await client.connect() first."
            )

        result = await self._session.list_tools()
        tools: List[Tool] = result.tools if result and result.tools else []

        logger.info(
            "[QuantumMCPClient] Discovered %d tools: %s",
            len(tools),
            [t.name for t in tools],
        )
        return tools

    # -------------------------------------------------------------------
    # High-Level Agent Convenience Methods
    # -------------------------------------------------------------------

    async def fetch_market_context(
        self,
        symbol: str,
        lookback: int = 64,
        provider: str = "yfinance",
        include_funding: bool = True,
    ) -> ToolCallResult:
        """
        Convenience method: fetch unified market context for a symbol.

        Wraps ``call_environmental_tool("fetch_market_context", ...)``
        with named parameters for ergonomic use by agents.

        Parameters
        ----------
        symbol : str
            Trading instrument symbol (e.g., "EURUSD", "BTC").
        lookback : int
            Number of historical bars.  Default: 64.
        provider : str
            OpenBB provider name.  Default: "yfinance".
        include_funding : bool
            Include Hyperliquid funding rate.  Default: True.

        Returns
        -------
        ToolCallResult
            Parsed market context envelope.

        Examples
        --------
        >>> result = await client.fetch_market_context("EURUSD", lookback=128)
        >>> if result.success:
        ...     bars = result.data["openbb"]["bars"]
        ...     funding = result.data["hyperliquid"]["funding_rate"]
        """
        return await self.call_environmental_tool(
            "fetch_market_context",
            {
                "symbol":          symbol,
                "lookback":        lookback,
                "openbb_provider": provider,
                "include_funding": include_funding,
            },
        )

    async def fetch_portfolio_state(
        self,
        include_positions: bool = True,
        max_position_count: int = 50,
    ) -> ToolCallResult:
        """
        Convenience method: fetch live MT5 portfolio state.

        Parameters
        ----------
        include_positions : bool
            Include open position list.  Default: True.
        max_position_count : int
            Maximum number of positions to return.  Default: 50.

        Returns
        -------
        ToolCallResult
            Portfolio state envelope with account metrics and positions.

        Examples
        --------
        >>> result = await client.fetch_portfolio_state()
        >>> if result.success:
        ...     equity = result.data["account"]["equity"]
        ...     dd_pct = result.data["account"]["drawdown_pct"]
        ...     positions = result.data["positions"]
        """
        return await self.call_environmental_tool(
            "fetch_mt5_portfolio_state",
            {
                "include_positions":  include_positions,
                "max_position_count": max_position_count,
            },
        )

    async def execute_order(
        self,
        symbol: str,
        action: str,
        lot_size: float,
        sl_pips: float,
        tp_pips: float,
        comment: str = "QuantumFSM_MCP",
        magic_override: Optional[int] = None,
    ) -> ToolCallResult:
        """
        Convenience method: route an execution order through the MCP server.

        This is the **single legal entry point** for all trade execution
        from any AI agent.  All orders route through the QuantumMCPServer's
        risk-validated MT5 gateway.

        Parameters
        ----------
        symbol : str
            MT5 instrument symbol.
        action : str
            Direction: "BUY" or "SELL".
        lot_size : float
            Trade volume in standard lots (0.01 – 100.0).
        sl_pips : float
            Stop-loss distance in pips (1.0 – 500.0).
        tp_pips : float
            Take-profit distance in pips (1.0 – 1000.0).
        comment : str
            MT5 order comment.  Max 31 chars.  Default: "QuantumFSM_MCP".
        magic_override : int, optional
            Custom magic number override.  None = use server default.

        Returns
        -------
        ToolCallResult
            Execution receipt envelope.

        Examples
        --------
        >>> result = await client.execute_order(
        ...     symbol="EURUSD",
        ...     action="BUY",
        ...     lot_size=0.10,
        ...     sl_pips=30.0,
        ...     tp_pips=60.0,
        ... )
        >>> if result.success and result.data.get("status") == "EXECUTED":
        ...     ticket = result.data["ticket"]
        ...     print(f"Trade opened: ticket={ticket}")
        """
        args: Dict[str, Any] = {
            "symbol":   symbol,
            "action":   action,
            "lot_size": lot_size,
            "sl_pips":  sl_pips,
            "tp_pips":  tp_pips,
            "comment":  comment,
        }
        if magic_override is not None:
            args["magic_override"] = magic_override

        return await self.call_environmental_tool("route_execution_order", args)

    # -------------------------------------------------------------------
    # Performance Telemetry
    # -------------------------------------------------------------------

    def get_session_metrics(self) -> Dict[str, Any]:
        """
        Return a performance telemetry snapshot for this client session.

        Returns
        -------
        dict
            Session metrics with the following keys:
            - ``total_calls`` (int): Total number of tool calls made.
            - ``failed_calls`` (int): Number of calls that returned errors.
            - ``success_rate_pct`` (float): Percentage of successful calls.
            - ``avg_latency_ms`` (float): Average wall-clock latency per call.
            - ``is_connected`` (bool): Current connection state.
            - ``server_path`` (str): Path to the server script.
            - ``client_version`` (str): Client version string.

        Examples
        --------
        >>> metrics = client.get_session_metrics()
        >>> print(f"Success rate: {metrics['success_rate_pct']:.1f}%")
        """
        success_calls = max(0, self._total_calls - self._failed_calls)
        success_rate  = (success_calls / max(self._total_calls, 1)) * 100.0
        avg_latency   = self._total_latency / max(self._total_calls, 1)

        return {
            "total_calls":       self._total_calls,
            "failed_calls":      self._failed_calls,
            "success_rate_pct":  round(success_rate, 2),
            "avg_latency_ms":    round(avg_latency, 2),
            "is_connected":      self.is_connected,
            "server_path":       str(self._server_path),
            "client_version":    _CLIENT_VERSION,
        }

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return (
            f"QuantumMCPClient("
            f"status={status}, "
            f"calls={self._total_calls}, "
            f"failed={self._failed_calls}, "
            f"timeout={self._call_timeout}s)"
        )

    # -------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _make_error_result(
        tool_name: str,
        latency_ms: float,
        error_code: int,
        error_message: str,
        retries_used: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> ToolCallResult:
        """
        Build a failed ``ToolCallResult`` with error fields populated.

        Parameters
        ----------
        tool_name : str
            Name of the tool that failed.
        latency_ms : float
            Total wall-clock time including retry delays.
        error_code : int
            JSON-RPC 2.0 error code.
        error_message : str
            Human-readable error description.
        retries_used : int
            Number of retry attempts made.
        data : dict, optional
            Optional parsed data payload (may contain error details).

        Returns
        -------
        ToolCallResult
        """
        return ToolCallResult(
            success=False,
            tool_name=tool_name,
            data=data or {"error": {"code": error_code, "message": error_message}},
            raw_text=json.dumps({"error": {"code": error_code, "message": error_message}}),
            latency_ms=latency_ms,
            retries_used=retries_used,
            error_code=error_code,
            error_message=error_message,
        )


# ===========================================================================
# Factory Helper — Managed Client Context
# ===========================================================================

@asynccontextmanager
async def quantum_mcp_session(
    server_script_path: Optional[str] = None,
    call_timeout: float = _DEFAULT_CALL_TIMEOUT,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> AsyncIterator[QuantumMCPClient]:
    """
    Async context manager factory for creating a fully managed client session.

    Preferred over manual ``__aenter__`` / ``__aexit__`` for one-off usage
    patterns where the caller wants zero lifecycle boilerplate.

    Parameters
    ----------
    server_script_path : str, optional
        Override the path to ``quantum_server.py``.
    call_timeout : float
        Per-call timeout in seconds.  Default: 30.0.
    max_retries : int
        Maximum retry attempts.  Default: 3.

    Yields
    ------
    QuantumMCPClient
        A fully connected, ready-to-use client instance.

    Examples
    --------
    >>> async with quantum_mcp_session() as client:
    ...     result = await client.fetch_portfolio_state()
    ...     equity = result.data["account"]["equity"]
    """
    client = QuantumMCPClient(
        server_script_path=server_script_path,
        call_timeout=call_timeout,
        max_retries=max_retries,
    )
    async with client:
        yield client
