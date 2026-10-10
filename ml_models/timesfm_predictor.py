"""
==============================================================
ml_models/timesfm_predictor.py  —  Google TimesFM 2.0 Inference Engine
==============================================================
Production-safe wrapper around Google TimesFM 2.0 (timesfm library v2.0.1+)
for zero-shot time-series forecasting using the PyTorch backend.

API Notes (v2.0.1)
------------------
The timesfm 2.0.x API changed significantly from 1.0:

    OLD (timesfm 1.0):
        timesfm.TimesFm(hparams=..., checkpoint=...)
        model.forecast(inputs=..., freq=...)

    NEW (timesfm 2.0.1):
        timesfm.TimesFM_2p5_200M_torch.from_pretrained(repo_id)
        model.compile(ForecastConfig(...))
        point_forecast, full_forecast = model.compiled_decode(horizon, inputs, masks)

HuggingFace Checkpoint
-----------------------
    PyTorch (recommended on Windows):
        ``google/timesfm-2.0-500m-pytorch``
        File: ``model.safetensors`` (~780MB)
        Local cache: ``C:\\Users\\<user>\\.cache\\huggingface\\hub\\
                       models--google--timesfm-2.0-500m-pytorch\\``

    JAX (Linux/WSL2 only):
        ``google/timesfm-1.0-200m``
        Requires: ``pip install flax jax[cuda12]``

Architecture
------------
TimesFM 2.5 200M is a patched-decoder Transformer with:
    - input_patch_len  = 32
    - output_patch_len = 128
    - num_layers       = 20
    - model_dims       = 1280
    - num_heads        = 16
Pre-trained on 100B+ real and synthetic time-series data points.

Usage
-----
    from ml_models.timesfm_predictor import TimesFMForecaster
    import pandas as pd

    forecaster = TimesFMForecaster(context_len=512, horizon_len=128)
    metrics = forecaster.generate_forecast_metrics(live_df["close"])

    # Feed directly to orchestrator:
    signal = orchestrator.evaluate(
        rf_prediction   = rf_pred,
        lstm_delta      = metrics["expected_return_delta"],
        dqn_q_values    = dqn_q,
        sentiment_score = sent_score,
    )
"""

from __future__ import annotations

import logging
import traceback
from typing import Dict, Final, List, Optional

import numpy as np
import pandas as pd

from ml_models.utils import (
    build_zeroed_forecast_metrics,
    linear_trend_direction,
    percent_return,
    validate_price_series,
)

logger: logging.Logger = logging.getLogger("ml_models.timesfm_predictor")


# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants
# ─────────────────────────────────────────────────────────────────────────────

#: HuggingFace repo for TimesFM 2.5 PyTorch (recommended for Windows).
_DEFAULT_REPO_ID_TORCH: Final[str] = "google/timesfm-2.5-200m-pytorch"

#: Default context window.  Must be a multiple of patch_len (32).
#: 512 = 16 patches — optimal for intraday hourly bars (covers ~3 weeks).
_DEFAULT_CONTEXT_LEN: Final[int] = 512

#: Horizon — number of future bars to forecast.
_DEFAULT_HORIZON_LEN: Final[int] = 128

#: Minimum absolute slope to classify forecast as trending (not neutral).
_SLOPE_THRESHOLD: Final[float] = 1e-5


# ─────────────────────────────────────────────────────────────────────────────
# TimesFMForecaster
# ─────────────────────────────────────────────────────────────────────────────


class TimesFMForecaster:
    """
    Production-safe Google TimesFM 2.5 (PyTorch) zero-shot inference wrapper.

    Wraps ``timesfm.TimesFM_2p5_200M_torch`` with:
        - Graceful degradation when timesfm / torch are not installed
        - Full input validation (length, NaN, positivity)
        - Three-tier exception isolation
        - JAX-style warm_up() API (calls a synthetic inference pass)

    Parameters
    ----------
    context_len : int
        Number of historical bars fed as model context.
        Must be a positive multiple of 32 (the model's patch_len).
        Default 512. For very short histories use 64 (minimum viable).
    horizon_len : int
        Number of future bars to predict.  Default 128.
        For point-in-time trading signals, we use ``forecast_vector[:10]``.
    repo_id : str
        HuggingFace repo ID for the PyTorch checkpoint.
        Default ``google/timesfm-2.5-200m-pytorch``.
    lazy_load : bool
        If True, defer weight download to the first inference call.
        Default True (fast startup).
    torch_compile : bool
        If True, call ``torch.compile()`` after weight loading.
        Default False (optimal on Windows CPU to prevent JIT compile stalls).

    Attributes
    ----------
    _model_ready : bool
        True when weights are loaded and the model is compiled.
    _backend : str
        ``"cuda"`` if a CUDA GPU was detected, else ``"cpu"``.
    _inference_count : int
        Total successful inference calls since instantiation.
    """

    def __init__(
        self,
        context_len:   int  = _DEFAULT_CONTEXT_LEN,
        horizon_len:   int  = _DEFAULT_HORIZON_LEN,
        repo_id:       str  = _DEFAULT_REPO_ID_TORCH,
        lazy_load:     bool = True,
        torch_compile: bool = False,
    ) -> None:
        self._context_len:   int  = context_len
        self._horizon_len:   int  = horizon_len

        # Check if local weights exist to support offline/local loading by default
        import os
        local_weights_dir = "C:/Users/magdi/timesfm_weights"
        if repo_id == _DEFAULT_REPO_ID_TORCH and os.path.isdir(local_weights_dir) and os.path.isfile(os.path.join(local_weights_dir, "model.safetensors")):
            logger.info(
                "[TimesFMForecaster] Found offline weights at '%s'. "
                "Defaulting to local load to bypass HuggingFace online check.",
                local_weights_dir,
            )
            self._repo_id = local_weights_dir
        else:
            self._repo_id = repo_id

        self._torch_compile: bool = torch_compile
        self._model_ready:   bool = False
        self._backend:       str  = "cpu"
        self._inference_count: int = 0
        self._model: Optional[object] = None
        self._forecast_config: Optional[object] = None

        self._backend = self._detect_backend()

        if not lazy_load:
            self._load_model()

    # ── Backend Detection ──────────────────────────────────────────────────

    def _detect_backend(self) -> str:
        """Detect CUDA vs CPU availability via PyTorch."""
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                logger.info(
                    "[TimesFMForecaster] CUDA GPU detected: %s. "
                    "TimesFM will use GPU inference.",
                    device_name,
                )
                return "cuda"
            else:
                logger.info(
                    "[TimesFMForecaster] No CUDA GPU found — using CPU inference. "
                    "(CPU inference: ~1-3s per call on Windows bare-metal)"
                )
                return "cpu"
        except ImportError:
            logger.debug("[TimesFMForecaster] PyTorch not installed — defaulting to cpu.")
            return "cpu"
        except Exception as exc:
            logger.warning("[TimesFMForecaster] Backend detection error: %s", exc)
            return "cpu"

    # ── Model Loading ──────────────────────────────────────────────────────

    def _load_model(self) -> None:
        """
        Download (if needed) and load TimesFM 2.0 weights from HuggingFace.

        On first run: downloads ``model.safetensors`` (~780MB) to:
            ``C:\\Users\\<user>\\.cache\\huggingface\\hub\\
              models--google--timesfm-2.0-500m-pytorch\\``
        Subsequent runs use the local cache instantly.

        After loading, calls ``model.compile(ForecastConfig(...))`` to
        JIT-compile the decode function for fast batched inference.
        """
        try:
            import os
            import timesfm
            from timesfm import ForecastConfig
            from timesfm import TimesFM_2p5_200M_torch

            logger.info(
                "[TimesFMForecaster] Loading TimesFM 2.5 from '%s' "
                "(backend=%s, context_len=%d, horizon_len=%d) ...",
                self._repo_id,
                self._backend,
                self._context_len,
                self._horizon_len,
            )

            # Load from local weights directory or HuggingFace Hub
            if os.path.isdir(self._repo_id):
                model = TimesFM_2p5_200M_torch(torch_compile=self._torch_compile)
                model.load_checkpoint(self._repo_id, torch_compile=self._torch_compile)
            else:
                model = TimesFM_2p5_200M_torch.from_pretrained(
                    self._repo_id,
                    torch_compile=self._torch_compile,
                )

            # Compile the decode function for the configured context/horizon
            forecast_config = ForecastConfig(
                max_context=self._context_len,
                max_horizon=self._horizon_len,
                normalize_inputs=True,    # safe for Forex price magnitudes
                per_core_batch_size=1,    # single-series real-time inference
                force_flip_invariance=True,
                infer_is_positive=True,   # Forex prices are always positive
            )
            model.compile(forecast_config)

            self._model          = model
            self._forecast_config = forecast_config
            self._model_ready    = True

            logger.info(
                "[TimesFMForecaster] ✓ Model loaded & compiled. "
                "Backend: %s | Ready for zero-shot inference.",
                self._backend,
            )

        except ImportError as exc:
            logger.error(
                "[TimesFMForecaster] Required package not installed: %s\n"
                "Install with:\n"
                "  pip install timesfm\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                "TimesFMForecaster will return zeroed metrics.",
                exc,
            )
            self._model_ready = False

        except Exception as exc:
            logger.error(
                "[TimesFMForecaster] Model loading failed: %s\n%s\n"
                "Returning zeroed metrics on all inference calls.",
                exc,
                traceback.format_exc(),
            )
            self._model_ready = False

    # ── Core Inference ─────────────────────────────────────────────────────

    def generate_forecast_metrics(
        self,
        price_series: pd.Series,
    ) -> Dict[str, object]:
        """
        Run zero-shot TimesFM 2.0 inference and compute directional metrics.

        The last ``context_len`` prices are passed to the model.
        Returns a dict with:

        ``expected_return_delta`` : float
            (mean(forecast_vector[:10]) - last_close) / last_close
            Maps directly to the orchestrator's ``lstm_delta`` slot.

        ``forecast_trend_direction`` : int
            +1 = Bullish, -1 = Bearish, 0 = Neutral (OLS slope).

        ``forecast_vector`` : list[float]
            First 10 bars of the model's point forecast.

        ``last_price`` : float
            Most recent closing price (normalisation anchor).

        ``is_valid`` : bool
            True if inference succeeded; False if any step failed.

        Parameters
        ----------
        price_series : pd.Series
            Chronologically ordered closing prices.
            Must have ≥ ``context_len`` rows and contain no NaN.

        Returns
        -------
        dict
            Always returns all keys — guaranteed non-None.
        """
        # ── Tier 0: Lazy load ──────────────────────────────────────────
        if not self._model_ready and self._model is None:
            logger.info("[TimesFMForecaster] Lazy loading model on first inference call...")
            self._load_model()

        # ── Tier 1: Model availability guard ──────────────────────────
        if not self._model_ready or self._model is None:
            logger.warning(
                "[TimesFMForecaster] Model not ready. Returning zeroed metrics. "
                "Install timesfm + torch and ensure weights are accessible."
            )
            return build_zeroed_forecast_metrics()

        # ── Tier 2: Input validation ───────────────────────────────────
        if not validate_price_series(
            series=price_series,
            min_len=self._context_len,
            name="TimesFM input (close prices)",
            allow_nan=False,
            allow_non_positive=False,
        ):
            return build_zeroed_forecast_metrics()

        # ── Tier 3: Inference execution ────────────────────────────────
        try:
            # Extract last context_len bars → shape (1, context_len)
            context_window = (
                price_series.iloc[-self._context_len:]
                .to_numpy(dtype=np.float32)
                .reshape(1, -1)
            )
            last_price = float(context_window[0, -1])

            if last_price <= 0.0:
                logger.error(
                    "[TimesFMForecaster] last_price=%.6f ≤ 0. "
                    "Data integrity issue. Returning zeroed metrics.",
                    last_price,
                )
                return build_zeroed_forecast_metrics()

            # Masks: all zeros = all observed (no missing values)
            masks = np.zeros_like(context_window, dtype=bool)

            logger.debug(
                "[TimesFMForecaster] Running inference | "
                "context_len=%d | last_price=%.6f | backend=%s",
                self._context_len, last_price, self._backend,
            )

            # ── TimesFM 2.0 API call ───────────────────────────────────
            # compiled_decode(horizon, inputs, masks)
            # inputs: np.ndarray shape (batch, context_len)
            # masks:  np.ndarray shape (batch, context_len) — bool, True=masked
            # returns: (point_forecast, full_forecast)
            #   point_forecast: np.ndarray shape (batch, horizon)  — median (q=5)
            #   full_forecast:  np.ndarray shape (batch, horizon, 10) — all quantiles
            point_forecast, full_forecast = self._model.compiled_decode(
                self._horizon_len,
                context_window,
                masks,
            )

            # Extract the 1D point forecast (shape: horizon,)
            forecast_vector_full: np.ndarray = point_forecast[0].astype(np.float64)

            # Use first 10 bars as the short-horizon signal
            signal_len = min(10, len(forecast_vector_full))
            forecast_vector_signal = forecast_vector_full[:signal_len]

            # Guard against NaN in forecast output
            if np.isnan(forecast_vector_signal).any():
                n_nan = int(np.isnan(forecast_vector_signal).sum())
                logger.warning(
                    "[TimesFMForecaster] Forecast contains %d NaN(s); "
                    "replacing with last_price.",
                    n_nan,
                )
                forecast_vector_signal = np.where(
                    np.isnan(forecast_vector_signal),
                    last_price,
                    forecast_vector_signal,
                )

            # ── Compute metrics ────────────────────────────────────────
            forecast_mean  = float(np.mean(forecast_vector_signal))
            expected_return_delta = percent_return(
                current=forecast_mean,
                reference=last_price,
            )
            forecast_trend_direction = linear_trend_direction(
                vector=forecast_vector_signal,
                slope_threshold=_SLOPE_THRESHOLD,
            )

            self._inference_count += 1

            metrics: Dict[str, object] = {
                "expected_return_delta":    expected_return_delta,
                "forecast_trend_direction": forecast_trend_direction,
                "forecast_vector":          forecast_vector_signal.tolist(),
                "last_price":               last_price,
                "is_valid":                 True,
            }

            logger.info(
                "[TimesFMForecaster] #%d | last_price=%.6f | "
                "forecast_mean=%.6f | return_delta=%.6f (%.4f%%) | "
                "direction=%+d (%s) | backend=%s",
                self._inference_count,
                last_price,
                forecast_mean,
                expected_return_delta,
                expected_return_delta * 100.0,
                forecast_trend_direction,
                {1: "Bullish", -1: "Bearish", 0: "Neutral"}[forecast_trend_direction],
                self._backend,
            )

            return metrics

        except Exception as exc:
            logger.error(
                "[TimesFMForecaster] Inference error on call #%d: %s\n%s\n"
                "Returning zeroed metrics.",
                self._inference_count + 1,
                exc,
                traceback.format_exc(),
            )
            return build_zeroed_forecast_metrics()

    # ── Warm-up ────────────────────────────────────────────────────────────

    def warm_up(self, synthetic_len: Optional[int] = None) -> bool:
        """
        Run a synthetic inference pass to pre-compile the torch decode graph.

        Call once at system startup before the first live bar arrives.

        Parameters
        ----------
        synthetic_len : int | None
            Length of the synthetic price series.  Defaults to
            ``context_len + 32`` (one extra patch as buffer).

        Returns
        -------
        bool
            True if the warm-up succeeded, False otherwise.
        """
        warmup_len = synthetic_len or (self._context_len + 32)
        rng = np.random.default_rng(seed=0)
        synthetic_prices = pd.Series(
            1.0850 + np.cumsum(rng.normal(0, 0.0005, warmup_len))
        )
        synthetic_prices = (synthetic_prices - synthetic_prices.min() + 0.001)

        logger.info(
            "[TimesFMForecaster] Running warm-up inference "
            "(synthetic len=%d) ...",
            warmup_len,
        )

        result = self.generate_forecast_metrics(synthetic_prices)
        success = bool(result.get("is_valid", False))

        if success:
            logger.info(
                "[TimesFMForecaster] ✓ Warm-up complete — "
                "inference is now latency-optimal."
            )
        else:
            logger.warning(
                "[TimesFMForecaster] Warm-up failed (model_ready=%s).",
                self._model_ready,
            )
        return success

    # ── Properties & Diagnostics ───────────────────────────────────────────

    @property
    def model_ready(self) -> bool:
        """True if the TimesFM model weights are loaded and compiled."""
        return self._model_ready

    @property
    def backend(self) -> str:
        """Active execution backend: ``"cuda"`` or ``"cpu"``."""
        return self._backend

    @property
    def context_len(self) -> int:
        """Configured historical context window length (bars)."""
        return self._context_len

    @property
    def horizon_len(self) -> int:
        """Configured forecast horizon length (bars)."""
        return self._horizon_len

    @property
    def inference_count(self) -> int:
        """Total successful inference calls since instantiation."""
        return self._inference_count

    def status_report(self) -> Dict[str, object]:
        """Return a structured health-check dictionary."""
        return {
            "model_ready":     self._model_ready,
            "backend":         self._backend,
            "repo_id":         self._repo_id,
            "context_len":     self._context_len,
            "horizon_len":     self._horizon_len,
            "inference_count": self._inference_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI Smoke-Test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    print("\n=== ml_models/timesfm_predictor.py — TimesFM 2.0 Smoke-Test ===\n")

    forecaster = TimesFMForecaster(
        context_len=512,
        horizon_len=128,
        lazy_load=False,
        torch_compile=False,   # Faster startup for smoke-test
    )
    print(f"Status: {forecaster.status_report()}")

    # Test 1: Happy path — if model loaded, run real inference
    rng = np.random.default_rng(42)
    n = 600
    close = pd.Series(
        1.0850 + np.cumsum(rng.normal(0, 0.0005, n)),
        name="close",
    )
    close = close - close.min() + 0.5

    print(f"\nTest 1: Full inference with {n}-bar synthetic series ...")
    m = forecaster.generate_forecast_metrics(close)
    print(f"  is_valid              : {m['is_valid']}")
    print(f"  last_price            : {m['last_price']:.6f}")
    print(f"  expected_return_delta : {m['expected_return_delta']:+.6f} ({m['expected_return_delta']*100:.4f}%)")
    print(f"  forecast_trend_dir    : {m['forecast_trend_direction']}")
    if m['forecast_vector']:
        fv = m['forecast_vector']
        print(f"  forecast_vector       : [{fv[0]:.6f} ... {fv[-1]:.6f}] (len={len(fv)})")

    # Test 2: Short series → should return is_valid=False
    print("\nTest 2: Short series (30 bars) → should return zeroed metrics ...")
    short = pd.Series(np.linspace(1.08, 1.09, 30))
    ms = forecaster.generate_forecast_metrics(short)
    assert ms["is_valid"] is False, "Expected is_valid=False"
    assert ms["expected_return_delta"] == 0.0
    print("  PASS: is_valid=False, delta=0.0")

    # Test 3: NaN series → should return is_valid=False
    print("\nTest 3: Series with NaN → should return zeroed metrics ...")
    nan_s = close.copy()
    nan_s.iloc[100] = float("nan")
    mn = forecaster.generate_forecast_metrics(nan_s)
    assert mn["is_valid"] is False
    print("  PASS: is_valid=False")

    print(f"\nFinal inference_count: {forecaster.inference_count}")
    print("\n=== ALL TESTS PASSED ===\n")
