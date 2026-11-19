"""
==============================================================================
agents/market_regime_hmm.py — Institutional Market Regime Agent (HMM)
==============================================================================
Module  : Market Regime Classification & Macro Veto System
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Replaces static rule thresholds with a mathematical Hidden Markov Model (HMM)
and temporal state estimator to categorize market environment into:
  1. TRENDING_BULLISH     - Strong directional upward flow
  2. TRENDING_BEARISH     - Strong directional downward flow
  3. MEAN_REVERTING       - Cyclical range-bound oscillating regime
  4. HIGH_VOL_COMPRESSED  - Volatility compression / high pre-expansion pressure

Macro Regime Veto:
------------------
Acts as the first-line hierarchical gatekeeper. If an entry signal directly
contradicts the macro market regime or occurs during dangerous compression,
the MarketRegimeAgent triggers an absolute VETO, halting execution.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("institutional_mas.regime_hmm")


class MarketRegimeState(str, Enum):
    """Institutional Market Regime Classifications."""
    TRENDING_BULLISH    = "TRENDING_BULLISH"
    TRENDING_BEARISH    = "TRENDING_BEARISH"
    MEAN_REVERTING      = "MEAN_REVERTING"
    HIGH_VOL_COMPRESSED = "HIGH_VOL_COMPRESSED"
    UNCERTAIN           = "UNCERTAIN"


@dataclass
class RegimeClassificationResult:
    """Detailed output from the Regime Agent."""
    symbol: str
    state: MarketRegimeState
    state_probabilities: Dict[str, float]
    transition_entropy: float
    volatility_compression_ratio: float
    trend_strength: float
    trade_allowed: bool
    allowed_directions: List[str]  # e.g. ["BUY"], ["SELL"], ["BUY", "SELL"], []
    veto_reason: Optional[str] = None


class GaussianHMMRegimeEstimator:
    """
    Lightweight, high-speed mathematical Hidden Markov Model estimator
    designed for zero-dependency runtime environments (uses pure math/numpy).
    Infers latent state from observation vector [normalized_return, volatility_ratio, directional_drift].
    """

    def __init__(self, num_states: int = 4):
        self.num_states = num_states
        # Prior state transition matrix [From_State, To_State]
        # Diagonal persistence reflects regime inertia (regimes tend to persist)
        self.transition_matrix = [
            [0.82, 0.03, 0.10, 0.05],  # BULLISH
            [0.03, 0.82, 0.10, 0.05],  # BEARISH
            [0.08, 0.08, 0.78, 0.06],  # MEAN_REVERTING
            [0.15, 0.15, 0.10, 0.60],  # COMPRESSED (lower persistence, breaks out)
        ]
        # State emission parameters for Forex log returns
        self.state_emissions = {
            MarketRegimeState.TRENDING_BULLISH:    {"ret_mu": +0.0003, "ret_var": 0.00005, "vol_mu": 1.1},
            MarketRegimeState.TRENDING_BEARISH:    {"ret_mu": -0.0003, "ret_var": 0.00005, "vol_mu": 1.1},
            MarketRegimeState.MEAN_REVERTING:      {"ret_mu":  0.0000, "ret_var": 0.00002, "vol_mu": 0.7},
            MarketRegimeState.HIGH_VOL_COMPRESSED: {"ret_mu":  0.0000, "ret_var": 0.00010, "vol_mu": 1.8},
        }

    def _gaussian_pdf(self, x: float, mean: float, var: float) -> float:
        """Compute 1D Gaussian probability density."""
        var = max(var, 1e-8)
        denom = math.sqrt(2.0 * math.pi * var)
        num = math.exp(-0.5 * ((x - mean) ** 2) / var)
        return max(num / denom, 1e-12)

    def estimate_state_probs(
        self,
        recent_returns: List[float],
        volatility_ratio: float,
        prev_probs: Optional[List[float]] = None,
        net_drift: float = 0.0,
    ) -> List[float]:
        """
        Computes the posterior probability distribution over states
        using forward Baum-Welch / HMM belief filtering.
        """
        if prev_probs is None or len(prev_probs) != 4:
            prev_probs = [0.25, 0.25, 0.25, 0.25]

        # Aggregate observation
        mean_ret = sum(recent_returns) / max(len(recent_returns), 1)

        # Emission likelihoods
        ret_var = 0.00005
        likelihoods = [
            self._gaussian_pdf(mean_ret, self.state_emissions[MarketRegimeState.TRENDING_BULLISH]["ret_mu"], ret_var),
            self._gaussian_pdf(mean_ret, self.state_emissions[MarketRegimeState.TRENDING_BEARISH]["ret_mu"], ret_var),
            self._gaussian_pdf(mean_ret, self.state_emissions[MarketRegimeState.MEAN_REVERTING]["ret_mu"], 0.00002),
            self._gaussian_pdf(volatility_ratio, self.state_emissions[MarketRegimeState.HIGH_VOL_COMPRESSED]["vol_mu"], 0.15),
        ]

        # Weight with macro drift
        if net_drift > 0.003:
            likelihoods[0] *= 2.5
        elif net_drift < -0.003:
            likelihoods[1] *= 2.5

        # Prior update via transition matrix: P(S_t) = sum( P(S_{t-1}) * T[S_{t-1}, S_t] )
        updated_priors = [0.0] * 4
        for j in range(4):
            updated_priors[j] = sum(prev_probs[i] * self.transition_matrix[i][j] for i in range(4))

        # Posterior: Likelihood * Prior
        posteriors = [likelihoods[i] * updated_priors[i] for i in range(4)]
        total = sum(posteriors)
        if total > 0:
            posteriors = [p / total for p in posteriors]
        else:
            posteriors = [0.25, 0.25, 0.25, 0.25]

        return posteriors


class MarketRegimeAgent:
    """
    Institutional Market Regime Classifier Agent.
    Operates at Macro / Higher Timeframe (H4 / D1 / H1) to govern order validation.
    """

    def __init__(self, confidence_cutoff: float = 0.55, veto_enabled: bool = False):
        """
        Parameters
        ----------
        veto_enabled : bool
            حق النقض السوقي (Macro Veto). **معطّل افتراضياً عن قصد** بعد معايرة
            بالبيانات (backend/cascade_calibration.py على 500 صفقة حقيقية):
              • الفيتو يرفض 29/500 صفقة، وهذه المجموعة **رابحة**: فوز 79.3%،
                أي أنه يمنع صفقات جيدة لا سيئة (أثره +14.04$ فقط من أصل 447.55$).
              • التصنيف نفسه يحمل معلومة مفيدة (يُحفظ ويُقاس): حالات الترند
                نسبة فوزها 56-60% مقابل 77.4% لحالة MEAN_REVERTING.
            فيبقى التصنيف والاتجاهات المسموحة معلومةً، ويسقط حق النقض الافتراضي.
        """
        self.confidence_cutoff = confidence_cutoff
        self.veto_enabled = veto_enabled
        self.hmm = GaussianHMMRegimeEstimator()
        self._history_state_probs: Dict[str, List[float]] = {}

    def classify(
        self,
        symbol: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        atr_current: float,
        atr_baseline: float,
    ) -> RegimeClassificationResult:
        """
        Classifies the current market regime for a given asset.
        """
        if len(closes) < 20:
            return RegimeClassificationResult(
                symbol=symbol,
                state=MarketRegimeState.UNCERTAIN,
                state_probabilities={},
                transition_entropy=1.0,
                volatility_compression_ratio=1.0,
                trend_strength=0.0,
                trade_allowed=False,
                allowed_directions=[],
                veto_reason="Insufficient price history for HMM evaluation.",
            )

        # 1. Compute recent log returns
        returns = [(closes[i] - closes[i - 1]) / max(closes[i - 1], 1e-6) for i in range(1, len(closes))]
        recent_returns = returns[-10:]

        # 2. Volatility Compression Ratio (current ATR vs long-term baseline ATR)
        vol_ratio = atr_current / max(atr_baseline, 1e-6)

        # 3. Trend strength (ADX / Slope proxy)
        net_drift = (closes[-1] - closes[-20]) / max(closes[-20], 1e-6)
        trend_strength = abs(net_drift) * 100.0

        # 4. HMM posterior probability inference
        prev_probs = self._history_state_probs.get(symbol, None)
        probs = self.hmm.estimate_state_probs(recent_returns, vol_ratio, prev_probs, net_drift=net_drift)
        self._history_state_probs[symbol] = probs

        prob_dict = {
            MarketRegimeState.TRENDING_BULLISH.value:    round(probs[0], 4),
            MarketRegimeState.TRENDING_BEARISH.value:    round(probs[1], 4),
            MarketRegimeState.MEAN_REVERTING.value:      round(probs[2], 4),
            MarketRegimeState.HIGH_VOL_COMPRESSED.value: round(probs[3], 4),
        }

        # Shannon Entropy as uncertainty metric
        entropy = -sum(p * math.log(max(p, 1e-12)) for p in probs) / math.log(4.0)

        # Identify dominant state
        state_idx = probs.index(max(probs))
        states_map = [
            MarketRegimeState.TRENDING_BULLISH,
            MarketRegimeState.TRENDING_BEARISH,
            MarketRegimeState.MEAN_REVERTING,
            MarketRegimeState.HIGH_VOL_COMPRESSED,
        ]
        dominant_state = states_map[state_idx]

        # 5. Determine trade allowance & allowed directions based on regime
        trade_allowed = True
        allowed_directions: List[str] = []
        veto_reason = None

        if dominant_state == MarketRegimeState.HIGH_VOL_COMPRESSED:
            # Dangerous pre-breakout volatility pinch: Veto all blind entries
            trade_allowed = False
            allowed_directions = []
            veto_reason = "HIGH_VOL_COMPRESSED: Volatility compression trap detected. High probability of whipsaw."

        elif dominant_state == MarketRegimeState.TRENDING_BULLISH:
            trade_allowed = True
            allowed_directions = ["BUY"]

        elif dominant_state == MarketRegimeState.TRENDING_BEARISH:
            trade_allowed = True
            allowed_directions = ["SELL"]

        elif dominant_state == MarketRegimeState.MEAN_REVERTING:
            trade_allowed = True
            # Both sides allowed (grid/mean-reversion strategies), but trend breakout blocked
            allowed_directions = ["BUY", "SELL"]

        return RegimeClassificationResult(
            symbol=symbol,
            state=dominant_state,
            state_probabilities=prob_dict,
            transition_entropy=round(entropy, 4),
            volatility_compression_ratio=round(vol_ratio, 3),
            trend_strength=round(trend_strength, 2),
            trade_allowed=trade_allowed,
            allowed_directions=allowed_directions,
            veto_reason=veto_reason,
        )

    def evaluate_macro_veto(
        self,
        symbol: str,
        proposed_action: str,
        regime_result: RegimeClassificationResult,
    ) -> Tuple[bool, Optional[str]]:
        """
        Mandatory gatekeeper check.
        Returns:
            (is_vetoed: bool, rejection_reason: Optional[str])

        ملاحظة معايرة: الفيتو لا يُطبَّق إلا عند veto_enabled=True. وإلا يُعاد
        (False, سبب_تشخيصي) مع الحفاظ على التصنيف والاتجاهات المسموحة كمعلومة.
        """
        if not self.veto_enabled:
            reason = None
            if not regime_result.trade_allowed:
                reason = f"MACRO VETO DISABLED (calibrated): market in {regime_result.state.value}"
            elif proposed_action.upper() not in regime_result.allowed_directions:
                reason = (f"MACRO VETO DISABLED (calibrated): '{proposed_action}' opposes "
                          f"'{regime_result.state.value}'")
            return False, reason

        if not regime_result.trade_allowed:
            return True, f"MACRO VETO: Market in {regime_result.state.value}. {regime_result.veto_reason}"

        if proposed_action.upper() not in regime_result.allowed_directions:
            return (
                True,
                f"MACRO VETO: Proposed direction '{proposed_action}' opposes dominant market regime "
                f"'{regime_result.state.value}'. Only {regime_result.allowed_directions} allowed."
            )

        return False, None
