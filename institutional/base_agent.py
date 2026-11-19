"""
Base Agent — abstract class shared by all AI trading agents.
Provides LLM routing, JSON response building, logging,
and standardized prompt formatting.
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from institutional.llm_router import LLMRouter, LLMResponse, AllProvidersExhaustedError

logger = logging.getLogger("base_agent")


class BaseAgent(ABC):
    """
    Abstract base for all AI agents in the trading company.
    Each agent has a name, role description, and LLM access.
    """

    name: str = "base_agent"
    role_description: str = "Base trading agent"
    preferred_llm_provider: Optional[str] = None

    def __init__(self, llm_router: LLMRouter, db=None):
        self.llm = llm_router
        self.db = db
        self.logger = logging.getLogger(self.name)
        self._cycle_count: int = 0
        self._last_response: Optional[LLMResponse] = None

    # ── LLM call ─────────────────────────────────────────────

    async def think(
        self,
        user_prompt: str,
        extra_context: dict = None,
        cycle_id: str = "",
    ) -> Optional[dict]:
        """
        Send a prompt to the LLM and return parsed JSON dict.
        Returns None if all providers are exhausted.
        """
        system_prompt = self._build_system_prompt(extra_context)

        try:
            response = await self.llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=self.name,
                preferred_provider=self.preferred_llm_provider,
            )
            self._last_response = response
            self.logger.info(
                f"[{self.name.upper()}] Response via {response.provider} "
                f"({len(response.text)} chars)"
            )
            # LLMResponse exposes .json() — the previous code read a
            # non-existent .parsed_json attribute, so every call raised
            # AttributeError and think() always returned None.
            payload = response.json()
            if payload is None:
                self.logger.warning(
                    f"[{self.name.upper()}] Provider returned non-JSON output — "
                    f"no decision taken (returning None)."
                )
                return None

            # Persist the reasoning only when the injected handle supports it
            log_reasoning = getattr(self.db, "log_reasoning", None) if self.db else None
            if log_reasoning:
                await log_reasoning(
                    agent=self.name,
                    cycle_id=cycle_id,
                    reasoning=response.text[:2000],
                    decision=str(payload.get("decision", "")),
                    llm_provider=response.provider,
                )
            return payload

        except AllProvidersExhaustedError as e:
            self.logger.error(f"[{self.name.upper()}] All LLM providers exhausted: {e}")
            return None
        except Exception as e:
            self.logger.error(f"[{self.name.upper()}] LLM call failed: {e}")
            return None

    def _build_system_prompt(self, extra_context: dict = None) -> str:
        """Build the system prompt for this agent."""
        base = f"""You are the {self.role_description} at AlphaEdge Capital AI, 
an autonomous AI trading firm managing a ${10000:.0f} portfolio.

CRITICAL RULES:
- Always respond with valid JSON only. No explanations outside JSON.
- Base all decisions on the provided market data.
- Do NOT use predefined strategies — reason from first principles.
- Be precise, data-driven, and professional.

CURRENT TIME (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
"""
        # Append subclass-specific system prompt extension if defined
        extension = getattr(self, "SYSTEM_PROMPT_EXTENSION", None)
        if extension:
            base += f"\n{extension}"

        if extra_context:
            base += f"\nADDITIONAL CONTEXT:\n{self._format_context(extra_context)}"
        return base

    def _format_context(self, ctx: dict) -> str:
        """Format context dict as readable text for the system prompt."""
        lines = []
        for k, v in ctx.items():
            if isinstance(v, dict):
                lines.append(f"{k}:")
                for kk, vv in v.items():
                    lines.append(f"  {kk}: {vv}")
            elif isinstance(v, list):
                lines.append(f"{k}: {', '.join(str(x) for x in v[:5])}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _safe_get(self, data: dict, *keys, default=None) -> Any:
        """Safely get nested dict values."""
        val = data
        for key in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(key, default)
        return val

    @property
    def last_provider(self) -> str:
        return self._last_response.provider if self._last_response else "none"
