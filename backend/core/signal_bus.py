"""
============================================================
signal_bus.py — قناة التواصل بين الوكلاء (asyncio)
============================================================
يتيح للوكلاء تبادل الرسائل بشكل متزامن وآمن
مع دعم: الأولوية، التسجيل، والإحصاءات
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Callable, Optional
from dataclasses import dataclass, field
from loguru import logger
from collections import defaultdict


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
        self._subscribers:  Dict[str, List[Callable]] = {}
        self._history:      List[BusMessage] = []
        self._max_history   = max_history
        self._lock          = asyncio.Lock()
        self._ws_callbacks: List[Callable] = []

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

        # إخطار المشتركين في الموضوع (ومشتركي *)
        handlers = self._subscribers.get(msg.topic, []) + self._subscribers.get("*", [])
        for handler in handlers:
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

    def subscribe(self, topic: str, handler: Callable):
        """الاشتراك في موضوع معين (* للكل)"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable):
        """إلغاء الاشتراك"""
        if topic in self._subscribers:
            self._subscribers[topic] = [h for h in self._subscribers[topic] if h != handler]

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
                          news_score: float = None, shadow: dict = None):
        """إشارة تداول (مع مقياس المشاعر وحكم مجلس الظل — للعرض والقياس فقط)"""
        await self.publish(BusMessage(
            topic    = "signal",
            sender   = sender,
            priority = 1,
            data     = {
                "symbol":    symbol,
                "direction": direction,
                "voting":    voting_result,
                "fsm":       fsm_result,
                "news_score": news_score,
                "shadow":    shadow,
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
        await self.publish(BusMessage(
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
        await self.publish(BusMessage(
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


# Singleton
_bus_instance: Optional[SignalBus] = None

def get_bus() -> SignalBus:
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = SignalBus()
    return _bus_instance
