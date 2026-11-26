# Task: run the replay-backtest CONTROL/DIAGNOSTIC experiments (read-only research — NO live trading)

Project root: `F:\config\Forex Trading System` (PowerShell). The data already exported in `data\replay\*.csv` is reused (do NOT re-export). Every run uses commission 7$ per lot (round turn) and the 70/30 split.

## Hard rules
- No trading orders, do not start the live system, do not open MT5 for anything. This only reads CSV files.
- Do NOT edit `.env`, `*.db`, `backend/models/*_state.json`, `mql5_shared_signals/*`, or anything under `backend/`, `council/`, `config/`.
- Do NOT tune or "improve" anything. Run exactly the commands below, in this order, and report numbers as they are.
- No `git push --force`. Ask me before any commit/push. Do not commit `backtest\out*`, `backtest\x*`, logs, or `data\replay`.

## 1. Update and verify
```powershell
cd "F:\config\Forex Trading System"
git pull --ff-only
$env:PYTHONPATH = "."
python -m unittest tests.test_replay_backtest -v        # expect: Ran 24 tests ... OK
```
If it fails, STOP and report the exact output. The pull brings `backtest\replay_backtest.py` (new options `--signal-mode`, `--seed`, `--regimes`, `--path-order`, and an entry-signal cache in `backtest\out_cache`).

## 2. Regression check (must reproduce the previous result exactly)
This first run also builds the signal cache (it takes about as long as the earlier runs; later runs are much faster).
```powershell
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --out backtest\x0_base 2>&1 | Tee-Object backtest\x0_base.log
```
Expected, identical to the earlier `out_v3_comm7`: baskets n = 2099, net = -197.32, final_equity = 800.97. If ANY of these differ, STOP and report both sets of numbers; do not run the rest.

## 3. Experiments (run sequentially, each with `Tee-Object` to a log named like the output folder)
```powershell
# Controls: same entry timing/ATR/regime as the real signals, but direction random (3 seeds) or inverted
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --signal-mode random --seed 1 --out backtest\x1_random_s1
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --signal-mode random --seed 2 --out backtest\x1_random_s2
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --signal-mode random --seed 3 --out backtest\x1_random_s3
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --signal-mode invert --out backtest\x2_invert
# No grid (no averaging down)
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --set grid_distance_pips=100000 --out backtest\x3_nogrid
# Trend-regime only
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --regimes STRONG_TREND --out backtest\x4_strongtrend
# Intrabar path robustness (worst / best case relative to open positions)
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --path-order adverse --out backtest\x5_adverse
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --path-order favorable --out backtest\x5_favorable
# Pre-specified combination (both ideas had an a-priori rationale)
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --regimes STRONG_TREND --set grid_distance_pips=100000 --out backtest\x6_strongtrend_nogrid
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --regimes STRONG_TREND --set grid_distance_pips=100000 --path-order adverse --out backtest\x7_strongtrend_nogrid_adverse
```
Every command carries the same two flags (`--oos-fraction 0.3 --commission-per-lot 7`); they must not change.

## 4. Final report (write it in Arabic)
One table with a row per run (x0, x1 s1/s2/s3, x2, x3, x4, x5 adverse/favorable, x6, x7) with, from `report.json` (`all.baskets`): n, win_rate and 95% CI, payoff_ratio, breakeven_win_rate, expectancy, profit_factor, t_stat, net, return_pct, max_equity_drawdown_pct. Then:
- the same fields for `in_sample` and `out_of_sample` of every run,
- for the three random seeds: the mean and the min/max of expectancy and profit_factor,
- `by_regime` and `by_exit_reason` for x0, x3 and x4,
- `entry_rejections` and `signals_passing_pipeline` for every run,
- warnings printed, commands run, and anything that failed.
Report numbers only. Do not interpret them as a trading recommendation, do not suggest parameter changes, and do not pick a "best" run. I will review them with Claude.
