"""
Main Asynchronous Multi-Agent Orchestrator (`main_orchestrator.py`)
Coordinates the 5-Agent Institutional Council in parallel and writes atomic
JSON payloads for the MQL5 Hot-Path Execution Engine (`InstitutionalExecutor.mq5`).

Upgrade (2026-10): 5 improvements applied
  #1 Real OFI via quant_core.RealOFIEngine (BetaOrderFlowAgent)
  #2 Agent Delta — MacroSentinelAgent (Forex Factory calendar embargo)
  #3 Adaptive Episodic Memory (TradeOutcomeRecorder → GammaRedTeamCritic)
  #4 M1 Confirmation Gate before final payload write
  #5 Dynamic Threshold Engine inside OmegaRiskGovernor
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

from council import (
    AlphaRegimeAgent,
    BetaOrderFlowAgent,
    GammaRedTeamCritic,
    OmegaRiskGovernor,
    MacroSentinelAgent,
    SignalPayload,
)
from memory_rag.adaptive_trade_journal import TradeOutcomeRecorder, TradeVectorRecord

# Attempt optional MetaTrader5 import for live terminal connection
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("QuantOrchestrator")


_BACKEND_DIR = str(Path(__file__).resolve().parent / "backend")


def build_omega_live_context(symbol: str, regime_value: str, reflection_reader=None):
    """
    يجمع السياق الحي الذي يستهلكه OmegaRiskGovernor.adjudicate() (2026 Batch 2):
      - bus_context: حالة الـ Bus (فيتو DD الطارئ / حظر الأخبار) التي يصدّرها الـ backend في ملف مشترك،
        لأن المجلس يعمل في عملية منفصلة عن SignalBus.
      - reflection_advisory: ذاكرة التأمّل (تبريد/عقوبة عتبة) من SQLite المشترك على مستوى الزوج،
        لأن مفردات أنظمة المجلس تختلف عن fsm_regime المخزَّن.
    كل مصدر غائب أو معطوب يعيد None (لا سياق) بدل أن يعطّل الدورة؛ الفيتوات الأخرى تعمل كالمعتاد.
    """
    if _BACKEND_DIR not in sys.path:
        sys.path.append(_BACKEND_DIR)  # append: لا يزاحم حزم الجذر (config)

    bus_context = None
    try:
        from core.signal_bus import load_council_context
        bus_context = load_council_context(symbol, regime_value)
    except Exception as exc:
        logger.warning("[%s] Omega bus_context unavailable: %s", symbol, exc)

    reflection_advisory = None
    if reflection_reader is not None:
        try:
            reflection_advisory = reflection_reader.evaluate_pair_regime(
                symbol, reflection_reader.ANY_REGIME
            ).to_dict()
        except Exception as exc:
            logger.warning("[%s] Omega reflection_advisory unavailable: %s", symbol, exc)

    return bus_context, reflection_advisory


def make_reflection_reader():
    """قارئ التأمّل على SQLite الـ backend، أو None إن تعذّر استيراده (لا يعطّل بدء المجلس)."""
    if _BACKEND_DIR not in sys.path:
        sys.path.append(_BACKEND_DIR)
    try:
        from core.reflection_memory import ReflectionMemoryReader
        from council.tuning import get_block
        c = get_block("COMMUNICATION_REFLECTION_2026")
        return ReflectionMemoryReader(
            lookback_days=c.get("reflection_lookback_days", 14),
            min_samples=c.get("reflection_min_samples", 4),
            cooldown_consecutive_losses=c.get("reflection_cooldown_consecutive_losses", 4),
            max_conf_penalty=c.get("reflection_max_conf_penalty", 15.0),
            max_omega_penalty=c.get("reflection_max_omega_penalty", 0.08),
            cache_ttl_sec=c.get("reflection_cache_ttl_sec", 30.0),
        )
    except Exception as exc:
        logger.warning("ReflectionMemoryReader unavailable: %s", exc)
        return None


class AtomicMQL5Bridge:
    """
    Writes SignalPayload JSON atomically (write to .tmp -> os.replace)
    so MQL5 FileOpen() never reads a half-written file.
    Mirrors output to both the local directory and MT5 Terminal Common Files directory.
    """

    def __init__(self, target_dir: str = "./mql5_shared_signals"):
        self.target_dir = Path(target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)
        # MT5 Terminal Common Files directory for FILE_COMMON IPC
        appdata = os.environ.get("APPDATA", "")
        self.common_files_dir = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files" if appdata else None
        if self.common_files_dir and not self.common_files_dir.exists():
            try:
                self.common_files_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.common_files_dir = None

    def _write_atomic(self, dest_dir: Path, filename: str, json_bytes: bytes) -> Path:
        final_path = dest_dir / filename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(dest_dir), prefix=f".tmp_{filename}_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as tmp_file:
                tmp_file.write(json_bytes)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, final_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return final_path

    def publish_signal(self, payload: SignalPayload) -> Path:
        filename = f"SignalPayload_{payload.symbol}.json"
        json_bytes = payload.model_dump_json(indent=2).encode("utf-8")

        # 1. Write to local project directory
        local_path = self._write_atomic(self.target_dir, filename, json_bytes)

        # 2. Mirror to MT5 Common Files directory for native MQL5 FILE_COMMON IPC
        if self.common_files_dir and self.common_files_dir.exists():
            try:
                self._write_atomic(self.common_files_dir, filename, json_bytes)
            except Exception as e:
                logger.debug(f"Could not mirror payload to MT5 Common Files: {e}")

        return local_path


class MarketDataUnavailable(RuntimeError):
    """بيانات السوق الحيّة ناقصة: يُمنع تقييم الرمز في هذه الدورة (fail-closed)."""


class MarketDataProvider:
    """
    Fetches live M5 and H1 OHLCV + Spread from MetaTrader 5 if installed and connected,
    or falls back to high-fidelity synthetic institutional order-flow data for testing/CI.
    """

    def __init__(self, use_live_mt5: bool = False):
        self.use_live_mt5 = use_live_mt5 and MT5_AVAILABLE
        if self.use_live_mt5:
            if not mt5.initialize():
                logger.warning("MT5 initialization failed; falling back to simulation feed.")
                self.use_live_mt5 = False

    async def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        if self.use_live_mt5:
            return await asyncio.to_thread(self._fetch_mt5_live, symbol)
        return await asyncio.to_thread(self._generate_institutional_snapshot, symbol)

    def _fetch_mt5_live(self, symbol: str) -> Dict[str, Any]:
        rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 200)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 120)
        tick_info = mt5.symbol_info(symbol)

        # IMPROVEMENT_PLAN §0: fail-closed — لا سبريد ولا نقطة مفترضة عند نقص البيانات
        if rates_m5 is None or len(rates_m5) == 0 or rates_h1 is None or len(rates_h1) == 0:
            raise MarketDataUnavailable(f"[{symbol}] MT5 returned no M5/H1 bars")
        if tick_info is None or not tick_info.point > 0:
            raise MarketDataUnavailable(f"[{symbol}] MT5 symbol_info unavailable or invalid point")

        return {
            "symbol": symbol,
            "df_m5": pd.DataFrame(rates_m5),
            "df_h1": pd.DataFrame(rates_h1),
            "spread_points": float(tick_info.spread),
            "point_value": float(tick_info.point),
        }

    @staticmethod
    def _generate_institutional_snapshot(symbol: str) -> Dict[str, Any]:
        """
        Generates 3 realistic institutional scenarios across symbols to verify
        every branch of the 4-Agent Council:
        - EURUSD: TRENDING_LOW_VOL + Bullish FVG Pullback (Approved Trade)
        - GBPUSD: MEAN_REVERTING_RANGE + Sell-Side Liquidity Sweep (Approved Reversal)
        - XAUUSD: HIGH_SPREAD / CHOPPY Trap (Critic Veto Triggered)
        """
        rng = np.random.default_rng(seed=42)
        n_m5 = 160
        n_h1 = 100

        if symbol == "EURUSD":
            # Smooth persistent institutional trend (Hurst > 0.65)
            t = np.linspace(0, 1, n_m5)
            base_m5 = 1.08000 + 0.00850 * t + 0.00012 * np.sin(8 * np.pi * t)
            high_m5 = base_m5 + 0.00022
            low_m5 = base_m5 - 0.00022
            open_m5 = np.roll(base_m5, 1)
            open_m5[0] = base_m5[0]
            tick_vol_m5 = rng.integers(500, 1100, size=n_m5).astype(float)

            # Inject a clean Bullish FVG (3-candle displacement) near the end
            c1_idx, c2_idx, c3_idx = n_m5 - 4, n_m5 - 3, n_m5 - 2
            high_m5[c1_idx] = base_m5[c1_idx] + 0.00010
            low_m5[c3_idx] = high_m5[c1_idx] + 0.00028
            base_m5[c2_idx] = high_m5[c1_idx] + 0.00035
            high_m5[c2_idx] = base_m5[c2_idx] + 0.00015
            base_m5[-1] = (high_m5[c1_idx] + low_m5[c3_idx]) / 2.0 + 0.00008
            high_m5[-1] = base_m5[-1] + 0.00020
            low_m5[-1] = base_m5[-1] - 0.00004
            tick_vol_m5[-1] = 1850.0  # Strong institutional buying delta
            spread_pts = 3.0

            steps_h1 = np.linspace(1.07200, float(base_m5[-1]), n_h1)
            df_h1 = pd.DataFrame({
                "open": steps_h1 - 0.00030,
                "high": steps_h1 + 0.00350,
                "low": steps_h1 - 0.00120,
                "close": steps_h1,
                "tick_volume": rng.integers(2000, 6000, size=n_h1).astype(float),
            })

        elif symbol == "GBPUSD":
            # Mean-reverting Ornstein-Uhlenbeck oscillation (Hurst < 0.42) + SSL Sweep
            base_m5 = np.zeros(n_m5)
            base_m5[0] = 1.26500
            for i in range(1, n_m5):
                base_m5[i] = base_m5[i - 1] + 0.65 * (1.26500 - base_m5[i - 1]) + rng.normal(0, 0.00025)
            high_m5 = base_m5 + 0.00025
            low_m5 = base_m5 - 0.00025
            open_m5 = np.roll(base_m5, 1)
            open_m5[0] = base_m5[0]
            tick_vol_m5 = rng.integers(450, 950, size=n_m5).astype(float)

            # Engineer a Sell-Side Liquidity Sweep on the penultimate candle with strong reclaim
            swing_low = float(np.min(low_m5[-26:-2]))
            low_m5[-2] = swing_low - 0.00035  # Pierces SSL
            base_m5[-2] = swing_low + 0.00005
            base_m5[-1] = swing_low + 0.00008  # Reclaims range while Z-score < -1.2
            low_m5[-1] = swing_low - 0.00005
            high_m5[-1] = base_m5[-1] + 0.00010
            tick_vol_m5[-1] = 1900.0
            spread_pts = 4.0

            steps_h1 = np.full(n_h1, 1.26500)
            df_h1 = pd.DataFrame({
                "open": steps_h1,
                "high": steps_h1 + 0.00400,
                "low": steps_h1 - 0.00400,
                "close": steps_h1,
                "tick_volume": rng.integers(2000, 5000, size=n_h1).astype(float),
            })

        else:
            # XAUUSD: Toxic Spread & High Volatility Trap -> Vetoed by Agent Gamma / Alpha
            steps = np.cumsum(rng.normal(0, 0.00030, size=n_m5))
            base_m5 = 1.08500 + steps
            high_m5 = base_m5 + 0.00025
            low_m5 = base_m5 - 0.00025
            open_m5 = np.roll(base_m5, 1)
            open_m5[0] = base_m5[0]
            tick_vol_m5 = rng.integers(300, 800, size=n_m5).astype(float)
            spread_pts = 28.0  # Toxic spread (>15% of ATR)

            steps_h1 = np.linspace(1.08000, float(base_m5[-1]), n_h1)
            df_h1 = pd.DataFrame({
                "open": steps_h1,
                "high": steps_h1 + 0.00040,
                "low": steps_h1 - 0.00040,
                "close": steps_h1,
                "tick_volume": rng.integers(1000, 3000, size=n_h1).astype(float),
            })

        df_m5 = pd.DataFrame({
            "open": open_m5,
            "high": high_m5,
            "low": low_m5,
            "close": base_m5,
            "tick_volume": tick_vol_m5,
        })

        return {
            "symbol": symbol,
            "df_m5": df_m5,
            "df_h1": df_h1,
            "spread_points": spread_pts,
            "point_value": 0.00001,  # بيانات المحاكاة مُصمَّمة بسعر 5 خانات لكل الرموز
        }

    async def get_m1_bars(self, symbol: str, n: int = 30) -> pd.DataFrame:
        """
        Returns the last N M1 candles.
        Live mode: mt5.copy_rates_from_pos(symbol, TIMEFRAME_M1, 0, n)
        Simulation: derives M1 bars from the last available M5 snapshot.
        """
        if self.use_live_mt5:
            return await asyncio.to_thread(self._fetch_m1_live, symbol, n)
        return await asyncio.to_thread(self._simulate_m1_bars, symbol, n)

    def _fetch_m1_live(self, symbol: str, n: int) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, n)
        return pd.DataFrame(rates)

    @staticmethod
    def _simulate_m1_bars(symbol: str, n: int) -> pd.DataFrame:
        """
        Derives synthetic M1 bars from the M5 simulation baseline.
        Uses same seed so results are deterministic and reproducible.
        """
        rng = np.random.default_rng(seed=42)
        if symbol == "EURUSD":
            base = 1.08852
            # Institutional trend alignment: upward drift produces BOS higher-high on M1
            trend = np.linspace(-0.00010, 0.00015, n)
            closes = np.cumsum(rng.normal(0, 0.00003, n)) + base + trend
        elif symbol == "GBPUSD":
            base = 1.26505
            closes = np.cumsum(rng.normal(0, 0.00005, n)) + base
        else:
            base = 1.08206
            closes = np.cumsum(rng.normal(0, 0.00005, n)) + base

        highs  = closes + rng.uniform(0.00005, 0.00015, n)
        lows   = closes - rng.uniform(0.00005, 0.00015, n)
        opens  = np.roll(closes, 1); opens[0] = closes[0]
        return pd.DataFrame({
            "open":  opens,
            "high":  highs,
            "low":   lows,
            "close": closes,
            "tick_volume": rng.integers(50, 300, size=n).astype(float),
        })


class MultiAgentOrchestrator:
    """
    Runs the 5-Agent Adversarial Council per symbol concurrently using asyncio.
    Agents: Alpha (Regime) → Delta (Macro) → Beta (OrderFlow) → Gamma (Critic) → Omega (Governor)
    """

    def __init__(self, mql5_shared_dir: str = "./mql5_shared_signals", use_live_mt5: bool = False):
        self.alpha = AlphaRegimeAgent(point_value=0.00001)
        self.beta  = BetaOrderFlowAgent(point_value=0.00001, use_live_mt5=use_live_mt5)
        self.delta = MacroSentinelAgent()
        # Adaptive memory — provides live trap vectors to Gamma
        self._recorder = TradeOutcomeRecorder()
        self.gamma = GammaRedTeamCritic(
            max_spread_atr_ratio=0.15,
            point_value=0.00001,
            adaptive_memory=self._recorder.trap_memory,
        )
        self.omega = OmegaRiskGovernor(approval_threshold=0.72)
        self._reflection_reader = make_reflection_reader()
        self.bridge = AtomicMQL5Bridge(target_dir=mql5_shared_dir)
        self.data_provider = MarketDataProvider(use_live_mt5=use_live_mt5)

    async def evaluate_symbol(
        self,
        symbol: str,
        current_daily_dd_pct: float = 0.0,
        override_utc_now: Optional[datetime] = None,
    ) -> SignalPayload:
        # IMPROVEMENT_PLAN §0: إصلاح الوقت الثابت — استخدام الوقت الحقيقي دائماً
        # كان النظام يقيّم كل شيء على 2026-10-14 13:30 مما يجعل الجلسات والأخبار لا تعكس الواقع
        utc_now = override_utc_now or datetime.now(tz=timezone.utc)

        snapshot = await self.data_provider.get_market_snapshot(symbol)
        df_m5 = snapshot["df_m5"]
        df_h1 = snapshot["df_h1"]
        spread_pts = snapshot["spread_points"]
        point_value = snapshot["point_value"]

        # Step 0: Agent Delta — Macro Sentinel (runs concurrently with Alpha)
        macro_task = asyncio.create_task(
            self.delta.assess(symbol=symbol, utc_now=utc_now)
        )

        # Step 1: Agent Alpha classifies mathematical market regime
        regime = await self.alpha.analyze(symbol, df_m5, df_h1, point_value=point_value)
        logger.info(
            f"[{symbol}] Agent Alpha → Regime={regime.regime_state.value} "
            f"(Conf={regime.regime_confidence:.2f}, Hurst={regime.hurst_exponent:.3f}, "
            f"ATR={regime.atr_points}pts, Bias={regime.directional_bias})"
        )

        # Collect Delta result
        macro = await macro_task
        logger.info(
            f"[{symbol}] Agent Delta → Macro={macro.risk_level.value} "
            f"(Embargo={macro.news_embargo_active}, "
            f"Event='{macro.next_event_name or 'None'}' in {macro.minutes_to_next_event or 'N/A'} min, "
            f"RiskMult={macro.risk_percent_multiplier})"
        )

        # Step 2: Agent Beta scans Microstructure & SMC Order Flow
        proposal = await self.beta.propose_setup(
            symbol=symbol,
            df_m5=df_m5,
            regime=regime,
            utc_now=utc_now,
            point_value=point_value,
        )
        logger.info(
            f"[{symbol}] Agent Beta  → Action={proposal.proposed_action} "
            f"({proposal.setup_type}, Conf={proposal.signal_confidence:.2f}, "
            f"Entry={proposal.entry_price:.5f}, OFI={proposal.ofi_z_score:.2f} [{proposal.ofi_source}])"
        )

        # Step 3: Agent Gamma (Red-Team Critic) attacks the proposal
        critic = await self.gamma.audit_proposal(
            proposal=proposal,
            regime=regime,
            df_h1=df_h1,
            current_spread_points=spread_pts,
        )
        logger.info(
            f"[{symbol}] Agent Gamma → Veto={critic.critic_veto_triggered} "
            f"(FailureProb={critic.failure_probability_score:.2f}, "
            f"Spread/ATR={critic.spread_to_atr_ratio:.1%})"
        )

        # Step 3.5: Fetch rolling win rate from Adaptive Memory for Omega
        rolling_win_rate = await self._recorder.get_recent_win_rate(last_n=20)

        # Step 4: Agent Omega — final verdict with Dynamic Threshold + Macro multiplier
        bus_context, reflection_advisory = build_omega_live_context(
            symbol, regime.regime_state.value, self._reflection_reader
        )
        final_payload = self.omega.adjudicate(
            regime=regime,
            proposal=proposal,
            critic=critic,
            current_daily_dd_pct=current_daily_dd_pct,
            rolling_win_rate=rolling_win_rate,
            macro_risk_multiplier=macro.risk_percent_multiplier,
            macro_risk_level=macro.risk_level.value,
            reflection_advisory=reflection_advisory,
            bus_context=bus_context,
        )
        logger.info(
            f"[{symbol}] Agent Omega → Verdict={final_payload.action} "
            f"(Score={final_payload.confidence_score:.3f}, "
            f"Thresh={final_payload.approval_threshold_used:.2f}, "
            f"Risk={final_payload.execution_params.risk_percent}%, "
            f"Macro={final_payload.macro_risk_level})"
        )

        # Step 4.5: M1 Confirmation Gate — final precision filter before execution
        if final_payload.action not in ("STAND_DOWN",) and proposal.proposed_action != "STAND_DOWN":
            m1_confirmed = await self._confirm_m1_entry(symbol, proposal, df_m5)
            if not m1_confirmed:
                logger.info(
                    f"[{symbol}] M1 Gate → FAILED — no BOS+OFI confirmation on M1. "
                    f"Downgrading to STAND_DOWN."
                )
                final_payload = final_payload.model_copy(update={
                    "action": "STAND_DOWN",
                    "critic_veto_triggered": True,
                    "critic_notes": "[M1 CONFIRMATION FAILED] " + final_payload.critic_notes,
                })

        # Step 5: Atomic write to MQL5 shared directory
        output_file = self.bridge.publish_signal(final_payload)
        logger.info(f"[{symbol}] Payload saved → {output_file}")

        # Step 6: Record this cycle to Adaptive Memory (outcome=OPEN, updated later)
        # IMPROVEMENT_PLAN §0: استخدام حجم النقطة الصحيح لكل رمز بدلاً من 0.00001 الثابتة
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
        await self._recorder.record_signal(record)

        return final_payload

    async def _confirm_m1_entry(
        self,
        symbol: str,
        proposal,
        df_m5: pd.DataFrame,
    ) -> bool:
        """
        M1 Confirmation Gate (Improvement #4):
        Before writing the payload, verify a Market Structure Shift (BOS)
        exists on M1 in the direction of the proposed trade, combined with
        a confirmatory OFI reading (OFI Z > 0.4 for BUY, < -0.4 for SELL).

        IMPROVEMENT_PLAN §0: البوابات الحامية تمنع عند الخطأ (fail-closed).
        إذا كانت بيانات M1 غير كافية أو حدث خطأ، يتم الرفض لحماية رأس المال.
        """
        try:
            df_m1 = await self.data_provider.get_m1_bars(symbol, n=30)
            if len(df_m1) < 12:
                logger.warning("[%s] M1 gate rejected: Insufficient M1 data (%d < 12, fail-closed)", symbol, len(df_m1))
                return False

            action = proposal.proposed_action
            ofi_z = proposal.ofi_z_score

            # BOS check: higher high (BUY) or lower low (SELL) in last 5 M1 bars vs prior 5
            recent_high = float(df_m1["high"].iloc[-5:].max())
            prior_high  = float(df_m1["high"].iloc[-10:-5].max())
            recent_low  = float(df_m1["low"].iloc[-5:].min())
            prior_low   = float(df_m1["low"].iloc[-10:-5].min())

            if "BUY" in action:
                bos_ok = recent_high > prior_high            # Higher High on M1
                ofi_ok = ofi_z > 0.4                        # OFI confirms buying pressure
                return bos_ok and ofi_ok
            elif "SELL" in action:
                bos_ok = recent_low < prior_low             # Lower Low on M1
                ofi_ok = ofi_z < -0.4                       # OFI confirms selling pressure
                return bos_ok and ofi_ok

            return False
        except Exception as exc:
            logger.warning("[%s] M1 gate exception (fail-closed): %s", symbol, exc)
            return False  # fail-closed: خطأ بيانات M1 يمنع الدخول

    async def run_parallel_cycle(self, symbols: list[str]) -> Dict[str, SignalPayload]:
        """Executes the 4-Agent council concurrently across multiple Forex pairs."""
        tasks = [self.evaluate_symbol(sym) for sym in symbols]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results: Dict[str, SignalPayload] = {}
        for sym, res in zip(symbols, outcomes):
            if isinstance(res, BaseException):
                # fail-closed: لا إشارة لهذا الرمز، وبقية الرموز تكمل
                logger.error("[%s] cycle aborted, no payload published: %s", sym, res)
                continue
            results[res.symbol] = res
        return results


async def main() -> None:
    orchestrator = MultiAgentOrchestrator(
        mql5_shared_dir="./mql5_shared_signals",
        use_live_mt5=False,
    )
    watchlist = ["EURUSD", "GBPUSD", "XAUUSD"]
    results = await orchestrator.run_parallel_cycle(watchlist)

    print("\n" + "=" * 75)
    print("INSTITUTIONAL MULTI-AGENT COUNCIL CYCLE COMPLETE (MQL5 PAYLOAD SAMPLE)")
    print("=" * 75)
    print(results["EURUSD"].model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
