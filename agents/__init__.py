"""Agents package — Quantum FSM Pro V4.2 Elite.

Sub-modules
-----------
blackboard       : QuantumBlackboard (centralized shared memory layer)
consensus_engine : ConsensusEngine   (mathematical aggregation layer)
planner_agent    : QuantumPlannerAgent (master bar-close orchestrator)
base_agent       : BaseAgent          (abstract LLM agent base class)
execution_agent  : ExecutionAgent     (trade execution layer)
"""
import os
_backend_agents = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend", "agents"))
if os.path.isdir(_backend_agents) and _backend_agents not in __path__:
    __path__.append(_backend_agents)

from agents.blackboard import (
    QuantumBlackboard,
    SignalPayload,
    SignalDirection,
    SignalStatus,
)
from agents.consensus_engine import (
    ConsensusEngine,
    ConsensusAction,
    ConsensusResult,
    AgentContribution,
)
from agents.planner_agent import (
    QuantumPlannerAgent,
    ExecutionMandate,
    MandateAction,
    OverrideReason,
    GridSpacingParams,
    AccountSnapshot,
)

from agents.code_healing_agent import (
    CodeHealingAgent,
    AgentExecutionMode,
    HealingStatus,
    PatchResult,
    DiagnosticTelemetry,
)

__all__ = [
    # Blackboard layer
    "QuantumBlackboard",
    "SignalPayload",
    "SignalDirection",
    "SignalStatus",
    # Consensus layer
    "ConsensusEngine",
    "ConsensusAction",
    "ConsensusResult",
    "AgentContribution",
    # Planner layer
    "QuantumPlannerAgent",
    "ExecutionMandate",
    "MandateAction",
    "OverrideReason",
    "GridSpacingParams",
    "AccountSnapshot",
    # Code Healing & Maintenance layer
    "CodeHealingAgent",
    "AgentExecutionMode",
    "HealingStatus",
    "PatchResult",
    "DiagnosticTelemetry",
]
