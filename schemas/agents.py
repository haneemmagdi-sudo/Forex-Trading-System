"""
schemas/agents.py — Pydantic Schemas for Multi-Agent Trading System.
Provides strongly-typed schemas for Strategy Proposals, Risk Verdicts,
and Execution Receipts.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class StrategyProposal(BaseModel):
    """Trading strategy proposal emitted by Analyst or Planner agents."""
    strategy_id: str = Field(..., description="Unique strategy proposal identifier")
    asset_class: Literal["FOREX", "EQUITY", "CRYPTO"] = Field(default="FOREX")
    symbol: str = Field(..., description="Trading pair or ticker, e.g. EURUSD")
    action: Literal["BUY", "SELL", "HOLD", "CLOSE", "LONG", "SHORT"] = Field(...)
    quantity: float = Field(default=0.01, description="Lot size or share quantity")
    entry_price: float = Field(..., description="Proposed entry price")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price level")
    take_profit: Optional[float] = Field(default=None, description="Take profit price level")
    timeframe: str = Field(default="H1", description="Candle timeframe, e.g. M15, H1, H4")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Conviction score")
    llm_provider: str = Field(default="system", description="Provider that generated this signal")
    rationale: Optional[str] = Field(default=None, description="Reasoning narrative")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── حقول المخاطرة/التخطيط التي يقرأها Risk Manager و CEO ──────────
    # (كانت تُمرَّر كوسائط فيُسقطها pydantic بصمت أو تُقرأ فترفع AttributeError)
    risk_reward_ratio: float = Field(default=0.0, description="Reward-to-risk ratio")
    stop_loss_pips: float = Field(default=0.0)
    take_profit_pips: float = Field(default=0.0)
    max_capital_at_risk: float = Field(default=0.0)
    max_loss_usd: float = Field(default=0.0)
    max_profit_usd: float = Field(default=0.0)
    lot_type: Optional[str] = Field(default=None, description="STANDARD / MINI / MICRO")
    strategy_type: Optional[str] = Field(default=None)
    confidence_score: Optional[float] = Field(default=None)
    pre_news_clearance: bool = Field(default=False)
    session: Optional[str] = Field(default=None)
    revision_round: int = Field(default=0)


class RiskVerdict(BaseModel):
    """Validation decision emitted by the Risk Manager."""
    strategy_id: str
    asset_class: str = "FOREX"
    verdict: Literal["APPROVED", "VETOED", "MODIFIED", "CONDITIONAL"] = "APPROVED"
    rule_violations: List[str] = Field(default_factory=list)
    risk_score: float = Field(default=1.0, description="Risk assessment score 0-10")
    veto_reason: Optional[str] = None
    llm_provider: str = "risk_rules"
    adjusted_quantity: Optional[float] = None
    max_allowable_quantity: Optional[float] = Field(
        default=None, description="أقصى كمية يسمح بها مدير المخاطر"
    )
    risk_manager_commentary: str = Field(default="", description="تعليق مدير المخاطر")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionReceipt(BaseModel):
    """Proof of trade execution returned by the Execution Agent."""
    trade_id: str
    strategy_id: str
    asset_class: str = "FOREX"
    symbol: str
    action: str
    quantity: float
    requested_price: float
    executed_price: float
    slippage: float = 0.0
    total_cost: Optional[float] = None
    status: Literal["EXECUTED", "REJECTED", "SIMULATED", "FAILED"] = "EXECUTED"
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CEODecision(BaseModel):
    """
    القرار النهائي لوكيل المدير التنفيذي على مقترح استراتيجية.
    يستهلكه Strategy Planner ليعرف إن كان المقترح مقبولاً وما التعليمات المرفقة.
    """
    decision: Literal["APPROVED", "REJECTED", "REVISION_REQUESTED"] = "REJECTED"
    market: Optional[str] = None
    reasoning: str = ""
    instructions_to_planner: str = ""
    capital_allocation: Dict[str, float] = Field(default_factory=dict)
    revision_round: int = 0
    llm_provider: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
