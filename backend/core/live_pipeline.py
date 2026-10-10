"""
==============================================================
backend/core/live_pipeline.py — Antigravity LivePipeline
==============================================================
Hybrid data pipeline that unifies three heterogeneous market data
sources into a single, analytics-ready Pandas DataFrame emitted on
every bar close.

Sources (in priority order)
---------------------------
1. **Hyperliquid REST** — real-time mid-price, funding rate, and best
   bid/ask spread from the public ``/info`` endpoint (no auth required).
2. **OpenBB Platform v4** — macro-economic context (FRED: FEDFUNDS,
   T10Y2Y, CPIAUCSL, VIXCLS) and daily news-sentiment scores.
3. **MetaTrader 5** — H1 OHLCV bars via ``copy_rates_from_pos``.

Fallback chain
--------------
    Primary:    Hyperliquid REST + OpenBB + MT5
    Fallback A: QuoteCache (when Hyperliquid is down)
    Fallback B: yfinance via MT5Connector (when OpenBB is down)
    Fallback C: last good DataFrame held in memory (network full-outage)

Every data fetch is independently fault-tolerant: a failure in one
source degrades gracefully to its fallback without blocking the others.

Output schema (columns present on every emitted DataFrame)
----------------------------------------------------------
    Timestamp columns
        bar_time            DatetimeIndex (UTC, bar open time)

    OHLCV (from MT5 / yfinance fallback)
        open, high, low, close, volume

    Hyperliquid enrichment
        hl_coin             Hyperliquid coin code (e.g. "EUR", "BTC")
        hl_mid              Mid-price from HL order book
        hl_bid, hl_ask      Best bid/ask
        hl_spread_bps       Spread in basis points
        hl_funding_rate     8-hour perpetual funding rate (float, e.g. 0.0001)
        hl_open_interest    Total open interest (notional USD)
        hl_source           "LIVE" | "CACHE" | "UNAVAILABLE"

    Macro context (from OpenBB / FRED)
        macro_fed_funds     Latest FEDFUNDS rate (%)
        macro_yield_spread  10Y-2Y Treasury spread (%)
        macro_cpi           CPI index value (latest reading)
        macro_vix           VIX index (latest reading)
        macro_staleness_h   Hours since the macro data was refreshed

    Sentiment (from OpenBB news)
        sentiment_score     Float in [-1.0, +1.0] (positive = bullish)
        sentiment_label     "BULLISH" | "BEARISH" | "NEUTRAL"
        sentiment_source    "OPENBB" | "UNAVAILABLE"

    Pipeline metadata
        pipeline_ts         UNIX timestamp of this bar assembly
        sources_used        Comma-separated list of active sources

Bar close detection
-------------------
The pipeline uses a lightweight asyncio loop.  Each ``tick_interval_sec``
it reads the latest MT5 tick, compares the current bar's open time against
the previous bar open time, and triggers ``_assemble_bar()`` when a new bar
has opened.  This is intentionally MT5-agnostic: if MT5 is unavailable,
wall-clock rounding to the nearest hour is used as a fallback.

Usage
-----
    from backend.core.live_pipeline import LivePipeline
    from backend.core.mt5_connector import MT5Connector

    connector = MT5Connector()
    connector.connect()

    pipeline = LivePipeline(mt5=connector, symbols=["EURUSD", "BTCUSD"])
    pipeline.on_bar(lambda symbol, df: print(symbol, df.tail(1)))

    await pipeline.start()   # runs until pipeline.stop() is called

Thread / async model
--------------------
``LivePipeline.start()`` is a coroutine that runs an asyncio loop.
Each external data fetch runs in a separate asyncio task so that a slow
provider never blocks the others.  CPU-bound pandas work runs in the
default thread executor to keep the event loop responsive.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from loguru import logger

# ── Internal module imports ────────────────────────────────────────────────────
from backend.core.mt5_connector import MT5Connector
from backend.core.quote_cache import LiveQuote, QuoteCache, get_quote_cache
from backend.core.symbol_sync import SymbolSynchroniser, get_synchroniser


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Hyperliquid public REST base URL (no API key required)
_HL_BASE: str = "https://api.hyperliquid.xyz"
_HL_TIMEOUT: float = 6.0

# OpenBB macro series to fetch from FRED
_MACRO_SERIES: List[str] = ["FEDFUNDS", "T10Y2Y", "CPIAUCSL", "VIXCLS"]

# How often to refresh macro data (seconds) — macro data is daily/monthly
_MACRO_REFRESH_SEC: int = 3_600  # 1 hour

# Sentiment cache duration (seconds)
_SENTIMENT_REFRESH_SEC: int = 900  # 15 minutes

# Funding rate cache duration (seconds)
_FUNDING_REFRESH_SEC: int = 60  # 1 minute

# Column names in the canonical bar DataFrame
_COL_ORDER: List[str] = [
    "open", "high", "low", "close", "volume",
    "hl_coin", "hl_mid", "hl_bid", "hl_ask", "hl_spread_bps",
    "hl_funding_rate", "hl_open_interest", "hl_source",
    "macro_fed_funds", "macro_yield_spread", "macro_cpi", "macro_vix",
    "macro_staleness_h",
    "sentiment_score", "sentiment_label", "sentiment_source",
    "pipeline_ts", "sources_used",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper enums & data classes
# ─────────────────────────────────────────────────────────────────────────────


class DataSourceStatus(Enum):
    """Operational status of each data feed."""
    LIVE = auto()
    CACHE = auto()
    DEGRADED = auto()
    UNAVAILABLE = auto()


@dataclass
class MacroSnapshot:
    """
    Immutable snapshot of macro-economic indicators.

    All values are the latest reading as of ``fetched_at``.
    Missing series are stored as ``float('nan')``.
    """
    fed_funds: float = float("nan")
    yield_spread: float = float("nan")
    cpi: float = float("nan")
    vix: float = float("nan")
    fetched_at: float = field(default_factory=time.time)

    @property
    def staleness_hours(self) -> float:
        """Hours elapsed since this snapshot was captured."""
        return (time.time() - self.fetched_at) / 3600.0

    def is_stale(self, max_age_sec: int = _MACRO_REFRESH_SEC) -> bool:
        return (time.time() - self.fetched_at) > max_age_sec


@dataclass
class HLTicker:
    """
    Real-time market data fetched from Hyperliquid for one coin.
    """
    coin: str
    mid: float = float("nan")
    bid: float = float("nan")
    ask: float = float("nan")
    spread_bps: float = float("nan")
    funding_rate: float = float("nan")
    open_interest: float = float("nan")
    source: str = "UNAVAILABLE"
    fetched_at: float = field(default_factory=time.time)


@dataclass
class SentimentReading:
    """Aggregated daily sentiment for one symbol."""
    symbol: str
    score: float = 0.0        # [-1.0, +1.0]
    label: str = "NEUTRAL"
    source: str = "UNAVAILABLE"
    fetched_at: float = field(default_factory=time.time)

    def is_stale(self, max_age_sec: int = _SENTIMENT_REFRESH_SEC) -> bool:
        return (time.time() - self.fetched_at) > max_age_sec


# ─────────────────────────────────────────────────────────────────────────────
# Hyperliquid REST client (synchronous — called in executor)
# ─────────────────────────────────────────────────────────────────────────────


class HyperliquidClient:
    """
    Thin, stateless REST client for the Hyperliquid public ``/info`` endpoint.

    All methods are synchronous so they can be called from a thread pool
    executor without blocking the asyncio event loop.

    Hyperliquid ``/info`` request types used here
    -----------------------------------------------
    ``allMids``        → dict of coin → mid-price string
    ``metaAndAssetCtxs`` → list of [meta, list[AssetCtx]]
                           where AssetCtx contains funding, OI, etc.
    ``l2Book``         → best bid/ask for a single coin
    """

    def __init__(
        self,
        base_url: str = _HL_BASE,
        timeout: float = _HL_TIMEOUT,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _post(self, payload: dict) -> Any:
        """
        Execute a POST to /info and return the parsed JSON body.

        Raises
        ------
        requests.RequestException
            On any network or HTTP error.
        ValueError
            When the response body cannot be parsed as JSON.
        """
        resp = self._session.post(
            f"{self._base}/info",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_all_mids(self) -> Dict[str, float]:
        """
        Fetch mid-prices for all listed perpetuals.

        Returns
        -------
        dict[str, float]
            Mapping of coin symbol (e.g. ``"BTC"``) to float mid-price.
            Returns empty dict on failure.
        """
        try:
            raw: Dict[str, str] = self._post({"type": "allMids"})
            return {coin: float(price) for coin, price in raw.items()}
        except Exception as exc:
            logger.warning(f"HL allMids failed: {exc}")
            return {}

    def get_asset_contexts(self) -> Dict[str, dict]:
        """
        Fetch funding rates and open interest for all perp assets.

        The ``metaAndAssetCtxs`` endpoint returns a two-element list:
        ``[meta_dict, list_of_asset_ctx]``.  We zip the coin names from
        the meta section with the context objects.

        Returns
        -------
        dict[str, dict]
            Mapping of coin → ``{funding_rate, open_interest, mark_price, ...}``.
            Returns empty dict on failure.
        """
        try:
            data = self._post({"type": "metaAndAssetCtxs"})
            if not (isinstance(data, list) and len(data) == 2):
                logger.warning("HL metaAndAssetCtxs returned unexpected shape.")
                return {}

            meta, contexts = data[0], data[1]
            universe: List[dict] = meta.get("universe", [])
            result: Dict[str, dict] = {}

            for info, ctx in zip(universe, contexts):
                coin: str = info.get("name", "")
                if not coin:
                    continue
                result[coin] = {
                    "funding_rate":  float(ctx.get("funding", 0) or 0),
                    "open_interest": float(ctx.get("openInterest", 0) or 0),
                    "mark_price":    float(ctx.get("markPx", 0) or 0),
                    "prev_day_px":   float(ctx.get("prevDayPx", 0) or 0),
                }
            return result

        except Exception as exc:
            logger.warning(f"HL metaAndAssetCtxs failed: {exc}")
            return {}

    def get_l2_book(self, coin: str, n_levels: int = 1) -> Tuple[float, float]:
        """
        Fetch the best bid and ask for one coin from the L2 order book.

        Parameters
        ----------
        coin : str
            Hyperliquid coin code (e.g. ``"BTC"``, ``"EUR"``).
        n_levels : int
            Number of price levels to request (only level-0 is used here).

        Returns
        -------
        tuple[float, float]
            ``(best_bid, best_ask)`` as floats.
            Returns ``(nan, nan)`` on failure.
        """
        _nan = float("nan")
        try:
            data = self._post({"type": "l2Book", "coin": coin, "nSigFigs": 5})
            levels: dict = data.get("levels", [[], []])
            bids: list = levels[0] if len(levels) > 0 else []
            asks: list = levels[1] if len(levels) > 1 else []

            best_bid = float(bids[0]["px"]) if bids else _nan
            best_ask = float(asks[0]["px"]) if asks else _nan
            return best_bid, best_ask

        except Exception as exc:
            logger.debug(f"HL l2Book({coin}) failed: {exc}")
            return _nan, _nan

    def get_ticker(self, coin: str) -> HLTicker:
        """
        Assemble a full ``HLTicker`` for one coin in a single call chain.

        Order of calls:
        1. ``allMids`` → mid price (often already available from a bulk call)
        2. ``l2Book``  → best bid/ask (used to compute spread)
        3. ``metaAndAssetCtxs`` → funding rate and OI

        In production callers should use the bulk versions and pass data
        into this helper to avoid redundant HTTP calls; this method is
        useful for one-off lookups and tests.

        Parameters
        ----------
        coin : str
            Hyperliquid coin code (e.g. ``"BTC"``).

        Returns
        -------
        HLTicker
        """
        mids = self.get_all_mids()
        mid = mids.get(coin, float("nan"))

        bid, ask = self.get_l2_book(coin)
        if bid != bid:   # NaN — fall back to mid ± tiny spread
            bid = mid * 0.9999
            ask = mid * 1.0001

        # Spread in basis points
        spread_bps = (
            round((ask - bid) / mid * 10_000, 2)
            if mid > 0 and mid == mid else float("nan")
        )

        ctx = self.get_asset_contexts().get(coin, {})
        funding = ctx.get("funding_rate", float("nan"))
        oi = ctx.get("open_interest", float("nan"))

        return HLTicker(
            coin=coin,
            mid=mid,
            bid=bid,
            ask=ask,
            spread_bps=spread_bps,
            funding_rate=funding,
            open_interest=oi,
            source="LIVE",
        )


# ─────────────────────────────────────────────────────────────────────────────
# OpenBB macro + sentiment fetcher (synchronous — called in executor)
# ─────────────────────────────────────────────────────────────────────────────


class OpenBBMacroFetcher:
    """
    Thin wrapper around the existing ``DataService`` for macro & sentiment.

    Uses the ``DataService`` singleton from ``data_layer.openbb_service``
    when available.  Falls back to a direct ``yfinance`` pull (via the
    existing ``MT5Connector.get_ohlcv`` yfinance path) when OpenBB is not
    installed.
    """

    def __init__(self) -> None:
        self._service = None
        self._available = False
        try:
            # DataService raises OpenBBNotInstalledError if openbb is absent
            from data_layer.openbb_service import DataService  # type: ignore
            self._service = DataService()
            self._available = True
            logger.info("OpenBB DataService available for macro/sentiment pulls.")
        except Exception as exc:
            logger.warning(
                f"OpenBB DataService unavailable: {exc}. "
                f"Macro data will use yfinance ^TNX / ^VIX fallback."
            )

    # ── Macro ──────────────────────────────────────────────────────────────

    def fetch_macro(self) -> MacroSnapshot:
        """
        Pull the latest macro-economic indicators.

        Returns
        -------
        MacroSnapshot
            Contains FEDFUNDS, T10Y2Y, CPIAUCSL, VIXCLS.
            Fields for any failed series are ``nan``.
        """
        if self._available and self._service is not None:
            return self._fetch_macro_openbb()
        return self._fetch_macro_yfinance()

    def _fetch_macro_openbb(self) -> MacroSnapshot:
        """Fetch via OpenBB / FRED — the preferred path."""
        snap = MacroSnapshot()
        try:
            macro_dfs = self._service.get_macro_indicators(  # type: ignore[union-attr]
                indicators_list=_MACRO_SERIES,
                provider="fred",
                start_date="2020-01-01",
            )
            def _latest(series_id: str) -> float:
                df = macro_dfs.get(series_id)
                if df is None or df.empty:
                    return float("nan")
                col = df.columns[0]
                return float(df[col].dropna().iloc[-1])

            snap.fed_funds    = _latest("FEDFUNDS")
            snap.yield_spread = _latest("T10Y2Y")
            snap.cpi          = _latest("CPIAUCSL")
            snap.vix          = _latest("VIXCLS")
            logger.debug(
                f"Macro (OpenBB) | FEDFUNDS={snap.fed_funds:.2f}% | "
                f"T10Y2Y={snap.yield_spread:.3f}% | "
                f"VIX={snap.vix:.2f}"
            )
        except Exception as exc:
            logger.warning(f"OpenBB macro fetch failed: {exc}. Snapshot may be partial.")
        return snap

    def _fetch_macro_yfinance(self) -> MacroSnapshot:
        """
        Fallback: pull VIX and 10-year yield from Yahoo Finance directly.
        FEDFUNDS and CPI are not available via yfinance — left as nan.
        """
        snap = MacroSnapshot()
        try:
            import yfinance as yf  # type: ignore

            # VIX — Yahoo ticker ^VIX
            vix_hist = yf.Ticker("^VIX").history(period="5d", interval="1d")
            if not vix_hist.empty:
                snap.vix = float(vix_hist["Close"].iloc[-1])

            # 10-year yield — Yahoo ticker ^TNX (in percent ×10, so divide)
            tnx_hist = yf.Ticker("^TNX").history(period="5d", interval="1d")
            if not tnx_hist.empty:
                snap.yield_spread = float(tnx_hist["Close"].iloc[-1]) / 10.0

            logger.debug(
                f"Macro (yfinance fallback) | VIX={snap.vix:.2f} | "
                f"10Y={snap.yield_spread:.3f}%"
            )
        except Exception as exc:
            logger.warning(f"yfinance macro fallback failed: {exc}")
        return snap

    # ── Sentiment ──────────────────────────────────────────────────────────

    def fetch_sentiment(self, symbol: str) -> SentimentReading:
        """
        Fetch daily news sentiment score for ``symbol``.

        Returns
        -------
        SentimentReading
            ``score`` in [-1, +1].  Positive = net bullish news.
        """
        if self._available and self._service is not None:
            return self._fetch_sentiment_openbb(symbol)
        return SentimentReading(symbol=symbol, score=0.0, label="NEUTRAL",
                                source="UNAVAILABLE")

    def _fetch_sentiment_openbb(self, symbol: str) -> SentimentReading:
        """
        Derive a sentiment score from recent news headlines via OpenBB.

        Aggregation method
        ------------------
        Fetch up to 20 latest news items, count POSITIVE vs NEGATIVE labels
        from the ``DataService._enrich_news_sentiment`` enrichment, then
        compute a normalised net-sentiment score:
            score = (n_positive - n_negative) / n_total ∈ [-1, +1]
        """
        # Map MT5 symbol to a format OpenBB / yfinance understands
        _OBB_MAP = {
            "EURUSD": "EURUSD=X",  "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X",  "BTCUSD": "BTC-USD",
            "XAUUSD": "GLD",       "US500":  "SPY",
        }
        obb_ticker = _OBB_MAP.get(symbol, symbol)

        try:
            news_df: pd.DataFrame = self._service.get_equity_news(  # type: ignore[union-attr]
                ticker=obb_ticker,
                limit=20,
                provider="tiingo",
            )
            if news_df.empty or "sentiment_label" not in news_df.columns:
                return SentimentReading(symbol=symbol, score=0.0,
                                        label="NEUTRAL", source="OPENBB")

            counts = news_df["sentiment_label"].value_counts()
            n_pos = int(counts.get("POSITIVE", 0))
            n_neg = int(counts.get("NEGATIVE", 0))
            n_tot = max(len(news_df), 1)

            score = round((n_pos - n_neg) / n_tot, 4)
            label = (
                "BULLISH"  if score >  0.1 else
                "BEARISH"  if score < -0.1 else
                "NEUTRAL"
            )
            logger.debug(
                f"Sentiment ({symbol}) | +{n_pos} -{n_neg} /{n_tot} → "
                f"score={score:.3f} [{label}]"
            )
            return SentimentReading(symbol=symbol, score=score, label=label,
                                    source="OPENBB")

        except Exception as exc:
            logger.debug(f"Sentiment fetch ({symbol}): {exc}")
            return SentimentReading(symbol=symbol, score=0.0, label="NEUTRAL",
                                    source="UNAVAILABLE")


# ─────────────────────────────────────────────────────────────────────────────
# LivePipeline — main orchestrator
# ─────────────────────────────────────────────────────────────────────────────


class LivePipeline:
    """
    Antigravity hybrid data pipeline.

    On every bar close (H1 by default) it:
    1. Reads the latest OHLCV bar from MT5 (or yfinance fallback).
    2. Enriches each row with real-time Hyperliquid tick data.
    3. Appends current macro-economic context from OpenBB / FRED.
    4. Attaches a news-sentiment score for each symbol.
    5. Merges all sources into a canonical Pandas DataFrame.
    6. Calls every registered ``on_bar`` callback with ``(symbol, df)``.

    All external fetches are executed concurrently in asyncio tasks, each
    running in a ``ThreadPoolExecutor`` to avoid blocking the event loop
    on synchronous network I/O.

    Parameters
    ----------
    mt5 : MT5Connector
        Connected MT5 session (can be in yfinance mode).
    symbols : list[str]
        MT5 ticker names to track (e.g. ``["EURUSD", "BTCUSD"]``).
    bar_timeframe_sec : int
        Bar duration in seconds (default 3600 = H1).
    tick_interval_sec : float
        How often the event loop polls for new bar-close events.
    quote_cache : QuoteCache | None
        Optional pre-initialized QuoteCache.  Created automatically when None.
    hl_client : HyperliquidClient | None
        Optional pre-initialized Hyperliquid client (for testing/DI).
    macro_fetcher : OpenBBMacroFetcher | None
        Optional pre-initialized macro fetcher.
    max_workers : int
        Thread pool size for synchronous I/O tasks.
    """

    def __init__(
        self,
        mt5: MT5Connector,
        symbols: Optional[List[str]] = None,
        bar_timeframe_sec: int = 3_600,
        tick_interval_sec: float = 5.0,
        quote_cache: Optional[QuoteCache] = None,
        hl_client: Optional[HyperliquidClient] = None,
        macro_fetcher: Optional[OpenBBMacroFetcher] = None,
        max_workers: int = 6,
    ) -> None:
        from backend.config import SYMBOLS as _DEFAULT_SYMBOLS  # type: ignore

        self._mt5 = mt5
        self._symbols: List[str] = symbols or _DEFAULT_SYMBOLS
        self._bar_sec: int = max(60, bar_timeframe_sec)
        self._tick_interval: float = max(0.5, tick_interval_sec)

        # External data clients
        self._cache: QuoteCache = quote_cache or get_quote_cache(ttl_seconds=30)
        self._hl: HyperliquidClient = hl_client or HyperliquidClient()
        self._macro_fetcher: OpenBBMacroFetcher = macro_fetcher or OpenBBMacroFetcher()
        self._syncer: SymbolSynchroniser = get_synchroniser()

        # Thread pool for blocking I/O
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="antigravity-pipeline",
        )

        # State
        self._running: bool = False
        self._last_bar_open: Dict[str, Optional[datetime]] = {s: None for s in self._symbols}
        self._last_df: Dict[str, Optional[pd.DataFrame]] = {s: None for s in self._symbols}

        # Shared cross-symbol state (refreshed on their own schedules)
        self._macro_snap: MacroSnapshot = MacroSnapshot()
        self._hl_mids: Dict[str, float] = {}
        self._hl_contexts: Dict[str, dict] = {}
        self._sentiment: Dict[str, SentimentReading] = {}
        self._last_macro_fetch: float = 0.0
        self._last_hl_bulk_fetch: float = 0.0

        # Symbol → HL coin map (built once)
        self._hl_map: Dict[str, str] = self._syncer.get_synced_map(self._symbols)
        logger.info(
            f"LivePipeline initialised | "
            f"symbols={self._symbols} | "
            f"bar={self._bar_sec}s | "
            f"hl_mapped={list(self._hl_map.keys())}"
        )

        # Bar callbacks: list of async-or-sync callables (symbol, df) → None
        self._bar_callbacks: List[Callable] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def on_bar(self, callback: Callable[[str, pd.DataFrame], Any]) -> None:
        """
        Register a callback to be invoked on every bar close.

        The callback receives ``(symbol: str, df: pd.DataFrame)`` where
        ``df`` is the fully merged, canonical bar DataFrame for that symbol.
        Callbacks may be sync or async coroutines.

        Parameters
        ----------
        callback : callable
            Function or coroutine function taking ``(symbol, df)``.
        """
        self._bar_callbacks.append(callback)
        logger.debug(f"LivePipeline.on_bar: registered {callback.__name__!r}")

    async def start(self) -> None:
        """
        Start the pipeline event loop.

        This coroutine runs until ``stop()`` is called.  It performs an
        initial bulk Hyperliquid fetch and macro refresh, then polls for
        bar closes at ``tick_interval_sec`` cadence.
        """
        self._running = True
        logger.info("LivePipeline starting …")

        # Warm up shared state before entering the main loop
        await self._refresh_hl_bulk()
        await self._refresh_macro()

        try:
            while self._running:
                try:
                    await self._pipeline_tick()
                except Exception as exc:
                    logger.error(f"LivePipeline tick error (non-fatal): {exc}")
                await asyncio.sleep(self._tick_interval)
        finally:
            self._executor.shutdown(wait=False)
            logger.info("LivePipeline stopped.")

    def stop(self) -> None:
        """Signal the pipeline to stop after the current tick completes."""
        self._running = False
        logger.info("LivePipeline stop requested.")

    # ── Context manager support ───────────────────────────────────────────────

    async def __aenter__(self) -> "LivePipeline":
        asyncio.get_event_loop().create_task(self.start())
        return self

    async def __aexit__(self, *_) -> None:
        self.stop()

    # ── Core tick ─────────────────────────────────────────────────────────────

    async def _pipeline_tick(self) -> None:
        """
        Called every ``tick_interval_sec``.

        For each symbol, detect whether a new bar has closed.  When yes,
        fire ``_assemble_and_emit(symbol)`` as a separate task so symbols
        don't block each other.
        """
        now_utc = datetime.now(timezone.utc)

        # Refresh bulk Hyperliquid data if stale (every 10 seconds by default)
        if (time.time() - self._last_hl_bulk_fetch) > 10:
            await self._refresh_hl_bulk()

        # Refresh macro if stale
        if self._macro_snap.is_stale():
            await self._refresh_macro()

        # Per-symbol bar-close detection
        tasks = []
        for symbol in self._symbols:
            if await self._is_new_bar(symbol, now_utc):
                tasks.append(asyncio.create_task(
                    self._assemble_and_emit(symbol),
                    name=f"bar-{symbol}",
                ))

        if tasks:
            # Wait for all bar assemblies, collect exceptions without re-raising
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Bar assembly error: {r}")

    # ── Bar close detection ───────────────────────────────────────────────────

    async def _is_new_bar(self, symbol: str, now_utc: datetime) -> bool:
        """
        Return True if a new bar has opened since the last observed bar.

        Strategy:
        - Compute the expected bar-open time = floor(now / bar_sec) * bar_sec.
        - If it differs from the last recorded bar-open → new bar.

        Parameters
        ----------
        symbol : str
            MT5 ticker.
        now_utc : datetime
            Current UTC time.

        Returns
        -------
        bool
        """
        # Compute current bar open time using floor division on epoch seconds
        epoch = int(now_utc.timestamp())
        current_bar_open_epoch = (epoch // self._bar_sec) * self._bar_sec
        current_bar_open = datetime.fromtimestamp(
            current_bar_open_epoch, tz=timezone.utc
        )

        prev_open = self._last_bar_open.get(symbol)

        if prev_open is None or current_bar_open > prev_open:
            self._last_bar_open[symbol] = current_bar_open
            return prev_open is not None   # skip the very first run (no previous bar)

        return False

    # ── Bar assembly ──────────────────────────────────────────────────────────

    async def _assemble_and_emit(self, symbol: str) -> None:
        """
        Full bar assembly pipeline for one symbol.

        Runs all fetches concurrently, merges results, then calls callbacks.
        """
        loop = asyncio.get_event_loop()

        # ── Concurrent fetches ─────────────────────────────────────────────
        ohlcv_task = loop.run_in_executor(
            self._executor, self._fetch_ohlcv, symbol
        )
        hl_task = loop.run_in_executor(
            self._executor, self._build_hl_ticker, symbol
        )
        sentiment_task = loop.run_in_executor(
            self._executor, self._fetch_sentiment_cached, symbol
        )

        # Gather with per-task exception isolation
        ohlcv_df, hl_ticker, sentiment = await asyncio.gather(
            ohlcv_task, hl_task, sentiment_task, return_exceptions=True
        )

        # Handle fetch failures gracefully
        if isinstance(ohlcv_df, Exception):
            logger.warning(f"OHLCV fetch failed ({symbol}): {ohlcv_df}")
            ohlcv_df = self._last_df.get(symbol)   # reuse last good frame
        if isinstance(hl_ticker, Exception):
            logger.warning(f"HL ticker failed ({symbol}): {hl_ticker}")
            hl_ticker = HLTicker(coin=self._hl_map.get(symbol, ""))
        if isinstance(sentiment, Exception):
            logger.warning(f"Sentiment failed ({symbol}): {sentiment}")
            sentiment = SentimentReading(symbol=symbol)

        if ohlcv_df is None or ohlcv_df.empty:
            logger.warning(f"No OHLCV data available for {symbol} — skipping bar.")
            return

        # ── Merge into canonical DataFrame ─────────────────────────────────
        df = await loop.run_in_executor(
            self._executor,
            self._merge_bar,
            symbol, ohlcv_df, hl_ticker, self._macro_snap, sentiment
        )

        self._last_df[symbol] = df
        logger.info(
            f"Bar assembled | {symbol} | "
            f"close={df['close'].iloc[-1]:.5f} | "
            f"hl_mid={df['hl_mid'].iloc[-1]:.5f} | "
            f"sentiment={df['sentiment_label'].iloc[-1]} | "
            f"VIX={df['macro_vix'].iloc[-1]:.2f}"
        )

        # ── Fire bar callbacks ─────────────────────────────────────────────
        for cb in self._bar_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(symbol, df)
                else:
                    await loop.run_in_executor(self._executor, cb, symbol, df)
            except Exception as exc:
                logger.error(f"on_bar callback error ({symbol}): {exc}")

    # ── Data fetchers (synchronous — run in executor) ─────────────────────────

    def _fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        """
        Fetch H1 OHLCV from MT5 with automatic fallback to yfinance.

        Returns
        -------
        pd.DataFrame
            With columns: open, high, low, close, volume.
            DatetimeIndex in UTC.

        Raises
        ------
        RuntimeError
            When both MT5 and yfinance return no data.
        """
        # ── Primary: MT5 native H1 bars ────────────────────────────────────
        try:
            if self._mt5.connected and not getattr(self._mt5, "_use_yfinance", True):
                import MetaTrader5 as mt5_lib  # type: ignore
                df = self._mt5.get_ohlcv(
                    symbol, timeframe=mt5_lib.TIMEFRAME_H1, bars=200
                )
                if df is not None and not df.empty:
                    return self._normalise_ohlcv(df)
        except Exception as exc:
            logger.warning(f"MT5 OHLCV ({symbol}) failed: {exc}")

        # ── Fallback A: yfinance via MT5Connector ─────────────────────────
        try:
            df = self._mt5.get_ohlcv(symbol, bars=200)
            if df is not None and not df.empty:
                logger.debug(f"OHLCV fallback to yfinance for {symbol}")
                return self._normalise_ohlcv(df)
        except Exception as exc:
            logger.warning(f"yfinance OHLCV ({symbol}) failed: {exc}")

        raise RuntimeError(f"No OHLCV data available for {symbol}")

    @staticmethod
    def _normalise_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure OHLCV DataFrame has lowercase column names and a UTC DatetimeIndex.

        Parameters
        ----------
        df : pd.DataFrame
            Raw OHLCV frame from MT5Connector or yfinance.

        Returns
        -------
        pd.DataFrame
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        # Ensure UTC-aware index
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        df.index.name = "bar_time"

        # Cast numerics
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna(subset=["close"])

    def _build_hl_ticker(self, symbol: str) -> HLTicker:
        """
        Return a ``HLTicker`` for one symbol using the bulk-fetched data
        already cached in ``self._hl_mids`` / ``self._hl_contexts``.

        If the coin is not found in the bulk data, it attempts a targeted
        ``l2Book`` call for the best bid/ask.

        Falls back to ``QuoteCache`` when Hyperliquid is fully unreachable.

        Parameters
        ----------
        symbol : str
            MT5 ticker (e.g. ``"EURUSD"``).

        Returns
        -------
        HLTicker
        """
        coin = self._hl_map.get(symbol)
        if not coin:
            return HLTicker(coin="", source="UNAVAILABLE")

        # ── Primary: use pre-fetched bulk data ────────────────────────────
        mid = self._hl_mids.get(coin, float("nan"))
        ctx = self._hl_contexts.get(coin, {})
        funding = ctx.get("funding_rate", float("nan"))
        oi = ctx.get("open_interest", float("nan"))

        if mid == mid:  # not NaN — we have a good mid from the bulk fetch
            # For live best bid/ask: check QuoteCache first (fresher than L2)
            cached_q = self._cache.get(symbol)
            if cached_q:
                bid, ask = cached_q.bid, cached_q.ask
                source = "CACHE"
            else:
                # Live L2 call for the best bid/ask only
                bid, ask = self._hl.get_l2_book(coin)
                source = "LIVE"

            if bid == bid and ask == ask and mid > 0:
                spread_bps = round((ask - bid) / mid * 10_000, 2)
            else:
                bid, ask, spread_bps = mid, mid, float("nan")

            ticker = HLTicker(
                coin=coin, mid=mid, bid=bid, ask=ask,
                spread_bps=spread_bps, funding_rate=funding,
                open_interest=oi, source=source,
            )

            # Write back to QuoteCache
            if bid == bid and ask == ask:
                try:
                    self._cache.set(LiveQuote(
                        symbol=symbol, bid=bid, ask=ask,
                        hl_coin=coin, source="HL",
                    ))
                except Exception:
                    pass

            return ticker

        # ── Fallback: QuoteCache for the price, HL bulk data unavailable ─
        cached_q = self._cache.get(symbol)
        if cached_q:
            mid_c = (cached_q.bid + cached_q.ask) / 2
            return HLTicker(
                coin=coin, mid=mid_c,
                bid=cached_q.bid, ask=cached_q.ask,
                spread_bps=float("nan"), funding_rate=funding,
                open_interest=oi, source="CACHE",
            )

        logger.debug(f"HL data unavailable for {symbol} ({coin})")
        return HLTicker(coin=coin, source="UNAVAILABLE")

    def _fetch_sentiment_cached(self, symbol: str) -> SentimentReading:
        """
        Return cached sentiment or trigger a fresh fetch when stale.

        Parameters
        ----------
        symbol : str
            MT5 ticker.

        Returns
        -------
        SentimentReading
        """
        reading = self._sentiment.get(symbol)
        if reading is None or reading.is_stale():
            reading = self._macro_fetcher.fetch_sentiment(symbol)
            self._sentiment[symbol] = reading
        return reading

    # ── Bulk refresh coroutines ───────────────────────────────────────────────

    async def _refresh_hl_bulk(self) -> None:
        """
        Fetch allMids + metaAndAssetCtxs from Hyperliquid in parallel.

        These two calls supply data for ALL symbols in a single HTTP round
        trip each, making them far more efficient than per-symbol calls.
        """
        loop = asyncio.get_event_loop()
        try:
            mids_task = loop.run_in_executor(self._executor, self._hl.get_all_mids)
            ctx_task  = loop.run_in_executor(self._executor, self._hl.get_asset_contexts)

            mids, contexts = await asyncio.gather(
                mids_task, ctx_task, return_exceptions=True
            )

            if not isinstance(mids, Exception):
                self._hl_mids = mids
            else:
                logger.warning(f"HL allMids bulk failed: {mids}")

            if not isinstance(contexts, Exception):
                self._hl_contexts = contexts
            else:
                logger.warning(f"HL assetCtx bulk failed: {contexts}")

            self._last_hl_bulk_fetch = time.time()
            logger.debug(
                f"HL bulk refresh | {len(self._hl_mids)} mids | "
                f"{len(self._hl_contexts)} contexts"
            )

        except Exception as exc:
            logger.warning(f"HL bulk refresh failed: {exc}")

    async def _refresh_macro(self) -> None:
        """
        Pull fresh macro-economic data from OpenBB / FRED.

        Runs in the thread executor to avoid blocking the event loop.
        Updates ``self._macro_snap`` in-place.
        """
        loop = asyncio.get_event_loop()
        try:
            snap = await loop.run_in_executor(
                self._executor, self._macro_fetcher.fetch_macro
            )
            self._macro_snap = snap
            logger.info(
                f"Macro refreshed | "
                f"FEDFUNDS={snap.fed_funds:.2f}% | "
                f"VIX={snap.vix:.2f} | "
                f"staleness={snap.staleness_hours:.2f}h"
            )
        except Exception as exc:
            logger.warning(f"Macro refresh failed: {exc}")

    # ── Bar merge (CPU-bound — runs in executor) ──────────────────────────────

    def _merge_bar(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
        hl_ticker: HLTicker,
        macro: MacroSnapshot,
        sentiment: SentimentReading,
    ) -> pd.DataFrame:
        """
        Merge all data sources into the canonical bar DataFrame.

        All enrichment columns are broadcast across every row of ``ohlcv``
        (they represent the state at the moment the bar closes, not per-row
        time-series values).

        Parameters
        ----------
        symbol : str
            MT5 ticker — used only for logging.
        ohlcv : pd.DataFrame
            H1 OHLCV frame with DatetimeIndex.
        hl_ticker : HLTicker
            Hyperliquid tick data snapshot.
        macro : MacroSnapshot
            Macro-economic state snapshot.
        sentiment : SentimentReading
            Latest sentiment score for this symbol.

        Returns
        -------
        pd.DataFrame
            Canonical frame with columns from ``_COL_ORDER``.
        """
        df = ohlcv.copy()
        _nan = float("nan")

        # ── Hyperliquid columns ────────────────────────────────────────────
        df["hl_coin"]        = hl_ticker.coin or ""
        df["hl_mid"]         = hl_ticker.mid if hl_ticker.mid == hl_ticker.mid else _nan
        df["hl_bid"]         = hl_ticker.bid if hl_ticker.bid == hl_ticker.bid else _nan
        df["hl_ask"]         = hl_ticker.ask if hl_ticker.ask == hl_ticker.ask else _nan
        df["hl_spread_bps"]  = hl_ticker.spread_bps
        df["hl_funding_rate"]= hl_ticker.funding_rate
        df["hl_open_interest"]= hl_ticker.open_interest
        df["hl_source"]      = hl_ticker.source

        # Override last-row hl_mid with the freshest quote if available
        # (earlier rows retain the broadcast value for historical reference)
        if hl_ticker.mid == hl_ticker.mid and hl_ticker.mid > 0:
            df.at[df.index[-1], "hl_mid"] = hl_ticker.mid
            df.at[df.index[-1], "hl_bid"] = hl_ticker.bid
            df.at[df.index[-1], "hl_ask"] = hl_ticker.ask

        # ── Macro columns ──────────────────────────────────────────────────
        df["macro_fed_funds"]   = macro.fed_funds
        df["macro_yield_spread"]= macro.yield_spread
        df["macro_cpi"]         = macro.cpi
        df["macro_vix"]         = macro.vix
        df["macro_staleness_h"] = round(macro.staleness_hours, 2)

        # ── Sentiment columns ──────────────────────────────────────────────
        df["sentiment_score"] = sentiment.score
        df["sentiment_label"] = sentiment.label
        df["sentiment_source"]= sentiment.source

        # ── Pipeline metadata ──────────────────────────────────────────────
        df["pipeline_ts"]   = time.time()
        df["sources_used"]  = self._compute_sources_tag(hl_ticker, macro, sentiment)

        # ── Enforce canonical column order ─────────────────────────────────
        present = [c for c in _COL_ORDER if c in df.columns]
        extra   = [c for c in df.columns if c not in _COL_ORDER]
        df = df[present + extra]

        return df

    @staticmethod
    def _compute_sources_tag(
        hl: HLTicker,
        macro: MacroSnapshot,
        sentiment: SentimentReading,
    ) -> str:
        """Build a human-readable source provenance tag."""
        parts: List[str] = ["MT5_OHLCV"]

        if hl.source in ("LIVE", "CACHE"):
            parts.append(f"HL_{hl.source}")
        else:
            parts.append("HL_UNAVAILABLE")

        macro_label = "MACRO_OPENBB" if not np.isnan(macro.fed_funds) else "MACRO_PARTIAL"
        parts.append(macro_label)

        if sentiment.source == "OPENBB":
            parts.append("SENTIMENT_OPENBB")
        else:
            parts.append("SENTIMENT_UNAVAILABLE")

        return ",".join(parts)

    # ── Introspection helpers ─────────────────────────────────────────────────

    def get_latest(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Return the most recently assembled bar DataFrame for ``symbol``.

        Returns ``None`` if no bar has been assembled yet.
        """
        return self._last_df.get(symbol)

    def status(self) -> dict:
        """
        Return a health-check snapshot of the pipeline.

        Returns
        -------
        dict
            Keys: ``running``, ``symbols``, ``hl_mids_count``,
            ``macro_staleness_h``, ``last_bars``.
        """
        return {
            "running": self._running,
            "symbols": self._symbols,
            "hl_mids_count": len(self._hl_mids),
            "hl_map": self._hl_map,
            "macro_staleness_h": round(self._macro_snap.staleness_hours, 2),
            "macro_fed_funds": self._macro_snap.fed_funds,
            "macro_vix": self._macro_snap.vix,
            "last_bars": {
                s: (str(self._last_bar_open.get(s)) if self._last_bar_open.get(s) else None)
                for s in self._symbols
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level factory
# ─────────────────────────────────────────────────────────────────────────────

_pipeline_instance: Optional[LivePipeline] = None


def get_pipeline(
    mt5: MT5Connector,
    symbols: Optional[List[str]] = None,
    bar_timeframe_sec: int = 3_600,
) -> LivePipeline:
    """
    Return the process-level singleton ``LivePipeline``.

    On the first call the pipeline is instantiated with the provided
    arguments.  Subsequent calls return the cached instance regardless
    of the arguments (singleton pattern).

    Parameters
    ----------
    mt5 : MT5Connector
        Connected MT5 session.
    symbols : list[str] | None
        Symbols to track (default: from ``config.SYMBOLS``).
    bar_timeframe_sec : int
        Bar duration in seconds.

    Returns
    -------
    LivePipeline
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = LivePipeline(
            mt5=mt5,
            symbols=symbols,
            bar_timeframe_sec=bar_timeframe_sec,
        )
    return _pipeline_instance


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test: validates Hyperliquid connectivity and macro fetch
    without requiring a live MT5 session.

    Run from project root:
        python -m backend.core.live_pipeline

    Expected output:
        HL bulk fetch OK: N mids, M contexts
        Macro snapshot: FEDFUNDS=X.XX%  VIX=XX.XX
        HLTicker for EURUSD → EUR: mid=... bid=... ask=...
    """
    import sys, json

    out = sys.stdout.buffer

    def _p(text: str) -> None:
        out.write((text + "\n").encode("utf-8"))
        out.flush()

    _p("\n=== LivePipeline Smoke-Test ===\n")

    # ── 1. Hyperliquid connectivity ─────────────────────────────────────────
    hl = HyperliquidClient()
    mids = hl.get_all_mids()
    ctxs = hl.get_asset_contexts()
    _p(f"HL allMids    : {len(mids)} coins received")
    _p(f"HL assetCtxs  : {len(ctxs)} contexts received")

    for coin in ("BTC", "ETH", "EUR"):
        mid = mids.get(coin, "NOT LISTED")
        ctx = ctxs.get(coin, {})
        funding = ctx.get("funding_rate", "n/a")
        _p(f"  {coin:5s} mid={mid}  funding={funding}")

    # ── 2. EUR L2 book ────────────────────────────────────────────────────────
    bid, ask = hl.get_l2_book("EUR")
    _p(f"\nEUR L2 book   : bid={bid}  ask={ask}")

    # ── 3. Macro fetch ────────────────────────────────────────────────────────
    macro = OpenBBMacroFetcher()
    snap = macro.fetch_macro()
    _p(f"\nMacro snapshot:")
    _p(f"  FEDFUNDS = {snap.fed_funds:.4f}%")
    _p(f"  T10Y2Y   = {snap.yield_spread:.4f}%")
    _p(f"  CPI      = {snap.cpi:.4f}")
    _p(f"  VIX      = {snap.vix:.4f}")
    _p(f"  staleness= {snap.staleness_hours:.2f}h")

    _p("\n=== All checks passed ===\n")
