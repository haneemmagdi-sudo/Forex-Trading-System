"""
==============================================================================
ml_models/feature_fusion.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : Synchronized Feature Fusion & Engineering Pipeline
Author : Principal Quantitative Research Engineer
Version: 4.2.0

Overview
--------
The ``QuantumFeaturePipeline`` is the central data transformation hub that
assembles the complete, leakage-free feature matrix for the Random Forest
ensemble classifier.  It performs three parallel engineering tasks and merges
their outputs into a single, scaled feature row at bar-close time.

Three-Track Feature Assembly
-----------------------------
::

    Track 1 — Classical Technical Features
    ├── ATR (Average True Range)         → volatility proxy
    ├── RSI (Relative Strength Index)    → momentum / exhaustion
    ├── EMA ratio (8/21)                 → trend state
    ├── Rolling realized volatility      → regime classifier
    ├── Close-return (1-bar, 5-bar)      → short-horizon momentum
    └── BB %B (Bollinger position)       → mean reversion signal

    Track 2 — Smart Money Concepts (SMC) Features
    ├── ob_distance_pct                  → distance to nearest Order Block
    ├── fvg_present                      → Fair Value Gap flag (0/1)
    ├── swing_structure                  → HH/HL=+1, LH/LL=-1, neutral=0
    └── liquidity_sweep_flag             → recent stop-hunt indicator

    Track 3 — TimesFM Foundation Model Features
    ├── timesfm_alpha_delta              → forecast directional momentum
    ├── forecast_momentum_slope          → forecast structural velocity (OLS β)
    └── forecast_variance_risk           → predictive uncertainty (σ²)

Leakage-Free Scaling Protocol
-------------------------------
All features are scaled using a ``RollingWindowScaler`` from ``ml_models.utils``.
The contract is strict:

    fit window  :  history[t − window_size : t]   (PAST rows only — no leakage)
    transform   :  live_row[t]                     (the single live bar at t)

The scaler is NEVER fitted on the row being transformed.  This eliminates
every form of future data look-ahead bias (the most common cause of
overstated backtest performance in production trading systems).

Feature Matrix Schema
---------------------
Final feature vector (14 dimensions):

    Index  Name                      Source Track    Type
    ─────  ─────────────────────────  ────────────    ──────
    0      atr_pct                    Classical       float
    1      rsi_14                     Classical       float
    2      ema_ratio                  Classical       float
    3      realized_vol_20            Classical       float
    4      return_1                   Classical       float
    5      return_5                   Classical       float
    6      bb_pct_b                   Classical       float
    7      ob_distance_pct            SMC             float
    8      fvg_present                SMC             int (0/1)
    9      swing_structure            SMC             int (-1/0/+1)
    10     liquidity_sweep_flag       SMC             int (0/1)
    11     timesfm_alpha_delta        TimesFM         float
    12     forecast_momentum_slope    TimesFM         float
    13     forecast_variance_risk     TimesFM         float

Usage
-----
    from ml_models.feature_fusion import QuantumFeaturePipeline

    pipeline = QuantumFeaturePipeline(scaling_window=128)

    # Build training dataset from historical OHLCV DataFrame
    X_df, feature_names = pipeline.build_training_matrix(hist_df)

    # Transform a single live row at bar close (zero leakage)
    live_row_scaled = pipeline.transform_live_row(
        ohlcv_df        = live_ohlcv_df,   # full history up to bar t
        smc_params      = smc_dict,        # from SMC module
    )  # → np.ndarray shape (1, 14)
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Dict, Final, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from ml_models.timesfm_extractor import TimesFMFeatureExtractor
from ml_models.utils import (
    RollingWindowScaler,
    safe_fill_series,
    safe_fill_feature_matrix,
    validate_price_series,
)

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger: logging.Logger = logging.getLogger("ml_models.feature_fusion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum historical bars required before the pipeline produces any output.
_MIN_BARS: Final[int] = 64

#: ATR computation period in bars.
_ATR_PERIOD: Final[int] = 14

#: RSI computation period in bars.
_RSI_PERIOD: Final[int] = 14

#: Short EMA period for the EMA-ratio trend feature.
_EMA_SHORT: Final[int] = 8

#: Long EMA period for the EMA-ratio trend feature.
_EMA_LONG: Final[int] = 21

#: Realized volatility rolling window (bars).
_RVOL_WINDOW: Final[int] = 20

#: Bollinger Band period for %B calculation.
_BB_PERIOD: Final[int] = 20

#: Bollinger Band standard deviation multiplier.
_BB_STD: Final[float] = 2.0

#: Ordered feature column names (matches the 14-dim schema in the docstring).
FEATURE_NAMES: Final[List[str]] = [
    "atr_pct",
    "rsi_14",
    "ema_ratio",
    "realized_vol_20",
    "return_1",
    "return_5",
    "bb_pct_b",
    "ob_distance_pct",
    "fvg_present",
    "swing_structure",
    "liquidity_sweep_flag",
    "timesfm_alpha_delta",
    "forecast_momentum_slope",
    "forecast_variance_risk",
]

_N_FEATURES: Final[int] = len(FEATURE_NAMES)


# ===========================================================================
# Pydantic v2 SMC Parameter Validation Schema
# ===========================================================================

class SMCParameters(BaseModel):
    """
    Pydantic v2 schema for Smart Money Concepts structural parameters.

    Validated at the boundary of each live feature extraction call.
    Provides safe defaults when the SMC module has not yet identified
    all structural elements (e.g., at system warm-up).

    Attributes
    ----------
    ob_distance_pct : float
        Distance from current price to the nearest Order Block as a
        percentage of current price.  Non-negative.  0.0 = at the OB.
    fvg_present : int
        Fair Value Gap flag.  1 = active FVG detected; 0 = none.
    swing_structure : int
        Market structure label: +1 = Higher Highs & Higher Lows (uptrend),
        -1 = Lower Highs & Lower Lows (downtrend), 0 = neutral / unknown.
    liquidity_sweep_flag : int
        Recent stop-hunt / liquidity sweep indicator.
        1 = sweep detected in the last N bars; 0 = no sweep.
    """
    model_config = {"frozen": True}

    ob_distance_pct:     float = Field(default=0.0, ge=0.0, description="OB distance %.")
    fvg_present:         int   = Field(default=0,   ge=0, le=1, description="FVG flag 0/1.")
    swing_structure:     int   = Field(default=0,   ge=-1, le=1, description="Structure: -1/0/+1.")
    liquidity_sweep_flag: int  = Field(default=0,   ge=0, le=1, description="Sweep flag 0/1.")

    @field_validator("ob_distance_pct")
    @classmethod
    def _clip_ob_distance(cls, v: float) -> float:
        """Clamp OB distance to a maximum of 10% to prevent outliers."""
        return float(np.clip(v, 0.0, 10.0))


# ===========================================================================
# Classical Technical Indicator Calculators
# ===========================================================================

def _compute_atr_pct(df: pd.DataFrame, period: int = _ATR_PERIOD) -> pd.Series:
    """
    Compute the ATR percentage (ATR / close) for each bar.

    ATR captures the average price range volatility over ``period`` bars.
    Dividing by close normalises it to be scale-invariant across instruments.

    Formula
    -------
        TR  = max(high − low, |high − prev_close|, |low − prev_close|)
        ATR = EMA(TR, period)
        ATR% = ATR / close

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``close`` columns (lowercase).
    period : int
        EMA smoothing period.

    Returns
    -------
    pd.Series
        ATR percentage series, same index as ``df``.
    """
    high:  pd.Series = df["high"]
    low:   pd.Series = df["low"]
    close: pd.Series = df["close"]
    prev_close: pd.Series = close.shift(1)

    tr1: pd.Series = high - low
    tr2: pd.Series = (high - prev_close).abs()
    tr3: pd.Series = (low  - prev_close).abs()
    true_range: pd.Series = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr: pd.Series = true_range.ewm(span=period, adjust=False).mean()
    atr_pct: pd.Series = (atr / close).fillna(0.0)
    return atr_pct


def _compute_rsi(close: pd.Series, period: int = _RSI_PERIOD) -> pd.Series:
    """
    Compute the Relative Strength Index (RSI) using Wilder's EMA smoothing.

    RSI measures momentum and exhaustion:
        RSI > 70 → overbought (potential reversal down)
        RSI < 30 → oversold  (potential reversal up)
        RSI ≈ 50 → neutral

    Formula
    -------
        delta = close − prev_close
        gain  = EMA(max(delta, 0), period)
        loss  = EMA(max(-delta, 0), period)
        RS    = gain / loss
        RSI   = 100 − (100 / (1 + RS))

    Parameters
    ----------
    close : pd.Series
        Chronological closing price series.
    period : int
        Wilder smoothing period.  Default: 14.

    Returns
    -------
    pd.Series
        RSI values in [0, 100], same index as ``close``.
    """
    delta: pd.Series = close.diff()
    gain:  pd.Series = delta.clip(lower=0.0)
    loss:  pd.Series = (-delta).clip(lower=0.0)

    avg_gain: pd.Series = gain.ewm(span=period, min_periods=period, adjust=False).mean()
    avg_loss: pd.Series = loss.ewm(span=period, min_periods=period, adjust=False).mean()

    rs: pd.Series = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi: pd.Series = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _compute_ema_ratio(close: pd.Series, short: int = _EMA_SHORT, long: int = _EMA_LONG) -> pd.Series:
    """
    Compute the EMA ratio (short_EMA / long_EMA) as a trend-state indicator.

    Interpretation:
        ratio > 1.0 → short-term EMA above long-term → bullish trend
        ratio < 1.0 → short-term EMA below long-term → bearish trend
        ratio ≈ 1.0 → neutral / consolidating

    Parameters
    ----------
    close : pd.Series
        Closing price series.
    short : int
        Short EMA span.  Default: 8.
    long : int
        Long EMA span.  Default: 21.

    Returns
    -------
    pd.Series
        EMA ratio series, same index as ``close``.
    """
    ema_s: pd.Series = close.ewm(span=short, adjust=False).mean()
    ema_l: pd.Series = close.ewm(span=long,  adjust=False).mean()
    ratio: pd.Series = (ema_s / ema_l.replace(0.0, np.nan)).fillna(1.0)
    return ratio


def _compute_realized_vol(close: pd.Series, window: int = _RVOL_WINDOW) -> pd.Series:
    """
    Compute rolling realized volatility (annualized standard deviation of
    log returns) over a ``window``-bar rolling window.

    Formula
    -------
        log_return = log(close_t / close_{t-1})
        rvol_t     = std(log_return, window) × √252

    The √252 factor annualises daily volatility.  For intraday bars,
    adjust the multiplier accordingly (e.g., √8760 for hourly).

    Parameters
    ----------
    close : pd.Series
        Closing prices.
    window : int
        Rolling window for std computation.  Default: 20 bars.

    Returns
    -------
    pd.Series
        Realized volatility series, same index as ``close``.
    """
    log_ret: pd.Series = np.log(close / close.shift(1))
    rvol: pd.Series    = log_ret.rolling(window=window, min_periods=2).std() * np.sqrt(252)
    return rvol.fillna(0.0)


def _compute_bollinger_pct_b(close: pd.Series, period: int = _BB_PERIOD, n_std: float = _BB_STD) -> pd.Series:
    """
    Compute Bollinger Band %B, indicating the position of the current close
    relative to the upper and lower Bollinger Bands.

    Formula
    -------
        BB_mid   = SMA(close, period)
        BB_upper = BB_mid + n_std × std(close, period)
        BB_lower = BB_mid − n_std × std(close, period)
        %B       = (close − BB_lower) / (BB_upper − BB_lower)

    Interpretation:
        %B > 1.0 → close above upper band (overbought)
        %B < 0.0 → close below lower band (oversold)
        %B = 0.5 → close at midline (neutral)

    Parameters
    ----------
    close : pd.Series
        Closing prices.
    period : int
        SMA and std rolling window.  Default: 20.
    n_std : float
        Number of standard deviations for band width.  Default: 2.0.

    Returns
    -------
    pd.Series
        %B series (may lie outside [0, 1] during extremes), same index as ``close``.
    """
    bb_mid: pd.Series   = close.rolling(window=period, min_periods=2).mean()
    bb_std: pd.Series   = close.rolling(window=period, min_periods=2).std()
    bb_upper: pd.Series = bb_mid + n_std * bb_std
    bb_lower: pd.Series = bb_mid - n_std * bb_std
    band_width: pd.Series = (bb_upper - bb_lower).replace(0.0, np.nan)
    pct_b: pd.Series    = (close - bb_lower) / band_width
    return pct_b.fillna(0.5)


# ===========================================================================
# QuantumFeaturePipeline
# ===========================================================================

class QuantumFeaturePipeline:
    """
    Centralized feature engineering and fusion pipeline for the Quantum FSM
    Pro V4.2 Elite Random Forest ensemble classifier.

    Assembles 14 features from three parallel tracks (Classical Technical,
    Smart Money Concepts, TimesFM Foundation Model) and scales them using
    a causal rolling-window ``StandardScaler`` to prevent look-ahead bias.

    Parameters
    ----------
    scaling_window : int
        Number of historical rows used to fit the ``StandardScaler`` at each
        bar close.  Must be ≥ 32.  Default: 128 bars.
        Larger windows → more stable scaling; smaller → more adaptive.
    timesfm_context_len : int
        Historical context window passed to the TimesFM extractor.
        Must be a multiple of 32.  Default: 64.
    timesfm_horizon_len : int
        Forecast horizon bars for feature derivation.  Default: 10.
    lazy_load_timesfm : bool
        If True, defer TimesFM model loading to the first call.
        Default: False (eager load for production).

    Attributes
    ----------
    _timesfm : TimesFMFeatureExtractor
        The underlying TimesFM zero-shot feature extractor.
    _scaler : RollingWindowScaler
        The causal rolling scaler (zero leakage).
    _call_count : int
        Total number of successful ``transform_live_row`` calls.

    Examples
    --------
    >>> pipeline = QuantumFeaturePipeline(scaling_window=128)
    >>> X_df, names = pipeline.build_training_matrix(hist_ohlcv_df)
    >>> live_X = pipeline.transform_live_row(
    ...     ohlcv_df=live_df,
    ...     smc_params={"ob_distance_pct": 0.003, "fvg_present": 1, ...}
    ... )
    """

    def __init__(
        self,
        scaling_window:       int  = 128,
        timesfm_context_len:  int  = 64,
        timesfm_horizon_len:  int  = 10,
        lazy_load_timesfm:    bool = False,
    ) -> None:
        if scaling_window < 32:
            raise ValueError(
                f"scaling_window must be ≥ 32; received {scaling_window}."
            )

        self._scaling_window: int = scaling_window
        self._call_count:     int = 0

        # Initialize the TimesFM feature extractor
        self._timesfm = TimesFMFeatureExtractor(
            context_len=timesfm_context_len,
            horizon_len=timesfm_horizon_len,
            lazy_load=lazy_load_timesfm,
        )

        # Initialize the causal rolling scaler
        self._scaler = RollingWindowScaler(window_size=scaling_window)

        logger.info(
            "[QuantumFeaturePipeline] Initialized | "
            "scaling_window=%d | timesfm_context=%d | "
            "timesfm_horizon=%d | n_features=%d",
            scaling_window,
            timesfm_context_len,
            timesfm_horizon_len,
            _N_FEATURES,
        )

    # -------------------------------------------------------------------
    # Internal: OHLCV Normalization
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to lowercase and validate required columns.

        Parameters
        ----------
        df : pd.DataFrame
            Raw OHLCV data.

        Returns
        -------
        pd.DataFrame
            DataFrame with lowercase column names.

        Raises
        ------
        ValueError
            If any required column (open, high, low, close, volume) is missing.
        """
        col_map: Dict[str, str] = {c: c.lower() for c in df.columns}
        df = df.rename(columns=col_map)
        required = {"high", "low", "close"}
        missing  = required - set(df.columns)
        if missing:
            raise ValueError(
                f"OHLCV DataFrame missing required columns: {missing}. "
                f"Available: {list(df.columns)}"
            )
        return df

    # -------------------------------------------------------------------
    # Track 1: Classical Technical Features
    # -------------------------------------------------------------------

    def _compute_classical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all six classical momentum and volatility features.

        All computations are applied to the normalized OHLCV DataFrame.
        NaN values are filled using the deterministic three-step protocol:
            1. ffill(limit=5) → propagate last valid value
            2. bfill(limit=2) → back-fill leading NaNs
            3. fillna(constant) → safe per-feature defaults

        Parameters
        ----------
        df : pd.DataFrame
            Normalized OHLCV data with lowercase columns.

        Returns
        -------
        pd.DataFrame
            Feature DataFrame with columns matching the classical track
            of ``FEATURE_NAMES``:
            [atr_pct, rsi_14, ema_ratio, realized_vol_20, return_1, return_5,
             bb_pct_b]
        """
        close: pd.Series = df["close"]

        # ATR percentage (volatility)
        atr_pct:      pd.Series = _compute_atr_pct(df, period=_ATR_PERIOD)

        # RSI (momentum / exhaustion)
        rsi_14:       pd.Series = _compute_rsi(close, period=_RSI_PERIOD)

        # EMA ratio (trend state)
        ema_ratio:    pd.Series = _compute_ema_ratio(close, short=_EMA_SHORT, long=_EMA_LONG)

        # Realized volatility (regime)
        realized_vol: pd.Series = _compute_realized_vol(close, window=_RVOL_WINDOW)

        # Short-horizon momentum returns
        return_1:     pd.Series = close.pct_change(1).fillna(0.0)
        return_5:     pd.Series = close.pct_change(5).fillna(0.0)

        # Bollinger %B (mean-reversion)
        bb_pct_b:     pd.Series = _compute_bollinger_pct_b(close, period=_BB_PERIOD, n_std=_BB_STD)

        feat_df = pd.DataFrame({
            "atr_pct":         atr_pct,
            "rsi_14":          rsi_14,
            "ema_ratio":       ema_ratio,
            "realized_vol_20": realized_vol,
            "return_1":        return_1,
            "return_5":        return_5,
            "bb_pct_b":        bb_pct_b,
        }, index=df.index)

        # Apply three-step NaN protocol
        safe_defaults: Dict[str, float] = {
            "atr_pct":         0.0,
            "rsi_14":         50.0,
            "ema_ratio":       1.0,
            "realized_vol_20": 0.0,
            "return_1":        0.0,
            "return_5":        0.0,
            "bb_pct_b":        0.5,
        }
        feat_df = feat_df.ffill(limit=5).bfill(limit=2)
        for col, val in safe_defaults.items():
            feat_df[col] = feat_df[col].fillna(val)

        return feat_df

    # -------------------------------------------------------------------
    # Track 2: SMC Features
    # -------------------------------------------------------------------

    @staticmethod
    def _build_smc_row(smc_params: Dict[str, object]) -> Dict[str, float]:
        """
        Validate and package Smart Money Concepts parameters into the
        SMC feature track.

        Parameters
        ----------
        smc_params : dict
            Raw SMC output dict with optional keys:
            ``ob_distance_pct``, ``fvg_present``, ``swing_structure``,
            ``liquidity_sweep_flag``.

        Returns
        -------
        dict
            Validated SMC feature row with all 4 SMC feature keys.
        """
        try:
            validated = SMCParameters(**smc_params)
        except Exception as exc:
            logger.warning(
                "[QuantumFeaturePipeline] SMC parameter validation failed: %s. "
                "Using safe defaults (all zeros).",
                exc,
            )
            validated = SMCParameters()

        return {
            "ob_distance_pct":      validated.ob_distance_pct,
            "fvg_present":          float(validated.fvg_present),
            "swing_structure":      float(validated.swing_structure),
            "liquidity_sweep_flag": float(validated.liquidity_sweep_flag),
        }

    # -------------------------------------------------------------------
    # Track 3: TimesFM Feature Injection
    # -------------------------------------------------------------------

    def _extract_timesfm_row(
        self, ohlcv_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Call the TimesFM feature extractor and package the three foundation
        model features.

        On any failure (model not loaded, invalid data), returns a zeroed
        SMC-row with ``is_valid=False`` embedded in the logs but safe
        numeric values (0.0) in the feature dict to prevent NaN poisoning
        of the downstream scaler.

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            Full OHLCV history passed to the extractor.

        Returns
        -------
        dict
            Three TimesFM feature values:
            ``timesfm_alpha_delta``, ``forecast_momentum_slope``,
            ``forecast_variance_risk``.
        """
        try:
            features: Dict[str, object] = self._timesfm.extract_foundation_features(
                ohlcv_df
            )
        except Exception as exc:
            logger.error(
                "[QuantumFeaturePipeline] TimesFM extraction failed: %s", exc
            )
            features = {"is_valid": False}

        if not features.get("is_valid", False):
            return {
                "timesfm_alpha_delta":     0.0,
                "forecast_momentum_slope": 0.0,
                "forecast_variance_risk":  0.0,
            }

        return {
            "timesfm_alpha_delta":     float(features.get("timesfm_alpha_delta",     0.0)),
            "forecast_momentum_slope": float(features.get("forecast_momentum_slope", 0.0)),
            "forecast_variance_risk":  float(features.get("forecast_variance_risk",  0.0)),
        }

    # -------------------------------------------------------------------
    # Public: Build Training Matrix (Historical)
    # -------------------------------------------------------------------

    def build_training_matrix(
        self,
        ohlcv_df: pd.DataFrame,
        smc_df:   Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Build the complete unscaled feature matrix from a historical OHLCV
        DataFrame for model training.

        This method does NOT apply the rolling scaler — training normalization
        must be handled by the caller using the fitted ``StandardScaler`` on
        the full training dataset.

        TimesFM features are NOT included in the training matrix because they
        require per-row inference calls (computationally expensive for training).
        Instead, their columns are filled with zeros, and the model is trained
        to use the 11 classical + SMC features.  The 3 TimesFM features are
        injected only during live inference via ``transform_live_row``.

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            Full historical OHLCV bar data.  Minimum: ``_MIN_BARS`` rows.
        smc_df : pd.DataFrame, optional
            Historical SMC parameter DataFrame indexed identically to
            ``ohlcv_df``.  If None, SMC features default to 0.

        Returns
        -------
        Tuple[pd.DataFrame, List[str]]
            (feature_matrix, feature_names)
            - feature_matrix : pd.DataFrame of shape (n_bars, 14)
              Unscaled, NaN-free feature matrix aligned to ``ohlcv_df`` index.
            - feature_names : List[str]
              Ordered column names (``FEATURE_NAMES``).

        Raises
        ------
        ValueError
            If the OHLCV DataFrame has fewer than ``_MIN_BARS`` rows.
        """
        if len(ohlcv_df) < _MIN_BARS:
            raise ValueError(
                f"build_training_matrix requires ≥ {_MIN_BARS} rows; "
                f"received {len(ohlcv_df)}."
            )

        logger.info(
            "[QuantumFeaturePipeline] Building training matrix | "
            "n_bars=%d | smc_df=%s",
            len(ohlcv_df),
            "provided" if smc_df is not None else "None (zeros)",
        )

        df = self._normalize_ohlcv(ohlcv_df.copy())

        # Track 1: Classical features
        classical_df: pd.DataFrame = self._compute_classical_features(df)

        # Track 2: SMC features
        if smc_df is not None:
            smc_df = smc_df.reindex(df.index)
            ob_dist  = smc_df.get("ob_distance_pct", pd.Series(0.0, index=df.index)).fillna(0.0)
            fvg_flag = smc_df.get("fvg_present", pd.Series(0, index=df.index)).fillna(0).astype(float)
            swing    = smc_df.get("swing_structure", pd.Series(0, index=df.index)).fillna(0).astype(float)
            sweep    = smc_df.get("liquidity_sweep_flag", pd.Series(0, index=df.index)).fillna(0).astype(float)
        else:
            n = len(df)
            ob_dist  = pd.Series(0.0, index=df.index)
            fvg_flag = pd.Series(0.0, index=df.index)
            swing    = pd.Series(0.0, index=df.index)
            sweep    = pd.Series(0.0, index=df.index)

        smc_feature_df = pd.DataFrame({
            "ob_distance_pct":      ob_dist,
            "fvg_present":          fvg_flag,
            "swing_structure":      swing,
            "liquidity_sweep_flag": sweep,
        }, index=df.index)

        # Track 3: TimesFM features — zero-fill for training
        timesfm_df = pd.DataFrame({
            "timesfm_alpha_delta":     np.zeros(len(df)),
            "forecast_momentum_slope": np.zeros(len(df)),
            "forecast_variance_risk":  np.zeros(len(df)),
        }, index=df.index)

        # Merge all tracks
        feature_matrix: pd.DataFrame = pd.concat(
            [classical_df, smc_feature_df, timesfm_df],
            axis=1,
        )[FEATURE_NAMES]

        # Final NaN sweep
        feature_matrix = safe_fill_feature_matrix(feature_matrix)

        logger.info(
            "[QuantumFeaturePipeline] Training matrix built | "
            "shape=%s | NaN_count=%d",
            feature_matrix.shape,
            int(feature_matrix.isna().sum().sum()),
        )

        return feature_matrix, FEATURE_NAMES

    # -------------------------------------------------------------------
    # Public: Transform Live Row (Zero Leakage)
    # -------------------------------------------------------------------

    def transform_live_row(
        self,
        ohlcv_df:   pd.DataFrame,
        smc_params: Optional[Dict[str, object]] = None,
    ) -> np.ndarray:
        """
        Produce a single leakage-free, scaled feature row at bar-close time.

        This is the primary inference entry point called at every bar close
        by the Quantum FSM Pro orchestrator.

        Execution Pipeline
        ------------------
        1. Validate and normalize ``ohlcv_df``.
        2. Compute all 7 classical technical features over the full history.
        3. Validate SMC parameters via ``SMCParameters`` Pydantic schema.
        4. Extract 3 TimesFM foundation model features (live inference call).
        5. Concatenate all 14 features into a single-row array.
        6. Apply the causal rolling-window scaler:
               fit_window = history[t − scaling_window : t]
               transform  = live_row[t]
           (ZERO look-ahead bias by construction)
        7. Return the scaled 1×14 numpy array.

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            Full OHLCV bar history up to and including bar t.
            Minimum rows: ``_MIN_BARS`` + ``scaling_window`` + ``context_len``.
        smc_params : dict, optional
            Smart Money Concepts parameters for the current bar.
            Keys: ``ob_distance_pct``, ``fvg_present``, ``swing_structure``,
            ``liquidity_sweep_flag``.  Missing keys default to 0.

        Returns
        -------
        np.ndarray
            Scaled feature row of shape ``(1, 14)``.
            Contains ``np.nan`` only if the history is too short to fit the
            rolling scaler (should not occur in production).

        Examples
        --------
        >>> live_X = pipeline.transform_live_row(
        ...     ohlcv_df=bar_df,
        ...     smc_params={
        ...         "ob_distance_pct":      0.00312,
        ...         "fvg_present":          1,
        ...         "swing_structure":      1,
        ...         "liquidity_sweep_flag": 0,
        ...     }
        ... )
        >>> print(live_X.shape)
        (1, 14)
        """
        t0 = time.perf_counter()
        smc_params = smc_params or {}

        # ── Step 1: Validate and normalize OHLCV ────────────────────────
        if len(ohlcv_df) < _MIN_BARS:
            logger.warning(
                "[QuantumFeaturePipeline] Insufficient bars (%d < %d). "
                "Returning zero feature row.",
                len(ohlcv_df), _MIN_BARS,
            )
            return np.zeros((1, _N_FEATURES), dtype=np.float64)

        try:
            df = self._normalize_ohlcv(ohlcv_df.copy())
        except ValueError as exc:
            logger.error("[QuantumFeaturePipeline] OHLCV normalization failed: %s", exc)
            return np.zeros((1, _N_FEATURES), dtype=np.float64)

        # ── Step 2: Classical technical features (over full history) ─────
        try:
            classical_df: pd.DataFrame = self._compute_classical_features(df)
        except Exception as exc:
            logger.error(
                "[QuantumFeaturePipeline] Classical feature computation failed: %s",
                exc,
            )
            return np.zeros((1, _N_FEATURES), dtype=np.float64)

        # Extract the live bar's classical features (last row)
        classical_live: np.ndarray = classical_df.iloc[-1:].values  # shape (1, 7)

        # ── Step 3: SMC features ─────────────────────────────────────────
        smc_row: Dict[str, float] = self._build_smc_row(smc_params)
        smc_live: np.ndarray = np.array([
            smc_row["ob_distance_pct"],
            smc_row["fvg_present"],
            smc_row["swing_structure"],
            smc_row["liquidity_sweep_flag"],
        ], dtype=np.float64).reshape(1, 4)  # shape (1, 4)

        # ── Step 4: TimesFM foundation model features ────────────────────
        timesfm_row: Dict[str, float] = self._extract_timesfm_row(df)
        timesfm_live: np.ndarray = np.array([
            timesfm_row["timesfm_alpha_delta"],
            timesfm_row["forecast_momentum_slope"],
            timesfm_row["forecast_variance_risk"],
        ], dtype=np.float64).reshape(1, 3)  # shape (1, 3)

        # ── Step 5: Concatenate all tracks → (1, 14) ────────────────────
        live_row_raw: np.ndarray = np.concatenate(
            [classical_live, smc_live, timesfm_live], axis=1
        )  # shape (1, 14)

        # ── Step 6: Leakage-free rolling-window scaling ──────────────────
        # Build the history matrix for scaler fitting: ALL classical + SMC
        # features over the past ``scaling_window`` bars (excluding live bar).
        # TimesFM rows in history are set to 0 (not computed for training set).
        history_classical: np.ndarray = classical_df.iloc[-(self._scaling_window + 1):-1].values
        n_hist: int = len(history_classical)

        # Pad SMC and TimesFM history with zeros (we only have live SMC/TF values)
        smc_history: np.ndarray    = np.zeros((n_hist, 4), dtype=np.float64)
        timesfm_history: np.ndarray = np.zeros((n_hist, 3), dtype=np.float64)

        history_matrix: np.ndarray = np.concatenate(
            [history_classical, smc_history, timesfm_history], axis=1
        )  # shape (n_hist, 14)

        if n_hist < 2:
            logger.warning(
                "[QuantumFeaturePipeline] History too short to fit scaler "
                "(%d rows). Returning unscaled feature row.",
                n_hist,
            )
            self._call_count += 1
            return live_row_raw

        try:
            scaled_row: np.ndarray = self._scaler.fit_transform_row(
                history_matrix=history_matrix,
                live_row=live_row_raw,
            )
        except Exception as exc:
            logger.error(
                "[QuantumFeaturePipeline] Scaler failed: %s. "
                "Returning unscaled row.",
                exc,
            )
            scaled_row = live_row_raw

        self._call_count += 1
        elapsed_ms: float = (time.perf_counter() - t0) * 1000.0

        logger.debug(
            "[QuantumFeaturePipeline] #%d | elapsed=%.1fms | "
            "timesfm_valid=%s | shape=%s",
            self._call_count,
            elapsed_ms,
            timesfm_row["timesfm_alpha_delta"] != 0.0,
            scaled_row.shape,
        )

        return scaled_row  # shape (1, 14)

    # -------------------------------------------------------------------
    # Properties & Diagnostics
    # -------------------------------------------------------------------

    @property
    def feature_names(self) -> List[str]:
        """Ordered list of feature column names (length = 14)."""
        return list(FEATURE_NAMES)

    @property
    def n_features(self) -> int:
        """Total number of features in the output vector."""
        return _N_FEATURES

    @property
    def call_count(self) -> int:
        """Total number of ``transform_live_row`` calls made."""
        return self._call_count

    @property
    def timesfm_ready(self) -> bool:
        """True if the TimesFM extractor is loaded and ready for inference."""
        return self._timesfm.model_ready

    def status_dict(self) -> Dict[str, object]:
        """
        Return a structured health-check and configuration dictionary.

        Returns
        -------
        dict
            Keys: ``n_features``, ``feature_names``, ``scaling_window``,
            ``call_count``, ``timesfm_status``.
        """
        return {
            "n_features":     _N_FEATURES,
            "feature_names":  FEATURE_NAMES,
            "scaling_window": self._scaling_window,
            "call_count":     self._call_count,
            "timesfm_status": self._timesfm.status_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"QuantumFeaturePipeline("
            f"n_features={_N_FEATURES}, "
            f"scaling_window={self._scaling_window}, "
            f"calls={self._call_count}, "
            f"timesfm_ready={self.timesfm_ready})"
        )
