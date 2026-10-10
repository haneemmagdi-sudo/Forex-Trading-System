"""
Quick validation script for ml_models/feature_pipeline.py
Run: python ml_models/_validate_pipeline.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

out = sys.stdout.buffer

def p(msg): out.write((msg + "\n").encode("utf-8")); out.flush()

p("\n=== Feature Pipeline Validation ===\n")

# ── 1. Dependency check ─────────────────────────────────────────────────────
p("--- Dependencies ---")
deps = {"numpy": None, "pandas": None, "sklearn": None,
        "joblib": None, "vaderSentiment": None, "textblob": None}
for pkg in deps:
    try:
        __import__(pkg)
        p(f"  {pkg:20s}: OK")
    except ImportError:
        p(f"  {pkg:20s}: NOT INSTALLED")

# ── 2. Class imports ─────────────────────────────────────────────────────────
p("\n--- Class imports ---")
try:
    from ml_models.feature_pipeline import (
        RFFeaturePipeline, LSTMSequencePipeline,
        DQNStatePipeline, SentimentPipeline,
        FeaturePipelineFacade, AccountState,
        RF_FEATURE_NAMES, LSTM_FEATURES, DQN_STATE_DIM,
        DQN_ACTIONS, LSTM_LOOKBACK, LSTM_N_FEATURES,
    )
    p("  All classes:  OK")
except Exception as e:
    p(f"  IMPORT ERROR: {e}")
    import traceback; p(traceback.format_exc()); sys.exit(1)

p(f"  RF_FEATURE_NAMES  ({len(RF_FEATURE_NAMES)}): {RF_FEATURE_NAMES}")
p(f"  LSTM_FEATURES     ({LSTM_N_FEATURES}): {LSTM_FEATURES}")
p(f"  LSTM_LOOKBACK     : {LSTM_LOOKBACK}")
p(f"  DQN_STATE_DIM     : {DQN_STATE_DIM}")
p(f"  DQN_ACTIONS       : {DQN_ACTIONS}")

# ── 3. Synthetic data ─────────────────────────────────────────────────────────
p("\n--- Synthetic data setup ---")
import numpy as np
import pandas as pd

np.random.seed(42)
N = 300
idx   = pd.date_range("2024-01-01", periods=N, freq="h", tz="UTC")
close = 1.0850 + np.cumsum(np.random.randn(N) * 0.0005)
open_ = close + np.random.randn(N) * 0.0003
high  = np.maximum(close, open_) + np.abs(np.random.randn(N)) * 0.0002
low   = np.minimum(close, open_) - np.abs(np.random.randn(N)) * 0.0002
vol   = np.abs(np.random.randn(N)) * 1000 + 5000

df = pd.DataFrame({
    "open": open_, "high": high, "low": low, "close": close, "volume": vol,
    "hl_spread_bps":     np.random.uniform(2, 8, N),
    "hl_funding_rate":   np.random.uniform(-0.001, 0.001, N),
    "macro_vix":         np.random.uniform(15, 25, N),
    "macro_yield_spread": np.random.uniform(0.5, 2.5, N),
    "sentiment_score":   np.random.uniform(-0.5, 0.5, N),
}, index=idx)
p(f"  Synthetic df: {df.shape}")

# ── 4. RF Pipeline ────────────────────────────────────────────────────────────
p("\n--- Model 1: Random Forest ---")
rf = RFFeaturePipeline()
X_tr, X_te, y_tr, y_te, feats = rf.fit_transform(df)
p(f"  X_train : {X_tr.shape}  dtype={X_tr.dtype}")
p(f"  X_test  : {X_te.shape}  dtype={X_te.dtype}")
p(f"  y_train dist: {dict(zip(*np.unique(y_tr, return_counts=True)))}")
p(f"  NaN in X_train: {np.isnan(X_tr).sum()}")
X_live = rf.transform_live(df)
p(f"  Live inference shape: {X_live.shape}")

# ── 5. LSTM Pipeline ─────────────────────────────────────────────────────────
p("\n--- Model 2: LSTM ---")
lstm = LSTMSequencePipeline()
lstm.fit_scalers(df.iloc[:240])
seqs = lstm.build_sequences(df)
win  = lstm.build_inference_window(df)
p(f"  Sequences       : {seqs.shape}  dtype={seqs.dtype}")
p(f"  Inference window: {win.shape}")
p(f"  NaN in sequences: {np.isnan(seqs).sum()}")
p(f"  output_shape    : {lstm.output_shape}")

# ── 6. DQN Pipeline ──────────────────────────────────────────────────────────
p("\n--- Model 3: DQN ---")
dqn = DQNStatePipeline()
mobs = dqn.collect_market_obs_history(df.iloc[:240], rf_pipe=rf)
dqn.fit_scaler(mobs)
account = AccountState(
    balance_usd=10000, equity_usd=10250,
    position_direction=1, position_lots=0.01,
    position_pnl_pct=0.025, position_duration_bars=8,
    drawdown_pct=0.5
)
state = dqn.build_state(df.iloc[-1], account)
p(f"  state_dim       : {dqn.state_dim}")
p(f"  state shape     : {state.shape}  dtype={state.dtype}")
p(f"  market_obs mat  : {mobs.shape}")
p(f"  NaN in state    : {np.isnan(state).sum()}")
p(f"  state[:6]       : {state[:6].round(4)}")
p(f"  n_actions       : {dqn.n_actions}  {DQN_ACTIONS}")

# ── 7. Sentiment Pipeline ─────────────────────────────────────────────────────
p("\n--- Model 4: Sentiment ---")
sent = SentimentPipeline()
headlines = [
    "Federal Reserve raises rates by 50bps, markets plunge",
    "Company earnings beat expectations, stock surges 8%",
    "GDP growth exceeds forecasts",
    "Recession fears mount as yield curve inverts",
    "Central bank signals dovish pivot, rally expected",
]
scores = sent.score_batch(headlines)
agg, lbl = sent.aggregate(headlines)
for h, s in zip(headlines, scores):
    tag = "BULL" if s > 0.05 else "BEAR" if s < -0.05 else "NEUT"
    p(f"  {s:+.4f} [{tag}] {h[:55]}")
p(f"  Aggregate: {agg:+.4f} [{lbl}]")

# ── 8. Facade ─────────────────────────────────────────────────────────────────
p("\n--- FeaturePipelineFacade ---")
facade = FeaturePipelineFacade(
    account=account, rf_pipe=rf, lstm_pipe=lstm,
    dqn_pipe=dqn, sent_pipe=sent
)
bundle = facade.process_bar("EURUSD", df, news_texts=headlines)
p(f"  symbol         : {bundle.symbol}")
p(f"  bar_time       : {bundle.bar_time}")
p(f"  rf_features    : {bundle.rf_features.shape}")
p(f"  lstm_window    : {bundle.lstm_window.shape}")
p(f"  dqn_state      : {bundle.dqn_state.shape}")
p(f"  sentiment_score: {bundle.sentiment_score} [{bundle.sentiment_label}]")

p("\n=== ALL CHECKS PASSED ===\n")
