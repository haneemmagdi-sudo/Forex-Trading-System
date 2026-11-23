"""
============================================================
signal_bus.py — قناة التواصل بين الوكلاء (asyncio)
============================================================
يتيح للوكلاء تبادل الرسائل بشكل متزامن وآمن
مع دعم: الأولوية، التسجيل، والإحصاءات
"""
import asyncio
import heapq
import itertools
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
from collections import defaultdict

# صلاحية تنبيهات الـ Bus: dd_alert لا يُبثّ عند التعافي (يُبثّ عند السوء فقط)، لذا بدون TTL
# يبقى emergency_dd_active=True للأبد ويحجب المجلس حتى بعد انتهاء الخطر. التنبيه المتكرر يجدد المهلة.
DEFAULT_BUS_ALERT_TTL_SEC = 1800.0
# ملف الحالة المشترك بين عملية الـ backend (صاحبة الـ Bus) وعملية المجلس council/ (عملية منفصلة)
DEFAULT_COUNCIL_STATE_PATH = Path(__file__).resolve().parent.parent / "models" / "council_bus_state.json"


@dataclass
class BusMessage:
    """رسالة في قناة التواصل"""
    topic:     str          # "signal", "trade_opened", "trade_closed", "dd_alert", "news_alert"
    sender:    str          # اسم الوكيل المُرسِل
    data:      Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority:  int = 0      # 0 = عادي, 1 = عالي, 2 = طوارئ

    def to_dict(self):
        return {
            "topic":     self.topic,
            "sender":    self.sender,
            "data":      self.data,
            "timestamp": self.timestamp,
            "priority":  self.priority,
        }


class SignalBus:
    """
    قناة رسائل asyncio لتواصل الوكلاء
    ─────────────────────────────────────────────
    ✅ نشر/اشتراك لكل موضوع (topic)
    ✅ دعم الأولوية (priority)
    ✅ تتبع إحصاءات التواصل بين الوكلاء
    ✅ سجل الرسائل الحقيقية (history)
    """

    def __init__(self, max_history: int = 1000):
        # قائمة المشتركين لكل موضوع بصيغة (handler_priority, seq, handler) لترتيب التنفيذ بالأولوية
        self._subscribers:  Dict[str, List[Tuple[int, int, Callable]]] = {}
        self._history:      List[BusMessage] = []
        self._max_history   = max_history
        self._lock          = asyncio.Lock()
        self._ws_callbacks: List[Callable] = []

        # طابور أولويات حقيقي (2026): (-msg.priority, seq, msg) لضمان سبق dd_alert و news_alert
        self._pq: List[Tuple[int, int, BusMessage]] = []
        self._seq = itertools.count()
        self._sub_seq = itertools.count()
        self._dispatch_event: Optional[asyncio.Event] = None
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._council_bridge: Optional["CouncilStateBridge"] = None

        # إحصاءات التواصل بين الوكلاء
        self._comm_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # من أرسل → إلى موضوع → عدد الرسائل
        self._agent_messages: Dict[str, int] = defaultdict(int)

    async def publish(self, msg: BusMessage):
        """نشر رسالة لجميع المشتركين"""
        async with self._lock:
            self._history.append(msg)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            # تحديث الإحصاءات
            self._agent_messages[msg.sender] += 1
            self._comm_stats[msg.sender][msg.topic] += 1

        # إخطار المشتركين مرتّبين تنازلياً حسب أولوية المشترك (handler_priority) ثم ترتيب التسجيل
        combined = self._subscribers.get(msg.topic, []) + self._subscribers.get("*", [])
        combined.sort(key=lambda item: (-item[0], item[1]))
        for _, _, handler in combined:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(msg)
                else:
                    handler(msg)
            except Exception as e:
                logger.error(f"❌ خطأ في معالج الرسائل [{msg.topic}]: {e}")

        # إرسال لـ WebSocket
        for ws_cb in self._ws_callbacks:
            try:
                if asyncio.iscoroutinefunction(ws_cb):
                    await ws_cb(msg.to_dict())
                else:
                    ws_cb(msg.to_dict())
            except Exception:
                pass

    def enqueue(self, msg: BusMessage) -> None:
        """إدراج رسالة في طابور الأولويات الحقيقي (priority=2 تسبق 1 وتسبق 0 مع FIFO لنفس الأولوية)."""
        heapq.heappush(self._pq, (-int(msg.priority), next(self._seq), msg))
        if self._dispatch_event is not None:
            self._dispatch_event.set()

    async def dispatch(self, msg: BusMessage) -> None:
        """مسار المنتجين الحيين للتنبيهات: عبر طابور الأولويات إن كان الموزّع شغّالاً، وإلا نشر مباشر
        (فلا تُفقد رسالة أبداً عند عدم تشغيل الموزّع، كما في الاختبارات والأدوات)."""
        if self._dispatcher_task is not None and not self._dispatcher_task.done():
            self.enqueue(msg)
        else:
            await self.publish(msg)

    async def drain_priority_queue(self, max_items: Optional[int] = None) -> int:
        """معالجة الرسائل المكدسة في طابور الأولويات بالترتيب الصارم للأولوية."""
        processed = 0
        while self._pq and (max_items is None or processed < max_items):
            _, _, msg = heapq.heappop(self._pq)
            await self.publish(msg)
            processed += 1
        return processed

    async def publish_batch(self, messages: List[BusMessage]) -> int:
        """نشر دفعة رسائل بترتيب الأولوية التنازلي (طوارئ → عالي → عادي)."""
        for m in messages:
            self.enqueue(m)
        return await self.drain_priority_queue()

    def start_dispatcher(self) -> asyncio.Task:
        """تشغيل موزع طابور الأولويات في الخلفية لوقت التشغيل الحي."""
        if self._dispatcher_task is not None and not self._dispatcher_task.done():
            return self._dispatcher_task
        self._dispatch_event = asyncio.Event()

        async def _loop():
            while True:
                await self.drain_priority_queue()
                self._dispatch_event.clear()
                if not self._pq:
                    await self._dispatch_event.wait()

        self._dispatcher_task = asyncio.create_task(_loop())
        return self._dispatcher_task

    async def stop_dispatcher(self) -> None:
        if self._dispatcher_task is not None and not self._dispatcher_task.done():
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        self._dispatcher_task = None

    def attach_council_bridge(self) -> "CouncilStateBridge":
        """يربط جسر الحالة الحية بين SignalBus ومجلس الوكلاء الخماسي council/."""
        if self._council_bridge is None:
            self._council_bridge = CouncilStateBridge(self)
        return self._council_bridge

    def subscribe(self, topic: str, handler: Callable, priority: int = 0):
        """الاشتراك في موضوع معين (* للكل) مع دعم أولوية تنفيذ المشترك."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append((int(priority), next(self._sub_seq), handler))

    def unsubscribe(self, topic: str, handler: Callable):
        """إلغاء الاشتراك"""
        if topic in self._subscribers:
            self._subscribers[topic] = [item for item in self._subscribers[topic] if item[2] != handler]

    def add_ws_callback(self, callback: Callable):
        self._ws_callbacks.append(callback)

    def remove_ws_callback(self, callback: Callable):
        self._ws_callbacks = [c for c in self._ws_callbacks if c != callback]

    def get_history(self, topic: Optional[str] = None, limit: int = 50) -> List[dict]:
        """آخر N رسالة"""
        if topic:
            msgs = [m for m in self._history if m.topic == topic]
        else:
            msgs = self._history
        return [m.to_dict() for m in msgs[-limit:]]

    def get_agent_comm_stats(self) -> Dict:
        """إحصاءات التواصل بين الوكلاء"""
        return {
            "messages_per_agent": dict(self._agent_messages),
            "topics_per_agent":   {k: dict(v) for k, v in self._comm_stats.items()},
            "total_messages":     len(self._history),
            "active_topics":      list(self._subscribers.keys()),
        }

    # ── اختصارات نشر الأحداث الرئيسية ────────────────────────────────

    async def emit_signal(self, sender: str, symbol: str, direction: str,
                          voting_result: dict, fsm_result: dict,
                          news_score: float = None, shadow: dict = None,
                          confluence: dict = None, signal_id: int = None):
        """إشارة تداول (مع معرّف الإشارة signal_id لربطها التام بالصفقة وقرار المجلس — IMPROVEMENT_PLAN §1)"""
        await self.publish(BusMessage(
            topic    = "signal",
            sender   = sender,
            priority = 1,
            data     = {
                "signal_id": signal_id,
                "symbol":    symbol,
                "direction": direction,
                "voting":    voting_result,
                "fsm":       fsm_result,
                "news_score": news_score,
                "shadow":    shadow,
                "confluence": confluence or {},
            }
        ))

    async def emit_trade_opened(self, sender: str, ticket: int, symbol: str,
                                 direction: str, lot: float, entry: float,
                                 sl: float, tp: float):
        await self.publish(BusMessage(
            topic    = "trade_opened",
            sender   = sender,
            priority = 1,
            data     = {
                "ticket": ticket, "symbol": symbol, "direction": direction,
                "lot": lot, "entry": entry, "sl": sl, "tp": tp,
            }
        ))

    async def emit_trade_closed(self, sender: str, ticket: int, symbol: str, profit: float):
        await self.publish(BusMessage(
            topic    = "trade_closed",
            sender   = sender,
            priority = 1,
            data     = {"ticket": ticket, "symbol": symbol, "profit": profit}
        ))

    async def emit_dd_alert(self, sender: str, dd_pct: float, mode: str):
        await self.dispatch(BusMessage(
            topic    = "dd_alert",
            sender   = sender,
            priority = 2,
            data     = {"dd_pct": dd_pct, "mode": mode}
        ))

    async def emit_agent_log(self, agent: str, level: str, message: str, extra: dict = None):
        await self.publish(BusMessage(
            topic    = "agent_log",
            sender   = agent,
            priority = 0,
            data     = {"level": level, "message": message, **(extra or {})}
        ))

    async def emit_learning_update(self, sender: str, insights: dict):
        """نشر نتائج التعلم لباقي الوكلاء"""
        await self.publish(BusMessage(
            topic    = "learning_update",
            sender   = sender,
            priority = 0,
            data     = insights
        ))

    async def emit_news_alert(self, sender: str, headline: str, impact: str,
                               symbols: List[str], sentiment: str):
        """تنبيه أخبار مهمة"""
        await self.dispatch(BusMessage(
            topic    = "news_alert",
            sender   = sender,
            priority = 2 if impact == "HIGH" else 1,
            data     = {
                "headline":        headline,
                "impact":          impact,
                "related_symbols": symbols,
                "sentiment":       sentiment,
                "recommendation":  "AVOID_NEW_TRADES" if impact == "HIGH" else "CAUTION",
            }
        ))




def _build_council_context(state: Dict[str, Any], symbol: str, regime: str, now: float, ttl_sec: float) -> Dict[str, Any]:
    """
    المنطق الوحيد لتحويل حالة الـ Bus إلى سياق Omega — يستخدمه الجسر الحي وقارئ الملف معاً.
    التنبيهات الأقدم من ttl_sec تُهمَل (انظر DEFAULT_BUS_ALERT_TTL_SEC).
    """
    dd_ts = float(state.get("last_dd_ts", 0.0) or 0.0)
    dd_fresh = dd_ts > 0.0 and (now - dd_ts) <= ttl_sec
    news_ts = float((state.get("news_blackout_ts") or {}).get(symbol, 0.0) or 0.0)
    news_fresh = news_ts > 0.0 and (now - news_ts) <= ttl_sec
    shift_pct = float((state.get("regime_threshold_shifts") or {}).get(regime, 0.0))
    # تحويل التشديد المئوي (مثلاً 5.0%) إلى زيادة منضبطة على عتبة Omega [0.0..0.06]
    omega_shift = round(min(0.06, max(0.0, shift_pct / 100.0)), 4)
    return {
        "emergency_dd_active": bool(state.get("emergency_dd_active", False)) and dd_fresh,
        "last_dd_pct": float(state.get("last_dd_pct", 0.0) or 0.0),
        "news_blackout": news_fresh,
        "bus_threshold_shift": omega_shift,
        "recent_rollback": bool(state.get("recent_rollback", False)),
        "champion_version": int(state.get("last_champion_version", 1) or 1),
    }


def load_council_context(
    symbol: str,
    regime: str,
    state_path: Optional[Path] = None,
    ttl_sec: float = DEFAULT_BUS_ALERT_TTL_SEC,
) -> Optional[Dict[str, Any]]:
    """
    يقرأ حالة الـ Bus التي صدّرها الـ backend (عملية منفصلة) ويعيد سياق Omega.
    يعيد None عند غياب الملف أو تلفه (الـ backend غير شغّال → لا سياق حي، وليس فيتو).
    """
    path = Path(state_path) if state_path else DEFAULT_COUNCIL_STATE_PATH
    try:
        with open(path, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict):
        return None
    return _build_council_context(state, symbol, regime, time.time(), ttl_sec)


class CouncilStateBridge:
    """
    جسر التواصل الموحّد (2026): ينقل أحداث SignalBus الحية
    (meta_learning_update, champion_rollback, dd_alert, news_alert)
    إلى لقطة حالة فورية يستهلكها مجلس الوكلاء (OmegaRiskGovernor / council/).

    المجلس يعمل في عملية منفصلة عن الـ backend، لذا يُصدّر الجسر لقطته إلى ملف ذري
    عند كل حدث (enable_state_export) ليقرأه المجلس عبر load_council_context().
    """

    def __init__(self, bus: SignalBus, ttl_sec: float = DEFAULT_BUS_ALERT_TTL_SEC):
        self.bus = bus
        self.ttl_sec = float(ttl_sec)
        self.regime_threshold_shifts: Dict[str, float] = {}
        self.emergency_dd_active: bool = False
        self.last_dd_pct: float = 0.0
        self.last_dd_mode: str = "NORMAL"
        self.last_dd_ts: float = 0.0
        self.news_blackout_symbols: set = set()
        self._news_blackout_ts: Dict[str, float] = {}
        self.last_champion_version: int = 1
        self.recent_rollback: bool = False
        self._state_path: Optional[Path] = None

        bus.subscribe("dd_alert", self._on_dd_alert, priority=2)
        bus.subscribe("news_alert", self._on_news_alert, priority=2)
        bus.subscribe("meta_learning_update", self._on_meta_learning, priority=1)
        bus.subscribe("champion_rollback", self._on_champion_rollback, priority=1)

    def _on_dd_alert(self, msg: BusMessage) -> None:
        data = msg.data or {}
        self.last_dd_pct = float(data.get("dd_pct", 0.0) or 0.0)
        self.last_dd_mode = str(data.get("mode", "NORMAL"))
        self.last_dd_ts = time.time()
        self.emergency_dd_active = self.last_dd_mode in ("EMERGENCY_STOP", "HARD_STOP", "CRITICAL")
        self._export()

    def _on_news_alert(self, msg: BusMessage) -> None:
        data = msg.data or {}
        if data.get("impact") == "HIGH" and data.get("recommendation") == "AVOID_NEW_TRADES":
            now = time.time()
            for sym in data.get("related_symbols") or []:
                self.news_blackout_symbols.add(sym)
                self._news_blackout_ts[sym] = now
            self._export()

    def _on_meta_learning(self, msg: BusMessage) -> None:
        shifts = (msg.data or {}).get("regime_threshold_shifts") or {}
        for reg, val in shifts.items():
            self.regime_threshold_shifts[str(reg)] = float(val)
        self._export()

    def _on_champion_rollback(self, msg: BusMessage) -> None:
        data = msg.data or {}
        self.last_champion_version = int(data.get("version", self.last_champion_version))
        self.recent_rollback = True
        self._export()

    def clear_emergency_dd(self) -> None:
        self.emergency_dd_active = False
        self.last_dd_mode = "NORMAL"
        self._export()

    def clear_news_blackout(self, symbol: Optional[str] = None) -> None:
        if symbol is None:
            self.news_blackout_symbols.clear()
            self._news_blackout_ts.clear()
        else:
            self.news_blackout_symbols.discard(symbol)
            self._news_blackout_ts.pop(symbol, None)
        self._export()

    def _snapshot(self) -> Dict[str, Any]:
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "emergency_dd_active": self.emergency_dd_active,
            "last_dd_pct": self.last_dd_pct,
            "last_dd_mode": self.last_dd_mode,
            "last_dd_ts": self.last_dd_ts,
            "news_blackout_ts": dict(self._news_blackout_ts),
            "regime_threshold_shifts": dict(self.regime_threshold_shifts),
            "last_champion_version": self.last_champion_version,
            "recent_rollback": self.recent_rollback,
        }

    def enable_state_export(self, path: Optional[Path] = None) -> Path:
        """يفعّل تصدير اللقطة لملف مشترك مع عملية المجلس، ويكتب الحالة الحالية فوراً."""
        self._state_path = Path(path) if path else DEFAULT_COUNCIL_STATE_PATH
        self._export()
        return self._state_path

    def _export(self) -> None:
        if self._state_path is None:
            return
        tmp_path = None
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(self._state_path.parent), prefix=".tmp_council_", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._snapshot(), fh)
            os.replace(tmp_path, self._state_path)
            tmp_path = None
        except Exception as exc:
            # تصدير الحالة خدمة مساندة: فشله يجب ألا يعطّل الـ Bus أو المعالجات الأخرى
            logger.warning(f"[CouncilStateBridge] state export failed: {exc}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def get_council_context(self, symbol: str, regime: str) -> Dict[str, Any]:
        """يعيد سياقاً جاهزاً للتمرير مباشرة إلى OmegaRiskGovernor.adjudicate(bus_context=...)."""
        state = {
            "emergency_dd_active": self.emergency_dd_active,
            "last_dd_pct": self.last_dd_pct,
            "last_dd_ts": self.last_dd_ts,
            "news_blackout_ts": self._news_blackout_ts,
            "regime_threshold_shifts": self.regime_threshold_shifts,
            "last_champion_version": self.last_champion_version,
            "recent_rollback": self.recent_rollback,
        }
        return _build_council_context(state, symbol, regime, time.time(), self.ttl_sec)


# Singleton
_bus_instance: Optional[SignalBus] = None

def get_bus() -> SignalBus:
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = SignalBus()
    return _bus_instance
