"""
==============================================================================
tests/test_code_healing_agent.py — Unit Tests for Code Healing Agent
==============================================================================
Tests the 4 stages of the Self-Healing Code Agent:
  1. AST Symbol Slicing
  2. Episodic Vault Remediation
  3. Deterministic Verification Gate (Sandbox)
  4. Suggest Mode vs Autonomous Sandbox Mode with Backup/Rollback
"""

import os
import tempfile
import unittest

from institutional.code_healing_agent import (
    CodeHealingAgent,
    AgentExecutionMode,
    HealingStatus,
    ASTSymbolSlicer,
    DeterministicVerificationGate,
)


class TestCodeHealingAgent(unittest.TestCase):

    def setUp(self):
        self.agent = CodeHealingAgent(mode=AgentExecutionMode.SUGGEST_MODE)

    def test_ast_symbol_slicing_python(self):
        sample_code = (
            "def calculate_spread(ask, bid):\n"
            "    # Line 2\n"
            "    return ask - bid\n"
            "\n"
            "def compute_indicator(val, denom):\n"
            "    # Line 6\n"
            "    res = val / denom\n"
            "    return res\n"
        )
        snippet, start, end, symbol_name = ASTSymbolSlicer.slice_python(sample_code, target_line=7)
        self.assertEqual(symbol_name, "compute_indicator")
        self.assertEqual(start, 5)
        self.assertEqual(end, 8)
        self.assertIn("res = val / denom", snippet)

    def test_deterministic_verification_gate_python(self):
        gate = DeterministicVerificationGate()
        clean_code = "def foo():\n    return 42\n"
        passed, log = gate.verify_python_code("test.py", clean_code)
        self.assertTrue(passed)

        broken_code = "def foo():\n    return 42 syntax error here"
        passed, log = gate.verify_python_code("test.py", broken_code)
        self.assertFalse(passed)
        self.assertIn("SyntaxError", log)

    def test_mql5_structural_bracket_verification(self):
        gate = DeterministicVerificationGate()
        clean_mql = "void OnTick() { Print(\"Tick\"); }"
        passed, _ = gate.verify_mql5_code("test.mq5", clean_mql)
        self.assertTrue(passed)

        unbalanced_mql = "void OnTick() { Print(\"Tick\"); "
        passed, log = gate.verify_mql5_code("test.mq5", unbalanced_mql)
        self.assertFalse(passed)
        self.assertIn("Unbalanced curly braces", log)

    def test_suggest_mode_does_not_modify_file(self):
        # Create a temporary file with a ZeroDivision risk
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write("def div(x, y):\n    return x / y\n")
            temp_path = tf.name

        try:
            agent = CodeHealingAgent(mode=AgentExecutionMode.SUGGEST_MODE)
            res = agent.heal_file(
                temp_path,
                error_message="ZeroDivisionError: division by zero",
                target_line=2,
            )

            # In SUGGEST_MODE, patch is generated and verified, but file remains unchanged
            self.assertEqual(res.status, HealingStatus.DIAGNOSED_PENDING_APPROVAL)
            self.assertTrue(res.verification_passed)
            self.assertIn("max(y, 1e-8)", res.diff)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("return x / y", content) # Unchanged

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_autonomous_sandbox_mode_applies_and_backs_up(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write("def safe_calc(val, factor):\n    return val / factor\n")
            temp_path = tf.name

        try:
            agent = CodeHealingAgent(mode=AgentExecutionMode.AUTONOMOUS_SANDBOX)
            res = agent.heal_file(
                temp_path,
                error_message="ZeroDivisionError: division by zero",
                target_line=2,
            )

            self.assertEqual(res.status, HealingStatus.REPAIRED_AND_VERIFIED)
            self.assertTrue(res.verification_passed)
            self.assertIsNotNone(res.backup_path)
            self.assertTrue(os.path.exists(res.backup_path))

            # Verify file content was safely updated
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("max(factor, 1e-8)", content)

            # Clean backup
            if res.backup_path and os.path.exists(res.backup_path):
                os.remove(res.backup_path)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
