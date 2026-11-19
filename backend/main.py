"""
============================================================
main.py — نقطة الدخول وتشغيل نظام تداول وكلاء الذكاء الاصطناعي
============================================================
يشغّل الخادم (FastAPI) ويدير دورة حياة الوكلاء الأربعة:
1. FX Analyst (محلل السوق)
2. Strategy Planner & Execution (منفذ الصفقات)
3. Monitor Agent (متابع الصفقات)
4. Learning Agent (التعلم المستمر)
"""
import sys, os
# Fix Windows encoding issue with Arabic/emoji terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import hmac
import json
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from loguru import logger

from core.mt5_connector import MT5Connector
from core.signal_bus import get_bus, BusMessage
from models.database import (
    create_tables, SessionLocal,
    Trade, Signal, PerformanceSnapshot, AgentLog
)
from agents.market_analyst import MarketAnalystAgent
from agents.execution_agent import ExecutionAgent
from agents.monitor_agent import MonitorAgent
from agents.learning_agent import LearningAgent
from agents.news_agent import NewsAgent
from agents.analyst_cycle_agent import AnalystCycleAgent
from config import SERVER, LOG_FILE, LOG_LEVEL, LOG_ROTATION, LOG_RETENTION

# ── إعدادات الـ Logging ────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL, colorize=False, format="{time:HH:mm:ss} | {level} | {message}")
logger.add(LOG_FILE, rotation=LOG_ROTATION, retention=LOG_RETENTION, level=LOG_LEVEL, encoding='utf-8')

# ── مراجع الوكلاء والاتصال ──────────────────────────────────────────────
mt5 = MT5Connector()
bus = get_bus()

# تعريف الوكلاء كمتغيرات عامة ليتم ملؤها في الـ Lifespan
analyst:  MarketAnalystAgent = None
executor: ExecutionAgent = None
monitor:  MonitorAgent = None
learner:  LearningAgent = None
news:     NewsAgent = None
analyst_team: AnalystCycleAgent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق والوكلاء"""
    global analyst, executor, monitor, learner, news, analyst_team

    logger.info("[DB] Initializing tables...")
    create_tables()

    logger.info("[MT5] Connecting to MetaTrader 5...")
    if not mt5.connect():
        logger.warning("[MT5] No MT5 connection — running with yfinance real data")

    logger.info(f"[DATA] Source: {mt5.data_source}")

    # تهيئة الوكلاء
    logger.info("[AGENTS] Initializing 5 AI Agents...")
    analyst  = MarketAnalystAgent(mt5)
    executor = ExecutionAgent(mt5)
    monitor  = MonitorAgent(mt5)
    learner  = LearningAgent(voting_engine=analyst.voting)
    news     = NewsAgent()
    analyst_team = AnalystCycleAgent(mt5)   # دورة فريق المحللين (قياس فقط، بلا تنفيذ)

    # مجلس الوكلاء في وضع الظل: يحكم على كل إشارة مرشّحة ويُسجَّل للمقارنة
    # دون أي تأثير على التنفيذ. يُوصَل هنا بمُتنبّئ النموذج المُدرَّب الحقيقي.
    from core.agent_council import get_council
    get_council().set_predictor(learner.predict)
    logger.info("[AGENTS] Shadow council armed (mode=shadow, execution impact=none)")

    # تشغيل الوكلاء (الترتيب مهم: executor أولاً ليستمع للإشارات)
    await news.start()      # ابدأ بالأخبار أولاً
    await executor.start()
    await monitor.start()
    await learner.start()
    await analyst.start()
    await analyst_team.start()

    logger.success("[READY] All 5 agents running! Data source: " + mt5.data_source)

    yield

    # When server stops
    logger.info("[STOP] Shutting down all agents...")
    await analyst.stop()
    await learner.stop()
    await monitor.stop()
    await executor.stop()
    await news.stop()
    if analyst_team:
        await analyst_team.stop()
    mt5.disconnect()
    logger.info("[STOP] MT5 disconnected.")

app = FastAPI(
    title="Quantum AI Agents Forex Trading Backend",
    description="نظام تداول الوكلاء الأربعة المتكامل مع MT5",
    version="4.2",
    lifespan=lifespan
)

# ── تفعيل CORS للمتصفح ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket للربط بالـ Dashboard ────────────────────────────────────
active_websockets: list = []

async def broadcast_to_ws(msg_dict: dict):
    """إرسال التحديثات لجميع المتصلين عبر الـ WebSocket"""
    if not active_websockets:
        return
    disconnected = []
    message = json.dumps(msg_dict, ensure_ascii=False, default=str)
    for ws in list(active_websockets):
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

# ربط الـ WS بـ SignalBus
bus.add_ws_callback(broadcast_to_ws)

def _build_status_payload() -> dict:
    """بناء حمولة الحالة الكاملة"""
    return {
        "topic": "system_status",
        "sender": "System",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "mt5_connected":  mt5.connected,
            "mt5_simulation": mt5._simulation_mode,
            "data_source":    mt5.data_source if hasattr(mt5, 'data_source') else 'UNKNOWN',
            "mt5_info":       mt5.account_info,
            "agents": {
                "analyst":  analyst.get_state()  if analyst  else {"status": "OFFLINE"},
                "executor": executor.get_state() if executor else {"status": "OFFLINE"},
                "monitor":  monitor.get_state()  if monitor  else {"status": "OFFLINE"},
                "learner":  learner.get_state()  if learner  else {"status": "OFFLINE"},
                "news":     news.get_state()     if news     else {"status": "OFFLINE"},
            }
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"[WS] New client connected. Total: {len(active_websockets)}")
    try:
        # إرسال الحالة الحالية للعميل فور اتصاله
        await websocket.send_text(
            json.dumps(_build_status_payload(), ensure_ascii=False, default=str)
        )

        while True:
            # استماع لأي رسائل واردة من الواجهة (مثل Pause/Resume)
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
            except json.JSONDecodeError:
                continue

            action     = cmd.get("action")
            agent_name = cmd.get("agent")

            # تنفيذ أوامر التحكم بالوكلاء
            target_agent = None
            if agent_name == "MarketAnalyst":  target_agent = analyst
            elif agent_name == "ExecutionAgent": target_agent = executor
            elif agent_name == "MonitorAgent":   target_agent = monitor
            elif agent_name == "LearningAgent":  target_agent = learner

            if target_agent:
                if action == "pause":
                    await target_agent.pause()
                elif action == "resume":
                    await target_agent.resume()
                elif action == "stop":
                    await target_agent.stop()
                elif action == "start":
                    await target_agent.start()

            # إرسال الحالة المحدَّثة بعد الأمر
            await websocket.send_text(
                json.dumps(_build_status_payload(), ensure_ascii=False, default=str)
            )

    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info("[WS] Client disconnected")
    except Exception as e:
        logger.error(f"[WS] Error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# ── API Endpoints ──────────────────────────────────────────────────────

@app.get("/")
def get_root():
    """تقديم الواجهة الأمامية إذا كانت موجودة"""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {
        "status":        "online",
        "system":        "Quantum AI Agents Forex Trading Backend",
        "version":       "4.2 Elite",
        "mt5_connected": mt5.connected,
        "simulation":    mt5._simulation_mode,
        "docs":          "/docs",
        "ws":            "/ws",
    }

@app.get("/api/health")
@app.get("/health")
def get_health():
    """فحص صحة النظام (Health Check)"""
    return {
        "status": "healthy",
        "system": "Quantum AI Agents Forex Trading Backend",
        "version": "4.2 Elite",
        "mt5_connected": getattr(mt5, 'connected', False),
        "simulation": getattr(mt5, '_simulation_mode', True),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
def get_status():
    """الحصول على الحالة الكاملة للنظام"""
    db = SessionLocal()
    try:
        trades_count  = db.query(Trade).count()
        signals_count = db.query(Signal).count()
        open_trades   = db.query(Trade).filter(Trade.status.in_(["OPEN", "PARTIAL"])).count()
        return {
            "mt5": {
                "connected":    mt5.connected,
                "simulation":   mt5._simulation_mode,
                "data_source":  mt5.data_source if hasattr(mt5, 'data_source') else 'UNKNOWN',
                "account":      mt5.account_info,
                "drawdown":     mt5.get_drawdown(),
            },
            "agents": {
                "analyst":  analyst.get_state()  if analyst  else None,
                "executor": executor.get_state() if executor else None,
                "monitor":  monitor.get_state()  if monitor  else None,
                "learner":  learner.get_state()  if learner  else None,
                "news":     news.get_state()     if news     else None,
            },
            "database": {
                "total_trades":  trades_count,
                "total_signals": signals_count,
                "open_trades":   open_trades,
            },
            "bus_history": bus.get_history(limit=10),
            "agent_communications": bus.get_agent_comm_stats(),
        }
    finally:
        db.close()

@app.get("/api/trades")
def get_trades(limit: int = 50, status: str = None):
    """سجل الصفقات"""
    db = SessionLocal()
    try:
        q = db.query(Trade)
        if status:
            q = q.filter(Trade.status == status)
        trades = q.order_by(Trade.opened_at.desc()).limit(limit).all()
        
        # Merge live metrics for open positions
        try:
            open_positions = mt5.get_open_positions()
            open_map = {pos["ticket"]: pos for pos in open_positions if "ticket" in pos}
        except Exception as e:
            logger.error(f"Error fetching open positions in /api/trades: {e}")
            open_map = {}
            
        results = []
        for t in trades:
            td = t.to_dict()
            if t.status in ("OPEN", "PARTIAL") and t.ticket in open_map:
                pos = open_map[t.ticket]
                td["profit_usd"] = pos.get("profit", td["profit_usd"])
                td["close_price"] = pos.get("current_price", td["close_price"])
                td["entry_price"] = pos.get("open_price", td["entry_price"])
                td["open_price"] = pos.get("open_price", td["open_price"])  # frontend alias
                td["sl_price"] = pos.get("sl", td["sl_price"])
                td["sl"] = pos.get("sl", td["sl"])  # frontend alias
                td["tp_price"] = pos.get("tp", td["tp_price"])
                td["tp"] = pos.get("tp", td["tp"])  # frontend alias
                td["lot_size"] = pos.get("volume", td["lot_size"])
                td["lot"] = pos.get("volume", td["lot"])  # frontend alias
            results.append(td)
        return results
    finally:
        db.close()

@app.get("/api/signals")
def get_signals(limit: int = 50):
    """سجل الإشارات"""
    db = SessionLocal()
    try:
        signals = db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()
        return [s.to_dict() for s in signals]
    finally:
        db.close()

@app.get("/api/latest-analysis")
def get_latest_analysis():
    """آخر تحليلات أزواج العملات"""
    return analyst.latest if analyst else {}

@app.get("/api/performance")
def get_performance():
    """إحصائيات الأداء"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        closed = db.query(Trade).filter(Trade.status == "CLOSED").all()
        total  = len(closed)
        if total == 0:
            return {"total_trades": 0, "win_rate": 0, "total_profit": 0}
        wins      = [t for t in closed if (t.profit_usd or 0) > 0]
        total_pnl = sum(t.profit_usd or 0 for t in closed)
        avg_conf  = sum(t.confidence or 0 for t in closed) / total
        return {
            "total_trades":  total,
            "win_rate":      round(len(wins) / total * 100, 2),
            "total_profit":  round(total_pnl, 2),
            "avg_profit":    round(total_pnl / total, 2),
            "avg_confidence":round(avg_conf, 2),
        }
    finally:
        db.close()

@app.get("/api/bus-history")
def get_bus_history(topic: str = None, limit: int = 50):
    """آخر رسائل Signal Bus"""
    return bus.get_history(topic=topic, limit=limit)

@app.get("/api/open-positions")
def get_open_positions():
    """الصفقات المفتوحة الحالية في MT5"""
    return mt5.get_open_positions()

@app.get("/api/account")
def get_account():
    """بيانات الحساب"""
    return mt5.get_account()

@app.get("/api/learning-logs")
def get_learning_logs(limit: int = 20):
    """سجل التعلم"""
    from models.database import LearningLog
    db = SessionLocal()
    try:
        logs = db.query(LearningLog).order_by(LearningLog.created_at.desc()).limit(limit).all()
        return [
            {
                "id":              l.id,
                "iteration":       l.iteration,
                "trades_analyzed": l.trades_analyzed,
                "win_rate":        l.win_rate,
                "best_regime":     l.best_regime,
                "worst_regime":    l.worst_regime,
                "notes":           l.notes,
                "weight_adjustments": json.loads(l.weight_adjustments or "{}"),
                "created_at":      l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    finally:
        db.close()

@app.get("/api/voting-weights")
def get_voting_weights():
    """أوزان التصويت الحالية"""
    if not analyst:
        return {}
    return {
        "base_weights":       analyst.voting.base_weights,
        "learned_multipliers":analyst.voting.learned_multipliers,
        "min_score":          analyst.voting.min_score,
    }

@app.get("/api/news")
async def get_news(limit: int = 20):
    """أخبار السوق الحقيقية من Finnhub"""
    if not news:
        return {"news": [], "sentiment": {}, "social_buzz": [], "status": "NewsAgent offline"}
    cached = news.get_cached_news()
    return {
        "news":        cached[:limit],
        "sentiment":   news.get_market_sentiment(),
        "social_buzz": news.get_social_buzz(),
        "total":       len(cached),
        "status":      "live" if cached else "fetching",
    }

@app.get("/api/news/calendar")
async def get_economic_calendar():
    """التقويم الاقتصادي الحقيقي من TradingView"""
    if not news or not hasattr(news, 'fetcher') or not news.fetcher:
        return []
    try:
        calendar_data = await news.fetcher.fetch_economic_calendar()
        return calendar_data
    except Exception as e:
        logger.error(f"Error in API get_economic_calendar: {e}")
        return []

@app.get("/api/agent-communications")
def get_agent_communications():
    """إحصاءات التواصل بين الوكلاء"""
    return bus.get_agent_comm_stats()

@app.get("/api/data-source")
def get_data_source():
    """معلومات مصدر البيانات الحالي"""
    return {
        "source":      mt5.data_source if hasattr(mt5, 'data_source') else 'UNKNOWN',
        "mt5_live":    mt5.connected and not getattr(mt5, '_use_yfinance', False),
        "yfinance":    getattr(mt5, '_use_yfinance', False),
        "simulation":  mt5._simulation_mode,
        "real_prices": not mt5._simulation_mode,
        "description": {
            "MT5_LIVE":        "بيانات حقيقية + تنفيذ صفقات حقيقي عبر MT5",
            "YFINANCE_REAL":   "بيانات حقيقية من Yahoo Finance (تأخير 15 دقيقة)",
            "SIMULATION":      "بيانات محاكاة — غير مستخدمة",
        }.get(mt5.data_source if hasattr(mt5, 'data_source') else 'SIMULATION', "غير معروف"),
    }

@app.get("/api/market-sentiment")
def get_market_sentiment():
    """اتجاه السوق من تحليل الأخبار"""
    if not news:
        return {}
    return news.get_market_sentiment()


# ── بوابة بيانات OpenBB (OpenBB Data Layer API) ───────────────────────────
from data_layer.openbb_service import DataService, DataServiceError

try:
    # Use cached configurations or defaults
    data_service = DataService(
        default_equity_provider="yfinance",
        default_macro_provider="fred"
    )
    logger.info("✅ OpenBB DataService loaded successfully in FastAPI.")
except Exception as e:
    logger.error(f"❌ Failed to load OpenBB DataService: {e}")
    data_service = None

@app.get("/api/openbb/historical")
def get_openbb_historical(symbol: str = "EURUSD", start_date: str = "2025-01-01"):
    if not data_service:
        return {"success": False, "error": "OpenBB DataService not initialized"}
    try:
        # Check if forex symbol and adjust format for yfinance (e.g. EURUSD -> EURUSD=X)
        ticker = symbol.upper()
        if "=" not in ticker and len(ticker) == 6:
            ticker = f"{ticker}=X"
            
        df = data_service.get_historical_prices(ticker, start_date=start_date)
        df_reset = df.reset_index()
        if 'index' in df_reset.columns and 'date' not in df_reset.columns:
            df_reset = df_reset.rename(columns={'index': 'date'})
        import pandas as pd
        df_reset['date'] = pd.to_datetime(df_reset['date']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return {
            "success": True,
            "symbol": symbol,
            "data": df_reset.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"[OpenBB API] Error fetching historical prices for {symbol}: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/openbb/macro")
def get_openbb_macro():
    if not data_service:
        return {"success": False, "error": "OpenBB DataService not initialized"}
    try:
        # FRED indicators: Interest Rate (FEDFUNDS), CPI/Inflation (CPIAUCSL), Unemployment (UNRATE)
        indicators = ["FEDFUNDS", "CPIAUCSL", "UNRATE"]
        macro_data = data_service.get_macro_indicators(indicators)
        response_data = {}
        for key, df in macro_data.items():
            df_reset = df.reset_index()
            if 'index' in df_reset.columns and 'date' not in df_reset.columns:
                df_reset = df_reset.rename(columns={'index': 'date'})
            import pandas as pd
            df_reset['date'] = pd.to_datetime(df_reset['date']).dt.strftime('%Y-%m-%d')
            response_data[key] = df_reset.to_dict(orient="records")
        return {
            "success": True,
            "data": response_data
        }
    except Exception as e:
        logger.error(f"[OpenBB API] Error fetching macro indicators: {e}")
        return {"success": False, "error": str(e)}

FOREX_MACRO_DATA = {
    "USD": {
        "rate": "5.25%",
        "inflation": "3.3%",
        "unemployment": "4.0%",
        "gdp_growth": "2.1%",
        "bank": "الفيدرالي الأمريكي (Fed)"
    },
    "EUR": {
        "rate": "4.00%",
        "inflation": "2.4%",
        "unemployment": "6.4%",
        "gdp_growth": "0.8%",
        "bank": "المركزي الأوروبي (ECB)"
    },
    "GBP": {
        "rate": "5.00%",
        "inflation": "2.0%",
        "unemployment": "4.4%",
        "gdp_growth": "0.7%",
        "bank": "بنك إنجلترا (BoE)"
    },
    "JPY": {
        "rate": "0.25%",
        "inflation": "2.5%",
        "unemployment": "2.6%",
        "gdp_growth": "0.3%",
        "bank": "بنك اليابان (BoJ)"
    },
    "AUD": {
        "rate": "4.35%",
        "inflation": "3.6%",
        "unemployment": "4.0%",
        "gdp_growth": "1.1%",
        "bank": "الاحتياطي الأسترالي (RBA)"
    },
    "CAD": {
        "rate": "4.50%",
        "inflation": "2.7%",
        "unemployment": "6.2%",
        "gdp_growth": "1.2%",
        "bank": "بنك كندا (BoC)"
    },
    "CHF": {
        "rate": "1.25%",
        "inflation": "1.3%",
        "unemployment": "2.3%",
        "gdp_growth": "1.0%",
        "bank": "الوطني السويسري (SNB)"
    },
    "NZD": {
        "rate": "5.50%",
        "inflation": "4.0%",
        "unemployment": "4.3%",
        "gdp_growth": "0.2%",
        "bank": "الاحتياطي النيوزيلندي (RBNZ)"
    }
}

@app.get("/api/openbb/fundamentals")
def get_openbb_fundamentals(symbol: str = "AAPL"):
    if not data_service:
        return {"success": False, "error": "OpenBB DataService not initialized"}
    try:
        # Clean symbol to detect forex pairs
        cleaned = symbol.upper().replace("/", "").replace("=X", "").strip()
        if len(cleaned) == 6 and cleaned.isalpha():
            base = cleaned[:3]
            quote = cleaned[3:]
            if base in FOREX_MACRO_DATA and quote in FOREX_MACRO_DATA:
                base_data = FOREX_MACRO_DATA[base]
                quote_data = FOREX_MACRO_DATA[quote]
                try:
                    b_rate = float(base_data["rate"].replace("%", ""))
                    q_rate = float(quote_data["rate"].replace("%", ""))
                    diff = b_rate - q_rate
                    diff_str = f"{diff:+.2f}%"
                except Exception:
                    diff_str = "N/A"
                
                ratios = {
                    "1. سعر فائدة العملة الأساسية": f"{base_data['rate']} ({base_data['bank']})",
                    "2. سعر فائدة عملة المقابلة": f"{quote_data['rate']} ({quote_data['bank']})",
                    "3. فرق سعر الفائدة (Differential)": diff_str,
                    "4. تضخم العملة الأساسية (CPI)": base_data["inflation"],
                    "5. تضخم عملة المقابلة (CPI)": quote_data["inflation"],
                    "6. بطالة العملة الأساسية": base_data["unemployment"],
                    "7. بطالة عملة المقابلة": quote_data["unemployment"],
                    "8. نمو الناتج المحلي للأساسية (GDP)": base_data["gdp_growth"],
                    "9. نمو الناتج المحلي للمقابلة (GDP)": quote_data["gdp_growth"],
                }
                
                health_summary = f"التحليل الأساسي لزوج {base}/{quote}: فارق فائدة يبلغ {diff_str}. تضخم الأساسية {base_data['inflation']} مقابل {quote_data['inflation']} للمقابلة."
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "data": {
                        "symbol": symbol.upper(),
                        "provider": "Central Banks / FRED",
                        "as_of": datetime.now(timezone.utc).isoformat(),
                        "period": "LATEST",
                        "ratios": ratios,
                        "health_summary": health_summary,
                        "raw_df_json": "{}"
                    }
                }

        # Otherwise standard equity fundamentals
        metrics = data_service.get_fundamental_metrics(symbol.upper(), provider="yfinance")
        return {
            "success": True,
            "symbol": symbol,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"[OpenBB API] Error fetching fundamentals for {symbol}: {e}")
        return {"success": False, "error": str(e)}


# ── التواصل مع الوكلاء (Agent Chat API) ───────────────────────────────────
from pydantic import BaseModel
import httpx

class AgentChatRequest(BaseModel):
    agent: str
    message: str

def get_local_fallback_response(system_prompt: str, user_message: str) -> str:
    msg = user_message.lower()
    is_analyst = "marketanalyst" in system_prompt.lower()
    is_executor = "executionagent" in system_prompt.lower()
    is_monitor = "monitoragent" in system_prompt.lower()
    is_learner = "learningagent" in system_prompt.lower()
    is_news = "newsagent" in system_prompt.lower()
    
    if is_analyst:
        if any(w in msg for w in ["eurusd", "يورو", "دولار"]):
            return "مرحباً بك. بتحليل زوج EURUSD حالياً، السعر يقع في وضع FSM Regime متوازن وسبريد مستقر. لا توجد إشارات دخول قوية حالياً، ونحن نراقب السعر عند مستويات الدعم والمقاومة التاريخية."
        if any(w in msg for w in ["صفقة", "دخول", "اشارة", "إشارة"]):
            return "نقوم بمسح أزواج العملات باستمرار. ننتقل فقط للفرص ذات الثقة العالية (>75%) وتصويت FSM الإيجابي لتقليل التراجعات الحادة."
        return "أنا الوكيل المحلل. أراقب الشارت والسيولة وأحلل المؤشرات الفنية الـ 9. هل تود الاستفسار عن زوج معين أو حالة FSM الحالية؟"
        
    elif is_executor:
        if any(w in msg for w in ["خسارة", "مخاطرة", "لوت", "حجم"]):
            return "نحن نطبق إدارة مخاطر صارمة بحد أقصى 1% مخاطرة لكل صفقة، مع حجم لوت أساسي 0.01 لضمان الأمان الفائق للمحفظة."
        return "أنا الوكيل المنفذ. مهمتي هي دقة الدخول وفتح وإغلاق الصفقات وإرسال التيكت لـ MT5. المحفظة آمنة تماماً وكل الأوامر مرتبطة بـ SL و TP."
        
    elif is_monitor:
        if any(w in msg for w in ["حالة", "ربح", "تراجع", "drawdown"]):
            return "أراقب المحفظة والصفقات المفتوحة 24/7. نطبق وقف خسارة متحرك (Trailing Stop) وتصفية جزئية لحماية الأرباح عند حدوث انعكاسات."
        return "أنا الوكيل المراقب. أعمل على حماية الحساب من Drawdown وتأمين الصفقات المفتوحة وتحديث وقف الخسارة ونقله للتعادل."
        
    elif is_learner:
        return "أنا وكيل التعلم الآلي. أدرس الصفقات السابقة لتحديث أوزان مجلس التصويت فنيًا. دقة نموذج التعلم الآلي ومعدل الربح الحالي يتم تحديثهما دورياً."
        
    elif is_news:
        return "أنا وكيل الأخبار. أتابع التقويم الاقتصادي مباشرة. عند صدور أخبار عالية التأثير (HIGH)، أقوم بتفعيل درع الأخبار (News Shield) لمنع أي دخول عشوائي."
        
    return "أهلاً بك. أنا وكيل التداول الذكي الخاص بك. كيف يمكنني مساعدتك اليوم في توجيه استراتيجيتك؟"

async def call_llm(system_prompt: str, user_message: str) -> str:
    modal_key = os.getenv("MODAL_API_KEY")
    modal_url = os.getenv("MODAL_BASE_URL", "https://api.us-west-2.modal.direct/v1")
    modal_model = os.getenv("MODAL_MODEL", "zai-org/GLM-5.1-FP8")
    
    github_key = os.getenv("GITHUB_MODELS_TOKEN")
    github_model = os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini")
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    groq_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    ollama_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # 1. Try Modal first
    if modal_key and not modal_key.startswith("your_") and modal_key != "modalresearch_HfCj7VBGKH9ZXY82GIWjNpMdW9Taa0YxFvvLTVmEaYQ":
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    f"{modal_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {modal_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": modal_model,
                        "messages": messages,
                        "temperature": 0.7
                    }
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                logger.warning(f"[LLM] Modal status {res.status_code}")
        except Exception as e:
            logger.warning(f"[LLM] Modal error: {e}")
            
    # 2. Try GitHub Models next
    if github_key and not github_key.startswith("your_"):
        try:
            url = "https://models.inference.ai.azure.com/chat/completions"
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {github_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": github_model,
                        "messages": messages,
                        "temperature": 0.7
                    }
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                logger.warning(f"[LLM] GitHub Models status {res.status_code}")
        except Exception as e:
            logger.warning(f"[LLM] GitHub Models error: {e}")
            
    # 3. Try Gemini next
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={gemini_key}"
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": gemini_model,
                        "messages": messages,
                        "temperature": 0.7
                    }
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                logger.warning(f"[LLM] Gemini status {res.status_code}")
        except Exception as e:
            logger.warning(f"[LLM] Gemini error: {e}")

    # 4. Try Groq next
    if groq_key and not groq_key.startswith("your_"):
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": groq_model,
                        "messages": messages,
                        "temperature": 0.7
                    }
                )
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                logger.warning(f"[LLM] Groq status {res.status_code}")
        except Exception as e:
            logger.warning(f"[LLM] Groq error: {e}")

    # 5. Try Ollama next
    if ollama_enabled:
        try:
            url = f"{ollama_url.rstrip('/')}/api/chat"
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(
                    url,
                    json={
                        "model": ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.7}
                    }
                )
                if res.status_code == 200:
                    return res.json()["message"]["content"]
        except Exception as e:
            logger.warning(f"[LLM] Ollama error: {e}")

    return get_local_fallback_response(system_prompt, user_message)

def _get_agent_context() -> str:
    """Build a rich, real-time context block injected into every agent's system prompt."""
    try:
        # ── Account Info (real MT5 or yfinance fallback) ──────────────
        acc_info = mt5.account_info or {}
        balance      = acc_info.get("balance", 0)
        equity       = acc_info.get("equity", 0)
        profit       = acc_info.get("profit", 0)
        margin_free  = acc_info.get("margin_free", 0)
        margin_level = acc_info.get("margin_level", 0)
        drawdown_pct = mt5.get_drawdown() if hasattr(mt5, 'get_drawdown') else 0
        data_source  = mt5.data_source if hasattr(mt5, 'data_source') else 'UNKNOWN'

        # ── Open Positions ────────────────────────────────────────────
        open_pos = mt5.get_open_positions() or []
        open_pos_lines = []
        total_open_profit = 0.0
        for p in open_pos:
            sym    = p.get('symbol', 'UNK')
            ptype  = 'LONG' if p.get('type', 0) == 0 else 'SHORT'
            lot    = p.get('volume', 0)
            ep     = p.get('price_open', p.get('entry_price', 0))
            cur    = p.get('price_current', 0)
            pnl    = p.get('profit', 0)
            total_open_profit += pnl
            open_pos_lines.append(
                f"  • {sym} | {ptype} | Lot={lot} | Entry={ep:.5f} | Now={cur:.5f} | P&L={pnl:+.2f}$"
            )
        open_pos_str = "\n".join(open_pos_lines) if open_pos_lines else "  لا توجد صفقات مفتوحة حالياً."

        # ── Live Market Analysis per pair (real indicators) ───────────
        regimes_lines = []
        analyst_strategies = []
        if analyst and hasattr(analyst, 'latest'):
            for sym, an in list(analyst.latest.items())[:8]:
                if not an:
                    continue
                price    = an.get('price', an.get('rate', 0))
                fsm      = an.get('fsm', {})
                regime   = fsm.get('regime', 'N/A')
                indic    = an.get('indicators', {})
                voting   = an.get('voting', {})
                rsi      = indic.get('RSI_14', indic.get('rsi', 'N/A'))
                macd     = indic.get('MACD', indic.get('macd', 'N/A'))
                atr      = indic.get('ATR_14', indic.get('atr', 'N/A'))
                ema      = indic.get('EMA_50', indic.get('ema', 'N/A'))
                adx      = indic.get('ADX_14', indic.get('adx', 'N/A'))
                signal   = an.get('overall_signal', an.get('signal', 'N/A'))
                score    = voting.get('confidence', voting.get('score', 0))
                action   = an.get('recommended_action', 'WATCH')
                regimes_lines.append(
                    f"  • {sym}: Price={price} | Signal={signal} | Regime={regime} | "
                    f"RSI={rsi} | MACD={macd} | ATR={atr} | EMA50={ema} | ADX={adx} | "
                    f"Score={score}% | Action={action}"
                )
                if action in ('CONSIDER_LONG', 'CONSIDER_SHORT', 'BUY', 'SELL'):
                    analyst_strategies.append(f"{sym}→{action}(conf={score}%)")
        regimes_str = "\n".join(regimes_lines) if regimes_lines else "  لا تتوفر بيانات تحليل السوق بعد."
        hot_signals_str = ", ".join(analyst_strategies) if analyst_strategies else "لا توجد إشارات نشطة حالياً"

        # ── ML Model Stats (real accuracy + iterations) ───────────────
        ml_str = "غير متاح"
        if learner:
            ml_acc   = getattr(learner, '_model_accuracy', None)
            ml_iter  = learner.stats.get('iterations', 0) if hasattr(learner, 'stats') else 0
            ml_trades= learner.stats.get('total_trades_analyzed', 0) if hasattr(learner, 'stats') else 0
            ml_wr    = learner.stats.get('current_win_rate', None) if hasattr(learner, 'stats') else None
            best_reg = learner.stats.get('best_regime', 'N/A') if hasattr(learner, 'stats') else 'N/A'
            worst_reg= learner.stats.get('worst_regime', 'N/A') if hasattr(learner, 'stats') else 'N/A'
            ml_str = (
                f"دقة={ml_acc:.1%} | دورات التعلم={ml_iter} | صفقات محللة={ml_trades} | "
                f"نسبة الربح={ml_wr:.1%} | أفضل Regime={best_reg} | أسوأ Regime={worst_reg}"
            ) if ml_acc is not None and ml_wr is not None else (
                f"دورات التعلم={ml_iter} | صفقات محللة={ml_trades} (النموذج لم يتدرب بعد)"
            )

        # ── Real News (cached from Finnhub / RSS) ─────────────────────
        news_lines = []
        if news:
            for n in (news.get_cached_news() or [])[:5]:
                impact    = n.get('impact', 'LOW')
                headline  = n.get('headline', n.get('title', ''))[:90]
                sentiment = n.get('sentiment', 'neutral')
                symbol_n  = n.get('symbol', n.get('category', ''))
                news_lines.append(f"  [{impact}] {symbol_n}: {headline} (Sentiment={sentiment})")
        news_str = "\n".join(news_lines) if news_lines else "  لا تتوفر أخبار في الوقت الحالي."

        # ── News Shield status ────────────────────────────────────────
        shield_active = False
        if news and hasattr(news, 'get_market_sentiment'):
            sent = news.get_market_sentiment() or {}
            shield_active = sent.get('shield_active', False)

        now_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 بيانات حقيقية ومباشرة — Antigravity Trading System
🕒 الوقت: {now_utc} | مصدر البيانات: {data_source}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 حالة الحساب (لحظية):
  الرصيد:      {balance:,.2f}$
  الإكويتي:    {equity:,.2f}$
  الربح المفتوح:{total_open_profit:+.2f}$
  هامش حر:    {margin_free:,.2f}$
  مستوى الهامش:{margin_level:.1f}%
  التراجع:     {drawdown_pct:.2f}%

📂 الصفقات المفتوحة ({len(open_pos)} صفقة):
{open_pos_str}

📈 تحليل السوق الحي (مؤشرات حقيقية):
{regimes_str}

⚡ الإشارات النشطة الآن:
  {hot_signals_str}

🧠 أداء نموذج التعلم الآلي:
  {ml_str}

📰 آخر الأخبار الحقيقية (Finnhub):
{news_str}
  درع الأخبار: {'🔴 نشط — تداول محظور' if shield_active else '🟢 غير نشط — تداول مسموح'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    except Exception as e:
        logger.error(f"Error building agent context: {e}")
        return "\n(لم نتمكن من جلب سياق النظام الحي — تحقق من تشغيل الـ Backend)\n"

@app.post("/api/agents/chat")
async def agents_chat(req: AgentChatRequest):
    """بوابة الدردشة والتواصل المباشر مع الوكلاء"""
    agent_prompts = {
        "MarketAnalyst": (
            "أنت 'محلل السوق' (Market Analyst) - العقل المدبر والعيون التقنية لنظام التداول الكمي Quantum FSM Pro.\n"
            "مهمتك تحليل 9 مؤشرات فنية وتحديد الـ FSM Regimes ورصد مناطق السيولة وكتل الأوامر (Order Blocks).\n"
            "تحدث بلهجة احترافية مالية دقيقة، وقدم نصائح فنية بناءً على معطيات السوق المرفقة وسؤال المستخدم.\n"
        ),
        "ExecutionAgent": (
            "أنت 'منفذ الصفقات' (Execution Agent) - اليد الحديدية المسؤول عن تنفيذ أوامر التداول وإدارة اللوت وحماية الحساب.\n"
            "مهمتك إدارة المخاطر وتأكيد الصفقات بناءً على SL و TP وحسابات ATR.\n"
            "تحدث بلهجة سريعة، صارمة، وموجهة نحو الأرقام والسلامة الحسابية.\n"
        ),
        "MonitorAgent": (
            "أنت 'مراقب الصفقات' (Monitor Agent) - الحارس الأمين للصفقات المفتوحة لحمايتها من الـ Drawdown.\n"
            "مهمتك تحديث وقف الخسارة المتحرك (Trailing Stop)، وإدارة الإغلاق الجزئي (Partial TP).\n"
            "تحدث بلهجة حذرة ومحبة للأمان والحد من الخسارة والتراجع.\n"
        ),
        "LearningAgent": (
            "أنت 'وكيل التعلم الآلي' (Learning Agent) - العقل المفكر الإحصائي للنظام.\n"
            "مهمتك دراسة الصفقات التاريخية باستخدام نماذج GradientBoosting لتحديث أوزان التصويت الفنية.\n"
            "استخدم الأرقام الحقيقية من سياق النظام (دقة النموذج، عدد الصفقات المحللة، Regimes) في إجاباتك.\n"
            "تحدث بلهجة علمية، إحصائية، ومبنية على البيانات الرياضية ودقة النماذج.\n"
        ),
        "NewsAgent": (
            "أنت 'محلل الأخبار' (News Agent) - المسؤول عن التقويم الاقتصادي ودرع حماية الأخبار (News Shield).\n"
            "مهمتك فحص الأخبار عالية التأثير وحظر التداول مؤقتاً لتفادي تقلبات السوق العنيفة.\n"
            "استخدم الأخبار الحقيقية من السياق المرفق في إجاباتك، وأشر دائماً لحالة درع الأخبار الفعلية.\n"
            "تحدث بلهجة إخبارية حيوية وسريعة ومركزة على المؤشرات الاقتصادية الكبرى.\n"
        ),
        "StrategyPlanner": (
            "أنت 'المخطط الاستراتيجي' (Strategy Planner) - عقل التخطيط الكمي المتقدم في نظام Antigravity.\n"
            "مهمتك تصميم استراتيجيات تداول دقيقة بناءً على:\n"
            "  • تحليل SMC (Smart Money Concepts): Order Blocks، Fair Value Gaps (FVG)، Liquidity Pools.\n"
            "  • حساب حجم اللوت الأمثل بناءً على الرصيد الحي وقواعد إدارة المخاطر (1-3% للصفقة).\n"
            "  • تحديد مستويات الدخول (Entry)، وقف الخسارة (SL)، وجني الأرباح (TP) بدقة هندسية.\n"
            "  • اعتبار نسبة المخاطرة/العائد (R:R) لا تقل عن 1.5:1.\n"
            "  • مراعاة حالة السوق الحالية (Regime، ATR، سيولة الجلسة).\n"
            "استخدم الأسعار والمؤشرات الحقيقية من السياق المرفق. لا تقترح استراتيجية عامة دون أرقام محددة.\n"
            "قدّم خطتك في صيغة منظمة: الإجراء (BUY/SELL)، نقطة الدخول، SL، TP، حجم اللوت، المبرر.\n"
            "تحدث بلهجة المحلل الكمي الاحترافي — دقيق، مباشر، مبني على البيانات.\n"
        )
    }
    
    agent_key = req.agent
    # Fallback to MarketAnalyst if key is not found
    if agent_key not in agent_prompts:
        agent_key = "MarketAnalyst"
        
    base_prompt = agent_prompts[agent_key]
    system_context = _get_agent_context()
    
    full_system_prompt = (
        f"{base_prompt}\n"
        "تعليمات هامة:\n"
        "1. يجب أن تتصرف بالكامل كشخصية الوكيل المحدد وتجيب وفق اختصاصه ولهجته.\n"
        "2. استخدم بيانات السوق الحية المرفقة أدناه لتدعيم إجابتك وجعلها واقعية ومرتبطة بصفقات المستخدم ورصيده الحالي.\n"
        "3. اكتب إجابتك باللغة العربية بأسلوب واضح ومحترف وجميل.\n\n"
        f"{system_context}"
    )
    
    try:
        reply = await call_llm(full_system_prompt, req.message)
        return {"agent": req.agent, "response": reply}
    except Exception as e:
        logger.error(f"Error in agents_chat endpoint: {e}")
        return {"agent": req.agent, "response": f"عذراً، واجهت مشكلة أثناء محاولة معالجة رسالتك: {e}"}


@app.post("/api/ml/predict")
def ml_predict(features: dict):
    """
    التنبؤ بجودة إشارة تداول باستخدام نموذج ML المدرب
    features: {buy_score, sell_score, confidence, ema, rsi, macd, adx, atr}
    returns: {probability, quality, model_trained}
    """
    if not learner:
        return {"probability": 0.5, "quality": "UNKNOWN", "model_trained": False}

    feat_list = [
        features.get("buy_score", 0),
        features.get("sell_score", 0),
        features.get("confidence", 0),
        features.get("ema", 0),
        features.get("rsi", 50),
        features.get("macd", 0),
        features.get("adx", 0),
        features.get("atr", 0),
    ]
    prob = learner.predict(feat_list)
    quality = "HIGH" if prob > 0.75 else "MEDIUM" if prob > 0.50 else "LOW"
    return {
        "probability":   round(prob, 4),
        "quality":       quality,
        "model_trained": learner._model is not None,
        "model_accuracy":learner._model_accuracy,
    }


@app.get("/api/ml/info")
def ml_info():
    """معلومات نموذج التعلم الآلي"""
    if not learner:
        return {"status": "OFFLINE"}
    return {
        "status":         "READY" if learner._model is not None else "TRAINING_NEEDED",
        "model_trained":  learner._model is not None,
        "model_accuracy": learner._model_accuracy,
        "iterations":     learner.stats.get("iterations", 0),
        "trades_analyzed":learner.stats.get("total_trades_analyzed", 0),
        "best_regime":    learner.stats.get("best_regime"),
        "worst_regime":   learner.stats.get("worst_regime"),
        "current_win_rate":learner.stats.get("current_win_rate"),
        "weight_updates": learner.stats.get("weight_updates", 0),
        "last_analysis":  learner.stats.get("last_analysis"),
        "model_path":     learner.stats.get("model_path"),
    }


@app.post("/api/ml/train-now")
async def ml_train_now():
    """تشغيل دورة تعلم فورية"""
    if not learner:
        return {"success": False, "error": "LearningAgent offline"}
    try:
        await learner.run_cycle()
        return {
            "success":        True,
            "model_accuracy": learner._model_accuracy,
            "iterations":     learner.stats.get("iterations", 0),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── بوابات الأنظمة المؤسسية (Institutional MAS & TradingView Webhooks) ──────
try:
    from core.execution_bridge import InstitutionalExecutionBridge
    inst_bridge = InstitutionalExecutionBridge()
except Exception as e:
    logger.warning(f"Could not initialize InstitutionalExecutionBridge: {e}")
    inst_bridge = None


@app.post("/api/webhook/tradingview")
async def tradingview_webhook(payload: dict):
    """
    استقبال تنبيهات واستراتيجيات TradingView Pine Script عبر الويب هوك فائق السرعة
    مع تمريرها الإلزامي عبر الغربلة الهرمية (Hierarchical MAS Filter)
    """
    symbol = payload.get("symbol", "EURUSD").replace("/", "").upper()
    action = payload.get("action", "BUY").upper()
    secret = payload.get("secret", "")

    # تحقق أمني بسيط
    if secret and secret != os.getenv("WEBHOOK_SECRET", "ANTIGRAVITY_HEDGE_2026"):
        return {"status": "UNAUTHORIZED", "message": "Invalid webhook secret."}

    logger.info(f"[WEBHOOK] Received TradingView alert: {action} {symbol} @ {payload.get('price')}")

    if not inst_bridge:
        return {"status": "OFFLINE", "message": "Institutional bridge is offline."}

    # جلب بيانات الشموع الحية من MT5
    df = mt5.get_ohlcv(symbol, bars=60)
    if df is None or len(df) < 30:
        return {"status": "REJECTED", "reason": "Insufficient live market data for validation."}

    price_series = {
        "closes": df["close"].tolist(),
        "opens":  df["open"].tolist(),
        "highs":  df["high"].tolist(),
        "lows":   df["low"].tolist(),
        "volumes":df["volume"].tolist() if "volume" in df.columns else [100.0] * len(df),
    }

    receipt = inst_bridge.process_entry_candidate(
        symbol=symbol,
        proposed_action=action,
        price_series=price_series,
    )

    if receipt.approved:
        logger.success(f"[INSTITUTIONAL MAS] Signal APPROVED for {symbol} {action}! Confidence={receipt.consensus_confidence}% | Latency={receipt.latency_ms}ms")
        # إذا كان مصرحاً، نمررها لمحرك التنفيذ المباشر
        if executor and getattr(executor, "is_running", False):
            await bus.publish(BusMessage(
                topic="signal",
                sender="InstitutionalMAS",
                data={
                    "symbol": symbol,
                    "direction": action,
                    "confidence": receipt.consensus_confidence,
                    "source": "TradingView_PineScript_MAS",
                }
            ))
        return {
            "status": "APPROVED",
            "symbol": symbol,
            "action": action,
            "confidence": receipt.consensus_confidence,
            "latency_ms": receipt.latency_ms,
            "details": receipt.details,
        }
    else:
        logger.warning(f"[INSTITUTIONAL MAS] Signal REJECTED: {receipt.rejection_stage} - {receipt.rejection_reason}")
        return {
            "status": "VETOED",
            "symbol": symbol,
            "action": action,
            "stage": receipt.rejection_stage,
            "reason": receipt.rejection_reason,
            "latency_ms": receipt.latency_ms,
        }


@app.get("/api/institutional/status")
def institutional_mas_status():
    """
    حالة حقيقية لطبقات الوكلاء المؤسسية.
    تعكس ما يعمل فعلاً (مجلس الظل، الجسر، المنتجون المتاحون) بدل إعلان
    كل الطبقات «ACTIVE» نصاً ثابتاً بلا أي فحص — كما كان سابقاً.
    """
    from core.agent_council import get_council

    council = get_council().status(probe=True)
    webhook_secret_set = bool(os.getenv("WEBHOOK_SECRET", "").strip())
    layer_state = "shadow" if council["bridge_ready"] else "unavailable"

    return {
        "council": council,
        "tradingview_webhook": {
            "endpoint_ready": True,
            "secret_configured": webhook_secret_set,
            "warning": None if webhook_secret_set else
                       "WEBHOOK_SECRET غير مضبوط — الفحص يعتمد على قيمة افتراضية مكتوبة في الكود",
        },
        "onnx_mql5_bridge": {
            "ready": False,
            "reason": "لا يوجد ملف .onnx ولا أي EA يضم الجسر",
        },
        "layers": {
            "blackboard_consensus": "shadow" if council["engine_ready"] else "unavailable",
            "market_regime_hmm": layer_state,
            "microstructure_order_flow": layer_state,
            "multi_agent_debate": layer_state,
            "cross_asset_agent": "shadow (static macro inputs)" if council["bridge_ready"] else "unavailable",
            "risk_adjusted_rl": "not wired (no trained policy)",
            "ml_ensemble_gate": "skipped (no trained RF/LSTM/DQN outputs)",
        },
        "note": "كل الطبقات في وضع الظل: تُحسب وتُسجَّل ولا تؤثر على التنفيذ.",
    }


@app.get("/api/council/report")
def council_report(limit: int = 2000):
    """
    تقرير قياس إضافة مجلس الوكلاء: يقارن حكم المجلس بالنتائج الفعلية
    المُسجَّلة، ويجيب بسؤال واحد: هل كان فيتو المجلس سيوفر خسائر أم سيمنع أرباحاً؟
    """
    from sqlalchemy import text
    from core.agent_council import get_council
    from models.database import engine, Base, SessionLocal, AgentReflection

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass

    # نفس مصدر الدليل الذي تستخدمه بوابة التمكين — فلا يختلف التقرير عن القرار
    council  = get_council()
    evidence = council.collect_evidence(limit=limit)

    reflections = []
    try:
        db = SessionLocal()
        reflections = [
            r.to_dict()
            for r in db.query(AgentReflection).order_by(AgentReflection.id.desc()).limit(10).all()
        ]
        db.close()
    except Exception:
        pass

    gate = {"enabled": council.filter_enabled(), "reason": council.gate_reason()}

    if not evidence.get("available"):
        return {
            "status": "UNAVAILABLE",
            "error": evidence.get("error"),
            "filter": gate,
            "hint": "أعد تشغيل الخادم لإنشاء الجداول الجديدة",
        }

    return {
        "status": "OK",
        "filter": gate,
        "linked_to_closed_trades": evidence["linked_trades"],
        "agreement_rate": evidence["agreement_rate"],
        "cohorts": evidence["cohorts"],
        "veto_counterfactual": {
            "losses_avoided_usd": evidence["losses_avoided_usd"],
            "wins_missed_usd": evidence["wins_missed_usd"],
            "net_effect_of_veto_usd": evidence["veto_net_effect_usd"],
            "interpretation": "قيمة موجبة = الفيتو كان سيربح (تفادي خسائر أكبر من أرباح فائتة)",
        },
        "block_reasons": evidence["block_reasons"],
        "ml_signal_quality": evidence["ml_quality"],
        "recent_reflections": reflections,
    }


@app.get("/api/analyst/report")
def analyst_team_report(limit: int = 20):
    """
    تقرير فريق المحللين: آخر دورات الفريق ومخرجاتها
    (تقارير → مقترح → قرار المدير التنفيذي → حكم المخاطر).
    للقياس فقط: لا مقترح يُنفَّذ تلقائياً.
    """
    from sqlalchemy import func
    from models.database import engine, Base, SessionLocal, AnalystCycle

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass

    try:
        db = SessionLocal()
        cycles = db.query(AnalystCycle).order_by(AnalystCycle.id.desc()).limit(limit).all()
        total = db.query(func.count(AnalystCycle.id)).scalar() or 0
        with_proposal = db.query(func.count(AnalystCycle.id)).filter(
            AnalystCycle.proposal_symbol.isnot(None)
        ).scalar() or 0
        db.close()
    except Exception as exc:
        return {"status": "UNAVAILABLE", "error": str(exc)}

    return {
        "status": "OK",
        "note": "قياس فقط: مقترحات الفريق لا تُنفَّذ",
        "interval_min": (round((analyst_team.interval or 3600) / 60, 1) if analyst_team else None),
        "cycles_total": total,
        "cycles_with_proposal": with_proposal,
        "stats": (analyst_team.stats if analyst_team else {"state": "not started"}),
        "recent": [cycle.to_dict() for cycle in cycles],
    }


# ── وكيل صيانة وترميم الأكواد (Self-Healing Code Agent Endpoints) ───────────
try:
    from institutional.code_healing_agent import CodeHealingAgent, AgentExecutionMode
    healing_agent = CodeHealingAgent(mode=AgentExecutionMode.SUGGEST_MODE)
except Exception as e:
    logger.warning(f"Could not initialize CodeHealingAgent: {e}")
    healing_agent = None


# جذر المشروع — لا يُسمح لوكيل الترميم بلمس أي ملف خارج هذا الجذر
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def require_healing_token(x_healing_token: str = Header(default=None)):
    """
    بوابة مصادقة لنقاط نهاية الترميم — تفشل مغلقة.
    إن لم يكن HEALING_TOKEN مضبوطاً في .env فالنقاط معطّلة بالكامل (503).
    """
    expected = os.getenv("HEALING_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Healing endpoints disabled: set HEALING_TOKEN in .env to enable them.",
        )
    if not x_healing_token or not hmac.compare_digest(x_healing_token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Healing-Token header.")


def confined_source_path(file_path: str) -> str:
    """
    يحصر المسار داخل جذر المشروع ويقبل ملفات الكود فقط.
    يمنع قراءة أو كتابة ملفات النظام أو ملفات الأسرار مثل .env أو trading.db.
    """
    if not file_path or not file_path.strip():
        raise HTTPException(status_code=400, detail="file_path is required.")
    base     = file_path if os.path.isabs(file_path) else os.path.join(PROJECT_ROOT, file_path)
    resolved = os.path.realpath(base)
    if resolved != PROJECT_ROOT and not resolved.startswith(PROJECT_ROOT + os.sep):
        raise HTTPException(status_code=400, detail="file_path must be inside the project directory.")
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if healing_agent.detect_language(resolved).value == "UNKNOWN":
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    return resolved


@app.post("/api/healing/diagnose", dependencies=[Depends(require_healing_token)])
def healing_diagnose(req: dict):
    """تشخيص الكود عبر شجرة AST وعزل الخطأ البرمجي بدقة (يتطلب ترويسة X-Healing-Token)"""
    if not healing_agent:
        return {"status": "OFFLINE", "message": "CodeHealingAgent is offline."}

    file_path = confined_source_path(req.get("file_path", ""))
    error_msg = req.get("error_message")
    line_num  = req.get("target_line")

    diag = healing_agent.diagnose_file(file_path, error_message=error_msg, target_line=line_num)
    return {
        "file_path":           diag.file_path,
        "language":            diag.language.value,
        "error_type":          diag.error_type,
        "line_number":         diag.line_number,
        "column_number":       diag.column_number,
        "error_message":       diag.error_message,
        "target_symbol_name":  diag.target_symbol_name,
        "slice_start_line":    diag.slice_start_line,
        "slice_end_line":      diag.slice_end_line,
        "enclosing_code_slice":diag.enclosing_code_slice,
    }


@app.post("/api/healing/heal", dependencies=[Depends(require_healing_token)])
def healing_execute(req: dict):
    """
    توليد رقعة إصلاح وعرضها للمراجعة فقط:
    [تشخيص] ──> [عزل AST] ──> [توليد الرقعة] ──> [بوابة التحقق الحتمي]

    لا يكتب على أي ملف: الوضع مفروض دائماً على SUGGEST_MODE، ولم يعد بإمكان
    الطلب تفعيل AUTONOMOUS_SANDBOX (كان ذلك يتيح تنفيذ كود وتعديل ملفات عن بُعد).
    """
    if not healing_agent:
        return {"status": "OFFLINE", "message": "CodeHealingAgent is offline."}

    file_path  = confined_source_path(req.get("file_path", ""))
    error_msg  = req.get("error_message")
    target_line= req.get("target_line")
    custom_fix = req.get("custom_fix")

    # فرض وضع الاقتراح — الطلب لا يستطيع تفعيل الكتابة على الملفات
    healing_agent.mode = AgentExecutionMode.SUGGEST_MODE

    patch_res = healing_agent.heal_file(
        file_path=file_path,
        error_message=error_msg,
        target_line=target_line,
        custom_fix_snippet=custom_fix,
    )

    return {
        "file_path":           patch_res.file_path,
        "status":              patch_res.status.value,
        "execution_mode":      patch_res.execution_mode.value,
        "diff":                patch_res.diff,
        "verification_passed": patch_res.verification_passed,
        "verification_log":    patch_res.verification_log,
        "backup_path":         patch_res.backup_path,
        "duration_ms":         patch_res.duration_ms,
    }


@app.get("/api/healing/history", dependencies=[Depends(require_healing_token)])
def healing_history():
    """سجل الرقع البرمجية وعمليات الإصلاح السابقة"""
    if not healing_agent:
        return {"history": []}
    return {
        "history": [
            {
                "file_path":           p.file_path,
                "status":              p.status.value,
                "verification_passed": p.verification_passed,
                "duration_ms":         p.duration_ms,
                "backup_path":         p.backup_path,
            }
            for p in healing_agent.history_patches
        ]
    }




# ── تشغيل الخادم ───────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"[SERVER] Starting on http://{SERVER['host']}:{SERVER['port']}")
    uvicorn.run(
        "main:app",
        host=SERVER["host"],
        port=SERVER["port"],
        reload=SERVER["reload"],
        log_level="info",
    )
