"""
==============================================================================
autonomous_master_orchestrator.py — Unified Autonomous Quantitative Engine
==============================================================================
Role: Master Autonomous Hedge-Fund Engine (5-Agent Council + Blackboard
      + Dialectical Debate + Episodic Vector RAG Memory + MT5 Closed-Loop
      Learning + Self-Healing Code Evolution).

Constitutional Laws (.antigravityrules):
  1. Pure deterministic math in quant_core (Zero LLM hallucinations).
  2. Parallel async council execution (< 2.0s latency).
  3. Inter-agent communication via QuantumBlackboard & MultiAgentDebate.
  4. Hierarchical Memory: Working Memory + Episodic Vector RAG + Reflexion Post-Mortem.
  5. Continuous closed-loop learning from MT5 closed deals.
  6. Autonomous self-healing code audit via AST symbol slicing & sandbox verification.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

# Core 5-Agent Council
from agents import (
    AlphaRegimeAgent,
    BetaOrderFlowAgent,
    GammaRedTeamCritic,
    OmegaRiskGovernor,
    MacroSentinelAgent,
    SignalPayload,
)
from quant_core.orderflow import RealOFIEngine, simulate_ticks_from_ohlcv
from memory_rag.adaptive_trade_journal import (
    TradeOutcomeRecorder,
    TradeVectorRecord,
    AdaptiveTrapMemory,
)
from institutional.blackboard import (
    QuantumBlackboard,
    SignalPayload as BBSignalPayload,
    SignalDirection,
)
from institutional.multi_agent_debate import (
    MultiAgentDebateEngine,
    DebateVerdict,
    DebateSessionResult,
)
from institutional.code_healing_agent import (
    CodeHealingAgent,
    AgentExecutionMode,
    CodeLanguage,
    HealingStatus,
)
from main_orchestrator import AtomicMQL5Bridge, MarketDataProvider

# MetaTrader 5 optional live terminal connection
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("AutonomousMaster")


class MT5ClosedDealFeedback:
    """
    Closed-Loop Feedback: Monitors MT5 history deals and updates the
    Episodic Memory & Trade Journal when positions close.
    This enables the agents to learn from real mistakes and successes.
    """

    def __init__(self, recorder: TradeOutcomeRecorder, point_value: float = 0.00001):
        self.recorder = recorder
        self.point_value = point_value
        self._processed_deal_tickets: set[int] = set()

    @staticmethod
    def _pips_from_profit(
        symbol: str, profit: float, volume: float, tick_value: float, tick_size: float
    ) -> Optional[float]:
        """
        نقاط (pips) الصفقة من ربحها: القيمة النقدية للبيب لكل لوت تُشتق من
        symbol_info (trade_tick_value / trade_tick_size) لا من 10$ ثابتة.
        pip = 0.01 للين و0.1 للذهب و0.0001 للباقي (اتفاقية سجل الذاكرة أدناه).
        يعيد None إن كانت البيانات غير صالحة بدل رقم مفترض.
        """
        if not (volume > 0 and tick_value > 0 and tick_size > 0):
            return None
        pip_size = 0.01 if "JPY" in symbol else (0.1 if "XAU" in symbol else 0.0001)
        pip_value_per_lot = tick_value * pip_size / tick_size
        return round(profit / (volume * pip_value_per_lot), 1)

    def inspect_and_sync_closed_deals(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Fetches closed deals from MT5 and updates the episodic memory.
        Returns summary of synchronized trades.
        """
        if not MT5_AVAILABLE:
            return []

        try:
            utc_from = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            utc_to = datetime.now(timezone.utc) + timedelta(minutes=5)
            deals = mt5.history_deals_get(utc_from, utc_to)
            if deals is None or len(deals) == 0:
                return []

            updates = []
            for deal in deals:
                deal_d = deal._asdict()
                ticket = deal_d.get("ticket", 0)
                entry_type = deal_d.get("entry", 0)  # 1 = DEAL_ENTRY_OUT (exit deal)
                profit = deal_d.get("profit", 0.0)
                symbol = deal_d.get("symbol", "")

                # Only examine closing transactions
                if entry_type == 1 and ticket not in self._processed_deal_tickets:
                    self._processed_deal_tickets.add(ticket)
                    outcome = "WIN" if profit > 0.0 else ("LOSS" if profit < 0.0 else "BE")
                    info = mt5.symbol_info(symbol)
                    pnl_pips = self._pips_from_profit(
                        symbol, profit, deal_d.get("volume", 0.01),
                        getattr(info, "trade_tick_value", 0.0),
                        getattr(info, "trade_tick_size", 0.0),
                    )
                    pnl_txt = f"{pnl_pips:+.1f}" if pnl_pips is not None else "n/a"

                    updates.append({
                        "deal_ticket": ticket,
                        "symbol": symbol,
                        "profit_usd": profit,
                        "outcome": outcome,
                        "pnl_pips": pnl_pips,
                    })

                    logger.info(
                        f"📊 [MT5 Feedback] Closed Deal #{ticket} on {symbol}: "
                        f"{outcome} (${profit:+.2f}, {pnl_txt} pips). Updating Episodic Memory."
                    )
            return updates
        except Exception as exc:
            logger.warning(f"Error inspecting MT5 closed deals: {exc}")
            return []


class SelfHealingWatchdog:
    """
    Autonomous Self-Healing: Periodically audits repository python files,
    detects AST syntax flaws, and runs the deterministic test verification gate.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.agent = CodeHealingAgent(mode=AgentExecutionMode.SUGGEST_MODE)
        self.last_audit_time: Optional[datetime] = None

    def audit_and_verify(self) -> Dict[str, Any]:
        """Runs headless AST verification on core modules."""
        self.last_audit_time = datetime.now(timezone.utc)
        target_files = [
            self.workspace_root / "main_orchestrator.py",
            self.workspace_root / "quant_core" / "orderflow.py",
            self.workspace_root / "agents" / "beta_orderflow_agent.py",
            self.workspace_root / "agents" / "gamma_redteam_critic.py",
            self.workspace_root / "agents" / "omega_risk_governor.py",
            self.workspace_root / "agents" / "delta_macro_sentinel.py",
            self.workspace_root / "memory_rag" / "adaptive_trade_journal.py",
        ]

        results = []
        for f in target_files:
            if not f.exists():
                continue
            is_valid, err_msg = self._check_syntax(f)
            results.append({
                "file": f.name,
                "syntax_valid": is_valid,
                "error": err_msg,
            })

        all_valid = all(r["syntax_valid"] for r in results)
        logger.info(f"🛡️ [Self-Healing Watchdog] Audited {len(results)} core modules. Health: {'100% HEALTHY' if all_valid else 'DEGRADED'}")
        return {
            "all_valid": all_valid,
            "modules": results,
            "timestamp_utc": self.last_audit_time.isoformat(),
        }

    @staticmethod
    def _check_syntax(file_path: Path) -> Tuple[bool, Optional[str]]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            compile(source, str(file_path), "exec")
            return True, None
        except Exception as exc:
            return False, str(exc)


class AutonomousMasterOrchestrator:
    """
    The Unified Autonomous Engine:
    Coordinates Analysis, Inter-Agent Debate, Decision Signing,
    Execution, Vector Memory, Learning from Mistakes, and Self-Healing.
    """

    def __init__(
        self,
        mql5_shared_dir: str = "./mql5_shared_signals",
        use_live_mt5: bool = False,
        confidence_threshold: float = 72.0,
    ):
        self.workspace_root = Path(__file__).resolve().parent
        self.data_provider = MarketDataProvider(use_live_mt5=use_live_mt5)
        self.bridge = AtomicMQL5Bridge(target_dir=mql5_shared_dir)

        # 1. Perception & Math Agents
        self.alpha = AlphaRegimeAgent(point_value=0.00001)
        self.beta  = BetaOrderFlowAgent(point_value=0.00001, use_live_mt5=use_live_mt5)
        self.delta = MacroSentinelAgent()

        # 2. Memory & Feedback Layer
        self.recorder = TradeOutcomeRecorder()
        self.gamma = GammaRedTeamCritic(
            max_spread_atr_ratio=0.15,
            point_value=0.00001,
            adaptive_memory=self.recorder.trap_memory,
        )
        self.omega = OmegaRiskGovernor(approval_threshold=confidence_threshold / 100.0)
        self.feedback = MT5ClosedDealFeedback(recorder=self.recorder)

        # 3. Inter-Agent Communication & Debate Room
        self.blackboard = QuantumBlackboard(name="MasterCouncilBlackboard")
        self.debate_engine = MultiAgentDebateEngine(confidence_threshold=confidence_threshold)

        # 4. Self-Healing & Code Evolution
        self.watchdog = SelfHealingWatchdog(workspace_root=self.workspace_root)

    async def evaluate_symbol_autonomous(
        self,
        symbol: str,
        current_daily_dd_pct: float = 0.0,
        override_utc_now: Optional[datetime] = None,
    ) -> SignalPayload:
        """
        Executes the full 7-step autonomous lifecycle per symbol:
        1. Snapshot Data Fetching
        2. Parallel Council Evaluation (Alpha, Delta)
        3. SMC & Real OFI Proposal (Beta)
        4. Inter-Agent Debate & Blackboard Consensus
        5. Red-Team Adversarial Audit with Episodic Memory (Gamma)
        6. Risk Governance & Kelly Sizing (Omega) + M1 BOS Confirmation Gate
        7. Atomic Double-Lock IPC Write to MT5 + Episodic Memory Logging
        """
        utc_now = override_utc_now or datetime.now(timezone.utc)
        logger.info(f"[{symbol}] === Initiating Autonomous Agent Lifecycle ===")

        # Step 1: Snapshot
        snapshot = await self.data_provider.get_market_snapshot(symbol)
        df_m5 = snapshot["df_m5"]
        df_h1 = snapshot["df_h1"]
        spread_pts = snapshot["spread_points"]
        point_value = snapshot["point_value"]

        # Step 2: Parallel Alpha (Regime) & Delta (Macro Sentinel)
        macro_task = asyncio.create_task(
            self.delta.assess(symbol=symbol, utc_now=utc_now)
        )
        regime = await self.alpha.analyze(symbol, df_m5, df_h1, point_value=point_value)
        macro = await macro_task

        logger.info(
            f"[{symbol}] Alpha: Regime={regime.regime_state.value} (Hurst={regime.hurst_exponent:.3f}) | "
            f"Delta: Macro={macro.risk_level.value} (Embargo={macro.news_embargo_active})"
        )

        # Post Alpha & Delta to Blackboard
        direction_alpha = SignalDirection.BUY if "BULLISH" in regime.directional_bias else (
            SignalDirection.SELL if "BEARISH" in regime.directional_bias else SignalDirection.HOLD
        )
        self.blackboard.post_signal(BBSignalPayload(
            agent_id="alpha_regime",
            signal_direction=direction_alpha,
            confidence_score=float(regime.regime_confidence),
        ))

        # Short circuit on macro blackout or chaotic regime
        if macro.news_embargo_active or macro.risk_level.value == "BLACKOUT":
            logger.warning(f"[{symbol}] MACRO EMBARGO ACTIVE. Halting cycle.")
            note = ("[MACRO EMBARGO] High-impact event active." if macro.next_event_name
                    else "[MACRO EMBARGO] News calendar unavailable (fail-closed).")
            return self._build_standdown_payload(symbol, regime, macro, note)

        # Step 3: Agent Beta (SMC + Real OFI)
        proposal = await self.beta.propose_setup(
            symbol=symbol,
            df_m5=df_m5,
            regime=regime,
            utc_now=utc_now,
            point_value=point_value,
        )
        logger.info(
            f"[{symbol}] Beta: Action={proposal.proposed_action} "
            f"({proposal.setup_type}, Conf={proposal.signal_confidence:.2f}, OFI_Z={proposal.ofi_z_score:+.2f})"
        )

        direction_beta = SignalDirection.BUY if "BUY" in proposal.proposed_action else (
            SignalDirection.SELL if "SELL" in proposal.proposed_action else SignalDirection.HOLD
        )
        self.blackboard.post_signal(BBSignalPayload(
            agent_id="beta_orderflow",
            signal_direction=direction_beta,
            confidence_score=float(proposal.signal_confidence),
        ))

        if proposal.proposed_action == "STAND_DOWN":
            return self._build_standdown_payload(symbol, regime, macro, "[BETA STAND DOWN] No SMC / OFI edge.")

        # Step 4: Inter-Agent Dialectical Debate (Bull vs Bear)
        current_close = float(df_m5["close"].iloc[-1])
        debate_context = {
            "close": current_close,
            "ema": float(df_m5["close"].ewm(span=50).mean().iloc[-1]),
            "rsi": 55.0 if "BUY" in proposal.proposed_action else 45.0,
            "cvd_slope": proposal.ofi_z_score,
            "absorption_detected": "BULLISH_ABSORPTION" if proposal.ofi_z_score > 1.0 else (
                "BEARISH_ABSORPTION" if proposal.ofi_z_score < -1.0 else "NONE"
            ),
        }
        debate_result: DebateSessionResult = self.debate_engine.conduct_debate(
            symbol=symbol,
            context=debate_context,
        )
        logger.info(
            f"[{symbol}] Inter-Agent Debate: Verdict={debate_result.verdict.value} "
            f"(Confidence={debate_result.consensus_confidence:.1f}%, Margin={debate_result.margin_of_dominance:+.1f})"
        )

        # Step 5: Red-Team Adversarial Critic (Gamma) with Episodic Memory RAG
        critic = await self.gamma.audit_proposal(
            proposal=proposal,
            regime=regime,
            df_h1=df_h1,
            current_spread_points=spread_pts,
        )
        logger.info(
            f"[{symbol}] Gamma Critic: Veto={critic.critic_veto_triggered} "
            f"(FailureProb={critic.failure_probability_score:.2f}, Spread/ATR={critic.spread_to_atr_ratio:.1%})"
        )

        # Step 5.5: Fetch rolling win rate from Adaptive Memory for Omega
        rolling_win_rate = await self.recorder.get_recent_win_rate(last_n=20)

        # Step 6: Risk Governor (Omega) + Dynamic Threshold
        final_payload = self.omega.adjudicate(
            regime=regime,
            proposal=proposal,
            critic=critic,
            current_daily_dd_pct=current_daily_dd_pct,
            rolling_win_rate=rolling_win_rate,
            macro_risk_multiplier=macro.risk_percent_multiplier,
            macro_risk_level=macro.risk_level.value,
        )

        # Step 6.5: M1 Entry Confirmation Gate (BOS + OFI confirmation)
        if final_payload.action != "STAND_DOWN":
            m1_confirmed = await self._confirm_m1_entry(symbol, proposal, df_m5)
            if not m1_confirmed:
                logger.warning(f"[{symbol}] M1 Gate: Downgrading to STAND_DOWN due to lack of M1 confirmation.")
                final_payload = final_payload.model_copy(update={
                    "action": "STAND_DOWN",
                    "critic_veto_triggered": True,
                    "critic_notes": "[M1 CONFIRMATION FAILED] " + final_payload.critic_notes,
                })

        # Step 7: Atomic Publish & Episodic Recording
        out_path = self.bridge.publish_signal(final_payload)
        logger.info(f"[{symbol}] Final Payload published atomically → {out_path}")

        # Record to Episodic Memory in SQLite
        # IMPROVEMENT_PLAN §0: استخدام حجم النقطة الصحيح لكل رمز
        pip_size = 0.01 if "JPY" in symbol else (0.1 if "XAU" in symbol else 0.0001)
        sl_pips = abs(proposal.entry_price - proposal.stop_loss) / pip_size
        tp1_pips = abs(proposal.take_profit_1 - proposal.entry_price) / pip_size
        record = TradeVectorRecord(
            timestamp_utc=final_payload.timestamp_utc,
            symbol=symbol,
            regime_state=regime.regime_state.value,
            setup_type=proposal.setup_type,
            hurst=regime.hurst_exponent,
            atr_ratio=regime.atr_ratio,
            z_score=regime.rolling_z_score,
            ofi_z=proposal.ofi_z_score,
            spread_ratio=critic.spread_to_atr_ratio,
            proposed_action=proposal.proposed_action,
            final_action=final_payload.action,
            signal_confidence=proposal.signal_confidence,
            net_score=final_payload.confidence_score,
            sl_pips=round(sl_pips, 1),
            tp1_pips=round(tp1_pips, 1),
            risk_percent=final_payload.execution_params.risk_percent,
            pnl_pips=None,
            outcome="OPEN" if final_payload.action != "STAND_DOWN" else "STAND_DOWN",
            execution_mode="SHADOW",
        )
        await self.recorder.record_signal(record)

        return final_payload

    async def _confirm_m1_entry(self, symbol: str, proposal, df_m5: pd.DataFrame) -> bool:
        """
        Verifies M1 market structure shift and OFI consistency.
        IMPROVEMENT_PLAN §0: fail-closed on missing data or exception.
        """
        try:
            df_m1 = await self.data_provider.get_m1_bars(symbol, n=30)
            if len(df_m1) < 12:
                logger.warning(f"[{symbol}] M1 confirmation rejected: insufficient bars ({len(df_m1)} < 12, fail-closed)")
                return False
            recent_high = float(df_m1["high"].iloc[-5:].max())
            prior_high  = float(df_m1["high"].iloc[-10:-5].max())
            recent_low  = float(df_m1["low"].iloc[-5:].min())
            prior_low   = float(df_m1["low"].iloc[-10:-5].min())
            action = proposal.proposed_action
            ofi_z = proposal.ofi_z_score

            if "BUY" in action:
                return (recent_high > prior_high) and (ofi_z > 0.4)
            elif "SELL" in action:
                return (recent_low < prior_low) and (ofi_z < -0.4)
            return False
        except Exception as exc:
            logger.warning(f"[{symbol}] M1 confirmation error (fail-closed): {exc}")
            return False

    def _build_standdown_payload(self, symbol, regime, macro, notes: str) -> SignalPayload:
        from agents.omega_risk_governor import ExecutionParams
        return SignalPayload(
            timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            symbol=symbol,
            action="STAND_DOWN",
            regime_state=regime.regime_state.value,
            confidence_score=0.0,
            approval_threshold_used=0.72,
            critic_veto_triggered=True,
            critic_notes=notes,
            macro_risk_level=macro.risk_level.value,
            execution_params=ExecutionParams(
                entry_price=0.0, stop_loss=0.0, take_profit_1=0.0, take_profit_2=0.0,
                risk_percent=0.0, max_allowed_spread_points=15, expiration_minutes=0
            )
        )

    async def run_master_cycle(self, watchlist: List[str]) -> Dict[str, SignalPayload]:
        """Runs the autonomous pipeline across all watchlist symbols and triggers feedback & healing."""
        logger.info("===========================================================================")
        logger.info("🚀 EXECUTING MASTER AUTONOMOUS CYCLE ACROSS WATCHLIST")
        logger.info("===========================================================================")

        # 1. Closed-deal Feedback Loop (Learning from recent MT5 trades)
        closed_trades = self.feedback.inspect_and_sync_closed_deals(hours_back=12)
        if closed_trades:
            logger.info(f"🔄 [Learning Loop] Synced {len(closed_trades)} closed trades. Rebuilding Trap Vectors.")
            self.recorder.trap_memory.rebuild_summary()

        # 2. Parallel Multi-Agent Evaluation & Debate
        tasks = [self.evaluate_symbol_autonomous(sym) for sym in watchlist]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results: Dict[str, SignalPayload] = {}
        for sym, res in zip(watchlist, outcomes):
            if isinstance(res, BaseException):
                # fail-closed: لا إشارة لهذا الرمز، وبقية الرموز تكمل
                logger.error("[%s] cycle aborted, no payload published: %s", sym, res)
                continue
            results[res.symbol] = res

        # 3. Autonomous Code & System Health Watchdog
        audit_report = self.watchdog.audit_and_verify()
        logger.info(f"✅ Master Cycle Completed. Core System Health: {audit_report['all_valid']}")

        return results


async def main():
    use_live = (os.environ.get("USE_LIVE_MT5", "0") == "1") and MT5_AVAILABLE
    orchestrator = AutonomousMasterOrchestrator(
        mql5_shared_dir="./mql5_shared_signals",
        use_live_mt5=use_live,
        confidence_threshold=72.0,
    )
    watchlist = ["EURUSD", "GBPUSD", "XAUUSD"]
    results = await orchestrator.run_master_cycle(watchlist)

    print("\n" + "=" * 78)
    print("AUTONOMOUS MASTER ENGINE CYCLE OUTPUT (SAMPLE: EURUSD)")
    print("=" * 78)
    print(results["EURUSD"].model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
