"""
==============================================================
ml_models/feature_pipeline.py — Antigravity Model Feature Pipeline
==============================================================
Transforms the unified LivePipeline DataFrame (from
``backend.core.live_pipeline``) into model-specific, production-ready
inputs for all four Antigravity ML models:

    Model 1 — Random Forest Classifier
        Input : 2-D feature matrix  (n_samples, n_features)
        Task  : Directional prediction (BUY / SELL / HOLD)
        Key features: RSI, realized volatility, MA crossovers,
                      ATR-normalized range, BB %B, spread regime

    Model 2 — LSTM Sequence Encoder
        Input : 3-D numpy array  (n_samples, 60, 5)
        Task  : Next-bar close prediction / sequence encoding
        Features: [close_norm, volume_norm, rsi, atr_norm, return_1h]
        Lookback: strict 60-candle window, zero-padding on warm-up

    Model 3 — Deep Q-Network (DQN) Agent
        Input : 1-D state vector  (n_state_dims,)
        Task  : Reinforcement learning — trade action selection
        State : market features + account balance + position status
        Actions: 0=HOLD, 1=BUY, 2=SELL, 3=CLOSE

    Model 4 — Sentiment Analyser
        Input : raw text (news headline / body)
        Output: polarity float in [-1.0, +1.0]
        Method: VADER lexicon (no GPU required) + keyword overrides
                for financial domain terminology

NaN Handling
------------
Every pipeline stage applies a deterministic three-step NaN protocol:
    1. ``ffill(limit=5)``   — propagate last valid value (gaps ≤ 5 bars)
    2. ``bfill(limit=2)``   — back-fill for leading NaN warm-up rows
    3. ``fillna(fill_val)`` — replace any remaining NaN with a safe
                              model-specific constant (0.0 for returns,
                              50.0 for RSI, etc.)

Scaling
-------
``StandardScaler`` is:
    - Fitted ONLY on training data to prevent look-ahead leakage.
    - Persisted alongside every model checkpoint via ``joblib``.
    - Exposed via ``get_scaler()`` so inference paths use the same
      fitted parameters.

Thread / async safety
---------------------
All pipeline classes are stateless with respect to market data.
The scaler state is immutable after fitting.  Multiple coroutines
may call ``transform_*`` methods concurrently without locking.

Usage
-----
    from ml_models.feature_pipeline import (
        RFFeaturePipeline,
        LSTMSequencePipeline,
        DQNStatePipeline,
        SentimentPipeline,
    )
    from backend.core.live_pipeline import LivePipeline

    # --- Random Forest ---
    rf_pipe  = RFFeaturePipeline()
    X, y     = rf_pipe.fit_transform(bar_df)
    X_live   = rf_pipe.transform_live(bar_df.iloc[[-1]])

    # --- LSTM ---
    lstm_pipe = LSTMSequencePipeline()
    X_seq     = lstm_pipe.build_sequences(bar_df)   # shape (N, 60, 5)
    X_live_3d = lstm_pipe.build_inference_window(bar_df)  # shape (1, 60, 5)

    # --- DQN ---
    dqn_pipe = DQNStatePipeline()
    state    = dqn_pipe.build_state(bar_df.iloc[-1], account)

    # --- Sentiment ---
    sent_pipe = SentimentPipeline()
    score     = sent_pipe.score("Fed raises interest rates by 25bps")
"""

from __future__ import annotations

import logging
import re
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("ml_models.feature_pipeline")


# ─────────────────────────────────────────────────────────────────────────────
# Shared constants
# ─────────────────────────────────────────────────────────────────────────────

# Minimum bars required before the pipeline produces valid output.
# Below this threshold methods return empty arrays / zero vectors.
_MIN_BARS: Final[int] = 60

# Scaler persistence directory (relative to project root)
_SCALER_DIR: Final[Path] = (
    Path(__file__).resolve().parent / "scalers"
)
_SCALER_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# NaN handling utilities
# ─────────────────────────────────────────────────────────────────────────────


def _safe_fill(
    df: pd.DataFrame,
    per_column_defaults: Optional[Dict[str, float]] = None,
    global_default: float = 0.0,
) -> pd.DataFrame:
    """
    Three-step NaN protocol applied to a DataFrame in-place on a copy.

    Protocol
    --------
    1. Forward-fill up to 5 consecutive missing values.
    2. Back-fill up to 2 remaining leading NaN rows.
    3. Fill any survivor NaN with a per-column default (or global_default).

    Parameters
    ----------
    df : pd.DataFrame
        Input frame (not mutated).
    per_column_defaults : dict | None
        Column-name → fill value for step 3 overrides.
    global_default : float
        Default fill value for columns not in ``per_column_defaults``.

    Returns
    -------
    pd.DataFrame
        Clean copy with no NaN values.
    """
    result = df.copy()
    result = result.ffill(limit=5).bfill(limit=2)

    per_col = per_column_defaults or {}
    for col in result.columns:
        fill_val = per_col.get(col, global_default)
        result[col] = result[col].fillna(fill_val)

    return result


def _require_columns(df: pd.DataFrame, cols: List[str], context: str) -> None:
    """Raise ``ValueError`` if any required column is absent."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{context}] Missing required columns: {missing}. "
            f"Available: {list(df.columns)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Technical indicator helpers (pure-pandas, no external TA library required)
# ─────────────────────────────────────────────────────────────────────────────


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed RSI in [0, 100]."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta).clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": (high - prev_close).abs(),
        "lc": (low  - prev_close).abs(),
    }).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def _bollinger_pct_b(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
    """Bollinger %B: position within bands [0=lower, 1=upper]."""
    mid = _sma(close, window)
    std = close.rolling(window=window, min_periods=1).std().replace(0, np.nan)
    upper = mid + n_std * std
    lower = mid - n_std * std
    band_w = (upper - lower).replace(0, np.nan)
    return ((close - lower) / band_w).fillna(0.5)


def _realized_vol(log_ret: pd.Series, window: int) -> pd.Series:
    """Annualized realized volatility: rolling std of log returns × √252."""
    return (
        log_ret.rolling(window=window, min_periods=max(1, window // 2)).std()
        * np.sqrt(252)
    )


def _ma_crossover(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """Normalized MA crossover: (EMA_fast - EMA_slow) / EMA_slow."""
    ema_f = _ema(close, fast)
    ema_s = _ema(close, slow)
    return ((ema_f - ema_s) / ema_s.replace(0, np.nan)).fillna(0.0)


def _macd_histogram(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    """MACD histogram = MACD line − signal line."""
    macd_line = _ema(close, fast) - _ema(close, slow)
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - sig_line


def _log_return(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1)).fillna(0.0)


def _stochastic_k(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    lowest  = low.rolling(period, min_periods=1).min()
    highest = high.rolling(period, min_periods=1).max()
    return (
        100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    ).fillna(50.0)


# ─────────────────────────────────────────────────────────────────────────────
# Model 1 — Random Forest Feature Pipeline
# ─────────────────────────────────────────────────────────────────────────────

# Feature registry — all column names produced by this pipeline
RF_FEATURE_NAMES: Final[List[str]] = [
    # ── Returns & Log Returns ─────────────────────────────────────────────
    "log_return",           # ln(close_t / close_{t-1})
    "return_1h",            # simple 1-bar % change
    "return_4h",            # 4-bar % change
    "return_24h",           # 24-bar (≈ daily on H1) % change
    # ── Volatility ────────────────────────────────────────────────────────
    "realized_vol_10",      # annualized vol over 10 bars
    "realized_vol_24",      # annualized vol over 24 bars (≈ 1 day on H1)
    "vol_regime",           # short_vol / long_vol (regime detection)
    "atr_norm",             # ATR / close (scale-free volatility)
    "bb_pct_b",             # Bollinger %B [0, 1]
    # ── Momentum ──────────────────────────────────────────────────────────
    "rsi_14",               # Wilder RSI [0, 100]
    "rsi_delta_5",          # RSI momentum: RSI_t − RSI_{t-5}
    "stoch_k",              # Stochastic %K [0, 100]
    "macd_hist",            # MACD histogram (momentum acceleration)
    # ── Trend ─────────────────────────────────────────────────────────────
    "ema_cross_9_21",       # (EMA9 − EMA21) / EMA21
    "ema_cross_21_50",      # (EMA21 − EMA50) / EMA50
    "ema_cross_50_200",     # (EMA50 − EMA200) / EMA200
    "price_vs_ema200",      # (close − EMA200) / EMA200
    # ── Hyperliquid enrichment (from LivePipeline) ─────────────────────────
    "hl_spread_bps",        # order-book spread in basis points
    "hl_funding_rate",      # perpetual funding rate (signed)
    # ── Macro context (from OpenBB) ────────────────────────────────────────
    "macro_vix_norm",       # VIX / 20 (normalised by long-run mean)
    "macro_yield_spread",   # 10Y-2Y Treasury spread
    # ── Candlestick patterns ───────────────────────────────────────────────
    "body_pct",             # |close - open| / (high - low)
    "upper_shadow",         # (high - max(O,C)) / (high - low)
    "lower_shadow",         # (min(O,C) - low) / (high - low)
    # ── Sentiment (from OpenBB news) ────────────────────────────────────────
    "sentiment_score",      # [-1, +1] from SentimentPipeline
]

# Safe fill defaults per feature (step 3 of NaN protocol)
_RF_NAN_DEFAULTS: Final[Dict[str, float]] = {
    "rsi_14": 50.0, "stoch_k": 50.0,
    "bb_pct_b": 0.5, "macro_vix_norm": 1.0,
    "hl_spread_bps": 5.0, "hl_funding_rate": 0.0,
    "macro_yield_spread": 0.0,
    "sentiment_score": 0.0,
}


class RFFeaturePipeline:
    """
    Feature engineering pipeline for the Random Forest classifier.

    Produces a 2-D ``(n_samples, n_features)`` float32 matrix from the
    canonical LivePipeline DataFrame.  The ``StandardScaler`` is fitted
    on the training partition and must be reused identically at inference.

    Parameters
    ----------
    scaler_path : Path | None
        Where to persist the fitted scaler.  Defaults to
        ``ml_models/scalers/rf_scaler.pkl``.
    """

    NAME: str = "RandomForest"

    def __init__(self, scaler_path: Optional[Path] = None) -> None:
        self._scaler_path = scaler_path or (_SCALER_DIR / "rf_scaler.pkl")
        self._scaler: Optional[StandardScaler] = None
        self._fitted: bool = False

    # ── Public API ─────────────────────────────────────────────────────────

    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all Random Forest features from a canonical bar DataFrame.

        The input ``df`` must contain at minimum: ``open``, ``high``,
        ``low``, ``close``, ``volume``.  Optional columns from LivePipeline
        (``hl_spread_bps``, ``hl_funding_rate``, ``macro_vix``,
        ``macro_yield_spread``, ``sentiment_score``) are used when present.

        Parameters
        ----------
        df : pd.DataFrame
            Canonical bar DataFrame from ``LivePipeline._merge_bar()``.

        Returns
        -------
        pd.DataFrame
            Feature-only DataFrame with columns matching ``RF_FEATURE_NAMES``.
            NaN values are fully resolved by ``_safe_fill()``.

        Raises
        ------
        ValueError
            If fewer than ``_MIN_BARS`` rows are available.
        """
        _require_columns(df, ["open", "high", "low", "close", "volume"], "RF.build_features")

        if len(df) < _MIN_BARS:
            raise ValueError(
                f"RF pipeline needs ≥{_MIN_BARS} bars; got {len(df)}."
            )

        feat = pd.DataFrame(index=df.index)

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        open_  = df["open"]

        log_ret = _log_return(close)

        # ── Returns ─────────────────────────────────────────────────────
        feat["log_return"]  = log_ret
        feat["return_1h"]   = close.pct_change(1).fillna(0.0)
        feat["return_4h"]   = close.pct_change(4).fillna(0.0)
        feat["return_24h"]  = close.pct_change(24).fillna(0.0)

        # ── Volatility ───────────────────────────────────────────────────
        rv10 = _realized_vol(log_ret, 10)
        rv24 = _realized_vol(log_ret, 24)
        feat["realized_vol_10"] = rv10
        feat["realized_vol_24"] = rv24
        feat["vol_regime"]  = (rv10 / rv24.replace(0, np.nan)).fillna(1.0)
        atr_val = _atr(high, low, close, 14)
        feat["atr_norm"]    = (atr_val / close.replace(0, np.nan)).fillna(0.0)
        feat["bb_pct_b"]    = _bollinger_pct_b(close)

        # ── Momentum ─────────────────────────────────────────────────────
        rsi14 = _rsi(close, 14)
        feat["rsi_14"]      = rsi14
        feat["rsi_delta_5"] = rsi14.diff(5).fillna(0.0)
        feat["stoch_k"]     = _stochastic_k(high, low, close, 14)
        feat["macd_hist"]   = _macd_histogram(close)

        # ── Trend ────────────────────────────────────────────────────────
        feat["ema_cross_9_21"]  = _ma_crossover(close, 9,  21)
        feat["ema_cross_21_50"] = _ma_crossover(close, 21, 50)
        feat["ema_cross_50_200"]= _ma_crossover(close, 50, 200)
        ema200 = _ema(close, 200)
        feat["price_vs_ema200"] = ((close - ema200) / ema200.replace(0, np.nan)).fillna(0.0)

        # ── Hyperliquid columns (optional) ───────────────────────────────
        feat["hl_spread_bps"]   = df.get("hl_spread_bps",   pd.Series(5.0, index=df.index))
        feat["hl_funding_rate"] = df.get("hl_funding_rate",  pd.Series(0.0, index=df.index))

        # ── Macro columns (optional) ──────────────────────────────────────
        vix = df.get("macro_vix", pd.Series(20.0, index=df.index))
        feat["macro_vix_norm"]      = (vix / 20.0).fillna(1.0)
        feat["macro_yield_spread"]  = df.get("macro_yield_spread", pd.Series(0.0, index=df.index))

        # ── Candlestick patterns ──────────────────────────────────────────
        candle_range = (high - low).replace(0, np.nan)
        feat["body_pct"]      = ((close - open_).abs() / candle_range).fillna(0.0)
        feat["upper_shadow"]  = ((high - df[["open", "close"]].max(axis=1)) / candle_range).fillna(0.0)
        feat["lower_shadow"]  = ((df[["open", "close"]].min(axis=1) - low) / candle_range).fillna(0.0)

        # ── Sentiment (optional) ─────────────────────────────────────────
        feat["sentiment_score"] = df.get("sentiment_score", pd.Series(0.0, index=df.index))

        # ── NaN resolution ────────────────────────────────────────────────
        feat = _safe_fill(feat, per_column_defaults=_RF_NAN_DEFAULTS)

        # Enforce column order matching RF_FEATURE_NAMES
        feat = feat[[c for c in RF_FEATURE_NAMES if c in feat.columns]]

        return feat

    def build_target(self, df: pd.DataFrame, horizon: int = 1) -> pd.Series:
        """
        Compute the directional classification target.

        Target encoding (3-class):
            +1  = close_{t+horizon} > close_t  × 1.0003  (UP with buffer)
            -1  = close_{t+horizon} < close_t  × 0.9997  (DOWN with buffer)
             0  = inside the ±0.03% neutral zone (HOLD)

        A small neutral buffer prevents the model from trading micro-noise.

        Parameters
        ----------
        df : pd.DataFrame
            Bar DataFrame with a ``close`` column.
        horizon : int
            How many bars ahead to predict (default 1).

        Returns
        -------
        pd.Series
            Integer series of {-1, 0, +1}.
        """
        future_close = df["close"].shift(-horizon)
        ratio = (future_close / df["close"])
        target = pd.Series(0, index=df.index, dtype=np.int8)
        target[ratio > 1.0003] =  1   # UP
        target[ratio < 0.9997] = -1   # DOWN
        return target

    def fit_transform(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        horizon: int = 1,
        random_state: int = 42,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
        """
        Full training-time pipeline: features + target + split + scaling.

        Parameters
        ----------
        df : pd.DataFrame
            Full historical bar DataFrame.
        test_size : float
            Fraction held out for evaluation.
        horizon : int
            Target lookahead in bars.
        random_state : int
            Seed for reproducible split.

        Returns
        -------
        tuple
            ``(X_train, X_test, y_train, y_test, feature_names)``
            where arrays are ``float32`` / ``int8`` numpy arrays.
        """
        from sklearn.model_selection import train_test_split

        feat_df = self.build_features(df)
        target  = self.build_target(df, horizon=horizon)

        # Align and drop NaN introduced by horizon shift
        mask = target.notna() & feat_df.notna().all(axis=1)
        X = feat_df[mask].values.astype(np.float32)
        y = target[mask].values.astype(np.int8)

        if len(X) < 60:
            raise ValueError(
                f"Insufficient training rows: {len(X)} < 60 after alignment."
            )

        # Temporal split — preserve time ordering (no random shuffling)
        split_idx = int(len(X) * (1 - test_size))
        X_train_raw, X_test_raw = X[:split_idx], X[split_idx:]
        y_train, y_test         = y[:split_idx], y[split_idx:]

        # Fit scaler on training partition ONLY
        self._scaler = StandardScaler()
        X_train = self._scaler.fit_transform(X_train_raw).astype(np.float32)
        X_test  = self._scaler.transform(X_test_raw).astype(np.float32)
        self._fitted = True

        self.save_scaler()

        logger.info(
            "[RF] fit_transform | train=%d test=%d features=%d | "
            "class dist: %s",
            len(X_train), len(X_test), X_train.shape[1],
            dict(zip(*np.unique(y_train, return_counts=True)))
        )

        return X_train, X_test, y_train, y_test, list(feat_df.columns)

    def transform_live(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform the latest bar for real-time inference.

        Uses only the last row of ``df`` after computing rolling features
        over the full history.  Requires a fitted scaler.

        Parameters
        ----------
        df : pd.DataFrame
            Recent bar history (at least ``_MIN_BARS`` rows).

        Returns
        -------
        np.ndarray
            Shape ``(1, n_features)`` float32 array.

        Raises
        ------
        RuntimeError
            If ``fit_transform()`` or ``load_scaler()`` has not been called.
        """
        if not self._fitted or self._scaler is None:
            self._try_load_scaler()

        feat_df = self.build_features(df)
        last_row = feat_df.iloc[[-1]].values.astype(np.float32)

        if self._scaler is not None:
            return self._scaler.transform(last_row).astype(np.float32)
        return last_row

    def save_scaler(self) -> None:
        """Persist the fitted StandardScaler to disk via joblib."""
        if self._scaler is None:
            return
        try:
            import joblib
            joblib.dump(self._scaler, str(self._scaler_path))
            logger.debug("[RF] Scaler saved to %s", self._scaler_path)
        except Exception as exc:
            logger.warning("[RF] Scaler save failed: %s", exc)

    def load_scaler(self) -> None:
        """Restore a previously saved scaler from disk."""
        try:
            import joblib
            self._scaler = joblib.load(str(self._scaler_path))
            self._fitted = True
            logger.info("[RF] Scaler loaded from %s", self._scaler_path)
        except Exception as exc:
            logger.warning("[RF] Scaler load failed: %s", exc)

    def _try_load_scaler(self) -> None:
        if self._scaler_path.is_file():
            self.load_scaler()
        else:
            raise RuntimeError(
                "RFFeaturePipeline: scaler not fitted. "
                "Call fit_transform() first, or load a persisted scaler."
            )

    @property
    def scaler(self) -> Optional[StandardScaler]:
        """The fitted StandardScaler, or None if not yet trained."""
        return self._scaler


# ─────────────────────────────────────────────────────────────────────────────
# Model 2 — LSTM Sequence Pipeline
# ─────────────────────────────────────────────────────────────────────────────

# The five features that form each time step of the LSTM input sequence.
# Order is significant — the LSTM weights are tied to this layout.
LSTM_FEATURES: Final[List[str]] = [
    "close_norm",   # close / ema200 (detrended, scale-free)
    "volume_norm",  # volume / rolling_mean_volume (relative activity)
    "rsi_14_norm",  # RSI / 100  (mapped to [0, 1])
    "atr_norm",     # ATR / close (scale-free volatility proxy)
    "return_1h",    # log return (signed momentum at each bar)
]

LSTM_LOOKBACK: Final[int] = 60  # strict 60-candle window (H1 = 60-hour context)
LSTM_N_FEATURES: Final[int] = len(LSTM_FEATURES)


class LSTMSequencePipeline:
    """
    Shapes H1 OHLCV data into 3-D LSTM input arrays.

    Output shape: ``(n_samples, 60, 5)``
        - Axis 0: sample index
        - Axis 1: time step (0 = oldest, 59 = most recent)
        - Axis 2: feature channel (matches ``LSTM_FEATURES``)

    Each feature is independently scaled using its own ``StandardScaler``
    fitted on the training partition.  This per-feature scaling preserves
    the relative magnitude differences across features while normalising
    each to zero mean / unit variance.

    Parameters
    ----------
    lookback : int
        Sequence length (default 60 bars).
    scaler_path : Path | None
        Persistence path for the fitted scaler bundle.
    """

    NAME: str = "LSTM"

    def __init__(
        self,
        lookback: int = LSTM_LOOKBACK,
        scaler_path: Optional[Path] = None,
    ) -> None:
        self._lookback    = lookback
        self._scaler_path = scaler_path or (_SCALER_DIR / "lstm_scaler.pkl")
        self._scalers: Dict[str, StandardScaler] = {}
        self._fitted: bool = False

    # ── Feature construction ───────────────────────────────────────────────

    def _build_feature_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the five LSTM features from a raw bar DataFrame.

        All features are designed to be:
        - Scale-free (no raw price values)
        - Bounded or approximately stationary
        - Valid even when HL/macro columns are absent

        Parameters
        ----------
        df : pd.DataFrame
            Bar frame with at minimum ``close``, ``volume``, ``high``, ``low``.

        Returns
        -------
        pd.DataFrame
            Columns: ``close_norm``, ``volume_norm``, ``rsi_14_norm``,
                     ``atr_norm``, ``return_1h``.
        """
        _require_columns(df, ["close", "volume", "high", "low"], "LSTM._build_feature_frame")

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]

        # 1. close_norm: detrend using EMA-200 to remove drift
        ema200 = _ema(close, 200)
        close_norm = (close / ema200.replace(0, np.nan)).fillna(1.0)

        # 2. volume_norm: volume relative to its 20-bar rolling mean
        vol_mean = volume.rolling(20, min_periods=1).mean().replace(0, np.nan)
        volume_norm = (volume / vol_mean).fillna(1.0).clip(0, 10)

        # 3. rsi_14_norm: RSI mapped to [0, 1]
        rsi_14_norm = _rsi(close, 14) / 100.0

        # 4. atr_norm: ATR as a fraction of close (volatility proxy)
        atr_val  = _atr(high, low, close, 14)
        atr_norm = (atr_val / close.replace(0, np.nan)).fillna(0.0)

        # 5. return_1h: log return for signed momentum
        return_1h = _log_return(close)

        feat = pd.DataFrame({
            "close_norm":  close_norm,
            "volume_norm": volume_norm,
            "rsi_14_norm": rsi_14_norm,
            "atr_norm":    atr_norm,
            "return_1h":   return_1h,
        }, index=df.index)

        # NaN fill with safe defaults
        defaults = {
            "close_norm":  1.0, "volume_norm": 1.0,
            "rsi_14_norm": 0.5, "atr_norm":    0.0,
            "return_1h":   0.0,
        }
        return _safe_fill(feat, per_column_defaults=defaults)

    # ── Sequence builder ───────────────────────────────────────────────────

    def build_sequences(
        self,
        df: pd.DataFrame,
        apply_scaling: bool = True,
    ) -> np.ndarray:
        """
        Convert a full bar history into sliding-window 3-D sequences.

        For each valid position ``t`` (where ``t >= lookback``), a sequence
        ``df[t-lookback : t]`` is extracted.  This produces N-lookback
        samples from N input rows.

        The ``StandardScaler`` is applied per-feature using scalers fitted
        during ``fit_scalers()``.  If scalers are not fitted, a runtime
        warning is emitted and raw (unscaled) features are returned.

        Parameters
        ----------
        df : pd.DataFrame
            Full bar history.  Minimum length: ``lookback + 1``.
        apply_scaling : bool
            Whether to apply the fitted scalers.

        Returns
        -------
        np.ndarray
            Shape ``(n_samples, lookback, n_features)`` float32.
        """
        feat_df = self._build_feature_frame(df)

        if apply_scaling and self._fitted:
            feat_df = self._apply_per_feature_scaling(feat_df)
        elif apply_scaling and not self._fitted:
            logger.warning(
                "[LSTM] Scalers not fitted; returning unscaled sequences. "
                "Call fit_scalers() first."
            )

        values = feat_df[LSTM_FEATURES].values.astype(np.float32)
        n = len(values)
        if n < self._lookback:
            raise ValueError(
                f"[LSTM] Need ≥{self._lookback} bars; got {n}."
            )

        # Build sliding windows using stride tricks for memory efficiency
        n_sequences = n - self._lookback
        sequences = np.lib.stride_tricks.as_strided(
            values,
            shape=(n_sequences, self._lookback, LSTM_N_FEATURES),
            strides=(
                values.strides[0],
                values.strides[0],
                values.strides[1],
            ),
        ).copy()  # .copy() breaks stride aliasing — required for safety

        return sequences  # (n_samples, 60, 5)

    def build_inference_window(self, df: pd.DataFrame) -> np.ndarray:
        """
        Build the single most-recent 60-candle window for live inference.

        Uses the last ``lookback`` rows of ``df``.  If the DataFrame has
        fewer than ``lookback`` rows, the sequence is zero-padded on the
        left (temporal padding) so the LSTM always receives a full window.

        Parameters
        ----------
        df : pd.DataFrame
            Recent bar history (as many bars as available).

        Returns
        -------
        np.ndarray
            Shape ``(1, 60, 5)`` float32 — a single-sample batch.
        """
        feat_df = self._build_feature_frame(df)

        if self._fitted:
            feat_df = self._apply_per_feature_scaling(feat_df)

        values = feat_df[LSTM_FEATURES].values.astype(np.float32)
        n = len(values)

        if n >= self._lookback:
            window = values[-self._lookback:]
        else:
            # Zero-pad on the left (older positions = absent data)
            pad_len = self._lookback - n
            window  = np.vstack([
                np.zeros((pad_len, LSTM_N_FEATURES), dtype=np.float32),
                values,
            ])

        return window[np.newaxis, :, :]   # shape: (1, 60, 5)

    def fit_scalers(self, df: pd.DataFrame) -> None:
        """
        Fit one StandardScaler per LSTM feature on training data.

        Scalers are fitted on raw (unscaled) feature values so that
        each feature channel is independently normalised to zero mean
        and unit variance.

        Parameters
        ----------
        df : pd.DataFrame
            Training partition of the bar history.
        """
        feat_df = self._build_feature_frame(df)
        for col in LSTM_FEATURES:
            values = feat_df[col].values.reshape(-1, 1)
            scaler = StandardScaler()
            scaler.fit(values)
            self._scalers[col] = scaler
        self._fitted = True
        self._save_scalers()
        logger.info("[LSTM] Per-feature scalers fitted for %s", LSTM_FEATURES)

    def _apply_per_feature_scaling(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted per-feature scalers to a feature DataFrame."""
        result = feat_df.copy()
        for col in LSTM_FEATURES:
            if col in self._scalers and col in result.columns:
                vals = result[col].values.reshape(-1, 1)
                result[col] = self._scalers[col].transform(vals).ravel()
        return result

    def _save_scalers(self) -> None:
        try:
            import joblib
            joblib.dump(self._scalers, str(self._scaler_path))
            logger.debug("[LSTM] Scalers saved to %s", self._scaler_path)
        except Exception as exc:
            logger.warning("[LSTM] Scaler save failed: %s", exc)

    def load_scalers(self) -> None:
        """Restore previously fitted per-feature scalers from disk."""
        try:
            import joblib
            self._scalers = joblib.load(str(self._scaler_path))
            self._fitted  = True
            logger.info("[LSTM] Scalers loaded from %s", self._scaler_path)
        except Exception as exc:
            logger.warning("[LSTM] Scaler load failed: %s", exc)

    @property
    def output_shape(self) -> Tuple[int, int]:
        """``(lookback, n_features)`` — input shape for the LSTM layer."""
        return (self._lookback, LSTM_N_FEATURES)


# ─────────────────────────────────────────────────────────────────────────────
# Model 3 — DQN State Space Pipeline
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AccountState:
    """
    Real-time account snapshot for DQN state construction.

    Attributes
    ----------
    balance_usd : float
        Current account balance in USD.
    equity_usd : float
        Current equity (balance ± unrealised P&L).
    position_direction : int
        -1 = SHORT, 0 = FLAT, +1 = LONG.
    position_lots : float
        Open lot size (0.0 when flat).
    position_pnl_pct : float
        Unrealised P&L as a fraction of balance (signed).
    position_duration_bars : int
        Number of H1 bars the position has been open.
    drawdown_pct : float
        Current drawdown percentage from peak equity.
    """
    balance_usd: float = 10_000.0
    equity_usd: float = 10_000.0
    position_direction: int = 0           # -1 SHORT | 0 FLAT | +1 LONG
    position_lots: float = 0.0
    position_pnl_pct: float = 0.0
    position_duration_bars: int = 0
    drawdown_pct: float = 0.0


# DQN actions
DQN_ACTIONS: Final[Dict[int, str]] = {
    0: "HOLD",
    1: "BUY",
    2: "SELL",
    3: "CLOSE",
}
DQN_N_ACTIONS: Final[int] = len(DQN_ACTIONS)

# State vector dimension registry
_DQN_MARKET_DIMS: Final[int] = 12   # market observation dimensions
_DQN_ACCOUNT_DIMS: Final[int] = 7   # account state dimensions
DQN_STATE_DIM: Final[int] = _DQN_MARKET_DIMS + _DQN_ACCOUNT_DIMS  # = 19


class DQNStatePipeline:
    """
    Constructs the observation state vector for the DQN trading agent.

    State vector layout (19 dimensions)
    ------------------------------------
    Market observations (12 dims):
        [0]  rsi_14_norm        RSI / 100 → [0, 1]
        [1]  atr_norm           ATR / close → ≈ [0, 0.05]
        [2]  bb_pct_b           Bollinger %B → ≈ [0, 1]
        [3]  ema_cross_9_21     fast/slow EMA crossover ratio
        [4]  ema_cross_21_50    medium/slow EMA crossover ratio
        [5]  vol_regime         short_vol / long_vol
        [6]  macd_hist_norm     MACD histogram / ATR (normalised)
        [7]  return_1h          log return of latest bar
        [8]  hl_spread_norm     HL spread_bps / 10 (normalised)
        [9]  hl_funding_rate    perpetual funding rate (signed)
        [10] macro_vix_norm     VIX / 20
        [11] sentiment_score    news sentiment [-1, +1]

    Account state (7 dims):
        [12] balance_norm       balance / 10 000 USD (normalised)
        [13] equity_norm        equity / 10 000 USD
        [14] position_dir       {-1, 0, +1}
        [15] position_lots_norm lots / 1.0 (normalised to standard lot)
        [16] pnl_pct            unrealised P&L fraction
        [17] duration_norm      bars_open / 24.0
        [18] drawdown_norm      drawdown_pct / 100.0

    Parameters
    ----------
    scaler_path : Path | None
        Persistence path for the fitted market-observation scaler.
    """

    NAME: str = "DQN"

    def __init__(self, scaler_path: Optional[Path] = None) -> None:
        self._scaler_path = scaler_path or (_SCALER_DIR / "dqn_scaler.pkl")
        self._scaler: Optional[StandardScaler] = None
        self._fitted: bool = False

    # ── State construction ─────────────────────────────────────────────────

    def build_market_obs(self, bar_row: pd.Series) -> np.ndarray:
        """
        Extract and normalise the 12-dimensional market observation from
        the latest bar row of the LivePipeline DataFrame.

        All features are designed to be approximately in [-3, +3] after
        StandardScaler normalisation, making them suitable for neural network
        input without gradient saturation.

        Parameters
        ----------
        bar_row : pd.Series
            A single row from the canonical bar DataFrame (the latest bar).

        Returns
        -------
        np.ndarray
            Shape ``(12,)`` float32 — raw (unscaled) market observation.
        """
        def _get(key: str, default: float = 0.0) -> float:
            val = bar_row.get(key, default)
            return float(val) if (val == val) else default   # NaN guard

        close = _get("close", 1.0)
        high  = _get("high",  close)
        low   = _get("low",   close)
        open_ = _get("open",  close)

        # Compute rolling indicators from a single row — use stored values
        # if available (pipeline already computed them), otherwise approximate.
        rsi    = _get("rsi_14",         50.0)    # RF pipeline may have added this
        atr    = _get("atr_norm",        0.0)
        bb_b   = _get("bb_pct_b",        0.5)
        xo_921 = _get("ema_cross_9_21",  0.0)
        xo_21  = _get("ema_cross_21_50", 0.0)
        vol_r  = _get("vol_regime",      1.0)
        macd_h = _get("macd_hist",       0.0)
        ret_1h = _get("return_1h",       0.0)
        spread = _get("hl_spread_bps",   5.0)
        fund   = _get("hl_funding_rate", 0.0)
        vix    = _get("macro_vix",      20.0)
        sent   = _get("sentiment_score", 0.0)

        # Normalise spread to avoid dominating the state
        spread_norm = spread / 10.0
        vix_norm    = vix / 20.0
        macd_norm   = macd_h / max(abs(atr * close), 1e-8)

        obs = np.array([
            rsi / 100.0,       # [0] rsi_14_norm
            atr,               # [1] atr_norm
            bb_b,              # [2] bb_pct_b
            xo_921,            # [3] ema_cross_9_21
            xo_21,             # [4] ema_cross_21_50
            vol_r,             # [5] vol_regime
            macd_norm,         # [6] macd_hist_norm
            ret_1h,            # [7] return_1h
            spread_norm,       # [8] hl_spread_norm
            fund,              # [9] hl_funding_rate
            vix_norm,          # [10] macro_vix_norm
            sent,              # [11] sentiment_score
        ], dtype=np.float32)

        # Clip to prevent extreme outliers from blowing up the network
        return np.clip(obs, -10.0, 10.0)

    def build_account_obs(self, account: AccountState) -> np.ndarray:
        """
        Encode the 7-dimensional account state into the observation vector.

        All values are normalised so they are approximately in [-1, +1]
        or [0, +1], making them compatible with the market observation
        without dominating by scale.

        Parameters
        ----------
        account : AccountState
            Current account snapshot.

        Returns
        -------
        np.ndarray
            Shape ``(7,)`` float32.
        """
        return np.array([
            account.balance_usd / 10_000.0,            # [12] balance_norm
            account.equity_usd  / 10_000.0,            # [13] equity_norm
            float(account.position_direction),          # [14] direction {-1,0,+1}
            account.position_lots / 1.0,               # [15] lots_norm
            account.position_pnl_pct,                  # [16] pnl_pct (signed)
            account.position_duration_bars / 24.0,     # [17] duration_norm
            account.drawdown_pct / 100.0,              # [18] drawdown_norm
        ], dtype=np.float32)

    def build_state(
        self,
        bar_row: pd.Series,
        account: AccountState,
        apply_scaling: bool = True,
    ) -> np.ndarray:
        """
        Assemble the full 19-dimensional DQN state vector.

        Concatenates the 12-dim market observation and the 7-dim account
        state.  If a fitted scaler is available, the market observation
        is normalised (the account state is already approximately normalised
        by design and is not scaled separately).

        Parameters
        ----------
        bar_row : pd.Series
            Latest bar row from the LivePipeline DataFrame.
        account : AccountState
            Current account snapshot.
        apply_scaling : bool
            Whether to apply the fitted market-obs scaler.

        Returns
        -------
        np.ndarray
            Shape ``(19,)`` float32 DQN state vector.
        """
        market_obs  = self.build_market_obs(bar_row)
        account_obs = self.build_account_obs(account)

        if apply_scaling and self._fitted and self._scaler is not None:
            market_obs = self._scaler.transform(
                market_obs.reshape(1, -1)
            ).ravel().astype(np.float32)

        state = np.concatenate([market_obs, account_obs])
        return np.clip(state, -10.0, 10.0)

    def fit_scaler(self, market_obs_matrix: np.ndarray) -> None:
        """
        Fit the market-observation StandardScaler on historical states.

        Parameters
        ----------
        market_obs_matrix : np.ndarray
            Shape ``(n_samples, 12)`` — stack of historical market observations
            collected from the training episode replay buffer.
        """
        self._scaler = StandardScaler()
        self._scaler.fit(market_obs_matrix)
        self._fitted = True
        self._save_scaler()
        logger.info(
            "[DQN] Market-obs scaler fitted on %d samples.", len(market_obs_matrix)
        )

    def collect_market_obs_history(
        self, df: pd.DataFrame, rf_pipe: Optional[RFFeaturePipeline] = None
    ) -> np.ndarray:
        """
        Materialise a full matrix of market observations from a bar history.

        This is used to fit the market-obs scaler on the training window.
        Each bar becomes one row of the ``(n, 12)`` output matrix.

        Parameters
        ----------
        df : pd.DataFrame
            Full bar history.
        rf_pipe : RFFeaturePipeline | None
            Optional pre-built RF feature frame — avoids recomputing
            indicators when the RF pipeline has already run on this DataFrame.

        Returns
        -------
        np.ndarray
            Shape ``(n_bars, 12)`` float32.
        """
        if rf_pipe is not None and rf_pipe._fitted:
            feat_df = rf_pipe.build_features(df)
        else:
            feat_df = RFFeaturePipeline().build_features(df)

        # Merge feat_df back into df so bar_row.get() finds everything
        merged = df.copy()
        for col in feat_df.columns:
            merged[col] = feat_df[col]

        obs_list = [
            self.build_market_obs(merged.iloc[i])
            for i in range(len(merged))
        ]
        return np.vstack(obs_list).astype(np.float32)

    def _save_scaler(self) -> None:
        try:
            import joblib
            joblib.dump(self._scaler, str(self._scaler_path))
        except Exception as exc:
            logger.warning("[DQN] Scaler save failed: %s", exc)

    def load_scaler(self) -> None:
        """Restore a previously fitted market-obs scaler."""
        try:
            import joblib
            self._scaler = joblib.load(str(self._scaler_path))
            self._fitted = True
            logger.info("[DQN] Scaler loaded from %s", self._scaler_path)
        except Exception as exc:
            logger.warning("[DQN] Scaler load failed: %s", exc)

    @property
    def state_dim(self) -> int:
        """Total state vector length: market + account dimensions."""
        return DQN_STATE_DIM

    @property
    def n_actions(self) -> int:
        """Number of discrete DQN actions: 4 (HOLD/BUY/SELL/CLOSE)."""
        return DQN_N_ACTIONS


# ─────────────────────────────────────────────────────────────────────────────
# Model 4 — Sentiment Analysis Pipeline
# ─────────────────────────────────────────────────────────────────────────────

# ── Financial domain VADER lexicon overrides ──────────────────────────────────
# These weights correct VADER's general-English bias for financial text.
# Positive polarity words that are strongly bullish in trading context.
_FIN_POS_OVERRIDES: Final[Dict[str, float]] = {
    "bullish": 3.0, "outperform": 2.5, "upgrade": 2.0, "beat": 2.5,
    "breakout": 2.0, "rally": 2.5, "surge": 2.5, "record": 1.8,
    "strong": 1.5, "growth": 1.5, "profits": 1.5, "raised": 1.8,
    "exceeded": 2.0, "expansion": 1.5, "hawkish": -1.5,  # rate hike context
    "taper": -1.0, "buy": 1.5, "long": 0.8,
    "quantitative_easing": 1.5, "stimulus": 1.5, "cut_rates": 2.0,
    "rate_cut": 2.0, "dovish": 1.5, "soft_landing": 2.0,
}

_FIN_NEG_OVERRIDES: Final[Dict[str, float]] = {
    "bearish": -3.0, "underperform": -2.5, "downgrade": -2.0,
    "miss": -2.5, "plunge": -2.5, "collapse": -3.0, "crash": -3.0,
    "weak": -1.5, "layoff": -2.0, "bankrupt": -3.0, "fraud": -3.0,
    "recall": -2.0, "sell": -1.5, "short": -0.8,
    "rate_hike": -1.5, "inflation": -1.2, "recession": -2.5,
    "stagflation": -2.5, "default": -3.0, "debt_ceiling": -2.0,
    "quantitative_tightening": -1.5, "hawkish": -1.5,
}

# Minimum absolute polarity before a reading is considered non-neutral
_NEUTRALITY_THRESHOLD: Final[float] = 0.05


class SentimentPipeline:
    """
    Fast, offline sentiment scorer for financial news text.

    Method
    ------
    1. **VADER** (Valence Aware Dictionary and sEntiment Reasoner):
       A rule-based lexicon optimised for social media / short text.
       Returns a compound score in [-1, +1].
    2. **Financial domain overrides**: A curated lexicon of 40+ terms
       corrects VADER's general-English bias (e.g. "strong" is 1.5×
       more positive in earnings context; "hawkish" is negative).
    3. **Numerical boosting**: Percentage values and dollar-figure
       contexts are detected and used to amplify the polarity signal.

    VADER falls back to ``TextBlob`` if not installed, and further
    falls back to a purely keyword-based baseline if neither is available.
    This ensures the pipeline is always operational.

    Parameters
    ----------
    use_vader : bool
        Use VADER scoring (default True).  Set False to force keyword-only.
    """

    NAME: str = "Sentiment"

    def __init__(self, use_vader: bool = True) -> None:
        self._vader_available: bool = False
        self._textblob_available: bool = False
        self._analyzer = None

        if use_vader:
            self._vader_available = self._try_init_vader()
        if not self._vader_available:
            self._textblob_available = self._try_init_textblob()

        if not self._vader_available and not self._textblob_available:
            logger.warning(
                "[Sentiment] Neither VADER nor TextBlob available. "
                "Using keyword-only baseline. "
                "Install: pip install vaderSentiment  OR  textblob"
            )

    # ── Public API ─────────────────────────────────────────────────────────

    def score(self, text: str) -> float:
        """
        Compute a financial sentiment polarity score for a piece of text.

        Scoring pipeline
        ----------------
        1. Clean and normalise the input text.
        2. Score with VADER / TextBlob / keyword baseline.
        3. Apply financial domain override adjustments.
        4. Apply numerical context boosting (large % moves amplify sentiment).
        5. Clip to [-1.0, +1.0] and apply neutrality threshold.

        Parameters
        ----------
        text : str
            Raw news headline or article text.

        Returns
        -------
        float
            Polarity score in [-1.0, +1.0]:
                +1.0 = extremely bullish
                 0.0 = neutral
                -1.0 = extremely bearish
        """
        if not text or not isinstance(text, str):
            return 0.0

        cleaned = self._clean(text)

        # ── Base score from primary scorer ─────────────────────────────
        if self._vader_available and self._analyzer is not None:
            base = float(self._analyzer.polarity_scores(cleaned)["compound"])
        elif self._textblob_available:
            base = self._textblob_score(cleaned)
        else:
            base = self._keyword_score(cleaned)

        # ── Financial domain adjustments ───────────────────────────────
        base += self._domain_override_adjustment(cleaned)

        # ── Numerical context boost ────────────────────────────────────
        base += self._numeric_boost(cleaned)

        # ── Clip, neutralise, and return ───────────────────────────────
        score = float(np.clip(base, -1.0, 1.0))
        if abs(score) < _NEUTRALITY_THRESHOLD:
            score = 0.0

        return round(score, 4)

    def score_batch(self, texts: List[str]) -> np.ndarray:
        """
        Score a list of texts and return their polarities.

        Parameters
        ----------
        texts : list[str]
            News headlines or body texts.

        Returns
        -------
        np.ndarray
            Shape ``(n,)`` float32 polarity scores.
        """
        return np.array([self.score(t) for t in texts], dtype=np.float32)

    def aggregate(
        self,
        texts: List[str],
        method: str = "weighted_mean",
    ) -> Tuple[float, str]:
        """
        Aggregate multiple sentiment scores into a single reading.

        Parameters
        ----------
        texts : list[str]
            Collection of news items (headlines / bodies).
        method : str
            Aggregation method:
            - ``"mean"``          : simple arithmetic mean
            - ``"weighted_mean"`` : weight recent items higher (exponential)
            - ``"majority_vote"`` : sign of the median

        Returns
        -------
        tuple[float, str]
            ``(aggregate_score, label)`` where label is one of
            ``"BULLISH"``, ``"BEARISH"``, or ``"NEUTRAL"``.
        """
        if not texts:
            return 0.0, "NEUTRAL"

        scores = self.score_batch(texts)

        if method == "mean":
            agg = float(np.mean(scores))
        elif method == "weighted_mean":
            weights = np.exp(np.linspace(0, 1, len(scores)))
            weights /= weights.sum()
            agg = float(np.dot(weights, scores))
        elif method == "majority_vote":
            agg = float(np.sign(np.median(scores)))
        else:
            raise ValueError(f"Unknown aggregation method: {method!r}")

        agg = round(float(np.clip(agg, -1.0, 1.0)), 4)
        label = (
            "BULLISH"  if agg >  0.05 else
            "BEARISH"  if agg < -0.05 else
            "NEUTRAL"
        )
        return agg, label

    def score_openbb_news_df(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score a complete OpenBB news DataFrame in-place.

        Expected input: DataFrame from ``DataService.get_equity_news()``
        with a ``title`` column and optionally a ``text`` / ``body`` column.

        The pipeline concatenates title + first 200 chars of body for
        richer context while keeping scoring fast.

        Parameters
        ----------
        news_df : pd.DataFrame
            OpenBB news DataFrame.

        Returns
        -------
        pd.DataFrame
            Original DataFrame with two new columns:
            - ``ag_sentiment_score``  : polarity float [-1, +1]
            - ``ag_sentiment_label``  : "BULLISH" | "BEARISH" | "NEUTRAL"
        """
        result = news_df.copy()

        def _row_text(row: pd.Series) -> str:
            title = str(row.get("title", "") or "")
            body  = str(row.get("text",  row.get("body", "")) or "")
            return title + " " + body[:200]

        scores = [self.score(_row_text(row)) for _, row in result.iterrows()]
        result["ag_sentiment_score"] = scores
        result["ag_sentiment_label"] = [
            "BULLISH" if s >  0.05 else
            "BEARISH" if s < -0.05 else
            "NEUTRAL"
            for s in scores
        ]
        return result

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Lowercase, strip HTML tags, normalise whitespace."""
        text = re.sub(r"<[^>]+>", " ", text)           # strip HTML
        text = re.sub(r"[^\w\s%$.,+-]", " ", text)    # keep financial chars
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text

    def _try_init_vader(self) -> bool:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            analyzer = SentimentIntensityAnalyzer()
            # Inject financial domain overrides into the VADER lexicon
            for word, score in {**_FIN_POS_OVERRIDES, **_FIN_NEG_OVERRIDES}.items():
                analyzer.lexicon[word.replace("_", " ")] = score
                analyzer.lexicon[word] = score
            self._analyzer = analyzer
            logger.debug("[Sentiment] VADER initialized with financial overrides.")
            return True
        except ImportError:
            return False

    def _try_init_textblob(self) -> bool:
        try:
            from textblob import TextBlob  # noqa: F401
            return True
        except ImportError:
            return False

    def _textblob_score(self, text: str) -> float:
        from textblob import TextBlob
        return float(TextBlob(text).sentiment.polarity)

    def _keyword_score(self, text: str) -> float:
        """Fallback: simple weighted keyword counter."""
        score = 0.0
        tokens = text.split()
        for token in tokens:
            pos = _FIN_POS_OVERRIDES.get(token, 0.0)
            neg = _FIN_NEG_OVERRIDES.get(token, 0.0)
            score += pos + neg
        # Normalise by token count to get a per-token average
        return float(np.clip(score / max(len(tokens), 1), -1.0, 1.0))

    def _domain_override_adjustment(self, text: str) -> float:
        """
        Scan text for financial domain override terms and accumulate
        their delta contributions beyond the base scorer's vocabulary.
        """
        adjustment = 0.0
        tokens = set(re.findall(r"\b\w+\b", text))
        for phrase, weight in {**_FIN_POS_OVERRIDES, **_FIN_NEG_OVERRIDES}.items():
            if phrase.replace("_", " ") in text or phrase in tokens:
                # Apply a fractional adjustment (base scorer may have partially caught it)
                adjustment += weight * 0.15
        return float(np.clip(adjustment, -0.5, 0.5))

    def _numeric_boost(self, text: str) -> float:
        """
        Detect large numeric moves (e.g. '+5%', '-$200M') and use their
        sign and magnitude to amplify the sentiment signal.

        Logic:
            - A positive %-figure alongside positive sentiment amplifies.
            - A negative %-figure alongside negative sentiment amplifies.
            - Magnitude scales the boost: ±5% → ±0.1, ±20%+ → ±0.3 cap.
        """
        # Match patterns like "+3.5%", "-12%", "up 8%", "down 4.2%"
        pct_matches = re.findall(
            r"(up|down|[+-])?\s*([\d]+\.?\d*)\s*%", text
        )
        boost = 0.0
        for direction, magnitude in pct_matches:
            try:
                mag  = float(magnitude)
                sign = -1.0 if direction in ("down", "-") else 1.0
                boost += sign * min(mag / 100.0, 0.3)
            except ValueError:
                pass
        return float(np.clip(boost, -0.5, 0.5))


# ─────────────────────────────────────────────────────────────────────────────
# Unified pipeline façade
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AntigravityFeatureBundle:
    """
    Single object containing all model-specific feature outputs for one bar.

    Produced by ``FeaturePipelineFacade.process_bar()`` and consumed by
    the model ensemble or individual agents.

    Attributes
    ----------
    symbol : str
        MT5 ticker this bundle was produced for.
    bar_time : Any
        Index timestamp of the bar.
    rf_features : np.ndarray
        Shape ``(1, n_rf_features)`` float32 — RF inference input.
    lstm_window : np.ndarray
        Shape ``(1, 60, 5)`` float32 — LSTM inference input.
    dqn_state : np.ndarray
        Shape ``(19,)`` float32 — DQN state vector.
    sentiment_score : float
        Latest news sentiment in [-1, +1].
    sentiment_label : str
        "BULLISH" | "BEARISH" | "NEUTRAL".
    produced_at : float
        UNIX timestamp of bundle assembly.
    """

    symbol: str
    bar_time: Any
    rf_features: np.ndarray
    lstm_window: np.ndarray
    dqn_state: np.ndarray
    sentiment_score: float
    sentiment_label: str
    produced_at: float = field(default_factory=time.time)


class FeaturePipelineFacade:
    """
    Façade that coordinates all four model-specific feature pipelines.

    Use this class instead of instantiating individual pipelines when
    the system processes bars through the full model ensemble.

    Parameters
    ----------
    account : AccountState
        Current account state for DQN state construction.
    rf_pipe : RFFeaturePipeline | None
        Pre-initialised RF pipeline (created if None).
    lstm_pipe : LSTMSequencePipeline | None
        Pre-initialised LSTM pipeline (created if None).
    dqn_pipe : DQNStatePipeline | None
        Pre-initialised DQN pipeline (created if None).
    sent_pipe : SentimentPipeline | None
        Pre-initialised sentiment pipeline (created if None).
    """

    def __init__(
        self,
        account: Optional[AccountState] = None,
        rf_pipe: Optional[RFFeaturePipeline] = None,
        lstm_pipe: Optional[LSTMSequencePipeline] = None,
        dqn_pipe: Optional[DQNStatePipeline] = None,
        sent_pipe: Optional[SentimentPipeline] = None,
    ) -> None:
        self.account   = account or AccountState()
        self.rf_pipe   = rf_pipe   or RFFeaturePipeline()
        self.lstm_pipe = lstm_pipe or LSTMSequencePipeline()
        self.dqn_pipe  = dqn_pipe  or DQNStatePipeline()
        self.sent_pipe = sent_pipe or SentimentPipeline()

        logger.info(
            "FeaturePipelineFacade ready | DQN state_dim=%d | "
            "LSTM shape=%s | RF features=%d",
            self.dqn_pipe.state_dim,
            self.lstm_pipe.output_shape,
            len(RF_FEATURE_NAMES),
        )

    def process_bar(
        self,
        symbol: str,
        df: pd.DataFrame,
        news_texts: Optional[List[str]] = None,
    ) -> AntigravityFeatureBundle:
        """
        Produce all model inputs for the latest bar in one call.

        Parameters
        ----------
        symbol : str
            MT5 ticker.
        df : pd.DataFrame
            Canonical bar DataFrame from LivePipeline (full history).
        news_texts : list[str] | None
            Recent news headlines/bodies for sentiment scoring.

        Returns
        -------
        AntigravityFeatureBundle
        """
        if len(df) < _MIN_BARS:
            raise ValueError(
                f"FeaturePipelineFacade.process_bar: need ≥{_MIN_BARS} bars; "
                f"got {len(df)} for {symbol}."
            )

        # ── RF features ───────────────────────────────────────────────────
        rf_features = self.rf_pipe.transform_live(df)   # (1, n_rf)

        # ── LSTM window ───────────────────────────────────────────────────
        lstm_window = self.lstm_pipe.build_inference_window(df)   # (1, 60, 5)

        # ── DQN state ─────────────────────────────────────────────────────
        latest_row = df.iloc[-1].copy()
        # Merge RF features into latest_row so DQN can read pre-computed indicators
        try:
            rf_feat_df = self.rf_pipe.build_features(df)
            for col in rf_feat_df.columns:
                latest_row[col] = rf_feat_df[col].iloc[-1]
        except Exception:
            pass
        dqn_state = self.dqn_pipe.build_state(latest_row, self.account)   # (19,)

        # ── Sentiment ─────────────────────────────────────────────────────
        if news_texts:
            sent_score, sent_label = self.sent_pipe.aggregate(news_texts)
        else:
            sent_col = df.get("sentiment_score")
            if sent_col is not None and not sent_col.empty:
                s = float(sent_col.iloc[-1])
                sent_score = s if s == s else 0.0   # NaN guard
            else:
                sent_score = 0.0
            sent_label = (
                "BULLISH" if sent_score >  0.05 else
                "BEARISH" if sent_score < -0.05 else
                "NEUTRAL"
            )

        return AntigravityFeatureBundle(
            symbol          = symbol,
            bar_time        = df.index[-1],
            rf_features     = rf_features,
            lstm_window     = lstm_window,
            dqn_state       = dqn_state,
            sentiment_score = sent_score,
            sentiment_label = sent_label,
        )

    def update_account(self, account: AccountState) -> None:
        """Update the account state used for DQN state construction."""
        self.account = account


# ─────────────────────────────────────────────────────────────────────────────
# CLI smoke-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test — validates all four pipelines with synthetic data.

    Run from project root:
        python -m ml_models.feature_pipeline

    Expected output:
        [RF]   X_train shape: (N, 25)  X_test: (M, 25)
        [LSTM] sequences shape: (K, 60, 5)  inference: (1, 60, 5)
        [DQN]  state shape: (19,)  state vector: [...]
        [SENT] score="Fed raises rates" → -0.25 [BEARISH]
        ALL PASS
    """
    import sys
    out = sys.stdout.buffer

    def _p(msg: str) -> None:
        out.write((msg + "\n").encode("utf-8"))
        out.flush()

    _p("\n=== Antigravity Feature Pipeline Smoke-Test ===\n")

    # ── Generate synthetic OHLCV + pipeline columns ──────────────────────
    np.random.seed(42)
    n_bars = 300
    idx    = pd.date_range("2024-01-01", periods=n_bars, freq="h", tz="UTC")

    close  = 1.0850 + np.cumsum(np.random.randn(n_bars) * 0.0005)
    open_  = close + np.random.randn(n_bars) * 0.0003
    high   = np.maximum(close, open_) + np.abs(np.random.randn(n_bars)) * 0.0002
    low    = np.minimum(close, open_) - np.abs(np.random.randn(n_bars)) * 0.0002
    volume = np.abs(np.random.randn(n_bars)) * 1_000 + 5_000

    df = pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
        "hl_spread_bps":    np.random.uniform(2, 8, n_bars),
        "hl_funding_rate":  np.random.uniform(-0.001, 0.001, n_bars),
        "macro_vix":        np.random.uniform(15, 25, n_bars),
        "macro_yield_spread": np.random.uniform(0.5, 2.5, n_bars),
        "sentiment_score":  np.random.uniform(-0.5, 0.5, n_bars),
    }, index=idx)

    # ── Model 1: Random Forest ────────────────────────────────────────────
    rf_pipe = RFFeaturePipeline()
    X_train, X_test, y_train, y_test, feat_names = rf_pipe.fit_transform(df)
    _p(f"[RF]   X_train: {X_train.shape}  X_test: {X_test.shape}  features: {len(feat_names)}")
    _p(f"       feature_names[0:5]: {feat_names[:5]}")
    _p(f"       y distribution (train): {dict(zip(*np.unique(y_train, return_counts=True)))}")

    # ── Model 2: LSTM ─────────────────────────────────────────────────────
    lstm_pipe = LSTMSequencePipeline()
    lstm_pipe.fit_scalers(df.iloc[:int(len(df)*0.8)])     # fit on training portion
    sequences = lstm_pipe.build_sequences(df)
    inference = lstm_pipe.build_inference_window(df)
    _p(f"\n[LSTM] sequences: {sequences.shape}  inference window: {inference.shape}")
    _p(f"       output_shape (lookback, features): {lstm_pipe.output_shape}")
    _p(f"       last step sample: {sequences[-1, -1, :]}")

    # ── Model 3: DQN ─────────────────────────────────────────────────────
    dqn_pipe = DQNStatePipeline()
    # Fit market-obs scaler using first 80% of bars
    market_obs_matrix = dqn_pipe.collect_market_obs_history(
        df.iloc[:int(len(df)*0.8)], rf_pipe=rf_pipe
    )
    dqn_pipe.fit_scaler(market_obs_matrix)

    account = AccountState(
        balance_usd=10_000, equity_usd=10_250,
        position_direction=1, position_lots=0.01,
        position_pnl_pct=0.025, position_duration_bars=8,
        drawdown_pct=0.5,
    )
    state = dqn_pipe.build_state(df.iloc[-1], account)
    _p(f"\n[DQN]  state_dim={dqn_pipe.state_dim} | n_actions={dqn_pipe.n_actions}")
    _p(f"       state vector: {state.round(4)}")
    _p(f"       market_obs matrix shape: {market_obs_matrix.shape}")

    # ── Model 4: Sentiment ────────────────────────────────────────────────
    sent_pipe = SentimentPipeline()
    headlines = [
        "Federal Reserve raises interest rates by 25bps amid inflation concerns",
        "US markets surge to record highs as earnings beat expectations",
        "Oil prices plunge on OPEC supply glut fears",
        "GDP growth exceeds forecasts; unemployment falls to 3.8%",
        "Central bank signals rate cut amid economic slowdown",
    ]
    scores = sent_pipe.score_batch(headlines)
    agg_score, agg_label = sent_pipe.aggregate(headlines)
    _p(f"\n[SENT] Individual scores:")
    for h, s in zip(headlines, scores):
        lbl = "BULLISH" if s > 0.05 else "BEARISH" if s < -0.05 else "NEUTRAL"
        _p(f"       {s:+.4f} [{lbl:7s}] '{h[:60]}'")
    _p(f"       Aggregate: {agg_score:+.4f} [{agg_label}]")

    # ── Façade ────────────────────────────────────────────────────────────
    facade  = FeaturePipelineFacade(
        account=account, rf_pipe=rf_pipe,
        lstm_pipe=lstm_pipe, dqn_pipe=dqn_pipe, sent_pipe=sent_pipe
    )
    bundle  = facade.process_bar("EURUSD", df, news_texts=headlines)
    _p(f"\n[FACADE] AntigravityFeatureBundle for {bundle.symbol}")
    _p(f"       bar_time       : {bundle.bar_time}")
    _p(f"       rf_features    : {bundle.rf_features.shape}")
    _p(f"       lstm_window    : {bundle.lstm_window.shape}")
    _p(f"       dqn_state      : {bundle.dqn_state.shape}")
    _p(f"       sentiment_score: {bundle.sentiment_score} [{bundle.sentiment_label}]")

    _p("\n=== ALL PASS ===\n")
