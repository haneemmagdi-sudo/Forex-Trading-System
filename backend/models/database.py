"""
============================================================
database.py — نماذج قاعدة البيانات SQLite + SQLAlchemy
============================================================
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, event, Column, Integer, Float, String, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime
import enum
from config import DATABASE_URL_SYNC


# ── Base ─────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────
class TradeType(str, enum.Enum):
    BUY  = "BUY"
    SELL = "SELL"

class TradeStatus(str, enum.Enum):
    OPEN    = "OPEN"
    CLOSED  = "CLOSED"
    PARTIAL = "PARTIAL"

class SignalDirection(str, enum.Enum):
    BUY     = "BUY"
    SELL    = "SELL"
    NO_TRADE= "NO_TRADE"

class FSMRegime(str, enum.Enum):
    LOW_VOL_RANGE  = "LOW_VOL_RANGE"
    HIGH_VOL_RANGE = "HIGH_VOL_RANGE"
    SLOW_TREND     = "SLOW_TREND"
    STRONG_TREND   = "STRONG_TREND"
    CHAOS          = "CHAOS"


# ── Trade ─────────────────────────────────────────────────────────────
class Trade(Base):
    __tablename__ = "trades"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    ticket       = Column(Integer, unique=True, index=True)   # MT5 ticket
    symbol       = Column(String(10), index=True)
    type         = Column(SAEnum(TradeType))
    status       = Column(SAEnum(TradeStatus), default=TradeStatus.OPEN)

    lot_size     = Column(Float)
    entry_price  = Column(Float)
    sl_price     = Column(Float, nullable=True)
    tp_price     = Column(Float, nullable=True)
    close_price  = Column(Float, nullable=True)

    profit_usd   = Column(Float, nullable=True)
    profit_pips  = Column(Float, nullable=True)

    fsm_regime   = Column(SAEnum(FSMRegime), nullable=True)
    buy_score    = Column(Float, nullable=True)
    sell_score   = Column(Float, nullable=True)
    confidence   = Column(Float, nullable=True)

    # Partial close tracking
    partial_l1_done = Column(Boolean, default=False)
    partial_l2_done = Column(Boolean, default=False)
    partial_l3_done = Column(Boolean, default=False)
    breakeven_done  = Column(Boolean, default=False)
    trailing_active = Column(Boolean, default=False)

    opened_at    = Column(DateTime, default=datetime.utcnow)
    closed_at    = Column(DateTime, nullable=True)
    comment      = Column(String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ticket": self.ticket,
            "symbol": self.symbol,
            "type": self.type.value if self.type else None,
            "direction": self.type.value if self.type else None,  # Frontend alias
            "status": self.status.value if self.status else None,
            "lot_size": self.lot_size,
            "lot": self.lot_size,  # Frontend alias
            "entry_price": self.entry_price,
            "open_price": self.entry_price,  # Frontend alias
            "sl_price": self.sl_price,
            "sl": self.sl_price,  # Frontend alias
            "tp_price": self.tp_price,
            "tp": self.tp_price,  # Frontend alias
            "close_price": self.close_price,
            "profit_usd": self.profit_usd,
            "profit_pips": self.profit_pips,
            "fsm_regime": self.fsm_regime.value if self.fsm_regime else None,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "confidence": self.confidence,
            "partial_l1_done": self.partial_l1_done,
            "partial_l2_done": self.partial_l2_done,
            "partial_l3_done": self.partial_l3_done,
            "breakeven_done": self.breakeven_done,
            "trailing_active": self.trailing_active,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "comment": self.comment,
        }


# ── Signal ────────────────────────────────────────────────────────────
class Signal(Base):
    __tablename__ = "signals"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String(10), index=True)
    direction   = Column(SAEnum(SignalDirection))
    fsm_regime  = Column(SAEnum(FSMRegime))
    buy_score   = Column(Float)
    sell_score  = Column(Float)
    total_weight= Column(Float)
    confidence  = Column(Float)
    executed    = Column(Boolean, default=False)
    trade_ticket= Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Indicator values at signal time
    ema_value   = Column(Float, nullable=True)
    rsi_value   = Column(Float, nullable=True)
    macd_value  = Column(Float, nullable=True)
    adx_value   = Column(Float, nullable=True)
    atr_value   = Column(Float, nullable=True)
    price       = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value if self.direction else None,
            "fsm_regime": self.fsm_regime.value if self.fsm_regime else None,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "total_weight": self.total_weight,
            "confidence": self.confidence,
            "executed": self.executed,
            "trade_ticket": self.trade_ticket,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "price": self.price,
            "ema_value": self.ema_value,
            "rsi_value": self.rsi_value,
            "macd_value": self.macd_value,
            "adx_value": self.adx_value,
            "atr_value": self.atr_value,
        }


# ── Performance ───────────────────────────────────────────────────────
class PerformanceSnapshot(Base):
    __tablename__ = "performance"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    balance       = Column(Float)
    equity        = Column(Float)
    drawdown_pct  = Column(Float)
    open_trades   = Column(Integer)
    daily_pnl     = Column(Float, nullable=True)
    win_rate      = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    recorded_at   = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "balance": self.balance,
            "equity": self.equity,
            "drawdown_pct": self.drawdown_pct,
            "open_trades": self.open_trades,
            "daily_pnl": self.daily_pnl,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


# ── Learning Log ──────────────────────────────────────────────────────
class LearningLog(Base):
    __tablename__ = "learning_logs"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    iteration      = Column(Integer)
    trades_analyzed= Column(Integer)
    win_rate       = Column(Float)
    best_regime    = Column(String(30), nullable=True)
    worst_regime   = Column(String(30), nullable=True)
    notes          = Column(Text, nullable=True)
    weight_adjustments = Column(Text, nullable=True)  # JSON string
    created_at     = Column(DateTime, default=datetime.utcnow)


# ── Agent Log ─────────────────────────────────────────────────────────
class AgentLog(Base):
    __tablename__ = "agent_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(50), index=True)
    level      = Column(String(10))   # INFO, WARNING, ERROR
    message    = Column(Text)
    symbol     = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "agent": self.agent_name,
            "level": self.level,
            "message": self.message,
            "symbol": self.symbol,
            "time": self.created_at.isoformat() if self.created_at else None,
        }


# ── Shadow Council Decision (وضع الظل) ────────────────────────────────
class ShadowDecision(Base):
    """
    حكم مجلس الوكلاء على كل إشارة مرشّحة — يُسجَّل للمقارنة والقياس فقط
    ولا يؤثر على التنفيذ. يُربط بالإشارة عبر signal_id ثم بالصفقة عبر
    Signal.trade_ticket، فيكتمل السلسلة: حكم المجلس → الصفقة → النتيجة.
    """
    __tablename__ = "shadow_decisions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    signal_id    = Column(Integer, index=True)
    symbol       = Column(String(10), index=True)
    fsm_regime   = Column(String(20), nullable=True)

    # القرار الحي (ما نُفِّذ فعلاً)
    live_direction   = Column(String(6))
    live_confidence  = Column(Float, nullable=True)

    # مدخلات حقيقية استُخدمت في الحكم
    ml_prob          = Column(Float, nullable=True)   # احتمال الربح من النموذج المُدرَّب
    news_sentiment   = Column(String(12), nullable=True)

    # حكم محرّك الإجماع (اللوحة + الأوزان)
    consensus_action = Column(String(6), nullable=True)
    consensus_score  = Column(Float, nullable=True)
    consensus_active = Column(Integer, nullable=True)
    consensus_missing= Column(String(60), nullable=True)
    consensus_partial= Column(Boolean, nullable=True)

    # حكم الجسر المؤسسي (HMM + Order Flow + MAD)
    bridge_approved  = Column(Boolean, nullable=True)
    bridge_stage     = Column(String(30), nullable=True)
    bridge_confidence= Column(Float, nullable=True)
    bridge_regime    = Column(String(20), nullable=True)
    bridge_absorption= Column(String(24), nullable=True)
    bridge_latency_ms= Column(Float, nullable=True)

    # خلاصة القياس
    council_aligned    = Column(Boolean, nullable=True)  # هل وافق المجلس اتجاه التنفيذ
    council_would_block= Column(Boolean, nullable=True)  # هل كان سيمنع الصفقة
    error              = Column(Text, nullable=True)

    created_at   = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "fsm_regime": self.fsm_regime,
            "live_direction": self.live_direction,
            "live_confidence": self.live_confidence,
            "ml_prob": self.ml_prob,
            "news_sentiment": self.news_sentiment,
            "consensus_action": self.consensus_action,
            "consensus_score": self.consensus_score,
            "consensus_active": self.consensus_active,
            "consensus_missing": self.consensus_missing,
            "consensus_partial": self.consensus_partial,
            "bridge_approved": self.bridge_approved,
            "bridge_stage": self.bridge_stage,
            "bridge_confidence": self.bridge_confidence,
            "bridge_regime": self.bridge_regime,
            "bridge_latency_ms": self.bridge_latency_ms,
            "council_aligned": self.council_aligned,
            "council_would_block": self.council_would_block,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Agent Reflection (ذاكرة التأمّل) ──────────────────────────────────
class AgentReflection(Base):
    """
    درس مُستخلَص من كل صفقة مغلقة نتيجتها معروفة: الحالة → القرار → النتيجة
    → الدرس. يُبنى بقواعد حتمية (لا LLM) فلا يعتمد على مزوّد خارجي.
    """
    __tablename__ = "agent_reflections"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    trade_ticket  = Column(Integer, index=True)
    signal_id     = Column(Integer, nullable=True)
    symbol        = Column(String(10), index=True)
    fsm_regime    = Column(String(20), nullable=True)
    confidence    = Column(Float, nullable=True)
    ml_prob       = Column(Float, nullable=True)
    council_aligned     = Column(Boolean, nullable=True)
    council_would_block = Column(Boolean, nullable=True)
    outcome_pnl   = Column(Float, nullable=True)
    outcome       = Column(String(6), nullable=True)   # WIN | LOSS
    lesson        = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "trade_ticket": self.trade_ticket,
            "symbol": self.symbol,
            "fsm_regime": self.fsm_regime,
            "confidence": self.confidence,
            "ml_prob": self.ml_prob,
            "council_aligned": self.council_aligned,
            "council_would_block": self.council_would_block,
            "outcome_pnl": self.outcome_pnl,
            "outcome": self.outcome,
            "lesson": self.lesson,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Analyst Team Cycle (دورة فريق المحللين المجدولة) ──────────────────
class AnalystCycle(Base):
    """
    سجل دورة فريق المحللين (FX/Equity → المخطط → المدير التنفيذي → المخاطر).
    يُسجَّل كل ما أنتجه الفريق في دورة واحدة للقياس، بلا أي تأثير على التنفيذ:
    المقترحات تبقى بيانات حتى يُقرَّر ربطها بالتنفيذ صراحةً.
    """
    __tablename__ = "analyst_cycles"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id      = Column(String(40), index=True)
    fx_reports    = Column(Integer, default=0)
    equity_reports= Column(Integer, default=0)
    duration_ms   = Column(Float, nullable=True)

    proposal_symbol    = Column(String(12), nullable=True)
    proposal_action    = Column(String(8), nullable=True)
    proposal_confidence= Column(Float, nullable=True)
    proposal_entry     = Column(Float, nullable=True)
    proposal_sl        = Column(Float, nullable=True)
    proposal_tp        = Column(Float, nullable=True)
    proposal_lot_type  = Column(String(10), nullable=True)

    ceo_decision    = Column(String(20), nullable=True)
    ceo_reasoning   = Column(Text, nullable=True)
    ceo_provider    = Column(String(20), nullable=True)

    risk_verdict    = Column(String(20), nullable=True)
    risk_score      = Column(Float, nullable=True)
    risk_violations = Column(Text, nullable=True)

    llm_provider  = Column(String(20), nullable=True)
    error         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "cycle_id": self.cycle_id,
            "fx_reports": self.fx_reports,
            "equity_reports": self.equity_reports,
            "duration_ms": self.duration_ms,
            "proposal": {
                "symbol": self.proposal_symbol,
                "action": self.proposal_action,
                "confidence": self.proposal_confidence,
                "entry": self.proposal_entry,
                "stop_loss": self.proposal_sl,
                "take_profit": self.proposal_tp,
                "lot_type": self.proposal_lot_type,
            },
            "ceo_decision": self.ceo_decision,
            "ceo_reasoning": self.ceo_reasoning,
            "risk_verdict": self.risk_verdict,
            "risk_score": self.risk_score,
            "risk_violations": self.risk_violations,
            "llm_provider": self.llm_provider,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Engine ────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL_SYNC,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, connection_record):
    """
    WAL + مهلة انتظار للأقفال.
    يمنع أخطاء 'database is locked' عند الكتابة المتزامنة من عدة وكلاء
    وخيوط FastAPI على نفس ملف SQLite (كانت تُسقط صفقات حقيقية من سجل التعلّم).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def create_tables():
    """إنشاء جميع الجداول إذا لم تكن موجودة"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency لـ FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
