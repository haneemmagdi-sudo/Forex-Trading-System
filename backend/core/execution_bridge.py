"""
==============================================================================
backend/core/execution_bridge.py — Low-Latency Hybrid Execution Bridge
==============================================================================
Module  : Low-Latency Bridge (ZeroMQ / Webhooks / Shared Memory IPC)
Author  : Principal Quantitative AI Architect & Systems Architect
Version : 5.0.0 Institutional
Reference: Chapter 14 / Institutional Multi-Agent Systems (MAS)

Overview:
---------
Connects external real-time signal sources (TradingView Pine Script Webhooks)
and ultra-low latency execution engines (MetaTrader 5 MQL5 via ZeroMQ / IPC)
with the core Institutional Multi-Agent brain.

Flow:
1. Pine Script Webhook / Market Tick arrives.
2. MarketRegimeAgent evaluates Macro HMM Veto.
3. OrderFlowMicrostructureAgent evaluates CVD and Absorption.
4. CrossAssetGraphAgent evaluates global yield/dollar flows.
5. MultiAgentDebateEngine runs Bullish vs Bearish debate.
6. If consensus exceeds 75% threshold -> Dispatches instant execution mandate
   via ZeroMQ / MT5 API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple

from agents.market_regime_hmm import MarketRegimeAgent, MarketRegimeState
from agents.order_flow_agent import OrderFlowMicrostructureAgent
from agents.multi_agent_debate import MultiAgentDebateEngine, DebateVerdict
from ml_models.cross_asset_agent import CrossAssetGraphAgent, MacroFlowMetrics

logger = logging.getLogger("institutional_mas.execution_bridge")


@dataclass
class BridgeExecutionReceipt:
    symbol: str
    action: str
    approved: bool
    rejection_stage: Optional[str] = None
    rejection_reason: Optional[str] = None
    consensus_confidence: float = 0.0
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class InstitutionalExecutionBridge:
    """
    Unified Low-Latency Execution Pipeline combining all institutional MAS layers.
    """

    def __init__(self, confidence_threshold: float = 75.0):
        self.regime_agent = MarketRegimeAgent()
        self.order_flow_agent = OrderFlowMicrostructureAgent()
        self.debate_engine = MultiAgentDebateEngine(confidence_threshold=confidence_threshold)
        self.cross_asset_agent = CrossAssetGraphAgent()

    def process_entry_candidate(
        self,
        symbol: str,
        proposed_action: str,  # "BUY" or "SELL"
        price_series: Dict[str, list],  # opens, highs, lows, closes, volumes
        macro_inputs: Optional[Dict[str, float]] = None,
        technical_indicators: Optional[Dict[str, float]] = None,
    ) -> BridgeExecutionReceipt:
        """
        Executes the hierarchical 5-stage institutional filtering cascade.
        Target pipeline latency: < 5ms.
        """
        start_ns = time.perf_counter_ns()
        closes = price_series.get("closes", [])
        highs = price_series.get("highs", [])
        lows = price_series.get("lows", [])
        opens = price_series.get("opens", closes)
        volumes = price_series.get("volumes", [100.0] * len(closes))

        # -------------------------------------------------------------
        # STAGE 1: Market Regime Agent (HMM Macro Veto)
        # -------------------------------------------------------------
        atr_cur = technical_indicators.get("atr", 0.0015) if technical_indicators else 0.0015
        regime_result = self.regime_agent.classify(
            symbol=symbol,
            closes=closes,
            highs=highs,
            lows=lows,
            atr_current=atr_cur,
            atr_baseline=0.0015,
        )

        is_vetoed, veto_msg = self.regime_agent.evaluate_macro_veto(symbol, proposed_action, regime_result)
        if is_vetoed:
            latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            return BridgeExecutionReceipt(
                symbol=symbol,
                action=proposed_action,
                approved=False,
                rejection_stage="STAGE_1_REGIME_VETO",
                rejection_reason=veto_msg,
                latency_ms=round(latency_ms, 2),
                details={"regime": regime_result.state.value},
            )

        # -------------------------------------------------------------
        # STAGE 2: Microstructure & Order Flow Agent (CVD & Absorption)
        # -------------------------------------------------------------
        of_result = self.order_flow_agent.validate_setup(
            symbol=symbol,
            proposed_action=proposed_action,
            closes=closes,
            opens=opens,
            highs=highs,
            lows=lows,
            volumes=volumes,
        )

        if not of_result.is_valid_entry:
            latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            return BridgeExecutionReceipt(
                symbol=symbol,
                action=proposed_action,
                approved=False,
                rejection_stage="STAGE_2_ORDER_FLOW_VETO",
                rejection_reason=of_result.veto_reason,
                latency_ms=round(latency_ms, 2),
                details={
                    "cvd_slope": of_result.cvd_slope,
                    "cvd_divergence": of_result.cvd_divergence,
                    "absorption": of_result.absorption_detected.value,
                },
            )

        # -------------------------------------------------------------
        # STAGE 3: Cross-Asset Capital Flow Agent
        # -------------------------------------------------------------
        if macro_inputs is None:
            macro_inputs = {"dxy_change": 0.0, "us10y_change": 0.0, "vix": 16.0, "gold_change": 0.0}

        macro_flow = self.cross_asset_agent.evaluate_intermarket_state(
            dxy_change_pct=macro_inputs.get("dxy_change", 0.0),
            us10y_change_pct=macro_inputs.get("us10y_change", 0.0),
            vix_level=macro_inputs.get("vix", 16.0),
            gold_change_pct=macro_inputs.get("gold_change", 0.0),
        )

        cross_result = self.cross_asset_agent.validate_pair_alignment(symbol, proposed_action, macro_flow)
        if cross_result.veto_recommended:
            latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            return BridgeExecutionReceipt(
                symbol=symbol,
                action=proposed_action,
                approved=False,
                rejection_stage="STAGE_3_CROSS_ASSET_VETO",
                rejection_reason=cross_result.rationale,
                latency_ms=round(latency_ms, 2),
            )

        # -------------------------------------------------------------
        # STAGE 4: Multi-Agent Debate (MAD) Engine
        # -------------------------------------------------------------
        debate_context = {
            "close": closes[-1] if closes else 0.0,
            "ema": technical_indicators.get("ema", closes[-1]) if technical_indicators else closes[-1],
            "rsi": technical_indicators.get("rsi", 50.0) if technical_indicators else 50.0,
            "atr": atr_cur,
            "regime": regime_result.state.value,
            "absorption_detected": of_result.absorption_detected.value,
            "sweep_direction": of_result.sweep_direction,
            "spread": technical_indicators.get("spread", 10.0) if technical_indicators else 10.0,
        }

        debate_result = self.debate_engine.conduct_debate(symbol, debate_context)
        if not debate_result.execution_permitted:
            latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            return BridgeExecutionReceipt(
                symbol=symbol,
                action=proposed_action,
                approved=False,
                rejection_stage="STAGE_4_DEBATE_REJECTION",
                rejection_reason=debate_result.synthesis_rationale,
                consensus_confidence=debate_result.consensus_confidence,
                latency_ms=round(latency_ms, 2),
            )

        # -------------------------------------------------------------
        # STAGE 5: All Institutional Gates Cleared -> Approve Execution
        # -------------------------------------------------------------
        latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        return BridgeExecutionReceipt(
            symbol=symbol,
            action=proposed_action,
            approved=True,
            consensus_confidence=debate_result.consensus_confidence,
            latency_ms=round(latency_ms, 2),
            details={
                "regime": regime_result.state.value,
                "cvd_divergence": of_result.cvd_divergence,
                "absorption": of_result.absorption_detected.value,
                "macro_alignment": cross_result.macro_alignment_score,
                "debate_rationale": debate_result.synthesis_rationale,
            },
        )
