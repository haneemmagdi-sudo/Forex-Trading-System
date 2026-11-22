"""
=============================================================================
quant_core — Pure Mathematical & Statistical Engine for Institutional MAS
=============================================================================
This package contains pure deterministic mathematical algorithms and quantitative
models. LLMs MUST NEVER be used for any computations within this layer.
All indicators and statistical metrics are computed deterministically using
NumPy, Pandas, and SciPy.
"""

from quant_core.orderflow import RealOFIEngine, OFIResult
from quant_core.regime_math import (
    RegimeType,
    VolatilityRegime,
    HurstResult,
    VarianceRatioResult,
    ATRZScoreResult,
    HMMRegimeResult,
    MarketRegimeSnapshot,
    compute_hurst_exponent,
    compute_rolling_hurst,
    compute_variance_ratio,
    compute_atr,
    compute_atr_z_score,
    GaussianHMM,
    InstitutionalRegimeEngine,
)

__all__ = [
    "RealOFIEngine",
    "OFIResult",
    "RegimeType",
    "VolatilityRegime",
    "HurstResult",
    "VarianceRatioResult",
    "ATRZScoreResult",
    "HMMRegimeResult",
    "MarketRegimeSnapshot",
    "compute_hurst_exponent",
    "compute_rolling_hurst",
    "compute_variance_ratio",
    "compute_atr",
    "compute_atr_z_score",
    "GaussianHMM",
    "InstitutionalRegimeEngine",
]
