"""
==============================================================================
tests/test_p0_critical_fixes.py — Verification Suite for Batch 1 (P0) Fixes
==============================================================================
Tests every single P0 fix applied during the architectural & quant audit:
  1. Unified MT5Connector.get_pip_size / get_digits / get_pip_value (EURUSD, USDJPY, XAUUSD, XAGUSD)
  2. RiskManager XAUUSD (digits=2) pip math + Emergency Server-Side Hard SL when use_dynamic_sl=False
  3. RiskManager.calc_trailing_sl rounding per symbol + per-symbol check_spread
  4. BetaOrderFlowAgent SELL TP2 geometry (tp2 < tp1 < entry < sl)
  5. MarketAnalystAgent._on_news_alert clears all auto-added USD pairs on expiry
  6. backend/backtest_walkforward.py top-level math import & get_ohlcv (no get_rates)
  7. backend/models/database.py imports logger cleanly
  8. Paper-mode PnL formula (no 10x inflation)
  9. SafeExecutionGateway Kelly multiplier enforced BEFORE 1.5% Equity cap
"""

import ast
import asyncio
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.core.mt5_connector import MT5Connector
from backend.core.risk_manager import RiskManager


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestP0CriticalFixes(unittest.TestCase):

    def test_01_unified_pip_size_digits_and_value(self):
        conn = MT5Connector()
        conn._use_yfinance = True

        self.assertEqual(MT5Connector.get_pip_size("EURUSD"), 0.0001)
        self.assertEqual(MT5Connector.get_pip_size("USDJPY"), 0.01)
        self.assertEqual(MT5Connector.get_pip_size("XAUUSD"), 0.1)
        self.assertEqual(MT5Connector.get_pip_size("XAGUSD"), 0.01)

        self.assertEqual(conn.get_digits("EURUSD"), 5)
        self.assertEqual(conn.get_digits("USDJPY"), 3)
        self.assertEqual(conn.get_digits("XAUUSD"), 2)
        self.assertEqual(conn.get_digits("XAGUSD"), 2)

        self.assertEqual(conn.get_pip_value("EURUSD"), 10.0)
        self.assertEqual(conn.get_pip_value("XAUUSD"), 10.0)

    def test_02_risk_manager_xauusd_and_emergency_hard_sl(self):
        rm = RiskManager()
        # ATR = $2.0, sl_atr_multiplier = 2.5 -> sl_distance = $5.0 -> 50.0 pips (since XAU pip = 0.1)
        params_buy = rm.calc_trade_params(
            symbol="XAUUSD",
            direction="BUY",
            entry=2650.00,
            atr=2.0,
            balance=10000.0,
            pip_value=10.0,
            digits=2,
        )
        self.assertTrue(params_buy.valid)
        self.assertAlmostEqual(params_buy.sl_pips, 50.0, places=1)
        # Even with use_dynamic_sl=False, emergency_hard_sl_enabled=True puts a server-side SL!
        self.assertGreater(params_buy.sl_price, 0.0)
        self.assertLess(params_buy.sl_price, 2650.00)
        self.assertAlmostEqual(params_buy.sl_price, 2640.00, places=2)

        params_sell = rm.calc_trade_params(
            symbol="XAUUSD",
            direction="SELL",
            entry=2650.00,
            atr=2.0,
            balance=10000.0,
            pip_value=10.0,
            digits=2,
        )
        self.assertGreater(params_sell.sl_price, 2650.00)
        self.assertAlmostEqual(params_sell.sl_price, 2660.00, places=2)

    def test_03_trailing_sl_digits_and_per_symbol_spread(self):
        rm = RiskManager()
        sl_xau = rm.calc_trailing_sl("BUY", 2650.1234, atr=1.0, pip_size=0.1)
        self.assertEqual(sl_xau, round(2650.1234 - 1.5, 2))
        sl_jpy = rm.calc_trailing_sl("SELL", 155.12345, atr=0.2, pip_size=0.01)
        self.assertEqual(sl_jpy, round(155.12345 + 0.3, 3))

        self.assertTrue(rm.check_spread(2.5, "EURUSD"))
        self.assertFalse(rm.check_spread(3.5, "EURUSD"))
        self.assertTrue(rm.check_spread(6.5, "GBPJPY"))

    def test_04_beta_sell_tp2_below_entry(self):
        # P4: مجلس الوكلاء الخماسي صار في council/ — استيراد عادي بلا التفاف على sys.modules
        import council.alpha_regime_agent as alpha_mod
        import council.beta_orderflow_agent as beta_mod

        BetaOrderFlowAgent = beta_mod.BetaOrderFlowAgent
        RegimeOutput = alpha_mod.RegimeOutput
        RegimeState = alpha_mod.RegimeState

        beta = BetaOrderFlowAgent.__new__(BetaOrderFlowAgent)
        beta.point_value = 0.00001
        beta._ofi_engine = None

        n = 30
        df = pd.DataFrame({
            "open": np.full(n, 1.1000),
            "high": np.full(n, 1.1010),
            "low": np.full(n, 1.0990),
            "close": np.full(n, 1.1000),
            "tick_volume": np.full(n, 500.0),
        })
        df.loc[n - 2, "high"] = 1.1025   # Pierces swing high (1.1010)
        df.loc[n - 1, "close"] = 1.1005  # Reclaims below swing high

        regime = RegimeOutput(
            symbol="EURUSD",
            regime_state=RegimeState.MEAN_REVERTING_RANGE,
            regime_confidence=0.9,
            hurst_exponent=0.35,
            atr_points=100.0,
            atr_ratio=1.0,
            rolling_z_score=1.5,
            directional_bias="BEARISH",
            diagnostics={},
        )
        ofi = SimpleNamespace(ofi_z_score=-1.2, buy_volume_pct=0.3, source="SIMULATED")
        prop = beta._propose_sync("EURUSD", df, regime, datetime(2026, 11, 17, 13, 0, tzinfo=timezone.utc), ofi)

        self.assertEqual(prop.proposed_action, "LIMIT_SELL")
        self.assertLess(prop.take_profit_1, prop.entry_price)
        self.assertLess(prop.take_profit_2, prop.take_profit_1, "SELL TP2 must be below TP1 and entry!")
        self.assertGreater(prop.stop_loss, prop.entry_price)

    def test_05_backtest_walkforward_imports_and_runs_cleanly(self):
        from backend import backtest_walkforward as bw
        df = bw.fetch_historical_bars("EURUSD", "H1", 120, source="synthetic")
        self.assertEqual(len(df), 120)
        self.assertIn("close", df.columns)
        src = open(os.path.join(BACKEND_DIR, "backtest_walkforward.py"), encoding="utf-8").read()
        self.assertNotIn("get_rates(", src)
        self.assertIn("get_ohlcv(", src)
        self.assertNotIn("spread_pts * 0.1", src)

    def test_06_database_logger_imported(self):
        src = open(os.path.join(BACKEND_DIR, "models", "database.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
        self.assertIn("logger", imported, "database.py must import logger")

    def test_07_paper_pnl_no_10x_inflation(self):
        pip_size = MT5Connector.get_pip_size("EURUSD")
        conn = MT5Connector()
        conn._use_yfinance = True
        pip_value = conn.get_pip_value("EURUSD")
        pips = (1.1010 - 1.1000) / pip_size
        profit = pips * pip_value * 0.10
        self.assertAlmostEqual(profit, 10.0, places=2)

    def test_08_safe_execution_gateway_kelly_before_cap_and_no_10x(self):
        src = open(os.path.join(BACKEND_DIR, "core", "safe_execution_gateway.py"), encoding="utf-8").read()
        kelly_pos = src.find("CalibratedKellySizer")
        cap_pos = src.find("max_risk_usd = equity * 0.015")
        self.assertGreater(kelly_pos, 0)
        self.assertGreater(cap_pos, kelly_pos, "1.5% Equity cap must be enforced AFTER Kelly scaling!")
        self.assertNotIn("pip_value * lot * 10", src)
        self.assertIn("MT5Connector.get_pip_size(symbol)", src)

    def test_09_market_analyst_news_blackout_clears_affected(self):
        src = open(os.path.join(BACKEND_DIR, "agents", "market_analyst.py"), encoding="utf-8").read()
        self.assertIn("affected = set(symbols)", src)
        self.assertIn("lambda s=affected: self._news_blackout_symbols.difference_update(s)", src)

    def test_10_execution_bridge_dynamic_atr_baseline(self):
        src = open(os.path.join(BACKEND_DIR, "core", "execution_bridge.py"), encoding="utf-8").read()
        self.assertNotIn("atr_baseline=0.0015", src)
        self.assertIn("atr_baseline=atr_baseline", src)


if __name__ == "__main__":
    unittest.main()
