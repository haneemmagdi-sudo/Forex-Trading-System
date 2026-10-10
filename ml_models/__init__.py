"""
ml_models — Antigravity machine learning models and pipelines.

Modules
-------
pipeline.py
    Legacy feature preparation utilities (``prepare_ml_features``, etc.).

orchestrator.py
    Weighted consensus engine (``AntigravityOrchestrator``).

feature_pipeline.py
    Classical ML feature pipelines:
    ``RFFeaturePipeline``, ``LSTMSequencePipeline``,
    ``DQNStatePipeline``, ``SentimentPipeline``.

timesfm_predictor.py  [TimesFM Core Upgrade]
    Google TimesFM zero-shot forecasting engine (``TimesFMForecaster``).

feature_pipeline_v2.py  [TimesFM Core Upgrade]
    Upgraded multi-model feature aggregator:
    ``build_orchestrator_feature_matrix``,
    ``TimesFMFeaturePipelineFacade``,
    ``AntigravityFeatureBundleV2``.

utils.py  [TimesFM Core Upgrade]
    Safety & scaling middleware:
    ``RollingWindowScaler``, ``safe_fill_series``,
    ``safe_fill_feature_matrix``, ``validate_price_series``.
"""
try:
    from ml_models.pipeline import prepare_ml_features, MLDataset, transform_inference_row
    from ml_models.orchestrator import AntigravityOrchestrator, OrchestratorSignal, Action
    from ml_models.timesfm_predictor import TimesFMForecaster
    from ml_models.feature_pipeline_v2 import (
        build_orchestrator_feature_matrix,
        TimesFMFeaturePipelineFacade,
        AntigravityFeatureBundleV2,
        RF_V2_FEATURE_NAMES,
        DQN_V2_STATE_DIM,
    )
    from ml_models.utils import (
        RollingWindowScaler,
        safe_fill_series,
        safe_fill_feature_matrix,
        validate_price_series,
        normalize_scalar,
        clip_array,
        linear_trend_direction,
        build_zeroed_forecast_metrics,
    )
    from ml_models.timesfm_extractor import TimesFMFeatureExtractor
    from ml_models.feature_fusion import QuantumFeaturePipeline
    from ml_models.rf_classifier import QuantumRFClassifier
except ImportError:
    pass

from ml_models.risk_adjusted_reward import RiskAdjustedRewardShaper, TradeTrajectorySnapshot
from ml_models.cross_asset_agent import CrossAssetGraphAgent, MacroFlowMetrics

__all__ = [
    # ── Legacy pipeline ──────────────────────────────────────────────────
    "prepare_ml_features",
    "MLDataset",
    "transform_inference_row",
    # ── Orchestrator ─────────────────────────────────────────────────────
    "AntigravityOrchestrator",
    "OrchestratorSignal",
    "Action",
    # ── TimesFM Core Upgrade ─────────────────────────────────────────────
    "TimesFMForecaster",
    "build_orchestrator_feature_matrix",
    "TimesFMFeaturePipelineFacade",
    "AntigravityFeatureBundleV2",
    "RF_V2_FEATURE_NAMES",
    "DQN_V2_STATE_DIM",
    # ── Safety & Scaling Middleware ───────────────────────────────────────
    "RollingWindowScaler",
    "safe_fill_series",
    "safe_fill_feature_matrix",
    "validate_price_series",
    "normalize_scalar",
    "clip_array",
    "linear_trend_direction",
    "build_zeroed_forecast_metrics",
    # ── Foundation Model Features & Classifier ───────────────────────────
    "TimesFMFeatureExtractor",
    "QuantumFeaturePipeline",
    "QuantumRFClassifier",
]
