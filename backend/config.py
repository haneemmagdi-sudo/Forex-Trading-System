"""
============================================================
config.py — إعدادات نظام التداول الكاملة
============================================================
عدّل هذا الملف بإعداداتك الخاصة قبل التشغيل
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bridge root config package so 'import config.settings' works seamlessly
_root_config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
__path__ = [_root_config_dir]
try:
    import sys
    if _root_config_dir not in sys.path:
        sys.path.append(_root_config_dir)
    import settings as _st
    settings = getattr(_st, "settings", None)
    get_settings = getattr(_st, "get_settings", None)
except Exception:
    settings = None
    get_settings = None


# ============================================================
# 🔌 إعدادات MT5
# ============================================================
MT5 = {
    "login":    int(os.getenv("MT5_LOGIN",    "0")),          # رقم حسابك
    "password": os.getenv("MT5_PASSWORD",     "your_password"),
    "server":   os.getenv("MT5_SERVER",       "ICMarkets-Demo"),
    "path":     os.getenv("MT5_TERMINAL_PATH", ""),
    "timeout":  10_000,   # ميلي ثانية
    "portable": False,
}

# ============================================================
# 🔢 سجل أرقام Magic الموحد (IMPROVEMENT_PLAN §6)
# ============================================================
MAGIC_NUMBERS = {
    "live_engine":    112345,   # المحرك الحي الرئيسي
    "shadow_council": 20261016, # صفقات/قرارات الظل
    "grid_engine":    112346,   # شبكة التعزيز
}

# ============================================================
# 📊 أزواج العملات المدعومة
# ============================================================
SYMBOLS = [
    # ── الأزواج الرئيسية والتقاطعات الـ 10 الأكثر سيولة عالمياً ────────
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP",
]
PRIMARY_SYMBOL = "EURUSD"

# ============================================================
# ⚙️ إعدادات الاستراتيجية (تطابق Blessing Pro V4.2)
# ============================================================
STRATEGY = {
    # الحماية
    "max_dd_percent":      5.0,   # إيقاف طوارئ عند هذا التراجع
    "soft_dd_percent":     3.0,   # وضع حذر
    "hedge_dd_percent":    2.5,   # تفعيل التحوط
    # IMPROVEMENT_PLAN §0: max_spread_pips لكل رمز (مشدَّد من 25 الوهمية)
    # القيم بوحدة البيب حسب MT5Connector.get_pip_size: 0.0001 للأزواج الرئيسية، 0.01 للين والفضة، 0.1 للذهب
    # (P3: MT5Connector.get_tick يُرجع السبريد بنفس الوحدة لكل الرموز → تطابق تام مع هذه الحدود)
    "max_spread_pips":     4.0,   # حد افتراضي للأزواج الرئيسية
    "symbol_spread_limits": {
        "EURUSD": 3.0, "GBPUSD": 4.0, "USDJPY": 3.0, "AUDUSD": 4.0,
        "USDCAD": 4.0, "USDCHF": 4.0, "NZDUSD": 5.0, "EURJPY": 5.0,
        "GBPJPY": 7.0, "EURGBP": 4.0, "XAUUSD": 4.0,  "XAGUSD": 50.0,   # P3: XAUUSD بالبيب (1 بيب = 0.10$) → 4.0 = 0.40$ (كانت 40.0 بوحدة 0.01$)
    },

    # إدارة المخاطر
    "risk_percent":        1.0,   # المخاطرة لكل صفقة (%)
    "sl_atr_multiplier":   2.5,   # SL = ATR × هذا
    "tp_rr_ratio":         2.0,   # TP = SL × هذا (RR 1:2)
    "trail_atr_multiplier":1.5,   # Trailing Stop
    "manual_lot_enabled":  True,  # تفعيل حجم اللوت اليدوي
    "fixed_lot_size":      0.01,  # الحد الأدنى للوت (0.01 لكل الأزواج)
    "min_lot_size":        0.01,  # الحد الأدنى المطلق
    "use_dynamic_sl":      False, # تعطيل الستوب لوس والتيك بروفيت الفردي
    # P5: مفاتيح إدارة الصفقة المفتوحة في MonitorAgent — مستقلة عن use_dynamic_sl
    # (قبل P5 كان use_dynamic_sl=False يُوقف كل الإدارة فيصير الوكيل بلا أثر على الصفقات)
    "monitor_breakeven_enabled": True,   # نقل SL لنقطة التعادل (+2 بيب) عند ربح >= breakeven_pips
    "monitor_trailing_enabled":  True,   # وقف متحرك عند ربح >= trail_activate_pips (يتحرك في اتجاه الربح فقط)
    "monitor_partial_enabled":   False,  # إغلاق جزئي: معطّل لأن لوت 0.01 لا يُقسَّم (راجع P5_CHANGELOG)
    "monitor_manage_untracked":  True,   # إدارة صفقات بلا سجل DB إن كان magic ضمن MAGIC_NUMBERS
    "monitor_heartbeat_cycles":  60,     # سطر حالة في السجل كل N دورة (يُظهر أن الوكيل يعمل)
    "emergency_hard_sl_enabled": True,  # P0: وقف خسارة طوارئ على خادم MT5 عند تعطيل SL الديناميكي لحماية الحساب عند انقطاع الاتصال
    "emergency_hard_sl_atr_mult": 5.0,  # مضاعف ATR لوقف الخسارة الكارثي على الخادم
    "basket_sl_atr_mult": 2.5,   # basket stop = this x entry ATR
    "basket_rr":          1.0,   # basket target = basket_rr x stop distance (1.0 = 1:1)
    "base_target_usd":     2.0,   # هدف السلة بالدولار — مسار احتياطي فقط حين يتعذّر ATR أو تكون السلة متحوِّطة
    "basket_max_loss_usd": 20.0,  # IMPROVEMENT_PLAN §0: سقف خسارة السلة (لكل رمز) بالدولار — شبكة أمان أخيرة فوق وقف ATR
    "basket_filter_by_magic": True,  # قصر حساب وإغلاق هدف/وقف السلة على صفقات MAGIC_NUMBERS فقط (عدم لمس الصفقات اليدوية)

    # الشبكة
    "max_open_trades":     5,     # أقصى صفقات مفتوحة (مخفَّض من 10 إلى 5 للحد من مخاطر التعزيز)
    "grid_distance_pips":  25,    # المسافة بين صفقات الشبكة

    # التصويت
    "min_vote_score":      3.5,   # الحد الأدنى لفتح صفقة
    "required_fsm_states": ["SLOW_TREND", "STRONG_TREND", "LOW_VOL"],

    # الإغلاق الجزئي (Ladder)
    "partial_tp_l1_pips":  10.0,  # إغلاق 30%
    "partial_tp_l2_pips":  20.0,  # إغلاق 50%
    "partial_tp_l3_pips":  35.0,  # إغلاق 70%
    "breakeven_pips":      20.0,  # نقل SL لنقطة التعادل
    "trail_activate_pips": 40.0,  # تفعيل Trailing

    # حماية Cascade
    "cascade_max_losses":  3,     # إيقاف بعد N خسائر
    "cascade_cooldown_min":30,    # انتظر N دقيقة

    # التحوط
    "hedge_lot_factor":    0.7,   # حجم اللوت عند التحوط
}

# ============================================================
# 🕐 إعدادات الجلسات
# ============================================================
SESSIONS = {
    "london": {"start": 7,  "end": 16},  # GMT
    "new_york":{"start": 13, "end": 22}, # GMT
    "asia":   {"start": 22, "end": 7},   # GMT — معطّل افتراضياً
    "trade_london":   True,
    "trade_new_york": True,
    "trade_asia":     False,
}

# ============================================================
# 🤖 إعدادات الوكلاء
# ============================================================
AGENTS = {
    "analyst_interval_sec":   5,    # الوكيل 1: يحلل كل N ثانية
    "monitor_interval_sec":   1,    # الوكيل 3: يراقب كل N ثانية
    "learning_interval_min":  60,   # الوكيل 4: يتعلم كل N دقيقة
    "min_trades_to_learn":    20,   # أدنى صفقات قبل التعلم
    "analyst_team_interval_min": 60, # دورة فريق المحللين (قياس فقط)
}

# ============================================================
# 🏛️ إعدادات مجلس الوكلاء (قياس في الظل / فلترة فعلية)
# ============================================================
# mode:
#   "shadow"  = يُحسب ويُسجَّل فقط، بلا أي تأثير على التنفيذ (الافتراضي الآمن)
#   "enforce" = فيتو المجلس يمنع نشر الإشارة فعلاً — لكنه **مقفول ببوابة إثبات**:
#               لا يُفعَّل حتى تتوفّر صفقات ظل مربوطة بنتائج كافية ويظهر أن
#               الفيتو يضيف قيمة صافية بالموجب. إن لم يتحقق الشرطان يبقى
#               shadow ويُسجَّل سبب الرفض في اللوج.
# يمكن تجاوز الوضع من البيئة: COUNCIL_MODE=enforce
COUNCIL = {
    "mode":                "shadow",
    "min_evidence_trades": 40,     # أدنى صفقات ظل مربوطة بنتائج معروفة
    "min_veto_edge_usd":   0.0,    # أدنى صافي ربح للفيتو (USD) لتمكينه
}

# ============================================================
# 📈 إعدادات المؤشرات الفنية
# ============================================================
INDICATORS = {
    "ema_period":      50,
    "rsi_period":      7,
    "rsi_overbought":  70,
    "rsi_oversold":    30,
    "macd_fast":       12,
    "macd_slow":       26,
    "macd_signal":     9,
    "bb_period":       20,
    "bb_dev":          2.0,
    "atr_period":      14,
    "adx_period":      14,
    "adx_threshold":   25,
    "momentum_period": 10,
    "stoch_k":         5,
    "stoch_d":         3,
    "ichi_tenkan":     9,
    "ichi_kijun":      26,
    "ichi_senkou":     52,
}

# ============================================================
# 💾 قاعدة البيانات
# IMPROVEMENT_PLAN §1: مسار مطلق لمنع إنشاء ملفات متعددة عند التشغيل من مجلدات مختلفة
# ============================================================
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BACKEND_DIR, "trading.db")
DATABASE_URL      = f"sqlite:///{_DB_PATH}"
DATABASE_URL_SYNC = f"sqlite:///{_DB_PATH}"

# ============================================================
# 🎯 Meta-Model — مسار الحفظ + بوابة التفعيل (P3)
# ============================================================
# المسار الوحيد لنموذج Meta-Labeling المعاير (يكتبه LearningAgent ويقرؤه ExecutionAgent)
META_MODEL_PATH = os.path.join(_BACKEND_DIR, "models", "meta_model.pkl")

# بوابة التفعيل (IMPROVEMENT_PLAN §3 + AGENTS.md «لا فلترة/تحجيم قبل قيمة موجبة خارج العيّنة»).
# الاحتمال المعاير لا يصل إلى تحجيم الصفقة إلا إذا اجتاز النموذج **كل** الشروط على تنبؤات خارج العيّنة (Purged K-Fold):
#   1) عدد عيّنات OOS ≥ min_oos_samples
#   2) الحدّ الأدنى لفترة ثقة AUC (bootstrap بالكتل) > min_auc_lower  (أي أن الفترة لا تشمل 0.5)
#   3) Brier Skill مقابل المتنبّئ الثابت (نسبة الفوز الأساسية) > min_brier_skill
# ⚠️ هذه عتبات سياسة (قرار مستخدم) وليست أرقاماً مقيسة: min_oos_samples=200 اختيرت لأن حجم العيّنة الموثّق 400-500 صفقة.
META_GATE = {
    "min_oos_samples": 200,
    "min_auc_lower":   0.50,
    "min_brier_skill": 0.0,
    "n_bootstrap":     1000,
    "confidence":      0.99,   # مقيس: فتح خاطئ على ضجيج 1/60 عند 0.95 مقابل 0/60 عند 0.99 (انظر P3_CHANGELOG)
    "block_size":      10,     # bootstrap بالكتل: الصفقات المتتالية مترابطة زمنياً
    "seed":            42,
}

# ============================================================
# 🌐 Server
# ============================================================
# أسرار الأمان تُقرأ من .env مباشرة في main.py (انظر .env.example):
#   API_TOKEN      — ترويسة X-API-Token لكل عملية تغيّر شيئاً؛ فارغ = معطّلة
#   WEBHOOK_SECRET — إلزامي لويب هوك TradingView؛ فارغ = معطّل
SERVER = {
    # الجهاز المحلي فقط افتراضياً؛ للوصول من الشبكة اضبط BACKEND_HOST=0.0.0.0 صراحةً
    "host": os.getenv("BACKEND_HOST", "127.0.0.1"),
    "port": int(os.getenv("PORT", "8000")),
    "reload": False,
}

# ============================================================
# 🚦 مفاتيح الميزات — كلها مطفأة افتراضياً، وتُشغَّل من .env
# ============================================================
def _env_flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() == "true"


FEATURES = {
    # تنفيذ صفقة TradingAgents يدوياً (يمر عبر SafeExecutionGateway)
    "tradingagents_execution": _env_flag("TRADINGAGENTS_EXECUTION_ENABLED"),
    # صفحتان تُخفيان إلى أن يوجد نموذج مُدرَّب
    "lstm_page":               _env_flag("LSTM_PAGE_ENABLED"),
    "rl_page":                 _env_flag("RL_PAGE_ENABLED"),
}

# ============================================================
# 📝 Logging
# ============================================================
LOG_LEVEL = "INFO"
LOG_FILE  = "logs/trading_{time}.log"
LOG_ROTATION = "1 day"
LOG_RETENTION = "7 days"

# ============================================================
# 🧮 ثوابت طبقة الوكلاء (فريق المحللين + مدير المخاطر)
# ============================================================
# هذا هو **المصدر الوحيد** لهذه القيم: حزمة config الجذرية تستورد هذا الملف
# نجماً (config/__init__.py) فيصلها كل ما هنا. وُضعت هنا لأن وحدات المحللين
# تقرأ `cfg.X` وفي سياق التشغيل الحقيقي تُحلّ `config` إلى هذا الملف —
# وكانت غائبة تماماً فترفع AttributeError قبل أي قرار.
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


def _env_list(name: str, default: list) -> list:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]


# ثوابت كانت معرّفة في حزمة config الجذرية فقط — أُضيفت هنا لأن هذا الملف
# هو ما تُحلّ إليه `config` في سياق التشغيل الفعلي.
STARTING_CAPITAL: float        = _env_float("STARTING_CAPITAL", 10000.0)
MAX_FOREX_LEVERAGE: float      = _env_float("MAX_FOREX_LEVERAGE", 100.0)
# فتح صفقات على حساب غير تجريبي ممنوع ما لم يكن true (انظر MT5Connector.entry_block_reason)
LIVE_TRADING_ENABLED: bool     = _env_bool("LIVE_TRADING_ENABLED", False)
# أقصى عمر (بالدقائق) لتحليل TradingAgents يقبله التنفيذ اليدوي — قيمة سياسة لا نتيجة قياس
TRADINGAGENTS_MAX_ANALYSIS_AGE_MINUTES: float = _env_float("TRADINGAGENTS_MAX_ANALYSIS_AGE_MINUTES", 15.0)

MAX_SINGLE_TRADE_RISK_PCT: float    = _env_float("MAX_SINGLE_TRADE_RISK_PCT", 0.03)
MIN_RISK_REWARD_RATIO: float        = _env_float("MIN_RISK_REWARD_RATIO", 1.5)
MAX_PIP_STOP_LOSS: float            = _env_float("MAX_PIP_STOP_LOSS", 50.0)
NEWS_SHIELD_MINUTES: float          = _env_float("NEWS_SHIELD_MINUTES", 30.0)
EQUITY_ALLOCATION_PCT: float        = _env_float("EQUITY_ALLOCATION_PCT", 0.0)
FOREX_ALLOCATION_PCT: float         = _env_float("FOREX_ALLOCATION_PCT", 1.0)
MANUAL_LOT_SIZE_ENABLED: bool       = _env_bool("MANUAL_LOT_SIZE_ENABLED", False)
FIXED_LOT_SIZE: float               = _env_float("FIXED_LOT_SIZE", 0.01)
MAX_LOT_SIZE: float                 = _env_float("MAX_LOT_SIZE", 0.5)
MAX_TOTAL_OPEN_POSITIONS: int       = int(_env_float("MAX_TOTAL_OPEN_POSITIONS", 20))
MAX_EQUITY_OPEN_POSITIONS: int      = int(_env_float("MAX_EQUITY_OPEN_POSITIONS", 5))
MAX_FOREX_OPEN_POSITIONS: int       = int(_env_float("MAX_FOREX_OPEN_POSITIONS", 15))
MAX_EQUITY_POSITION_PCT: float      = _env_float("MAX_EQUITY_POSITION_PCT", 0.20)
EQUITY_VOLATILITY_ATR_FILTER: float = _env_float("EQUITY_VOLATILITY_ATR_FILTER", 0.05)
FX_WATCHLIST: list = _env_list("FX_WATCHLIST", [
    "EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X",
    "USDCHF=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X",
])
EQUITY_WATCHLIST: list = _env_list("EQUITY_WATCHLIST", [])


# ============================================================
# 🚀 إعدادات ترقيات إشارة الدخول (2026 Entry Signal Upgrades v2)
# ============================================================
ENTRY_UPGRADES_2026 = {
    # أوزان سقف المحاور الأربعة المتعامدة حسب نظام FSM (المجموع دائماً = 7.5 للحفاظ على معايرة min_vote_score)
    "regime_pillar_caps": {
        "STRONG_TREND": {"trend": 2.7, "momentum": 1.5, "strength": 1.8, "structure": 1.5},
        "SLOW_TREND":   {"trend": 2.6, "momentum": 1.7, "strength": 1.7, "structure": 1.5},
        "LOW_VOL_RANGE":  {"trend": 1.8, "momentum": 2.2, "strength": 1.2, "structure": 2.3},
        "HIGH_VOL_RANGE": {"trend": 1.8, "momentum": 2.2, "strength": 1.2, "structure": 2.3},
        "LOW_VOL":        {"trend": 1.8, "momentum": 2.2, "strength": 1.2, "structure": 2.3},
        "DEFAULT":      {"trend": 2.5, "momentum": 2.0, "strength": 1.5, "structure": 1.5},
    },
    # حد التنازع بين المحاور المتعامدة (Anti-Groupthink / Conflict Guard)
    "conflict_strong_multiplier": 1.55,
    # أدنى إزاحة سعرية لفجوة FVG كنسبة من ATR لفلترة ضوضاء الفجوات الصغيرة
    "fvg_min_atr_ratio":          0.15,
    # حد تدفق الأوامر المعاكس الشديد في BetaOrderFlowAgent
    "ofi_counter_flow_z":         1.8,
    # عمر النصف باليوم لتضائل أوزان الذاكرة العرضية (FinMem Time-Decay)
    "episodic_half_life_days":    14.0,
    # عدد أقرب الفخاخ المستخدمة في المتوسط المرجح (Top-K) بدل القيمة القصوى المعزولة
    "episodic_top_k":             3,
    # قاطع الدائرة المزدوج للذاكرة: تعليق الاسترجاع عند صدمة التقلب أو انهيار ثقة النظام
    "memory_cb_atr_ratio":        2.0,
    "memory_cb_min_regime_conf":  0.45,
    # وزن دمج الاحتمال المعايَر (Calibrated Meta-Model) في OmegaRiskGovernor
    "calibrated_fusion_weight":   0.55,
}


# ============================================================
# 🧠 إعدادات ترقية التعلم الآلي وحوكمة Champion/Challenger (2026)
# ============================================================
LEARNING_UPGRADES_2026 = {
    "probation_trades":                10,    # عدد الصفقات المغلقة لتقييم Challenger قبل الترقية أو التراجع
    "max_consecutive_losses_rollback": 4,     # تراجع تلقائي فوري عند N خسائر متتالية للـ Challenger
    "max_weight_step":                 0.25,  # أقصى تغير مسموح لكل وزن في الدورة الواحدة
    "rollback_cooldown_trades":        5,     # فترة تهدئة بعد أي تراجع تلقائي قبل اقتراح أوزان جديدة
    "wr_tolerance":                    0.05,  # هامش التسامح في نسبة الفوز عند المقارنة مع Champion
    "min_signal_confidence":           55.0,  # عتبة الثقة الأساسية التي يُضاف إليها _regime_confidence_boost
    "cv_embargo_bars":                 2,     # فجوة حظر زمني (Embargo) في التقييم التسلسلي لمنع التسرّب
}


# ============================================================
# 📡 إعدادات توحيد التواصل وذاكرة التأمّل النشطة (2026 Batch 2)
# ============================================================
COMMUNICATION_REFLECTION_2026 = {
    "reflection_lookback_days":            14,     # نافذة قراءة دروس AgentReflection بالأيام
    "reflection_min_samples":              4,      # أدنى عدد دروس قبل فرض عقوبة انخفاض نسبة الفوز
    "reflection_cooldown_consecutive_losses": 4,   # حظر مؤقت للزوج/النظام عند N خسائر متتالية خلال 48 ساعة
    "reflection_max_conf_penalty":         15.0,   # أقصى زيادة مئوية على عتبة ثقة MarketAnalyst
    "reflection_max_omega_penalty":        0.08,   # أقصى زيادة على عتبة OmegaRiskGovernor
    "reflection_cache_ttl_sec":            30.0,   # مدة كاش القراءة بالثواني (يُلغى فوراً عند إغلاق صفقة)
}


# ============================================================
# 🛡️ إعدادات الترميم الذاتي ومراقب انجراف الألفا (2026 Batch 3)
# ============================================================
SELF_HEALING_2026 = {
    "require_suggest_mode_live":    True,    # منع تعديل الكود الحي تلقائياً (معيار أمان 2026)
    "heartbeat_max_silence_sec":    60.0,    # أقصى صمت للوكيل قبل إعلان توقف النبضة (Stall)
    "latency_spike_ms":             1500.0,  # عتبة تأخير التنفيذ بالمللي ثانية
    "mt5_max_reconnect_attempts":   3,       # أقصى محاولات إعادة اتصال قبل فتح قاطع الدائرة
    "mt5_reconnect_cooldown_sec":   30.0,    # فترة التهدئة بين محاولات استرداد MT5
    "ph_delta":                     0.05,    # معامل تسامح Page-Hinkley لانجراف الألفا
    "ph_threshold":                 4.0,     # عتبة التراكم لإعلان الانجراف والتحويل للظل (Shadow Demotion)
    "ph_min_samples":               10,      # أدنى عدد صفقات قبل تفعيل كاشف الانجراف
}


# ============================================================
# 🧬 إعدادات نماذج الأساس 2026 (TimesFM 2.5 + FinBERT + Gemma)
# ============================================================
FOUNDATION_MODELS_2026 = {
    # TimesFM 2.5 (200M) — Apache-2.0 (مسموح للإنتاج المحلي؛ TimesFM 3.0 غير تجاري محلياً)
    "timesfm_enabled":              True,
    "timesfm_repo_id":              "google/timesfm-2.5-200m-pytorch",
    "timesfm_allow_non_commercial": False,
    "timesfm_cache_ttl_sec":        300.0,   # تحديث كل 5 دقائق (لا يعمل داخل حلقة الـ 5 ثوانٍ)
    "timesfm_high_uncertainty_var": 5e-5,    # حد التباين الذي يشدّد عتبة الثقة (+5%)
    # FinBERT (المسار السريع الدائم) + Gemma 3/4 (المسار العميق لأخبار HIGH)
    "finbert_enabled":              True,
    "finbert_model_id":             "ProsusAI/finbert",
    "gemma_enabled_for_high_impact":True,
    "gemma_model_id":               "gemma3:4b",
    "gemma_ollama_url":             "http://127.0.0.1:11434",
    # RESERVED / NOT WIRED: لا يوجد مسار تدريب أو تقديم لنموذج v2 ذي الـ 12 ميزة بعد
    "v2_feature_count":             12,
}
