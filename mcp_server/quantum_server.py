"""
==============================================================================
mcp_server/quantum_server.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Centralized Asynchronous MCP Server
Author : Principal Integration Architect
Version: 4.2.0

Overview
--------
Implements the ``QuantumMCPServer`` — a JSON-RPC 2.0 compliant, fully
asynchronous Model Context Protocol server that exposes three production
tools as a unified, vendor-neutral interface for all downstream AI agents:

    Tool A: fetch_market_context      — OpenBB v4 historical data +
                                        Hyperliquid live orderbook & funding
    Tool B: fetch_mt5_portfolio_state — Live MT5 account equity, margin,
                                        leverage, and drawdown snapshot
    Tool C: route_execution_order     — Atomic MT5 order_send execution with
                                        tick-value computation and receipt

Architectural Integration
--------------------------
Before MCP (tight coupling, N×M complexity):
    Agent1 → OpenBB (direct)
    Agent1 → Hyperliquid (direct)
    Agent1 → MT5 (direct)
    Agent2 → OpenBB (direct)
    Agent2 → Hyperliquid (direct)  ...etc

After MCP (decoupled, N+M linear complexity):
    Agent1 → QuantumMCPClient → QuantumMCPServer → OpenBB
                                                  → Hyperliquid
                                                  → MT5
    Agent2 → QuantumMCPClient → QuantumMCPServer (same server, shared)

Hyperliquid API Reference
--------------------------
Base URL: https://api.hyperliquid.xyz/info (POST, application/json)

    OrderBook : {"type": "l2Book", "coin": "<COIN>"}
    Funding   : {"type": "metaAndAssetCtxs"}
    Ticker    : {"type": "allMids"}

OpenBB Platform v4 Reference
------------------------------
    from openbb import obb
    hist  = obb.equity.price.historical(symbol=sym, provider="yfinance")
    macro = obb.economy.fred_series(symbol="DFF")  # Fed Funds Rate

Transport
---------
The server runs over stdio transport for local process-to-process IPC.
For remote deployments, replace ``stdio_server()`` with an SSE/WebSocket
transport from the ``mcp`` library.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

import httpx
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# MCP SDK imports — official Model Context Protocol Python SDK
# ---------------------------------------------------------------------------
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from mcp_server.exceptions import (
    HyperliquidTimeoutError,
    InternalError,
    InvalidParamsError,
    MT5DisconnectedError,
    OpenBBProviderError,
    OrderRejectedError,
    InsufficientMarginError,
    SymbolNotFoundError,
    mcp_error_interceptor,
)

# ---------------------------------------------------------------------------
# Conditional provider imports
# ---------------------------------------------------------------------------
try:
    from openbb import obb as _OBB
    _OPENBB_AVAILABLE: bool = True
except ImportError:
    _OBB = None  # type: ignore[assignment]
    _OPENBB_AVAILABLE: bool = False

try:
    import MetaTrader5 as _mt5
    _MT5_AVAILABLE: bool = True
except ImportError:
    _mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE: bool = False

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("quantum_fsm.mcp.server")

# ---------------------------------------------------------------------------
# Global configuration constants
# ---------------------------------------------------------------------------
_HYPERLIQUID_BASE_URL: str   = "https://api.hyperliquid.xyz/info"
_HYPERLIQUID_TIMEOUT:  float = 8.0       # seconds — raise HyperliquidTimeoutError if exceeded
_OPENBB_LOOKBACK_MAX:  int   = 500       # maximum bars returned by OpenBB
_MT5_MAGIC_NUMBER:     int   = 442001    # unique identifier for all orders from this server
_MT5_DEVIATION:        int   = 20        # maximum price deviation in points
_DATA_FRESHNESS_TTL:   int   = 120       # seconds before market data is considered stale
_SERVER_VERSION:       str   = "4.2.0"


# ===========================================================================
# Pydantic v2 Argument Schemas — validated before tool execution
# ===========================================================================

class FetchMarketContextArgs(BaseModel):
    """
    Validated argument schema for the ``fetch_market_context`` tool.

    Attributes
    ----------
    symbol : str
        Trading instrument symbol.  For MT5 forex: "EURUSD", "GBPUSD", etc.
        For Hyperliquid crypto: "BTC", "ETH", "SOL", etc.
        Must be 1–20 uppercase alphanumeric characters.
    lookback : int
        Number of historical bars to fetch from OpenBB.
        Clamped to [1, 500].  Default: 64.
    openbb_provider : str
        OpenBB data provider to use for historical OHLCV data.
        Default: "yfinance" (free, no API key required).
    include_funding : bool
        Whether to query Hyperliquid funding rate data.
        Default: True.
    """

    model_config = {"frozen": True}

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Trading instrument symbol (e.g., 'EURUSD', 'BTC').",
    )
    lookback: int = Field(
        default=64,
        ge=1,
        le=_OPENBB_LOOKBACK_MAX,
        description="Number of historical OHLCV bars to return from OpenBB.",
    )
    openbb_provider: str = Field(
        default="yfinance",
        description="OpenBB provider to use for historical data fetch.",
    )
    include_funding: bool = Field(
        default=True,
        description="Whether to include Hyperliquid funding rate in the response.",
    )

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        """Strip whitespace and convert to uppercase."""
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol must be a non-empty string after stripping.")
        return v


class FetchMT5PortfolioStateArgs(BaseModel):
    """
    Validated argument schema for the ``fetch_mt5_portfolio_state`` tool.

    This tool takes no user-supplied parameters — all state is fetched
    directly from the connected MT5 terminal. The schema exists for
    JSON-RPC protocol compliance and potential future filtering args.

    Attributes
    ----------
    include_positions : bool
        Whether to include the full list of open positions.  Default: True.
    max_position_count : int
        Maximum number of open positions to return.  Default: 50.
    """

    model_config = {"frozen": True}

    include_positions: bool = Field(
        default=True,
        description="Include open positions list in the response.",
    )
    max_position_count: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of open positions to return.",
    )


class RouteExecutionOrderArgs(BaseModel):
    """
    Validated argument schema for the ``route_execution_order`` tool.

    All numerical parameters are range-validated to prevent catastrophic
    mis-trades from misconfigured agent outputs.

    Attributes
    ----------
    symbol : str
        MT5 instrument symbol (e.g., "EURUSD", "GBPJPY").
    action : str
        Trade direction: must be exactly "BUY" or "SELL".
    lot_size : float
        Trade volume in standard lots.  Range: [0.01, 100.0].
    sl_pips : float
        Stop-loss distance in pips from entry price.  Range: [1.0, 500.0].
    tp_pips : float
        Take-profit distance in pips from entry price.  Range: [1.0, 1000.0].
    comment : str
        Order comment tag (max 31 characters, MT5 limit).
    magic_override : int, optional
        Override the default magic number.  If None, uses ``_MT5_MAGIC_NUMBER``.
    """

    model_config = {"frozen": True}

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="MT5 instrument symbol for the order.",
    )
    action: str = Field(
        ...,
        description="Trade direction: 'BUY' or 'SELL'.",
    )
    lot_size: float = Field(
        ...,
        ge=0.01,
        le=100.0,
        description="Trade volume in standard lots.",
    )
    sl_pips: float = Field(
        ...,
        ge=1.0,
        le=500.0,
        description="Stop-loss distance in pips from entry.",
    )
    tp_pips: float = Field(
        ...,
        ge=1.0,
        le=1000.0,
        description="Take-profit distance in pips from entry.",
    )
    comment: str = Field(
        default="QuantumFSM_MCP",
        max_length=31,
        description="MT5 order comment tag (max 31 chars).",
    )
    magic_override: Optional[int] = Field(
        default=None,
        description="Override magic number. None = use server default.",
    )

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("BUY", "SELL"):
            raise ValueError(f"action must be 'BUY' or 'SELL'; received {v!r}.")
        return v


# ===========================================================================
# QuantumMCPServer — Centralized Tool Registration and Runtime
# ===========================================================================

class QuantumMCPServer:
    """
    Asynchronous MCP Server that exposes OpenBB, Hyperliquid, and MetaTrader 5
    as standardized JSON-RPC 2.0 tools for all downstream AI agents.

    The server is instantiated once per process and runs indefinitely over
    the stdio transport, processing tool calls from any connected MCP client.

    Attributes
    ----------
    _server : mcp.server.Server
        The underlying MCP SDK server instance.
    _http_client : httpx.AsyncClient
        Shared async HTTP client for Hyperliquid REST calls.
        Uses HTTP/2 and a persistent connection pool.
    _mt5_initialized : bool
        Whether the MT5 terminal has been successfully initialized.
    _startup_ts : float
        UNIX timestamp when the server was started.
    """

    def __init__(self) -> None:
        """Initialize the QuantumMCPServer with all required provider clients."""
        self._server: Server = Server("QuantumMCPServer")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._mt5_initialized: bool = False
        self._startup_ts: float = time.time()

        # Register all tools on the server instance
        self._register_tools()

        logger.info(
            "[QuantumMCPServer] Initialized | version=%s | "
            "OpenBB=%s | MT5=%s",
            _SERVER_VERSION,
            "available" if _OPENBB_AVAILABLE else "unavailable",
            "available" if _MT5_AVAILABLE else "unavailable",
        )

    # -------------------------------------------------------------------
    # Server Lifecycle
    # -------------------------------------------------------------------

    async def _ensure_http_client(self) -> httpx.AsyncClient:
        """
        Lazily initialize the shared async HTTP client for Hyperliquid calls.

        Uses HTTP/2 for multiplexed connections and a persistent pool to
        minimize latency on repeated API calls.

        Returns
        -------
        httpx.AsyncClient
            The shared, initialized HTTP client instance.
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(
                    connect=4.0,
                    read=_HYPERLIQUID_TIMEOUT,
                    write=4.0,
                    pool=10.0,
                ),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent":   f"QuantumFSM-MCP/{_SERVER_VERSION}",
                    "Accept":       "application/json",
                },
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0,
                ),
            )
        return self._http_client

    def _initialize_mt5(self) -> bool:
        """
        Attempt to initialize and authenticate the MT5 terminal connection.

        Reads credentials from environment variables set in the project .env file:
            MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_TERMINAL_PATH

        Returns
        -------
        bool
            True if MT5 initialized successfully; False otherwise.
        """
        if not _MT5_AVAILABLE:
            logger.warning("[QuantumMCPServer] MetaTrader5 library not installed.")
            return False

        if self._mt5_initialized:
            return True

        terminal_path = os.getenv("MT5_TERMINAL_PATH", "")
        try:
            if terminal_path:
                success = _mt5.initialize(path=terminal_path.replace("/", "\\"))
            else:
                success = _mt5.initialize()

            if not success:
                logger.error(
                    "[QuantumMCPServer] mt5.initialize() failed: %s",
                    _mt5.last_error(),
                )
                return False

            login_id = int(os.getenv("MT5_LOGIN", "0"))
            if login_id > 0:
                authorized = _mt5.login(
                    login=login_id,
                    password=os.getenv("MT5_PASSWORD", ""),
                    server=os.getenv("MT5_SERVER", ""),
                    timeout=10_000,
                )
                if not authorized:
                    logger.error(
                        "[QuantumMCPServer] MT5 login failed: %s",
                        _mt5.last_error(),
                    )
                    _mt5.shutdown()
                    return False

            self._mt5_initialized = True
            info = _mt5.account_info()
            if info:
                logger.info(
                    "[QuantumMCPServer] MT5 connected | %d@%s | balance=%.2f",
                    info.login,
                    info.server,
                    info.balance,
                )
            return True

        except Exception as exc:
            logger.error("[QuantumMCPServer] MT5 init exception: %s", exc, exc_info=True)
            return False

    async def run(self) -> None:
        """
        Start the MCP server over stdio transport.

        This method blocks indefinitely, reading JSON-RPC messages from stdin
        and writing responses to stdout.  It is the entry point when this
        module is run as a subprocess by the MCP client.

        The server gracefully initializes the MT5 terminal on startup and
        shuts it down on process exit.

        Examples
        --------
        >>> import asyncio
        >>> server = QuantumMCPServer()
        >>> asyncio.run(server.run())
        """
        # Initialize MT5 on startup
        self._initialize_mt5()

        # Ensure HTTP client is ready
        await self._ensure_http_client()

        logger.info(
            "[QuantumMCPServer] Starting stdio transport | "
            "uptime=0s | pid=%d",
            os.getpid(),
        )

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        """Clean up all resources on server exit."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            logger.info("[QuantumMCPServer] HTTP client closed.")

        if _MT5_AVAILABLE and self._mt5_initialized:
            try:
                _mt5.shutdown()
                logger.info("[QuantumMCPServer] MT5 shutdown complete.")
            except Exception as exc:
                logger.warning("[QuantumMCPServer] MT5 shutdown error: %s", exc)

        uptime = time.time() - self._startup_ts
        logger.info(
            "[QuantumMCPServer] Server stopped | total_uptime=%.1fs",
            uptime,
        )

    # -------------------------------------------------------------------
    # Tool Registration
    # -------------------------------------------------------------------

    def _register_tools(self) -> None:
        """
        Register all three production tools with the MCP server instance.

        This method binds the ``list_tools`` and ``call_tool`` handlers to
        the server, making the tools discoverable by any connected MCP client.
        """
        server = self._server

        @server.list_tools()
        async def _handle_list_tools() -> List[types.Tool]:
            """Return the tool manifest — all tools registered on this server."""
            return [
                types.Tool(
                    name="fetch_market_context",
                    description=(
                        "Fetches unified market context for a given symbol by "
                        "combining OpenBB v4 historical OHLCV data with live "
                        "Hyperliquid orderbook spreads and funding rate metrics. "
                        "Returns a sanitized JSON string with macro + microstructure data."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading instrument symbol (e.g., 'EURUSD', 'BTC').",
                            },
                            "lookback": {
                                "type": "integer",
                                "default": 64,
                                "minimum": 1,
                                "maximum": 500,
                                "description": "Number of historical OHLCV bars to return.",
                            },
                            "openbb_provider": {
                                "type": "string",
                                "default": "yfinance",
                                "description": "OpenBB provider for historical data.",
                            },
                            "include_funding": {
                                "type": "boolean",
                                "default": True,
                                "description": "Whether to include Hyperliquid funding data.",
                            },
                        },
                        "required": ["symbol"],
                    },
                ),
                types.Tool(
                    name="fetch_mt5_portfolio_state",
                    description=(
                        "Returns a live snapshot of the MetaTrader 5 account state: "
                        "equity, balance, free margin, leverage, current drawdown percentage, "
                        "and the full list of open positions with profit/loss metrics."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_positions": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include open positions list in the response.",
                            },
                            "max_position_count": {
                                "type": "integer",
                                "default": 50,
                                "minimum": 1,
                                "maximum": 500,
                                "description": "Maximum number of positions to return.",
                            },
                        },
                        "required": [],
                    },
                ),
                types.Tool(
                    name="route_execution_order",
                    description=(
                        "Routes an atomic market order to MetaTrader 5. Computes "
                        "tick values, builds the TRADE_ACTION_DEAL request structure, "
                        "enforces SL/TP placement, and returns the execution receipt "
                        "(ticket number, fill price) or the exact broker error string."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symbol":   {"type": "string", "description": "MT5 instrument symbol."},
                            "action":   {"type": "string", "enum": ["BUY", "SELL"]},
                            "lot_size": {"type": "number", "minimum": 0.01, "maximum": 100.0},
                            "sl_pips":  {"type": "number", "minimum": 1.0, "maximum": 500.0},
                            "tp_pips":  {"type": "number", "minimum": 1.0, "maximum": 1000.0},
                            "comment":  {"type": "string", "maxLength": 31, "default": "QuantumFSM_MCP"},
                            "magic_override": {"type": "integer", "nullable": True},
                        },
                        "required": ["symbol", "action", "lot_size", "sl_pips", "tp_pips"],
                    },
                ),
            ]

        @server.call_tool()
        async def _handle_call_tool(
            name: str,
            arguments: Dict[str, Any],
        ) -> List[types.TextContent]:
            """
            Dispatch incoming tool calls to the appropriate handler method.

            Parameters
            ----------
            name : str
                The tool name as registered (e.g., ``"fetch_market_context"``).
            arguments : dict
                Raw argument dictionary from the JSON-RPC call payload.

            Returns
            -------
            List[types.TextContent]
                A single-element list containing the tool's JSON string result.
            """
            logger.info(
                "[QuantumMCPServer] Tool call received | name=%r | args_keys=%s",
                name,
                list((arguments or {}).keys()),
            )
            call_start = time.time()

            try:
                if name == "fetch_market_context":
                    result = await self._tool_fetch_market_context(arguments or {})
                elif name == "fetch_mt5_portfolio_state":
                    result = await self._tool_fetch_mt5_portfolio_state(arguments or {})
                elif name == "route_execution_order":
                    result = await self._tool_route_execution_order(arguments or {})
                else:
                    from mcp_server.exceptions import MethodNotFoundError
                    raise MethodNotFoundError(name)

            except Exception as exc:
                # All exceptions are serialized to JSON-RPC error strings
                if hasattr(exc, "to_tool_error_string"):
                    result = exc.to_tool_error_string()
                else:
                    wrapped = InternalError(
                        f"Unhandled error in tool '{name}': {exc}",
                        original_exception=exc,
                    )
                    result = wrapped.to_tool_error_string()
                logger.error(
                    "[QuantumMCPServer] Tool '%s' failed: %s",
                    name,
                    exc,
                )

            elapsed_ms = (time.time() - call_start) * 1000
            logger.info(
                "[QuantumMCPServer] Tool '%s' completed in %.2fms",
                name,
                elapsed_ms,
            )
            return [types.TextContent(type="text", text=result)]

    # -------------------------------------------------------------------
    # Tool A: fetch_market_context
    # -------------------------------------------------------------------

    async def _tool_fetch_market_context(
        self, raw_args: Dict[str, Any]
    ) -> str:
        """
        Tool A — Unified Market Context Fetcher.

        Execution Pipeline
        ------------------
        1. Validate arguments via ``FetchMarketContextArgs`` (Pydantic v2).
        2. Concurrently execute two async sub-tasks:
               a. ``_fetch_openbb_historical()``: Queries OpenBB Platform v4 for
                  OHLCV history using the provider chain.
               b. ``_fetch_hyperliquid_context()``: Queries Hyperliquid REST API
                  for live L2 orderbook (best bid/ask/spread) and funding rate.
        3. Merge results into a unified response dictionary.
        4. Serialize to a sanitized JSON string.

        Parameters
        ----------
        raw_args : dict
            Raw argument dictionary from the JSON-RPC call.

        Returns
        -------
        str
            JSON string with schema::

                {
                  "symbol":           str,
                  "timestamp_utc":    str,
                  "openbb": {
                    "provider":       str,
                    "lookback_bars":  int,
                    "bars":           [{"date": str, "open": float, "high": float,
                                        "low": float, "close": float, "volume": float}, ...],
                    "latest_close":   float,
                    "price_change_pct": float,
                    "available":      bool,
                    "error":          str | null
                  },
                  "hyperliquid": {
                    "best_bid":       float | null,
                    "best_ask":       float | null,
                    "spread_bps":     float | null,
                    "funding_rate":   float | null,
                    "open_interest":  float | null,
                    "mid_price":      float | null,
                    "available":      bool,
                    "error":          str | null
                  },
                  "server_version":   str
                }
        """
        async with mcp_error_interceptor("fetch_market_context"):
            # Step 1: Validate arguments
            try:
                args = FetchMarketContextArgs(**raw_args)
            except Exception as exc:
                raise InvalidParamsError(
                    f"Argument validation failed for fetch_market_context: {exc}",
                    validation_errors=exc,
                ) from exc

            logger.info(
                "[fetch_market_context] symbol=%r | lookback=%d | "
                "provider=%r | include_funding=%s",
                args.symbol,
                args.lookback,
                args.openbb_provider,
                args.include_funding,
            )

            # Step 2: Concurrently fetch OpenBB + Hyperliquid
            openbb_task = asyncio.create_task(
                self._fetch_openbb_historical(
                    symbol=args.symbol,
                    lookback=args.lookback,
                    provider=args.openbb_provider,
                )
            )
            hyperliquid_task = asyncio.create_task(
                self._fetch_hyperliquid_context(
                    coin=args.symbol,
                    include_funding=args.include_funding,
                )
            )

            openbb_result, hyperliquid_result = await asyncio.gather(
                openbb_task,
                hyperliquid_task,
                return_exceptions=True,
            )

            # Step 3: Normalize gather results (exceptions become dicts with error key)
            def _normalize_result(r: Any, source_name: str) -> Dict[str, Any]:
                if isinstance(r, Exception):
                    logger.warning(
                        "[fetch_market_context] %s fetch failed: %s",
                        source_name,
                        r,
                    )
                    return {
                        "available": False,
                        "error": str(r),
                    }
                return r

            openbb_data = _normalize_result(openbb_result, "OpenBB")
            hl_data     = _normalize_result(hyperliquid_result, "Hyperliquid")

            # Step 4: Build unified response
            import datetime
            response: Dict[str, Any] = {
                "symbol":        args.symbol,
                "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
                "openbb":        openbb_data,
                "hyperliquid":   hl_data,
                "server_version": _SERVER_VERSION,
            }

            result_str = json.dumps(response, default=str)
            logger.info(
                "[fetch_market_context] Response size=%d bytes | "
                "openbb_ok=%s | hl_ok=%s",
                len(result_str),
                openbb_data.get("available", False),
                hl_data.get("available", False),
            )
            return result_str

    async def _fetch_openbb_historical(
        self,
        symbol: str,
        lookback: int,
        provider: str,
    ) -> Dict[str, Any]:
        """
        Internal async sub-task: fetch historical OHLCV data from OpenBB v4.

        Runs in the event loop's thread pool executor to avoid blocking the
        async loop since the OpenBB SDK is synchronous.

        Parameters
        ----------
        symbol : str
            Instrument symbol in OpenBB format.
        lookback : int
            Number of bars to return (newest first after reversal).
        provider : str
            OpenBB provider chain name.

        Returns
        -------
        dict
            OpenBB response payload conforming to the ``openbb`` schema defined
            in ``_tool_fetch_market_context``.
        """
        if not _OPENBB_AVAILABLE:
            logger.warning(
                "[fetch_openbb_historical] OpenBB not installed — returning empty."
            )
            return {
                "available": False,
                "provider":  provider,
                "lookback_bars": lookback,
                "bars":          [],
                "latest_close":  None,
                "price_change_pct": None,
                "error": "openbb package not installed. Run: pip install openbb>=4.3.0",
            }

        def _sync_openbb_call() -> Dict[str, Any]:
            """Synchronous OpenBB call — runs in thread pool executor."""
            try:
                # OpenBB Platform v4 historical price fetch
                # The symbol for forex should be in "EURUSD" format;
                # for equities "AAPL", for crypto "BTC-USD".
                hist = _OBB.equity.price.historical(
                    symbol=symbol,
                    provider=provider,
                )

                if hist is None or not hasattr(hist, "results") or not hist.results:
                    return {
                        "available": False,
                        "provider":  provider,
                        "lookback_bars": 0,
                        "bars":  [],
                        "latest_close":  None,
                        "price_change_pct": None,
                        "error": f"No results returned by OpenBB for symbol '{symbol}'.",
                    }

                # Convert to plain dicts and slice to lookback
                raw_bars = hist.to_df().tail(lookback)
                bars: List[Dict[str, Any]] = []
                for idx, row in raw_bars.iterrows():
                    bars.append({
                        "date":   str(idx),
                        "open":   round(float(row.get("open",  row.get("Open",  0))), 6),
                        "high":   round(float(row.get("high",  row.get("High",  0))), 6),
                        "low":    round(float(row.get("low",   row.get("Low",   0))), 6),
                        "close":  round(float(row.get("close", row.get("Close", 0))), 6),
                        "volume": round(float(row.get("volume",row.get("Volume",0))), 2),
                    })

                latest_close  = bars[-1]["close"] if bars else None
                oldest_close  = bars[0]["close"]  if bars else None
                price_chg_pct = None
                if latest_close and oldest_close and oldest_close != 0:
                    price_chg_pct = round(
                        (latest_close - oldest_close) / oldest_close * 100, 4
                    )

                return {
                    "available":        True,
                    "provider":         provider,
                    "lookback_bars":    len(bars),
                    "bars":             bars,
                    "latest_close":     latest_close,
                    "price_change_pct": price_chg_pct,
                    "error":            None,
                }

            except Exception as exc:
                logger.error(
                    "[fetch_openbb_historical] OpenBB call failed: %s",
                    exc,
                    exc_info=True,
                )
                raise OpenBBProviderError(
                    symbol=symbol,
                    provider_attempted=provider,
                    original_error=exc,
                ) from exc

        # Run synchronous OpenBB call in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_openbb_call)

    async def _fetch_hyperliquid_context(
        self,
        coin: str,
        include_funding: bool,
    ) -> Dict[str, Any]:
        """
        Internal async sub-task: fetch live orderbook + funding from Hyperliquid.

        Makes two concurrent POST requests to the Hyperliquid info endpoint:
            1. L2 orderbook snapshot (best bid, best ask, spread in bps).
            2. Metadata + asset contexts (funding rate, open interest).

        Parameters
        ----------
        coin : str
            Coin ticker in Hyperliquid format (e.g., "BTC", "ETH", "SOL").
            For forex/equity symbols, this path will return empty data with
            ``available=False`` and a descriptive error.
        include_funding : bool
            Whether to include the second funding/OI API call.

        Returns
        -------
        dict
            Hyperliquid payload conforming to the ``hyperliquid`` schema
            in ``_tool_fetch_market_context``.
        """
        client = await self._ensure_http_client()

        result: Dict[str, Any] = {
            "best_bid":      None,
            "best_ask":      None,
            "spread_bps":    None,
            "funding_rate":  None,
            "open_interest": None,
            "mid_price":     None,
            "available":     False,
            "error":         None,
        }

        try:
            # ── Request 1: L2 OrderBook ──────────────────────────────────
            ob_payload = {"type": "l2Book", "coin": coin}
            ob_response = await client.post(
                _HYPERLIQUID_BASE_URL,
                json=ob_payload,
            )
            ob_response.raise_for_status()
            ob_data: Dict[str, Any] = ob_response.json()

            # Parse orderbook structure: {"levels": [[bids], [asks]]}
            levels = ob_data.get("levels", [[], []])
            bids_raw: List = levels[0] if len(levels) > 0 else []
            asks_raw: List = levels[1] if len(levels) > 1 else []

            best_bid: Optional[float] = None
            best_ask: Optional[float] = None

            if bids_raw:
                # Each level: {"px": "price", "sz": "size", "n": count}
                top_bid = bids_raw[0]
                best_bid = float(top_bid.get("px", top_bid[0] if isinstance(top_bid, list) else 0))

            if asks_raw:
                top_ask = asks_raw[0]
                best_ask = float(top_ask.get("px", top_ask[0] if isinstance(top_ask, list) else 0))

            spread_bps: Optional[float] = None
            mid_price:  Optional[float] = None
            if best_bid and best_ask and best_bid > 0:
                mid_price  = round((best_bid + best_ask) / 2.0, 8)
                spread_bps = round((best_ask - best_bid) / mid_price * 10_000, 4)

            result.update({
                "best_bid":   best_bid,
                "best_ask":   best_ask,
                "mid_price":  mid_price,
                "spread_bps": spread_bps,
                "available":  True,
            })

        except httpx.TimeoutException:
            raise HyperliquidTimeoutError(
                endpoint=_HYPERLIQUID_BASE_URL,
                timeout_seconds=_HYPERLIQUID_TIMEOUT,
            )
        except httpx.HTTPStatusError as exc:
            result["error"] = f"Hyperliquid HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.warning("[fetch_hyperliquid_context] HTTP error: %s", exc)
            return result
        except Exception as exc:
            result["error"] = f"Orderbook fetch failed: {exc}"
            logger.warning("[fetch_hyperliquid_context] Orderbook error: %s", exc)
            return result

        # ── Request 2: Funding Rate + Open Interest ───────────────────────
        if include_funding:
            try:
                meta_payload = {"type": "metaAndAssetCtxs"}
                meta_response = await client.post(
                    _HYPERLIQUID_BASE_URL,
                    json=meta_payload,
                )
                meta_response.raise_for_status()
                meta_data = meta_response.json()

                # Structure: [universe_list, asset_ctx_list]
                # universe_list: [{"name": "BTC", ...}, ...]
                # asset_ctx_list: [{"funding": "0.0001", "openInterest": "123456", ...}, ...]
                if isinstance(meta_data, list) and len(meta_data) >= 2:
                    universe:    List[Dict] = meta_data[0].get("universe", [])
                    asset_ctxs:  List[Dict] = meta_data[1]

                    # Find index of our coin in the universe
                    coin_idx: Optional[int] = None
                    for i, asset in enumerate(universe):
                        if asset.get("name", "").upper() == coin.upper():
                            coin_idx = i
                            break

                    if coin_idx is not None and coin_idx < len(asset_ctxs):
                        ctx = asset_ctxs[coin_idx]
                        funding_str = ctx.get("funding", None)
                        oi_str      = ctx.get("openInterest", None)

                        result["funding_rate"]  = float(funding_str) if funding_str else None
                        result["open_interest"] = float(oi_str)      if oi_str      else None

            except httpx.TimeoutException:
                # Funding fetch timeout is non-fatal — orderbook data is still valid
                logger.warning(
                    "[fetch_hyperliquid_context] Funding rate fetch timed out (non-fatal)."
                )
                result["error"] = "Funding rate fetch timed out (orderbook data available)."
            except Exception as exc:
                logger.warning(
                    "[fetch_hyperliquid_context] Funding fetch error: %s", exc
                )

        return result

    # -------------------------------------------------------------------
    # Tool B: fetch_mt5_portfolio_state
    # -------------------------------------------------------------------

    async def _tool_fetch_mt5_portfolio_state(
        self, raw_args: Dict[str, Any]
    ) -> str:
        """
        Tool B — Live MT5 Portfolio State Snapshot.

        Execution Pipeline
        ------------------
        1. Validate arguments via ``FetchMT5PortfolioStateArgs``.
        2. Call ``mt5.account_info()`` for equity, balance, margin metrics.
        3. Call ``mt5.positions_get()`` for open positions (if requested).
        4. Compute dynamic drawdown percentage.
        5. Serialize all state to a sanitized JSON string.

        Parameters
        ----------
        raw_args : dict
            Raw argument dictionary from the JSON-RPC call.

        Returns
        -------
        str
            JSON string with schema::

                {
                  "timestamp_utc":    str,
                  "data_source":      str,
                  "account": {
                    "login":          int,
                    "server":         str,
                    "currency":       str,
                    "leverage":       int,
                    "balance":        float,
                    "equity":         float,
                    "free_margin":    float,
                    "margin_used":    float,
                    "margin_level":   float,
                    "drawdown_pct":   float,
                    "profit_floating":float
                  },
                  "grid_pro": {
                    "max_drawdown_pct":    float,
                    "current_dd_pct":      float,
                    "dd_headroom_pct":     float,
                    "emergency_stop_triggered": bool
                  },
                  "positions": [
                    {
                      "ticket":       int,
                      "symbol":       str,
                      "type":         str,
                      "volume":       float,
                      "open_price":   float,
                      "current_price":float,
                      "sl":           float,
                      "tp":           float,
                      "profit":       float,
                      "swap":         float,
                      "magic":        int,
                      "comment":      str
                    }, ...
                  ],
                  "server_version":   str
                }
        """
        async with mcp_error_interceptor("fetch_mt5_portfolio_state"):
            # Step 1: Validate arguments
            try:
                args = FetchMT5PortfolioStateArgs(**raw_args)
            except Exception as exc:
                raise InvalidParamsError(
                    "Argument validation failed for fetch_mt5_portfolio_state.",
                    validation_errors=exc,
                ) from exc

            import datetime

            # Step 2: Check MT5 availability — ensure initialized
            if not _MT5_AVAILABLE:
                # Return simulated fallback data when MT5 is not installed
                logger.warning(
                    "[fetch_mt5_portfolio_state] MT5 unavailable — returning fallback."
                )
                account_data = self._build_fallback_account()
                return json.dumps({
                    "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
                    "data_source":   "fallback_no_mt5",
                    "account":       account_data,
                    "grid_pro":      self._compute_grid_pro_metrics(account_data),
                    "positions":     [],
                    "server_version": _SERVER_VERSION,
                })

            # Ensure MT5 is initialized
            if not self._mt5_initialized:
                initialized = self._initialize_mt5()
                if not initialized:
                    raise MT5DisconnectedError(
                        "MT5 terminal could not be initialized for portfolio state fetch.",
                        last_error=_mt5.last_error() if _mt5 else None,
                    )

            # Step 3: Fetch live account info
            def _sync_mt5_portfolio() -> Dict[str, Any]:
                """Synchronous MT5 read — runs in thread pool executor."""
                acct = _mt5.account_info()
                if acct is None:
                    raise MT5DisconnectedError(
                        "mt5.account_info() returned None.",
                        last_error=_mt5.last_error(),
                    )

                balance: float = float(acct.balance)
                equity:  float = float(acct.equity)
                margin:  float = float(acct.margin)
                free_mg: float = float(acct.margin_free)

                drawdown_pct: float = 0.0
                if balance > 0:
                    drawdown_pct = max(0.0, (balance - equity) / balance * 100.0)

                account_data: Dict[str, Any] = {
                    "login":           int(acct.login),
                    "server":          str(acct.server),
                    "currency":        str(acct.currency),
                    "leverage":        int(acct.leverage),
                    "balance":         round(balance, 2),
                    "equity":          round(equity, 2),
                    "free_margin":     round(free_mg, 2),
                    "margin_used":     round(margin, 2),
                    "margin_level":    round(float(acct.margin_level), 4),
                    "drawdown_pct":    round(drawdown_pct, 4),
                    "profit_floating": round(equity - balance, 2),
                }

                # Step 4: Fetch open positions
                positions_data: List[Dict[str, Any]] = []
                if args.include_positions:
                    raw_positions = _mt5.positions_get()
                    if raw_positions:
                        for pos in list(raw_positions)[:args.max_position_count]:
                            pos_type = "BUY" if pos.type == _mt5.ORDER_TYPE_BUY else "SELL"
                            positions_data.append({
                                "ticket":        int(pos.ticket),
                                "symbol":        str(pos.symbol),
                                "type":          pos_type,
                                "volume":        round(float(pos.volume), 2),
                                "open_price":    round(float(pos.price_open), 6),
                                "current_price": round(float(pos.price_current), 6),
                                "sl":            round(float(pos.sl), 6),
                                "tp":            round(float(pos.tp), 6),
                                "profit":        round(float(pos.profit), 2),
                                "swap":          round(float(pos.swap), 2),
                                "magic":         int(pos.magic),
                                "comment":       str(pos.comment),
                            })

                return {"account": account_data, "positions": positions_data}

            # Run synchronous MT5 calls in executor
            loop = asyncio.get_event_loop()
            try:
                portfolio = await loop.run_in_executor(None, _sync_mt5_portfolio)
            except MT5DisconnectedError:
                raise
            except Exception as exc:
                raise InternalError(
                    f"MT5 portfolio fetch failed unexpectedly: {exc}",
                    original_exception=exc,
                ) from exc

            # Step 5: Build final response
            account_data = portfolio["account"]
            response: Dict[str, Any] = {
                "timestamp_utc":  datetime.datetime.utcnow().isoformat() + "Z",
                "data_source":    "mt5_live",
                "account":        account_data,
                "grid_pro":       self._compute_grid_pro_metrics(account_data),
                "positions":      portfolio["positions"],
                "server_version": _SERVER_VERSION,
            }

            result_str = json.dumps(response, default=str)
            logger.info(
                "[fetch_mt5_portfolio_state] account=%.2f | equity=%.2f | "
                "dd=%.2f%% | positions=%d",
                account_data["balance"],
                account_data["equity"],
                account_data["drawdown_pct"],
                len(portfolio["positions"]),
            )
            return result_str

    def _compute_grid_pro_metrics(
        self, account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute Grid Pro subsystem risk metrics from account data.

        Parameters
        ----------
        account_data : dict
            Account snapshot from MT5 or fallback.

        Returns
        -------
        dict
            Grid Pro metrics with drawdown headroom and emergency stop flag.
        """
        max_dd_pct: float    = 5.0  # Configured threshold matching STRATEGY["max_dd_percent"]
        current_dd: float    = account_data.get("drawdown_pct", 0.0)
        headroom:   float    = max(0.0, max_dd_pct - current_dd)
        emergency:  bool     = current_dd >= max_dd_pct

        return {
            "max_drawdown_pct":         max_dd_pct,
            "current_dd_pct":           round(current_dd, 4),
            "dd_headroom_pct":          round(headroom, 4),
            "emergency_stop_triggered": emergency,
        }

    def _build_fallback_account(self) -> Dict[str, Any]:
        """Return a zero-risk fallback account dict when MT5 is unavailable."""
        return {
            "login":           0,
            "server":          "OFFLINE",
            "currency":        "USD",
            "leverage":        500,
            "balance":         0.0,
            "equity":          0.0,
            "free_margin":     0.0,
            "margin_used":     0.0,
            "margin_level":    0.0,
            "drawdown_pct":    0.0,
            "profit_floating": 0.0,
        }

    # -------------------------------------------------------------------
    # Tool C: route_execution_order
    # -------------------------------------------------------------------

    async def _tool_route_execution_order(
        self, raw_args: Dict[str, Any]
    ) -> str:
        """
        Tool C — Atomic MT5 Market Order Execution Router.

        Execution Pipeline
        ------------------
        1. Validate arguments via ``RouteExecutionOrderArgs`` (Pydantic v2).
        2. Verify MT5 is connected and initialized.
        3. Fetch live tick data for the symbol (``mt5.symbol_info_tick()``).
        4. Compute entry price, SL price, TP price from tick + pip offsets.
        5. Compute contract tick value for margin validation.
        6. Determine optimal filling mode from symbol info.
        7. Build the complete ``TRADE_ACTION_DEAL`` request structure.
        8. Submit via ``mt5.order_send()``.
        9. Parse retcode — map non-DONE codes to ``OrderRejectedError``.
        10. Return serialized execution receipt or error string.

        Parameters
        ----------
        raw_args : dict
            Raw argument dictionary from the JSON-RPC call.

        Returns
        -------
        str
            JSON string with schema::

                {
                  "status":         "EXECUTED" | "REJECTED" | "ERROR",
                  "ticket":         int | null,
                  "symbol":         str,
                  "action":         str,
                  "lot_size":       float,
                  "entry_price":    float | null,
                  "sl_price":       float | null,
                  "tp_price":       float | null,
                  "sl_pips":        float,
                  "tp_pips":        float,
                  "request_id":     str,
                  "timestamp_utc":  str,
                  "broker_comment": str | null,
                  "retcode":        int | null,
                  "margin_required":float | null,
                  "server_version": str
                }
        """
        async with mcp_error_interceptor("route_execution_order"):
            # Step 1: Validate arguments
            try:
                args = RouteExecutionOrderArgs(**raw_args)
            except Exception as exc:
                raise InvalidParamsError(
                    "Argument validation failed for route_execution_order.",
                    validation_errors=exc,
                ) from exc

            import datetime, hashlib
            request_id: str = hashlib.sha256(
                f"{args.symbol}{args.action}{args.lot_size}{time.time()}".encode()
            ).hexdigest()[:12].upper()

            logger.info(
                "[route_execution_order] req=%s | %s %s | lot=%.2f | "
                "sl=%.1fp | tp=%.1fp",
                request_id,
                args.action,
                args.symbol,
                args.lot_size,
                args.sl_pips,
                args.tp_pips,
            )

            base_receipt: Dict[str, Any] = {
                "status":         "ERROR",
                "ticket":         None,
                "symbol":         args.symbol,
                "action":         args.action,
                "lot_size":       args.lot_size,
                "entry_price":    None,
                "sl_price":       None,
                "tp_price":       None,
                "sl_pips":        args.sl_pips,
                "tp_pips":        args.tp_pips,
                "request_id":     request_id,
                "timestamp_utc":  datetime.datetime.utcnow().isoformat() + "Z",
                "broker_comment": None,
                "retcode":        None,
                "margin_required": None,
                "server_version": _SERVER_VERSION,
            }

            # Step 2: Verify MT5 availability
            if not _MT5_AVAILABLE:
                base_receipt["broker_comment"] = (
                    "MT5 library not installed. Install with: pip install MetaTrader5"
                )
                return json.dumps(base_receipt)

            if not self._mt5_initialized:
                initialized = self._initialize_mt5()
                if not initialized:
                    raise MT5DisconnectedError(
                        "MT5 terminal unavailable for order execution.",
                        last_error=_mt5.last_error() if _mt5 else None,
                    )

            def _sync_execute_order() -> Dict[str, Any]:
                """
                Synchronous MT5 order execution — runs in thread pool executor.

                Contains all blocking MT5 SDK calls that must not be awaited
                directly in the event loop.
                """
                # Step 3: Symbol info + validation
                sym_info = _mt5.symbol_info(args.symbol)
                if sym_info is None:
                    raise SymbolNotFoundError(args.symbol)

                # Ensure symbol is visible in Market Watch
                if not sym_info.visible:
                    _mt5.symbol_select(args.symbol, True)
                    sym_info = _mt5.symbol_info(args.symbol)

                # Step 4: Live tick data
                tick = _mt5.symbol_info_tick(args.symbol)
                if tick is None:
                    raise MT5DisconnectedError(
                        f"No tick data for symbol '{args.symbol}'.",
                        last_error=_mt5.last_error(),
                    )

                digits:   int   = sym_info.digits
                # pip size: 0.0001 for 5-digit pairs, 0.01 for 3-digit JPY pairs
                pip_size: float = (
                    0.01 if digits <= 3 else (0.001 if digits == 4 else 0.0001)
                )

                # Step 4: Compute prices
                if args.action == "BUY":
                    entry_price: float = tick.ask
                    sl_price:    float = round(entry_price - args.sl_pips * pip_size, digits)
                    tp_price:    float = round(entry_price + args.tp_pips * pip_size, digits)
                    order_type         = _mt5.ORDER_TYPE_BUY
                else:  # SELL
                    entry_price = tick.bid
                    sl_price    = round(entry_price + args.sl_pips * pip_size, digits)
                    tp_price    = round(entry_price - args.tp_pips * pip_size, digits)
                    order_type  = _mt5.ORDER_TYPE_SELL

                # Step 5: Compute margin required
                # margin = (lot_size × contract_size) / leverage × price
                # We use the MT5 tick value approach for precision
                contract_size:    float = float(sym_info.trade_contract_size)  # e.g., 100,000
                tick_size:        float = float(sym_info.trade_tick_size)       # e.g., 0.00001
                tick_value:       float = float(sym_info.trade_tick_value)      # e.g., 1.0 USD
                leverage:         int   = int(_mt5.account_info().leverage) if _mt5.account_info() else 500

                # Required margin = (lot_size * contract_size * entry_price) / leverage
                margin_required: float = (args.lot_size * contract_size * entry_price) / max(leverage, 1)

                # Margin check against free margin
                acct_info = _mt5.account_info()
                if acct_info is not None:
                    free_margin = float(acct_info.margin_free)
                    if free_margin < margin_required:
                        raise InsufficientMarginError(
                            free_margin=free_margin,
                            required_margin=margin_required,
                        )

                # Step 6: Determine optimal filling mode
                filling_mode_bits: int = sym_info.filling_mode
                if filling_mode_bits & 1:
                    filling = _mt5.ORDER_FILLING_FOK
                elif filling_mode_bits & 2:
                    filling = _mt5.ORDER_FILLING_IOC
                else:
                    filling = _mt5.ORDER_FILLING_RETURN

                # Step 7: Build order request structure
                magic = args.magic_override if args.magic_override is not None else _MT5_MAGIC_NUMBER
                request: Dict[str, Any] = {
                    "action":       _mt5.TRADE_ACTION_DEAL,
                    "symbol":       args.symbol,
                    "volume":       round(args.lot_size, 2),
                    "type":         order_type,
                    "price":        entry_price,
                    "sl":           sl_price,
                    "tp":           tp_price,
                    "deviation":    _MT5_DEVIATION,
                    "magic":        magic,
                    "comment":      args.comment[:31],  # MT5 enforces 31-char limit
                    "type_time":    _mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }

                logger.debug(
                    "[route_execution_order] MT5 request=%s",
                    request,
                )

                # Step 8: Submit order
                result = _mt5.order_send(request)

                if result is None:
                    last_err = _mt5.last_error()
                    raise MT5DisconnectedError(
                        f"order_send() returned None for '{args.symbol}'.",
                        last_error=last_err,
                    )

                # Step 9: Parse retcode
                if result.retcode != _mt5.TRADE_RETCODE_DONE:
                    raise OrderRejectedError(
                        symbol=args.symbol,
                        retcode=result.retcode,
                        comment=result.comment,
                    )

                # Step 10: Build success receipt
                return {
                    "status":          "EXECUTED",
                    "ticket":          int(result.order),
                    "entry_price":     round(float(result.price), digits),
                    "sl_price":        sl_price,
                    "tp_price":        tp_price,
                    "broker_comment":  result.comment,
                    "retcode":         result.retcode,
                    "margin_required": round(margin_required, 2),
                }

            # Run in executor
            loop = asyncio.get_event_loop()
            try:
                execution_data = await loop.run_in_executor(None, _sync_execute_order)
                base_receipt.update(execution_data)
                logger.info(
                    "[route_execution_order] EXECUTED | req=%s | ticket=%s | "
                    "price=%.5f | sl=%.5f | tp=%.5f",
                    request_id,
                    base_receipt.get("ticket"),
                    base_receipt.get("entry_price", 0),
                    base_receipt.get("sl_price", 0),
                    base_receipt.get("tp_price", 0),
                )
            except (OrderRejectedError, InsufficientMarginError,
                    SymbolNotFoundError, MT5DisconnectedError) as exc:
                base_receipt["status"]         = "REJECTED"
                base_receipt["broker_comment"] = exc.message
                base_receipt["retcode"]        = exc.data.get("retcode")
                logger.warning(
                    "[route_execution_order] REJECTED | req=%s | reason=%s",
                    request_id,
                    exc.message,
                )
            except Exception as exc:
                raise InternalError(
                    f"Unexpected order execution failure: {exc}",
                    original_exception=exc,
                ) from exc

            return json.dumps(base_receipt, default=str)


# ===========================================================================
# Server Entry Point
# ===========================================================================

async def _main() -> None:
    """
    Async entry point for the QuantumMCPServer process.

    Configure logging to write to stderr (so stdout remains clean for the
    MCP stdio transport) and start the server.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )
    logger.info("QuantumMCPServer starting up | version=%s", _SERVER_VERSION)
    server = QuantumMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(_main())
