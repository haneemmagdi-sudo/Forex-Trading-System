"""
============================================================
base_agent.py — القاعدة المشتركة لجميع الوكلاء
============================================================
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from loguru import logger
from core.signal_bus import SignalBus, get_bus


class AgentStatus(str, Enum):
    IDLE     = "IDLE"
    RUNNING  = "RUNNING"
    PAUSED   = "PAUSED"
    STOPPED  = "STOPPED"
    ERROR    = "ERROR"


class BaseAgent(ABC):
    """القاعدة المشتركة لجميع الوكلاء"""

    def __init__(self, name: str, interval_sec: float = 5.0):
        self.name         = name
        self.interval     = interval_sec
        self.status       = AgentStatus.IDLE
        self.iteration    = 0
        self.errors       = 0
        self.last_run     = None
        self._task        = None
        self._stop_event  = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # غير متوقف افتراضياً
        self.bus: SignalBus = get_bus()
        self.stats        = {}  # إحصائيات خاصة بكل وكيل

    @abstractmethod
    async def run_cycle(self):
        """دورة عمل الوكيل — تُنفَّذ كل N ثانية"""
        pass

    async def start(self):
        """تشغيل الوكيل في الخلفية"""
        if self.status == AgentStatus.RUNNING:
            return
        self._stop_event.clear()
        self._pause_event.set()
        self.status = AgentStatus.RUNNING
        self._task  = asyncio.create_task(self._loop(), name=self.name)
        await self.bus.emit_agent_log(self.name, "INFO", f"▶️ تشغيل الوكيل [{self.name}]")
        logger.info(f"▶️ [{self.name}] بدأ التشغيل")

    async def stop(self):
        """إيقاف الوكيل"""
        self._stop_event.set()
        self._pause_event.set()
        self.status = AgentStatus.STOPPED
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.bus.emit_agent_log(self.name, "INFO", f"⏹️ إيقاف الوكيل [{self.name}]")
        logger.info(f"⏹️ [{self.name}] توقف")

    async def pause(self):
        """إيقاف مؤقت"""
        self._pause_event.clear()
        self.status = AgentStatus.PAUSED
        await self.bus.emit_agent_log(self.name, "INFO", f"⏸️ إيقاف مؤقت [{self.name}]")

    async def resume(self):
        """استئناف"""
        self._pause_event.set()
        self.status = AgentStatus.RUNNING
        await self.bus.emit_agent_log(self.name, "INFO", f"▶️ استئناف [{self.name}]")

    async def _loop(self):
        """حلقة التشغيل الرئيسية"""
        while not self._stop_event.is_set():
            try:
                await self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                self.last_run   = datetime.utcnow().isoformat()
                self.iteration += 1
                await self.run_cycle()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.errors += 1
                self.status  = AgentStatus.ERROR
                logger.error(f"❌ [{self.name}] خطأ في الدورة {self.iteration}: {e}")
                await self.bus.emit_agent_log(self.name, "ERROR", str(e))
                await asyncio.sleep(5)  # انتظر قبل إعادة المحاولة
                self.status = AgentStatus.RUNNING

            await asyncio.sleep(self.interval)

    def get_state(self) -> dict:
        """الحالة الحالية للوكيل"""
        return {
            "name":      self.name,
            "status":    self.status.value,
            "iteration": self.iteration,
            "errors":    self.errors,
            "last_run":  self.last_run,
            "interval":  self.interval,
            **self.stats,
        }

    async def log(self, level: str, message: str, extra: dict = None):
        """تسجيل رسالة في السجل والـ Bus"""
        getattr(logger, level.lower(), logger.info)(f"[{self.name}] {message}")
        await self.bus.emit_agent_log(self.name, level, message, extra)
