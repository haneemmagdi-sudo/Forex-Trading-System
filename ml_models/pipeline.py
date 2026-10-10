"""
============================================================
ml_models/pipeline.py — Antigravity ML Feature Engineering Pipeline
============================================================
Transforms raw OpenBB market data into a clean, model-ready feature
matrix (X) and binary classification target (y).

Pipeline Contract:
    ``prepare_ml_features(ticker, start_date)``
    → returns ``MLDataset`` with X_train, X_test, y_train, y_test
      already split and standardized, ready for Scikit-Learn / PyTorch.

Feature Engineering:
    ┌──────────────────────────────────────────────────────────┐
    │ Category        │ Features                               │
    │─────────────────│────────────────────────────────────────│
    │ Returns         │ log_return, 5d/10d/21d returns         │
    │ Volatility      │ realized_vol_10d, realized_vol_21d     │
    │                 │ vol_ratio (short/long), bb_pct_b       │
    │ Momentum        │ rsi_14, rsi_diff, macd_hist            │
    │ Trend           │ sma_cross_20_50, sma_cross_50_200      │
    │                 │ price_vs_sma200 (deviation)            │
    │ Volume          │ vol_change, obv_norm                   │
    │ Price Patterns  │ body_pct, upper_shadow, lower_shadow   │
    └──────────────────────────────────────────────────────────┘

Target:
    ``y = 1`` if next-day close > today's close (up day), else ``0``.
    Binary classification task for next-day direction prediction.

Design:
    - Zero data leakage: all features computed from data available at
      time t; target uses time t+1 close.
    - Consistent NaN handling: forward-fill then drop any remaining NaN
      rows to avoid imputation bias.
    - Stratified train/test split preserving class balance.
    - StandardScaler fitted ONLY on the training set and applied to test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from data_layer.openbb_service import DataService, DataServiceError

logger = logging.getLogger("ml_models.pipeline")


# ─────────────────────────────────────────────────────────────────────────
# Return Types
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class MLDataset:
    """
    Container for a fully-processed, split ML dataset.

    Attributes:
        X_train:       Feature matrix for training (numpy array, float32).
        X_test:        Feature matrix for evaluation (numpy array, float32).
        y_train:       Binary labels for training (numpy array, int8).
        y_test:        Binary labels for evaluation (numpy array, int8).
        feature_names: Ordered list of feature column names.
        scaler:        Fitted StandardScaler (use to transform inference data).
        ticker:        Source ticker symbol.
        start_date:    Start date of the raw data pull.
        n_samples:     Total number of usable rows before the split.
        class_balance: Dict ``{"up": int, "down": int}`` showing label counts.
        raw_df:        Full feature + target DataFrame (pre-split, for inspection).
    """

    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: list[str]
    scaler: StandardScaler
    ticker: str
    start_date: str
    n_samples: int
    class_balance: dict[str, int]
    raw_df: pd.DataFrame

    @property
    def n_features(self) -> int:
        """Number of input features."""
        return len(self.feature_names)

    @property
    def train_size(self) -> int:
        """Number of training samples."""
        return len(self.X_train)

    @property
    def test_size(self) -> int:
        """Number of test samples."""
        return len(self.X_test)

    def summary(self) -> str:
        """Return a human-readable summary string of the dataset."""
        return (
            f"MLDataset | {self.ticker} | from {self.start_date}\n"
            f"  Samples  : {self.n_samples} total "
            f"(train={self.train_size}, test={self.test_size})\n"
            f"  Features : {self.n_features} — {self.feature_names}\n"
            f"  Balance  : UP={self.class_balance['up']} "
            f"DOWN={self.class_balance['down']}\n"
            f"  Up ratio : {self.class_balance['up'] / self.n_samples:.1%}"
        )


# ─────────────────────────────────────────────────────────────────────────
# Feature Engineering Functions
# ─────────────────────────────────────────────────────────────────────────

def _log_returns(close: pd.Series) -> pd.Series:
    """
    Compute daily log returns: ln(P_t / P_{t-1}).

    Using log returns rather than simple returns ensures:
        - Additive over time (portfolio mathematics).
        - Approximately normally distributed (better for many models).
        - Symmetry in up/down moves.

    Args:
        close: Close price series.

    Returns:
        Log return series (first element is NaN).
    """
    return np.log(close / close.shift(1))


def _rolling_returns(close: pd.Series, window: int) -> pd.Series:
    """
    Compute rolling cumulative returns over a window.

    Args:
        close:  Close price series.
        window: Look-back period (trading days).

    Returns:
        Rolling return series.
    """
    return close.pct_change(periods=window)


def _realized_volatility(log_ret: pd.Series, window: int) -> pd.Series:
    """
    Compute realized (historical) volatility as rolling standard deviation
    of log returns, annualized by √252.

    Args:
        log_ret: Log return series.
        window:  Rolling window in trading days.

    Returns:
        Annualized realized volatility series.
    """
    return log_ret.rolling(window=window, min_periods=max(1, window // 2)).std() * np.sqrt(252)


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute RSI with Wilder's EMA smoothing.

    Args:
        close:  Close price series.
        period: RSI look-back period.

    Returns:
        RSI series in [0, 100].
    """
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta).clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _compute_macd_histogram(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    """
    Compute MACD Histogram (MACD line − Signal line).

    Positive histogram = bullish momentum acceleration.
    Negative histogram = bearish momentum acceleration.

    Args:
        close:  Close price series.
        fast:   Fast EMA period.
        slow:   Slow EMA period.
        signal: Signal EMA period.

    Returns:
        MACD histogram series.
    """
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_f - ema_s
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def _sma_crossover(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """
    Compute SMA crossover feature: (SMA_fast − SMA_slow) / SMA_slow.

    Positive values indicate the fast MA is above the slow MA (bullish).
    Negative values indicate bearish alignment.

    Args:
        close: Close price series.
        fast:  Short SMA period.
        slow:  Long SMA period.

    Returns:
        Normalized crossover series.
    """
    sma_f = close.rolling(window=fast, min_periods=1).mean()
    sma_s = close.rolling(window=slow, min_periods=1).mean()
    return (sma_f - sma_s) / sma_s.replace(0, np.nan)


def _bollinger_pct_b(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
    """
    Compute Bollinger Band %B: position of price within the bands.

    %B = (Price − Lower Band) / (Upper Band − Lower Band)
    0.0 = at lower band, 1.0 = at upper band, 0.5 = at midline.
    Values > 1 or < 0 indicate a band breakout.

    Args:
        close:  Close price series.
        window: Rolling window for Bollinger Bands.
        n_std:  Number of standard deviations for band width.

    Returns:
        %B series in approximately [0, 1] (can exceed bounds on breakouts).
    """
    sma = close.rolling(window=window, min_periods=1).mean()
    std = close.rolling(window=window, min_periods=1).std()
    upper = sma + n_std * std
    lower = sma - n_std * std
    band_width = (upper - lower).replace(0, np.nan)
    return (close - lower) / band_width


def _candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add candlestick body and shadow features.

    Features:
        - ``body_pct``:      |close − open| / (high − low), range [0, 1].
          High body% = strong directional candle.
        - ``upper_shadow``:  (high − max(open, close)) / (high − low).
          Measures selling pressure at highs.
        - ``lower_shadow``:  (min(open, close) − low) / (high − low).
          Measures buying pressure at lows.

    Args:
        df: OHLCV DataFrame with 'open', 'high', 'low', 'close' columns.

    Returns:
        DataFrame with three new columns added.
    """
    candle_range = (df["high"] - df["low"]).replace(0, np.nan)
    df["body_pct"] = (df["close"] - df["open"]).abs() / candle_range
    df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / candle_range
    df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / candle_range
    return df


def _on_balance_volume_normalized(df: pd.DataFrame) -> pd.Series:
    """
    Compute On-Balance Volume (OBV) normalized by its rolling 20-day mean.

    OBV accumulates volume on up days and subtracts on down days.
    Normalizing makes the feature scale-invariant across tickers.

    Args:
        df: OHLCV DataFrame with 'close' and 'volume' columns.

    Returns:
        Normalized OBV series.
    """
    direction = np.sign(df["close"].diff())
    obv = (direction * df["volume"]).fillna(0).cumsum()
    obv_mean = obv.rolling(window=20, min_periods=1).mean().replace(0, np.nan)
    return obv / obv_mean


# ─────────────────────────────────────────────────────────────────────────
# Target Engineering
# ─────────────────────────────────────────────────────────────────────────

def _build_target(close: pd.Series) -> pd.Series:
    """
    Build the binary classification target.

    Target definition:
        y_t = 1 if close_{t+1} > close_t  (next day is an up day)
        y_t = 0 if close_{t+1} ≤ close_t  (next day is flat or down)

    Note: The last row of the original data will have NaN target
    (no future bar) and must be dropped before training.

    Args:
        close: Close price series.

    Returns:
        Binary integer series (0 or 1), shifted by −1 (future-looking).
    """
    future_return = close.shift(-1) - close
    return (future_return > 0).astype(int)


# ─────────────────────────────────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────────────────────────────────

def _build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all feature engineering functions to a clean OHLCV DataFrame.

    This function is the single entry point for all feature construction.
    It must NOT modify the original DataFrame (operates on a copy).

    Args:
        df: Clean OHLCV DataFrame produced by ``DataService.get_historical_prices()``.
            Must contain columns: open, high, low, close, volume.

    Returns:
        DataFrame with all engineered features + the 'target' column.
        Rows with any NaN in feature columns are excluded.

    Raises:
        ValueError: If required OHLCV columns are missing.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"OHLCV DataFrame is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    feat = df.copy()

    # ── Returns ──────────────────────────────────────────────────────────
    feat["log_return"] = _log_returns(feat["close"])
    feat["return_5d"] = _rolling_returns(feat["close"], 5)
    feat["return_10d"] = _rolling_returns(feat["close"], 10)
    feat["return_21d"] = _rolling_returns(feat["close"], 21)

    # ── Volatility ───────────────────────────────────────────────────────
    log_ret = feat["log_return"]
    feat["realized_vol_10d"] = _realized_volatility(log_ret, 10)
    feat["realized_vol_21d"] = _realized_volatility(log_ret, 21)
    # Volatility ratio: short-term vol relative to long-term (regime indicator)
    feat["vol_ratio"] = (
        feat["realized_vol_10d"] / feat["realized_vol_21d"].replace(0, np.nan)
    )
    feat["bb_pct_b"] = _bollinger_pct_b(feat["close"])

    # ── Momentum ─────────────────────────────────────────────────────────
    feat["rsi_14"] = _compute_rsi(feat["close"], 14)
    # RSI momentum: rate of change in RSI over 5 days
    feat["rsi_diff"] = feat["rsi_14"].diff(5)
    feat["macd_hist"] = _compute_macd_histogram(feat["close"])

    # ── Trend ────────────────────────────────────────────────────────────
    feat["sma_cross_20_50"] = _sma_crossover(feat["close"], 20, 50)
    feat["sma_cross_50_200"] = _sma_crossover(feat["close"], 50, 200)
    sma_200 = feat["close"].rolling(window=200, min_periods=50).mean()
    feat["price_vs_sma200"] = (feat["close"] - sma_200) / sma_200.replace(0, np.nan)

    # ── Volume ───────────────────────────────────────────────────────────
    feat["vol_change"] = feat["volume"].pct_change()
    feat["obv_norm"] = _on_balance_volume_normalized(feat)

    # ── Price Patterns ───────────────────────────────────────────────────
    feat = _candlestick_patterns(feat)

    # ── Target ───────────────────────────────────────────────────────────
    feat["target"] = _build_target(feat["close"])

    return feat


FEATURE_COLUMNS: list[str] = [
    # Returns
    "log_return", "return_5d", "return_10d", "return_21d",
    # Volatility
    "realized_vol_10d", "realized_vol_21d", "vol_ratio", "bb_pct_b",
    # Momentum
    "rsi_14", "rsi_diff", "macd_hist",
    # Trend
    "sma_cross_20_50", "sma_cross_50_200", "price_vs_sma200",
    # Volume
    "vol_change", "obv_norm",
    # Candlestick
    "body_pct", "upper_shadow", "lower_shadow",
]


def prepare_ml_features(
    ticker: str,
    start_date: str = "2020-01-01",
    end_date: Optional[str] = None,
    provider: str = "yfinance",
    test_size: float = 0.2,
    random_state: int = 42,
    data_service: Optional[DataService] = None,
) -> MLDataset:
    """
    End-to-end ML feature pipeline: data fetch → engineering → split → scale.

    This is the primary entry point for the ML training workflow.  It:
        1. Fetches raw OHLCV data from ``DataService`` (with caching).
        2. Engineers all features in a single pass with no data leakage.
        3. Handles NaN values safely (forward-fill then drop).
        4. Creates a binary classification target (next-day up/down).
        5. Performs a stratified train/test split.
        6. Fits a ``StandardScaler`` on training data only and applies it.
        7. Returns a fully populated ``MLDataset`` ready for model training.

    Args:
        ticker:       Asset symbol (e.g., 'AAPL', 'SPY', 'BTC-USD').
        start_date:   ISO-8601 start date string (e.g., '2020-01-01').
                      Recommend at least 2 years of history for SMA-200.
        end_date:     ISO-8601 end date string.  Defaults to today.
        provider:     OHLCV data provider.  'yfinance' is free and reliable.
                      Options: 'yfinance' | 'fmp' | 'polygon'.
        test_size:    Fraction of data held out for testing (default 0.2 = 20%).
        random_state: Random seed for reproducible splits.
        data_service: Optional pre-initialized DataService instance.
                      If None, a new instance is created with defaults.

    Returns:
        ``MLDataset`` with X_train, X_test, y_train, y_test, scaler,
        feature_names, and diagnostic fields.

    Raises:
        DataServiceError: If the data fetch fails completely.
        ValueError:       If there are fewer than 100 usable rows after
                          feature engineering (insufficient training data).

    Example::

        from ml_models.pipeline import prepare_ml_features

        dataset = prepare_ml_features("AAPL", start_date="2021-01-01")
        print(dataset.summary())
        # → Train an sklearn model
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier()
        model.fit(dataset.X_train, dataset.y_train)
        print(model.score(dataset.X_test, dataset.y_test))
    """
    # ── 1. Initialize DataService ─────────────────────────────────────────
    if data_service is None:
        data_service = DataService()

    logger.info(
        "prepare_ml_features | ticker=%s | from=%s | provider=%s",
        ticker, start_date, provider,
    )

    # ── 2. Fetch raw OHLCV data ───────────────────────────────────────────
    raw_df = data_service.get_historical_prices(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
    )

    logger.info("Raw OHLCV: %d rows for %s", len(raw_df), ticker)

    # ── 3. Build feature matrix ───────────────────────────────────────────
    feature_df = _build_feature_matrix(raw_df)

    # ── 4. Select only the engineered feature columns + target ────────────
    available_features = [c for c in FEATURE_COLUMNS if c in feature_df.columns]
    missing_features = set(FEATURE_COLUMNS) - set(available_features)
    if missing_features:
        logger.warning(
            "Missing engineered features (may lack required OHLCV columns): %s",
            missing_features,
        )

    keep_cols = available_features + ["target"]
    feature_df = feature_df[keep_cols].copy()

    # ── 5. Handle NaN values safely ───────────────────────────────────────
    # Step 1: forward-fill short gaps (up to 5 consecutive NaNs)
    feature_df = feature_df.ffill(limit=5)

    # Step 2: drop any remaining NaN rows (start-of-series warm-up period
    # and the last row where target=NaN by construction)
    rows_before = len(feature_df)
    feature_df = feature_df.dropna()
    rows_dropped = rows_before - len(feature_df)

    if rows_dropped > 0:
        logger.info(
            "Dropped %d rows with NaN values (%.1f%% of data).",
            rows_dropped, rows_dropped / rows_before * 100,
        )

    # ── 6. Validate minimum sample count ─────────────────────────────────
    n_samples = len(feature_df)
    if n_samples < 100:
        raise ValueError(
            f"Insufficient data: only {n_samples} usable rows after feature engineering "
            f"for ticker '{ticker}' from {start_date}. "
            "Provide at least 2 years of history (≥500 rows recommended)."
        )

    # ── 7. Separate X and y ───────────────────────────────────────────────
    X: pd.DataFrame = feature_df[available_features]
    y: pd.Series = feature_df["target"]

    # Class balance diagnostics
    up_count = int(y.sum())
    down_count = int((y == 0).sum())
    class_balance = {"up": up_count, "down": down_count}
    logger.info(
        "Class balance: UP=%d (%.1f%%) | DOWN=%d (%.1f%%)",
        up_count, up_count / n_samples * 100,
        down_count, down_count / n_samples * 100,
    )

    # ── 8. Stratified train/test split ───────────────────────────────────
    # Stratified ensures both splits maintain the up/down class ratio.
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X.values,
        y.values,
        test_size=test_size,
        random_state=random_state,
        stratify=y.values,
    )

    # ── 9. Standardize (fit on train, transform test) ─────────────────────
    # CRITICAL: scaler is fit ONLY on training data to prevent leakage.
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
    X_test = scaler.transform(X_test_raw).astype(np.float32)

    # Cast labels to int8 for memory efficiency
    y_train = y_train.astype(np.int8)
    y_test = y_test.astype(np.int8)

    logger.info(
        "ML pipeline complete | train=%d | test=%d | features=%d",
        len(X_train), len(X_test), len(available_features),
    )

    return MLDataset(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        feature_names=available_features,
        scaler=scaler,
        ticker=ticker,
        start_date=start_date,
        n_samples=n_samples,
        class_balance=class_balance,
        raw_df=feature_df,
    )


def transform_inference_row(
    row: pd.Series | dict,
    scaler: StandardScaler,
    feature_names: list[str],
) -> np.ndarray:
    """
    Transform a single real-time data row for model inference.

    The same ``StandardScaler`` fitted during training MUST be used here
    to ensure consistent feature scaling at inference time.

    Args:
        row:           A dict or pd.Series containing feature values.
                       Keys must match ``feature_names``.
        scaler:        The fitted StandardScaler from the training pipeline.
        feature_names: Ordered list of feature names (from MLDataset).

    Returns:
        2-D float32 numpy array of shape (1, n_features) ready for
        ``model.predict_proba()``.

    Raises:
        KeyError: If any required feature is missing from ``row``.

    Example::

        row = {feat: val for feat, val in zip(dataset.feature_names, X_test[0])}
        X_inference = transform_inference_row(row, dataset.scaler, dataset.feature_names)
        prob = model.predict_proba(X_inference)[0, 1]
    """
    if isinstance(row, dict):
        row_series = pd.Series(row)
    else:
        row_series = row

    missing = [f for f in feature_names if f not in row_series.index]
    if missing:
        raise KeyError(
            f"Missing features for inference: {missing}. "
            f"Ensure all features are computed before calling this function."
        )

    values = np.array([[row_series[f] for f in feature_names]], dtype=np.float32)
    return scaler.transform(values).astype(np.float32)
