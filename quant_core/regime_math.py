"""
=============================================================================
quant_core/regime_math.py — Pure Deterministic Quantitative Regime Engine
=============================================================================
Architectural Authority: .antigravityrules (Section 2, Law 1 & Law 2)
Environment: Antigravity IDE | MetaTrader 5 (MQL5) + Python 3.11+

ZERO LLM CALCULATIONS:
This module contains pure mathematical and statistical algorithms for detecting
and quantifying financial market regimes. All calculations are 100% deterministic,
vectorized with NumPy and Pandas, and statistically rigorous.

Quantitative Models Implemented:
1. Hurst Exponent (H): Rescaled Range (R/S) analysis for persistence vs. mean reversion.
   - 0.45 <= H <= 0.55: CHOPPY_RANDOM_WALK (Mandatory Hard Veto)
   - H > 0.55: TRENDING (Momentum / Breakout valid)
   - H < 0.45: MEAN_REVERTING (Liquidity Sweep Fade valid)
2. Lo-MacKinlay Variance Ratio Test: Heteroskedasticity-robust random walk test.
3. Average True Range (ATR) Z-Score: Statistical volatility shock & compression detection.
   - Z >= 2.0: HIGH_VOL_SHOCK (Mandatory Hard Veto / Circuit Breaker)
   - Z <= -1.0: VOLATILITY_COMPRESSION
4. Gaussian Hidden Markov Model (HMM): 4-State latent regime filter with forward belief
   updating and Viterbi path decoding.
=============================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import norm


class RegimeType(str, Enum):
    """Institutional Market Regime Classifications."""
    CHOPPY_RANDOM_WALK = "CHOPPY_RANDOM_WALK"
    TRENDING = "TRENDING"
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    MEAN_REVERTING = "MEAN_REVERTING"
    HIGH_VOL_SHOCK = "HIGH_VOL_SHOCK"
    VOLATILITY_COMPRESSION = "VOLATILITY_COMPRESSION"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"


class VolatilityRegime(str, Enum):
    """Categorical Volatility Regime Classifications."""
    HIGH_VOL_SHOCK = "HIGH_VOL_SHOCK"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    VOLATILITY_COMPRESSION = "VOLATILITY_COMPRESSION"


@dataclass(frozen=True)
class HurstResult:
    """Output container for Rescaled Range (R/S) Hurst Exponent analysis."""
    hurst: float
    regime: str
    r_squared: float
    is_valid: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Union[float, str, bool]]:
        return {
            "hurst": round(self.hurst, 4),
            "regime": self.regime,
            "r_squared": round(self.r_squared, 4),
            "is_valid": self.is_valid,
            "interpretation": self.interpretation,
        }


@dataclass(frozen=True)
class VarianceRatioResult:
    """Output container for Lo-MacKinlay Variance Ratio Test."""
    vr: float
    z_stat: float
    p_value: float
    k_lag: int
    regime: str
    is_random_walk: bool

    def to_dict(self) -> Dict[str, Union[float, str, bool, int]]:
        return {
            "vr": round(self.vr, 4),
            "z_stat": round(self.z_stat, 4),
            "p_value": round(self.p_value, 4),
            "k_lag": self.k_lag,
            "regime": self.regime,
            "is_random_walk": self.is_random_walk,
        }


@dataclass(frozen=True)
class ATRZScoreResult:
    """Output container for Normalized ATR Z-Score Volatility metrics."""
    atr: float
    atr_mean: float
    atr_std: float
    atr_z_score: float
    regime: str
    is_vol_shock: bool

    def to_dict(self) -> Dict[str, Union[float, str, bool]]:
        return {
            "atr": round(self.atr, 6),
            "atr_mean": round(self.atr_mean, 6),
            "atr_std": round(self.atr_std, 6),
            "atr_z_score": round(self.atr_z_score, 4),
            "regime": self.regime,
            "is_vol_shock": self.is_vol_shock,
        }


@dataclass(frozen=True)
class HMMRegimeResult:
    """Output container for Gaussian Hidden Markov Model filter."""
    state: str
    state_id: int
    probabilities: Dict[str, float]
    entropy: float
    normalized_entropy: float

    def to_dict(self) -> Dict[str, Union[str, int, float, Dict[str, float]]]:
        return {
            "state": self.state,
            "state_id": self.state_id,
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "entropy": round(self.entropy, 4),
            "normalized_entropy": round(self.normalized_entropy, 4),
        }


@dataclass
class MarketRegimeSnapshot:
    """
    Comprehensive institutional regime state passed from quant_core
    to the 4-Agent Adversarial Council (specifically Alpha Regime Gatekeeper).
    """
    symbol: str
    timeframe: str
    primary_regime: str
    hurst: HurstResult
    variance_ratio: VarianceRatioResult
    atr_z: ATRZScoreResult
    hmm: HMMRegimeResult
    regime_alignment_score: float  # A_alpha in [0.0, 1.0]
    veto_triggered: bool           # True if Hard Veto active
    veto_reason: Optional[str]
    allowed_directions: List[str]  # ["BUY"], ["SELL"], ["BUY", "SELL"], or []
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Union[str, float, bool, List[str], Dict]]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "primary_regime": self.primary_regime,
            "hurst": self.hurst.to_dict(),
            "variance_ratio": self.variance_ratio.to_dict(),
            "atr_z": self.atr_z.to_dict(),
            "hmm": self.hmm.to_dict(),
            "regime_alignment_score": round(self.regime_alignment_score, 4),
            "veto_triggered": self.veto_triggered,
            "veto_reason": self.veto_reason,
            "allowed_directions": self.allowed_directions,
            "timestamp_utc": self.timestamp_utc.isoformat(),
        }


# =============================================================================
# 1. HURST EXPONENT VIA RESCALED RANGE (R/S) ANALYSIS
# =============================================================================

def compute_hurst_exponent(
    prices: Union[np.ndarray, pd.Series, List[float]],
    min_subperiod: int = 8,
    max_subperiod: Optional[int] = None,
) -> HurstResult:
    """
    Computes the Hurst Exponent (H) via classical Rescaled Range (R/S) analysis.

    Mathematical Formulation:
        For log returns x_i = ln(P_i / P_{i-1}) over subseries of length n:
        Mean: m_n = (1/n) * sum(x_i)
        Mean-adjusted cumulative deviations: Z_t = sum_{i=1}^t (x_i - m_n)
        Range: R_n = max(Z_1, ..., Z_n) - min(Z_1, ..., Z_n)
        Standard Deviation: S_n = sqrt((1/n) * sum((x_i - m_n)^2))
        Rescaled Range: (R/S)_n = R_n / S_n

        Power law relationship:
        E[(R/S)_n] = c * n^H
        ln(E[(R/S)_n]) = ln(c) + H * ln(n)

    Classification Rules (Constitutional Law 2):
        - 0.45 <= H <= 0.55: CHOPPY_RANDOM_WALK (Hard Veto)
        - H > 0.55: TRENDING (Persistent)
        - H < 0.45: MEAN_REVERTING (Anti-persistent)

    Args:
        prices: Sequence of financial asset prices (minimum 32 bars required).
        min_subperiod: Minimum window length for R/S calculation (default 8).
        max_subperiod: Maximum window length. If None, uses len(returns) // 2.

    Returns:
        HurstResult containing estimated H, regime string, R-squared, and validity.
    """
    arr = np.asarray(prices, dtype=np.float64)
    # Remove NaNs or non-finite values
    arr = arr[np.isfinite(arr)]

    if len(arr) < 32:
        return HurstResult(
            hurst=0.50,
            regime=RegimeType.CHOPPY_RANDOM_WALK.value,
            r_squared=0.0,
            is_valid=False,
            interpretation="Insufficient data bars (minimum 32 required for Hurst R/S). Defaulting to random walk.",
        )

    # Compute logarithmic returns
    with np.errstate(divide="ignore", invalid="ignore"):
        log_prices = np.log(arr)
        returns = np.diff(log_prices)
        returns = returns[np.isfinite(returns)]

    n_total = len(returns)
    if n_total < 30:
        return HurstResult(
            hurst=0.50,
            regime=RegimeType.CHOPPY_RANDOM_WALK.value,
            r_squared=0.0,
            is_valid=False,
            interpretation="Insufficient returns after cleaning. Defaulting to random walk.",
        )

    if max_subperiod is None:
        max_subperiod = max(min_subperiod * 2, n_total // 2)

    max_subperiod = min(max_subperiod, n_total)
    if min_subperiod >= max_subperiod:
        min_subperiod = max(4, max_subperiod // 2)

    # Generate subperiod intervals (powers of 2 / log scale)
    subperiods: List[int] = []
    current = min_subperiod
    while current <= max_subperiod:
        subperiods.append(current)
        current = int(math.ceil(current * 1.414))  # sqrt(2) geometric progression

    # Ensure at least 4 distinct subperiod sizes for regression
    if len(subperiods) < 4:
        subperiods = list(np.unique(np.linspace(min_subperiod, max_subperiod, 6, dtype=int)))

    rs_values: List[float] = []
    valid_subperiods: List[int] = []

    for n in subperiods:
        k_blocks = n_total // n
        if k_blocks < 1:
            continue

        rs_blocks: List[float] = []
        for i in range(k_blocks):
            sub_series = returns[i * n : (i + 1) * n]
            sub_mean = np.mean(sub_series)
            deviations = sub_series - sub_mean
            cum_dev = np.cumsum(deviations)
            r = np.ptp(cum_dev)  # max(cum_dev) - min(cum_dev)
            s = np.std(sub_series, ddof=1) if len(sub_series) > 1 else np.std(sub_series)

            if s > 1e-12 and r > 1e-12:
                rs_blocks.append(r / s)

        if rs_blocks:
            rs_values.append(float(np.mean(rs_blocks)))
            valid_subperiods.append(n)

    if len(valid_subperiods) < 3:
        return HurstResult(
            hurst=0.50,
            regime=RegimeType.CHOPPY_RANDOM_WALK.value,
            r_squared=0.0,
            is_valid=False,
            interpretation="Could not compute sufficient valid R/S blocks. Flat prices or near-zero variance.",
        )

    # Ordinary Least Squares regression: ln(R/S) vs ln(n)
    log_n = np.log(np.array(valid_subperiods, dtype=np.float64))
    log_rs = np.log(np.array(rs_values, dtype=np.float64))

    poly, residuals, _, _, _ = np.polyfit(log_n, log_rs, 1, full=True)
    hurst_raw = float(poly[0])

    # Compute coefficient of determination R^2
    y_pred = poly[0] * log_n + poly[1]
    ss_tot = np.sum((log_rs - np.mean(log_rs)) ** 2)
    ss_res = np.sum((log_rs - y_pred) ** 2)
    r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-12 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))

    # Bound H within institutional theoretical range [0.0, 1.0]
    hurst = float(np.clip(hurst_raw, 0.01, 0.99))

    # Strict Law 2 classification
    if 0.45 <= hurst <= 0.55:
        regime = RegimeType.CHOPPY_RANDOM_WALK.value
        interpretation = (
            f"Choppy Random Walk detected (H={hurst:.4f} in [0.45, 0.55]). "
            "Market lacks directional memory or mean-reverting predictability. HARD VETO ACTIVE."
        )
    elif hurst > 0.55:
        regime = RegimeType.TRENDING.value
        interpretation = (
            f"Persistent Trending regime detected (H={hurst:.4f} > 0.55). "
            "Positive autocorrelation present. Trend-following and breakout setups permitted."
        )
    else:  # hurst < 0.45
        regime = RegimeType.MEAN_REVERTING.value
        interpretation = (
            f"Mean-Reverting regime detected (H={hurst:.4f} < 0.45). "
            "Negative autocorrelation present. Liquidity sweep fades and range boundaries permitted."
        )

    return HurstResult(
        hurst=hurst,
        regime=regime,
        r_squared=r_squared,
        is_valid=True,
        interpretation=interpretation,
    )


def compute_rolling_hurst(
    series: pd.Series,
    window: int = 100,
    min_subperiod: int = 8,
) -> pd.Series:
    """
    Computes a rolling Hurst exponent over a pandas Series of prices.

    Args:
        series: Pandas Series of historical prices.
        window: Rolling window size (e.g. 100 bars).
        min_subperiod: Minimum subperiod for R/S analysis.

    Returns:
        Pandas Series of rolling Hurst exponents (NaN for initial warm-up period).
    """
    result = pd.Series(index=series.index, dtype=np.float64)
    values = series.to_numpy(dtype=np.float64)

    for i in range(window, len(values) + 1):
        window_prices = values[i - window : i]
        h_res = compute_hurst_exponent(window_prices, min_subperiod=min_subperiod)
        result.iloc[i - 1] = h_res.hurst

    return result


# =============================================================================
# 2. LO-MACKINLAY VARIANCE RATIO TEST (HETEROSKEDASTICITY-ROBUST)
# =============================================================================

def compute_variance_ratio(
    prices: Union[np.ndarray, pd.Series, List[float]],
    k: int = 5,
) -> VarianceRatioResult:
    """
    Implements the Lo & MacKinlay (1988) Variance Ratio Test with heteroskedasticity-
    consistent asymptotic standard errors (Z2 statistic).

    Mathematical Formulation:
        Let p_t = ln(P_t).
        mu_hat = (1/T) * (p_T - p_0)
        sigma_a^2 = (1 / (T - 1)) * sum_{t=1}^T (p_t - p_{t-1} - mu_hat)^2
        m = k * (T - k + 1) * (1 - k/T)
        sigma_c^2(k) = (1/m) * sum_{t=k}^T (p_t - p_{t-k} - k*mu_hat)^2
        VR(k) = sigma_c^2(k) / sigma_a^2

        Under heteroskedasticity:
        phi*(k) = sum_{j=1}^{k-1} [ (2*(k - j) / k) ]^2 * delta_j
        where delta_j = { sum_{t=j+1}^T (r_t - mu_hat)^2 * (r_{t-j} - mu_hat)^2 } /
                        { [ sum_{t=1}^T (r_t - mu_hat)^2 ]^2 }
        Z2 = (VR(k) - 1) / sqrt(phi*(k)) ~ N(0, 1)

    Interpretation:
        - VR(k) ~ 1.0, |Z2| < 1.96: Null of Random Walk cannot be rejected (p > 0.05).
        - VR(k) > 1.0, Z2 > +1.96: Statistically significant trending / momentum (p < 0.05).
        - VR(k) < 1.0, Z2 < -1.96: Statistically significant mean-reversion (p < 0.05).

    Args:
        prices: Asset price series (minimum 40 bars required).
        k: Holding period / lag factor (standard values: 2, 5, 10).

    Returns:
        VarianceRatioResult containing VR, Z-statistic, p-value, and classification.
    """
    arr = np.asarray(prices, dtype=np.float64)
    arr = arr[np.isfinite(arr)]

    if len(arr) < 30 or k < 2 or k >= len(arr) // 2:
        return VarianceRatioResult(
            vr=1.0,
            z_stat=0.0,
            p_value=1.0,
            k_lag=k,
            regime=RegimeType.CHOPPY_RANDOM_WALK.value,
            is_random_walk=True,
        )

    log_p = np.log(arr)
    t_len = len(log_p) - 1  # Total 1-period increments
    p_diff = np.diff(log_p)

    mu_hat = (log_p[-1] - log_p[0]) / t_len
    centered_diff = p_diff - mu_hat

    # 1-period variance estimator (unbiased)
    sigma_a_sq = float(np.sum(centered_diff ** 2) / (t_len - 1)) if t_len > 1 else 1e-8

    if sigma_a_sq <= 1e-14:
        return VarianceRatioResult(
            vr=1.0,
            z_stat=0.0,
            p_value=1.0,
            k_lag=k,
            regime=RegimeType.CHOPPY_RANDOM_WALK.value,
            is_random_walk=True,
        )

    # Multi-period overlapping increments
    k_diff = log_p[k:] - log_p[:-k]
    centered_k_diff = k_diff - (k * mu_hat)
    m = k * (t_len - k + 1) * (1.0 - (k / t_len))
    sigma_c_sq = float(np.sum(centered_k_diff ** 2) / m) if m > 0 else sigma_a_sq

    vr = float(sigma_c_sq / sigma_a_sq)

    # Heteroskedasticity-consistent variance estimation phi*(k)
    denom_delta = (np.sum(centered_diff ** 2)) ** 2
    phi_star = 0.0

    if denom_delta > 1e-16:
        for j in range(1, k):
            weight = (2.0 * (k - j) / k) ** 2
            num_delta = np.sum((centered_diff[j:] ** 2) * (centered_diff[:-j] ** 2))
            delta_j = float(num_delta / denom_delta)
            phi_star += weight * delta_j

    phi_star = max(phi_star, 1e-10)
    z_stat = float((vr - 1.0) / math.sqrt(phi_star))

    # Two-sided p-value from standard normal
    p_value = float(2.0 * (1.0 - norm.cdf(abs(z_stat))))

    # Regime identification
    if p_value > 0.05:
        regime = RegimeType.CHOPPY_RANDOM_WALK.value
        is_rw = True
    elif z_stat > 1.96:
        regime = RegimeType.TRENDING.value
        is_rw = False
    else:  # z_stat < -1.96
        regime = RegimeType.MEAN_REVERTING.value
        is_rw = False

    return VarianceRatioResult(
        vr=vr,
        z_stat=z_stat,
        p_value=p_value,
        k_lag=k,
        regime=regime,
        is_random_walk=is_rw,
    )


# =============================================================================
# 3. AVERAGE TRUE RANGE (ATR) & VOLATILITY Z-SCORE ENGINE
# =============================================================================

def compute_atr(
    high: Union[np.ndarray, pd.Series],
    low: Union[np.ndarray, pd.Series],
    close: Union[np.ndarray, pd.Series],
    period: int = 14,
) -> np.ndarray:
    """
    Computes Average True Range (ATR) via Wilder's Smoothing / RMA.

    Args:
        high: High prices sequence.
        low: Low prices sequence.
        close: Close prices sequence.
        period: Smoothing lookback period (default 14).

    Returns:
        NumPy array of ATR values with matching length.
    """
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)

    n = len(c)
    if n < 2:
        return np.zeros(n, dtype=np.float64)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = h[0] - l[0]

    prev_c = c[:-1]
    hl = h[1:] - l[1:]
    h_pc = np.abs(h[1:] - prev_c)
    l_pc = np.abs(l[1:] - prev_c)

    tr[1:] = np.maximum(hl, np.maximum(h_pc, l_pc))

    # Wilder's Smoothing (alpha = 1 / period)
    atr = np.zeros(n, dtype=np.float64)
    if n <= period:
        atr[:] = np.mean(tr)
        return atr

    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period

    for i in range(period, n):
        atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i - 1]

    # Fill warmup initial window
    atr[: period - 1] = atr[period - 1]
    return atr


def compute_atr_z_score(
    high: Union[np.ndarray, pd.Series],
    low: Union[np.ndarray, pd.Series],
    close: Union[np.ndarray, pd.Series],
    atr_period: int = 14,
    lookback_period: int = 100,
    shock_threshold: float = 2.0,
    compression_threshold: float = -1.0,
) -> ATRZScoreResult:
    """
    Computes statistical Z-Score of the current ATR relative to its rolling distribution.

    Mathematical Formulation:
        Z_{ATR} = (ATR_t - mu_{ATR, lookback}) / sigma_{ATR, lookback}

    Constitutional Rules:
        - Z >= 2.0: HIGH_VOL_SHOCK (Triggers short-circuit / Hard Veto per Law 3)
        - Z <= -1.0: VOLATILITY_COMPRESSION (Potential energy building for breakout)
        - -1.0 < Z < 2.0: NORMAL_VOLATILITY

    Args:
        high: High prices.
        low: Low prices.
        close: Close prices.
        atr_period: ATR smoothing period.
        lookback_period: Rolling distribution window.
        shock_threshold: Z-Score threshold for volatility shock.
        compression_threshold: Z-Score threshold for volatility compression.

    Returns:
        ATRZScoreResult container.
    """
    atr_series = compute_atr(high, low, close, period=atr_period)
    n = len(atr_series)

    if n < lookback_period:
        sample = atr_series
    else:
        sample = atr_series[-lookback_period:]

    current_atr = float(atr_series[-1]) if n > 0 else 0.0
    atr_mean = float(np.mean(sample)) if len(sample) > 0 else current_atr
    atr_std = float(np.std(sample, ddof=1)) if len(sample) > 1 else 1e-6

    atr_std = max(atr_std, 1e-8)
    atr_z_score = float((current_atr - atr_mean) / atr_std)

    if atr_z_score >= shock_threshold:
        regime = VolatilityRegime.HIGH_VOL_SHOCK.value
        is_shock = True
    elif atr_z_score <= compression_threshold:
        regime = VolatilityRegime.VOLATILITY_COMPRESSION.value
        is_shock = False
    else:
        regime = VolatilityRegime.NORMAL_VOLATILITY.value
        is_shock = False

    return ATRZScoreResult(
        atr=current_atr,
        atr_mean=atr_mean,
        atr_std=atr_std,
        atr_z_score=atr_z_score,
        regime=regime,
        is_vol_shock=is_shock,
    )


# =============================================================================
# 4. GAUSSIAN HIDDEN MARKOV MODEL (HMM) REGIME FILTER
# =============================================================================

class GaussianHMM:
    """
    Pure NumPy 4-State Gaussian Hidden Markov Model for financial regime estimation.
    Zero external C-library dependency.

    Hidden States:
        State 0: TRENDING_BULLISH  (Positive drift, standard variance)
        State 1: TRENDING_BEARISH  (Negative drift, standard variance)
        State 2: MEAN_REVERTING    (Zero drift, low variance)
        State 3: HIGH_VOL_SHOCK    (Zero drift, high variance)
    """

    STATE_NAMES = [
        RegimeType.TRENDING_BULLISH.value,
        RegimeType.TRENDING_BEARISH.value,
        RegimeType.MEAN_REVERTING.value,
        RegimeType.HIGH_VOL_SHOCK.value,
    ]

    def __init__(self, num_states: int = 4):
        self.num_states = num_states

        # Stationary prior initial state distribution
        self.pi = np.array([0.25, 0.25, 0.35, 0.15], dtype=np.float64)

        # Transition Probability Matrix A[i, j] = P(S_t = j | S_{t-1} = i)
        # Diagonal persistence reflects institutional regime inertia (regimes stay stable)
        self.A = np.array(
            [
                [0.82, 0.03, 0.10, 0.05],  # BULLISH -> persistence 82%
                [0.03, 0.82, 0.10, 0.05],  # BEARISH -> persistence 82%
                [0.07, 0.07, 0.80, 0.06],  # MEAN_REVERTING -> persistence 80%
                [0.15, 0.15, 0.20, 0.50],  # VOL_SHOCK -> transient 50%
            ],
            dtype=np.float64,
        )

        # Emission Parameters for [log_return, volatility_ratio]:
        # Means: mu[state, feature]
        self.means = np.array(
            [
                [+0.0004, 1.05],  # BULLISH: positive return, normal/elevated vol
                [-0.0004, 1.05],  # BEARISH: negative return, normal/elevated vol
                [0.0000, 0.75],   # MEAN_REVERTING: zero return, subdued vol
                [0.0000, 2.20],   # VOL_SHOCK: neutral return, severe vol
            ],
            dtype=np.float64,
        )

        # Variances: var[state, feature]
        self.vars = np.array(
            [
                [0.00008, 0.15],  # BULLISH
                [0.00008, 0.15],  # BEARISH
                [0.00003, 0.08],  # MEAN_REVERTING
                [0.00035, 0.60],  # VOL_SHOCK
            ],
            dtype=np.float64,
        )

    def _gaussian_emission_prob(self, observation: np.ndarray, state: int) -> float:
        """
        Computes multivariate independent Gaussian emission probability density:
        f(x | S_k) = prod_{d} (1 / sqrt(2*pi*sigma_d^2)) * exp(-0.5 * (x_d - mu_d)^2 / sigma_d^2)
        """
        prob = 1.0
        for d in range(len(observation)):
            mu = self.means[state, d]
            var = max(self.vars[state, d], 1e-8)
            diff = observation[d] - mu
            dens = (1.0 / math.sqrt(2.0 * math.pi * var)) * math.exp(-0.5 * (diff ** 2) / var)
            prob *= max(dens, 1e-12)
        return prob

    def forward_belief_update(
        self,
        observation: np.ndarray,
        prev_belief: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Performs a Bayesian recursive forward belief step:
        P(S_t = j | O_{1:t}) proportional to P(O_t | S_t = j) * sum_i P(S_{t-1} = i | O_{1:t-1}) * A[i, j]
        """
        if prev_belief is None or len(prev_belief) != self.num_states:
            prior = self.pi
        else:
            # Propagate prior through Markov transition matrix
            prior = np.dot(prev_belief, self.A)

        # Compute emission likelihoods
        likelihoods = np.zeros(self.num_states, dtype=np.float64)
        for s in range(self.num_states):
            likelihoods[s] = self._gaussian_emission_prob(observation, s)

        # Posterior = likelihood * prior
        unnormalized = likelihoods * prior
        total = np.sum(unnormalized)

        if total > 1e-16:
            posterior = unnormalized / total
        else:
            posterior = prior

        return posterior

    def predict_sequence_probabilities(
        self,
        observations: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes forward state probabilities across an entire sequence of observations.

        Args:
            observations: 2D array of shape (T, num_features).

        Returns:
            Tuple of:
            - Final posterior state probability distribution (num_states,)
            - Entire sequence of belief states (T, num_states)
        """
        t_steps = len(observations)
        if t_steps == 0:
            return self.pi.copy(), np.empty((0, self.num_states))

        beliefs = np.zeros((t_steps, self.num_states), dtype=np.float64)
        current_belief = self.pi.copy()

        for t in range(t_steps):
            current_belief = self.forward_belief_update(observations[t], current_belief)
            beliefs[t] = current_belief

        return current_belief, beliefs

    def viterbi(self, observations: np.ndarray) -> np.ndarray:
        """
        Decodes the globally optimal sequence of hidden states using the Viterbi algorithm.

        Args:
            observations: 2D array of shape (T, num_features).

        Returns:
            1D array of optimal state IDs [0..3].
        """
        t_len = len(observations)
        if t_len == 0:
            return np.array([], dtype=int)

        log_A = np.log(np.maximum(self.A, 1e-12))
        log_pi = np.log(np.maximum(self.pi, 1e-12))

        # Trellis matrices
        viterbi_matrix = np.zeros((t_len, self.num_states), dtype=np.float64)
        backpointers = np.zeros((t_len, self.num_states), dtype=int)

        # t = 0
        for s in range(self.num_states):
            log_emit = math.log(max(self._gaussian_emission_prob(observations[0], s), 1e-12))
            viterbi_matrix[0, s] = log_pi[s] + log_emit

        # Dynamic programming forward pass
        for t in range(1, t_len):
            for s in range(self.num_states):
                log_emit = math.log(max(self._gaussian_emission_prob(observations[t], s), 1e-12))
                trans_probs = viterbi_matrix[t - 1, :] + log_A[:, s]
                best_prev = int(np.argmax(trans_probs))
                viterbi_matrix[t, s] = trans_probs[best_prev] + log_emit
                backpointers[t, s] = best_prev

        # Backtrack optimal path
        best_path = np.zeros(t_len, dtype=int)
        best_path[-1] = int(np.argmax(viterbi_matrix[-1, :]))

        for t in range(t_len - 2, -1, -1):
            best_path[t] = backpointers[t + 1, best_path[t + 1]]

        return best_path

    @staticmethod
    def compute_entropy(probs: np.ndarray) -> Tuple[float, float]:
        """
        Computes Shannon entropy H = -sum(p_i * ln(p_i)) and normalized entropy H / ln(K).
        """
        p = np.clip(probs, 1e-12, 1.0)
        p = p / np.sum(p)
        raw_entropy = float(-np.sum(p * np.log(p)))
        max_entropy = math.log(len(probs))
        norm_entropy = float(raw_entropy / max_entropy) if max_entropy > 0 else 0.0
        return raw_entropy, norm_entropy


# =============================================================================
# 5. INSTITUTIONAL REGIME ENGINE (COORDINATOR & SYNTHESIS)
# =============================================================================

class InstitutionalRegimeEngine:
    """
    High-level quantitative regime orchestrator.
    Combines Hurst Exponent, Variance Ratio, ATR Z-Score, and Gaussian HMM
    into a unified deterministic assessment for Agent Alpha (Regime Gatekeeper).
    """

    def __init__(
        self,
        hurst_min_subperiod: int = 8,
        vr_lag: int = 5,
        atr_period: int = 14,
        atr_lookback: int = 100,
        vol_shock_threshold: float = 2.0,
    ):
        self.hurst_min_subperiod = hurst_min_subperiod
        self.vr_lag = vr_lag
        self.atr_period = atr_period
        self.atr_lookback = atr_lookback
        self.vol_shock_threshold = vol_shock_threshold
        self.hmm = GaussianHMM(num_states=4)

    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        timeframe: str = "H1",
    ) -> MarketRegimeSnapshot:
        """
        Executes complete quantitative regime analysis across OHLCV bars.

        Args:
            df: DataFrame containing at least 'open', 'high', 'low', 'close' columns (case-insensitive).
            symbol: Financial instrument symbol (e.g. 'EURUSD').
            timeframe: Data resolution (e.g. 'H1').

        Returns:
            MarketRegimeSnapshot containing full metrics, alignment score, and veto state.
        """
        # Normalize column names to lowercase
        cols = {str(c).lower(): c for c in df.columns}
        for req in ["high", "low", "close"]:
            if req not in cols:
                raise ValueError(f"Input DataFrame missing required column '{req}'. Present: {list(df.columns)}")

        highs = df[cols["high"]].to_numpy(dtype=np.float64)
        lows = df[cols["low"]].to_numpy(dtype=np.float64)
        closes = df[cols["close"]].to_numpy(dtype=np.float64)

        # 1. Compute Hurst Exponent
        hurst_res = compute_hurst_exponent(
            closes,
            min_subperiod=self.hurst_min_subperiod,
        )

        # 2. Compute Variance Ratio
        vr_res = compute_variance_ratio(closes, k=self.vr_lag)

        # 3. Compute ATR Z-Score
        atr_z_res = compute_atr_z_score(
            highs,
            lows,
            closes,
            atr_period=self.atr_period,
            lookback_period=self.atr_lookback,
            shock_threshold=self.vol_shock_threshold,
        )

        # 4. Prepare HMM Observations: [log_return, volatility_ratio]
        atr_series = compute_atr(highs, lows, closes, period=self.atr_period)
        atr_mean = np.mean(atr_series[-self.atr_lookback:]) if len(atr_series) >= self.atr_lookback else np.mean(atr_series)
        atr_mean = max(atr_mean, 1e-6)

        vol_ratios = atr_series / atr_mean

        log_closes = np.log(np.maximum(closes, 1e-12))
        log_returns = np.diff(log_closes, prepend=log_closes[0])

        obs_matrix = np.column_stack([log_returns, vol_ratios])

        # Feed last 50 bars to HMM forward belief filter
        recent_obs = obs_matrix[-min(50, len(obs_matrix)) :]
        final_probs, _ = self.hmm.predict_sequence_probabilities(recent_obs)

        best_state_id = int(np.argmax(final_probs))
        best_state_name = GaussianHMM.STATE_NAMES[best_state_id]
        raw_ent, norm_ent = GaussianHMM.compute_entropy(final_probs)

        hmm_dict = {
            GaussianHMM.STATE_NAMES[i]: float(final_probs[i]) for i in range(len(final_probs))
        }

        hmm_res = HMMRegimeResult(
            state=best_state_name,
            state_id=best_state_id,
            probabilities=hmm_dict,
            entropy=raw_ent,
            normalized_entropy=norm_ent,
        )

        # 5. Synthesize Primary Regime & Enforce Constitutional Laws
        veto_triggered = False
        veto_reasons: List[str] = []
        allowed_directions: List[str] = []

        # Law 2: Hurst Hard Veto on Choppy Random Walk
        if hurst_res.regime == RegimeType.CHOPPY_RANDOM_WALK.value:
            veto_triggered = True
            veto_reasons.append(
                f"HURST_VETO: Choppy Random Walk (H={hurst_res.hurst:.4f} in [0.45, 0.55])."
            )

        # Law 3: High Volatility Shock Hard Veto
        if atr_z_res.is_vol_shock:
            veto_triggered = True
            veto_reasons.append(
                f"VOL_SHOCK_VETO: Extreme ATR Z-Score ({atr_z_res.atr_z_score:.2f} >= {self.vol_shock_threshold})."
            )

        # Determine Primary Regime
        if atr_z_res.is_vol_shock:
            primary_regime = RegimeType.HIGH_VOL_SHOCK.value
        elif hurst_res.regime == RegimeType.CHOPPY_RANDOM_WALK.value:
            primary_regime = RegimeType.CHOPPY_RANDOM_WALK.value
        elif hurst_res.regime == RegimeType.TRENDING.value:
            if best_state_id == 0 or (best_state_id != 1 and log_returns[-5:].mean() > 0):
                primary_regime = RegimeType.TRENDING_BULLISH.value
            else:
                primary_regime = RegimeType.TRENDING_BEARISH.value
        else:  # Mean reverting
            primary_regime = RegimeType.MEAN_REVERTING.value

        # Set Allowed Directions if trade permitted
        if not veto_triggered:
            if primary_regime == RegimeType.TRENDING_BULLISH.value:
                allowed_directions = ["BUY"]
            elif primary_regime == RegimeType.TRENDING_BEARISH.value:
                allowed_directions = ["SELL"]
            elif primary_regime == RegimeType.MEAN_REVERTING.value:
                # Fading extremes allowed in both directions
                allowed_directions = ["BUY", "SELL"]
        else:
            allowed_directions = []

        # 6. Calculate Regime Alignment Score (A_alpha in [0.0, 1.0])
        # Used directly in Consensus Score: S_final = (C_beta * A_alpha) - P_gamma
        if veto_triggered:
            alignment_score = 0.0
        else:
            # Component 1: Hurst conviction distance from 0.50 (random walk)
            hurst_conviction = min(1.0, abs(hurst_res.hurst - 0.50) / 0.25)

            # Component 2: HMM certainty (inverse of normalized entropy)
            hmm_certainty = max(0.0, 1.0 - norm_ent)

            # Component 3: HMM dominant state probability
            hmm_max_prob = float(np.max(final_probs))

            # Component 4: Variance Ratio significance support
            vr_support = 1.0 - min(1.0, vr_res.p_value)

            # Weighted harmonic synthesis
            alignment_score = (
                0.35 * hurst_conviction
                + 0.30 * hmm_max_prob
                + 0.20 * hmm_certainty
                + 0.15 * vr_support
            )
            alignment_score = float(np.clip(alignment_score, 0.0, 1.0))

        return MarketRegimeSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            primary_regime=primary_regime,
            hurst=hurst_res,
            variance_ratio=vr_res,
            atr_z=atr_z_res,
            hmm=hmm_res,
            regime_alignment_score=alignment_score,
            veto_triggered=veto_triggered,
            veto_reason=" | ".join(veto_reasons) if veto_reasons else None,
            allowed_directions=allowed_directions,
        )
