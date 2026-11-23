"""
Agent Beta: Microstructure & SMC Order Flow (`beta_orderflow_agent.py`)
Scans Real Tick OFI (quant_core.RealOFIEngine), Fair Value Gaps (FVG),
Order Blocks (OB), and Liquidity Sweeps (BSL/SSL) to propose
high-precision institutional setups.

Upgrade (2026-10): replaced synthetic tick_volume_delta_z with
RealOFIEngine backed by mt5.copy_ticks_from() in live mode and
a high-fidelity OHLCV tick-simulator in backtesting/CI mode.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from .alpha_regime_agent import RegimeOutput, RegimeState
from .tuning import get_value
from quant_core.orderflow import RealOFIEngine, OFIResult


class OrderFlowProposal(BaseModel):
    symbol: str
    proposed_action: str = Field(..., description="BUY | SELL | LIMIT_BUY | LIMIT_SELL | STAND_DOWN")
    signal_confidence: float = Field(..., ge=0.0, le=1.0)
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    setup_type: str
    liquidity_sweep_detected: bool
    fvg_magnet_price: Optional[float] = None
    # Real OFI fields (replaces synthetic tick_volume_delta_z)
    ofi_z_score: float = Field(
        ...,
        description="Real Order Flow Imbalance Z-score from tick data. >1.5=institutional buying.",
    )
    ofi_buy_pct: float = Field(..., ge=0.0, le=1.0)
    ofi_source: str = Field(..., description="LIVE_MT5 | SIMULATED | NO_INPUT")
    killzone_active: bool
    rationale: str
    metadata: Dict[str, Any]


class BetaOrderFlowAgent:
    """
    Institutional Order Flow & Smart Money Concepts (SMC) Signal Engine.
    Powered by RealOFIEngine (quant_core) for tick-accurate pressure detection.
    """

    def __init__(self, point_value: float = 0.00001, use_live_mt5: bool = False):
        self.point_value = point_value
        self._ofi_engine = RealOFIEngine(use_live_mt5=use_live_mt5)
        self._fvg_min_atr_ratio = float(get_value("ENTRY_UPGRADES_2026", "fvg_min_atr_ratio", 0.15))
        self._ofi_counter_flow_z = float(get_value("ENTRY_UPGRADES_2026", "ofi_counter_flow_z", 1.8))

    @staticmethod
    def is_institutional_killzone(utc_now: datetime) -> bool:
        """
        Checks if current UTC hour falls within London Open (06:00-10:00 UTC)
        or New York Open (12:00-16:00 UTC).
        """
        hour = utc_now.hour
        return (6 <= hour <= 10) or (12 <= hour <= 16)

    @staticmethod
    def detect_fvg(df: pd.DataFrame, min_gap_size: float = 0.0) -> Dict[str, Any]:
        """
        Upgrade (2026 v2): Detects the most recent unmitigated 3-candle Fair Value Gap
        over the last 20 candles with institutional displacement filtering (min_gap_size)
        and age_bars metadata to reject stale/micro-noise imbalances.
        """
        recent = df.iloc[-22:].reset_index(drop=True)
        bullish_fvg = None
        bearish_fvg = None
        last_idx = len(recent) - 1

        for i in range(2, len(recent)):
            c1_high = float(recent.loc[i - 2, "high"])
            c1_low = float(recent.loc[i - 2, "low"])
            c3_high = float(recent.loc[i, "high"])
            c3_low = float(recent.loc[i, "low"])

            # Bullish FVG: Candle 3 Low > Candle 1 High, unmitigated, and meets displacement floor
            gap_bull = c3_low - c1_high
            if gap_bull > 0.0 and gap_bull >= min_gap_size:
                subsequent_low = float(recent.loc[i + 1 :, "low"].min()) if (i + 1) < len(recent) else c3_low
                if subsequent_low > c1_high:
                    bullish_fvg = {
                        "top": c3_low,
                        "bottom": c1_high,
                        "midpoint": (c3_low + c1_high) / 2.0,
                        "gap_size": gap_bull,
                        "age_bars": int(last_idx - i),
                    }
            # Bearish FVG: Candle 3 High < Candle 1 Low, unmitigated, and meets displacement floor
            gap_bear = c1_low - c3_high
            if gap_bear > 0.0 and gap_bear >= min_gap_size:
                subsequent_high = float(recent.loc[i + 1 :, "high"].max()) if (i + 1) < len(recent) else c3_high
                if subsequent_high < c1_low:
                    bearish_fvg = {
                        "top": c1_low,
                        "bottom": c3_high,
                        "midpoint": (c1_low + c3_high) / 2.0,
                        "gap_size": gap_bear,
                        "age_bars": int(last_idx - i),
                    }

        return {"bullish_fvg": bullish_fvg, "bearish_fvg": bearish_fvg}

    @staticmethod
    def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 24) -> Dict[str, Any]:
        """
        Detects Buy-Side Liquidity (BSL) or Sell-Side Liquidity (SSL) sweeps:
        Wick pierces prior swing high/low, but candle closes back inside range
        with elevated tick volume.
        """
        prior_window = df.iloc[-(lookback + 2) : -2]
        last_two = df.iloc[-2:]

        swing_high = float(prior_window["high"].max())
        swing_low = float(prior_window["low"].min())

        recent_high = float(last_two["high"].max())
        recent_low = float(last_two["min"] if "min" in last_two.columns else last_two["low"].min())
        current_close = float(df["close"].iloc[-1])

        ssl_swept = (recent_low < swing_low) and (current_close > swing_low)
        bsl_swept = (recent_high > swing_high) and (current_close < swing_high)

        return {
            "ssl_swept": ssl_swept,
            "bsl_swept": bsl_swept,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "sweep_extreme_low": recent_low,
            "sweep_extreme_high": recent_high,
        }

    # compute_tick_volume_delta_z removed — superseded by RealOFIEngine
    # (quant_core/orderflow.py). Retained signature below for any legacy callers.
    @staticmethod
    def _legacy_tick_vol_delta_z(df: pd.DataFrame) -> float:
        """Deprecated synthetic proxy. Use RealOFIEngine instead."""
        candle_range = (df["high"] - df["low"]).replace(0, 1e-8)
        close_pos = ((df["close"] - df["low"]) / candle_range) * 2.0 - 1.0
        signed_vol = close_pos * df["tick_volume"]
        mean_v = signed_vol.rolling(30, min_periods=10).mean().iloc[-1]
        std_v = signed_vol.rolling(30, min_periods=10).std().iloc[-1]
        if std_v <= 1e-8 or np.isnan(std_v):
            return 0.0
        return float(np.clip((signed_vol.iloc[-1] - mean_v) / std_v, -4.0, 4.0))

    def _propose_sync(
        self,
        symbol: str,
        df_m5: pd.DataFrame,
        regime: RegimeOutput,
        utc_now: datetime,
        ofi: OFIResult,
        point_value: Optional[float] = None,
    ) -> OrderFlowProposal:
        current_price = float(df_m5["close"].iloc[-1])
        pv = self.point_value if point_value is None else point_value
        atr_price = regime.atr_points * pv

        min_fvg_gap = max(0.0, self._fvg_min_atr_ratio * atr_price)
        fvg_data = self.detect_fvg(df_m5, min_gap_size=min_fvg_gap)
        sweep_data = self.detect_liquidity_sweep(df_m5, lookback=24)
        vol_delta_z = ofi.ofi_z_score   # Real OFI Z-score from quant_core
        killzone = self.is_institutional_killzone(utc_now)

        # Hard Regime Gate: Never propose trades in Shock or Random Walk
        if regime.regime_state in (RegimeState.HIGH_VOL_SHOCK, RegimeState.CHOPPY_RANDOM_WALK):
            return OrderFlowProposal(
                symbol=symbol,
                proposed_action="STAND_DOWN",
                signal_confidence=0.0,
                entry_price=current_price,
                stop_loss=current_price,
                take_profit_1=current_price,
                take_profit_2=current_price,
                setup_type="REGIME_BLOCKED",
                liquidity_sweep_detected=False,
                ofi_z_score=round(vol_delta_z, 3),
                ofi_buy_pct=ofi.buy_volume_pct,
                ofi_source=ofi.source,
                killzone_active=killzone,
                rationale=f"Blocked by Agent Alpha Regime: {regime.regime_state.value}",
                metadata=sweep_data,
            )

        action = "STAND_DOWN"
        confidence = 0.0
        entry_price = current_price
        sl = current_price
        tp1 = current_price
        tp2 = current_price
        setup_type = "NONE"
        fvg_magnet = None
        sweep_flag = False
        rationale = "No institutional confluence detected."

        # CASE 1: MEAN_REVERTING_RANGE -> Trade Liquidity Sweeps (Turtle Soup / Judas Swing)
        if regime.regime_state == RegimeState.MEAN_REVERTING_RANGE:
            if sweep_data["ssl_swept"] and regime.rolling_z_score < -1.1:
                action = "LIMIT_BUY"
                sweep_flag = True
                setup_type = "SSL_SWEEP_REVERSAL"
                bull_fvg = fvg_data.get("bullish_fvg")
                entry_price = bull_fvg["midpoint"] if bull_fvg else current_price - (0.15 * atr_price)
                sl = min(sweep_data["sweep_extreme_low"], entry_price) - (0.65 * atr_price)
                risk_dist = abs(entry_price - sl)
                tp1 = entry_price + (2.0 * risk_dist)
                tp2 = max(sweep_data["swing_high"], entry_price + (3.2 * risk_dist))
                confidence = 0.82 + (0.06 if killzone else 0.0) + (0.05 if vol_delta_z > 0.8 else 0.0)
                rationale = "Sell-Side Liquidity swept below swing low with strong reclaim and negative Z-score stretch."

            elif sweep_data["bsl_swept"] and regime.rolling_z_score > 1.1:
                action = "LIMIT_SELL"
                sweep_flag = True
                setup_type = "BSL_SWEEP_REVERSAL"
                bear_fvg = fvg_data.get("bearish_fvg")
                entry_price = bear_fvg["midpoint"] if bear_fvg else current_price + (0.15 * atr_price)
                sl = max(sweep_data["sweep_extreme_high"], entry_price) + (0.65 * atr_price)
                risk_dist = abs(sl - entry_price)
                tp1 = entry_price - (2.0 * risk_dist)
                tp2 = min(sweep_data["swing_low"], entry_price - (3.2 * risk_dist))  # P0 fix: subtract for SELL TP2
                confidence = 0.82 + (0.06 if killzone else 0.0) + (0.05 if vol_delta_z < -0.8 else 0.0)
                rationale = "Buy-Side Liquidity swept above swing high with rejection close and positive Z-score stretch."

        # CASE 2: TRENDING_LOW_VOL -> Trade Order Block / FVG Pullbacks in HTF Direction
        elif regime.regime_state == RegimeState.TRENDING_LOW_VOL:
            bull_fvg = fvg_data.get("bullish_fvg")
            bear_fvg = fvg_data.get("bearish_fvg")

            if regime.directional_bias == "BULLISH" and bull_fvg is not None:
                action = "LIMIT_BUY"
                setup_type = "TREND_FVG_PULLBACK_LONG"
                fvg_magnet = round(bull_fvg["midpoint"], 5)
                entry_price = bull_fvg["midpoint"]
                sl = bull_fvg["bottom"] - (1.1 * atr_price)
                risk_dist = max(abs(entry_price - sl), 0.5 * atr_price)
                tp1 = entry_price + (2.2 * risk_dist)
                tp2 = entry_price + (3.8 * risk_dist)
                sweep_flag = sweep_data["ssl_swept"]
                # Continuous bounded OFI adjustment + severe counter-flow guard (2026 v2)
                ofi_adj = float(np.clip(vol_delta_z * 0.03, -0.10, 0.05))
                if vol_delta_z < -self._ofi_counter_flow_z:
                    ofi_adj -= 0.12  # Severe opposing institutional selling flow
                age_decay = max(0.0, (bull_fvg.get("age_bars", 0) - 8) * 0.004)
                confidence = 0.84 + (0.05 if killzone else 0.0) + (0.05 if sweep_flag else 0.0) + ofi_adj - age_decay
                sweep_data["ofi_counter_flow"] = bool(vol_delta_z < -self._ofi_counter_flow_z)
                sweep_data["fvg_gap_atr_ratio"] = round(bull_fvg.get("gap_size", 0.0) / max(atr_price, 1e-8), 3)
                rationale = "Bullish HTF trend aligned with displacement-verified unmitigated M5 Bullish FVG + OFI."

            elif regime.directional_bias == "BEARISH" and bear_fvg is not None:
                action = "LIMIT_SELL"
                setup_type = "TREND_FVG_PULLBACK_SHORT"
                fvg_magnet = round(bear_fvg["midpoint"], 5)
                entry_price = bear_fvg["midpoint"]
                sl = bear_fvg["top"] + (1.1 * atr_price)
                risk_dist = max(abs(sl - entry_price), 0.5 * atr_price)
                tp1 = entry_price - (2.2 * risk_dist)
                tp2 = entry_price - (3.8 * risk_dist)
                sweep_flag = sweep_data["bsl_swept"]
                # Continuous bounded OFI adjustment + severe counter-flow guard (2026 v2)
                ofi_adj = float(np.clip((-vol_delta_z) * 0.03, -0.10, 0.05))
                if vol_delta_z > self._ofi_counter_flow_z:
                    ofi_adj -= 0.12  # Severe opposing institutional buying flow
                age_decay = max(0.0, (bear_fvg.get("age_bars", 0) - 8) * 0.004)
                confidence = 0.84 + (0.05 if killzone else 0.0) + (0.05 if sweep_flag else 0.0) + ofi_adj - age_decay
                sweep_data["ofi_counter_flow"] = bool(vol_delta_z > self._ofi_counter_flow_z)
                sweep_data["fvg_gap_atr_ratio"] = round(bear_fvg.get("gap_size", 0.0) / max(atr_price, 1e-8), 3)
                rationale = "Bearish HTF trend aligned with displacement-verified unmitigated M5 Bearish FVG + OFI."

        return OrderFlowProposal(
            symbol=symbol,
            proposed_action=action,
            signal_confidence=round(float(np.clip(confidence, 0.0, 0.98)), 4),
            entry_price=round(entry_price, 5),
            stop_loss=round(sl, 5),
            take_profit_1=round(tp1, 5),
            take_profit_2=round(tp2, 5),
            setup_type=setup_type,
            liquidity_sweep_detected=sweep_flag,
            fvg_magnet_price=fvg_magnet,
            ofi_z_score=round(vol_delta_z, 3),
            ofi_buy_pct=ofi.buy_volume_pct,
            ofi_source=ofi.source,
            killzone_active=killzone,
            rationale=rationale,
            metadata=sweep_data,
        )

    async def propose_setup(
        self,
        symbol: str,
        df_m5: pd.DataFrame,
        regime: RegimeOutput,
        utc_now: Optional[datetime] = None,
        point_value: Optional[float] = None,
    ) -> OrderFlowProposal:
        """Async entry point — computes Real OFI concurrently then proposes setup."""
        if utc_now is None:
            utc_now = datetime.now(timezone.utc)
        # Compute Real OFI concurrently with regime (already done upstream).
        # Here we receive the result from the orchestrator — pass it through.
        # For backward-compat when called standalone, compute OFI from df_m5.
        ofi = await self._ofi_engine.compute(symbol=symbol, df_m5=df_m5)
        return await asyncio.to_thread(self._propose_sync, symbol, df_m5, regime, utc_now, ofi, point_value)
