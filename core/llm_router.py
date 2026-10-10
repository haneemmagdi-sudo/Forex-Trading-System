"""
core/llm_router.py — Multi-provider LLM routing and resilience engine.

Real HTTP calls with a fallback chain:
    preferred provider → Gemini → GitHub Models → Groq → Ollama (if enabled)

IMPORTANT — honesty contract
----------------------------
This module previously returned a hardcoded
``{"action": "HOLD", "confidence": 0.5}`` payload without contacting any
provider, which silently turned every LLM-driven agent into a no-op that
looked like it was reasoning.  It now raises ``AllProvidersExhaustedError``
when no provider is reachable, so callers can fall back to their own
deterministic logic instead of acting on a fabricated decision.
"""

from __future__ import annotations
import os
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Awaitable

import httpx

logger = logging.getLogger("core.llm_router")


class AllProvidersExhaustedError(Exception):
    """Raised when every configured LLM provider fails or is unconfigured."""
    pass


@dataclass
class LLMResponse:
    provider: str
    model: str
    text: str
    raw_response: Optional[Dict[str, Any]] = None

    def json(self) -> Optional[Dict[str, Any]]:
        """
        Parse the response text as a JSON object.

        Handles ```json fences and, as a last resort, extracts the outermost
        {...} block so that a model which adds prose around its JSON still
        yields a usable decision.  Returns None when nothing parses.
        """
        clean = self.text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        start, end = clean.find("{"), clean.rfind("}")
        if 0 <= start < end:
            try:
                parsed = json.loads(clean[start:end + 1])
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None


class LLMRouter:
    """
    Routes agent prompts to the best available LLM provider.

    Keys are read lazily on every call (not at construction) so that the
    router works regardless of import order relative to ``load_dotenv()``
    and picks up rotated credentials without a restart.
    """

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.api_keys = api_keys or {}
        self.timeout = timeout
        self.max_retries = max_retries

    # ── configuration helpers ────────────────────────────────────────

    def _key(self, name: str, env_var: str) -> str:
        """Read a key from the injected dict first, then the environment."""
        value = self.api_keys.get(name) or os.getenv(env_var, "")
        value = (value or "").strip()
        # Placeholders from .env.example must never be treated as credentials
        if not value or value.startswith("your_") or value == "changeme":
            return ""
        return value

    def _provider_chain(self, preferred: Optional[str]) -> List[str]:
        chain = ["gemini", "github", "groq", "ollama"]
        if preferred in chain:
            chain.remove(preferred)
            chain.insert(0, preferred)
        elif preferred and preferred != "rule_engine":
            logger.warning(
                "[LLMRouter] Unknown preferred provider %r — using default chain.", preferred
            )
        return chain

    def _provider_config(self, name: str) -> Optional[Tuple[str, Dict[str, str], str]]:
        """Return (url, headers, model) for a provider, or None if unconfigured."""
        if name == "gemini":
            key = self._key("gemini", "GEMINI_API_KEY")
            if not key:
                return None
            return (
                f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={key}",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            )
        if name == "github":
            key = self._key("github", "GITHUB_MODELS_TOKEN")
            if not key:
                return None
            return (
                "https://models.inference.ai.azure.com/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini"),
            )
        if name == "groq":
            key = self._key("groq", "GROQ_API_KEY")
            if not key:
                return None
            return (
                "https://api.groq.com/openai/v1/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            )
        if name == "ollama":
            if os.getenv("OLLAMA_ENABLED", "false").strip().lower() not in ("1", "true", "yes"):
                return None
            base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
            return (
                f"{base}/v1/chat/completions",
                {"Content-Type": "application/json"},
                os.getenv("OLLAMA_MODEL", "llama3.2"),
            )
        return None

    # ── transport ────────────────────────────────────────────────────

    async def _call_provider(
        self, name: str, system_prompt: str, user_prompt: str, temperature: float
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Perform one real HTTP call. Returns (text, model, raw) or None."""
        cfg = self._provider_config(name)
        if cfg is None:
            return None
        url, headers, model = cfg
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not text or not str(text).strip():
            raise RuntimeError("empty completion")
        return str(text).strip(), model, data

    # ── public API ───────────────────────────────────────────────────

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "general",
        preferred_provider: Optional[str] = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """
        Request a completion from the preferred provider or the fallback chain.

        Raises
        ------
        AllProvidersExhaustedError
            When no provider is configured or every attempt failed.  Callers
            must handle this — the router never fabricates a decision.
        """
        errors: List[str] = []

        for name in self._provider_chain(preferred_provider):
            if self._provider_config(name) is None:
                continue

            for attempt in range(1, self.max_retries + 1):
                try:
                    result = await self._call_provider(
                        name, system_prompt, user_prompt, temperature
                    )
                    text, model, raw = result
                    logger.info(
                        "[LLMRouter] %s answered via %s/%s (%d chars)",
                        agent_name, name, model, len(text),
                    )
                    return LLMResponse(
                        provider=name, model=model, text=text, raw_response=raw
                    )
                except Exception as exc:
                    errors.append(f"{name} (attempt {attempt}): {exc}")
                    logger.warning(
                        "[LLMRouter] %s failed on %s attempt %d/%d: %s",
                        agent_name, name, attempt, self.max_retries, exc,
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * attempt)

        raise AllProvidersExhaustedError(
            f"No LLM provider could serve {agent_name!r}. "
            f"Attempts: {'; '.join(errors) if errors else 'no provider configured'}"
        )
