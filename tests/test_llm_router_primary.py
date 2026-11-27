"""
tests/test_llm_router_primary.py — Unit tests for Gemini-primary LLM routing & resilience.
All network calls are mocked; no API keys or external network required.
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
for _p in (BACKEND, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from institutional.llm_router import AllProvidersExhaustedError, LLMRouter
from institutional.risk_manager import RiskManagerAgent
from backend.agents.tradingagents_bridge import TradingAgentsBridge


class TestLLMRouterPrimaryGemini(unittest.TestCase):

    def setUp(self):
        LLMRouter._cooldowns.clear()

    def tearDown(self):
        LLMRouter._cooldowns.clear()

    def test_gemini_is_first_and_nvidia_is_second_in_default_chain(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)
            router = LLMRouter(api_keys={"gemini": "g-key", "nvidia": "n-key", "groq": "q-key"})
            chain = router._provider_chain(None)
            self.assertEqual(chain[0], "gemini")
            self.assertEqual(chain[1], "modal")
            self.assertEqual(chain[2], "groq")

            # "google" alias routes to gemini first
            self.assertEqual(router._provider_chain("google")[0], "gemini")

    def test_gemini_default_model_and_google_api_key_fallback(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "g-from-google-env"}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("GEMINI_MODEL", None)
            router = LLMRouter()
            cfg = router._provider_config("gemini")
            self.assertIsNotNone(cfg)
            _url, _headers, model = cfg
            self.assertEqual(model, "gemini-2.5-flash")

    def test_transient_timeout_retries_gemini_before_falling_back(self):
        router = LLMRouter(api_keys={"gemini": "g-key", "nvidia": "n-key"}, max_retries=2)
        calls = []

        async def fake_call(name, system_prompt, user_prompt, temperature):
            calls.append(name)
            if len(calls) == 1:
                raise RuntimeError("transient read timeout")
            return '{"ok": true}', "gemini-2.5-flash", {}

        with patch.object(router, "_call_provider", side_effect=fake_call), \
             patch("institutional.llm_router.asyncio.sleep", new=AsyncMock()):
            res = asyncio.run(router.complete("sys", "user", agent_name="fx_analyst"))

        self.assertEqual(res.provider, "gemini")
        self.assertEqual(calls, ["gemini", "gemini"])

    def test_quota_or_model_error_falls_back_to_nvidia(self):
        router = LLMRouter(api_keys={"gemini": "g-key", "nvidia": "n-key"}, max_retries=2)
        calls = []

        async def fake_call(name, system_prompt, user_prompt, temperature):
            calls.append(name)
            if name == "gemini":
                raise RuntimeError("HTTP 429: quota exceeded")
            return '{"ok": true}', "nvidia/nemotron-3.5-lightning-30b-a3b", {}

        with patch.object(router, "_call_provider", side_effect=fake_call):
            res = asyncio.run(router.complete("sys", "user", agent_name="fx_analyst"))

        self.assertEqual(res.provider, "modal")
        self.assertEqual(calls, ["gemini", "modal"])

    def test_all_providers_exhausted_still_raises(self):
        router = LLMRouter(api_keys={})
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "your_gemini_api_key_here",
            "GOOGLE_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "MODAL_API_KEY": "",
            "GROQ_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "AGNES_API_KEY": "",
            "UNOROUTER_API_KEY": "",
            "XKIRO_API_KEY": "",
            "GITHUB_MODELS_TOKEN": "",
            "OLLAMA_ENABLED": "false",
        }):
            with self.assertRaises(AllProvidersExhaustedError):
                asyncio.run(router.complete("sys", "user"))

    def test_risk_manager_does_not_force_groq(self):
        self.assertIsNone(RiskManagerAgent.preferred_llm_provider)

    def test_tradingagents_bridge_uses_gemini_25_flash_and_sets_google_key(self):
        bridge = TradingAgentsBridge()
        mock_graph_cls = MagicMock()
        mock_graph = mock_graph_cls.return_value
        mock_graph.propagate.return_value = ({
            "market_report": "ok",
            "sentiment_report": "ok",
            "news_report": "ok",
            "fundamentals_report": "ok",
            "investment_debate_state": {"bull_history": "", "bear_history": "", "judge_decision": "ok"},
            "risk_debate_state": {"risky_history": "", "safe_history": "", "neutral_history": "", "judge_decision": "ok"},
            "final_trade_decision": "HOLD",
        }, "Hold")

        fake_tech = {
            "price": 1.1, "rsi": 50.0, "macd": 0.0, "macd_signal": 0.0,
            "sma20": 1.1, "sma50": 1.1, "atr": 0.001, "trend": "صاعد", "data_points": 50,
        }
        fake_default_mod = MagicMock()
        fake_default_mod.DEFAULT_CONFIG = {
            "max_debate_rounds": 1,
            "results_dir": "./logs",
            "llm_provider": "openai",
            "deep_think_llm": "gpt-6-sol",
            "quick_think_llm": "gpt-6-luna",
        }
        fake_ta_pkg = MagicMock()
        fake_graph_mod = MagicMock(TradingAgentsGraph=mock_graph_cls)

        with patch.object(bridge, "_fetch_technical_snapshot", return_value=fake_tech), \
             patch.object(bridge, "_save_run"), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "g-test-key", "TRADINGAGENTS_FORCE_SIMULATOR": "false"}, clear=False), \
             patch.dict(sys.modules, {
                 "tradingagents": fake_ta_pkg,
                 "tradingagents.default_config": fake_default_mod,
                 "tradingagents.graph": MagicMock(),
                 "tradingagents.graph.trading_graph": fake_graph_mod,
             }):
            os.environ.pop("GOOGLE_API_KEY", None)
            os.environ.pop("GEMINI_MODEL", None)
            bridge.analyze("EURUSD", "2026-11-27")
            cfg = mock_graph_cls.call_args.kwargs["config"]
            self.assertEqual(cfg["llm_provider"], "google")
            self.assertEqual(cfg["deep_think_llm"], "gemini-2.5-flash")
            self.assertEqual(cfg["quick_think_llm"], "gemini-2.5-flash")
            self.assertEqual(os.environ.get("GOOGLE_API_KEY"), "g-test-key")


if __name__ == "__main__":
    unittest.main()
