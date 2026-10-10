"""
============================================================
agent.py — نقطة الدخول لـ MT5 Agent (نسخة محسّنة)
============================================================
يشغّله المستخدم على جهازه (Windows + MT5)
يتصل بـ MT5 محلياً ويرسل البيانات للسحابة
الوكلاء الأربعة يعملون بشكل متكامل ويتواصلون فيما بينهم
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# إضافة مسار backend للـ Python path
BACKEND_PATH = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_PATH))

from loguru import logger
from config_agent import AGENT_TOKEN, CLOUD_URL, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
from cloud_bridge import CloudBridge

# استيراد الوكلاء من backend الموجود
from core.mt5_connector import MT5Connector
from core.signal_bus import get_bus, BusMessage
from agents.market_analyst import MarketAnalystAgent
from agents.execution_agent import ExecutionAgent
from agents.monitor_agent import MonitorAgent
from agents.learning_agent import LearningAgent

# إعداد Logging
logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    colorize=True,
)
logger.add(
    "logs/agent_{time}.log",
    rotation="1 day",
    retention="7 days",
    encoding="utf-8",
    level="DEBUG",
)

VERSION = "1.1.0"


class CloudLogForwarder:
    """يحوّل رسائل Signal Bus إلى سجلات على السحابة"""

    def __init__(self, bridge: CloudBridge):
        self.bridge = bridge
        self.bus = get_bus()
        # الاشتراك في جميع سجلات الوكلاء
        self.bus.subscribe("agent_log", self._on_agent_log)
        self.bus.subscribe("signal", self._on_signal)
        self.bus.subscribe("trade_opened", self._on_trade_event)
        self.bus.subscribe("trade_closed", self._on_trade_event)

    async def _on_agent_log(self, msg: BusMessage):
        """إعادة توجيه سجلات الوكلاء للسحابة"""
        data = msg.data
        self.bridge.queue_log(
            agent_name = msg.sender,
            level      = data.get("level", "INFO"),
            message    = data.get("message", ""),
            symbol     = data.get("symbol"),
        )

    async def _on_signal(self, msg: BusMessage):
        """رفع الإشارة للسحابة"""
        signal_data = msg.data
        self.bridge.queue_signal({
            "symbol":    signal_data.get("symbol"),
            "direction": signal_data.get("direction"),
            "confidence": signal_data.get("voting", {}).get("confidence"),
            "fsm_regime": signal_data.get("fsm", {}).get("regime"),
            "buy_score":  signal_data.get("voting", {}).get("buy_score"),
            "sell_score": signal_data.get("voting", {}).get("sell_score"),
        })

    async def _on_trade_event(self, msg: BusMessage):
        """رفع أحداث الصفقات للسحابة"""
        trade_data = msg.data
        status = "OPEN" if msg.topic == "trade_opened" else "CLOSED"
        self.bridge.queue_trade({
            "ticket":      trade_data.get("ticket"),
            "symbol":      trade_data.get("symbol"),
            "type":        trade_data.get("direction"),
            "status":      status,
            "lot_size":    trade_data.get("lot"),
            "entry_price": trade_data.get("entry"),
            "sl_price":    trade_data.get("sl"),
            "tp_price":    trade_data.get("tp"),
            "profit_usd":  trade_data.get("profit"),
            "opened_at":   datetime.utcnow().isoformat(),
        })


async def run_agent():
    """تشغيل الـ Agent الرئيسي"""
    logger.info("=" * 60)
    logger.info(f"  ⚡ Quantum Forex AI — MT5 Agent v{VERSION}")
    logger.info("=" * 60)
    logger.info(f"  Cloud: {CLOUD_URL}")
    logger.info(f"  MT5 Login: {MT5_LOGIN} @ {MT5_SERVER}")
    logger.info("=" * 60)

    if AGENT_TOKEN == "ضع_agent_token_هنا" or AGENT_TOKEN == "":
        logger.error("❌ لم تُعيَّن AGENT_TOKEN! افتح ملف .env وأضف التوكن من الموقع")
        sys.exit(1)

    # ── الاتصال بالسحابة ───────────────────────────────────────
    bridge = CloudBridge(AGENT_TOKEN, CLOUD_URL)
    await bridge.start()

    # ── الاتصال بـ MT5 ─────────────────────────────────────────
    mt5 = MT5Connector()
    # تعيين بيانات الاتصال من إعدادات الـ Agent
    mt5._login    = MT5_LOGIN
    mt5._password = MT5_PASSWORD
    mt5._server   = MT5_SERVER

    if not mt5.connect():
        logger.warning("[MT5] فشل الاتصال — وضع المحاكاة مُفعَّل")
        bridge.queue_log("Agent", "WARNING", "MT5 غير متصل — وضع المحاكاة فعّال")
    else:
        logger.success(f"[MT5] ✅ متصل بنجاح — الحساب: {MT5_LOGIN}")
        bridge.queue_log("Agent", "INFO", f"MT5 متصل — الحساب: {MT5_LOGIN}@{MT5_SERVER}")

    # ── تهيئة الوكلاء الأربعة ─────────────────────────────────
    analyst  = MarketAnalystAgent(mt5)
    executor = ExecutionAgent(mt5)
    monitor  = MonitorAgent(mt5)
    learner  = LearningAgent(voting_engine=analyst.voting)

    # ── ربط Bus بالسحابة ───────────────────────────────────────
    cloud_forwarder = CloudLogForwarder(bridge)

    # تشغيل الوكلاء
    await executor.start()
    await monitor.start()
    await learner.start()
    await analyst.start()

    logger.success("✅ جميع الوكلاء تعمل!")
    bridge.queue_log("Agent", "INFO", "جميع الوكلاء الأربعة تعمل بنجاح")

    # ── الحلقة الرئيسية ────────────────────────────────────────
    try:
        heartbeat_count = 0
        while True:
            heartbeat_count += 1

            # جمع بيانات الأداء الحالية
            account_info = mt5.get_account()
            positions    = mt5.get_open_positions()

            # حالة الوكلاء الأربعة
            agents_status = {
                "MarketAnalyst":  analyst.get_state(),
                "ExecutionAgent": executor.get_state(),
                "MonitorAgent":   monitor.get_state(),
                "LearningAgent":  learner.get_state(),
            }

            data = {
                "version": VERSION,
                "timestamp": datetime.utcnow().isoformat(),
                "performance": {
                    "balance":      account_info.get("balance", 0),
                    "equity":       account_info.get("equity", 0),
                    "drawdown_pct": mt5.get_drawdown(),
                    "open_trades":  len(positions),
                } if account_info else None,
                "agents": agents_status,
            }

            # ── رفع البيانات واستقبال الأوامر ─────────────────
            commands = await bridge.heartbeat(data)

            # ── تنفيذ أوامر الـ Dashboard ─────────────────────
            for cmd in commands:
                action     = cmd.get("action")
                agent_name = cmd.get("agent")
                target = {
                    "MarketAnalyst":  analyst,
                    "ExecutionAgent": executor,
                    "MonitorAgent":   monitor,
                    "LearningAgent":  learner,
                }.get(agent_name)

                if target:
                    if action == "pause":
                        await target.pause()
                        logger.info(f"[CMD] ⏸ إيقاف مؤقت → {agent_name}")
                    elif action == "resume":
                        await target.resume()
                        logger.info(f"[CMD] ▶ استئناف → {agent_name}")
                    elif action == "stop":
                        await target.stop()
                        logger.info(f"[CMD] ⏹ إيقاف → {agent_name}")

            # طباعة الحالة كل دقيقتين
            if heartbeat_count % 8 == 0:
                cloud_status = "✅ متصل" if bridge.is_connected else "⚠️ أوفلاين"
                mt5_mode = "محاكاة" if mt5._simulation_mode else "حقيقي"
                logger.info(
                    f"[STATUS] السحابة:{cloud_status} | "
                    f"MT5:{mt5_mode} | "
                    f"الصفقات:{len(positions)} | "
                    f"Iteration:{heartbeat_count}"
                )

            await asyncio.sleep(15)  # heartbeat كل 15 ثانية

    except KeyboardInterrupt:
        logger.info("\n[STOP] إيقاف الـ Agent...")
        bridge.queue_log("Agent", "INFO", "إيقاف الـ Agent بأمر المستخدم")
    finally:
        await analyst.stop()
        await learner.stop()
        await monitor.stop()
        await executor.stop()
        mt5.disconnect()
        await bridge.stop()
        logger.info("[STOP] ✅ تم الإيقاف بنجاح")


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    asyncio.run(run_agent())
