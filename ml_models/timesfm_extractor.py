"""
==============================================================================
ml_models/timesfm_extractor.py — Quantum FSM Pro V4.2 Elite
==============================================================================
Module : TimesFM Zero-Shot Feature Extraction Engine
Author : Principal Quantitative Research Engineer
Version: 4.2.0

Overview
--------
Replaces the legacy LSTM naive-predictor trap with a patch-based
Transformer feature extractor built on Google's TimesFM 2.0 foundation
model. Rather than producing raw price predictions (which fall into the
structural-lag trap), this module extracts *three mathematical feature
tensors* from the forecast distribution that serve as high-information
inputs to the downstream Random Forest ensemble classifier.

Why TimesFM over LSTM
----------------------
The LSTM "Naive Predictor Trap":
    LSTM learns to output  ŷ_{t+1} ≈ y_t  (yesterday's close ≈ today's close).
    This produces RMSE close to 0 on training data but zero directional
    edge in live trading — the model predicts nothing, it merely echoes.

TimesFM as Feature Extractor (not predictor):
    - TimesFM's forecast *distribution* (mean, slope, variance) encodes
      the model's structural view of the regime.
    - These 3 derived scalars are orthogonal to price level — they encode
      *direction*, *velocity*, and *uncertainty*, which are the true
      edge-generating signals for a classification forest.

Architecture
------------
TimesFM 2.0 is a patched-decoder Transformer:
    input_patch_len  = 32   (each patch = 32 bars)
    output_patch_len = 128
    num_layers       = 20
    model_dims       = 1280
    num_heads        = 16

Feature Engineering Mathematics
---------------------------------
Given:
    close_t          : last observed closing price (the anchor)
    F = [f₁, f₂, ..., f₁₀] : 10-step mean forecast vector from TimesFM
    Q_low, Q_high   : 10th and 90th percentile quantile forecasts

1. timesfm_alpha_delta (directional momentum signal)
   ─────────────────────────────────────────────────
   Formula:  α = (mean(F) − close_t) / close_t
   Economic interpretation:
       α > 0 → model expects price to rise over the 10-bar horizon (bullish)
       α < 0 → model expects price to fall (bearish)
       |α|   → magnitude of expected move as fraction of current price

2. forecast_momentum_slope (structural velocity)
   ──────────────────────────────────────────────
   Formula:  β = OLS slope fitted over (x=[1..10], y=F)
             β = Σ((xᵢ - x̄)(fᵢ - f̄)) / Σ((xᵢ - x̄)²)
   Economic interpretation:
       β > 0 → forecast trajectory is accelerating upward (trend conviction)
       β < 0 → trajectory is decelerating / reversing
       |β|   → rate of directional change per forecast bar

3. forecast_variance_risk (predictive uncertainty for Grid Pro)
   ─────────────────────────────────────────────────────────────
   Formula:  σ² = Var(Q_high − Q_low) over the 10-bar horizon
   If quantile outputs unavailable: σ² = Var(F)  (fallback)
   Economic interpretation:
       σ² → width of the prediction interval; high values signal
            regime uncertainty → Grid Pro should widen spacing
       σ² → low values signal high model conviction → tight grid

Usage
-----
    from ml_models.timesfm_extractor import TimesFMFeatureExtractor
    import pandas as pd

    extractor = TimesFMFeatureExtractor()
    features  = extractor.extract_foundation_features(ohlcv_df)
    # {
    #   "timesfm_alpha_delta":      0.00142,
    #   "forecast_momentum_slope":  0.000087,
    #   "forecast_variance_risk":   1.4e-07,
    #   "forecast_vector":          [1.0851, 1.0855, ...],
    #   "last_close":               1.08401,
    #   "is_valid":                 True,
    #   "backend":                  "cuda",
    #   "inference_count":          12,
    # }
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Dict, Final, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    from pydantic import BaseModel, Field, validator as field_validator  # Pydantic v1 fallback

# ---------------------------------------------------------------------------
# Internal project utilities (validated as existing in utils.py)
# ---------------------------------------------------------------------------
try:
    from ml_models.utils import (
        validate_price_series,
        build_zeroed_forecast_metrics,
        linear_trend_direction,
        percent_return,
        safe_fill_series,
    )
except ImportError:
    def validate_price_series(s, min_len=64): return s is not None and len(s) >= min_len
    def build_zeroed_forecast_metrics(backend="cpu", inference_count=0, last_close=0.0):
        return {
            "timesfm_alpha_delta": 0.0, "forecast_momentum_slope": 0.0,
            "forecast_variance_risk": 0.0, "forecast_vector": [],
            "last_close": float(last_close), "is_valid": False,
            "backend": backend, "inference_count": int(inference_count),
        }
    def linear_trend_direction(vals): return 0.0
    def percent_return(a, b): return (b - a) / a if a else 0.0
    def safe_fill_series(s): return s.ffill().bfill()

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger: logging.Logger = logging.getLogger("ml_models.timesfm_extractor")

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: HuggingFace repo for TimesFM 2.5 PyTorch (Windows-compatible).
_REPO_ID_DEFAULT: Final[str] = "google/timesfm-2.5-200m-pytorch"

#: Strict 64-bar input window as specified in the architectural directive.
_CONTEXT_LEN: Final[int] = 64

#: 10-bar forecast horizon — the feature derivation window.
_HORIZON_LEN: Final[int] = 10

#: Minimum OLS slope magnitude to consider the forecast trending.
_SLOPE_THRESHOLD: Final[float] = 1e-7

#: Keys guaranteed to exist in every returned feature dict.
_FEATURE_KEYS: Final[Tuple[str, ...]] = (
    "timesfm_alpha_delta",
    "forecast_momentum_slope",
    "forecast_variance_risk",
    "forecast_vector",
    "last_close",
    "is_valid",
    "backend",
    "inference_count",
)


# ===========================================================================
# Pydantic v2 Input Validation Schema
# ===========================================================================

class OHLCVInputSchema(BaseModel):
    """
    Pydantic v2 schema that validates the OHLCV DataFrame structure passed
    to ``extract_foundation_features`` before any computation occurs.

    Attributes
    ----------
    n_rows : int
        Number of rows in the input DataFrame.  Must be ≥ _CONTEXT_LEN (64).
    has_close : bool
        True when the DataFrame contains a ``close`` (or ``Close``) column.
    close_min : float
        Minimum close price.  Must be strictly positive (price > 0).
    n_nan : int
        Total NaN count across the close column.  Must be 0.
    """
    model_config = {"frozen": True}

    n_rows:    int   = Field(..., ge=_CONTEXT_LEN, description="Row count ≥ 64 required.")
    has_close: bool  = Field(..., description="DataFrame must contain a 'close' column.")
    close_min: float = Field(..., gt=0.0, description="All close prices must be > 0.")
    n_nan:     int   = Field(..., ge=0, le=0, description="Zero NaN values allowed.")

    @field_validator("has_close")
    @classmethod
    def _check_has_close(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "OHLCV DataFrame must contain a 'close' (or 'Close') column."
            )
        return v


def _validate_ohlcv_dataframe(
    ohlcv_df: pd.DataFrame,
    context_len: int,
) -> Tuple[bool, Optional[pd.Series]]:
    """
    Validate the incoming OHLCV DataFrame and extract the clean close series.

    Parameters
    ----------
    ohlcv_df : pd.DataFrame
        Raw OHLCV data from the market feed.
    context_len : int
        Minimum row count required.

    Returns
    -------
    Tuple[bool, Optional[pd.Series]]
        (True, close_series) on success; (False, None) on any validation failure.
    """
    if not isinstance(ohlcv_df, pd.DataFrame):
        logger.error(
            "[TimesFMFeatureExtractor] Input must be a pd.DataFrame; "
            "received %s.", type(ohlcv_df).__name__
        )
        return False, None

    # Normalise column names to lowercase
    col_lower: Dict[str, str] = {c: c.lower() for c in ohlcv_df.columns}
    df = ohlcv_df.rename(columns=col_lower)

    if "close" not in df.columns:
        logger.error(
            "[TimesFMFeatureExtractor] DataFrame missing 'close' column. "
            "Available columns: %s", list(ohlcv_df.columns)
        )
        return False, None

    close: pd.Series = df["close"].copy()

    # Forward-fill isolated gaps (market close / data hiccups)
    close = safe_fill_series(close, method="ffill")

    n_nan: int = int(close.isna().sum())
    n_rows: int = len(close)

    try:
        OHLCVInputSchema(
            n_rows=n_rows,
            has_close=True,
            close_min=float(close.min()) if n_nan == 0 else 1.0,
            n_nan=n_nan,
        )
    except Exception as exc:
        logger.error(
            "[TimesFMFeatureExtractor] Input validation failed: %s", exc
        )
        return False, None

    return True, close


# ===========================================================================
# Feature Output Schema
# ===========================================================================

def _zeroed_feature_dict(
    backend: str = "cpu",
    inference_count: int = 0,
) -> Dict[str, object]:
    """
    Return a fully zeroed feature dict with all required keys populated.

    Used as a safe fallback when inference fails or the model is not ready.
    The ``is_valid=False`` flag signals to the downstream pipeline that these
    values must NOT be used for live trading decisions.

    Returns
    -------
    dict
        All keys from ``_FEATURE_KEYS`` with zero / empty values.
    """
    return {
        "timesfm_alpha_delta":     0.0,
        "forecast_momentum_slope": 0.0,
        "forecast_variance_risk":  0.0,
        "forecast_vector":         [0.0] * _HORIZON_LEN,
        "last_close":              0.0,
        "is_valid":                False,
        "backend":                 backend,
        "inference_count":         inference_count,
    }


# ===========================================================================
# OLS Slope Calculator
# ===========================================================================

def _compute_ols_slope(y: np.ndarray) -> float:
    """
    Compute the Ordinary Least Squares slope of a 1-D array over its indices.

    Formula
    -------
        x  = [1, 2, ..., n]
        β  = Σ((xᵢ − x̄)(yᵢ − ȳ)) / Σ((xᵢ − x̄)²)

    Parameters
    ----------
    y : np.ndarray
        1-D array of forecast values.

    Returns
    -------
    float
        The OLS slope coefficient β.  Returns 0.0 if computation fails
        (e.g., constant series, length < 2).
    """
    n: int = len(y)
    if n < 2:
        return 0.0

    x: np.ndarray = np.arange(1, n + 1, dtype=np.float64)
    x_mean: float = float(np.mean(x))
    y_mean: float = float(np.mean(y))

    numerator:   float = float(np.sum((x - x_mean) * (y - y_mean)))
    denominator: float = float(np.sum((x - x_mean) ** 2))

    if abs(denominator) < 1e-15:
        return 0.0

    slope: float = numerator / denominator
    return slope


# ===========================================================================
# TimesFMFeatureExtractor
# ===========================================================================

class TimesFMFeatureExtractor:
    """
    Production-grade zero-shot feature extraction engine based on Google
    TimesFM 2.0 (PyTorch backend).

    This class wraps the existing ``TimesFMForecaster`` inference engine and
    extends it with the three canonical feature engineering operations
    required by the Quantum FSM Pro V4.2 Elite pipeline:

        1. ``timesfm_alpha_delta``      — directional momentum signal
        2. ``forecast_momentum_slope``  — structural velocity (OLS β)
        3. ``forecast_variance_risk``   — predictive uncertainty (σ²)

    Unlike the legacy LSTM that outputs a raw price prediction
    (fallen into the naive-predictor trap), this extractor outputs
    *distribution statistics* that are orthogonal to the price level
    and carry genuine directional information.

    Parameters
    ----------
    context_len : int
        Historical bar window fed to the model.  Clamped to a multiple
        of 32 (the model's patch_len).  Default: 64 (minimum viable,
        as specified in the architectural directive).
    horizon_len : int
        Number of forecast steps to produce.  Features are derived from
        the full ``horizon_len`` distribution.  Default: 10.
    lazy_load : bool
        If True, defer model loading to the first ``extract_foundation_features``
        call.  Default: False (load at construction for production use).
    torch_compile : bool
        If True, compile the decode graph for accelerated inference.
        Default: True.
    repo_id : str
        HuggingFace repo or local path for the TimesFM weights.

    Attributes
    ----------
    _model_ready : bool
        True when the underlying TimesFMForecaster is loaded and compiled.
    _backend : str
        Active compute backend: ``"cuda"`` or ``"cpu"``.
    _inference_count : int
        Monotonic counter of successful feature extractions.

    Examples
    --------
    >>> extractor = TimesFMFeatureExtractor(lazy_load=True)
    >>> features  = extractor.extract_foundation_features(ohlcv_df)
    >>> alpha = features["timesfm_alpha_delta"]
    >>> slope = features["forecast_momentum_slope"]
    >>> risk  = features["forecast_variance_risk"]
    """

    def __init__(
        self,
        context_len:   int  = _CONTEXT_LEN,
        horizon_len:   int  = _HORIZON_LEN,
        lazy_load:     bool = True,
        torch_compile: bool = False,
        repo_id:       str  = _REPO_ID_DEFAULT,
    ) -> None:
        # Clamp context_len to nearest multiple of 32 (TimesFM patch_len)
        if context_len % 32 != 0:
            adjusted = max(64, (context_len // 32) * 32)
            logger.warning(
                "[TimesFMFeatureExtractor] context_len=%d is not a multiple of 32. "
                "Adjusting to %d.",
                context_len, adjusted,
            )
            context_len = adjusted

        self._context_len:     int  = context_len
        self._horizon_len:     int  = max(1, horizon_len)
        self._inference_count: int  = 0
        self._model_ready:     bool = False
        self._backend:         str  = "cpu"
        self._forecaster: Optional[object] = None

        # Detect compute backend before loading weights
        self._backend = self._detect_compute_backend()

        logger.info(
            "[TimesFMFeatureExtractor] Initializing | context_len=%d | "
            "horizon_len=%d | backend=%s | lazy_load=%s",
            self._context_len, self._horizon_len, self._backend, lazy_load,
        )

        if not lazy_load:
            self._initialize_forecaster(repo_id=repo_id, torch_compile=torch_compile)

    # -------------------------------------------------------------------
    # Backend Detection
    # -------------------------------------------------------------------

    def _detect_compute_backend(self) -> str:
        """
        Detect CUDA GPU availability and select the optimal compute backend.

        Implements strict fallback: CUDA → CPU.  Never raises — any detection
        failure silently defaults to CPU to preserve system stability.

        Returns
        -------
        str
            ``"cuda"`` if a CUDA-capable device is found; ``"cpu"`` otherwise.
        """
        try:
            import torch
            if torch.cuda.is_available():
                device_name: str = torch.cuda.get_device_name(0)
                vram_gb: float = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                logger.info(
                    "[TimesFMFeatureExtractor] CUDA GPU detected: %s | VRAM: %.1f GB. "
                    "TimesFM will use GPU inference for optimal latency.",
                    device_name, vram_gb,
                )
                return "cuda"
            else:
                logger.info(
                    "[TimesFMFeatureExtractor] No CUDA GPU detected. "
                    "Falling back to CPU inference (~1-3s per call on bare-metal Windows). "
                    "GPU acceleration: install CUDA drivers and torch[cuda]."
                )
                return "cpu"
        except ImportError:
            logger.warning(
                "[TimesFMFeatureExtractor] PyTorch not installed — backend=cpu. "
                "Install: pip install torch --index-url https://download.pytorch.org/whl/cpu"
            )
            return "cpu"
        except Exception as exc:
            logger.warning(
                "[TimesFMFeatureExtractor] Backend detection error (defaulting to cpu): %s",
                exc,
            )
            return "cpu"

    # -------------------------------------------------------------------
    # Forecaster Initialization
    # -------------------------------------------------------------------

    def _initialize_forecaster(
        self,
        repo_id: str = _REPO_ID_DEFAULT,
        torch_compile: bool = True,
    ) -> None:
        """
        Load and compile the TimesFM 2.0 foundation model.

        Delegates to the existing ``TimesFMForecaster`` class which already
        handles the full HuggingFace download, caching, and compile pipeline.
        This avoids duplicating weight loading logic.

        On failure (ImportError, OOM, network error), the extractor enters
        degraded mode: ``_model_ready=False``, all feature extractions return
        zeroed outputs with ``is_valid=False``.

        Parameters
        ----------
        repo_id : str
            HuggingFace repo or local weights directory path.
        torch_compile : bool
            Whether to JIT-compile the decode function.
        """
        try:
            # Use the existing production-grade TimesFMForecaster
            from ml_models.timesfm_predictor import TimesFMForecaster

            self._forecaster = TimesFMForecaster(
                context_len=self._context_len,
                horizon_len=self._horizon_len,
                repo_id=repo_id,
                lazy_load=False,
                torch_compile=torch_compile,
            )
            self._model_ready = self._forecaster.model_ready
            self._backend     = self._forecaster.backend

            if self._model_ready:
                logger.info(
                    "[TimesFMFeatureExtractor] TimesFM 2.0 ready | "
                    "backend=%s | context_len=%d | horizon_len=%d",
                    self._backend, self._context_len, self._horizon_len,
                )
            else:
                logger.warning(
                    "[TimesFMFeatureExtractor] TimesFMForecaster loaded but "
                    "model_ready=False. Feature extractions will return zeroed outputs."
                )

        except ImportError as exc:
            logger.error(
                "[TimesFMFeatureExtractor] Cannot import TimesFMForecaster: %s\n"
                "Ensure ml_models/timesfm_predictor.py is present.\n"
                "Extractor entering degraded (zeroed) mode.",
                exc,
            )
            self._model_ready = False

        except Exception as exc:
            logger.error(
                "[TimesFMFeatureExtractor] Model initialization failed: %s\n%s\n"
                "Extractor entering degraded (zeroed) mode.",
                exc,
                traceback.format_exc(),
            )
            self._model_ready = False

    # -------------------------------------------------------------------
    # Primary Feature Extraction Method
    # -------------------------------------------------------------------

    def extract_foundation_features(
        self,
        ohlcv_df: pd.DataFrame,
    ) -> Dict[str, object]:
        """
        Execute zero-shot TimesFM inference and derive the three canonical
        foundation model features.

        This is the primary entry point for the ``QuantumFeaturePipeline``.

        Input Contract
        --------------
        ``ohlcv_df`` must satisfy ALL of the following (validated by Pydantic):
            - Must be a ``pd.DataFrame`` with a ``"close"`` (or ``"Close"``) column
            - Must contain ≥ ``context_len`` rows (default: 64)
            - Close prices must all be strictly positive (no zero or negative prices)
            - After forward-filling, zero NaN values are permitted

        Execution Pipeline
        ------------------
        1. Validate ``ohlcv_df`` via ``OHLCVInputSchema`` (Pydantic v2).
        2. Extract the last ``context_len`` close prices → context window.
        3. Run ``TimesFMForecaster.generate_forecast_metrics()`` for the
           ``forecast_vector`` (10-step mean forecast sequence).
        4. Compute the three derived features from the forecast distribution:
               a. ``timesfm_alpha_delta``      : (mean(F) - close_t) / close_t
               b. ``forecast_momentum_slope``  : OLS β over F[1..10]
               c. ``forecast_variance_risk``   : Var(F[1..10])
        5. Return a guaranteed-non-None feature dict.

        Parameters
        ----------
        ohlcv_df : pd.DataFrame
            OHLCV bar data from the Hyperliquid/OpenBB market stream.
            Minimum length: ``context_len`` rows.  Required columns: ``"close"``.

        Returns
        -------
        Dict[str, object]
            Feature dictionary with the following keys:

            ``"timesfm_alpha_delta"`` : float
                Directional momentum signal.
                Formula: (mean(F₁..₁₀) - close_t) / close_t
                Range: typically ±0.01 for Forex; dimensionless ratio.

            ``"forecast_momentum_slope"`` : float
                Structural velocity (OLS slope) over the 10-bar forecast.
                Formula: OLS β over (x=[1..10], y=F₁..₁₀)
                Positive → upward acceleration; negative → reversal.

            ``"forecast_variance_risk"`` : float
                Predictive uncertainty for the Grid Pro spacing engine.
                Formula: Var(F₁..₁₀)
                High variance → widen grid; low variance → tight grid.

            ``"forecast_vector"`` : List[float]
                The raw 10-step mean forecast sequence from TimesFM.

            ``"last_close"`` : float
                The last observed close price (normalisation anchor).

            ``"is_valid"`` : bool
                True if inference succeeded and features are usable.
                False if any validation or inference step failed.

            ``"backend"`` : str
                Active compute backend: ``"cuda"`` or ``"cpu"``.

            ``"inference_count"`` : int
                Monotonic count of successful extractions since startup.

        Examples
        --------
        >>> extractor = TimesFMFeatureExtractor(context_len=64, horizon_len=10)
        >>> features  = extractor.extract_foundation_features(ohlcv_df)
        >>> if features["is_valid"]:
        ...     alpha = features["timesfm_alpha_delta"]   # +0.00142 → bullish
        ...     slope = features["forecast_momentum_slope"]
        ...     risk  = features["forecast_variance_risk"]
        """
        t0 = time.perf_counter()

        # ── Lazy load on first call ──────────────────────────────────────
        if not self._model_ready and self._forecaster is None:
            logger.info(
                "[TimesFMFeatureExtractor] Lazy loading model on first call..."
            )
            self._initialize_forecaster()

        if not self._model_ready:
            logger.warning(
                "[TimesFMFeatureExtractor] Model not ready. "
                "Returning zeroed features with is_valid=False."
            )
            return _zeroed_feature_dict(self._backend, self._inference_count)

        # ── Step 1: Validate OHLCV DataFrame ────────────────────────────
        valid, close_series = _validate_ohlcv_dataframe(ohlcv_df, self._context_len)
        if not valid or close_series is None:
            return _zeroed_feature_dict(self._backend, self._inference_count)

        # ── Step 2: Extract context window (last 64 bars) ────────────────
        context_close: pd.Series = close_series.iloc[-self._context_len:]
        last_close: float = float(context_close.iloc[-1])

        if last_close <= 0.0:
            logger.error(
                "[TimesFMFeatureExtractor] last_close=%.8f ≤ 0 — "
                "data integrity violation. Returning zeroed features.",
                last_close,
            )
            return _zeroed_feature_dict(self._backend, self._inference_count)

        # ── Step 3: Run TimesFM zero-shot inference ──────────────────────
        try:
            raw_metrics: Dict[str, object] = self._forecaster.generate_forecast_metrics(
                context_close
            )
        except Exception as exc:
            logger.error(
                "[TimesFMFeatureExtractor] Forecaster call failed: %s\n%s",
                exc, traceback.format_exc(),
            )
            return _zeroed_feature_dict(self._backend, self._inference_count)

        if not raw_metrics.get("is_valid", False):
            logger.warning(
                "[TimesFMFeatureExtractor] TimesFMForecaster returned "
                "is_valid=False. Returning zeroed features."
            )
            return _zeroed_feature_dict(self._backend, self._inference_count)

        # ── Step 4: Extract and validate the forecast vector ─────────────
        forecast_vector_raw: List[float] = raw_metrics.get("forecast_vector", [])
        if not forecast_vector_raw:
            logger.error(
                "[TimesFMFeatureExtractor] Empty forecast_vector from forecaster."
            )
            return _zeroed_feature_dict(self._backend, self._inference_count)

        # Ensure we have exactly horizon_len values; pad or trim as needed
        fv: np.ndarray = np.asarray(forecast_vector_raw, dtype=np.float64)
        if len(fv) < self._horizon_len:
            # Pad with last forecast value (flat extrapolation)
            pad_len = self._horizon_len - len(fv)
            fv = np.concatenate([fv, np.full(pad_len, fv[-1])])
            logger.debug(
                "[TimesFMFeatureExtractor] forecast_vector padded from %d to %d.",
                len(forecast_vector_raw), self._horizon_len,
            )
        else:
            fv = fv[:self._horizon_len]

        # Sanitize: replace any NaN in the forecast vector
        nan_mask: np.ndarray = np.isnan(fv)
        if nan_mask.any():
            n_nan = int(nan_mask.sum())
            logger.warning(
                "[TimesFMFeatureExtractor] %d NaN(s) in forecast_vector; "
                "replacing with last_close.",
                n_nan,
            )
            fv = np.where(nan_mask, last_close, fv)

        # ── Step 5a: timesfm_alpha_delta ─────────────────────────────────
        # Formula: (mean(F) − close_t) / close_t
        # Represents the percentage expected move over the forecast horizon.
        forecast_mean: float = float(np.mean(fv))
        alpha_delta: float   = (forecast_mean - last_close) / last_close
        alpha_delta           = float(np.clip(alpha_delta, -1.0, 1.0))  # cap at ±100%

        # ── Step 5b: forecast_momentum_slope ─────────────────────────────
        # Formula: OLS β fitted over (x=[1..horizon], y=F)
        # Represents the structural velocity of the forecast trajectory.
        momentum_slope: float = _compute_ols_slope(fv)

        # ── Step 5c: forecast_variance_risk ──────────────────────────────
        # Formula: Var(F[1..horizon])
        # Represents predictive uncertainty for the Grid Pro spacing engine.
        variance_risk: float = float(np.var(fv))

        # ── Step 6: Assemble output dictionary ───────────────────────────
        self._inference_count += 1
        elapsed_ms: float = (time.perf_counter() - t0) * 1000.0

        features: Dict[str, object] = {
            "timesfm_alpha_delta":     alpha_delta,
            "forecast_momentum_slope": momentum_slope,
            "forecast_variance_risk":  variance_risk,
            "forecast_vector":         fv.tolist(),
            "last_close":              last_close,
            "is_valid":                True,
            "backend":                 self._backend,
            "inference_count":         self._inference_count,
        }

        logger.info(
            "[TimesFMFeatureExtractor] #%d | last_close=%.6f | "
            "alpha_delta=%+.6f | slope=%+.8f | variance_risk=%.4e | "
            "elapsed=%.1fms | backend=%s",
            self._inference_count,
            last_close,
            alpha_delta,
            momentum_slope,
            variance_risk,
            elapsed_ms,
            self._backend,
        )

        return features

    # -------------------------------------------------------------------
    # Warm-up (pre-compiles the torch decode graph)
    # -------------------------------------------------------------------

    def warm_up(self) -> bool:
        """
        Execute a synthetic inference pass to pre-compile the PyTorch decode
        graph before the first live bar arrives.

        Generates ``context_len + 32`` bars of synthetic EURUSD-like prices
        and runs a full feature extraction cycle.

        Returns
        -------
        bool
            True if warm-up succeeded (``is_valid=True`` returned).
            False if the model is not loaded or inference fails.
        """
        rng = np.random.default_rng(seed=42)
        n: int = self._context_len + 32
        synthetic_close: np.ndarray = (
            1.0850 + np.cumsum(rng.normal(0.0, 0.0005, n))
        )
        # Ensure all prices are positive
        synthetic_close = np.abs(synthetic_close - synthetic_close.min()) + 0.001

        synthetic_df = pd.DataFrame({
            "open":   synthetic_close * 0.9999,
            "high":   synthetic_close * 1.0002,
            "low":    synthetic_close * 0.9998,
            "close":  synthetic_close,
            "volume": np.ones(n) * 1000.0,
        })

        logger.info(
            "[TimesFMFeatureExtractor] Executing warm-up inference "
            "(synthetic n=%d bars) ...", n,
        )
        result = self.extract_foundation_features(synthetic_df)
        success: bool = bool(result.get("is_valid", False))

        if success:
            logger.info(
                "[TimesFMFeatureExtractor] Warm-up complete. "
                "Decode graph compiled. Latency-optimal for live inference."
            )
        else:
            logger.warning(
                "[TimesFMFeatureExtractor] Warm-up FAILED (model_ready=%s). "
                "Live features will be zeroed until model loads.",
                self._model_ready,
            )
        return success

    # -------------------------------------------------------------------
    # Properties & Diagnostics
    # -------------------------------------------------------------------

    @property
    def model_ready(self) -> bool:
        """True if the underlying TimesFM model is loaded and ready."""
        return self._model_ready

    @property
    def backend(self) -> str:
        """Active compute backend: ``'cuda'`` or ``'cpu'``."""
        return self._backend

    @property
    def context_len(self) -> int:
        """Configured historical context window (number of bars)."""
        return self._context_len

    @property
    def horizon_len(self) -> int:
        """Configured forecast horizon (number of future bars)."""
        return self._horizon_len

    @property
    def inference_count(self) -> int:
        """Total successful feature extractions since instantiation."""
        return self._inference_count

    def status_dict(self) -> Dict[str, object]:
        """
        Return a structured health-check and configuration dictionary.

        Returns
        -------
        dict
            Keys: ``model_ready``, ``backend``, ``context_len``,
            ``horizon_len``, ``inference_count``.
        """
        return {
            "model_ready":     self._model_ready,
            "backend":         self._backend,
            "context_len":     self._context_len,
            "horizon_len":     self._horizon_len,
            "inference_count": self._inference_count,
        }

    def __repr__(self) -> str:
        status = "READY" if self._model_ready else "DEGRADED"
        return (
            f"TimesFMFeatureExtractor("
            f"status={status}, "
            f"backend={self._backend!r}, "
            f"context_len={self._context_len}, "
            f"horizon_len={self._horizon_len}, "
            f"inferences={self._inference_count})"
        )


# ===========================================================================
# 2026 Production License Guard & Non-Blocking CachedTimesFMService
# ===========================================================================

_APACHE2_PRODUCTION_PREFIXES: Final[Tuple[str, ...]] = (
    "google/timesfm-2.5",
    "google/timesfm-2.0",
    "google/timesfm-1.0",
)


def validate_timesfm_repo_license(repo_id: str, allow_non_commercial: bool = False) -> Tuple[bool, str]:
    """
    حارس الترخيص الإنتاجي (2026):
      - أوزان TimesFM 2.5 (وما قبلها) مرخّصة بـ Apache-2.0 ومسموح بتشغيلها تجارياً/إنتاجياً محلياً.
      - أوزان TimesFM 3.0 تخضع لرخصة غير تجارية (timesfm-non-commercial-license-v1.0)
        عند الاستضافة الذاتية، لذا تُمنع في الإنتاج ما لم يُسمح صراحةً بالاستخدام البحثي غير التجاري.
    """
    rid = (repo_id or "").strip().lower()
    if any(rid.startswith(p) for p in _APACHE2_PRODUCTION_PREFIXES):
        return True, f"Apache-2.0 production-safe weights ({repo_id})"
    if "timesfm-3" in rid and not allow_non_commercial:
        return False, (
            f"Blocked non-commercial self-hosted weights '{repo_id}' in production mode. "
            "Use 'google/timesfm-2.5-200m-pytorch' (Apache-2.0) or Google Cloud BigQuery ML."
        )
    return True, f"Custom/research weights permitted ({repo_id})"


class CachedTimesFMService:
    """
    غلاف غير معطّل (Zero-Latency Guard) لـ TimesFMFeatureExtractor:
      - تحميل كسول (Lazy Load) للأوزان حتى لا يبطئ إقلاع النظام أو اختبارات الوحدة.
      - كاش لكل رمز بمدة صلاحية `cache_ttl_sec` (افتراضياً 300 ثانية = إغلاق شمعة M5)
        حتى لا يعمل الاستدلال داخل دورة الـ 5 ثوانٍ في MarketAnalystAgent.
      - تدهور آمن (Graceful Fallback) يعيد مقاييس صفرية مع `is_valid=False`
        إن لم تكن حزمة `timesfm` أو الأوزان محمَّلة بعد.
    """

    def __init__(
        self,
        repo_id: str = _REPO_ID_DEFAULT,
        cache_ttl_sec: float = 300.0,
        enabled: bool = True,
        allow_non_commercial: bool = False,
        extractor=None,
    ):
        ok, reason = validate_timesfm_repo_license(repo_id, allow_non_commercial=allow_non_commercial)
        if not ok:
            raise ValueError(reason)
        self.repo_id = repo_id
        self.cache_ttl_sec = max(0.0, float(cache_ttl_sec))
        self.enabled = bool(enabled)
        self._extractor = extractor
        self._init_attempted = extractor is not None
        self._cache: Dict[str, Tuple[float, Dict[str, object]]] = {}

    def _ensure_extractor(self):
        if self._extractor is not None or self._init_attempted:
            return self._extractor
        self._init_attempted = True
        try:
            self._extractor = TimesFMFeatureExtractor(repo_id=self.repo_id)
        except Exception as exc:
            logger.warning("CachedTimesFMService fallback (extractor unavailable): %s", exc)
            self._extractor = None
        return self._extractor

    def invalidate(self, symbol: Optional[str] = None) -> None:
        if symbol is None:
            self._cache.clear()
        else:
            self._cache.pop(symbol, None)

    def get_features(
        self,
        symbol: str,
        df: Optional[pd.DataFrame],
        now_monotonic: Optional[float] = None,
    ) -> Dict[str, object]:
        if not self.enabled or df is None or len(df) < _CONTEXT_LEN:
            return build_zeroed_forecast_metrics(backend="disabled", inference_count=0, last_close=0.0)

        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        if self.cache_ttl_sec > 0 and symbol in self._cache:
            ts, cached = self._cache[symbol]
            if (now - ts) < self.cache_ttl_sec:
                return dict(cached)

        ext = self._ensure_extractor()
        if ext is None:
            return build_zeroed_forecast_metrics(backend="fallback", inference_count=0, last_close=0.0)

        try:
            res = ext.extract_foundation_features(df)
        except Exception as exc:
            logger.warning("CachedTimesFMService inference error for %s: %s", symbol, exc)
            return build_zeroed_forecast_metrics(backend="error_fallback", inference_count=0, last_close=0.0)

        if self.cache_ttl_sec > 0:
            self._cache[symbol] = (now, dict(res))
        return res
