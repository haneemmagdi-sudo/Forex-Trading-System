"""
Agent Gamma: The Red-Team Adversarial Critic (`gamma_redteam_critic.py`)
Mandate: Attempt to DESTROY and INVALIDATE the trade proposed by Agent Beta.
Checks:
1. Spread-to-ATR toxicity (Veto if current_spread > 15% of M5 ATR)
2. Higher Timeframe (H1) opposing structure / unmitigated wall within 1.5R
3. Reward-to-Risk Ratio sanity check
4. Episodic Memory — Adaptive vector similarity check (live SQLite-backed,
   replaces the original 3-vector static array).
"""

import asyncio
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from .alpha_regime_agent import RegimeOutput, RegimeState
from .beta_orderflow_agent import OrderFlowProposal


class CriticAssessment(BaseModel):
    symbol: str
    critic_veto_triggered: bool
    failure_probability_score: float = Field(..., ge=0.0, le=1.0)
    fatal_flaws: List[str]
    critic_notes: str
    spread_to_atr_ratio: float
    episodic_similarity_loss_rate: float


class GammaRedTeamCritic:
    """
    Adversarial Red-Team Agent. Assumes every trade is a retail inducement trap
    until proven otherwise.
    Trap vectors are sourced from AdaptiveTrapMemory (live SQLite) when available,
    falling back to a 5-vector bootstrap seed.
    """

    def __init__(
        self,
        max_spread_atr_ratio: float = 0.15,
        point_value: float = 0.00001,
        historical_trap_vectors: Optional[np.ndarray] = None,
        adaptive_memory=None,   # memory_rag.AdaptiveTrapMemory instance
    ):
        self.max_spread_atr_ratio = max_spread_atr_ratio
        self.point_value = point_value
        self._adaptive_memory = adaptive_memory  # optional live memory hook

        # Bootstrap matrix used when adaptive_memory is None or has < MIN_RECORDS
        if historical_trap_vectors is not None:
            self._bootstrap_vectors = historical_trap_vectors
        else:
            self._bootstrap_vectors = np.array(
                [
                    [0.50, 2.30, 2.80, -1.50, 0.18],  # High-vol exhaustion trap
                    [0.49, 1.05, 0.20,  0.10, 0.16],  # Mid-range chop trap
                    [0.62, 1.85, 2.95, -1.90, 0.14],  # Late trend buying into HTF wall
                    [0.51, 1.40, 1.60, -0.80, 0.17],  # Low-conviction FOMO entry
                    [0.53, 0.95, 0.05,  0.05, 0.19],  # Wide spread, low momentum
                ],
                dtype=float,
            )

    @property
    def trap_vectors(self) -> np.ndarray:
        """Returns live trap vectors from adaptive memory, or bootstrap fallback."""
        if self._adaptive_memory is not None:
            vecs = self._adaptive_memory.get_trap_vectors()
            if vecs is not None and len(vecs) > 0:
                return vecs
        return self._bootstrap_vectors

    def _compute_episodic_trap_similarity(self, feature_vec: np.ndarray) -> float:
        """
        Computes cosine similarity against historical losing trade embeddings (RAG Memory).
        Returns estimated historical loss probability [0.0 - 1.0].
        """
        norm_f = np.linalg.norm(feature_vec)
        if norm_f <= 1e-9 or len(self.trap_vectors) == 0:
            return 0.05

        norms_db = np.linalg.norm(self.trap_vectors, axis=1)
        valid = norms_db > 1e-9
        if not np.any(valid):
            return 0.05

        sims = np.dot(self.trap_vectors[valid], feature_vec) / (norms_db[valid] * norm_f)
        max_sim = float(np.max(np.clip(sims, 0.0, 1.0)))
        # Map high cosine similarity (>0.85) to elevated failure probability
        if max_sim > 0.90:
            return round(0.35 + (max_sim - 0.90) * 4.0, 4)
        return round(max_sim * 0.12, 4)

    def _audit_sync(
        self,
        proposal: OrderFlowProposal,
        regime: RegimeOutput,
        df_h1: pd.DataFrame,
        current_spread_points: float,
    ) -> CriticAssessment:
        flaws: List[str] = []
        penalty_score = 0.04  # Base market friction uncertainty

        if proposal.proposed_action == "STAND_DOWN":
            return CriticAssessment(
                symbol=proposal.symbol,
                critic_veto_triggered=True,
                failure_probability_score=1.0,
                fatal_flaws=["No active trade proposed by Agent Beta."],
                critic_notes="Stand down confirmed.",
                spread_to_atr_ratio=0.0,
                episodic_similarity_loss_rate=0.0,
            )

        # 1. Spread-to-ATR Toxicity Check (Rule from .antigravityrules)
        atr_points = max(regime.atr_points, 1.0)
        spread_ratio = current_spread_points / atr_points
        if spread_ratio > self.max_spread_atr_ratio:
            flaws.append(
                f"TOXIC_SPREAD: Current spread ({current_spread_points} pts) is "
                f"{spread_ratio:.1%} of M5 ATR (Max allowed: {self.max_spread_atr_ratio:.0%})."
            )
            penalty_score += 0.55

        # 2. Higher Timeframe (H1) Opposing Wall Check
        h1_high = float(df_h1["high"].iloc[-12:].max())
        h1_low = float(df_h1["low"].iloc[-12:].min())
        risk_distance = abs(proposal.entry_price - proposal.stop_loss)

        if "BUY" in proposal.proposed_action:
            dist_to_h1_resistance = h1_high - proposal.entry_price
            if 0 < dist_to_h1_resistance < (0.9 * risk_distance):
                flaws.append(
                    f"HTF_RESISTANCE_WALL: Buying directly into 12-hour H1 high ({h1_high:.5f}) "
                    f"with less than 0.9R room."
                )
                penalty_score += 0.25

        elif "SELL" in proposal.proposed_action:
            dist_to_h1_support = proposal.entry_price - h1_low
            if 0 < dist_to_h1_support < (0.9 * risk_distance):
                flaws.append(
                    f"HTF_SUPPORT_WALL: Selling directly into 12-hour H1 low ({h1_low:.5f}) "
                    f"with less than 0.9R room."
                )
                penalty_score += 0.25

        # 3. Order Flow Divergence Check (using Real OFI Z-score)
        if "BUY" in proposal.proposed_action and proposal.ofi_z_score < -1.5:
            flaws.append("DELTA_DIVERGENCE: Aggressive institutional selling delta against Long setup.")
            penalty_score += 0.20
        elif "SELL" in proposal.proposed_action and proposal.ofi_z_score > 1.5:
            flaws.append("DELTA_DIVERGENCE: Aggressive institutional buying delta against Short setup.")
            penalty_score += 0.20

        # 4. Off-Killzone Liquidity Penalty
        if not proposal.killzone_active:
            flaws.append("LOW_LIQUIDITY_SESSION: Setup occurred outside London/NY Killzones.")
            penalty_score += 0.06

        # 5. Episodic Memory RAG Check (adaptive live vectors)
        current_vec = np.array(
            [
                regime.hurst_exponent,
                regime.atr_ratio,
                abs(regime.rolling_z_score),
                proposal.ofi_z_score,   # real OFI Z-score (replaces tick_volume_delta_z)
                spread_ratio,
            ],
            dtype=float,
        )
        episodic_loss_prob = self._compute_episodic_trap_similarity(current_vec)
        if episodic_loss_prob > 0.25:
            flaws.append(
                f"EPISODIC_TRAP_MATCH: Setup matches historical losing volatility profile "
                f"(Loss score: {episodic_loss_prob:.2f})."
            )
            penalty_score += episodic_loss_prob * 0.5

        total_failure_prob = float(np.clip(penalty_score, 0.0, 1.0))
        veto = (spread_ratio > self.max_spread_atr_ratio) or (total_failure_prob >= 0.45)

        if not flaws:
            notes = "Red-Team Critic found zero structural flaws. Setup survived adversarial audit."
        else:
            notes = " | ".join(flaws)

        return CriticAssessment(
            symbol=proposal.symbol,
            critic_veto_triggered=veto,
            failure_probability_score=round(total_failure_prob, 4),
            fatal_flaws=flaws,
            critic_notes=notes,
            spread_to_atr_ratio=round(spread_ratio, 4),
            episodic_similarity_loss_rate=episodic_loss_prob,
        )

    async def audit_proposal(
        self,
        proposal: OrderFlowProposal,
        regime: RegimeOutput,
        df_h1: pd.DataFrame,
        current_spread_points: float,
    ) -> CriticAssessment:
        return await asyncio.to_thread(
            self._audit_sync, proposal, regime, df_h1, current_spread_points
        )
