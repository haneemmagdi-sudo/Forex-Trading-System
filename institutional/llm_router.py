"""
core/llm_router.py — Multi-provider LLM routing and resilience engine.

Real HTTP calls with a fallback chain:
    preferred provider → Gemini → NVIDIA/Modal → Groq → OpenRouter/others → Ollama (if enabled)

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
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Awaitable

import httpx
from dotenv import load_dotenv

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

    _cooldowns: Dict[str, float] = {}
    COOLDOWN_SECONDS: float = 60.0

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        timeout: float = 45.0,
        max_retries: int = 2,
    ):
        load_dotenv()
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
        # Supported provider names and aliases
        aliases = {
            "google": "gemini",
            "nvidia": "modal",
            "agnes_ai": "agnes",
            "agnes-ai": "agnes",
        }
        default_pref = os.getenv("DEFAULT_LLM_PROVIDER", "").strip().lower()
        if not preferred and default_pref:
            preferred = default_pref

        preferred = aliases.get(preferred, preferred)

        chain = [
            "gemini",
            "modal",
            "groq",
            "openrouter",
            "agnes",
            "unorouter",
            "xkiro",
            "ollama",
        ]
        if preferred in chain:
            chain.remove(preferred)
            chain.insert(0, preferred)
        elif preferred and preferred != "rule_engine":
            logger.warning(
                "[LLMRouter] Unknown preferred provider %r — using default chain.", preferred
            )

        now = time.time()
        active = [p for p in chain if self._cooldowns.get(p, 0.0) <= now]
        cooling = [p for p in chain if self._cooldowns.get(p, 0.0) > now]
        return active + cooling

    def _provider_config(self, name: str) -> Optional[Tuple[str, Dict[str, str], str]]:
        """Return (url, headers, model) for a provider, or None if unconfigured."""
        common_ua = "AlphaEdge-TradingSystem/1.0"

        if name == "gemini":
            key = self._key("gemini", "GEMINI_API_KEY") or self._key("gemini", "GOOGLE_API_KEY")
            if not key:
                return None
            return (
                f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={key}",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
            )
        if name == "groq":
            key = self._key("groq", "GROQ_API_KEY")
            if not key:
                return None
            return (
                "https://api.groq.com/openai/v1/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            )
        if name in ("modal", "nvidia"):
            key = self._key("nvidia", "NVIDIA_API_KEY") or self._key("modal", "MODAL_API_KEY")
            if not key:
                return None
            base = os.getenv("NVIDIA_BASE_URL", os.getenv("MODAL_BASE_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
            model = os.getenv("NVIDIA_MODEL", os.getenv("MODAL_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"))
            return (
                f"{base}/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                model,
            )
        if name == "openrouter":
            key = self._key("openrouter", "OPENROUTER_API_KEY")
            if not key:
                return None
            base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
            model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
            return (
                f"{base}/chat/completions",
                {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://alphaedge.ai",
                    "X-Title": "AlphaEdge-TradingSystem",
                    "User-Agent": common_ua,
                },
                model,
            )
        if name in ("agnes", "agnes_ai"):
            key = self._key("agnes", "AGNES_API_KEY")
            if not key:
                return None
            base = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1").rstrip("/")
            model = os.getenv("AGNES_MODEL", "agnes-2.5-flash")
            return (
                f"{base}/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                model,
            )
        if name == "unorouter":
            key = self._key("unorouter", "UNOROUTER_API_KEY")
            if not key:
                return None
            base = os.getenv("UNOROUTER_BASE_URL", "https://api.unorouter.com/v1").rstrip("/")
            model = os.getenv("UNOROUTER_MODEL", "deepseek-chat:free")
            return (
                f"{base}/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                model,
            )
        if name == "xkiro":
            key = self._key("xkiro", "XKIRO_API_KEY")
            if not key:
                return None
            base = os.getenv("XKIRO_BASE_URL", "https://api.xkiro.com/v1").rstrip("/")
            model = os.getenv("XKIRO_MODEL", "google/gemini-2.5-flash")
            return (
                f"{base}/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                model,
            )
        if name == "github":
            key = self._key("github", "GITHUB_MODELS_TOKEN")
            if not key:
                return None
            return (
                "https://models.inference.ai.azure.com/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": common_ua},
                os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini"),
            )
        if name == "ollama":
            if os.getenv("OLLAMA_ENABLED", "false").strip().lower() not in ("1", "true", "yes"):
                return None
            base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
            headers = {"Content-Type": "application/json", "User-Agent": common_ua}
            key = self._key("ollama", "OLLAMA_API_KEY")
            if key:
                headers["Authorization"] = f"Bearer {key}"
            return (
                f"{base}/v1/chat/completions",
                headers,
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
            "max_tokens": 1024,
        }
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, self.timeout))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        msg = (data.get("choices") or [{}])[0].get("message", {})
        text = msg.get("content") or msg.get("reasoning_content") or ""
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
                    LLMRouter._cooldowns.pop(name, None)
                    logger.info(
                        "[LLMRouter] %s answered via %s/%s (%d chars)",
                        agent_name, name, model, len(text),
                    )
                    return LLMResponse(
                        provider=name, model=model, text=text, raw_response=raw
                    )
                except Exception as exc:
                    err_msg = str(exc)
                    errors.append(f"{name} (attempt {attempt}): {exc}")
                    logger.warning(
                        "[LLMRouter] %s failed on %s attempt %d/%d: %s",
                        agent_name, name, attempt, self.max_retries, exc,
                    )
                    # Non-retryable auth / missing-model or quota-exhausted responses:
                    # enter cooldown and switch to fallback provider immediately.
                    is_auth_or_missing = (
                        any(code in err_msg for code in ("HTTP 400", "HTTP 401", "HTTP 403", "HTTP 404"))
                        or "Invalid Auth key" in err_msg
                        or "UNAUTHENTICATED" in err_msg
                    )
                    is_rate_limit = "HTTP 429" in err_msg
                    if is_auth_or_missing or is_rate_limit:
                        cooldown = 300.0 if is_auth_or_missing else self.COOLDOWN_SECONDS
                        LLMRouter._cooldowns[name] = time.time() + cooldown
                        reason = "auth/model error (HTTP 400-404)" if is_auth_or_missing else "rate-limit (HTTP 429)"
                        logger.warning(
                            "[LLMRouter] %s hit %s. Entering %.0fs cooldown; switching to next provider.",
                            name, reason, cooldown,
                        )
                        break

                    if attempt < self.max_retries:
                        await asyncio.sleep(0.8 * attempt)
                    else:
                        # Transient failures exhausted retries for this cycle: brief cooldown so backup serves next
                        LLMRouter._cooldowns[name] = time.time() + self.COOLDOWN_SECONDS

        raise AllProvidersExhaustedError(
            f"No LLM provider could serve {agent_name!r}. "
            f"Attempts: {'; '.join(errors) if errors else 'no provider configured'}"
        )
