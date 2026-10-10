"""
schemas/forex.py — Forex Pip, Margin, and Leverage Calculations.
"""

from __future__ import annotations

from enum import Enum


# ── Lots ──────────────────────────────────────────────────────────────
class LotType(str, Enum):
    """تصنيف حجم اللوت المتعارف عليه."""
    STANDARD = "STANDARD"
    MINI     = "MINI"
    MICRO    = "MICRO"


def lot_type_from_size(lot_size: float) -> LotType:
    """تصنيف حجم اللوت: 1.0+ قياسي، 0.1+ مصغّر، وما دون ذلك مايكرو."""
    try:
        size = abs(float(lot_size))
    except (TypeError, ValueError):
        return LotType.MICRO
    if size >= 1.0:
        return LotType.STANDARD
    if size >= 0.1:
        return LotType.MINI
    return LotType.MICRO


def display_pair(symbol: str) -> str:
    """يحوّل أي صيغة رمز إلى شكل عرض موحّد: EURUSD / EURUSD=X → EUR/USD."""
    clean = (symbol or "").upper().replace("/", "").replace("-", "").replace("=X", "").strip()
    if len(clean) == 6:
        return f"{clean[:3]}/{clean[3:]}"
    return (symbol or "").upper()


# ── Sessions ──────────────────────────────────────────────────────────
class ForexSession(str, Enum):
    """جلسات سوق الفوركس (بالتوقيت العالمي UTC)."""
    SYDNEY    = "SYDNEY"
    TOKYO     = "TOKYO"
    LONDON    = "LONDON"
    NEW_YORK  = "NEW_YORK"
    OFF_HOURS = "OFF_HOURS"


# نوافذ الجلسات (ساعة البداية، ساعة النهاية) بالتوقيت العالمي.
# مطابقة لـ SESSIONS في backend/config.py، والأولوية للجلسات الأعلى سيولة.
_SESSION_WINDOWS = {
    ForexSession.LONDON:   (7, 16),
    ForexSession.NEW_YORK: (13, 22),
    ForexSession.TOKYO:    (0, 9),
    ForexSession.SYDNEY:   (21, 6),
}
_SESSION_PRIORITY = (
    ForexSession.LONDON, ForexSession.NEW_YORK, ForexSession.TOKYO, ForexSession.SYDNEY,
)


def get_active_forex_session(utc_hour: int) -> ForexSession:
    """
    الجلسة النشطة في ساعة UTC معيّنة.
    تُرجَع أول جلسة مفتوحة حسب الأولوية (لندن ثم نيويورك ثم طوكيو ثم سيدني)
    لأن تداخل لندن/نيويورك هو الأعلى سيولة. وإن لم تُفتح أي جلسة → OFF_HOURS.
    """
    try:
        hour = int(utc_hour) % 24
    except (TypeError, ValueError):
        return ForexSession.OFF_HOURS

    for session in _SESSION_PRIORITY:
        start, end = _SESSION_WINDOWS[session]
        in_window = (start <= hour < end) if start < end else (hour >= start or hour < end)
        if in_window:
            return session
    return ForexSession.OFF_HOURS


def get_pip_size(symbol: str) -> float:
    """Return pip size: 0.01 for JPY pairs, 0.0001 for standard Forex pairs."""
    clean = symbol.upper().replace("/", "").replace("-", "")
    if "JPY" in clean:
        return 0.01
    return 0.0001


def price_to_pips(symbol: str, price_diff: float) -> float:
    """Convert price difference to pips."""
    pip_size = get_pip_size(symbol)
    return round(abs(price_diff) / pip_size, 2)


def pips_to_usd(symbol: str, pips: float, quantity: float = 0.01) -> float:
    """
    Approximate dollar value of a pip move for a given lot size.
    Standard lot = 100,000 units ($10 per pip on EURUSD).
    0.01 lot (micro lot) = $0.10 per pip.
    """
    pip_size = get_pip_size(symbol)
    # Standard lot size is 100,000 units
    contract_size = 100_000.0
    usd_per_pip_standard = 10.0
    return round(pips * usd_per_pip_standard * quantity, 2)


def calculate_margin_required(
    symbol: str,
    quantity: float,
    price: float,
    leverage: float = 100.0,
) -> float:
    """
    Calculate required margin in USD for a Forex trade.
    Formula: (Contract Size * Lots * Price) / Leverage
    """
    if leverage <= 0:
        leverage = 100.0
    contract_size = 100_000.0
    notional = contract_size * quantity * price
    margin = notional / leverage
    return round(margin, 2)
