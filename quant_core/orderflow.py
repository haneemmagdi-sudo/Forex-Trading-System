"""
quant_core/orderflow.py
=======================
Real Order Flow Imbalance (OFI) Engine — Pure NumPy Math, Zero LLM.

Uses mt5.copy_ticks_from() for live mode, or a high-fidelity tick
simulator derived from OHLCV bar data for CI / backtesting.

Law 1 (from .antigravityrules): No LLM computes these numbers.
All math is deterministic NumPy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False


# ---------------------------------------------------------------------------
# Pydantic output contract (passed to BetaOrderFlowAgent)
# ---------------------------------------------------------------------------

class OFIResult(BaseModel):
    """
    Strict Pydantic output of the Real OFI computation.
    All fields are calibrated, normalised, and ready for downstream agents.
    """
    symbol: str
    ofi_z_score: float = Field(
        ...,
        ge=-4.0,
        le=4.0,
        description=(
            "Z-score of net buy/sell tick-volume pressure over the last "
            "N_RECENT_TICKS vs a 10-min rolling baseline. "
            ">1.5 = strong institutional buying, <-1.5 = strong selling."
        ),
    )
    cumulative_delta: float = Field(
        ...,
        description="Raw Σ(signed_volume) for the last N_RECENT_TICKS. In tick-units.",
    )
    buy_volume_pct: float = Field(..., ge=0.0, le=1.0)
    sell_volume_pct: float = Field(..., ge=0.0, le=1.0)
    tick_count_used: int
    source: str = Field(..., description="LIVE_MT5 | SIMULATED")


# ---------------------------------------------------------------------------
# Pure-math helpers (quant_core layer — no IO)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _TickFrame:
    """Lightweight struct for a processed tick dataframe."""
    price: np.ndarray   # shape (N,)  float64
    volume: np.ndarray  # shape (N,)  float64
    time: np.ndarray    # shape (N,)  int64  (Unix ms)


def _compute_ofi_from_arrays(
    price: np.ndarray,
    volume: np.ndarray,
    n_recent: int = 400,
    baseline_window: int = 2000,
) -> OFIResult:
    """
    Core OFI formula:
        signed_vol[i] = +volume[i]  if price[i] > price[i-1]  (aggressive buy)
                      = -volume[i]  if price[i] < price[i-1]  (aggressive sell)
                      = 0           if price[i] == price[i-1]  (neutral)

    Z-score baseline = rolling mean/std of cumulative OFI windows.
    """
    if len(price) < max(n_recent + 10, baseline_window // 4):
        # Not enough ticks — return neutral
        return OFIResult(
            symbol="",
            ofi_z_score=0.0,
            cumulative_delta=0.0,
            buy_volume_pct=0.5,
            sell_volume_pct=0.5,
            tick_count_used=len(price),
            source="INSUFFICIENT_DATA",
        )

    # Directional assignment
    price_delta = np.diff(price, prepend=price[0])
    direction = np.sign(price_delta)  # +1, -1, 0

    signed_vol = direction * volume

    # Cumulative delta for the recent window
    recent_sv = signed_vol[-n_recent:]
    cumulative_delta = float(recent_sv.sum())

    buy_vol = float(volume[-n_recent:][direction[-n_recent:] > 0].sum())
    sell_vol = float(volume[-n_recent:][direction[-n_recent:] < 0].sum())
    total_vol = buy_vol + sell_vol + 1e-9

    # Rolling baseline: chunk signed_vol into windows of size n_recent,
    # compute mean/std of each chunk's sum to get the Z-score baseline
    n_chunks = len(signed_vol) // n_recent
    if n_chunks >= 4:
        chunk_sums = np.array([
            signed_vol[i * n_recent: (i + 1) * n_recent].sum()
            for i in range(n_chunks)
        ])
        baseline_mean = float(chunk_sums[:-1].mean())
        baseline_std = float(chunk_sums[:-1].std())
    else:
        baseline_mean = 0.0
        baseline_std = float(np.abs(signed_vol).mean()) * n_recent + 1e-9

    if baseline_std < 1e-9:
        z = 0.0
    else:
        z = (cumulative_delta - baseline_mean) / baseline_std

    return OFIResult(
        symbol="",          # filled by caller
        ofi_z_score=float(np.clip(z, -4.0, 4.0)),
        cumulative_delta=round(cumulative_delta, 2),
        buy_volume_pct=round(buy_vol / total_vol, 4),
        sell_volume_pct=round(sell_vol / total_vol, 4),
        tick_count_used=n_recent,
        source="COMPUTED",
    )


def simulate_ticks_from_ohlcv(df: pd.DataFrame, ticks_per_bar: int = 30) -> _TickFrame:
    """
    High-fidelity tick simulator from M5 OHLCV bars.
    Synthesises realistic tick pressure within each bar using:
      - Bar direction (close vs open) determines dominant pressure
      - Volume distributed across simulated ticks with institutional clustering
    Used in backtesting / CI (no MT5 terminal required).
    """
    rng = np.random.default_rng(seed=99)
    all_prices: list[float] = []
    all_volumes: list[float] = []

    for _, row in df.iterrows():
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        tv = float(row.get("tick_volume", 100.0))

        # Guarantee valid OHLC ordering regardless of synthetic data artifacts
        real_low  = min(o, h, l, c)
        real_high = max(o, h, l, c)
        if real_high - real_low < 1e-10:
            real_high = real_low + 1e-5  # Minimum 1-pip range

        # Bullish bar: most ticks cluster from low → high → close
        # Bearish bar: most ticks cluster from high → low → close
        if c >= o:
            path = np.sort(rng.uniform(real_low, real_high, ticks_per_bar))
            path[-1] = float(np.clip(c, real_low, real_high))
        else:
            path = np.sort(rng.uniform(real_low, real_high, ticks_per_bar))[::-1].copy()
            path[-1] = float(np.clip(c, real_low, real_high))

        # Volume per tick: lognormal with mean = tv / ticks_per_bar
        mean_tick_vol = tv / ticks_per_bar
        tick_vols = rng.lognormal(mean=np.log(max(mean_tick_vol, 0.1)), sigma=0.6, size=ticks_per_bar)

        all_prices.extend(path.tolist())
        all_volumes.extend(tick_vols.tolist())

    return _TickFrame(
        price=np.array(all_prices, dtype=np.float64),
        volume=np.array(all_volumes, dtype=np.float64),
        time=np.arange(len(all_prices), dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# Public interface — async, MT5-aware
# ---------------------------------------------------------------------------

class RealOFIEngine:
    """
    Computes Real Order Flow Imbalance.
    Falls back to OHLCV tick simulation when MT5 is unavailable.
    Thread-safe: computation offloaded via asyncio.to_thread().
    """

    N_RECENT_TICKS: int = 400    # ~3-5 min of ticks on majors
    N_BASELINE_TICKS: int = 4000  # ~30-40 min baseline

    def __init__(self, use_live_mt5: bool = False):
        self.use_live_mt5 = use_live_mt5 and _MT5_AVAILABLE

    # ------------------------------------------------------------------
    # Live MT5 path
    # ------------------------------------------------------------------

    def _fetch_and_compute_live(self, symbol: str) -> OFIResult:
        """Fetches real ticks from MT5 terminal and computes OFI."""
        from_dt = datetime.now(timezone.utc) - timedelta(minutes=45)
        ticks = mt5.copy_ticks_from(
            symbol,
            from_dt,
            self.N_BASELINE_TICKS,
            mt5.COPY_TICKS_ALL,
        )
        if ticks is None or len(ticks) < self.N_RECENT_TICKS + 50:
            # Graceful degradation
            return OFIResult(
                symbol=symbol,
                ofi_z_score=0.0,
                cumulative_delta=0.0,
                buy_volume_pct=0.5,
                sell_volume_pct=0.5,
                tick_count_used=0,
                source="MT5_NO_DATA",
            )

        df_t = pd.DataFrame(ticks)
        # MT5 tick columns: time, bid, ask, last, volume, time_msc, flags, volume_real
        # Use 'last' as trade price when available, else mid(bid, ask)
        if "last" in df_t.columns and df_t["last"].iloc[-1] > 0:
            price_arr = df_t["last"].to_numpy(dtype=np.float64)
        else:
            price_arr = ((df_t["bid"] + df_t["ask"]) / 2.0).to_numpy(dtype=np.float64)

        # Use volume_real if available (actual contract volume), else volume (tick count)
        if "volume_real" in df_t.columns and df_t["volume_real"].sum() > 0:
            vol_arr = df_t["volume_real"].to_numpy(dtype=np.float64)
        else:
            vol_arr = df_t["volume"].to_numpy(dtype=np.float64)

        result = _compute_ofi_from_arrays(
            price=price_arr,
            volume=vol_arr,
            n_recent=self.N_RECENT_TICKS,
        )
        return result.model_copy(update={"symbol": symbol, "source": "LIVE_MT5"})

    # ------------------------------------------------------------------
    # Simulation path (CI / Backtesting)
    # ------------------------------------------------------------------

    def _compute_from_ohlcv(self, symbol: str, df_m5: pd.DataFrame) -> OFIResult:
        """Synthesises tick-level OFI from M5 OHLCV bars."""
        tick_frame = simulate_ticks_from_ohlcv(df_m5.iloc[-80:], ticks_per_bar=50)
        result = _compute_ofi_from_arrays(
            price=tick_frame.price,
            volume=tick_frame.volume,
            n_recent=self.N_RECENT_TICKS,
        )
        return result.model_copy(update={"symbol": symbol, "source": "SIMULATED"})

    # ------------------------------------------------------------------
    # Async public API
    # ------------------------------------------------------------------

    async def compute(
        self,
        symbol: str,
        df_m5: Optional[pd.DataFrame] = None,
    ) -> OFIResult:
        """
        Returns OFIResult asynchronously.
        If use_live_mt5=True → fetches from terminal.
        Otherwise → synthesises from df_m5 OHLCV.
        """
        if self.use_live_mt5:
            return await asyncio.to_thread(self._fetch_and_compute_live, symbol)
        if df_m5 is not None:
            return await asyncio.to_thread(self._compute_from_ohlcv, symbol, df_m5)
        return OFIResult(
            symbol=symbol,
            ofi_z_score=0.0,
            cumulative_delta=0.0,
            buy_volume_pct=0.5,
            sell_volume_pct=0.5,
            tick_count_used=0,
            source="NO_INPUT",
        )
