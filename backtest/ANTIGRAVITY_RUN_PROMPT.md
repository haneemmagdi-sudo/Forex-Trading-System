# Task: run the MT5 replay backtest (read-only research run — NO live trading)

Project root: `F:\config\Forex Trading System` (PowerShell). Branch: current (`chore/baseline-snapshot`).

## Hard rules
- DEMO account only. Before exporting, confirm the logged-in MT5 account is a demo (`mt5.account_info().trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO`). If it is not demo, STOP and tell me.
- Do NOT send any trading order. Do NOT start the live system (`Start_System.bat`, orchestrators). The tool only reads history.
- Do NOT edit `.env`, `*.db`, `backend/models/*_state.json`, `mql5_shared_signals/*`, or any file under `backend/`, `council/`, `config/`.
- Do NOT tune parameters to improve the numbers. Run exactly the commands below and report what comes out.
- No `git push --force`. Ask me before any commit or push.

## 1. Verify files are in place
Copy the files from the zip into the project (do not overwrite anything else): `backtest\replay_backtest.py`, `backtest\__init__.py`, `backtest\README.md`, `backtest\ANTIGRAVITY_RUN_PROMPT.md`, `tests\test_replay_backtest.py`.
Then APPEND (do not replace the file) these two lines to `.gitignore` if they are not already there: `data/replay/` and `backtest/out*/`.
```powershell
cd "F:\config\Forex Trading System"
git status --short
python -m pip install MetaTrader5 pandas numpy
```

## 2. Tests must pass first
```powershell
$env:PYTHONPATH = "."
python -m unittest tests.test_replay_backtest -v          # expect: Ran 19 tests ... OK
python -m unittest tests.test_basket_per_symbol_atr tests.test_basket_magic_filter tests.test_p5_monitor_agent tests.test_no_package_name_collision   # expect OK
```
If anything fails, STOP and report the exact output.

## 3. Export history (read-only)
Open MT5 (demo) and make sure it is logged in. In MT5: Tools > Options > Charts > "Max bars in chart" >= 100000, and scroll each chart back once so the history is downloaded.
```powershell
python backtest\replay_backtest.py export --days 365 --symbols EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,NZDUSD,EURJPY,GBPJPY,EURGBP
```
Report bars per symbol, first/last timestamp, median spread. A full year of H1 is roughly 6000 bars per symbol; warn me if a symbol has far fewer.

## 4. Smoke run (fast), then the real runs
```powershell
python backtest\replay_backtest.py run --symbols EURUSD --from 2026-09-01 --out backtest\out_smoke
```
If it finishes without errors, run these three (each can take 20+ minutes: run them one after another and log to files):
```powershell
python backtest\replay_backtest.py run --oos-fraction 0.3 --out backtest\out_v3                                  2>&1 | Tee-Object backtest\run_v3.log
python backtest\replay_backtest.py run --oos-fraction 0.3 --legacy-basket --out backtest\out_legacy               2>&1 | Tee-Object backtest\run_legacy.log
python backtest\replay_backtest.py run --oos-fraction 0.3 --commission-per-lot 7 --out backtest\out_v3_comm7      2>&1 | Tee-Object backtest\run_v3_comm7.log
```

## 5. Final report (write it in Arabic)
For each of the three runs give a compact table from `report.json` (`all.baskets`): n, win_rate and its 95% CI, payoff_ratio, breakeven_win_rate, expectancy, profit_factor, net, return_pct, max_equity_drawdown_pct. Then:
- in_sample vs out_of_sample baskets (same fields),
- `by_symbol`, `by_exit_reason`, `by_regime` for the v3 run,
- `entry_rejections` and `signals_passing_pipeline`,
- any warnings printed (missing CSVs, "approximating pip value", fewer than 100 baskets),
- the commands you ran and anything that failed.
State the numbers as they are. Do not interpret them as a trading recommendation and do not suggest parameter changes; I will review them with Claude.

## 6. Git
Do not commit CSVs, logs, or `backtest\out*`. Ask me before committing only: `backtest/`(scripts + README + prompt), `tests/test_replay_backtest.py`, `.gitignore`.
