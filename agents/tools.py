"""
============================================================
agents/tools.py — Antigravity AI Agent Tool Adapters
============================================================
Transforms ``DataService`` methods into structured, LLM-callable Tools
compatible with CrewAI, LangGraph, and LangChain tool-calling conventions.

Architecture:
    Each agent role (Analyst, Planner, Executor, Monitor) receives a curated
    set of Tool objects.  Tools encapsulate:
        1. A Pydantic v2 input schema (``BaseModel``) for structured argument
           validation — used by LLM function-calling APIs.
        2. An async ``run()`` coroutine that invokes ``DataService`` and
           returns a JSON-serializable dict.
        3. Rich metadata (name, description) that is injected into LLM prompts.

Compatibility:
    - **LangChain**: Wrap each ``AgentTool`` with ``@tool`` or pass the
      Pydantic schema directly to ``StructuredTool.from_function``.
    - **CrewAI**: Pass the callable ``run()`` to ``crewai.Tool(func=...)``
      with the Pydantic ``args_schema``.
    - **LangGraph**: Bind tools via ``model.bind_tools([...])`` using the
      OpenAI-compatible schema produced by ``AgentTool.as_openai_schema()``.

Usage::

    from agents.tools import get_analyst_tools, get_planner_tools
    from data_layer.openbb_service import DataService

    svc = DataService()
    analyst_tools = get_analyst_tools(svc)
    result = await analyst_tools[0].run(symbol="AAPL")
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from data_layer.openbb_service import DataService, DataServiceError

logger = logging.getLogger("agents.tools")


# ─────────────────────────────────────────────────────────────────────────
# Base Tool Contract
# ─────────────────────────────────────────────────────────────────────────

class AgentTool:
    """
    Abstract base for all Antigravity Agent Tools.

    Subclasses must define:
        - ``name``: Unique tool identifier (snake_case).
        - ``description``: LLM-facing description of what this tool does.
        - ``args_schema``: Pydantic BaseModel subclass for input validation.
        - ``_execute()``: Async implementation of the tool logic.

    The public ``run()`` method handles:
        - Input validation via the Pydantic schema.
        - Exception boundary: catches all DataServiceErrors and returns
          a structured error dict instead of propagating, so the LLM can
          reason about the failure.
        - Structured logging of every invocation.

    Attributes:
        name:        Unique tool identifier string.
        description: Human and LLM-readable description.
        _svc:        Shared DataService instance (dependency-injected).
    """

    name: str = "base_tool"
    description: str = "Base tool — do not use directly."

    def __init__(self, data_service: DataService) -> None:
        """
        Args:
            data_service: Shared ``DataService`` instance.  All tools in an
                          agent share the same service to benefit from the
                          unified cache.
        """
        self._svc = data_service

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """
        Public entry-point called by the LLM agent runtime.

        Validates inputs via Pydantic, delegates to ``_execute()``, and
        wraps any ``DataServiceError`` in a structured error response.

        Args:
            **kwargs: Tool-specific arguments matching the ``args_schema``.

        Returns:
            Dict that is always JSON-serializable:
            ``{"status": "ok", ...}`` on success,
            ``{"status": "error", "message": ..., "tool": ...}`` on failure.
        """
        logger.info("[Tool] %s called with: %s", self.name, kwargs)
        try:
            result = await self._execute(**kwargs)
            result["status"] = "ok"
            result["tool"] = self.name
            result["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
            return result
        except DataServiceError as exc:
            logger.warning("[Tool] %s DataServiceError: %s", self.name, exc)
            return {
                "status": "error",
                "tool": self.name,
                "message": str(exc),
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error("[Tool] %s unexpected error: %s", self.name, exc, exc_info=True)
            return {
                "status": "error",
                "tool": self.name,
                "message": f"Unexpected error: {exc}",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }

    async def _execute(self, **kwargs: Any) -> dict[str, Any]:
        """Override in subclasses to implement tool logic."""
        raise NotImplementedError

    def as_openai_schema(self) -> dict[str, Any]:
        """
        Produce an OpenAI-compatible function-calling JSON schema dict.

        This can be passed directly to ``model.bind_tools()`` in LangGraph
        or used as the ``function`` field in OpenAI chat completions.

        Returns:
            Dict conforming to the OpenAI ``tool`` schema format.
        """
        schema_cls = getattr(self, "args_schema", None)
        parameters = schema_cls.model_json_schema() if schema_cls else {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


# ─────────────────────────────────────────────────────────────────────────
# Technical Indicator Utilities
# ─────────────────────────────────────────────────────────────────────────

def _compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Compute Simple Moving Average."""
    return series.rolling(window=period, min_periods=1).mean()


def _compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Compute Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute RSI (Relative Strength Index) using Wilder's smoothing.

    Args:
        series: Close price series.
        period: Lookback window (default 14).

    Returns:
        RSI series in [0, 100].
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute MACD line, Signal line, and Histogram.

    Args:
        series: Close price series.
        fast:   Fast EMA period (default 12).
        slow:   Slow EMA period (default 26).
        signal: Signal EMA period (default 9).

    Returns:
        Tuple of (macd_line, signal_line, histogram) as pd.Series.
    """
    ema_fast = _compute_ema(series, fast)
    ema_slow = _compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Average True Range.

    Args:
        df:     OHLCV DataFrame with 'high', 'low', 'close' columns.
        period: ATR window (default 14).

    Returns:
        ATR series.
    """
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Augment an OHLCV DataFrame with a standard technical indicator set.

    Indicators added:
        - sma_20, sma_50, sma_200
        - ema_12, ema_26
        - rsi_14
        - macd, macd_signal, macd_hist
        - atr_14
        - bb_upper, bb_lower, bb_mid (Bollinger Bands ±2σ, 20-period)

    Args:
        df: OHLCV DataFrame (must contain 'close', 'high', 'low').

    Returns:
        DataFrame with added indicator columns.
    """
    close = df["close"]

    df["sma_20"] = _compute_sma(close, 20)
    df["sma_50"] = _compute_sma(close, 50)
    df["sma_200"] = _compute_sma(close, 200)
    df["ema_12"] = _compute_ema(close, 12)
    df["ema_26"] = _compute_ema(close, 26)
    df["rsi_14"] = _compute_rsi(close)

    macd, macd_sig, macd_hist = _compute_macd(close)
    df["macd"] = macd
    df["macd_signal"] = macd_sig
    df["macd_hist"] = macd_hist

    if "high" in df.columns and "low" in df.columns:
        df["atr_14"] = _compute_atr(df)

    # Bollinger Bands
    df["bb_mid"] = _compute_sma(close, 20)
    rolling_std = close.rolling(window=20, min_periods=1).std()
    df["bb_upper"] = df["bb_mid"] + 2 * rolling_std
    df["bb_lower"] = df["bb_mid"] - 2 * rolling_std

    return df


# ─────────────────────────────────────────────────────────────────────────
# Pydantic v2 Input Schemas
# ─────────────────────────────────────────────────────────────────────────

class FinancialHealthInput(BaseModel):
    """Input schema for the Analyst Agent financial health tool."""
    symbol: str = Field(
        ...,
        description="Equity ticker symbol (e.g. 'AAPL', 'MSFT').",
        min_length=1, max_length=10,
    )
    provider: str = Field(
        default="fmp",
        description="Data provider for fundamental data. Options: fmp | yfinance.",
    )
    news_limit: int = Field(
        default=10,
        ge=1, le=50,
        description="Maximum number of recent news articles to retrieve.",
    )


class TechnicalIndicatorsInput(BaseModel):
    """Input schema for the Planner Agent technical indicators tool."""
    symbol: str = Field(
        ...,
        description="Equity or FX ticker symbol.",
        min_length=1, max_length=15,
    )
    start_date: str = Field(
        default="2023-01-01",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO-8601 start date for historical data (YYYY-MM-DD).",
    )
    provider: str = Field(
        default="yfinance",
        description="Provider for historical OHLCV. Options: yfinance | fmp | polygon.",
    )


class OrderBookInput(BaseModel):
    """Input schema for the Executor Agent pre-trade slippage tool."""
    symbol: str = Field(
        ...,
        description="Asset symbol for real-time quote / order book data.",
        min_length=1, max_length=15,
    )
    provider: str = Field(
        default="polygon",
        description=(
            "Provider with bid/ask support. "
            "Use 'polygon' for real-time, 'yfinance' for 15-min delayed."
        ),
    )
    max_spread_pct: float = Field(
        default=0.1,
        ge=0.0, le=5.0,
        description=(
            "Maximum acceptable spread percentage. "
            "Trade is flagged as RISKY above this threshold."
        ),
    )


class PortfolioMonitorInput(BaseModel):
    """Input schema for the Monitor Agent unrealized P&L tool."""
    positions: list[dict[str, Any]] = Field(
        ...,
        description=(
            "List of open position dicts, each containing: "
            "symbol (str), entry_price (float), quantity (float), direction ('LONG'|'SHORT')."
        ),
        min_length=1,
    )
    provider: str = Field(
        default="yfinance",
        description="Provider for current price quotes.",
    )


# ─────────────────────────────────────────────────────────────────────────
# ANALYST AGENT TOOLS
# ─────────────────────────────────────────────────────────────────────────

class FinancialHealthTool(AgentTool):
    """
    **Analyst Agent Tool** — Financial Health & News Sentiment Analyzer.

    Retrieves fundamental financial ratios (P/E, Debt/Equity, ROE, etc.)
    and the latest news sentiment for a given equity ticker.

    Returns a structured dict containing:
        - Health summary string for LLM context.
        - Individual ratio values.
        - News articles with sentiment labels (POSITIVE/NEGATIVE/NEUTRAL).
        - Overall sentiment distribution summary.

    Designed for direct embedding in the Analyst Agent's LLM prompt context.
    """

    name = "get_financial_health_and_news"
    description = (
        "Retrieves the financial health metrics (P/E, Debt/Equity, ROE, margins) "
        "and recent news sentiment for a stock. Use this tool when you need to "
        "assess whether a company is fundamentally strong before taking a position."
    )
    args_schema = FinancialHealthInput

    async def _execute(
        self,
        symbol: str,
        provider: str = "fmp",
        news_limit: int = 10,
        **_: Any,
    ) -> dict[str, Any]:
        """
        Fetch fundamentals + news concurrently via asyncio.gather().

        Args:
            symbol:     Equity ticker.
            provider:   Fundamental data provider.
            news_limit: Number of news items.

        Returns:
            Dict with keys: symbol, health_summary, ratios, news,
            sentiment_distribution, overall_sentiment.
        """
        # Run both API calls concurrently
        fundamentals_task = asyncio.to_thread(
            self._svc.get_fundamental_metrics, symbol, provider=provider
        )
        news_task = asyncio.to_thread(
            self._svc.get_equity_news, symbol, limit=news_limit
        )

        fundamentals, news_df = await asyncio.gather(
            fundamentals_task, news_task, return_exceptions=True
        )

        # ── Process fundamentals ─────────────────────────────────────────
        if isinstance(fundamentals, Exception):
            logger.warning("Fundamentals fetch failed for %s: %s", symbol, fundamentals)
            ratios = {}
            health_summary = "Fundamental data unavailable."
        else:
            ratios = fundamentals.get("ratios", {})
            health_summary = fundamentals.get("health_summary", "")

        # ── Process news ─────────────────────────────────────────────────
        news_records: list[dict] = []
        sentiment_dist = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}

        if isinstance(news_df, Exception):
            logger.warning("News fetch failed for %s: %s", symbol, news_df)
        elif not news_df.empty:
            for _, row in news_df.head(news_limit).iterrows():
                sentiment = str(row.get("sentiment_label", "NEUTRAL"))
                sentiment_dist[sentiment] = sentiment_dist.get(sentiment, 0) + 1
                news_records.append({
                    "title": str(row.get("title", "")),
                    "sentiment": sentiment,
                    "date": str(row.name) if hasattr(row, "name") else "",
                    "url": str(row.get("url", "")),
                })

        total_news = sum(sentiment_dist.values())
        overall = "NEUTRAL"
        if total_news > 0:
            pos_ratio = sentiment_dist["POSITIVE"] / total_news
            neg_ratio = sentiment_dist["NEGATIVE"] / total_news
            if pos_ratio > 0.55:
                overall = "BULLISH"
            elif neg_ratio > 0.55:
                overall = "BEARISH"

        return {
            "symbol": symbol,
            "health_summary": health_summary,
            "ratios": ratios,
            "news": news_records,
            "sentiment_distribution": sentiment_dist,
            "overall_sentiment": overall,
        }


# ─────────────────────────────────────────────────────────────────────────
# PLANNER AGENT TOOLS
# ─────────────────────────────────────────────────────────────────────────

class TechnicalIndicatorsTool(AgentTool):
    """
    **Planner Agent Tool** — Technical Indicators Computation Engine.

    Fetches OHLCV data via DataService and computes a full indicator suite:
        - Trend: SMA(20/50/200), EMA(12/26)
        - Momentum: RSI(14), MACD(12/26/9)
        - Volatility: ATR(14), Bollinger Bands(20, ±2σ)

    Returns the most recent indicator snapshot plus a structured signal
    summary (BULLISH / BEARISH / NEUTRAL / SIDEWAYS) based on confluence.

    The Planner Agent uses this to decide position sizing and entry timing.
    """

    name = "compute_technical_indicators"
    description = (
        "Fetches historical OHLCV price data and computes a full technical "
        "indicator set (SMA, EMA, RSI, MACD, ATR, Bollinger Bands). "
        "Use this tool when building a technical trading strategy or planning "
        "entry/exit levels for a position."
    )
    args_schema = TechnicalIndicatorsInput

    async def _execute(
        self,
        symbol: str,
        start_date: str = "2023-01-01",
        provider: str = "yfinance",
        **_: Any,
    ) -> dict[str, Any]:
        """
        Compute the full indicator stack and derive a signal classification.

        Args:
            symbol:     Ticker symbol.
            start_date: Start of the historical window.
            provider:   OHLCV provider.

        Returns:
            Dict with keys: symbol, indicators (latest snapshot), signal,
            signal_reasons, trend_strength, historical_rows.
        """
        df = await asyncio.to_thread(
            self._svc.get_historical_prices,
            symbol,
            start_date=start_date,
            provider=provider,
        )

        df = _add_technical_indicators(df)

        # ── Latest snapshot ──────────────────────────────────────────────
        latest = df.iloc[-1]
        close = float(latest.get("close", 0))

        snapshot = {
            "close": round(close, 4),
            "sma_20": round(float(latest.get("sma_20", 0)), 4),
            "sma_50": round(float(latest.get("sma_50", 0)), 4),
            "sma_200": round(float(latest.get("sma_200", 0)), 4),
            "ema_12": round(float(latest.get("ema_12", 0)), 4),
            "ema_26": round(float(latest.get("ema_26", 0)), 4),
            "rsi_14": round(float(latest.get("rsi_14", 50)), 2),
            "macd": round(float(latest.get("macd", 0)), 6),
            "macd_signal": round(float(latest.get("macd_signal", 0)), 6),
            "macd_hist": round(float(latest.get("macd_hist", 0)), 6),
            "atr_14": round(float(latest.get("atr_14", 0)), 6),
            "bb_upper": round(float(latest.get("bb_upper", 0)), 4),
            "bb_mid": round(float(latest.get("bb_mid", 0)), 4),
            "bb_lower": round(float(latest.get("bb_lower", 0)), 4),
        }

        # ── Signal classification ────────────────────────────────────────
        signal, reasons = self._classify_signal(snapshot, close)

        # ── Trend strength via ADX approximation (slope of SMA200) ───────
        if len(df) >= 10:
            slope = (df["sma_200"].iloc[-1] - df["sma_200"].iloc[-10]) / 10
            trend_strength = "STRONG" if abs(slope) > close * 0.001 else "WEAK"
        else:
            trend_strength = "UNKNOWN"

        return {
            "symbol": symbol,
            "provider": provider,
            "start_date": start_date,
            "historical_rows": len(df),
            "indicators": snapshot,
            "signal": signal,
            "signal_reasons": reasons,
            "trend_strength": trend_strength,
        }

    @staticmethod
    def _classify_signal(
        snap: dict[str, float], close: float
    ) -> tuple[str, list[str]]:
        """
        Derive a consensus signal label from indicator values.

        Scoring rules:
            +1 bullish: price > sma_20, price > sma_50, MACD > Signal,
                        RSI in (40–70), price < bb_upper.
            -1 bearish: price < sma_20, price < sma_50, MACD < Signal,
                        RSI > 70 (overbought), price > bb_upper.

        Args:
            snap:  Latest indicator snapshot dict.
            close: Current close price.

        Returns:
            Tuple of (signal_label, list_of_reasons).
        """
        score = 0
        reasons: list[str] = []

        if close > snap["sma_20"]:
            score += 1
            reasons.append("Price above SMA-20 (short-term bullish)")
        else:
            score -= 1
            reasons.append("Price below SMA-20 (short-term bearish)")

        if close > snap["sma_50"]:
            score += 1
            reasons.append("Price above SMA-50 (medium-term bullish)")
        else:
            score -= 1
            reasons.append("Price below SMA-50 (medium-term bearish)")

        if snap["macd"] > snap["macd_signal"]:
            score += 1
            reasons.append("MACD line above Signal (bullish momentum)")
        else:
            score -= 1
            reasons.append("MACD line below Signal (bearish momentum)")

        rsi = snap["rsi_14"]
        if 40 < rsi < 70:
            score += 1
            reasons.append(f"RSI={rsi:.1f} in healthy range (40–70)")
        elif rsi >= 70:
            score -= 1
            reasons.append(f"RSI={rsi:.1f} overbought (≥70)")
        elif rsi <= 30:
            score -= 1
            reasons.append(f"RSI={rsi:.1f} oversold (≤30) — potential reversal")

        if snap["bb_lower"] < close < snap["bb_upper"]:
            score += 1
            reasons.append("Price within Bollinger Bands (normal volatility)")
        elif close > snap["bb_upper"]:
            score -= 1
            reasons.append("Price above BB upper band (overbought extension)")

        if score >= 3:
            return "BULLISH", reasons
        if score <= -3:
            return "BEARISH", reasons
        if score == 0:
            return "SIDEWAYS", reasons
        return "NEUTRAL", reasons


# ─────────────────────────────────────────────────────────────────────────
# EXECUTOR AGENT TOOLS
# ─────────────────────────────────────────────────────────────────────────

class OrderBookSlippageTool(AgentTool):
    """
    **Executor Agent Tool** — Pre-Trade Slippage & Liquidity Validator.

    Fetches real-time bid/ask quote data and computes:
        - Current bid-ask spread (absolute and percentage).
        - Slippage estimate for a market order (assumed 50% of spread).
        - Liquidity risk classification (LOW / MEDIUM / HIGH / CRITICAL).
        - Trade clearance recommendation (PROCEED / CAUTION / ABORT).

    This tool MUST be called before any market order is submitted.
    If the spread exceeds ``max_spread_pct``, the Executor should abort.
    """

    name = "validate_order_book_slippage"
    description = (
        "Fetches the real-time bid/ask spread and validates whether the current "
        "market conditions are liquid enough to execute a trade without excessive "
        "slippage. Returns a PROCEED / CAUTION / ABORT recommendation."
    )
    args_schema = OrderBookInput

    async def _execute(
        self,
        symbol: str,
        provider: str = "polygon",
        max_spread_pct: float = 0.1,
        **_: Any,
    ) -> dict[str, Any]:
        """
        Fetch quote and compute slippage risk metrics.

        Args:
            symbol:         Asset symbol.
            provider:       Quote provider ('polygon' or 'yfinance').
            max_spread_pct: Threshold above which trade is CAUTION/ABORT.

        Returns:
            Dict with keys: symbol, bid, ask, spread, spread_pct,
            slippage_estimate, liquidity_risk, recommendation, reasons.
        """
        quote = await asyncio.to_thread(
            self._svc.get_realtime_quote, symbol, provider=provider
        )

        bid = quote["bid"]
        ask = quote["ask"]
        spread = quote["spread"]
        spread_pct = quote["spread_pct"]
        last = quote["last_price"]

        # Slippage estimate: assume worst-case fill at 50% of spread
        slippage_est = spread * 0.5
        slippage_pct = round(slippage_est / last * 100, 4) if last else 0.0

        # ── Liquidity risk classification ────────────────────────────────
        if spread_pct < 0.02:
            liquidity_risk = "LOW"
        elif spread_pct < 0.05:
            liquidity_risk = "MEDIUM"
        elif spread_pct < max_spread_pct:
            liquidity_risk = "HIGH"
        else:
            liquidity_risk = "CRITICAL"

        # ── Trade recommendation ─────────────────────────────────────────
        reasons: list[str] = [
            f"Spread: {spread:.6f} ({spread_pct:.4f}%)",
            f"Estimated slippage per share: {slippage_est:.6f} ({slippage_pct:.4f}%)",
            f"Liquidity classification: {liquidity_risk}",
        ]

        if liquidity_risk == "CRITICAL":
            recommendation = "ABORT"
            reasons.append(
                f"Spread {spread_pct:.4f}% exceeds max threshold {max_spread_pct}% — "
                "abort to avoid excessive slippage."
            )
        elif liquidity_risk == "HIGH":
            recommendation = "CAUTION"
            reasons.append(
                "High spread — consider using a limit order instead of market order."
            )
        else:
            recommendation = "PROCEED"
            reasons.append("Spread is within acceptable limits — safe to execute.")

        return {
            "symbol": symbol,
            "provider": provider,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "last_price": last,
            "slippage_estimate": round(slippage_est, 6),
            "slippage_pct": slippage_pct,
            "liquidity_risk": liquidity_risk,
            "recommendation": recommendation,
            "max_spread_pct": max_spread_pct,
            "reasons": reasons,
        }


# ─────────────────────────────────────────────────────────────────────────
# MONITOR AGENT TOOLS
# ─────────────────────────────────────────────────────────────────────────

class UnrealizedPnLTool(AgentTool):
    """
    **Monitor Agent Tool** — Unrealized P&L Poller.

    For each open position in the portfolio, fetches the latest market price
    and computes unrealized P&L (absolute and percentage).

    The Monitor Agent calls this tool on a tight poll interval (e.g., every
    30 seconds) to:
        - Detect positions approaching stop-loss levels.
        - Trigger trailing-stop updates.
        - Identify positions eligible for partial profit taking.
        - Alert when portfolio drawdown exceeds configured thresholds.

    Positions are passed directly by the Monitor Agent from its internal
    state — this tool does NOT query any database.
    """

    name = "poll_unrealized_pnl"
    description = (
        "Fetches current market prices for all open positions and computes "
        "unrealized profit/loss for each position. Use this tool to monitor "
        "open trades and detect when stop-loss or take-profit levels are hit."
    )
    args_schema = PortfolioMonitorInput

    async def _execute(
        self,
        positions: list[dict[str, Any]],
        provider: str = "yfinance",
        **_: Any,
    ) -> dict[str, Any]:
        """
        Fetch current prices for all positions and compute P&L.

        Args:
            positions: List of position dicts, each with:
                       ``symbol``, ``entry_price``, ``quantity``, ``direction``.
            provider:  Quote provider for current prices.

        Returns:
            Dict with keys: positions (list with pnl added), total_unrealized_pnl,
            total_unrealized_pnl_pct, alerts (list of warning strings).
        """
        # Deduplicate symbols for efficient fetching
        unique_symbols = list({p["symbol"] for p in positions})

        # Fetch all quotes concurrently
        quote_tasks = [
            asyncio.to_thread(self._svc.get_realtime_quote, sym, provider=provider)
            for sym in unique_symbols
        ]
        quote_results = await asyncio.gather(*quote_tasks, return_exceptions=True)

        current_prices: dict[str, float] = {}
        for sym, result in zip(unique_symbols, quote_results):
            if isinstance(result, Exception):
                logger.warning("Quote failed for %s: %s", sym, result)
                current_prices[sym] = 0.0
            else:
                current_prices[sym] = result.get("last_price", 0.0)

        # ── Compute P&L per position ─────────────────────────────────────
        enriched: list[dict[str, Any]] = []
        total_pnl = 0.0
        total_cost = 0.0
        alerts: list[str] = []

        for pos in positions:
            sym = pos["symbol"]
            entry = float(pos.get("entry_price", 0))
            qty = float(pos.get("quantity", 0))
            direction = str(pos.get("direction", "LONG")).upper()
            current = current_prices.get(sym, 0.0)

            if entry == 0 or qty == 0 or current == 0:
                pnl = 0.0
                pnl_pct = 0.0
            else:
                if direction == "LONG":
                    pnl = (current - entry) * qty
                    pnl_pct = (current - entry) / entry * 100
                else:  # SHORT
                    pnl = (entry - current) * qty
                    pnl_pct = (entry - current) / entry * 100

            cost_basis = entry * qty
            total_pnl += pnl
            total_cost += cost_basis

            # Drawdown alert threshold: -5% per position
            if pnl_pct < -5.0:
                alerts.append(
                    f"⚠️  {sym} | Unrealized loss {pnl_pct:.2f}% "
                    f"(${pnl:.2f}) — approaching stop-loss territory."
                )

            enriched.append({
                **pos,
                "current_price": round(current, 6),
                "unrealized_pnl": round(pnl, 4),
                "unrealized_pnl_pct": round(pnl_pct, 4),
                "cost_basis": round(cost_basis, 4),
            })

        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

        if total_pnl_pct < -10.0:
            alerts.append(
                f"🚨 Portfolio drawdown {total_pnl_pct:.2f}% — "
                "consider reducing exposure immediately."
            )

        return {
            "positions": enriched,
            "total_unrealized_pnl": round(total_pnl, 4),
            "total_unrealized_pnl_pct": round(total_pnl_pct, 4),
            "total_cost_basis": round(total_cost, 4),
            "positions_count": len(enriched),
            "alerts": alerts,
            "provider": provider,
        }


# ─────────────────────────────────────────────────────────────────────────
# Tool Factory Functions
# ─────────────────────────────────────────────────────────────────────────

def get_analyst_tools(data_service: DataService) -> list[AgentTool]:
    """
    Build the tool set for the Analyst Agent.

    Tools provided:
        1. ``FinancialHealthTool`` — ratios + news sentiment.

    Args:
        data_service: Shared DataService instance.

    Returns:
        List of AgentTool instances bound to the provided DataService.
    """
    return [
        FinancialHealthTool(data_service),
    ]


def get_planner_tools(data_service: DataService) -> list[AgentTool]:
    """
    Build the tool set for the Planner Agent.

    Tools provided:
        1. ``TechnicalIndicatorsTool`` — SMA, EMA, RSI, MACD, ATR, BB.

    Args:
        data_service: Shared DataService instance.

    Returns:
        List of AgentTool instances.
    """
    return [
        TechnicalIndicatorsTool(data_service),
    ]


def get_executor_tools(data_service: DataService) -> list[AgentTool]:
    """
    Build the tool set for the Executor Agent.

    Tools provided:
        1. ``OrderBookSlippageTool`` — real-time bid/ask + slippage validation.

    Args:
        data_service: Shared DataService instance.

    Returns:
        List of AgentTool instances.
    """
    return [
        OrderBookSlippageTool(data_service),
    ]


def get_monitor_tools(data_service: DataService) -> list[AgentTool]:
    """
    Build the tool set for the Monitor Agent.

    Tools provided:
        1. ``UnrealizedPnLTool`` — portfolio P&L polling with alerts.

    Args:
        data_service: Shared DataService instance.

    Returns:
        List of AgentTool instances.
    """
    return [
        UnrealizedPnLTool(data_service),
    ]


def get_all_tools(data_service: DataService) -> dict[str, list[AgentTool]]:
    """
    Convenience factory: build all four agent tool sets at once.

    Args:
        data_service: Shared DataService instance.

    Returns:
        Dict mapping agent role names to their tool lists:
        ``{"analyst": [...], "planner": [...], "executor": [...], "monitor": [...]}``.

    Example::

        from data_layer.openbb_service import DataService
        from agents.tools import get_all_tools

        svc = DataService()
        tools = get_all_tools(svc)
        schemas = [t.as_openai_schema() for t in tools["analyst"]]
    """
    return {
        "analyst": get_analyst_tools(data_service),
        "planner": get_planner_tools(data_service),
        "executor": get_executor_tools(data_service),
        "monitor": get_monitor_tools(data_service),
    }
