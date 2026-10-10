"""
============================================================
cloud_bridge.py — الجسر بين MT5 Agent والسحابة (نسخة محسّنة)
============================================================
يرسل البيانات إلى Next.js API ويستقبل الأوامر
يرسل سجلات الوكلاء والصفقات والإشارات للسحابة في الوقت الفعلي
"""
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger


class CloudBridge:
    """يتواصل مع Next.js API على السحابة"""

    def __init__(self, agent_token: str, cloud_url: str):
        self.agent_token = agent_token
        self.cloud_url   = cloud_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.version = "1.1.0"
        self._connected = False

        # طابور لإرسال البيانات عند انقطاع الشبكة
        self._pending_logs:    List[dict] = []
        self._pending_trades:  List[dict] = []
        self._pending_signals: List[dict] = []

    async def start(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )
        logger.info(f"[CLOUD] Bridge started → {self.cloud_url}")

    async def stop(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("[CLOUD] Bridge stopped")

    # ─────────────────────────────────────────────────────────────
    # Heartbeat — كل 15 ثانية
    # ─────────────────────────────────────────────────────────────
    async def heartbeat(self, data: dict = None) -> list:
        """
        إرسال heartbeat كل 15 ثانية مع البيانات الحالية
        يُعيد قائمة الأوامر المعلّقة من الـ Dashboard
        """
        if not self.session:
            return []

        # تجميع البيانات المعلّقة مع بيانات الـ heartbeat
        payload_data = {
            "version": self.version,
            **(data or {}),
        }

        # إرسال الصفقات المعلّقة
        if self._pending_trades:
            payload_data["trades"] = self._pending_trades[:50]
            self._pending_trades = self._pending_trades[50:]

        # إرسال الإشارات المعلّقة
        if self._pending_signals:
            payload_data["signals"] = self._pending_signals[:50]
            self._pending_signals = self._pending_signals[50:]

        # إرسال سجلات الوكلاء المعلّقة
        if self._pending_logs:
            payload_data["agent_logs"] = self._pending_logs[:100]
            self._pending_logs = self._pending_logs[100:]

        payload = {
            "agent_token": self.agent_token,
            "data": payload_data,
        }

        try:
            async with self.session.post(
                f"{self.cloud_url}/api/mt5/heartbeat",
                json=payload,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if not self._connected:
                        self._connected = True
                        logger.success("[CLOUD] ✅ متصل بالسحابة")
                    return result.get("commands", [])
                elif resp.status == 401:
                    logger.error("[CLOUD] ❌ agent_token غير صالح! تحقق من إعداداتك.")
                    self._connected = False
                elif resp.status == 403:
                    logger.error("[CLOUD] ❌ الاشتراك منتهي — يرجى التجديد من الموقع")
                else:
                    logger.warning(f"[CLOUD] Heartbeat فشل: {resp.status}")
                    self._connected = False
        except asyncio.TimeoutError:
            logger.warning("[CLOUD] Heartbeat timeout — سيُعاد المحاولة")
            self._connected = False
        except aiohttp.ClientConnectorError:
            logger.warning("[CLOUD] تعذّر الاتصال بالسحابة — العمل في وضع محلي")
            self._connected = False
        except Exception as e:
            logger.error(f"[CLOUD] خطأ: {e}")
            self._connected = False

        return []

    # ─────────────────────────────────────────────────────────────
    # إضافة للطوابير (تُرسل في الـ heartbeat التالي)
    # ─────────────────────────────────────────────────────────────
    def queue_signal(self, signal: dict):
        """إضافة إشارة للإرسال في الـ heartbeat القادم"""
        self._pending_signals.append({
            **signal,
            "queued_at": datetime.utcnow().isoformat(),
        })

    def queue_trade(self, trade: dict):
        """إضافة تحديث صفقة للإرسال في الـ heartbeat القادم"""
        self._pending_trades.append({
            **trade,
            "queued_at": datetime.utcnow().isoformat(),
        })

    def queue_log(self, agent_name: str, level: str, message: str, symbol: str = None):
        """إضافة سجل وكيل للإرسال في الـ heartbeat القادم"""
        self._pending_logs.append({
            "agent_name": agent_name,
            "level":      level,
            "message":    message,
            "symbol":     symbol,
            "created_at": datetime.utcnow().isoformat(),
        })
        # تحديد حجم أقصى للطابور لتجنب استهلاك الذاكرة
        if len(self._pending_logs) > 500:
            self._pending_logs = self._pending_logs[-200:]

    # ─────────────────────────────────────────────────────────────
    # الخصائص
    # ─────────────────────────────────────────────────────────────
    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_status(self) -> dict:
        return {
            "connected":        self._connected,
            "cloud_url":        self.cloud_url,
            "pending_logs":     len(self._pending_logs),
            "pending_trades":   len(self._pending_trades),
            "pending_signals":  len(self._pending_signals),
            "version":          self.version,
        }
