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
# Lazy loader for heavy dependencies to prevent massive startup latency on Windows
_LAZY_IMPORTS = {
    "prepare_ml_features": ("ml_models.pipeline", "prepare_ml_features"),
    "MLDataset": ("ml_models.pipeline", "MLDataset"),
    "transform_inference_row": ("ml_models.pipeline", "transform_inference_row"),
    "AntigravityOrchestrator": ("ml_models.orchestrator", "AntigravityOrchestrator"),
    "OrchestratorSignal": ("ml_models.orchestrator", "OrchestratorSignal"),
    "Action": ("ml_models.orchestrator", "Action"),
    "TimesFMForecaster": ("ml_models.timesfm_predictor", "TimesFMForecaster"),
    "build_orchestrator_feature_matrix": ("ml_models.feature_pipeline_v2", "build_orchestrator_feature_matrix"),
    "TimesFMFeaturePipelineFacade": ("ml_models.feature_pipeline_v2", "TimesFMFeaturePipelineFacade"),
    "AntigravityFeatureBundleV2": ("ml_models.feature_pipeline_v2", "AntigravityFeatureBundleV2"),
    "RF_V2_FEATURE_NAMES": ("ml_models.feature_pipeline_v2", "RF_V2_FEATURE_NAMES"),
    "DQN_V2_STATE_DIM": ("ml_models.feature_pipeline_v2", "DQN_V2_STATE_DIM"),
    "RollingWindowScaler": ("ml_models.utils", "RollingWindowScaler"),
    "safe_fill_series": ("ml_models.utils", "safe_fill_series"),
    "safe_fill_feature_matrix": ("ml_models.utils", "safe_fill_feature_matrix"),
    "validate_price_series": ("ml_models.utils", "validate_price_series"),
    "normalize_scalar": ("ml_models.utils", "normalize_scalar"),
    "clip_array": ("ml_models.utils", "clip_array"),
    "linear_trend_direction": ("ml_models.utils", "linear_trend_direction"),
    "build_zeroed_forecast_metrics": ("ml_models.utils", "build_zeroed_forecast_metrics"),
    "TimesFMFeatureExtractor": ("ml_models.timesfm_extractor", "TimesFMFeatureExtractor"),
    "QuantumFeaturePipeline": ("ml_models.feature_fusion", "QuantumFeaturePipeline"),
    "QuantumRFClassifier": ("ml_models.rf_classifier", "QuantumRFClassifier"),
    "RiskAdjustedRewardShaper": ("ml_models.risk_adjusted_reward", "RiskAdjustedRewardShaper"),
    "TradeTrajectorySnapshot": ("ml_models.risk_adjusted_reward", "TradeTrajectorySnapshot"),
    "CrossAssetGraphAgent": ("ml_models.cross_asset_agent", "CrossAssetGraphAgent"),
    "MacroFlowMetrics": ("ml_models.cross_asset_agent", "MacroFlowMetrics"),
}

def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        mod_name, attr_name = _LAZY_IMPORTS[name]
        import importlib
        mod = importlib.import_module(mod_name)
        val = getattr(mod, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# P3: كانت هنا استيرادات مباشرة (risk_adjusted_reward وcross_asset_agent) تُبطل الاستيراد الكسول أعلاه.
# أصبحت ضمن _LAZY_IMPORTS: تُحمَّل عند أول وصول فقط (ml_models.CrossAssetGraphAgent ... لا تزال تعمل).

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
