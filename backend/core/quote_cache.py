"""
==============================================================
backend/core/quote_cache.py — Antigravity Live Quote Cache
==============================================================
SQLite-backed caching layer for live bid/ask tick data.

Why this exists
---------------
Both the MT5 terminal bridge and the Hyperliquid WebSocket feed can be
rate-limited or intermittently unavailable.  This module provides a
transparent write-through / read-on-miss cache so that:

* Every consumer reads from the local cache first (μs latency).
* A cache miss triggers a live fetch **and** a cache write.
* Stale records older than ``ttl_seconds`` are never returned to callers.
* A background vacuum routine prevents unbounded DB growth.

Database layout
---------------
Table: ``quotes``

    Column          Type       Description
    ──────────────  ─────────  ─────────────────────────────────────────────
    id              INTEGER    Auto-increment PK
    symbol          TEXT       MT5 ticker (e.g. "EURUSD")
    hl_coin         TEXT       Hyperliquid coin code (e.g. "EUR"); nullable
    bid             REAL       Bid price
    ask             REAL       Ask price
    mid             REAL       (bid + ask) / 2
    spread_raw      REAL       ask - bid (in price units)
    volume          REAL       Tick volume (0 when not available)
    source          TEXT       "MT5" | "HL" | "YFINANCE" | "MANUAL"
    captured_at     REAL       UNIX timestamp of the original tick
    cached_at       REAL       UNIX timestamp when this row was written

Indices: ``(symbol, cached_at)`` — covering index for TTL-filtered lookups.

Thread-safety
-------------
SQLite's WAL mode is enabled at creation time. Each method acquires a
per-instance threading lock before executing SQL, so the cache is safe
to use from multiple threads within the same process.

Usage
-----
    from backend.core.quote_cache import QuoteCache, LiveQuote

    cache = QuoteCache()         # uses CACHE_DB_PATH from settings

    # Write a tick received from MT5
    quote = LiveQuote(symbol="EURUSD", bid=1.08520, ask=1.08535, source="MT5")
    cache.set(quote)

    # Read back (returns None if expired / absent)
    q = cache.get("EURUSD")
    if q:
        print(q.mid)

    # Bulk read
    quotes = cache.get_many(["EURUSD", "GBPUSD"])

    # Expire & vacuum old rows
    cache.vacuum()
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Generator, Iterator, List, Optional, Sequence

from loguru import logger

# ── Project settings (optional dependency — falls back to sane defaults) ──────
try:
    from config.settings import settings as _settings  # type: ignore

    _DEFAULT_DB_PATH: str = str(_settings.resolved_cache_db_path())
    _DEFAULT_TTL: int = _settings.CACHE_TTL_SECONDS
except Exception:
    # Fallback: store DB in the data_layer/cache directory relative to project root
    _DEFAULT_DB_PATH = str(
        Path(__file__).resolve().parents[3] / "data_layer" / "cache" / "quotes.db"
    )
    _DEFAULT_TTL = 30  # seconds — short default for live-tick freshness

# ─────────────────────────────────────────────────────────────────────────────
# Schema DDL
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_QUOTES_TABLE: str = """
CREATE TABLE IF NOT EXISTS quotes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    hl_coin     TEXT,
    bid         REAL    NOT NULL,
    ask         REAL    NOT NULL,
    mid         REAL    NOT NULL,
    spread_raw  REAL    NOT NULL,
    volume      REAL    NOT NULL DEFAULT 0,
    source      TEXT    NOT NULL DEFAULT 'UNKNOWN',
    captured_at REAL    NOT NULL,
    cached_at   REAL    NOT NULL
);
"""

_CREATE_INDEX: str = """
CREATE INDEX IF NOT EXISTS idx_quotes_symbol_cached
    ON quotes (symbol, cached_at DESC);
"""

_UPSERT_QUOTE: str = """
INSERT INTO quotes
    (symbol, hl_coin, bid, ask, mid, spread_raw, volume, source, captured_at, cached_at)
VALUES
    (:symbol, :hl_coin, :bid, :ask, :mid, :spread_raw, :volume, :source, :captured_at, :cached_at);
"""

_SELECT_LATEST: str = """
SELECT symbol, hl_coin, bid, ask, mid, spread_raw, volume, source, captured_at, cached_at
FROM   quotes
WHERE  symbol   = :symbol
AND    cached_at > :min_cached_at
ORDER  BY cached_at DESC
LIMIT  1;
"""

_SELECT_MANY: str = """
SELECT symbol, hl_coin, bid, ask, mid, spread_raw, volume, source, captured_at, cached_at
FROM   quotes
WHERE  symbol   IN ({placeholders})
AND    cached_at > :min_cached_at
GROUP  BY symbol
HAVING cached_at = MAX(cached_at);
"""

_DELETE_EXPIRED: str = """
DELETE FROM quotes
WHERE cached_at <= :cutoff;
"""

_COUNT_ALL: str = "SELECT COUNT(*) FROM quotes;"


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class LiveQuote:
    """
    Immutable representation of a single live bid/ask tick.

    Parameters
    ----------
    symbol : str
        MT5 ticker name (e.g. ``"EURUSD"``).
    bid : float
        Bid price from the market feed.
    ask : float
        Ask price from the market feed.
    hl_coin : str | None
        Corresponding Hyperliquid coin code; ``None`` when not mapped.
    volume : float
        Tick volume as reported by the source; 0 when unavailable.
    source : str
        Origin tag: ``"MT5"``, ``"HL"``, ``"YFINANCE"``, or ``"MANUAL"``.
    captured_at : float
        UNIX timestamp of the original market tick.
        Defaults to ``time.time()`` at object creation.
    cached_at : float
        UNIX timestamp when this record was stored.
        Set automatically by ``QuoteCache.set()``.
    """

    symbol: str
    bid: float
    ask: float
    hl_coin: Optional[str] = None
    volume: float = 0.0
    source: str = "UNKNOWN"
    captured_at: float = field(default_factory=time.time)
    cached_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Validate bid/ask ordering and compute derived fields."""
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError(
                f"LiveQuote({self.symbol!r}): bid and ask must be positive; "
                f"got bid={self.bid}, ask={self.ask}."
            )
        if self.bid > self.ask:
            raise ValueError(
                f"LiveQuote({self.symbol!r}): bid ({self.bid}) > ask ({self.ask}). "
                f"Inverted market data is invalid."
            )

    @property
    def mid(self) -> float:
        """Midpoint price: ``(bid + ask) / 2``."""
        return (self.bid + self.ask) / 2.0

    @property
    def spread_raw(self) -> float:
        """Raw spread in price units: ``ask - bid``."""
        return self.ask - self.bid

    def spread_pips(self, pip_size: float = 0.0001) -> float:
        """
        Spread converted to pips.

        Parameters
        ----------
        pip_size : float
            One pip in price units (0.0001 for most pairs, 0.01 for JPY).

        Returns
        -------
        float
            Spread in pips, rounded to one decimal.
        """
        if pip_size <= 0:
            raise ValueError("pip_size must be positive.")
        return round(self.spread_raw / pip_size, 1)

    def to_dict(self) -> dict:
        """Serialise all fields to a plain dict (JSON-safe)."""
        return {
            "symbol": self.symbol,
            "hl_coin": self.hl_coin,
            "bid": self.bid,
            "ask": self.ask,
            "mid": round(self.mid, 8),
            "spread_raw": round(self.spread_raw, 8),
            "volume": self.volume,
            "source": self.source,
            "captured_at": self.captured_at,
            "cached_at": self.cached_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "LiveQuote":
        """
        Reconstruct a ``LiveQuote`` from a ``sqlite3.Row`` fetched from the
        ``quotes`` table.

        Parameters
        ----------
        row : sqlite3.Row
            A row with columns matching the ``quotes`` DDL.

        Returns
        -------
        LiveQuote
        """
        return cls(
            symbol=row["symbol"],
            bid=row["bid"],
            ask=row["ask"],
            hl_coin=row["hl_coin"],
            volume=row["volume"],
            source=row["source"],
            captured_at=row["captured_at"],
            cached_at=row["cached_at"],
        )


@dataclass
class CacheStats:
    """
    Snapshot of current QuoteCache health metrics.

    Attributes
    ----------
    total_rows : int
        Total rows stored (including expired but not yet vacuumed).
    live_symbols : int
        Number of distinct symbols with at least one non-expired row.
    db_size_bytes : int
        Physical size of the SQLite database file on disk.
    ttl_seconds : int
        Configured TTL used to determine staleness.
    last_vacuum_at : float | None
        UNIX timestamp of the last successful vacuum run.
    """

    total_rows: int
    live_symbols: int
    db_size_bytes: int
    ttl_seconds: int
    last_vacuum_at: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# QuoteCache
# ─────────────────────────────────────────────────────────────────────────────


class QuoteCache:
    """
    Thread-safe SQLite write-through cache for live market quotes.

    Parameters
    ----------
    db_path : str | Path | None
        Filesystem path for the SQLite database file.  Defaults to
        ``CACHE_DB_PATH`` from project settings.
    ttl_seconds : int
        How long a cached quote is considered fresh.  Reads older than
        this threshold return ``None``.  Defaults to ``CACHE_TTL_SECONDS``
        from project settings (or 30 s as a safe fallback).
    vacuum_interval_sec : int
        How often the auto-vacuum background job runs (seconds).
        Set to 0 to disable automatic vacuuming.
    """

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        ttl_seconds: int = _DEFAULT_TTL,
        vacuum_interval_sec: int = 300,
    ) -> None:
        # Resolve DB path
        path = Path(db_path) if db_path else Path(_DEFAULT_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path: Path = path

        self._ttl: int = max(1, ttl_seconds)
        self._vacuum_interval: int = max(0, vacuum_interval_sec)
        self._last_vacuum: float = 0.0
        self._lock = threading.Lock()

        self._initialise_db()
        logger.info(
            f"QuoteCache ready | db={self._db_path} | ttl={self._ttl}s"
        )

    # ── Connection context manager ─────────────────────────────────────────────

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Yield a thread-local SQLite connection in WAL mode.

        Using ``check_same_thread=False`` is safe here because the
        ``threading.Lock`` prevents concurrent access.
        """
        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10,
        )
        conn.row_factory = sqlite3.Row
        # Enable WAL for better concurrent read performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Schema initialisation ─────────────────────────────────────────────────

    def _initialise_db(self) -> None:
        """Create the schema if it does not already exist."""
        with self._lock, self._connect() as conn:
            conn.execute(_CREATE_QUOTES_TABLE)
            conn.execute(_CREATE_INDEX)
        logger.debug(f"QuoteCache schema verified | {self._db_path}")

    # ── Write operations ──────────────────────────────────────────────────────

    def set(self, quote: LiveQuote) -> None:
        """
        Write a ``LiveQuote`` into the cache.

        The ``cached_at`` timestamp is always overwritten with the current
        time so that TTL calculations are based on *storage time*, not on
        the original tick time.

        Parameters
        ----------
        quote : LiveQuote
            The tick to persist.

        Raises
        ------
        sqlite3.Error
            On any database write failure.
        """
        now = time.time()
        params = {
            "symbol": quote.symbol,
            "hl_coin": quote.hl_coin,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": quote.mid,
            "spread_raw": quote.spread_raw,
            "volume": quote.volume,
            "source": quote.source,
            "captured_at": quote.captured_at,
            "cached_at": now,
        }
        with self._lock, self._connect() as conn:
            conn.execute(_UPSERT_QUOTE, params)
        logger.debug(
            f"QuoteCache.set | {quote.symbol} | "
            f"bid={quote.bid} ask={quote.ask} | src={quote.source}"
        )
        self._maybe_vacuum()

    def set_many(self, quotes: Sequence[LiveQuote]) -> int:
        """
        Bulk-write multiple quotes in a single transaction.

        Parameters
        ----------
        quotes : Sequence[LiveQuote]
            Quotes to persist.  An empty sequence is a no-op.

        Returns
        -------
        int
            Number of rows written.
        """
        if not quotes:
            return 0
        now = time.time()
        rows = [
            {
                "symbol": q.symbol,
                "hl_coin": q.hl_coin,
                "bid": q.bid,
                "ask": q.ask,
                "mid": q.mid,
                "spread_raw": q.spread_raw,
                "volume": q.volume,
                "source": q.source,
                "captured_at": q.captured_at,
                "cached_at": now,
            }
            for q in quotes
        ]
        with self._lock, self._connect() as conn:
            conn.executemany(_UPSERT_QUOTE, rows)
        logger.debug(f"QuoteCache.set_many | {len(rows)} rows written")
        self._maybe_vacuum()
        return len(rows)

    # ── Read operations ───────────────────────────────────────────────────────

    def get(self, symbol: str) -> Optional[LiveQuote]:
        """
        Return the freshest cached quote for ``symbol`` that is still
        within the TTL window.

        Parameters
        ----------
        symbol : str
            MT5 ticker name (e.g. ``"EURUSD"``).

        Returns
        -------
        LiveQuote | None
            ``None`` when no non-expired record exists.
        """
        min_ts = time.time() - self._ttl
        with self._lock, self._connect() as conn:
            row = conn.execute(
                _SELECT_LATEST,
                {"symbol": symbol, "min_cached_at": min_ts},
            ).fetchone()
        if row is None:
            logger.debug(f"QuoteCache.get | MISS | {symbol}")
            return None
        logger.debug(
            f"QuoteCache.get | HIT  | {symbol} | "
            f"age={(time.time() - row['cached_at']):.1f}s"
        )
        return LiveQuote.from_row(row)

    def get_many(self, symbols: Sequence[str]) -> Dict[str, LiveQuote]:
        """
        Bulk-read the freshest non-expired quotes for a list of symbols.

        Parameters
        ----------
        symbols : Sequence[str]
            MT5 tickers to fetch.

        Returns
        -------
        dict[str, LiveQuote]
            Only symbols that had a fresh cache hit are included.
        """
        if not symbols:
            return {}

        min_ts = time.time() - self._ttl
        placeholders = ",".join("?" * len(symbols))
        sql = _SELECT_MANY.format(placeholders=placeholders)

        params: list = list(symbols) + [min_ts]
        # Rebuild query with positional params (no named `:min_cached_at` mixing)
        sql_positional = f"""
            SELECT symbol, hl_coin, bid, ask, mid, spread_raw, volume,
                   source, captured_at, cached_at
            FROM   quotes
            WHERE  symbol   IN ({placeholders})
            AND    cached_at > ?
            GROUP  BY symbol
            HAVING cached_at = MAX(cached_at);
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql_positional, params).fetchall()

        result: Dict[str, LiveQuote] = {
            row["symbol"]: LiveQuote.from_row(row) for row in rows
        }
        hits = len(result)
        misses = len(symbols) - hits
        logger.debug(
            f"QuoteCache.get_many | {hits} hits / {misses} misses | "
            f"symbols={list(symbols)}"
        )
        return result

    def get_all_live(self) -> List[LiveQuote]:
        """
        Return the latest non-expired quote for every symbol currently in
        the cache.

        Returns
        -------
        list[LiveQuote]
            Ordered by ``symbol`` ascending.
        """
        min_ts = time.time() - self._ttl
        sql = """
            SELECT symbol, hl_coin, bid, ask, mid, spread_raw, volume,
                   source, captured_at, cached_at
            FROM   quotes
            WHERE  cached_at > ?
            GROUP  BY symbol
            HAVING cached_at = MAX(cached_at)
            ORDER  BY symbol ASC;
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, (min_ts,)).fetchall()
        return [LiveQuote.from_row(r) for r in rows]

    # ── Maintenance ───────────────────────────────────────────────────────────

    def vacuum(self, max_age_sec: Optional[int] = None) -> int:
        """
        Delete all rows older than ``max_age_sec`` seconds from the DB.

        This prevents unbounded table growth in long-running deployments.
        Note: SQLite's file does not automatically shrink after DELETE;
        call ``VACUUM`` on a maintenance schedule to reclaim disk space.

        Parameters
        ----------
        max_age_sec : int | None
            Rows with ``cached_at`` older than this are deleted.
            Defaults to ``2 * ttl_seconds`` (keep two TTL windows of history).

        Returns
        -------
        int
            Number of rows deleted.
        """
        cutoff = time.time() - (max_age_sec if max_age_sec else 2 * self._ttl)
        with self._lock, self._connect() as conn:
            cur = conn.execute(_DELETE_EXPIRED, {"cutoff": cutoff})
            deleted = cur.rowcount
        self._last_vacuum = time.time()
        if deleted:
            logger.info(f"QuoteCache vacuum | {deleted} expired rows removed")
        return deleted

    def stats(self) -> CacheStats:
        """
        Return a snapshot of current cache health metrics.

        Returns
        -------
        CacheStats
        """
        min_ts = time.time() - self._ttl
        with self._lock, self._connect() as conn:
            total = conn.execute(_COUNT_ALL).fetchone()[0]
            live = conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM quotes WHERE cached_at > ?",
                (min_ts,),
            ).fetchone()[0]

        db_size = self._db_path.stat().st_size if self._db_path.is_file() else 0
        return CacheStats(
            total_rows=total,
            live_symbols=live,
            db_size_bytes=db_size,
            ttl_seconds=self._ttl,
            last_vacuum_at=self._last_vacuum or None,
        )

    def clear(self) -> int:
        """
        **Destructive**: delete ALL rows from the quotes table.

        Returns
        -------
        int
            Total rows removed.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM quotes;")
            deleted = cur.rowcount
        logger.warning(f"QuoteCache.clear() | {deleted} rows purged")
        return deleted

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _maybe_vacuum(self) -> None:
        """
        Trigger an auto-vacuum if ``vacuum_interval_sec`` has elapsed since
        the last vacuum run.  Called after every ``set`` / ``set_many``.
        """
        if self._vacuum_interval <= 0:
            return
        if (time.time() - self._last_vacuum) >= self._vacuum_interval:
            deleted = self.vacuum()
            logger.debug(f"Auto-vacuum | {deleted} rows cleaned")

    # ── Context manager protocol ──────────────────────────────────────────────

    def __enter__(self) -> "QuoteCache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Nothing to teardown — SQLite connections are closed per-operation.
        pass

    def __repr__(self) -> str:
        return (
            f"QuoteCache(db={self._db_path.name!r}, ttl={self._ttl}s)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

_quote_cache: Optional[QuoteCache] = None


def get_quote_cache(
    db_path: Optional[str | Path] = None,
    ttl_seconds: int = _DEFAULT_TTL,
    vacuum_interval_sec: int = 300,
) -> QuoteCache:
    """
    Return the process-level singleton ``QuoteCache``.

    Parameters are forwarded to ``QuoteCache.__init__`` **only on the
    first call** — subsequent calls return the cached instance unchanged.

    Returns
    -------
    QuoteCache
    """
    global _quote_cache
    if _quote_cache is None:
        _quote_cache = QuoteCache(
            db_path=db_path,
            ttl_seconds=ttl_seconds,
            vacuum_interval_sec=vacuum_interval_sec,
        )
    return _quote_cache


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test — writes two quotes, reads them back, prints stats.

    Run from project root:
        python -m backend.core.quote_cache
    """
    import tempfile, json

    with tempfile.TemporaryDirectory() as tmp:
        cache = QuoteCache(db_path=Path(tmp) / "test_quotes.db", ttl_seconds=60)

        # Write
        q1 = LiveQuote("EURUSD", bid=1.08500, ask=1.08515, source="MT5", hl_coin="EUR")
        q2 = LiveQuote("BTCUSD", bid=67_250.0, ask=67_255.0, source="HL", hl_coin="BTC")
        q3 = LiveQuote("XAUUSD", bid=2_320.50, ask=2_321.10, source="YFINANCE", hl_coin="XAU")
        cache.set_many([q1, q2, q3])

        # Read
        hit = cache.get("EURUSD")
        miss = cache.get("UNKNOWN")

        assert hit is not None, "Expected cache HIT for EURUSD"
        assert miss is None, "Expected cache MISS for UNKNOWN"

        bulk = cache.get_many(["EURUSD", "BTCUSD", "MISSING"])
        assert len(bulk) == 2, f"Expected 2 hits, got {len(bulk)}"

        # Stats
        st = cache.stats()
        # ── Print results using explicit UTF-8 to avoid Windows cp125x issues ──
        import sys
        out = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else None

        def _print(text: str) -> None:
            if out:
                out.write((text + "\n").encode("utf-8"))
                out.flush()
            else:
                print(text)

        _print("\n QuoteCache Smoke-Test  [PASS]")
        _print(f"  total_rows     = {st.total_rows}")
        _print(f"  live_symbols   = {st.live_symbols}")
        _print(f"  db_size_bytes  = {st.db_size_bytes}")
        _print(f"  EURUSD mid     = {hit.mid:.5f}")
        _print(f"  EURUSD spread  = {hit.spread_pips():.1f} pips")
        _print(f"  All live:")
        for q in cache.get_all_live():
            _print(f"    {json.dumps(q.to_dict(), indent=4)}")
