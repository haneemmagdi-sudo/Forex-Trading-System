"""
Quick standalone validation for ml_models/orchestrator.py
Run: python ml_models/_validate_orchestrator.py

Uses importlib.util to load orchestrator.py directly, bypassing
ml_models/__init__.py (which pulls in heavyweight OpenBB dependencies).
"""
import sys, os, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

out = sys.stdout.buffer
def p(msg): out.write((msg + "\n").encode("utf-8")); out.flush()

p("\n=== Orchestrator Validation ===\n")

# ── 1. Dependency check ─────────────────────────────────────────────────────
p("--- Dependencies ---")
for pkg in ["numpy"]:
    try:
        __import__(pkg)
        p(f"  {pkg:20s}: OK")
    except ImportError:
        p(f"  {pkg:20s}: NOT INSTALLED")
        sys.exit(1)

# ── 2. Direct module load (bypasses __init__.py) ─────────────────────────────
p("\n--- Imports ---")
try:
    _orch_path = os.path.join(os.path.dirname(__file__), "orchestrator.py")
    spec = importlib.util.spec_from_file_location("ml_models.orchestrator", _orch_path)
    _mod = importlib.util.module_from_spec(spec)
    sys.modules["ml_models.orchestrator"] = _mod
    spec.loader.exec_module(_mod)

    AntigravityOrchestrator = _mod.AntigravityOrchestrator
    OrchestratorSignal      = _mod.OrchestratorSignal
    ModelScore              = _mod.ModelScore
    Action                  = _mod.Action
    _normalise_rf           = _mod._normalise_rf
    _normalise_lstm_delta   = _mod._normalise_lstm_delta
    _normalise_dqn_qvalues  = _mod._normalise_dqn_qvalues
    _normalise_sentiment    = _mod._normalise_sentiment
    _DEFAULT_WEIGHTS        = _mod._DEFAULT_WEIGHTS
    _CONFIDENCE_THRESHOLD   = _mod._CONFIDENCE_THRESHOLD
    p("  All imports: OK")
except Exception as e:
    p(f"  IMPORT ERROR: {e}")
    import traceback; p(traceback.format_exc()); sys.exit(1)

p(f"  Default weights:    {_DEFAULT_WEIGHTS}")
p(f"  Default threshold:  {_CONFIDENCE_THRESHOLD}%")

# ── 3. Normalisation functions ───────────────────────────────────────────────
p("\n--- Normalisation tests ---")
import numpy as np

# RF
assert _normalise_rf(1)  ==  1.0
assert _normalise_rf(-1) == -1.0
assert _normalise_rf(0)  ==  0.0
p("  RF normalisation:   OK")

# LSTM delta
assert _normalise_lstm_delta(0.002)  ==  1.0    # ceiling
assert _normalise_lstm_delta(-0.002) == -1.0
assert _normalise_lstm_delta(0.001)  ==  0.5
assert _normalise_lstm_delta(0.0)    ==  0.0
p("  LSTM normalisation: OK")

# DQN Q-values
score = _normalise_dqn_qvalues([0.1, 0.9, 0.1, 0.0])   # BUY dominant
assert score > 0.5, f"Expected >0.5, got {score}"
score2 = _normalise_dqn_qvalues([0.1, 0.1, 0.9, 0.0])   # SELL dominant
assert score2 < -0.5, f"Expected <-0.5, got {score2}"
score3 = _normalise_dqn_qvalues([0.25, 0.25, 0.25, 0.25]) # Uniform
assert abs(score3) < 0.01, f"Expected ~0, got {score3}"
score4 = _normalise_dqn_qvalues([0.1, 0.05, 0.15, 0.70])  # CLOSE dominant
assert score4 == -0.3, f"Expected -0.3, got {score4}"
p("  DQN normalisation:  OK")

# Sentiment
assert _normalise_sentiment(0.5)   ==  0.5
assert _normalise_sentiment(-1.5)  == -1.0   # clipped
assert _normalise_sentiment(1.5)   ==  1.0   # clipped
p("  Sentiment norm:     OK")

# ── 4. Orchestrator creation ─────────────────────────────────────────────────
p("\n--- Orchestrator creation ---")
orch = AntigravityOrchestrator()
p(f"  {orch}")
p(f"  Weights:   {orch.weights}")
p(f"  Threshold: {orch.threshold}%")

# ── 5. Scenario: Strong BUY ──────────────────────────────────────────────────
p("\n--- Scenario 1: Strong BUY ---")
sig = orch.evaluate(
    rf_prediction=1,
    lstm_delta=0.0018,
    dqn_q_values=[0.05, 0.85, 0.08, 0.02],
    sentiment_score=0.55,
)
p(f"  {sig.summary()}")
p(f"  Confidence: {sig.confidence:.1f}%  (threshold: {sig.threshold}%)")
for ms in sig.model_scores:
    p(f"    {ms.model_name:15s} | score={ms.directional_score:+.4f} "
      f"| weight={ms.weight:.2f} | contribution={ms.weighted_contribution:+.4f}")
assert sig.action == Action.BUY, f"Expected BUY, got {sig.action}"
assert sig.confidence > 78.0
p("  ✓ PASS")

# ── 6. Scenario: Strong SELL ─────────────────────────────────────────────────
p("\n--- Scenario 2: Strong SELL ---")
sig2 = orch.evaluate(
    rf_prediction=-1,
    lstm_delta=-0.0020,
    dqn_q_values=[0.05, 0.02, 0.90, 0.03],
    sentiment_score=-0.70,
)
p(f"  {sig2.summary()}")
assert sig2.action == Action.SELL
assert sig2.confidence > 78.0
p("  ✓ PASS")

# ── 7. Scenario: Mixed → HOLD ────────────────────────────────────────────────
p("\n--- Scenario 3: Mixed → HOLD ---")
sig3 = orch.evaluate(
    rf_prediction=1,
    lstm_delta=-0.0005,
    dqn_q_values=[0.30, 0.25, 0.35, 0.10],
    sentiment_score=0.10,
)
p(f"  {sig3.summary()}")
assert sig3.action == Action.HOLD
p("  ✓ PASS")

# ── 8. Scenario: All neutral ─────────────────────────────────────────────────
p("\n--- Scenario 4: All neutral → HOLD (confidence=0%) ---")
sig4 = orch.evaluate(
    rf_prediction=0,
    lstm_delta=0.0,
    dqn_q_values=[0.25, 0.25, 0.25, 0.25],
    sentiment_score=0.0,
)
p(f"  {sig4.summary()}")
assert sig4.action == Action.HOLD
assert sig4.confidence == 0.0
p("  ✓ PASS")

# ── 9. to_dict serialisation ─────────────────────────────────────────────────
p("\n--- Serialisation test ---")
d = sig.to_dict()
assert d["action"] == "BUY"
assert "model_breakdown" in d
assert len(d["model_breakdown"]) == 4
p(f"  to_dict() keys: {list(d.keys())}")
p("  ✓ PASS")

# ── 10. Dynamic weight update ─────────────────────────────────────────────────
p("\n--- Dynamic weight update ---")
orch.update_weights({"rf": 0.20, "lstm": 0.35, "dqn": 0.30, "sentiment": 0.15})
p(f"  New weights: {orch.weights}")
assert orch.weights["lstm"] == 0.35
p("  ✓ PASS")

# ── 11. Dynamic threshold update ─────────────────────────────────────────────
p("\n--- Dynamic threshold update ---")
orch.update_threshold(85.0)
assert orch.threshold == 85.0
p(f"  New threshold: {orch.threshold}%")
p("  ✓ PASS")

# ── 12. Error handling ────────────────────────────────────────────────────────
p("\n--- Error handling ---")
try:
    bad = AntigravityOrchestrator(weights={"rf": 0.5, "lstm": 0.5, "dqn": 0.5, "sentiment": 0.5})
    p("  FAIL — should have raised ValueError for weights summing to 2.0")
    sys.exit(1)
except ValueError as e:
    p(f"  Bad weights caught: {e}")
    p("  ✓ PASS")

# ── 13. Diagnostics ──────────────────────────────────────────────────────────
p("\n--- Diagnostics ---")
state = orch.get_state()
p(f"  Signal count:     {state['signal_count']}")
p(f"  Action histogram: {state['action_histogram']}")
p(f"  Last signal:      {state['last_signal']['action']} "
  f"conf={state['last_signal']['confidence']}%")

# ── 14. Properties ───────────────────────────────────────────────────────────
p("\n--- Properties ---")
p(f"  last_signal.is_actionable: {orch.last_signal.is_actionable}")
p(f"  last_signal.direction:     {orch.last_signal.direction}")

p("\n=== ALL CHECKS PASSED ===\n")
