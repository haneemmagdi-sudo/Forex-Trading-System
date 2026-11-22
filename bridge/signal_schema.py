"""
=============================================================================
bridge/signal_schema.py — Strict Pydantic Contracts for Institutional MAS IPC
=============================================================================
Architectural Authority: .antigravityrules (Section 1, Section 2 Law 2 & Law 4, Section 3)
Environment: Antigravity IDE | MetaTrader 5 (MQL5) + Python 3.11+

Core Contracts:
1. SignalPayload: Strict, cryptographically signable contract for SignalPayload.json,
   enforcing the MQL5 Double-Lock Protocol (expiration_timestamp_utc and max_allowed_spread_points).
2. AgentCouncilVerdict: Consensus contract evaluating:
   S_final = (C_beta * A_alpha) - P_gamma
   Execution threshold: S_final > 0.72 and critic_veto_triggered == False.
3. Inter-Agent Communication Schemas:
   - AlphaRegimeMessage (Agent 1: Market Regime Gatekeeper)
   - BetaSetupMessage (Agent 2: SMC & Institutional Entry Generator)
   - GammaCriticMessage (Agent 3: Adversarial Critic & Trap Detector)
   - OmegaGovernorVerdict (Agent 4: Final Consensus Judge & Payload Signer)
   - ExecutionReceipt (MQL5 Hot Path -> Python Feedback Loop)
=============================================================================
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# Global Execution Mode: "SHADOW" prevents live orders while running the full 4-agent council
EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "SHADOW").upper()


class OrderAction(str, Enum):
    """Institutional Order Action directives."""
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


class OrderType(str, Enum):
    """Execution Order Types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class ExecutionMode(str, Enum):
    """System Execution Modes."""
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class RegimeClassification(str, Enum):
    """Market Regime Classifications emitted by Quant Core & Alpha Agent."""
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    MEAN_REVERTING = "MEAN_REVERTING"
    CHOPPY_RANDOM_WALK = "CHOPPY_RANDOM_WALK"
    HIGH_VOL_SHOCK = "HIGH_VOL_SHOCK"
    VOLATILITY_COMPRESSION = "VOLATILITY_COMPRESSION"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"


# =============================================================================
# SUB-CONTRACTS: COUNCIL VERDICT & RISK METRICS
# =============================================================================

class AgentCouncilVerdict(BaseModel):
    """
    Consensus verdict emitted by the 4-Agent Adversarial Council.
    Enforces Law 2 formulation: S_final = (C_beta * A_alpha) - P_gamma.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha_regime_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent Alpha regime alignment score (A_alpha in [0, 1])",
    )
    beta_setup_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent Beta setup confidence (C_beta in [0, 1])",
    )
    gamma_failure_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Agent Gamma adversarial failure probability (P_gamma in [0, 1])",
    )
    omega_consensus_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Adversarial Consensus Score S_final = (C_beta * A_alpha) - P_gamma",
    )
    critic_veto_triggered: bool = Field(
        default=False,
        description="Hard veto flag raised by Gamma RedTeam Critic",
    )
    verdict_status: Literal["APPROVED", "VETOED", "SHADOW_APPROVED"] = Field(
        ...,
        description="Categorical council determination",
    )
    rationale: str = Field(
        ...,
        min_length=5,
        description="Detailed synthesis narrative explaining consensus outcome",
    )
    evaluated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC evaluation timestamp",
    )

    @model_validator(mode="after")
    def validate_consensus_formula(self) -> "AgentCouncilVerdict":
        """Verify mathematical integrity of S_final calculation."""
        expected_s = (self.beta_setup_confidence * self.alpha_regime_score) - self.gamma_failure_probability
        # Tolerance for floating point precision
        if abs(self.omega_consensus_score - expected_s) > 1e-3:
            raise ValueError(
                f"Consensus score mismatch: expected S_final = ({self.beta_setup_confidence} * "
                f"{self.alpha_regime_score}) - {self.gamma_failure_probability} = {expected_s:.4f}, "
                f"got {self.omega_consensus_score:.4f}"
            )
        return self


class RiskMetrics(BaseModel):
    """
    Quantitative risk parameters calculated deterministically by risk_math.py.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_reward_ratio: float = Field(
        ...,
        ge=0.0,
        description="Reward-to-Risk ratio (TP distance / SL distance)",
    )
    stop_loss_pips: float = Field(
        ...,
        ge=0.0,
        description="Distance from entry to stop loss in pips",
    )
    take_profit_pips: float = Field(
        ...,
        ge=0.0,
        description="Distance from entry to take profit in pips",
    )
    risk_capital_usd: float = Field(
        ...,
        ge=0.0,
        description="Total capital at risk for this trade in account currency",
    )
    max_loss_usd: float = Field(
        ...,
        ge=0.0,
        description="Maximum permissible dollar loss including worst-case slippage",
    )
    account_balance_usd: float = Field(
        ...,
        gt=0.0,
        description="Account balance snapshot used for lot sizing",
    )
    risk_per_trade_pct: float = Field(
        ...,
        gt=0.0,
        le=5.0,
        description="Account risk fraction capped at institutional limit (e.g. 1.0% - 2.0%)",
    )
    fractional_kelly_factor: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Fractional Kelly sizing scalar (Quarter-Kelly standard = 0.25)",
    )
    var_95_pct: float = Field(
        default=0.0,
        ge=0.0,
        description="Parametric 95% 1-day Value-at-Risk percentage",
    )


# =============================================================================
# MASTER CONTRACT: SIGNAL PAYLOAD (MQL5 DOUBLE-LOCK PROTOCOL)
# =============================================================================

class SignalPayload(BaseModel):
    """
    Strict institutional trade payload dispatched to MetaTrader 5 Expert Advisor
    via atomic IPC file exchange (SignalPayload.tmp -> SignalPayload.json).

    Law 4 Double-Lock Execution Guarantees:
    1. Lock 1: Time Expiration — Discarded if current UTC > expiration_timestamp_utc.
    2. Lock 2: Spread Guard — Discarded if current MT5 spread > max_allowed_spread_points.
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    signal_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique UUID for trade lifecycle tracking",
    )
    symbol: str = Field(
        ...,
        min_length=3,
        max_length=12,
        description="Financial instrument symbol (e.g. EURUSD, GBPUSD)",
    )
    action: OrderAction = Field(
        ...,
        description="Trade action: BUY, SELL, CLOSE, HOLD",
    )
    order_type: OrderType = Field(
        default=OrderType.MARKET,
        description="Order execution type: MARKET, LIMIT, STOP",
    )
    entry_price: float = Field(
        ...,
        gt=0.0,
        description="Proposed or limit entry price",
    )
    stop_loss: float = Field(
        ...,
        gt=0.0,
        description="Absolute stop loss price level",
    )
    take_profit: float = Field(
        ...,
        gt=0.0,
        description="Absolute take profit price level",
    )
    volume: float = Field(
        ...,
        gt=0.0,
        le=100.0,
        description="Calculated position lot size (fractional Kelly sizing)",
    )
    magic_number: int = Field(
        default=777001,
        ge=100000,
        le=999999,
        description="Unique MQL5 EA magic number identifier",
    )
    deviation_points: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Maximum permissible broker execution slippage in points",
    )
    max_allowed_spread_points: float = Field(
        default=25.0,
        gt=0.0,
        description="MQL5 Double-Lock: Max permissible spread in points at execution instant",
    )
    expiration_timestamp_utc: datetime = Field(
        ...,
        description="MQL5 Double-Lock: Expiration timestamp in UTC after which signal is void",
    )
    consensus_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Adversarial Consensus Score S_final",
    )
    execution_mode: ExecutionMode = Field(
        default_factory=lambda: ExecutionMode(EXECUTION_MODE),
        description="System mode: SHADOW (log only) or LIVE (execute on broker)",
    )
    regime_classification: RegimeClassification = Field(
        ...,
        description="Market regime evaluated by Alpha Agent and quant_core",
    )
    critic_veto_triggered: bool = Field(
        default=False,
        description="Adversarial critic veto status",
    )
    council_verdict: AgentCouncilVerdict = Field(
        ...,
        description="Complete breakdown of 4-Agent Adversarial Council evaluation",
    )
    risk_metrics: RiskMetrics = Field(
        ...,
        description="Mathematical risk and sizing parameters",
    )
    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Signal creation timestamp in UTC",
    )
    signature: str = Field(
        default="",
        description="HMAC-SHA256 signature sealing payload integrity",
    )

    # ── VALIDATORS ───────────────────────────────────────────────────────────

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Strip whitespace and enforce uppercase symbol format."""
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Symbol cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def validate_price_geometry(self) -> "SignalPayload":
        """
        Enforce geometric consistency between entry, stop loss, and take profit.
        """
        if self.action == OrderAction.BUY:
            if not (self.stop_loss < self.entry_price < self.take_profit):
                raise ValueError(
                    f"BUY geometry invalid: require stop_loss ({self.stop_loss}) < "
                    f"entry ({self.entry_price}) < take_profit ({self.take_profit})"
                )
        elif self.action == OrderAction.SELL:
            if not (self.stop_loss > self.entry_price > self.take_profit):
                raise ValueError(
                    f"SELL geometry invalid: require stop_loss ({self.stop_loss}) > "
                    f"entry ({self.entry_price}) > take_profit ({self.take_profit})"
                )
        return self

    @model_validator(mode="after")
    def validate_institutional_consensus_rules(self) -> "SignalPayload":
        """
        Enforce Law 2: Trade can ONLY be LIVE if S_final > 0.72 and critic_veto_triggered == False.
        """
        if self.action in (OrderAction.BUY, OrderAction.SELL):
            if self.critic_veto_triggered and self.execution_mode == ExecutionMode.LIVE:
                raise ValueError(
                    "Violation of Law 2: Cannot emit LIVE order when critic_veto_triggered is True."
                )
            if self.execution_mode == ExecutionMode.LIVE and self.consensus_score <= 0.72:
                raise ValueError(
                    f"Violation of Law 2: LIVE order requires consensus_score > 0.72. Got {self.consensus_score:.4f}"
                )
        return self

    @model_validator(mode="after")
    def validate_expiration_future(self) -> "SignalPayload":
        """Ensure expiration timestamp is in the future relative to creation."""
        created = self.created_at_utc
        if self.expiration_timestamp_utc <= created:
            raise ValueError(
                f"Expiration timestamp ({self.expiration_timestamp_utc.isoformat()}) must be later "
                f"than creation timestamp ({created.isoformat()})."
            )
        return self

    # ── HELPER METHODS ───────────────────────────────────────────────────────

    def is_expired(
        self,
        as_of: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Lock 1 Check: Evaluates whether this signal payload has exceeded its UTC lifetime.
        Accepts `as_of` or `current_time` as reference datetime (defaults to now UTC).
        """
        ref_time = as_of if as_of is not None else current_time
        now = ref_time or datetime.now(timezone.utc)
        if self.expiration_timestamp_utc.tzinfo is None:
            exp = self.expiration_timestamp_utc.replace(tzinfo=timezone.utc)
        else:
            exp = self.expiration_timestamp_utc
        return now > exp

    def is_spread_acceptable(self, current_spread_points: float) -> bool:
        """
        Lock 2 Check: Evaluates whether current broker spread violates maximum tolerance.
        """
        return current_spread_points <= self.max_allowed_spread_points

    def compute_canonical_hash(self) -> str:
        """
        Generates a deterministic SHA256 digest of core financial parameters.
        Used for payload tamper detection and HMAC signature generation.
        """
        canonical_str = (
            f"{self.signal_id}:{self.symbol}:{self.action.value}:{self.order_type.value}:"
            f"{self.entry_price:.6f}:{self.stop_loss:.6f}:{self.take_profit:.6f}:"
            f"{self.volume:.4f}:{self.magic_number}:{self.max_allowed_spread_points:.2f}:"
            f"{int(self.expiration_timestamp_utc.timestamp())}:{self.consensus_score:.4f}:"
            f"{self.execution_mode.value}"
        )
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def sign_payload(self, secret_key: str) -> str:
        """
        Seals the payload with an HMAC-SHA256 digital signature.
        """
        digest = self.compute_canonical_hash()
        sig = hmac.new(
            secret_key.encode("utf-8"),
            digest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.signature = sig
        return sig

    def verify_signature(self, secret_key: str) -> bool:
        """
        Verifies that payload signature matches expected HMAC-SHA256 digest.
        """
        if not self.signature:
            return False
        digest = self.compute_canonical_hash()
        expected = hmac.new(
            secret_key.encode("utf-8"),
            digest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.signature, expected)

    def to_mql5_dict(self) -> Dict[str, Any]:
        """
        Serializes payload into a clean format tailored for MQL5's JsonParser.mqh.
        Converts timestamps to integer UNIX epoch seconds and ensures standard field names.
        """
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "entry_price": round(self.entry_price, 5),
            "stop_loss": round(self.stop_loss, 5),
            "take_profit": round(self.take_profit, 5),
            "volume": round(self.volume, 2),
            "magic_number": self.magic_number,
            "deviation_points": self.deviation_points,
            "max_allowed_spread_points": round(self.max_allowed_spread_points, 1),
            "expiration_epoch_utc": int(self.expiration_timestamp_utc.timestamp()),
            "created_epoch_utc": int(self.created_at_utc.timestamp()),
            "consensus_score": round(self.consensus_score, 4),
            "execution_mode": self.execution_mode.value,
            "regime": self.regime_classification.value,
            "critic_veto": 1 if self.critic_veto_triggered else 0,
            "signature": self.signature,
        }

    def to_mql5_json(self, indent: Optional[int] = None) -> str:
        """
        Returns JSON string representation optimized for atomic IPC file delivery.
        """
        return json.dumps(self.to_mql5_dict(), indent=indent)


# =============================================================================
# INTER-AGENT MESSAGE SCHEMAS (4-AGENT ADVERSARIAL COUNCIL)
# =============================================================================

class AlphaRegimeMessage(BaseModel):
    """
    Message emitted by Agent 1 (Alpha Regime Gatekeeper).
    Provides quantitative regime analysis and macro alignment score (A_alpha).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    timeframe: str
    regime: RegimeClassification
    hurst_exponent: float
    variance_ratio: float
    atr_z_score: float
    hmm_probabilities: Dict[str, float]
    alignment_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Regime Alignment Score A_alpha in [0, 1]",
    )
    veto_active: bool = Field(
        ...,
        description="True if CHOPPY_RANDOM_WALK or HIGH_VOL_SHOCK triggered",
    )
    veto_reason: Optional[str] = None
    allowed_directions: List[str] = Field(default_factory=list)
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BetaSetupMessage(BaseModel):
    """
    Message emitted by Agent 2 (Beta OrderFlow Agent).
    Proposes institutional entry setup based on Smart Money Concepts (SMC) & Order Flow.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    timeframe: str
    action: OrderAction
    setup_type: str = Field(
        ...,
        description="SMC setup pattern (e.g. ORDER_BLOCK_RETEST, FVG_EXPANSION, LIQUIDITY_SWEEP)",
    )
    entry_price: float = Field(..., gt=0.0)
    stop_loss: float = Field(..., gt=0.0)
    take_profit: float = Field(..., gt=0.0)
    setup_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Beta Setup Confidence C_beta in [0, 1]",
    )
    smc_confluence_factors: List[str] = Field(
        default_factory=list,
        description="Identified institutional footprints (e.g. ['OB_M15', 'FVG_H1', 'SSL_SWEEP'])",
    )
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GammaCriticMessage(BaseModel):
    """
    Message emitted by Agent 3 (Gamma RedTeam Critic).
    Performs adversarial interrogation of Beta's proposal to uncover traps and calculate P_gamma.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str = Field(..., description="Target BetaSetupMessage ID being critiqued")
    failure_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Gamma Failure Probability P_gamma in [0, 1]",
    )
    critic_veto: bool = Field(
        ...,
        description="Hard veto raised if high-impact trap or conflict detected",
    )
    traps_detected: List[str] = Field(
        default_factory=list,
        description="Identified traps (e.g. ['INDUCEMENT_LIQUIDITY_TRAP', 'HTF_FLOW_CONFLICT'])",
    )
    adversarial_critique: str = Field(
        ...,
        min_length=10,
        description="Detailed adversarial reasoning explaining identified vulnerabilities",
    )
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OmegaGovernorVerdict(BaseModel):
    """
    Message emitted by Agent 4 (Omega Risk Governor).
    Evaluates adversarial synthesis, solves Kelly lot sizing, and signs execution payload.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    symbol: str
    consensus_score: float = Field(
        ...,
        description="Computed S_final = (C_beta * A_alpha) - P_gamma",
    )
    is_approved: bool = Field(
        ...,
        description="True if consensus_score > 0.72 and critic_veto is False",
    )
    execution_mode: ExecutionMode
    allocated_lot_size: float = Field(..., ge=0.0, le=100.0)
    governor_notes: str = Field(..., min_length=5)
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionReceipt(BaseModel):
    """
    Receipt returned from MQL5 Hot Path or bridge after execution attempt.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str
    symbol: str
    order_ticket: Optional[int] = None
    status: Literal[
        "EXECUTED",
        "REJECTED",
        "EXPIRED",
        "SPREAD_VIOLATION",
        "SLIPPAGE_VIOLATION",
        "SHADOW_LOGGED",
    ]
    executed_price: Optional[float] = None
    executed_volume: Optional[float] = None
    spread_at_execution_points: float = 0.0
    slippage_points: float = 0.0
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# FACTORY BUILDER FUNCTION
# =============================================================================

def build_signal_payload(
    symbol: str,
    action: OrderAction,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    volume: float,
    alpha_score: float,
    beta_confidence: float,
    gamma_prob: float,
    critic_veto: bool,
    regime: RegimeClassification,
    risk_metrics: RiskMetrics,
    validity_duration_seconds: int = 120,
    max_allowed_spread_points: float = 25.0,
    magic_number: int = 777001,
    deviation_points: int = 10,
    execution_mode: Optional[ExecutionMode] = None,
    secret_key: Optional[str] = None,
    rationale: str = "4-Agent Adversarial Consensus achieved.",
) -> SignalPayload:
    """
    Institutional helper factory to assemble, compute consensus score,
    validate, and digitally sign a complete SignalPayload instance.
    """
    mode = execution_mode or ExecutionMode(EXECUTION_MODE)
    consensus_score = (beta_confidence * alpha_score) - gamma_prob

    if critic_veto or consensus_score <= 0.72:
        verdict_status = "VETOED" if mode == ExecutionMode.LIVE else "SHADOW_APPROVED"
    else:
        verdict_status = "APPROVED" if mode == ExecutionMode.LIVE else "SHADOW_APPROVED"

    council_verdict = AgentCouncilVerdict(
        alpha_regime_score=alpha_score,
        beta_setup_confidence=beta_confidence,
        gamma_failure_probability=gamma_prob,
        omega_consensus_score=consensus_score,
        critic_veto_triggered=critic_veto,
        verdict_status=verdict_status,
        rationale=rationale,
    )

    now = datetime.now(timezone.utc)
    expiration = datetime.fromtimestamp(now.timestamp() + validity_duration_seconds, tz=timezone.utc)

    payload = SignalPayload(
        symbol=symbol,
        action=action,
        order_type=OrderType.MARKET,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume,
        magic_number=magic_number,
        deviation_points=deviation_points,
        max_allowed_spread_points=max_allowed_spread_points,
        expiration_timestamp_utc=expiration,
        consensus_score=consensus_score,
        execution_mode=mode,
        regime_classification=regime,
        critic_veto_triggered=critic_veto,
        council_verdict=council_verdict,
        risk_metrics=risk_metrics,
        created_at_utc=now,
    )

    if secret_key:
        payload.sign_payload(secret_key)

    return payload
