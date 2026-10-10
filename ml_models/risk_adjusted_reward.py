"""
==============================================================================
ml_models/risk_adjusted_reward.py — Institutional Reward Shaping
==============================================================================
Module  : Risk-Adjusted Reward Shaping (Sortino & MAE Penalty)
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Replaces naive pip-maximizing rewards with an institutional risk-adjusted reward
function for Reinforcement Learning agents (PPO, SAC, DQN).

Mathematical Formulation:
-------------------------
Reward = w_pnl * R_pnl
       + w_sortino * R_sortino
       - w_mae * R_mae_penalty
       - w_slip * R_slippage_penalty

Key Components:
1. Sortino Reward:
   Penalizes solely downside deviation (downside semivariance) rather than
   upside volatility.
2. Maximum Adverse Excursion (MAE) Penalty:
   Measures the maximum intra-trade drawdown experienced immediately post-entry.
   Even if a trade closes in profit, experiencing a deep MAE incurs a sharp penalty,
   forcing the RL policy to learn sniper-like, precise entry timing.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("institutional_mas.reward_shaping")


@dataclass
class TradeTrajectorySnapshot:
    entry_price: float
    current_price: float
    direction: int                # +1 for BUY, -1 for SELL
    bars_held: int
    unrealized_pnl_pct: float
    max_adverse_excursion_pct: float  # Maximum negative floating dip since entry
    max_favorable_excursion_pct: float # Peak floating profit since entry


class RiskAdjustedRewardShaper:
    """
    Computes dense and step rewards emphasizing Sortino ratio and entry precision.
    """

    def __init__(
        self,
        target_annual_return: float = 0.20,
        mae_penalty_weight: float = 2.5,
        sortino_weight: float = 1.8,
        drawdown_soft_cap: float = 0.015,  # 1.5% max acceptable entry dip
    ):
        self.target_annual_return = target_annual_return
        self.mae_penalty_weight = mae_penalty_weight
        self.sortino_weight = sortino_weight
        self.drawdown_soft_cap = drawdown_soft_cap
        self._rolling_returns: List[float] = []

    def compute_step_reward(
        self,
        snapshot: TradeTrajectorySnapshot,
        bar_return_pct: float,
        is_terminal: bool = False,
    ) -> float:
        """
        Calculates the risk-adjusted reward for the current RL environment step.
        """
        self._rolling_returns.append(bar_return_pct)
        if len(self._rolling_returns) > 100:
            self._rolling_returns.pop(0)

        # 1. Base PnL Return
        r_pnl = snapshot.unrealized_pnl_pct * 10.0

        # 2. Maximum Adverse Excursion (MAE) Penalty
        # If MAE exceeds soft cap (e.g. 1.5%), apply quadratic penalty
        mae = snapshot.max_adverse_excursion_pct
        if mae > self.drawdown_soft_cap:
            excess_mae = mae - self.drawdown_soft_cap
            mae_penalty = self.mae_penalty_weight * (excess_mae ** 1.5) * 100.0
        else:
            mae_penalty = 0.0

        # 3. Rolling Sortino Ratio calculation
        sortino_reward = 0.0
        if len(self._rolling_returns) >= 15:
            mean_ret = sum(self._rolling_returns) / len(self._rolling_returns)
            downside_sq = [min(0.0, r) ** 2 for r in self._rolling_returns]
            downside_dev = math.sqrt(sum(downside_sq) / max(len(downside_sq), 1))

            if downside_dev > 1e-6:
                sortino = mean_ret / downside_dev
                # Bounded reward contribution
                sortino_reward = self.sortino_weight * max(-2.0, min(2.0, sortino))

        # 4. Immediate Post-Entry Sniping Bonus
        # Rewarding trades that immediately move into profit within first 3 bars
        sniper_bonus = 0.0
        if snapshot.bars_held <= 3 and snapshot.unrealized_pnl_pct > 0.0020:
            sniper_bonus = 0.35

        # Aggregate total step reward
        total_reward = r_pnl + sortino_reward - mae_penalty + sniper_bonus

        # Terminal trade close settlement
        if is_terminal:
            if snapshot.unrealized_pnl_pct > 0 and mae < self.drawdown_soft_cap:
                total_reward += 1.0  # Clean win bonus
            elif snapshot.unrealized_pnl_pct < 0:
                total_reward -= 0.5

        return round(total_reward, 4)

    def reset(self):
        """Reset trajectory memory for new episode."""
        self._rolling_returns.clear()
