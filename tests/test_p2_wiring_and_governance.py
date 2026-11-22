"""
==============================================================================
tests/test_p2_wiring_and_governance.py — Verification Suite for Batch 3 (P2)
==============================================================================
Tests every P2 fix:
  1. CodeHealingAgent defaults to SUGGEST_MODE and for_http_api() blocks paths outside project root
  2. LearningAgent persists/reloads META_MODEL_PATH and removes fabricated 70.0% accuracy
  3. SafeExecutionGateway only scales via CalibratedKellySizer when calibrated meta_probability is present
  4. ExecutionAgent forwards calibrated ml_prob from shadow council to SafeExecutionGateway
  5. OmegaRiskGovernor integrates CalibratedKellySizer cleanly
  6. NewsAgent.get_social_buzz() and TradingAgentsBridge contain zero fabricated numbers
  7. test_autonomous_master.py has exactly one tearDownClass restoring delta fetcher
"""

import ast
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from institutional.code_healing_agent import (
    CodeHealingAgent,
    AgentExecutionMode,
    HealingStatus,
)


class TestP2WiringAndGovernance(unittest.TestCase):

    def test_01_code_healing_default_suggest_mode_and_root_jail(self):
        # Default mode must be SUGGEST_MODE (AGENTS.md §4)
        agent = CodeHealingAgent()
        self.assertEqual(agent.mode, AgentExecutionMode.SUGGEST_MODE)

        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
            outside_file = os.path.join(outside_dir, "escape.py")
            with open(outside_file, "w", encoding="utf-8") as f:
                f.write("def div(x, y):\n    return x / y\n")

            http_agent = CodeHealingAgent.for_http_api(project_root=root_dir)
            self.assertEqual(http_agent.mode, AgentExecutionMode.SUGGEST_MODE)
            res = http_agent.heal_file(outside_file, error_message="ZeroDivisionError", target_line=2)
            self.assertEqual(res.status, HealingStatus.ERROR)
            self.assertFalse(res.verification_passed)
            self.assertIn("outside allowed project root", res.verification_log)

    def test_02_learning_agent_persists_meta_model_and_no_fake_70_pct(self):
        src = open(os.path.join(BACKEND_DIR, "agents", "learning_agent.py"), encoding="utf-8").read()
        self.assertIn("META_MODEL_PATH", src)
        self.assertIn("meta_clf.save(META_MODEL_PATH)", src)
        self.assertIn("MetaLabelingClassifier.load(META_MODEL_PATH)", src)
        self.assertNotIn("self._model_accuracy = 70.0", src)

    def test_03_gateway_and_execution_agent_calibrated_meta_prob_wiring(self):
        gw_src = open(os.path.join(BACKEND_DIR, "core", "safe_execution_gateway.py"), encoding="utf-8").read()
        ex_src = open(os.path.join(BACKEND_DIR, "agents", "execution_agent.py"), encoding="utf-8").read()

        self.assertIn("meta_probability: Optional[float] = None", gw_src)
        self.assertIn("and meta_probability is not None:", gw_src)
        # P3: لا يُمرَّر shadow["ml_prob"] الخام (مصدره غير مضمون)؛ الاحتمال يأتي من المزوّد المحكوم ببوابة OOS.
        # السلوك الفعلي مغطّى في tests/test_p3_behavioral.py (TestExecutionAgentUsesOnlyGatedProbability).
        self.assertNotIn('shadow_data.get("ml_prob")', ex_src)
        self.assertIn("self._gated_meta_probability(shadow_data)", ex_src)
        self.assertIn("meta_probability=meta_prob", ex_src)

    def test_04_omega_risk_governor_integrates_calibrated_kelly_sizer(self):
        src = open(os.path.join(ROOT_DIR, "council", "omega_risk_governor.py"), encoding="utf-8").read()
        self.assertIn("from quant_core.meta_model import CalibratedKellySizer", src)
        self.assertIn("self._kelly_sizer = CalibratedKellySizer", src)
        self.assertIn("calibrated_p_win: Optional[float] = None", src)

    def test_05_zero_fabricated_numbers_in_news_and_tradingagents(self):
        news_src = open(os.path.join(BACKEND_DIR, "agents", "news_agent.py"), encoding="utf-8").read()
        self.assertNotIn("base_mentions", news_src)
        self.assertNotIn("random.uniform", news_src)

        ta_src = open(os.path.join(BACKEND_DIR, "agents", "tradingagents_bridge.py"), encoding="utf-8").read()
        self.assertNotIn("استقرار نسبي عند 54/100", ta_src)
        self.assertNotIn('"price": 1.0850', ta_src)

    def test_06_autonomous_master_test_single_teardown(self):
        src = open(os.path.join(ROOT_DIR, "tests", "test_autonomous_master.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestAutonomousMasterOrchestrator":
                teardowns = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "tearDownClass"]
                self.assertEqual(len(teardowns), 1)


if __name__ == "__main__":
    unittest.main()
