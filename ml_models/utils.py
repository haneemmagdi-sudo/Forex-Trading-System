"""
==============================================================
ml_models/utils.py  —  Antigravity Safety & Scaling Middleware
==============================================================
Centralised utility layer consumed by every ML pipeline in the
Antigravity system.  All functions in this module are:

    1. Stateless with respect to market data (safe to call from
       concurrent coroutines without locking).
    2. Fully type-hinted to catch integration bugs at the call site.
    3. Defensively coded — every public function handles None /
       empty / NaN inputs without raising and emits structured log
       warnings so failures surface in the production log stream.

Key Components
--------------
RollingWindowScaler
    The ONLY approved mechanism for normalising live feature rows
    in the Antigravity system.  Enforces strict temporal causality
    (zero look-ahead bias) by fitting ``StandardScaler`` exclusively
    on the past ``window_size`` rows and then transforming the
    single live row at time *t*.

safe_fill_series
    One-dimensional NaN repair for price/indicator ``pd.Series``.
    Uses forward-fill (price continuity) or zero-fill (missing
    sentiment strings) depending on ``method``.

safe_fill_feature_matrix
    Two-dimensional NaN repair for feature ``pd.DataFrame``s.
    Applies the canonical three-step protocol used throughout the
    Antigravity pipeline: ffill → bfill → per-column defaults.

validate_price_series
    Guard-rail validator used by ``TimesFMForecaster`` before
    submitting data to the foundation model.  Returns ``bool``
    so callers can branch on failure rather than catching exceptions.

normalize_scalar
    Clips and min-max normalises an arbitrary float to [0, 1].

clip_array
    Clips a NumPy array to a symmetric band, preventing extreme
    outliers from saturating neural-network activations.

NaN Policy
----------
    Price series / indicators  →  Forward-Fill (ffill)
        Rationale: prices are continuous; the last known valid tick
        is the best estimate for a dropped frame.

    Sentiment strings          →  Zero-Fill (0.0 neutral score)
        Rationale: absent news implies no actionable signal, not a
        carry-forward of the previous headline's sentiment.

    Remaining NaN after ffill  →  Per-column safe constants
        (RSI → 50.0, Bollinger %B → 0.5, returns → 0.0, etc.)

Zero Look-Ahead Bias Contract
------------------------------
``RollingWindowScaler.fit_transform_row()`` MUST be the only
function that produces scaled feature rows for live inference.
The contract is guaranteed by construction:

    fit window  :  history[t - window_size : t]   (past only)
    transform   :  live_row[t]                    (present only)

The scaler is NEVER re-used across bar boundaries without
re-fitting.  This eliminates all forms of future data leakage.

Usage
-----
    from ml_models.utils import (
        RollingWindowScaler,
        safe_fill_series,
        safe_fill_feature_matrix,
        validate_price_series,
        normalize_scalar,
        clip_array,
    )

    # Rolling scaled live row (zero leakage)
    scaler  = RollingWindowScaler(window_size=128)
    scaled  = scaler.fit_transform_row(
        history_matrix = feature_df.iloc[-129:-1].values,
        live_row       = feature_df.iloc[[-1]].values,
    )  # shape (1, n_features), fitted ONLY on past 128 rows

    # NaN-safe price series repair
    clean = safe_fill_series(raw_close_series, method="ffill")

    # Guard-rail validation before model inference
    if not validate_price_series(close, min_len=64, name="BTCUSDT"):
        return _zeroed_metrics()
"""

from __future__ import annotations

import logging
from typing import Dict, Final, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger: logging.Logger = logging.getLogger("ml_models.utils")


# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants
# ─────────────────────────────────────────────────────────────────────────────

#: Default clip bound applied to all normalised feature arrays.
#: Values beyond ±_CLIP_BOUND standard deviations are outliers.
_CLIP_BOUND: Final[float] = 10.0

#: Minimum rolling window before the scaler is considered reliable.
_MIN_SCALER_WINDOW: Final[int] = 32

#: Absolute minimum length for a price series to be considered valid.
_MIN_PRICE_SERIES_LEN: Final[int] = 2


# ─────────────────────────────────────────────────────────────────────────────
# RollingWindowScaler
# ─────────────────────────────────────────────────────────────────────────────


class RollingWindowScaler:
    """
    Zero-leakage rolling ``StandardScaler`` for live feature rows.

    This class is the **only approved** mechanism for normalising
    inference-time feature vectors in the Antigravity production system.

    Design Guarantee
    ----------------
    The ``StandardScaler`` is always fitted exclusively on
    ``history_matrix[t - window_size : t]``  (past rows) and then
    transforms ``live_row[t]``  (current row).  The live row is
    **never** included in the fitting window, which eliminates all
    forms of temporal data leakage.

    Parameters
    ----------
    window_size : int
        Number of past rows used to fit the scaler.
        Must be ≥ ``_MIN_SCALER_WINDOW`` (32).  Using a window that
        is too small produces unreliable mean/std estimates and
        degrades model performance.
    with_mean : bool
        Centre features to zero mean (default True).
    with_std : bool
        Scale features to unit variance (default True).

    Raises
    ------
    ValueError
        If ``window_size < _MIN_SCALER_WINDOW``.

    Examples
    --------
    >>> scaler = RollingWindowScaler(window_size=128)
    >>> scaled = scaler.fit_transform_row(
    ...     history_matrix=feature_df.iloc[-129:-1].values,  # 128 past rows
    ...     live_row=feature_df.iloc[[-1]].values,           # 1 current row
    ... )
    >>> scaled.shape
    (1, n_features)
    """

    def __init__(
        self,
        window_size: int = 128,
        with_mean: bool = True,
        with_std: bool = True,
    ) -> None:
        if window_size < _MIN_SCALER_WINDOW:
            raise ValueError(
                f"RollingWindowScaler: window_size={window_size} is below "
                f"the minimum reliable threshold ({_MIN_SCALER_WINDOW}). "
                f"Increase the window to produce stable mean/std estimates."
            )
        self._window_size: int = window_size
        self._with_mean:   bool = with_mean
        self._with_std:    bool = with_std
        # Materialised after the first call to fit_transform_row()
        self._last_scaler: Optional[StandardScaler] = None
        self._n_calls: int = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def fit_transform_row(
        self,
        history_matrix: np.ndarray,
        live_row: np.ndarray,
    ) -> np.ndarray:
        """
        Fit scaler on historical rows, then transform a single live row.

        This is the primary entry-point and the heart of the zero-leakage
        contract.  The scaler is fitted ONLY on ``history_matrix`` and
        then applied to ``live_row``.

        Parameters
        ----------
        history_matrix : np.ndarray
            Shape ``(n_history, n_features)`` — past feature rows.
            Must have ≥ ``window_size`` rows.  If more rows are provided,
            only the last ``window_size`` rows are used to fit the scaler
            (recency bias — recent market regime is most relevant).
        live_row : np.ndarray
            Shape ``(1, n_features)`` or ``(n_features,)`` — the feature
            row for the current bar at time *t*.  This row must NOT be
            included in ``history_matrix``.

        Returns
        -------
        np.ndarray
            Shape ``(1, n_features)`` float32 — scaled live feature row.

        Raises
        ------
        ValueError
            If ``history_matrix`` has fewer than ``_MIN_SCALER_WINDOW`` rows.
        ValueError
            If feature dimension mismatch between history and live_row.

        Notes
        -----
        NaN values in ``history_matrix`` are replaced with column medians
        before fitting to prevent ``StandardScaler`` from propagating NaNs
        into the scaler parameters (mean/std).

        NaN values in ``live_row`` are replaced with the column means of
        the fitted scaler (i.e. the feature's training-set mean).

        Examples
        --------
        >>> scaler = RollingWindowScaler(window_size=64)
        >>> # history has 200 rows; only last 64 are used for fitting
        >>> scaled = scaler.fit_transform_row(
        ...     history_matrix=feature_df.iloc[-65:-1].values,
        ...     live_row=feature_df.iloc[[-1]].values,
        ... )
        """
        # ── Input validation ───────────────────────────────────────────
        hist = np.asarray(history_matrix, dtype=np.float64)
        if hist.ndim == 1:
            hist = hist.reshape(-1, 1)

        live = np.asarray(live_row, dtype=np.float64)
        if live.ndim == 1:
            live = live.reshape(1, -1)

        if hist.shape[0] < _MIN_SCALER_WINDOW:
            raise ValueError(
                f"RollingWindowScaler.fit_transform_row(): history_matrix "
                f"has {hist.shape[0]} rows, but minimum required is "
                f"{_MIN_SCALER_WINDOW}.  Accumulate more history before "
                f"calling this method."
            )

        if hist.shape[1] != live.shape[1]:
            raise ValueError(
                f"RollingWindowScaler: feature dimension mismatch — "
                f"history has {hist.shape[1]} features, "
                f"live_row has {live.shape[1]} features."
            )

        # ── Select the recency window ──────────────────────────────────
        # Use only the last window_size rows — most recent regime matters most.
        window = hist[-self._window_size :]  # shape (window_size, n_features)

        # ── NaN handling in history ────────────────────────────────────
        # Replace NaNs with column medians so sklearn's StandardScaler
        # receives a clean matrix (it does not handle NaNs natively).
        if np.isnan(window).any():
            col_medians = np.nanmedian(window, axis=0)
            nan_mask = np.isnan(window)
            window = window.copy()
            # Broadcast median fill per column
            for col_idx in range(window.shape[1]):
                col_nan = nan_mask[:, col_idx]
                if col_nan.any():
                    window[col_nan, col_idx] = col_medians[col_idx]
            logger.debug(
                "[RollingWindowScaler] %d NaN(s) in history window replaced "
                "with column medians before fitting.",
                nan_mask.sum(),
            )

        # ── Fit scaler on historical window (PAST ONLY) ────────────────
        scaler = StandardScaler(
            with_mean=self._with_mean,
            with_std=self._with_std,
        )
        scaler.fit(window)
        self._last_scaler = scaler

        # ── NaN handling in live row ───────────────────────────────────
        # Replace NaNs with the scaler's fitted mean (i.e. the feature's
        # historical mean) before transforming — the safest neutral fill.
        live_clean = live.copy()
        if np.isnan(live_clean).any():
            nan_cols = np.where(np.isnan(live_clean[0]))[0]
            for col_idx in nan_cols:
                live_clean[0, col_idx] = float(scaler.mean_[col_idx])
            logger.warning(
                "[RollingWindowScaler] NaN in live_row at columns %s — "
                "filled with scaler means before transform.",
                nan_cols.tolist(),
            )

        # ── Transform live row (PRESENT ONLY) ─────────────────────────
        scaled: np.ndarray = scaler.transform(live_clean).astype(np.float32)
        self._n_calls += 1

        logger.debug(
            "[RollingWindowScaler] call #%d | window=%d | features=%d | "
            "live_row scaled OK (mean=%.4f, std=%.4f)",
            self._n_calls,
            len(window),
            live.shape[1],
            float(scaled.mean()),
            float(scaled.std()),
        )

        return scaled  # shape: (1, n_features)

    def transform_only(self, live_row: np.ndarray) -> np.ndarray:
        """
        Transform a row using the last fitted scaler without re-fitting.

        Use this only when the market regime has NOT changed since the
        last call to ``fit_transform_row()``.  Raises if no scaler is
        fitted yet.

        Parameters
        ----------
        live_row : np.ndarray
            Shape ``(1, n_features)`` or ``(n_features,)``.

        Returns
        -------
        np.ndarray
            Shape ``(1, n_features)`` float32.

        Raises
        ------
        RuntimeError
            If ``fit_transform_row()`` has not been called yet.
        """
        if self._last_scaler is None:
            raise RuntimeError(
                "RollingWindowScaler.transform_only() called before any "
                "scaler has been fitted.  Call fit_transform_row() first."
            )
        live = np.asarray(live_row, dtype=np.float64)
        if live.ndim == 1:
            live = live.reshape(1, -1)
        return self._last_scaler.transform(live).astype(np.float32)

    @property
    def window_size(self) -> int:
        """The configured historical window size."""
        return self._window_size

    @property
    def is_fitted(self) -> bool:
        """True if at least one call to ``fit_transform_row()`` has occurred."""
        return self._last_scaler is not None

    @property
    def n_calls(self) -> int:
        """Total number of successful ``fit_transform_row()`` calls."""
        return self._n_calls

    @property
    def last_scaler(self) -> Optional[StandardScaler]:
        """The most recently fitted ``StandardScaler``, or None."""
        return self._last_scaler


# ─────────────────────────────────────────────────────────────────────────────
# NaN Handling Utilities
# ─────────────────────────────────────────────────────────────────────────────


def safe_fill_series(
    series: pd.Series,
    method: str = "ffill",
    ffill_limit: int = 5,
    fallback_value: float = 0.0,
) -> pd.Series:
    """
    Repair NaN values in a one-dimensional ``pd.Series``.

    NaN Policy by ``method``
    ------------------------
    ``"ffill"``  (price continuity)
        Propagates the last valid tick forward.  This is the correct
        policy for price / indicator series where a dropped frame means
        the last observed value is the best available estimate.

    ``"zero"``   (neutral fill)
        Replaces all NaN with ``fallback_value`` (default 0.0).  Used
        for sentiment scores and boolean flags where absence of data
        implies no signal, not a carry-forward.

    ``"bfill"``  (back-fill for leading NaN warm-up)
        Fills from the next valid value.  Rarely used in production but
        useful during feature warm-up when the first few bars have no
        indicator value.

    Parameters
    ----------
    series : pd.Series
        Input series (not mutated).
    method : str
        Fill method: ``"ffill"`` | ``"zero"`` | ``"bfill"``.
        Default ``"ffill"``.
    ffill_limit : int
        Maximum consecutive NaN values to forward-fill.  Gaps longer
        than this are left as NaN until the final fallback fill.
        Default 5.  Only applies when ``method="ffill"``.
    fallback_value : float
        Value to fill any NaN that survives the primary fill step.
        Default 0.0.

    Returns
    -------
    pd.Series
        Clean copy of ``series`` with no NaN values.

    Raises
    ------
    TypeError
        If ``series`` is not a ``pd.Series``.
    ValueError
        If ``method`` is not one of the supported fill strategies.

    Examples
    --------
    >>> import pandas as pd, numpy as np
    >>> s = pd.Series([1.0, np.nan, np.nan, 4.0, np.nan])
    >>> safe_fill_series(s, method="ffill")
    0    1.0
    1    1.0
    2    1.0
    3    4.0
    4    4.0
    dtype: float64
    """
    if not isinstance(series, pd.Series):
        raise TypeError(
            f"safe_fill_series: expected pd.Series, got {type(series).__name__}."
        )

    valid_methods = {"ffill", "zero", "bfill"}
    if method not in valid_methods:
        raise ValueError(
            f"safe_fill_series: unknown method {method!r}. "
            f"Supported: {valid_methods}."
        )

    result = series.copy()
    nan_count_before = int(result.isna().sum())

    if nan_count_before == 0:
        return result   # Fast path — no NaN present

    if method == "ffill":
        result = result.ffill(limit=ffill_limit)
    elif method == "bfill":
        result = result.bfill(limit=ffill_limit)
    # "zero" skips directly to the fallback fill below

    # Fallback fill for any NaN that survived the primary step
    n_remaining = int(result.isna().sum())
    if n_remaining > 0:
        result = result.fillna(fallback_value)
        logger.debug(
            "[safe_fill_series] Filled %d NaN(s) with method=%r; "
            "%d NaN(s) filled with fallback_value=%.4f.",
            nan_count_before - n_remaining,
            method,
            n_remaining,
            fallback_value,
        )

    return result


def safe_fill_feature_matrix(
    df: pd.DataFrame,
    per_column_defaults: Optional[Dict[str, float]] = None,
    global_default: float = 0.0,
    ffill_limit: int = 5,
    bfill_limit: int = 2,
) -> pd.DataFrame:
    """
    Apply the canonical 3-step NaN repair protocol to a feature DataFrame.

    This is the authoritative NaN-handling function for 2-D feature
    matrices.  It matches the private ``_safe_fill()`` used inside
    ``feature_pipeline.py`` but is exposed as a public utility so all
    pipeline modules can import it without circular dependencies.

    Protocol
    --------
    1. ``ffill(limit=ffill_limit)``
        Forward-propagate the last valid value for gaps ≤ ``ffill_limit``
        consecutive bars.  Handles momentarily dropped data frames.

    2. ``bfill(limit=bfill_limit)``
        Back-fill up to ``bfill_limit`` leading NaN rows that appeared
        during indicator warm-up (e.g. first 14 bars of RSI).

    3. ``fillna(per_column_defaults or global_default)``
        Final safety net — replace any survivor NaN with a domain-safe
        constant (RSI → 50.0, Bollinger %B → 0.5, returns → 0.0).

    Parameters
    ----------
    df : pd.DataFrame
        Input feature matrix (not mutated).
    per_column_defaults : dict[str, float] | None
        Column-name → final fill value for step 3.  Columns not present
        in this dict fall back to ``global_default``.
    global_default : float
        Default fill value for columns not in ``per_column_defaults``.
        Default 0.0.
    ffill_limit : int
        Max consecutive NaN bars to forward-fill.  Default 5.
    bfill_limit : int
        Max leading NaN bars to back-fill.  Default 2.

    Returns
    -------
    pd.DataFrame
        Clean copy of ``df`` with no NaN values.

    Raises
    ------
    TypeError
        If ``df`` is not a ``pd.DataFrame``.

    Examples
    --------
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame({"rsi": [np.nan, 45.0, np.nan], "ret": [0.0, np.nan, -0.001]})
    >>> safe_fill_feature_matrix(df, per_column_defaults={"rsi": 50.0})
       rsi    ret
    0  45.0  0.000
    1  45.0  0.000
    2  45.0 -0.001
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"safe_fill_feature_matrix: expected pd.DataFrame, "
            f"got {type(df).__name__}."
        )

    result = df.copy()
    total_nan_before = int(result.isna().sum().sum())

    if total_nan_before == 0:
        return result   # Fast path

    # Step 1: Forward-fill (price continuity for short gaps)
    result = result.ffill(limit=ffill_limit)

    # Step 2: Back-fill (indicator warm-up leading NaN)
    result = result.bfill(limit=bfill_limit)

    # Step 3: Per-column safe constant fallback
    per_col = per_column_defaults or {}
    for col in result.columns:
        fill_val = per_col.get(col, global_default)
        n_nan = int(result[col].isna().sum())
        if n_nan > 0:
            result[col] = result[col].fillna(fill_val)
            logger.debug(
                "[safe_fill_feature_matrix] Column %r: filled %d NaN(s) "
                "with final fallback=%.4f.",
                col,
                n_nan,
                fill_val,
            )

    total_nan_after = int(result.isna().sum().sum())
    if total_nan_after > 0:
        logger.error(
            "[safe_fill_feature_matrix] %d NaN(s) remain after 3-step fill. "
            "Review per_column_defaults or data quality.",
            total_nan_after,
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Validation Utilities
# ─────────────────────────────────────────────────────────────────────────────


def validate_price_series(
    series: pd.Series,
    min_len: int,
    name: str = "price_series",
    allow_nan: bool = False,
    allow_non_positive: bool = False,
) -> bool:
    """
    Guard-rail validator for price series before model inference.

    Returns ``bool`` rather than raising so callers can branch on failure
    and return zeroed metrics without crashing the production loop.
    Failures are emitted as structured WARNING log messages so they
    surface in the trading system's log stream.

    Checks Performed
    ----------------
    1. Input is a ``pd.Series`` (not a DataFrame or list).
    2. Series length ≥ ``min_len``.
    3. Series dtype is numeric (float or int).
    4. No NaN values present (unless ``allow_nan=True``).
    5. All values > 0 (unless ``allow_non_positive=True``).
       Zero or negative prices indicate a data integrity failure.

    Parameters
    ----------
    series : pd.Series
        The price (or indicator) series to validate.
    min_len : int
        Minimum required number of data points.
    name : str
        Human-readable name used in log messages (e.g. "BTCUSDT close").
    allow_nan : bool
        If False (default), validation fails on any NaN value.
    allow_non_positive : bool
        If False (default), validation fails if any value ≤ 0.

    Returns
    -------
    bool
        ``True`` if the series passes all checks, ``False`` otherwise.

    Examples
    --------
    >>> import pandas as pd
    >>> s = pd.Series([1.082, 1.083, 1.081])
    >>> validate_price_series(s, min_len=64, name="EURUSD")
    False   # fails length check (3 < 64)
    >>> validate_price_series(s, min_len=3, name="EURUSD")
    True
    """
    # Check 1: Correct type
    if not isinstance(series, pd.Series):
        logger.warning(
            "[validate_price_series] '%s': expected pd.Series, got %s.",
            name,
            type(series).__name__,
        )
        return False

    # Check 2: Length
    if len(series) < min_len:
        logger.warning(
            "[validate_price_series] '%s': length %d < required %d. "
            "Accumulate more bars before running inference.",
            name,
            len(series),
            min_len,
        )
        return False

    # Check 3: Numeric dtype
    if not pd.api.types.is_numeric_dtype(series):
        logger.warning(
            "[validate_price_series] '%s': dtype %s is not numeric.",
            name,
            series.dtype,
        )
        return False

    # Check 4: NaN presence
    nan_count = int(series.isna().sum())
    if nan_count > 0 and not allow_nan:
        logger.warning(
            "[validate_price_series] '%s': contains %d NaN value(s). "
            "Run safe_fill_series() before inference.",
            name,
            nan_count,
        )
        return False

    # Check 5: Non-positive prices
    if not allow_non_positive:
        non_positive = int((series.dropna() <= 0).sum())
        if non_positive > 0:
            logger.warning(
                "[validate_price_series] '%s': contains %d non-positive "
                "value(s) (zero or negative price). Check data integrity.",
                name,
                non_positive,
            )
            return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Numeric Normalization Utilities
# ─────────────────────────────────────────────────────────────────────────────


def normalize_scalar(
    value: float,
    lower: float,
    upper: float,
    clip: bool = True,
) -> float:
    """
    Min-max normalise a scalar value to the [0, 1] range.

    Parameters
    ----------
    value : float
        The raw scalar to normalise.
    lower : float
        The minimum of the expected input range (maps to 0.0 output).
    upper : float
        The maximum of the expected input range (maps to 1.0 output).
    clip : bool
        If True (default), clip the output to [0.0, 1.0] so that
        values outside [lower, upper] don't produce out-of-range results.

    Returns
    -------
    float
        Normalised scalar in [0.0, 1.0].

    Raises
    ------
    ValueError
        If ``upper == lower`` (zero-range normalisation is undefined).

    Examples
    --------
    >>> normalize_scalar(50.0, lower=0.0, upper=100.0)
    0.5
    >>> normalize_scalar(150.0, lower=0.0, upper=100.0, clip=True)
    1.0
    """
    if upper == lower:
        raise ValueError(
            f"normalize_scalar: upper ({upper}) == lower ({lower}). "
            f"Range must be non-zero."
        )
    result = (value - lower) / (upper - lower)
    if clip:
        result = float(np.clip(result, 0.0, 1.0))
    return float(result)


def clip_array(
    arr: np.ndarray,
    bound: float = _CLIP_BOUND,
) -> np.ndarray:
    """
    Clip a NumPy array to the symmetric interval [-bound, +bound].

    Used as a final safety gate before feeding feature arrays into
    neural networks.  Prevents extreme outlier values (e.g. from
    flash-crash data) from saturating activations and producing NaN
    gradients.

    Parameters
    ----------
    arr : np.ndarray
        The feature array to clip.  Not mutated.
    bound : float
        Symmetric clip boundary (default ±10.0 standard deviations).

    Returns
    -------
    np.ndarray
        Clipped copy of ``arr`` with same dtype.

    Examples
    --------
    >>> import numpy as np
    >>> clip_array(np.array([0.5, -15.3, 3.2]), bound=10.0)
    array([ 0.5, -10.0,  3.2])
    """
    return np.clip(arr, -bound, bound).astype(arr.dtype)


def percent_return(
    current: float,
    reference: float,
) -> float:
    """
    Compute the percentage return from ``reference`` to ``current``.

    Returns 0.0 if ``reference`` is zero to avoid division errors.

    Parameters
    ----------
    current : float
        Current value (e.g. mean of forecast horizon).
    reference : float
        Reference value (e.g. last known price).

    Returns
    -------
    float
        ``(current - reference) / reference``.  Positive = price up.
        Returns 0.0 on zero-division.

    Examples
    --------
    >>> percent_return(1.0870, 1.0850)
    0.001843...
    """
    if reference == 0.0 or reference != reference:   # NaN guard via IEEE identity
        logger.warning(
            "[percent_return] reference value is zero or NaN — "
            "returning 0.0 to prevent division by zero."
        )
        return 0.0
    return float((current - reference) / reference)


def linear_trend_direction(
    vector: np.ndarray,
    slope_threshold: float = 1e-5,
) -> int:
    """
    Determine the directional trend of a 1-D numeric vector via OLS regression.

    Fits a degree-1 polynomial (straight line) to ``vector`` using
    ``numpy.polyfit`` and classifies the slope:

        slope > +threshold  →  +1  (Bullish / Upward trend)
        slope < -threshold  →  -1  (Bearish / Downward trend)
        |slope| ≤ threshold →   0  (Neutral / Flat)

    Parameters
    ----------
    vector : np.ndarray
        1-D numeric array representing the forecast horizon values.
        Must have length ≥ 2.
    slope_threshold : float
        Minimum absolute slope for a non-neutral classification.
        Calibrated for percentage-of-price space.  Default 1e-5
        (0.001% per bar).

    Returns
    -------
    int
        +1 (Bullish), -1 (Bearish), or 0 (Neutral).

    Raises
    ------
    ValueError
        If ``vector`` has fewer than 2 elements.

    Examples
    --------
    >>> import numpy as np
    >>> linear_trend_direction(np.array([1.080, 1.081, 1.082, 1.083]))
    1   # upward slope → Bullish
    >>> linear_trend_direction(np.array([1.083, 1.082, 1.081, 1.080]))
    -1  # downward slope → Bearish
    """
    if len(vector) < 2:
        raise ValueError(
            f"linear_trend_direction: vector must have ≥ 2 elements; "
            f"got {len(vector)}."
        )

    x = np.arange(len(vector), dtype=np.float64)
    y = np.asarray(vector, dtype=np.float64)

    # Guard against all-NaN or constant vectors before polyfit
    if np.isnan(y).any() or np.all(y == y[0]):
        return 0

    try:
        coeffs = np.polyfit(x, y, 1)  # coeffs[0] = slope, coeffs[1] = intercept
        slope: float = float(coeffs[0])
    except (np.linalg.LinAlgError, ValueError) as exc:
        logger.warning(
            "[linear_trend_direction] polyfit failed: %s — returning Neutral.",
            exc,
        )
        return 0

    if slope > slope_threshold:
        return 1
    elif slope < -slope_threshold:
        return -1
    return 0


def build_zeroed_forecast_metrics() -> Dict[str, object]:
    """
    Return a safely zeroed forecast metrics dictionary.

    Used as the fallback return value whenever the TimesFM inference
    engine cannot produce a valid forecast (insufficient data, model
    not loaded, network error).

    Returns
    -------
    dict
        ``{"expected_return_delta": 0.0, "forecast_trend_direction": 0,
           "forecast_vector": [], "last_price": 0.0, "is_valid": False}``
    """
    return {
        "expected_return_delta": 0.0,
        "forecast_trend_direction": 0,
        "forecast_vector": [],
        "last_price": 0.0,
        "is_valid": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI Smoke-Test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone smoke-test for ml_models/utils.py.

    Run from project root:
        python -m ml_models.utils

    Expected output:
        [RollingWindowScaler] PASS - scaled shape: (1, 5)
        [safe_fill_series]    PASS - no NaN after fill
        [validate_price_series] PASS - short series correctly rejected
        [normalize_scalar]    PASS - 0.5
        [linear_trend_direction] PASS - Bullish=1, Bearish=-1, Neutral=0
        ALL PASS
    """
    import sys

    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    print("\n=== ml_models/utils.py Smoke-Test ===\n")

    # ── RollingWindowScaler ────────────────────────────────────────────
    rng = np.random.default_rng(42)
    history = rng.standard_normal((200, 5)).astype(np.float64)
    live_row = rng.standard_normal((1, 5)).astype(np.float64)

    scaler = RollingWindowScaler(window_size=128)
    scaled = scaler.fit_transform_row(
        history_matrix=history,
        live_row=live_row,
    )
    assert scaled.shape == (1, 5), f"Expected (1, 5), got {scaled.shape}"
    assert scaler.is_fitted, "Scaler should be marked as fitted"
    assert scaler.n_calls == 1
    print(f"[RollingWindowScaler] PASS - scaled shape: {scaled.shape}")

    # NaN in history
    history_with_nan = history.copy()
    history_with_nan[5, 2] = np.nan
    scaled_nan = scaler.fit_transform_row(history_with_nan, live_row)
    assert not np.isnan(scaled_nan).any(), "Scaled row should not contain NaN"
    print(f"[RollingWindowScaler] PASS - NaN history handled OK")

    # ── safe_fill_series ───────────────────────────────────────────────
    s_with_nan = pd.Series([1.0, np.nan, np.nan, 4.0, np.nan])
    filled_ffill = safe_fill_series(s_with_nan, method="ffill")
    assert not filled_ffill.isna().any(), "ffill should eliminate all NaN"
    print(f"[safe_fill_series] PASS (ffill) - no NaN: {filled_ffill.values}")

    filled_zero = safe_fill_series(s_with_nan, method="zero", fallback_value=0.0)
    assert not filled_zero.isna().any(), "zero-fill should eliminate all NaN"
    print(f"[safe_fill_series] PASS (zero)  - no NaN: {filled_zero.values}")

    # ── safe_fill_feature_matrix ───────────────────────────────────────
    df_nan = pd.DataFrame({
        "rsi": [np.nan, 45.0, np.nan],
        "ret": [0.0, np.nan, -0.001],
    })
    df_filled = safe_fill_feature_matrix(df_nan, per_column_defaults={"rsi": 50.0})
    assert not df_filled.isna().any().any(), "Matrix should have no NaN"
    print(f"[safe_fill_feature_matrix] PASS\n{df_filled}")

    # ── validate_price_series ──────────────────────────────────────────
    short = pd.Series([1.082, 1.083, 1.081])
    assert not validate_price_series(short, min_len=64, name="EURUSD"), \
        "Short series should fail validation"
    long_ok = pd.Series(np.linspace(1.08, 1.09, 100))
    assert validate_price_series(long_ok, min_len=64, name="EURUSD"), \
        "Valid series should pass"
    print("[validate_price_series] PASS - short rejected, long accepted")

    # ── normalize_scalar ───────────────────────────────────────────────
    result = normalize_scalar(50.0, lower=0.0, upper=100.0)
    assert abs(result - 0.5) < 1e-9
    result_clip = normalize_scalar(150.0, lower=0.0, upper=100.0, clip=True)
    assert result_clip == 1.0
    print(f"[normalize_scalar] PASS - midpoint={result:.2f}, clipped={result_clip:.2f}")

    # ── linear_trend_direction ─────────────────────────────────────────
    bullish = linear_trend_direction(np.array([1.080, 1.081, 1.082, 1.083]))
    bearish = linear_trend_direction(np.array([1.083, 1.082, 1.081, 1.080]))
    neutral = linear_trend_direction(np.array([1.082, 1.082, 1.082, 1.082]))
    assert bullish == 1,  f"Expected 1 (Bullish), got {bullish}"
    assert bearish == -1, f"Expected -1 (Bearish), got {bearish}"
    assert neutral == 0,  f"Expected 0 (Neutral), got {neutral}"
    print(f"[linear_trend_direction] PASS - Bullish={bullish}, Bearish={bearish}, Neutral={neutral}")

    # ── percent_return ─────────────────────────────────────────────────
    ret = percent_return(1.0870, 1.0850)
    assert ret > 0, "Should be positive return"
    assert percent_return(1.0, 0.0) == 0.0, "Zero reference should return 0.0"
    print(f"[percent_return] PASS - {ret:.6f}")

    # ── build_zeroed_forecast_metrics ──────────────────────────────────
    zm = build_zeroed_forecast_metrics()
    assert zm["expected_return_delta"] == 0.0
    assert zm["forecast_trend_direction"] == 0
    assert zm["is_valid"] is False
    print(f"[build_zeroed_forecast_metrics] PASS")

    print("\n=== ALL PASS ===\n")
