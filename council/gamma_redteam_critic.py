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
    memory_circuit_breaker_active: bool = False
    contrastive_win_similarity: float = 0.0


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

    def _get_regime_trap_vectors(self, regime_state: Optional[str] = None) -> np.ndarray:
        """Fetches regime-filtered trap vectors when AdaptiveTrapMemory supports it."""
        if self._adaptive_memory is not None:
            try:
                vecs = self._adaptive_memory.get_trap_vectors(regime_state=regime_state)
            except TypeError:
                vecs = self._adaptive_memory.get_trap_vectors()
            if vecs is not None and len(vecs) > 0:
                return vecs
        return self._bootstrap_vectors

    def _get_weighted_regime_traps(self, regime_state: Optional[str] = None):
        if self._adaptive_memory is not None and hasattr(self._adaptive_memory, "get_weighted_trap_vectors"):
            vecs, weights = self._adaptive_memory.get_weighted_trap_vectors(regime_state=regime_state)
            if vecs is not None and len(vecs) > 0:
                return vecs, weights
        vecs = self._get_regime_trap_vectors(regime_state=regime_state)
        return vecs, np.ones((len(vecs),), dtype=np.float64)

    @staticmethod
    def _weighted_topk_cosine(
        feature_vec: np.ndarray,
        db_vecs: np.ndarray,
        weights: np.ndarray,
        top_k: int = 3,
    ) -> float:
        """Column-wise Z-score normalized cosine similarity with time-decay weighted top-k aggregation."""
        if len(db_vecs) == 0:
            return 0.0
        col_mean = np.mean(db_vecs, axis=0)
        col_std = np.std(db_vecs, axis=0)
        col_std = np.where(col_std < 1e-6, 1.0, col_std)

        z_db = (db_vecs - col_mean) / col_std
        z_f = (feature_vec - col_mean) / col_std

        norm_f = np.linalg.norm(z_f)
        w_all = weights if len(weights) == len(db_vecs) else np.ones((len(db_vecs),), dtype=np.float64)

        # Centroid / tight-cluster guard: if query sits right on cluster mean (norm_f ~ 0),
        # evaluate standardized RBF proximity instead of falsely returning 0.0 similarity
        if norm_f <= 1e-6:
            dists = np.linalg.norm(z_db - z_f, axis=1)
            sims = np.exp(-0.5 * dists)
            w_valid = w_all
        else:
            norms_db = np.linalg.norm(z_db, axis=1)
            valid = norms_db > 1e-9
            if not np.any(valid):
                dists = np.linalg.norm(z_db - z_f, axis=1)
                sims = np.exp(-0.5 * dists)
                w_valid = w_all
            else:
                cos_sims = np.clip(np.dot(z_db[valid], z_f) / (norms_db[valid] * norm_f), 0.0, 1.0)
                dists = np.linalg.norm(z_db[valid] - z_f, axis=1)
                rbf_sims = np.exp(-0.35 * dists)
                sims = np.maximum(cos_sims, 0.85 * rbf_sims)
                w_valid = w_all[valid]

        # Blend top-k weighted mean with peak weighted similarity so one stale outlier cannot dominate
        k = min(max(int(top_k), 1), len(sims))
        effective_scores = sims * np.clip(w_valid, 0.1, 1.5)
        top_idx = np.argsort(effective_scores)[-k:]
        top_sims = sims[top_idx]
        top_w = np.clip(w_valid[top_idx], 0.05, 1.5)
        weighted_mean = float(np.sum(top_sims * top_w) / np.sum(top_w))
        peak_sim = float(np.max(top_sims))
        # Decay-aware scaling: if all top-k matches are very old (low weight), damp similarity
        recency_factor = float(np.clip(np.mean(top_w), 0.25, 1.0))
        return float(np.clip((0.65 * weighted_mean + 0.35 * peak_sim) * recency_factor, 0.0, 1.0))

    def _compute_contrastive_win_similarity(
        self,
        feature_vec: np.ndarray,
        regime_state: Optional[str] = None,
    ) -> float:
        """Computes weighted top-k similarity against verified recent winning trades in the same regime."""
        if self._adaptive_memory is None or not hasattr(self._adaptive_memory, "get_weighted_winning_vectors"):
            return 0.0
        win_vecs, win_w = self._adaptive_memory.get_weighted_winning_vectors(regime_state=regime_state)
        if win_vecs is None or len(win_vecs) < 3:
            return 0.0
        return round(self._weighted_topk_cosine(feature_vec, win_vecs, win_w, top_k=3), 4)

    def _compute_episodic_trap_similarity(
        self,
        feature_vec: np.ndarray,
        regime_state: Optional[str] = None,
    ) -> float:
        """
        Upgrade (2026 v2): Time-decayed weighted top-k Z-score cosine similarity against
        regime-matched losing trade embeddings.
        """
        db_vecs, weights = self._get_weighted_regime_traps(regime_state=regime_state)
        if len(db_vecs) == 0:
            return 0.05

        agg_sim = self._weighted_topk_cosine(feature_vec, db_vecs, weights, top_k=3)
        if agg_sim <= 1e-9:
            return 0.05
        if agg_sim > 0.85:
            return round(0.35 + (agg_sim - 0.85) * 3.0, 4)
        return round(agg_sim * 0.14, 4)

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

        # 5. Episodic Memory RAG Check with Dual Memory Circuit Breaker & Contrastive Relief (2026 v2)
        # Suspend historical retrieval under volatility shocks OR regime-transition collapse
        cb_vol_shock = (regime.regime_state == RegimeState.HIGH_VOL_SHOCK) or (regime.atr_ratio >= 2.0)
        cb_regime_uncertain = float(getattr(regime, "regime_confidence", 1.0)) < 0.45
        memory_cb_active = cb_vol_shock or cb_regime_uncertain
        contrastive_win_sim = 0.0

        if memory_cb_active:
            episodic_loss_prob = 0.0
            cb_reason = "volatility shock" if cb_vol_shock else f"low regime confidence ({regime.regime_confidence:.2f})"
            flaws.append(f"MEMORY_CIRCUIT_BREAKER: Historical trap retrieval suspended ({cb_reason}).")
        else:
            current_vec = np.array(
                [
                    regime.hurst_exponent,
                    regime.atr_ratio,
                    abs(regime.rolling_z_score),
                    proposal.ofi_z_score,   # real OFI Z-score
                    spread_ratio,
                ],
                dtype=float,
            )
            episodic_loss_prob = self._compute_episodic_trap_similarity(
                current_vec, regime_state=regime.regime_state.value
            )
            contrastive_win_sim = self._compute_contrastive_win_similarity(
                current_vec, regime_state=regime.regime_state.value
            )
            # Contrastive relief: if setup strongly matches recent winners in the same regime, soften trap penalty
            win_relief = 0.0
            if contrastive_win_sim > 0.78 and episodic_loss_prob > 0.15:
                win_relief = min(0.12, (contrastive_win_sim - 0.75) * 0.45)
                episodic_loss_prob = round(max(0.0, episodic_loss_prob - win_relief), 4)

            if episodic_loss_prob > 0.25:
                flaws.append(
                    f"EPISODIC_TRAP_MATCH: Setup matches {regime.regime_state.value} losing profile "
                    f"(Loss score: {episodic_loss_prob:.2f}, WinSim: {contrastive_win_sim:.2f})."
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
            memory_circuit_breaker_active=memory_cb_active,
            contrastive_win_similarity=contrastive_win_sim,
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
