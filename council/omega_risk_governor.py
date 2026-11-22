"""
Agent Omega: Chief Risk & Execution Governor (`omega_risk_governor.py`)
Synthesizes the debate between Agent Alpha (Regime), Agent Beta (Order Flow),
and Agent Gamma (Red-Team Critic).
Applies the strict approval formula, Dynamic Threshold Engine, and
Fractional Kelly dynamic position sizing.

Upgrade (2026-10):
  - AdaptiveThresholdEngine adjusts the 0.72 approval threshold based on:
    * Current market regime (CHOPPY → +0.10)
    * Rolling 20-trade win rate (< 40% → +0.08)
    * ATR volatility ratio (> 1.8 → +0.05)
    * MacroSentinel risk multiplier (applied to final risk_percent)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import numpy as np
from pydantic import BaseModel, Field

from .alpha_regime_agent import RegimeOutput, RegimeState
from .beta_orderflow_agent import OrderFlowProposal
from .gamma_redteam_critic import CriticAssessment
from quant_core.meta_model import CalibratedKellySizer


class ExecutionParams(BaseModel):
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_percent: float = Field(..., ge=0.0, le=2.0)
    max_allowed_spread_points: int
    expiration_minutes: int


class SignalPayload(BaseModel):
    """
    Strict JSON Contract between Python Multi-Agent Council and MQL5 InstitutionalExecutor.mq5
    """
    timestamp_utc: str
    symbol: str
    action: str = Field(..., description="BUY | SELL | LIMIT_BUY | LIMIT_SELL | STAND_DOWN")
    regime_state: str
    confidence_score: float
    approval_threshold_used: float = Field(
        ...,
        description="Dynamic approval threshold applied by AdaptiveThresholdEngine.",
    )
    critic_veto_triggered: bool
    critic_notes: str
    macro_risk_level: str = Field(
        default="CLEAR",
        description="MacroSentinel risk level at signal time.",
    )
    execution_params: ExecutionParams


# ---------------------------------------------------------------------------
# AdaptiveThresholdEngine
# ---------------------------------------------------------------------------

class AdaptiveThresholdEngine:
    """
    Adjusts OmegaRiskGovernor's approval threshold dynamically based on:
      1. Market regime from Agent Alpha
      2. Rolling win rate from AdaptiveTrapMemory / TradeJournalDB
      3. Current ATR volatility ratio

    Thresholds never drop below BASE_THRESHOLD and are capped at 0.92.
    All adjustments are additive penalties (conservative direction only).
    """

    BASE_THRESHOLD: float = 0.72

    def compute(
        self,
        regime: RegimeOutput,
        rolling_win_rate: float = 0.50,
        regime_win_rate: Optional[float] = None,
        critic_flaw_count: int = 0,
        reflection_penalty: float = 0.0,
        bus_threshold_shift: float = 0.0,
    ) -> float:
        """
        Returns the final dynamic approval threshold.

        Args:
            regime: Output from AlphaRegimeAgent containing regime_state and atr_ratio.
            rolling_win_rate: Win rate from last 20 closed trades (0.0-1.0).
                              Defaults to 0.50 (neutral) when no history exists.
        """
        threshold = self.BASE_THRESHOLD
        adjustments: list[tuple[str, float]] = []

        # Penalty 1: Choppy / random walk regime — harder to extract edge
        if regime.regime_state == RegimeState.CHOPPY_RANDOM_WALK:
            threshold += 0.10
            adjustments.append(("CHOPPY_REGIME", 0.10))

        # Penalty 2: Recent system underperformance
        if rolling_win_rate < 0.40:
            threshold += 0.08
            adjustments.append(("LOW_WIN_RATE", 0.08))
        elif rolling_win_rate < 0.48:
            threshold += 0.04
            adjustments.append(("BORDERLINE_WIN_RATE", 0.04))

        # Penalty 3: Elevated volatility — higher noise, wider spreads
        if regime.atr_ratio > 1.8:
            threshold += 0.05
            adjustments.append(("HIGH_ATR_RATIO", 0.05))

        # Penalty 4: High Vol Shock regime — extra caution even if not vetoed
        if regime.regime_state == RegimeState.HIGH_VOL_SHOCK:
            threshold += 0.08
            adjustments.append(("HIGH_VOL_SHOCK", 0.08))

        # Penalty 5 (2026 v2): Regime-specific win rate degradation
        if regime_win_rate is not None and regime_win_rate < 0.42:
            threshold += 0.05
            adjustments.append(("LOW_REGIME_WIN_RATE", 0.05))

        # Penalty 6 (2026 v2): Multiple non-fatal Red-Team flaws tighten selectivity
        if critic_flaw_count >= 2:
            threshold += 0.03
            adjustments.append(("MULTI_CRITIC_FLAWS", 0.03))

        # Penalty 7 (2026 Batch 2): Active AgentReflection & SignalBus live threshold shift
        if reflection_penalty > 0.0:
            rp = min(0.08, float(reflection_penalty))
            threshold += rp
            adjustments.append(("REFLECTION_MEMORY", rp))
        if bus_threshold_shift > 0.0:
            bs = min(0.06, float(bus_threshold_shift))
            threshold += bs
            adjustments.append(("SIGNAL_BUS_SHIFT", bs))

        final_threshold = round(min(threshold, 0.92), 4)
        return final_threshold


class OmegaRiskGovernor:
    """
    Final Judge & Risk Governor.
    Enforces:
      Net_Approval_Score = (Signal_Confidence * Regime_Confidence) - Failure_Probability_Score
    The approval threshold is dynamic (AdaptiveThresholdEngine), not fixed at 0.72.
    Macro risk multiplier from Agent Delta is applied to final risk_percent.
    """

    def __init__(
        self,
        approval_threshold: float = 0.72,
        max_risk_percent: float = 1.0,
        min_risk_percent: float = 0.25,
        max_daily_drawdown_pct: float = 3.0,
    ):
        self.approval_threshold = approval_threshold  # base threshold (overridden by adaptive)
        self.max_risk_percent = max_risk_percent
        self.min_risk_percent = min_risk_percent
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self._threshold_engine = AdaptiveThresholdEngine()
        self._kelly_sizer = CalibratedKellySizer(fractional_kelly=0.25, min_multiplier=0.25, max_multiplier=1.50)

    def compute_fractional_kelly_risk(
        self,
        win_prob: float,
        reward_to_risk: float,
        current_daily_dd_pct: float = 0.0,
    ) -> float:
        """
        Calculates Half-Kelly dynamic risk percentage, scaled down as daily drawdown approaches limit.
        f* = (p * b - q) / b
        """
        if current_daily_dd_pct >= (self.max_daily_drawdown_pct * 0.85):
            return 0.0

        b = max(reward_to_risk, 0.5)
        p = np.clip(win_prob, 0.01, 0.99)
        q = 1.0 - p

        # Drawdown damper
        dd_headroom = max(0.0, 1.0 - (current_daily_dd_pct / self.max_daily_drawdown_pct))

        full_kelly = (p * b - q) / b
        if full_kelly <= 0:
            # IMPROVEMENT_PLAN §3: Sizing scale floor instead of binary elimination
            return round(float(self.min_risk_percent * dd_headroom), 2)

        # Quarter-Kelly for institutional forex capital preservation
        quarter_kelly_pct = (full_kelly * 0.25) * 100.0
        adjusted_risk = quarter_kelly_pct * dd_headroom

        return round(float(np.clip(adjusted_risk, self.min_risk_percent, self.max_risk_percent)), 2)

    def adjudicate(
        self,
        regime: RegimeOutput,
        proposal: OrderFlowProposal,
        critic: CriticAssessment,
        current_daily_dd_pct: float = 0.0,
        rolling_win_rate: float = 0.50,
        macro_risk_multiplier: float = 1.0,
        macro_risk_level: str = "CLEAR",
        calibrated_p_win: Optional[float] = None,
        regime_win_rate: Optional[float] = None,
        reflection_advisory: Optional[Dict[str, Any]] = None,
        bus_context: Optional[Dict[str, Any]] = None,
    ) -> SignalPayload:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Extract live SignalBus & ReflectionMemory context (2026 Batch 2)
        refl_dict = reflection_advisory or {}
        bus_dict = bus_context or {}
        refl_cooldown = bool(refl_dict.get("temporary_cooldown", False))
        bus_emergency_dd = bool(bus_dict.get("emergency_dd_active", False))
        bus_news_blackout = bool(bus_dict.get("news_blackout", False))
        refl_pen = float(refl_dict.get("threshold_penalty", 0.0) or 0.0)
        bus_shift = float(bus_dict.get("bus_threshold_shift", 0.0) or 0.0)

        # Dynamic threshold (2026 v2 + Batch 2: regime WR, flaws, reflection memory & bus shift)
        non_cb_flaws = [f for f in critic.fatal_flaws if not f.startswith("MEMORY_CIRCUIT_BREAKER")]
        dynamic_threshold = self._threshold_engine.compute(
            regime=regime,
            rolling_win_rate=rolling_win_rate,
            regime_win_rate=regime_win_rate,
            critic_flaw_count=len(non_cb_flaws),
            reflection_penalty=refl_pen,
            bus_threshold_shift=bus_shift,
        )

        # Calculate Net Approval Score per .antigravityrules formula
        structural_net = (proposal.signal_confidence * regime.regime_confidence) - critic.failure_probability_score
        structural_net = float(np.clip(structural_net, 0.0, 1.0))

        # 2026 Calibrated Probability Fusion: when Meta-Model supplies calibrated_p_win,
        # fuse it with structural_net so uncalibrated heuristics cannot override calibrated edge
        if calibrated_p_win is not None:
            cal_net = float(np.clip(float(calibrated_p_win) - critic.failure_probability_score, 0.0, 1.0))
            net_score = round(float(np.clip(0.45 * structural_net + 0.55 * cal_net, 0.0, 1.0)), 4)
        else:
            net_score = round(structural_net, 4)

        max_spread_pts = max(5, int(round(regime.atr_points * 0.15)))

        # Check Hard Veto conditions
        is_approved = (
            proposal.proposed_action != "STAND_DOWN"
            and not critic.critic_veto_triggered
            and regime.regime_state not in (RegimeState.HIGH_VOL_SHOCK, RegimeState.CHOPPY_RANDOM_WALK)
            and net_score >= dynamic_threshold
            and current_daily_dd_pct < (self.max_daily_drawdown_pct * 0.85)
            and macro_risk_multiplier > 0.0   # Agent Delta BLACKOUT = hard veto
            and not refl_cooldown
            and not bus_emergency_dd
            and not bus_news_blackout
        )

        if not is_approved:
            reason_prefix = "[GOVERNOR STAND_DOWN] "
            if critic.critic_veto_triggered:
                reason_prefix = "[RED-TEAM VETO] "
            elif bus_emergency_dd:
                reason_prefix = "[BUS EMERGENCY DD] "
            elif bus_news_blackout:
                reason_prefix = "[BUS NEWS BLACKOUT] "
            elif refl_cooldown:
                reason_prefix = f"[REFLECTION COOLDOWN: {refl_dict.get('summary', 'loss_streak')}] "
            elif macro_risk_multiplier == 0.0:
                reason_prefix = f"[MACRO BLACKOUT: {macro_risk_level}] "
            elif net_score < dynamic_threshold:
                reason_prefix = (
                    f"[SCORE BELOW {dynamic_threshold:.2f} (Got {net_score:.2f})"
                    f" | Thresh adjusted from 0.72] "
                )

            return SignalPayload(
                timestamp_utc=now_iso,
                symbol=proposal.symbol,
                action="STAND_DOWN",
                regime_state=regime.regime_state.value,
                confidence_score=net_score,
                approval_threshold_used=dynamic_threshold,
                critic_veto_triggered=True,
                critic_notes=f"{reason_prefix}{critic.critic_notes}",
                macro_risk_level=macro_risk_level,
                execution_params=ExecutionParams(
                    entry_price=proposal.entry_price,
                    stop_loss=proposal.stop_loss,
                    take_profit_1=proposal.take_profit_1,
                    take_profit_2=proposal.take_profit_2,
                    risk_percent=0.0,
                    max_allowed_spread_points=max_spread_pts,
                    expiration_minutes=0,
                ),
            )

        # Calculate Reward-to-Risk Ratio for TP1
        risk_dist = max(abs(proposal.entry_price - proposal.stop_loss), 1e-6)
        reward_dist = abs(proposal.take_profit_1 - proposal.entry_price)
        rr_ratio = reward_dist / risk_dist

        # P2 fix: use CalibratedKellySizer when calibrated_p_win is supplied (otherwise smooth Kelly on net_score)
        if calibrated_p_win is not None:
            dd_headroom = max(0.0, 1.0 - (current_daily_dd_pct / self.max_daily_drawdown_pct))
            base_risk = (self.min_risk_percent + self.max_risk_percent) / 2.0
            kelly_mult = self._kelly_sizer.compute_size_multiplier(calibrated_p_win, rr_ratio)
            dynamic_risk_pct = round(
                float(np.clip(base_risk * kelly_mult * dd_headroom, self.min_risk_percent, self.max_risk_percent)),
                2,
            )
        else:
            dynamic_risk_pct = self.compute_fractional_kelly_risk(
                win_prob=net_score,
                reward_to_risk=rr_ratio,
                current_daily_dd_pct=current_daily_dd_pct,
            )
        # Apply MacroSentinel risk multiplier (scales down risk near news events)
        dynamic_risk_pct = round(
            float(np.clip(dynamic_risk_pct * macro_risk_multiplier,
                          0.0, self.max_risk_percent)),
            2,
        )

        return SignalPayload(
            timestamp_utc=now_iso,
            symbol=proposal.symbol,
            action=proposal.proposed_action,
            regime_state=regime.regime_state.value,
            confidence_score=net_score,
            approval_threshold_used=dynamic_threshold,
            critic_veto_triggered=False,
            critic_notes=f"[APPROVED | RR={rr_ratio:.2f} | Thresh={dynamic_threshold:.2f}] {critic.critic_notes}",
            macro_risk_level=macro_risk_level,
            execution_params=ExecutionParams(
                entry_price=proposal.entry_price,
                stop_loss=proposal.stop_loss,
                take_profit_1=proposal.take_profit_1,
                take_profit_2=proposal.take_profit_2,
                risk_percent=dynamic_risk_pct,
                max_allowed_spread_points=max_spread_pts,
                expiration_minutes=15,
            ),
        )
