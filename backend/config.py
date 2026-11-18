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
    # القيم بوحدة البيب (0.0001 للأزواج الرئيسية، 0.01 لأزواج الين)
    "max_spread_pips":     4.0,   # حد افتراضي للأزواج الرئيسية
    "symbol_spread_limits": {
        "EURUSD": 3.0, "GBPUSD": 4.0, "USDJPY": 3.0, "AUDUSD": 4.0,
        "USDCAD": 4.0, "USDCHF": 4.0, "NZDUSD": 5.0, "EURJPY": 5.0,
        "GBPJPY": 7.0, "EURGBP": 4.0, "XAUUSD": 40.0, "XAGUSD": 50.0,
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
    "base_target_usd":     2.0,   # الهدف الإجمالي للمحفظة 2 دولار
    "basket_max_loss_usd": 20.0,  # IMPROVEMENT_PLAN §0: وقف خسارة إجمالي للسلة بالدولار لحماية الحساب من شبكة التعزيز
    # IMPROVEMENT_PLAN §0: وقف السلة بالـATR = أعمق طبقة في الشبكة ∓ ATR(M15, 14) × هذا المضاعِف.
    # قيمة ≤ 0 أو غير رقمية تعني الافتراضي 2.5 (الوقف لا يُعطَّل من هنا). وقف الدولار أعلاه يبقى حداً أقصى.
    "basket_sl_atr_multiplier": 2.5,

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
# 🌐 Server
# ============================================================
SERVER = {
    "host": "0.0.0.0",
    "port": int(os.getenv("PORT", "8000")),
    "reload": False,
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
LIVE_TRADING_ENABLED: bool     = _env_bool("LIVE_TRADING_ENABLED", False)

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
