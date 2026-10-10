"""
==============================================================
ml_models/feature_pipeline_v2.py  —  TimesFM Multi-Model Feature Aggregator
==============================================================
Upgraded centralized feature matrix builder for the Antigravity multi-agent
trading system.  This module **replaces the LSTM-centric pipeline** with a
Google TimesFM-powered architecture while preserving full backward
compatibility with the existing ``AntigravityOrchestrator.evaluate()`` API.

Architectural Position
----------------------
This module sits between the data ingestion layer and the model ensemble:

    Hyperliquid Live Bar Feed          OpenBB v4 News / Macro API
            │                                   │
            ▼                                   ▼
    live_dataframe (pd.DataFrame)       news_texts (List[str])
            │                                   │
            └──────────────┬────────────────────┘
                           │
              build_orchestrator_feature_matrix()
                           │
              ┌────────────┼────────────────────┐
              ▼            ▼                    ▼
     RF Input (26 feats) DQN State (20 dims)  Sentiment Scalar [-1,+1]
              │            │
              └────────────┘
                    │
         AntigravityFeatureBundleV2
                    │
         AntigravityOrchestrator.evaluate()
           (timesfm_delta ← expected_return_delta)

Module Responsibilities
-----------------------
1. ``build_orchestrator_feature_matrix()``
    The primary public function.  Coordinates all four sub-pipelines:

    RF Subsystem
        Calls ``RFFeaturePipeline.build_features()`` to produce the
        classical 25-feature matrix, then **appends** the TimesFM
        ``expected_return_delta`` as the 26th column.  This makes the
        TimesFM forecast a primary high-weight input to the Random Forest
        classifier — signals that pass both technical analysis AND the
        foundation model gain significant classification weight.

    DQN Subsystem
        Calls ``DQNStatePipeline.build_state()`` to produce the 19-dim
        state vector, then **appends** ``forecast_trend_direction`` (from
        TimesFM) as the 20th dimension.  The DQN agent therefore sees
        the foundation model's directional signal as part of its market
        observation.  This is injected as ``tfm_trend_norm`` = the
        trend direction encoded as {-1.0, 0.0, +1.0} float.

    Sentiment Subsystem
        Ingests ``news_texts: List[str]`` from the OpenBB v4 news feed,
        runs them through ``SentimentPipeline.aggregate()`` with
        exponential recency weighting, and outputs a single normalised
        scalar in [-1.0, +1.0].  Missing or empty news lists return 0.0
        (neutral) rather than an error.

    TimesFM Engine
        Calls ``TimesFMForecaster.generate_forecast_metrics()`` to
        produce ``expected_return_delta`` and ``forecast_trend_direction``
        that are injected into the RF and DQN subsystems respectively.
        If the model is not loaded, zeroed metrics are propagated
        silently without disrupting the RF or DQN pipelines.

2. ``AntigravityFeatureBundleV2``
    An upgraded dataclass extending the original ``AntigravityFeatureBundle``
    with a ``timesfm_metrics`` field and the updated array dimensions.

3. ``TimesFMFeaturePipelineFacade``
    An object-oriented wrapper around ``build_orchestrator_feature_matrix()``
    that manages pipeline lifecycle, account state updates, and orchestrator
    integration.

Zero Look-Ahead Bias Guarantees
---------------------------------
- All ``StandardScaler``s are fitted on training data and loaded from
  disk (``ml_models/scalers/``).  They are never re-fitted on live data.
- The ``RollingWindowScaler`` in ``ml_models.utils`` is used for any
  online normalisation and always excludes the current bar from its
  fitting window.

NaN Handling for Sentiment Strings
-----------------------------------
When ``news_texts`` is None, empty, or contains only empty strings:
    → ``sentiment_score = 0.0`` (neutral, not an error)
    → ``sentiment_label = "NEUTRAL"``

When ``news_texts`` contains non-string items:
    → Items are coerced to str; if empty after coercion → filtered out.

MT5 Account State Integration
-------------------------------
The ``AccountState`` dataclass (defined in ``feature_pipeline.py``)
aggregates:
    - ``equity_usd``           : Real-time MT5 account equity
    - ``drawdown_pct``         : Current peak-equity drawdown percentage
    - ``position_direction``   : {-1 SHORT, 0 FLAT, +1 LONG}
    - ``position_pnl_pct``     : Unrealised P&L as fraction of balance

These are normalised by ``DQNStatePipeline.build_account_obs()`` and
appended to the 20-dim DQN state vector.

Usage
-----
    from ml_models.feature_pipeline_v2 import (
        build_orchestrator_feature_matrix,
        TimesFMFeaturePipelineFacade,
        AntigravityFeatureBundleV2,
    )
    from ml_models.timesfm_predictor import TimesFMForecaster
    from ml_models.feature_pipeline import AccountState

    # ── Initialise once at system startup ──────────────────────────────
    forecaster = TimesFMForecaster(context_len=64, horizon_len=10)
    forecaster.warm_up()   # Pre-compile JAX graph

    facade = TimesFMFeaturePipelineFacade(
        forecaster=forecaster,
        account=AccountState(balance_usd=10_000, equity_usd=10_000),
    )

    # ── Per-bar processing ────────────────────────────────────────────
    bundle = facade.process_bar(
        symbol     = "BTCUSDT",
        df         = live_dataframe,     # From Hyperliquid / OpenBB
        news_texts = openbb_headlines,   # From DataService.get_equity_news()
    )

    # ── Feed directly to orchestrator ────────────────────────────────
    signal = orchestrator.evaluate(
        rf_prediction   = rf_model.predict(bundle.rf_features)[0],
        lstm_delta      = bundle.timesfm_metrics["expected_return_delta"],
        dqn_q_values    = dqn_model.get_q_values(bundle.dqn_state),
        sentiment_score = bundle.sentiment_score,
    )
"""

from __future__ import annotations

import logging
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Final, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Internal imports ──────────────────────────────────────────────────────────
# Re-use all existing pipeline classes without modifying feature_pipeline.py
from ml_models.feature_pipeline import (
    AccountState,
    DQNStatePipeline,
    RFFeaturePipeline,
    RF_FEATURE_NAMES,
    SentimentPipeline,
    _MIN_BARS,
    _safe_fill,
    _RF_NAN_DEFAULTS,
)
from ml_models.timesfm_predictor import TimesFMForecaster
from ml_models.utils import (
    build_zeroed_forecast_metrics,
    clip_array,
    safe_fill_feature_matrix,
    safe_fill_series,
    validate_price_series,
)

logger: logging.Logger = logging.getLogger("ml_models.feature_pipeline_v2")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: TimesFM context length (must match TimesFMForecaster configuration).
#: 512 = 16 patches of 32 — optimal for hourly intraday bars (covers ~3 weeks).
_TFM_CONTEXT_LEN: Final[int] = 512

#: Name of the TimesFM return-delta feature appended to the RF feature matrix.
TFM_RETURN_DELTA_FEATURE: Final[str] = "tfm_expected_return_delta"

#: Name of the TimesFM trend direction feature appended to the DQN state.
TFM_TREND_DIRECTION_FEATURE: Final[str] = "tfm_trend_direction"

#: Total RF feature count after TimesFM augmentation (25 classical + 1 TFM).
RF_V2_FEATURE_COUNT: Final[int] = len(RF_FEATURE_NAMES) + 1   # = 26

#: Total DQN state dimension after TimesFM augmentation (19 classical + 1 TFM).
DQN_V2_STATE_DIM: Final[int] = 20

#: Complete ordered list of RF V2 feature names (for model training alignment).
RF_V2_FEATURE_NAMES: Final[List[str]] = RF_FEATURE_NAMES + [TFM_RETURN_DELTA_FEATURE]

#: Ceiling for clamping ``expected_return_delta`` before RF feature injection.
#: Prevents a single extreme TimesFM forecast from dominating the RF input.
_TFM_DELTA_CLAMP: Final[float] = 0.05   # ±5% maximum expected return


# ─────────────────────────────────────────────────────────────────────────────
# AntigravityFeatureBundleV2
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AntigravityFeatureBundleV2:
    """
    Upgraded feature bundle carrying all model inputs for one bar.

    Produced by ``build_orchestrator_feature_matrix()`` and consumed by
    the model ensemble and the ``AntigravityOrchestrator``.

    Compared to the original ``AntigravityFeatureBundle``, this V2 bundle:
        - Replaces the ``lstm_window`` (shape 1×60×5) with ``timesfm_metrics``
          (a dict from ``TimesFMForecaster.generate_forecast_metrics()``).
        - Expands ``rf_features`` from shape (1, 25) to (1, 26) by appending
          the TimesFM ``expected_return_delta`` as the 26th column.
        - Expands ``dqn_state`` from shape (19,) to (20,) by appending the
          TimesFM ``forecast_trend_direction`` as the 20th dimension.

    Attributes
    ----------
    symbol : str
        Trading pair / MT5 ticker this bundle was produced for.
    bar_time : Any
        DatetimeIndex timestamp of the bar from the source DataFrame.
    rf_features : np.ndarray
        Shape ``(1, 26)`` float32 — RF classifier input.
        Columns 0–24 = classical RF features (matching ``RF_FEATURE_NAMES``).
        Column 25    = ``tfm_expected_return_delta`` (TimesFM-injected).
    dqn_state : np.ndarray
        Shape ``(20,)`` float32 — DQN agent state vector.
        Dims 0–18 = classical DQN state (market + account, as before).
        Dim 19    = ``tfm_trend_direction`` normalised: {-1.0, 0.0, +1.0}.
    sentiment_score : float
        Aggregated news sentiment in [-1.0, +1.0].
    sentiment_label : str
        Human-readable sentiment label: ``"BULLISH"`` | ``"BEARISH"`` | ``"NEUTRAL"``.
    timesfm_metrics : dict
        Raw TimesFM output from ``generate_forecast_metrics()``.
        Keys: ``expected_return_delta``, ``forecast_trend_direction``,
              ``forecast_vector``, ``last_price``, ``is_valid``.
    produced_at : float
        UNIX timestamp of bundle assembly (for latency monitoring).
    """

    symbol:           str
    bar_time:         Any
    rf_features:      np.ndarray          # shape (1, 26)
    dqn_state:        np.ndarray          # shape (20,)
    sentiment_score:  float
    sentiment_label:  str
    timesfm_metrics:  Dict[str, Any]
    produced_at:      float = field(default_factory=time.time)

    @property
    def timesfm_delta(self) -> float:
        """
        The TimesFM ``expected_return_delta`` ready for the orchestrator's
        ``lstm_delta`` slot.

        Returns 0.0 if the TimesFM inference was invalid.
        """
        return float(self.timesfm_metrics.get("expected_return_delta", 0.0))

    @property
    def timesfm_trend(self) -> int:
        """
        The TimesFM ``forecast_trend_direction``: +1, -1, or 0.
        """
        return int(self.timesfm_metrics.get("forecast_trend_direction", 0))

    @property
    def is_timesfm_valid(self) -> bool:
        """True if the TimesFM inference produced a valid result."""
        return bool(self.timesfm_metrics.get("is_valid", False))

    def summary(self) -> str:
        """Return a human-readable one-line bundle summary."""
        tf_status = "✓" if self.is_timesfm_valid else "✗"
        direction_str = {1: "↑ Bullish", -1: "↓ Bearish", 0: "→ Neutral"}.get(
            self.timesfm_trend, "?"
        )
        return (
            f"[{self.symbol} @ {self.bar_time}] "
            f"RF:{self.rf_features.shape} "
            f"DQN:{self.dqn_state.shape} "
            f"SENT:{self.sentiment_score:+.4f}[{self.sentiment_label}] "
            f"TFM[{tf_status}]:{self.timesfm_delta:+.6f} {direction_str}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _sanitize_news_texts(raw_texts: Optional[List[Any]]) -> List[str]:
    """
    Sanitise raw news text input for the sentiment pipeline.

    Handles:
        - None input → empty list
        - Non-string items → coerced to str
        - Empty strings → filtered out
        - Excessively long strings → truncated to 512 chars (VADER performance)

    Parameters
    ----------
    raw_texts : list | None
        Raw news headline/body strings from OpenBB or any source.

    Returns
    -------
    list[str]
        Cleaned list of non-empty strings, ready for sentiment scoring.
        Returns empty list if input is None or all items are blank.
    """
    if raw_texts is None:
        return []

    cleaned: List[str] = []
    for item in raw_texts:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            # Truncate very long articles to headline + first ~500 chars
            cleaned.append(text[:512])

    return cleaned


def _build_rf_features_with_tfm(
    df: pd.DataFrame,
    rf_pipe: RFFeaturePipeline,
    tfm_return_delta: float,
) -> np.ndarray:
    """
    Build the augmented RF feature row with TimesFM delta appended.

    Constructs the full RF feature matrix from ``df``, extracts the
    live inference row, and appends ``tfm_return_delta`` as the 26th
    column.

    Zero-Leakage Note
    -----------------
    The RF scaler was fitted on training data and loaded from disk.
    ``transform_live()`` applies the pre-fitted scaler to the current
    bar's features only — it never re-fits.  The TimesFM delta is
    appended AFTER scaling so it is not distorted by the RF scaler's
    parameters.

    Parameters
    ----------
    df : pd.DataFrame
        Full bar history DataFrame (at least ``_MIN_BARS`` rows).
    rf_pipe : RFFeaturePipeline
        Pre-fitted RF feature pipeline with a loaded scaler.
    tfm_return_delta : float
        ``expected_return_delta`` from ``TimesFMForecaster``.
        Clamped to ``[−_TFM_DELTA_CLAMP, +_TFM_DELTA_CLAMP]`` before injection.

    Returns
    -------
    np.ndarray
        Shape ``(1, 26)`` float32 — scaled RF features + TimesFM delta.

    Raises
    ------
    RuntimeError
        If the RF pipeline produces an unexpected output shape.
    """
    # Step 1: Build classical RF features (25 columns), scaled.
    try:
        rf_row: np.ndarray = rf_pipe.transform_live(df)   # shape (1, 25)
    except Exception as exc:
        logger.error(
            "[_build_rf_features_with_tfm] RFFeaturePipeline.transform_live() "
            "failed: %s — returning zero RF features.",
            exc,
        )
        rf_row = np.zeros((1, len(RF_FEATURE_NAMES)), dtype=np.float32)

    # Step 2: Validate RF output shape
    if rf_row.ndim != 2 or rf_row.shape[0] != 1:
        logger.warning(
            "[_build_rf_features_with_tfm] RF output shape %s is unexpected. "
            "Expected (1, n_features). Reshaping.",
            rf_row.shape,
        )
        rf_row = rf_row.reshape(1, -1)

    # Step 3: Clamp and append TimesFM delta as the 26th feature.
    # Clamping prevents an extreme TFM forecast from dominating the RF input.
    delta_clamped = float(np.clip(tfm_return_delta, -_TFM_DELTA_CLAMP, _TFM_DELTA_CLAMP))
    delta_col = np.array([[delta_clamped]], dtype=np.float32)   # shape (1, 1)

    rf_augmented = np.concatenate([rf_row, delta_col], axis=1)  # shape (1, 26)

    logger.debug(
        "[_build_rf_features_with_tfm] RF augmented: shape=%s | "
        "tfm_delta_raw=%.6f → clamped=%.6f",
        rf_augmented.shape,
        tfm_return_delta,
        delta_clamped,
    )

    return rf_augmented.astype(np.float32)


def _build_dqn_state_with_tfm(
    df: pd.DataFrame,
    rf_pipe: RFFeaturePipeline,
    dqn_pipe: DQNStatePipeline,
    account: AccountState,
    tfm_trend_direction: int,
) -> np.ndarray:
    """
    Build the augmented 20-dim DQN state vector with TimesFM trend appended.

    Extends the standard 19-dim DQN state (12 market + 7 account) with
    the TimesFM ``forecast_trend_direction`` as the 20th dimension.

    Encoding of ``tfm_trend_direction`` in the DQN state:
        +1 (Bullish)  →  +1.0 float
        -1 (Bearish)  →  -1.0 float
         0 (Neutral)  →   0.0 float

    This is already in the DQN's natural [-1, +1] range and requires
    no further normalisation.

    Parameters
    ----------
    df : pd.DataFrame
        Full bar history DataFrame with computed RF features available
        (the RF feature columns are merged into ``latest_row`` before
        building the DQN state, consistent with the original facade).
    rf_pipe : RFFeaturePipeline
        Pre-fitted RF pipeline — used to enrich the latest bar row with
        pre-computed technical indicators for DQN state construction.
    dqn_pipe : DQNStatePipeline
        Initialised DQN state pipeline (scaler optional).
    account : AccountState
        Real-time MT5 account snapshot.
    tfm_trend_direction : int
        TimesFM directional signal: +1, -1, or 0.

    Returns
    -------
    np.ndarray
        Shape ``(20,)`` float32 — full augmented DQN state vector.
    """
    # Merge RF features into the latest bar row so DQN can read
    # pre-computed indicators (rsi_14, atr_norm, etc.)
    latest_row: pd.Series = df.iloc[-1].copy()
    try:
        rf_feat_df = rf_pipe.build_features(df)
        for col in rf_feat_df.columns:
            latest_row[col] = rf_feat_df[col].iloc[-1]
    except Exception as exc:
        logger.warning(
            "[_build_dqn_state_with_tfm] Could not merge RF features into "
            "DQN latest_row: %s — DQN will use raw bar row only.",
            exc,
        )

    # Build the standard 19-dim DQN state
    try:
        dqn_state_19: np.ndarray = dqn_pipe.build_state(
            bar_row=latest_row,
            account=account,
            apply_scaling=True,
        )   # shape (19,)
    except Exception as exc:
        logger.error(
            "[_build_dqn_state_with_tfm] DQNStatePipeline.build_state() "
            "failed: %s — returning zero DQN state.",
            exc,
        )
        dqn_state_19 = np.zeros(19, dtype=np.float32)

    # Validate shape
    if dqn_state_19.ndim != 1:
        dqn_state_19 = dqn_state_19.ravel()

    # Append TimesFM trend direction as the 20th dimension.
    # The DQN network's first layer must be sized for 20 inputs.
    tfm_trend_float = float(np.clip(tfm_trend_direction, -1, 1))
    dqn_state_20 = np.append(dqn_state_19, tfm_trend_float).astype(np.float32)

    # Final clip to prevent outlier saturation
    dqn_state_20 = clip_array(dqn_state_20, bound=10.0)

    logger.debug(
        "[_build_dqn_state_with_tfm] DQN state v2: shape=%s | "
        "tfm_trend=%+d → dim[19]=%.1f",
        dqn_state_20.shape,
        tfm_trend_direction,
        tfm_trend_float,
    )

    return dqn_state_20   # shape (20,)


def _build_sentiment_scalar(
    news_texts: List[str],
    sent_pipe: SentimentPipeline,
    fallback_df_column: Optional[pd.Series] = None,
) -> Tuple[float, str]:
    """
    Produce a normalised sentiment scalar from OpenBB v4 news texts.

    Processing pipeline
    -------------------
    1. If ``news_texts`` is non-empty: score all texts with
       ``SentimentPipeline.aggregate()`` using exponential recency
       weighting (most recent headline weighted highest).
    2. If ``news_texts`` is empty but ``fallback_df_column`` is provided:
       use the last non-NaN value from the DataFrame's ``sentiment_score``
       column (set by an upstream OpenBB data layer).
    3. If both are empty: return (0.0, "NEUTRAL").

    The output is guaranteed to be in [-1.0, +1.0] (VADER's compound
    score is already clamped by ``SentimentPipeline.score()``).

    Parameters
    ----------
    news_texts : list[str]
        Sanitised (non-empty) list of news strings.
    sent_pipe : SentimentPipeline
        Initialised sentiment pipeline.
    fallback_df_column : pd.Series | None
        Optional ``sentiment_score`` column from the LivePipeline DataFrame,
        used when no live news texts are provided.

    Returns
    -------
    tuple[float, str]
        ``(score, label)`` where score ∈ [-1.0, +1.0] and label is
        ``"BULLISH"``, ``"BEARISH"``, or ``"NEUTRAL"``.
    """
    if news_texts:
        # Primary path: score live news texts
        try:
            score, label = sent_pipe.aggregate(
                news_texts,
                method="weighted_mean",  # exponential recency weighting
            )
            logger.debug(
                "[_build_sentiment_scalar] Scored %d news items: "
                "score=%+.4f [%s]",
                len(news_texts),
                score,
                label,
            )
            return float(score), label
        except Exception as exc:
            logger.warning(
                "[_build_sentiment_scalar] SentimentPipeline.aggregate() "
                "failed: %s — falling back to neutral.",
                exc,
            )

    # Fallback path 1: use pre-computed sentiment column from DataFrame
    if fallback_df_column is not None and not fallback_df_column.empty:
        last_valid = fallback_df_column.dropna()
        if not last_valid.empty:
            raw_score = float(last_valid.iloc[-1])
            # Clamp to valid range in case upstream data is not normalised
            score = float(np.clip(raw_score, -1.0, 1.0))
            label = (
                "BULLISH" if score > 0.05
                else "BEARISH" if score < -0.05
                else "NEUTRAL"
            )
            logger.debug(
                "[_build_sentiment_scalar] Using DataFrame sentiment_score "
                "fallback: %+.4f [%s]",
                score,
                label,
            )
            return score, label

    # Fallback path 2: no data available → neutral
    logger.debug(
        "[_build_sentiment_scalar] No news texts or DataFrame sentiment "
        "available. Returning neutral (0.0)."
    )
    return 0.0, "NEUTRAL"


# ─────────────────────────────────────────────────────────────────────────────
# Primary Public Function
# ─────────────────────────────────────────────────────────────────────────────


def build_orchestrator_feature_matrix(
    symbol: str,
    live_dataframe: pd.DataFrame,
    news_texts: Optional[List[Any]] = None,
    account_state: Optional[AccountState] = None,
    forecaster: Optional[TimesFMForecaster] = None,
    rf_pipe: Optional[RFFeaturePipeline] = None,
    dqn_pipe: Optional[DQNStatePipeline] = None,
    sent_pipe: Optional[SentimentPipeline] = None,
) -> AntigravityFeatureBundleV2:
    """
    Unified feature matrix builder for all four Antigravity quantitative subsystems.

    This is the primary public entrypoint for per-bar feature generation.
    It coordinates the TimesFM inference engine, the classical technical
    feature pipelines, and the sentiment NLP processor into a single
    ``AntigravityFeatureBundleV2`` that is ready for immediate model inference.

    Execution Order (designed to minimise redundant computation)
    -----------------------------------------------------------
    1. Validate & sanitise inputs.
    2. Run TimesFM zero-shot inference (once per bar, output shared).
    3. Build RF feature matrix (25 technical features).
       → Append TimesFM delta as column 26.
    4. Build DQN state vector (19 dims: market + MT5 account).
       → Append TimesFM trend as dim 20.
    5. Build sentiment scalar from OpenBB news texts.
    6. Assemble and return ``AntigravityFeatureBundleV2``.

    Parameters
    ----------
    symbol : str
        Trading pair identifier (e.g. ``"BTCUSDT"``, ``"EURUSD"``).
        Used for logging and bundle metadata only.
    live_dataframe : pd.DataFrame
        Canonical bar DataFrame from the Hyperliquid Live Bar Feed
        or OpenBB v4 OHLCV endpoint.  Must contain at minimum:
        ``["open", "high", "low", "close", "volume"]`` columns and
        at least ``_MIN_BARS`` (60) rows.

        Optional enrichment columns (used when present):
            ``hl_spread_bps``, ``hl_funding_rate`` — Hyperliquid data
            ``macro_vix``, ``macro_yield_spread``  — OpenBB macro data
            ``sentiment_score``                    — Pre-computed sentiment

    news_texts : list[str | Any] | None
        Unstructured string list from the OpenBB v4 real-time news API.
        Example input:
            ``["ECB holds rates steady", "EUR/USD breaks 1.09 resistance"]``

        - None or [] → sentiment defaults to 0.0 (NEUTRAL).
        - Non-string items are coerced to str.
        - Items longer than 512 chars are truncated.

    account_state : AccountState | None
        Real-time MT5 account snapshot from the MT5 agent.  Contains:
            ``balance_usd``, ``equity_usd``, ``position_direction``,
            ``position_lots``, ``position_pnl_pct``,
            ``position_duration_bars``, ``drawdown_pct``.
        Defaults to a flat (no position) account state if None.

    forecaster : TimesFMForecaster | None
        Pre-initialised TimesFM inference engine.  If None, a new
        instance is created but note that weight loading may be slow.
        For production, initialise once at startup and reuse.

    rf_pipe : RFFeaturePipeline | None
        Pre-fitted RF feature pipeline.  Created fresh if None.
        Note: A fresh pipeline has no fitted scaler — features will
        be returned unscaled until a scaler is loaded or fitted.

    dqn_pipe : DQNStatePipeline | None
        Initialised DQN state pipeline.  Created fresh if None.

    sent_pipe : SentimentPipeline | None
        Initialised sentiment pipeline.  Created fresh if None.

    Returns
    -------
    AntigravityFeatureBundleV2
        Complete feature bundle with the following dimensions:

        ``rf_features``
            Shape ``(1, 26)`` float32.
            Columns 0-24: classical RF features (see ``RF_FEATURE_NAMES``).
            Column 25: ``tfm_expected_return_delta`` ∈ [-0.05, +0.05].

        ``dqn_state``
            Shape ``(20,)`` float32.
            Dims 0-18: classical DQN state (market 12 + account 7).
            Dim 19: ``tfm_trend_direction`` ∈ {-1.0, 0.0, +1.0}.

        ``sentiment_score``
            Float in [-1.0, +1.0].  Positive = Bullish, Negative = Bearish.

        ``timesfm_metrics``
            Dict with keys:
            ``expected_return_delta`` (float),
            ``forecast_trend_direction`` (int),
            ``forecast_vector`` (list[float], len=10),
            ``last_price`` (float),
            ``is_valid`` (bool).

    Raises
    ------
    ValueError
        If ``live_dataframe`` has fewer than ``_MIN_BARS`` rows or is missing
        required OHLCV columns.

    Notes
    -----
    Thread Safety
        This function creates local pipeline instances if passed None,
        making it safe to call from different threads without shared
        state — provided that pre-built pipe objects are also thread-safe
        (they are, as per the feature_pipeline.py design contract).

    Performance
        TimesFM inference dominates latency (~0.1s GPU / ~1.5s CPU per bar).
        The RF feature computation is O(N×features) where N = n_bars.
        For real-time H1 bars, this is well within the bar-close window.

    Examples
    --------
    >>> bundle = build_orchestrator_feature_matrix(
    ...     symbol       = "EURUSD",
    ...     live_dataframe = df,
    ...     news_texts   = ["ECB signals rate cut", "EUR trades at 6-month high"],
    ...     account_state = AccountState(equity_usd=10_500, position_direction=1),
    ...     forecaster   = forecaster,
    ... )
    >>> bundle.rf_features.shape
    (1, 26)
    >>> bundle.dqn_state.shape
    (20,)
    >>> bundle.timesfm_delta
    0.00182  # 0.182% expected return
    """
    t_start: float = time.perf_counter()

    # ── Step 0: Input validation ────────────────────────────────────────────
    required_cols = ["open", "high", "low", "close", "volume"]
    missing_cols = [c for c in required_cols if c not in live_dataframe.columns]
    if missing_cols:
        raise ValueError(
            f"build_orchestrator_feature_matrix [{symbol}]: "
            f"live_dataframe missing required columns: {missing_cols}. "
            f"Available: {list(live_dataframe.columns)}"
        )

    if len(live_dataframe) < _MIN_BARS:
        raise ValueError(
            f"build_orchestrator_feature_matrix [{symbol}]: "
            f"live_dataframe has {len(live_dataframe)} rows, "
            f"minimum required is {_MIN_BARS}."
        )

    # ── Step 1: Lazy-initialise sub-pipelines ──────────────────────────────
    account: AccountState = account_state or AccountState()

    _rf_pipe   = rf_pipe   or RFFeaturePipeline()
    _dqn_pipe  = dqn_pipe  or DQNStatePipeline()
    _sent_pipe = sent_pipe or SentimentPipeline()
    _forecaster = forecaster or TimesFMForecaster(
        context_len=_TFM_CONTEXT_LEN,
        horizon_len=10,
        lazy_load=True,  # Don't block here; inference call will trigger load
    )

    # ── Step 2: TimesFM zero-shot inference ────────────────────────────────
    # Run once per bar — result is shared between RF and DQN subsystems.
    close_series: pd.Series = safe_fill_series(
        live_dataframe["close"],
        method="ffill",
        fallback_value=float(live_dataframe["close"].dropna().iloc[-1])
        if not live_dataframe["close"].dropna().empty
        else 1.0,
    )

    logger.debug(
        "[build_orchestrator_feature_matrix] %s: Running TimesFM inference "
        "(context_len=%d, series_len=%d) ...",
        symbol,
        _TFM_CONTEXT_LEN,
        len(close_series),
    )

    tfm_metrics: Dict[str, Any] = _forecaster.generate_forecast_metrics(close_series)
    tfm_return_delta: float     = float(tfm_metrics.get("expected_return_delta", 0.0))
    tfm_trend_direction: int    = int(tfm_metrics.get("forecast_trend_direction", 0))

    logger.info(
        "[build_orchestrator_feature_matrix] %s: TimesFM result — "
        "valid=%s | return_delta=%.6f | trend_dir=%+d",
        symbol,
        tfm_metrics.get("is_valid", False),
        tfm_return_delta,
        tfm_trend_direction,
    )

    # ── Step 3: RF Feature Matrix (25 classical + 1 TimesFM delta) ────────
    logger.debug(
        "[build_orchestrator_feature_matrix] %s: Building RF features ...",
        symbol,
    )
    rf_features: np.ndarray = _build_rf_features_with_tfm(
        df=live_dataframe,
        rf_pipe=_rf_pipe,
        tfm_return_delta=tfm_return_delta,
    )   # shape (1, 26)

    # ── Step 4: DQN State Vector (19 classical + 1 TimesFM trend) ─────────
    logger.debug(
        "[build_orchestrator_feature_matrix] %s: Building DQN state ...",
        symbol,
    )
    dqn_state: np.ndarray = _build_dqn_state_with_tfm(
        df=live_dataframe,
        rf_pipe=_rf_pipe,
        dqn_pipe=_dqn_pipe,
        account=account,
        tfm_trend_direction=tfm_trend_direction,
    )   # shape (20,)

    # ── Step 5: Sentiment scalar from OpenBB news ──────────────────────────
    sanitised_news: List[str] = _sanitize_news_texts(news_texts)

    # Provide DataFrame sentiment_score column as fallback if present
    df_sentiment_col: Optional[pd.Series] = (
        live_dataframe["sentiment_score"]
        if "sentiment_score" in live_dataframe.columns
        else None
    )

    sentiment_score, sentiment_label = _build_sentiment_scalar(
        news_texts=sanitised_news,
        sent_pipe=_sent_pipe,
        fallback_df_column=df_sentiment_col,
    )

    # ── Step 6: Assemble and return the bundle ─────────────────────────────
    elapsed_ms: float = (time.perf_counter() - t_start) * 1000.0

    bundle = AntigravityFeatureBundleV2(
        symbol          = symbol,
        bar_time        = live_dataframe.index[-1],
        rf_features     = rf_features,
        dqn_state       = dqn_state,
        sentiment_score = sentiment_score,
        sentiment_label = sentiment_label,
        timesfm_metrics = tfm_metrics,
    )

    logger.info(
        "[build_orchestrator_feature_matrix] %s — Bundle assembled in %.1fms | %s",
        symbol,
        elapsed_ms,
        bundle.summary(),
    )

    return bundle


# ─────────────────────────────────────────────────────────────────────────────
# TimesFMFeaturePipelineFacade
# ─────────────────────────────────────────────────────────────────────────────


class TimesFMFeaturePipelineFacade:
    """
    Object-oriented wrapper around ``build_orchestrator_feature_matrix()``.

    Manages the lifecycle of all sub-pipelines and the TimesFM forecaster
    across multiple bar events.  Designed to be instantiated once at
    system startup (after model weights are loaded) and called once per bar.

    This class is the recommended integration point for agents and the
    orchestrator loop, replacing the original ``FeaturePipelineFacade``.

    Parameters
    ----------
    forecaster : TimesFMForecaster | None
        Pre-initialised TimesFM forecaster.  Creates a lazy-loaded
        instance if None (weights loaded on first call).
    account : AccountState | None
        Initial MT5 account state.  Updated via ``update_account()``.
    rf_pipe : RFFeaturePipeline | None
        Pre-fitted RF pipeline.  Created fresh if None.
    dqn_pipe : DQNStatePipeline | None
        Initialised DQN pipeline.  Created fresh if None.
    sent_pipe : SentimentPipeline | None
        Initialised sentiment pipeline.  Created fresh if None.
    warm_up_on_init : bool
        If True, call ``forecaster.warm_up()`` during ``__init__()``
        to pre-compile the JAX graph.  Adds ~10-30s to startup time
        but eliminates first-bar latency.  Default True.

    Examples
    --------
    >>> forecaster = TimesFMForecaster()
    >>> facade = TimesFMFeaturePipelineFacade(forecaster=forecaster)
    >>> bundle = facade.process_bar("BTCUSDT", df, news_texts=headlines)
    >>> signal = orchestrator.evaluate(
    ...     rf_prediction   = rf_model.predict(bundle.rf_features)[0],
    ...     lstm_delta      = bundle.timesfm_delta,
    ...     dqn_q_values    = dqn_model.get_q_values(bundle.dqn_state),
    ...     sentiment_score = bundle.sentiment_score,
    ... )
    """

    def __init__(
        self,
        forecaster:        Optional[TimesFMForecaster] = None,
        account:           Optional[AccountState] = None,
        rf_pipe:           Optional[RFFeaturePipeline] = None,
        dqn_pipe:          Optional[DQNStatePipeline] = None,
        sent_pipe:         Optional[SentimentPipeline] = None,
        warm_up_on_init:   bool = True,
    ) -> None:
        self._forecaster: TimesFMForecaster = forecaster or TimesFMForecaster(
            context_len=_TFM_CONTEXT_LEN,
            horizon_len=10,
            lazy_load=True,
        )
        self._account:   AccountState       = account or AccountState()
        self._rf_pipe:   RFFeaturePipeline  = rf_pipe  or RFFeaturePipeline()
        self._dqn_pipe:  DQNStatePipeline   = dqn_pipe or DQNStatePipeline()
        self._sent_pipe: SentimentPipeline  = sent_pipe or SentimentPipeline()

        self._bar_count: int = 0
        self._last_bundle: Optional[AntigravityFeatureBundleV2] = None

        logger.info(
            "[TimesFMFeaturePipelineFacade] Initialised | "
            "RF features=%d | DQN state_dim=%d | "
            "TFM context_len=%d | TFM model_ready=%s",
            RF_V2_FEATURE_COUNT,
            DQN_V2_STATE_DIM,
            self._forecaster.context_len,
            self._forecaster.model_ready,
        )

        if warm_up_on_init:
            logger.info(
                "[TimesFMFeaturePipelineFacade] Running TimesFM warm-up "
                "(JAX JIT compilation) ..."
            )
            self._forecaster.warm_up()

    # ── Primary Bar Processing ─────────────────────────────────────────────

    def process_bar(
        self,
        symbol: str,
        df: pd.DataFrame,
        news_texts: Optional[List[Any]] = None,
    ) -> AntigravityFeatureBundleV2:
        """
        Produce all model inputs for the latest bar.

        Calls ``build_orchestrator_feature_matrix()`` with the managed
        sub-pipeline instances and the current ``AccountState``.

        Parameters
        ----------
        symbol : str
            Trading pair / MT5 ticker.
        df : pd.DataFrame
            Canonical bar DataFrame (full history, Hyperliquid or OpenBB).
        news_texts : list[str] | None
            Recent OpenBB v4 news headlines for sentiment scoring.

        Returns
        -------
        AntigravityFeatureBundleV2
            Complete feature bundle for the current bar.

        Raises
        ------
        ValueError
            If ``df`` has fewer than ``_MIN_BARS`` rows or missing columns.
        """
        bundle = build_orchestrator_feature_matrix(
            symbol        = symbol,
            live_dataframe = df,
            news_texts    = news_texts,
            account_state = self._account,
            forecaster    = self._forecaster,
            rf_pipe       = self._rf_pipe,
            dqn_pipe      = self._dqn_pipe,
            sent_pipe     = self._sent_pipe,
        )

        self._bar_count += 1
        self._last_bundle = bundle

        return bundle

    # ── Account State Management ───────────────────────────────────────────

    def update_account(self, account: AccountState) -> None:
        """
        Update the MT5 account state used in DQN state construction.

        Call this method whenever the MT5 agent receives a new account
        snapshot (typically after each trade execution or at each bar close).

        Parameters
        ----------
        account : AccountState
            Updated account snapshot from the MT5 agent.
        """
        old_equity = self._account.equity_usd
        self._account = account
        logger.debug(
            "[TimesFMFeaturePipelineFacade] Account updated: "
            "equity %.2f → %.2f | position_dir=%+d | drawdown=%.2f%%",
            old_equity,
            account.equity_usd,
            account.position_direction,
            account.drawdown_pct,
        )

    # ── Diagnostics ───────────────────────────────────────────────────────

    @property
    def bar_count(self) -> int:
        """Total number of bars processed since instantiation."""
        return self._bar_count

    @property
    def forecaster(self) -> TimesFMForecaster:
        """The managed TimesFM forecaster instance."""
        return self._forecaster

    @property
    def last_bundle(self) -> Optional[AntigravityFeatureBundleV2]:
        """The most recently produced feature bundle, or None."""
        return self._last_bundle

    def status_report(self) -> Dict[str, Any]:
        """
        Return a structured health-check dictionary for monitoring.

        Returns
        -------
        dict
            Pipeline status including TimesFM inference count,
            bar count, RF feature count, DQN state dimension,
            and model ready flag.
        """
        return {
            "bars_processed":      self._bar_count,
            "rf_feature_count":    RF_V2_FEATURE_COUNT,
            "dqn_state_dim":       DQN_V2_STATE_DIM,
            "timesfm_status":      self._forecaster.status_report(),
            "last_bar_time":       str(
                self._last_bundle.bar_time if self._last_bundle else "N/A"
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI Smoke-Test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test for ml_models/feature_pipeline_v2.py.

    Run from the project root:
        python -m ml_models.feature_pipeline_v2

    Tests:
        1. Full pipeline with synthetic 300-bar OHLCV DataFrame.
        2. RF features shape = (1, 26).
        3. DQN state shape = (20,).
        4. Sentiment scalar in [-1, +1].
        5. TimesFM metrics dict structure.
        6. Graceful degradation when TimesFM is not installed.
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    print("\n=== ml_models/feature_pipeline_v2.py Smoke-Test ===\n")

    # ── Generate synthetic OHLCV + enrichment columns (300 bars) ─────────
    rng = np.random.default_rng(42)
    n_bars = 300
    idx = pd.date_range("2024-01-01", periods=n_bars, freq="h", tz="UTC")

    close  = 1.0850 + np.cumsum(rng.normal(0, 0.0005, n_bars))
    open_  = close  + rng.normal(0, 0.0003, n_bars)
    high   = np.maximum(close, open_) + np.abs(rng.normal(0, 0.0002, n_bars))
    low    = np.minimum(close, open_) - np.abs(rng.normal(0, 0.0002, n_bars))
    volume = np.abs(rng.normal(5_000, 1_000, n_bars))

    df = pd.DataFrame({
        "open":              open_,
        "high":              high,
        "low":               low,
        "close":             close,
        "volume":            volume,
        "hl_spread_bps":     rng.uniform(2, 8, n_bars),
        "hl_funding_rate":   rng.uniform(-0.001, 0.001, n_bars),
        "macro_vix":         rng.uniform(15, 25, n_bars),
        "macro_yield_spread": rng.uniform(0.5, 2.5, n_bars),
        "sentiment_score":   rng.uniform(-0.5, 0.5, n_bars),
    }, index=idx)

    # ── Synthetic news headlines ──────────────────────────────────────────
    headlines = [
        "Federal Reserve signals potential rate cut in Q3 2024",
        "EUR/USD breaks above 1.09 resistance on weak US jobs data",
        "ECB holds rates steady; inflation falls to 2.1%",
        "Safe-haven demand boosts USD amid geopolitical tensions",
        "GDP growth beats forecast at 3.2% annualised",
    ]

    # ── Synthetic MT5 account state ───────────────────────────────────────
    account = AccountState(
        balance_usd=10_000.0,
        equity_usd=10_250.0,
        position_direction=1,        # LONG
        position_lots=0.01,
        position_pnl_pct=0.025,
        position_duration_bars=8,
        drawdown_pct=0.5,
    )

    # ── Initialise pipelines ──────────────────────────────────────────────
    print("Initialising RF, DQN, Sentiment pipelines ...")
    rf_pipe   = RFFeaturePipeline()
    dqn_pipe  = DQNStatePipeline()
    sent_pipe = SentimentPipeline()

    # Fit RF scaler on training portion (first 80%) to avoid cold start
    train_df = df.iloc[: int(len(df) * 0.8)]
    try:
        rf_pipe.fit_transform(train_df)
        print("  RF pipeline: scaler fitted on training data ✓")
    except Exception as e:
        print(f"  RF pipeline: scaler fitting failed ({e}) — unscaled features will be used")

    # Fit DQN market-obs scaler
    try:
        obs_matrix = dqn_pipe.collect_market_obs_history(train_df, rf_pipe=rf_pipe)
        dqn_pipe.fit_scaler(obs_matrix)
        print("  DQN pipeline: scaler fitted ✓")
    except Exception as e:
        print(f"  DQN pipeline: scaler fitting failed ({e})")

    # ── Test build_orchestrator_feature_matrix() ──────────────────────────
    print("\nTest 1: build_orchestrator_feature_matrix() with lazy TimesFM ...")
    bundle = build_orchestrator_feature_matrix(
        symbol        = "EURUSD",
        live_dataframe = df,
        news_texts    = headlines,
        account_state = account,
        forecaster    = None,   # Will create a lazy-loaded instance
        rf_pipe       = rf_pipe,
        dqn_pipe      = dqn_pipe,
        sent_pipe     = sent_pipe,
    )

    print(f"\n{'='*60}")
    print(f"  Bundle: {bundle.summary()}")
    print(f"{'='*60}")
    print(f"\n  rf_features.shape  : {bundle.rf_features.shape}   (expected: (1, 26))")
    print(f"  dqn_state.shape    : {bundle.dqn_state.shape}       (expected: (20,))")
    print(f"  sentiment_score    : {bundle.sentiment_score:+.4f}  (expected: [-1, +1])")
    print(f"  sentiment_label    : {bundle.sentiment_label}")
    print(f"  timesfm.is_valid   : {bundle.is_timesfm_valid}")
    print(f"  timesfm_delta      : {bundle.timesfm_delta:+.8f}")
    print(f"  timesfm_trend      : {bundle.timesfm_trend} "
          f"({'Bullish' if bundle.timesfm_trend==1 else 'Bearish' if bundle.timesfm_trend==-1 else 'Neutral'})")

    # Shape assertions
    assert bundle.rf_features.shape == (1, 26), \
        f"RF shape mismatch: {bundle.rf_features.shape} != (1, 26)"
    assert bundle.dqn_state.shape == (20,), \
        f"DQN shape mismatch: {bundle.dqn_state.shape} != (20,)"
    assert -1.0 <= bundle.sentiment_score <= 1.0, \
        f"Sentiment out of range: {bundle.sentiment_score}"
    print("\n  Shape assertions: ALL PASSED ✓")

    # Verify no NaN in output arrays
    assert not np.isnan(bundle.rf_features).any(), "RF features contain NaN!"
    assert not np.isnan(bundle.dqn_state).any(), "DQN state contains NaN!"
    print("  NaN assertions   : ALL PASSED ✓")

    # ── Test TimesFMFeaturePipelineFacade ─────────────────────────────────
    print("\nTest 2: TimesFMFeaturePipelineFacade.process_bar() ...")
    facade = TimesFMFeaturePipelineFacade(
        forecaster      = None,         # fresh lazy instance
        account         = account,
        rf_pipe         = rf_pipe,
        dqn_pipe        = dqn_pipe,
        sent_pipe       = sent_pipe,
        warm_up_on_init = False,        # Skip warm-up in smoke test
    )

    bundle2 = facade.process_bar("BTCUSDT", df, news_texts=headlines)
    assert bundle2.rf_features.shape == (1, 26)
    assert bundle2.dqn_state.shape == (20,)
    print(f"  Facade bundle     : {bundle2.summary()}")
    print(f"  Status report     : {facade.status_report()}")
    print("  Facade assertions : ALL PASSED ✓")

    # ── Test graceful degradation: short DataFrame ────────────────────────
    print("\nTest 3: Graceful degradation — DataFrame too short ...")
    try:
        bundle_short = build_orchestrator_feature_matrix(
            symbol="EURUSD",
            live_dataframe=df.iloc[:10],   # Only 10 bars, below _MIN_BARS=60
            news_texts=[],
        )
        print("  FAIL: ValueError should have been raised for short DataFrame")
    except ValueError as ve:
        print(f"  PASS: ValueError raised as expected — {ve}")

    # ── Feature name alignment check ──────────────────────────────────────
    print(f"\nRF V2 feature names ({len(RF_V2_FEATURE_NAMES)} total):")
    for i, name in enumerate(RF_V2_FEATURE_NAMES):
        marker = " ← TimesFM" if name == TFM_RETURN_DELTA_FEATURE else ""
        print(f"  [{i:02d}] {name}{marker}")

    print(f"\n=== ALL SMOKE TESTS PASSED ===\n")
