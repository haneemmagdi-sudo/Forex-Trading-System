"""
=============================================================================
quant_core/labeling.py — Institutional Triple-Barrier & Statistical Metrics
=============================================================================
Architectural Authority: .antigravityrules & IMPROVEMENT_PLAN (Phase 2 & Phase 3)
Reference: Marcos Lopez de Prado (Advances in Financial Machine Learning, 2018)

Implements:
1. Triple-Barrier Labeling:
   - Upper barrier (profit-taking, dynamic ATR multiple)
   - Lower barrier (stop-loss, dynamic ATR multiple)
   - Vertical barrier (holding period horizon, max candles)
   - Realistic cost deduction: bid/ask spread + commission
   - Output labels: +1 (Win), -1 (Loss), 0 (Timeout / Breakeven)

2. Quantitative Backtest & Edge Metrics:
   - Net Expectancy (per trade after costs)
   - Profit Factor, Win Rate, Max Drawdown
   - Deflated Sharpe Ratio (DSR - Bailey & Lopez de Prado 2014)
   - Monte Carlo Random Entry Baseline for true edge validation
=============================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis


@dataclass
class BarrierEvent:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    direction: int                # +1 (BUY) or -1 (SELL)
    barrier_hit: str              # "UPPER", "LOWER", "VERTICAL"
    label: int                    # +1, -1, or 0
    pnl_pips: float
    net_return_pct: float
    holding_bars: int


@dataclass
class QuantitativeEdgeReport:
    total_trades: int
    win_rate: float
    profit_factor: float
    net_expectancy_pips: float
    max_drawdown_pct: float
    annualized_sharpe: float
    deflated_sharpe_ratio: float
    is_edge_significant: bool     # True if DSR > 0.95 (statistically significant edge)
    random_baseline_expectancy: float
    edge_over_random_pips: float


class TripleBarrierLabeler:
    """
    Vectorized & candle-level Triple-Barrier Labeling Engine.
    Converts raw OHLCV price histories into clean ML targets.
    """

    def __init__(
        self,
        pt_atr_mult: float = 2.0,
        sl_atr_mult: float = 1.5,
        max_holding_bars: int = 24,
        cost_pips: float = 1.5,
    ):
        self.pt_mult = pt_atr_mult
        self.sl_mult = sl_atr_mult
        self.max_holding = max_holding_bars
        self.cost_pips = cost_pips

    def label_candle_series(
        self,
        df: pd.DataFrame,
        symbol: str,
        direction: int = 1,
        atr_col: str = "atr",
    ) -> List[BarrierEvent]:
        """
        Labels all candles in df with triple-barrier outcomes.
        df must contain ['open', 'high', 'low', 'close'] and ATR.
        direction: +1 for BUY, -1 for SELL.
        """
        if df is None or len(df) < self.max_holding + 10:
            return []

        pip_size = 0.01 if "JPY" in symbol.upper() else (0.1 if "XAU" in symbol.upper() else 0.0001)

        # Ensure ATR is calculated
        if atr_col not in df.columns:
            high = df["high"]
            low = df["low"]
            close = df["close"]
            prev_close = close.shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs()
            ], axis=1).max(axis=1)
            atr_series = tr.rolling(14).mean().bfill()
        else:
            atr_series = df[atr_col]

        events: List[BarrierEvent] = []
        n = len(df)
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        atrs = atr_series.values

        for i in range(14, n - self.max_holding):
            entry_p = closes[i]
            cur_atr = atrs[i]
            if cur_atr <= 0 or np.isnan(cur_atr):
                continue

            pt_dist = cur_atr * self.pt_mult
            sl_dist = cur_atr * self.sl_mult

            if direction == 1:  # BUY
                upper_barrier = entry_p + pt_dist
                lower_barrier = entry_p - sl_dist
            else:  # SELL
                upper_barrier = entry_p - pt_dist
                lower_barrier = entry_p + sl_dist

            hit = "VERTICAL"
            exit_p = closes[i + self.max_holding]
            exit_idx = i + self.max_holding

            # Scan future bars
            for h in range(1, self.max_holding + 1):
                idx = i + h
                bar_high = highs[idx]
                bar_low = lows[idx]

                if direction == 1:  # BUY
                    if bar_low <= lower_barrier:
                        hit = "LOWER"
                        exit_p = lower_barrier
                        exit_idx = idx
                        break
                    elif bar_high >= upper_barrier:
                        hit = "UPPER"
                        exit_p = upper_barrier
                        exit_idx = idx
                        break
                else:  # SELL
                    if bar_high >= lower_barrier:
                        hit = "LOWER"
                        exit_p = lower_barrier
                        exit_idx = idx
                        break
                    elif bar_low <= upper_barrier:
                        hit = "UPPER"
                        exit_p = upper_barrier
                        exit_idx = idx
                        break

            # Calculate Net PnL in Pips after spread/commission
            raw_pips = ((exit_p - entry_p) / pip_size) if direction == 1 else ((entry_p - exit_p) / pip_size)
            net_pips = raw_pips - self.cost_pips
            ret_pct = ((exit_p - entry_p) / entry_p) if direction == 1 else ((entry_p - exit_p) / entry_p)

            if hit == "UPPER":
                label = 1
            elif hit == "LOWER":
                label = -1
            else:
                label = 1 if net_pips > 0 else (-1 if net_pips < 0 else 0)

            events.append(BarrierEvent(
                entry_index=i,
                exit_index=exit_idx,
                entry_price=entry_p,
                exit_price=exit_p,
                direction=direction,
                barrier_hit=hit,
                label=label,
                pnl_pips=round(net_pips, 2),
                net_return_pct=round(ret_pct, 6),
                holding_bars=exit_idx - i,
            ))

        return events


class StatisticalEdgeValidator:
    """
    Computes rigorous statistical metrics for backtest validation.
    Includes Deflated Sharpe Ratio (DSR) to guard against data snooping.
    """

    @staticmethod
    def compute_deflated_sharpe_ratio(
        returns: np.ndarray,
        num_trials: int = 1,
        benchmark_sharpe: float = 0.0,
    ) -> float:
        """
        Calculates the Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).
        Adjusts the estimated Sharpe ratio for:
          - Non-normality (skewness and excess kurtosis)
          - Multiple testing across N trial configurations
          - Sample size / track record length
        """
        if len(returns) < 5 or np.std(returns) == 0:
            return 0.0

        n = len(returns)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        sr = (mean_ret / std_ret) * math.sqrt(252 * 24)  # Annualized (hourly basis)

        gamma_skew = float(skew(returns))
        gamma_kurt = float(kurtosis(returns, fisher=True))

        # Expected maximum Sharpe ratio under null hypothesis (Euler-Mascheroni constant)
        if num_trials > 1:
            euler_mascheroni = 0.5772156649
            expected_max_sr = (
                (1.0 - euler_mascheroni) * norm.ppf(1.0 - 1.0 / num_trials)
                + euler_mascheroni * norm.ppf(1.0 - 1.0 / (num_trials * math.e))
            )
        else:
            expected_max_sr = benchmark_sharpe

        # Standard error of Sharpe ratio accounting for non-normality
        var_sr = (1.0 + 0.5 * (sr ** 2) - gamma_skew * sr + 0.25 * gamma_kurt * (sr ** 2)) / max(n - 1, 1)
        sigma_sr = math.sqrt(max(var_sr, 1e-8))

        # DSR = CDF of standard normal
        z_stat = (sr - expected_max_sr) / sigma_sr
        dsr = float(norm.cdf(z_stat))
        return dsr

    @classmethod
    def evaluate_performance(
        cls,
        pnl_series: List[float],
        num_trials: int = 10,
        random_baseline_runs: int = 100,
    ) -> QuantitativeEdgeReport:
        """
        Comprehensive edge validation report.
        """
        if not pnl_series:
            return QuantitativeEdgeReport(
                total_trades=0, win_rate=0.0, profit_factor=0.0,
                net_expectancy_pips=0.0, max_drawdown_pct=0.0,
                annualized_sharpe=0.0, deflated_sharpe_ratio=0.0,
                is_edge_significant=False, random_baseline_expectancy=0.0,
                edge_over_random_pips=0.0
            )

        arr = np.array(pnl_series, dtype=float)
        wins = arr[arr > 0]
        losses = arr[arr < 0]

        total = len(arr)
        win_rate = (len(wins) / total) * 100.0 if total > 0 else 0.0

        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 1e-9
        profit_factor = round(gross_profit / gross_loss, 2)

        expectancy = float(np.mean(arr))

        # Max Drawdown
        cum_pnl = np.cumsum(arr)
        running_max = np.maximum.accumulate(cum_pnl)
        drawdowns = running_max - cum_pnl
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Sharpe & DSR
        std_pnl = np.std(arr, ddof=1) if len(arr) > 1 else 1.0
        ann_sharpe = float((expectancy / max(std_pnl, 1e-6)) * math.sqrt(252))
        dsr = cls.compute_deflated_sharpe_ratio(arr, num_trials=num_trials)

        # Random Entry Baseline: simulated random flips on same trades
        rng = np.random.default_rng(42)
        random_expectancies = []
        for _ in range(random_baseline_runs):
            random_signs = rng.choice([-1, 1], size=total)
            random_pnl = np.abs(arr) * random_signs - 1.5  # minus spread
            random_expectancies.append(np.mean(random_pnl))
        baseline_exp = float(np.mean(random_expectancies))

        edge_over_random = expectancy - baseline_exp
        is_significant = (dsr >= 0.95) and (edge_over_random > 0.0)

        return QuantitativeEdgeReport(
            total_trades=total,
            win_rate=round(win_rate, 1),
            profit_factor=profit_factor,
            net_expectancy_pips=round(expectancy, 2),
            max_drawdown_pct=round(max_dd, 2),
            annualized_sharpe=round(ann_sharpe, 2),
            deflated_sharpe_ratio=round(dsr, 4),
            is_edge_significant=is_significant,
            random_baseline_expectancy=round(baseline_exp, 2),
            edge_over_random_pips=round(edge_over_random, 2),
        )
