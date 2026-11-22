"""
=============================================================================
backend/backtest_walkforward.py — Walk-Forward Backtest Execution & Edge Verification
=============================================================================
Architectural Authority: IMPROVEMENT_PLAN (Phase 2 & Phase 3)
Usage:
  python backend/backtest_walkforward.py --symbol EURUSD --bars 2000
  python backend/backtest_walkforward.py --symbol GBPUSD --bars 3000 --export-dataset

Key Features:
- Connects to MT5 to fetch real historical bars if available, or generates realistic jump-diffusion price data.
- Strict accounting of spread and broker commission.
- Outputs Bailey & Lopez de Prado Deflated Sharpe Ratio (DSR) to avoid data snooping.
- Evaluates against Monte Carlo Random Entry Baselines.
- Prepares and exports verified (X, y) datasets for Meta-Labeling.
=============================================================================
"""

import argparse
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# Path normalization
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from quant_core.backtester import WalkForwardBacktester
from quant_core.labeling import StatisticalEdgeValidator
from backend.config import STRATEGY


def fetch_historical_bars(symbol: str, timeframe_str: str, num_bars: int, source: str = "auto") -> pd.DataFrame:
    """Fetches historical bars from MT5/yfinance or realistic geometric jump-diffusion."""
    if source in ("auto", "mt5"):
        try:
            from backend.core.mt5_connector import MT5Connector
            connector = MT5Connector()
            if connector.connect():
                df = connector.get_ohlcv(symbol, bars=num_bars)  # P0 fix: valid MT5Connector method
                if df is not None and len(df) > 50:
                    print(f"✅ Fetched {len(df)} bars via MT5Connector for {symbol}")
                    return df
        except Exception as exc:
            print(f"⚠️ Live market data fetch skipped ({exc}). Using synthetic realistic geometric jump-diffusion.")

    # High-fidelity synthetic price generation (GBM + Jump Diffusion)
    np.random.seed(42)
    dt = 1.0 / (252.0 * 24.0)
    mu = 0.0002
    sigma = 0.008

    prices = [1.0850 if "EUR" in symbol else (1.2700 if "GBP" in symbol else 150.0)]
    for _ in range(num_bars):
        drift = (mu - 0.5 * sigma ** 2) * dt
        shock = sigma * math.sqrt(dt) * np.random.normal()
        jump = np.random.normal(0, 0.002) if np.random.rand() < 0.02 else 0.0
        ret = drift + shock + jump
        prices.append(prices[-1] * math.exp(ret))

    prices = np.array(prices[:num_bars])
    highs = prices * (1.0 + np.abs(np.random.normal(0, 0.0008, num_bars)))
    lows = prices * (1.0 - np.abs(np.random.normal(0, 0.0008, num_bars)))
    opens = prices * (1.0 + np.random.normal(0, 0.0003, num_bars))

    df = pd.DataFrame({
        "time": pd.date_range(end=datetime.now(timezone.utc), periods=num_bars, freq="1h"),
        "open": opens,
        "high": np.maximum(highs, np.maximum(opens, prices)),
        "low": np.minimum(lows, np.minimum(opens, prices)),
        "close": prices,
        "tick_volume": np.random.randint(50, 500, num_bars),
    })
    return df


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Quantitative Backtester")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Trading symbol (e.g. EURUSD, GBPUSD, USDJPY)")
    parser.add_argument("--bars", type=int, default=1500, help="Number of historical bars to evaluate")
    parser.add_argument("--timeframe", type=str, default="H1", help="Timeframe (e.g. M15, H1, H4)")
    parser.add_argument("--source", type=str, default="synthetic", choices=["auto", "mt5", "synthetic"], help="Data source")
    parser.add_argument("--export-dataset", action="store_true", help="Export (X, y) feature dataset for Meta-Labeling")
    args = parser.parse_args()

    print(f"\n🚀 Initializing Walk-Forward Backtester for {args.symbol} ({args.bars} bars on {args.timeframe}, source={args.source})...")
    df = fetch_historical_bars(args.symbol, args.timeframe, args.bars, source=args.source)

    # Load symbol-specific spread from config
    spread_limits = STRATEGY.get("symbol_spread_limits", {})
    # P0 fix: symbol_spread_limits in config.py is already denominated in pips
    spread_pips = float(spread_limits.get(args.symbol, 3.0))

    backtester = WalkForwardBacktester(
        pt_atr_mult=2.0,
        sl_atr_mult=1.5,
        max_holding_bars=24,
        spread_pips=spread_pips,
        commission_pips=0.7,
        min_vote_score=STRATEGY.get("min_vote_score", 3.5),
        num_windows=3,
        train_ratio=0.6,
    )

    result = backtester.run_walk_forward(df, symbol=args.symbol)
    print("\n" + result.summary())

    if args.export_dataset:
        out_dir = os.path.join(BASE_DIR, "models")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"meta_dataset_{args.symbol}.csv")

        # Convert candidate signals to dataframe
        records = []
        for cand in result.candidate_signals:
            rec = dict(cand["features"])
            rec["symbol"] = cand["symbol"]
            rec["vote_direction"] = cand["vote_direction"]
            rec["executed"] = cand["executed"]
            rec["label"] = cand["label"]
            records.append(rec)

        meta_df = pd.DataFrame(records)
        meta_df.to_csv(out_path, index=False)
        print(f"\n💾 Successfully exported {len(meta_df)} candidate feature rows to {out_path}")


if __name__ == "__main__":
    main()
