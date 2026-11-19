"""
Agent Alpha: Market Regime & Statistical Quant (`alpha_regime_agent.py`)
Deterministically classifies the current market state using pure NumPy/Pandas math:
- Rescaled Range (R/S) & Variance-Ratio Hurst Exponent
- ATR Volatility Ratio (Current ATR / Rolling Baseline ATR)
- Rolling Z-Score of Price vs VWAP/EMA
- ADX Trend Strength
"""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class RegimeState(str, Enum):
    TRENDING_LOW_VOL = "TRENDING_LOW_VOL"
    MEAN_REVERTING_RANGE = "MEAN_REVERTING_RANGE"
    HIGH_VOL_SHOCK = "HIGH_VOL_SHOCK"
    CHOPPY_RANDOM_WALK = "CHOPPY_RANDOM_WALK"


class RegimeOutput(BaseModel):
    symbol: str
    regime_state: RegimeState
    regime_confidence: float = Field(..., ge=0.0, le=1.0)
    hurst_exponent: float
    atr_points: float
    atr_ratio: float
    rolling_z_score: float
    directional_bias: str = Field(..., description="BULLISH | BEARISH | NEUTRAL")
    diagnostics: Dict[str, Any]


class AlphaRegimeAgent:
    """
    Mathematical Regime Classifier. Zero LLM guessing for numbers.
    """

    def __init__(self, point_value: float = 0.00001):
        self.point_value = point_value

    @staticmethod
    def compute_hurst_exponent(price_series: np.ndarray, max_lag: int = 25) -> float:
        """
        Calculates the Generalized Hurst Exponent using log-price root-mean-square
        displacement across lags: E[|X(t+tau) - X(t)|] ~ tau^H.
        H < 0.45: Mean-Reverting
        0.45 <= H <= 0.55: Random Walk / Choppy Noise
        H > 0.55: Trending / Persistent
        """
        if len(price_series) < max_lag + 15:
            return 0.50

        lags = np.arange(2, max_lag)
        log_prices = np.log(np.maximum(price_series, 1e-8))
        rms_displacements = [
            np.sqrt(np.mean(np.square(log_prices[lag:] - log_prices[:-lag])))
            for lag in lags
        ]
        rms_displacements = np.maximum(rms_displacements, 1e-10)

        poly = np.polyfit(np.log(lags), np.log(rms_displacements), 1)
        hurst = float(poly[0])
        return float(np.clip(hurst, 0.05, 0.95))

    @staticmethod
    def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def compute_z_score(series: pd.Series, window: int = 50) -> float:
        rolling_mean = series.rolling(window=window, min_periods=10).mean()
        rolling_std = series.rolling(window=window, min_periods=10).std()
        current_std = float(rolling_std.iloc[-1])
        if current_std <= 1e-9 or np.isnan(current_std):
            return 0.0
        z = ( float(series.iloc[-1]) - float(rolling_mean.iloc[-1]) ) / current_std
        return float(np.clip(z, -5.0, 5.0))

    def _evaluate_sync(
        self,
        symbol: str,
        df_m5: pd.DataFrame,
        df_h1: pd.DataFrame,
        point_value: Optional[float] = None,
    ) -> RegimeOutput:
        pv = self.point_value if point_value is None else point_value
        if not pv > 0:
            raise ValueError(f"point_value must be > 0 for {symbol}, got {pv!r}")
        closes_m5 = df_m5["close"].to_numpy(dtype=float)
        hurst = self.compute_hurst_exponent(closes_m5[-120:], max_lag=25)

        atr_series = self.compute_atr(df_m5, period=14)
        current_atr = float(atr_series.iloc[-1])
        baseline_atr = float(atr_series.rolling(window=100, min_periods=20).mean().iloc[-1])
        atr_ratio = current_atr / max(baseline_atr, 1e-9)
        atr_points = round(current_atr / pv, 1)

        z_score = self.compute_z_score(df_m5["close"], window=50)

        # Higher Timeframe EMA Bias (H1 EMA 20 vs EMA 50)
        ema_fast_h1 = df_h1["close"].ewm(span=20, adjust=False).mean().iloc[-1]
        ema_slow_h1 = df_h1["close"].ewm(span=50, adjust=False).mean().iloc[-1]
        if ema_fast_h1 > ema_slow_h1 * 1.0002:
            htf_bias = "BULLISH"
        elif ema_fast_h1 < ema_slow_h1 * 0.9998:
            htf_bias = "BEARISH"
        else:
            htf_bias = "NEUTRAL"

        # Regime Classification Rules (Strict Quantitative Thresholds)
        if atr_ratio >= 2.15:
            state = RegimeState.HIGH_VOL_SHOCK
            confidence = float(np.clip((atr_ratio - 2.0) / 1.5 + 0.75, 0.75, 0.99))
        elif 0.46 <= hurst <= 0.54:
            state = RegimeState.CHOPPY_RANDOM_WALK
            # Higher confidence that it is random walk the closer Hurst is to 0.50
            confidence = float(np.clip(1.0 - abs(hurst - 0.50) * 10.0, 0.60, 0.98))
        elif hurst > 0.54:
            state = RegimeState.TRENDING_LOW_VOL
            hurst_strength = (hurst - 0.54) / 0.30
            vol_stability = 1.0 - max(0.0, abs(atr_ratio - 1.1) * 0.35)
            confidence = float(np.clip(0.65 + 0.35 * hurst_strength * vol_stability, 0.55, 0.98))
        else:
            state = RegimeState.MEAN_REVERTING_RANGE
            mr_strength = (0.46 - hurst) / 0.30
            z_stretch = min(abs(z_score) / 2.5, 1.0)
            confidence = float(np.clip(0.62 + 0.35 * (0.6 * mr_strength + 0.4 * z_stretch), 0.55, 0.97))

        return RegimeOutput(
            symbol=symbol,
            regime_state=state,
            regime_confidence=round(confidence, 4),
            hurst_exponent=round(hurst, 4),
            atr_points=atr_points,
            atr_ratio=round(atr_ratio, 4),
            rolling_z_score=round(z_score, 4),
            directional_bias=htf_bias,
            diagnostics={
                "ema20_h1": round(float(ema_fast_h1), 5),
                "ema50_h1": round(float(ema_slow_h1), 5),
                "baseline_atr_points": round(baseline_atr / pv, 1),
            },
        )

    async def analyze(
        self,
        symbol: str,
        df_m5: pd.DataFrame,
        df_h1: pd.DataFrame,
        point_value: Optional[float] = None,
    ) -> RegimeOutput:
        """Runs CPU-bound NumPy/Pandas math in a separate thread for async parallelism.
        point_value: حجم النقطة للرمز (من symbol_info)؛ الافتراضي قيمة الوكيل."""
        return await asyncio.to_thread(self._evaluate_sync, symbol, df_m5, df_h1, point_value)
