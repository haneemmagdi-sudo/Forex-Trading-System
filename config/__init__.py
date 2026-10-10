"""
config — Antigravity system configuration package.
Import `settings` from `config.settings` for all configuration values.
"""
from config.settings import settings, get_settings

# Global Forex & System Execution Parameters
MAX_FOREX_LEVERAGE: float = 100.0
LIVE_TRADING_ENABLED: bool = False
STARTING_CAPITAL: float = 10000.0

# Bridge backend configuration symbols so imports like 'from config import MT5, SYMBOLS' work universally
try:
    from backend.config import *
except Exception:
    pass

# ملاحظة: ثوابت طبقة الوكلاء (MAX_SINGLE_TRADE_RISK_PCT، NEWS_SHIELD_MINUTES،
# MAX_*_OPEN_POSITIONS، FX_WATCHLIST ...) تُعرَّف في backend/config.py كمصدر
# وحيد، وتصل إلى هنا عبر الاستيراد النجمي أعلاه. لا تُكرّرها في هذا الملف.

