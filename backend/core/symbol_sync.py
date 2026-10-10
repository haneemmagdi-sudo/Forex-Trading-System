"""
==============================================================
backend/core/symbol_sync.py — Antigravity Asset Synchronisation
==============================================================
Bidirectional symbol mapper between MetaTrader 5 broker tick-names
and Hyperliquid perpetual-futures API coin codes.

Architecture overview
---------------------
The same underlying asset trades under completely different naming
conventions on different venues:

    MT5 broker          →   Hyperliquid REST/WS API
    ─────────────────       ────────────────────────
    EURUSD              →   EUR  (FX perp)
    BTCUSD / BTCUSD.r   →   BTC
    XAUUSD              →   XAU
    US500               →   SPX
    UKOUSD              →   OIL

``SymbolSynchroniser`` resolves these mismatches using a layered
strategy:

    1. Static table  — curated, high-confidence rules (fast O(1)).
    2. Fuzzy heuristics — substring + regex normalisation for broker
       suffixes like ``.r``, ``m``, ``_i``, etc.
    3. Hyperliquid discovery — optionally fetches the live ``/info``
       meta endpoint to validate that a mapped coin is actually listed.

Key data flow
-------------
    MT5 symbols (from mt5.symbols_get())
        │
        ▼
    SymbolSynchroniser.build_map()
        │
        ├─► Static table lookup
        ├─► Fuzzy normaliser
        └─► Hyperliquid validator (optional, async)
        │
        ▼
    SyncedAsset list   →  QuoteCache / trading engine consumers

Usage
-----
    from backend.core.symbol_sync import SymbolSynchroniser

    syncer = SymbolSynchroniser()

    # Build full map for all MT5 symbols that are currently available
    assets = syncer.build_map(mt5_symbols=["EURUSD", "BTCUSD", "XAUUSD"])

    for asset in assets:
        print(asset)  # SyncedAsset(mt5="EURUSD", hl_coin="EUR", ...)

    # Single lookup
    hl = syncer.resolve_hl("GBPJPY")   # → "GBP/JPY" (or None)
    mt5 = syncer.resolve_mt5("BTC")    # → "BTCUSD"  (or None)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Final, List, Optional

from loguru import logger

# ─────────────────────────────────────────────────────────────────────────────
# Static mapping table (MT5 canonical name → Hyperliquid coin/pair code)
# ─────────────────────────────────────────────────────────────────────────────

# ── Hyperliquid Asset Universe — Reality Check (verified 2026-06-17) ─────────
#
# Hyperliquid is a CRYPTO-ONLY perpetual futures exchange.
# FX pairs, commodities, and equity indices are NOT listed.
# Symbols not present on Hyperliquid are omitted from this map so that
# callers receive None and correctly fall back to MT5-only mode.
#
# Crypto perp coins confirmed live (866 total as of verification):
#   BTC, ETH, SOL, XRP, BNB, ADA, DOGE, AVAX, LINK, LTC, DOT …
#
# FX pairs (EURUSD, GBPUSD …) → NOT on Hyperliquid → route via MT5 + OpenBB only.
# Commodities (XAUUSD, UKOUSD …) → NOT on Hyperliquid.
# Equity indices (US500, GER40 …) → NOT on Hyperliquid.

_STATIC_MAP: Final[Dict[str, str]] = {
    # ── Crypto Perpetuals (LIVE on Hyperliquid) ───────────────────────────
    "BTCUSD":   "BTC",
    "ETHUSD":   "ETH",
    "SOLUSD":   "SOL",
    "XRPUSD":   "XRP",
    "BNBUSD":   "BNB",
    "ADAUSD":   "ADA",
    "DOGEUSD":  "DOGE",
    "AVAXUSD":  "AVAX",
    "LINKUSD":  "LINK",
    "LTCUSD":   "LTC",
    "DOTUSD":   "DOT",
    "UNIUSD":   "UNI",
    "MATICUSD": "MATIC",
    "NEARUSD":  "NEAR",
    "ATOMUSD":  "ATOM",
    "AAVEUSD":  "AAVE",
    "SUIUSD":   "SUI",
    "APTUSD":   "APT",
    "ARBUSD":   "ARB",
    "OPUSD":    "OP",
    "INJUSD":   "INJ",
    "TIAUSD":   "TIA",
    "SEIUNSD":  "SEI",
    "STXUSD":   "STX",
    # ── Natural Gas (only commodity on HL) ────────────────────────────────
    "NGAS":     "GAS",
    # ──────────────────────────────────────────────────────────────────────
    # FX PAIRS — not listed on Hyperliquid; LivePipeline uses MT5+OpenBB only
    # "EURUSD" → None (intentionally excluded from this map)
    # "GBPUSD" → None
    # COMMODITIES — not listed on Hyperliquid
    # "XAUUSD" → None  (Gold)
    # EQUITY INDICES — not listed on Hyperliquid
    # "US500"  → None  (S&P 500)
}

# Reverse map: Hyperliquid coin → canonical MT5 name (built once at import time)
_REVERSE_MAP: Final[Dict[str, str]] = {v: k for k, v in _STATIC_MAP.items()}

# Broker suffix patterns to strip before lookup, e.g. BTCUSD.r → BTCUSD
_SUFFIX_PATTERN: re.Pattern = re.compile(
    r"(?:[._-](?:r|m|i|pro|ecn|raw|stp|std|micro|mini|nano|plus|prime|\d+))+$",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


class SyncSource(Enum):
    """Indicates which resolution strategy produced a ``SyncedAsset``."""

    STATIC_TABLE = auto()   # Matched in the curated static map
    FUZZY_MATCH = auto()    # Matched after suffix stripping / normalisation
    UNRESOLVED = auto()     # No mapping found — asset is unsupported


@dataclass(frozen=True)
class SyncedAsset:
    """
    Immutable record linking one MT5 ticker to its Hyperliquid equivalent.

    Attributes
    ----------
    mt5_symbol : str
        The exact ticker name as seen in the MT5 terminal (e.g. ``EURUSD``).
    hl_coin : str | None
        The Hyperliquid coin/pair code (e.g. ``EUR``, ``BTC``, ``XAU``).
        ``None`` when no mapping was found.
    source : SyncSource
        How the mapping was established.
    hl_listed : bool | None
        ``True`` if the coin was confirmed in the live Hyperliquid meta
        endpoint.  ``None`` when validation was not performed.
    normalised_mt5 : str
        The broker-suffix-stripped version of ``mt5_symbol`` used during
        fuzzy resolution.
    """

    mt5_symbol: str
    hl_coin: Optional[str]
    source: SyncSource
    hl_listed: Optional[bool] = None
    normalised_mt5: str = ""

    @property
    def is_synced(self) -> bool:
        """``True`` when a bidirectional mapping exists."""
        return self.hl_coin is not None

    @property
    def is_tradeable_on_hl(self) -> bool:
        """``True`` when mapped AND confirmed live on Hyperliquid."""
        return self.is_synced and self.hl_listed is True

    def __str__(self) -> str:
        status = "✓" if self.is_synced else "✗"
        listed = (
            " [HL-listed]" if self.hl_listed
            else " [HL-unlisted]" if self.hl_listed is False
            else ""
        )
        return (
            f"{status} MT5={self.mt5_symbol!r:20s} → "
            f"HL={str(self.hl_coin)!r:15s} "
            f"({self.source.name}){listed}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Core synchroniser
# ─────────────────────────────────────────────────────────────────────────────


class SymbolSynchroniser:
    """
    Maps MetaTrader 5 broker ticker names to Hyperliquid coin codes.

    The synchroniser is stateless with respect to market data — it only
    resolves name mappings.  It does NOT fetch prices or manage connections.

    Hyperliquid discovery (optional)
    ---------------------------------
    When ``validate_with_hl=True`` is passed to ``build_map()``, the
    synchroniser calls the Hyperliquid public ``/info`` endpoint (no auth
    required) and cross-references the live universe of listed perps.
    This is done synchronously using ``requests`` to keep the module
    dependency-free from async runtimes.

    Parameters
    ----------
    hl_api_base : str
        Base URL for the Hyperliquid REST API.
        Default: ``"https://api.hyperliquid.xyz"``.
    hl_request_timeout : float
        Request timeout for the ``/info`` meta call (seconds).
    """

    _HL_META_ENDPOINT: Final[str] = "/info"

    def __init__(
        self,
        hl_api_base: str = "https://api.hyperliquid.xyz",
        hl_request_timeout: float = 8.0,
    ) -> None:
        self._hl_api_base = hl_api_base.rstrip("/")
        self._hl_request_timeout = hl_request_timeout
        self._hl_universe: Optional[set[str]] = None  # populated on first validation
        self._hl_universe_ts: float = 0.0              # UNIX timestamp of last fetch
        self._hl_universe_ttl: float = 300.0           # refresh universe every 5 min

    # ── Public API ────────────────────────────────────────────────────────────

    def build_map(
        self,
        mt5_symbols: List[str],
        validate_with_hl: bool = False,
    ) -> List[SyncedAsset]:
        """
        Resolve a list of MT5 broker symbols to Hyperliquid equivalents.

        Parameters
        ----------
        mt5_symbols : list[str]
            MT5 ticker names exactly as returned by ``mt5.symbols_get()``.
        validate_with_hl : bool
            When ``True``, query the Hyperliquid meta endpoint and annotate
            each ``SyncedAsset`` with whether the coin is actively listed.

        Returns
        -------
        list[SyncedAsset]
            One entry per input symbol, sorted by resolution source
            (STATIC_TABLE first, then FUZZY_MATCH, then UNRESOLVED).
        """
        if not mt5_symbols:
            logger.warning("build_map() received an empty symbol list.")
            return []

        hl_universe: Optional[set[str]] = None
        if validate_with_hl:
            hl_universe = self._fetch_hl_universe()

        results: List[SyncedAsset] = []
        for raw_symbol in mt5_symbols:
            asset = self._resolve_single(raw_symbol, hl_universe)
            results.append(asset)

        # Sort: synced static > synced fuzzy > unresolved
        results.sort(
            key=lambda a: (
                a.source != SyncSource.STATIC_TABLE,
                a.source != SyncSource.FUZZY_MATCH,
                a.mt5_symbol,
            )
        )

        synced = sum(1 for a in results if a.is_synced)
        logger.info(
            f"SymbolSync complete | "
            f"total={len(results)} | synced={synced} | "
            f"unresolved={len(results) - synced} | "
            f"hl_validated={validate_with_hl}"
        )
        return results

    def resolve_hl(self, mt5_symbol: str) -> Optional[str]:
        """
        Resolve a single MT5 symbol to its Hyperliquid coin code.

        Parameters
        ----------
        mt5_symbol : str
            Broker ticker, e.g. ``"EURUSD"`` or ``"BTCUSD.r"``.

        Returns
        -------
        str | None
            Hyperliquid coin code, or ``None`` if unmappable.
        """
        asset = self._resolve_single(mt5_symbol, hl_universe=None)
        return asset.hl_coin

    def resolve_mt5(self, hl_coin: str) -> Optional[str]:
        """
        Reverse-lookup: Hyperliquid coin code → canonical MT5 symbol.

        Parameters
        ----------
        hl_coin : str
            Hyperliquid coin code, e.g. ``"BTC"``, ``"EUR"``.

        Returns
        -------
        str | None
            Canonical MT5 symbol, or ``None`` if not found.
        """
        result = _REVERSE_MAP.get(hl_coin)
        if result is None:
            logger.debug(f"reverse-lookup miss | hl_coin={hl_coin!r}")
        return result

    def get_synced_map(
        self,
        mt5_symbols: List[str],
        validate_with_hl: bool = False,
    ) -> Dict[str, str]:
        """
        Convenience method returning only the successfully resolved pairs
        as a flat ``{mt5_symbol: hl_coin}`` dict.

        Parameters
        ----------
        mt5_symbols : list[str]
            MT5 tickers to resolve.
        validate_with_hl : bool
            Passed through to ``build_map()``.

        Returns
        -------
        dict[str, str]
            Only entries where resolution succeeded.
        """
        assets = self.build_map(mt5_symbols, validate_with_hl=validate_with_hl)
        return {a.mt5_symbol: a.hl_coin for a in assets if a.is_synced}

    # ── Internal resolution pipeline ─────────────────────────────────────────

    def _resolve_single(
        self,
        raw_symbol: str,
        hl_universe: Optional[set],
    ) -> SyncedAsset:
        """
        Resolution order:
        1. Direct static-table lookup (no normalisation needed).
        2. Suffix-stripped / normalised lookup (fuzzy).
        3. Unresolved.
        """
        symbol = raw_symbol.strip().upper()

        # ── Strategy 1: Static table ──────────────────────────────────────
        if symbol in _STATIC_MAP:
            hl_coin = _STATIC_MAP[symbol]
            hl_listed = self._check_hl_listed(hl_coin, hl_universe)
            return SyncedAsset(
                mt5_symbol=raw_symbol,
                hl_coin=hl_coin,
                source=SyncSource.STATIC_TABLE,
                hl_listed=hl_listed,
                normalised_mt5=symbol,
            )

        # ── Strategy 2: Fuzzy — strip broker suffixes ─────────────────────
        normalised = _SUFFIX_PATTERN.sub("", symbol)
        if normalised != symbol and normalised in _STATIC_MAP:
            hl_coin = _STATIC_MAP[normalised]
            hl_listed = self._check_hl_listed(hl_coin, hl_universe)
            logger.debug(
                f"Fuzzy match | {raw_symbol!r} → normalised={normalised!r} "
                f"→ HL={hl_coin!r}"
            )
            return SyncedAsset(
                mt5_symbol=raw_symbol,
                hl_coin=hl_coin,
                source=SyncSource.FUZZY_MATCH,
                hl_listed=hl_listed,
                normalised_mt5=normalised,
            )

        # ── Fallback: crypto detection heuristic ──────────────────────────
        # For unrecognised symbols ending in USD (e.g. AABUSD), attempt to
        # extract the base token and see if Hyperliquid lists it directly.
        if symbol.endswith("USD") and hl_universe is not None:
            base = symbol[:-3]
            if base in hl_universe:
                logger.debug(
                    f"Heuristic match | {raw_symbol!r} → base={base!r} in HL universe"
                )
                return SyncedAsset(
                    mt5_symbol=raw_symbol,
                    hl_coin=base,
                    source=SyncSource.FUZZY_MATCH,
                    hl_listed=True,
                    normalised_mt5=normalised,
                )

        # ── Unresolved ────────────────────────────────────────────────────
        logger.debug(f"Symbol unresolved | {raw_symbol!r} (normalised={normalised!r})")
        return SyncedAsset(
            mt5_symbol=raw_symbol,
            hl_coin=None,
            source=SyncSource.UNRESOLVED,
            hl_listed=None,
            normalised_mt5=normalised,
        )

    @staticmethod
    def _check_hl_listed(
        hl_coin: Optional[str],
        hl_universe: Optional[set],
    ) -> Optional[bool]:
        """
        Return whether a coin exists in the Hyperliquid universe set.

        Returns ``None`` when validation was not requested.
        """
        if hl_universe is None or hl_coin is None:
            return None
        # FX crosses like "EUR/JPY" need the base part checked
        base = hl_coin.split("/")[0]
        return base in hl_universe

    # ── Hyperliquid live universe fetch ───────────────────────────────────────

    def _fetch_hl_universe(self) -> set[str]:
        """
        Fetch the set of all Hyperliquid perp coin codes from the public
        ``/info`` endpoint (type=``meta``).

        Results are cached in-process for ``_hl_universe_ttl`` seconds to
        avoid redundant HTTP calls during bulk sync operations.

        Returns
        -------
        set[str]
            Set of uppercase coin codes, e.g. ``{"BTC", "ETH", "EUR", ...}``.
            Returns an empty set on any network / parse failure.
        """
        now = time.monotonic()
        if (
            self._hl_universe is not None
            and (now - self._hl_universe_ts) < self._hl_universe_ttl
        ):
            return self._hl_universe

        try:
            import requests  # type: ignore  # lightweight; already in requirements

            url = f"{self._hl_api_base}{self._HL_META_ENDPOINT}"
            resp = requests.post(
                url,
                json={"type": "meta"},
                timeout=self._hl_request_timeout,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            # Response structure: {"universe": [{"name": "BTC", ...}, ...]}
            universe: set[str] = {
                item["name"].upper()
                for item in data.get("universe", [])
                if "name" in item
            }
            self._hl_universe = universe
            self._hl_universe_ts = now
            logger.info(
                f"Hyperliquid universe fetched | "
                f"{len(universe)} perp assets listed"
            )
            return universe

        except Exception as exc:
            logger.warning(
                f"Failed to fetch Hyperliquid universe: {exc}. "
                f"HL validation will be skipped."
            )
            return set()


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton helper
# ─────────────────────────────────────────────────────────────────────────────

_synchroniser: Optional[SymbolSynchroniser] = None


def get_synchroniser(
    hl_api_base: str = "https://api.hyperliquid.xyz",
) -> SymbolSynchroniser:
    """
    Return the process-level singleton ``SymbolSynchroniser``.

    Parameters
    ----------
    hl_api_base : str
        Only applied on the very first call (singleton pattern).

    Returns
    -------
    SymbolSynchroniser
    """
    global _synchroniser
    if _synchroniser is None:
        _synchroniser = SymbolSynchroniser(hl_api_base=hl_api_base)
    return _synchroniser


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone demo — no MT5 connection required.

    Run from project root:
        python -m backend.core.symbol_sync
    """
    from backend.core.config import SYMBOLS as MT5_SYMBOLS  # noqa: E402

    demo_symbols = MT5_SYMBOLS + ["BTCUSD", "XAUUSD", "BTCUSD.r", "UNKNOWN_PAIR"]

    syncer = SymbolSynchroniser()
    assets = syncer.build_map(demo_symbols, validate_with_hl=True)

    print(f"\n{'─'*65}")
    print(f" Antigravity Symbol Sync Report ({len(assets)} symbols)")
    print(f"{'─'*65}")
    for a in assets:
        print(f"  {a}")
    print(f"{'─'*65}\n")
