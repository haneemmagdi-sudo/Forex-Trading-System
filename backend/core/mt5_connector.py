"""
============================================================
mt5_connector.py — الاتصال الحقيقي بـ MetaTrader 5
============================================================
يدير الاتصال، قراءة الأسعار، وتنفيذ الصفقات
عند غياب MT5 → يستخدم yfinance (بيانات حقيقية من Yahoo Finance)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("⚠️ MetaTrader5 غير متوفر — سيستخدم yfinance كمصدر بيانات حقيقي")

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("⚠️ yfinance غير متوفر")

import pandas as pd
import numpy as np
from config import MT5, SYMBOLS, MAGIC_NUMBERS, LIVE_TRADING_ENABLED
from core.runtime_resilience import get_runtime_watchdog


# ── خريطة تحويل رموز العملات لـ yfinance ──────────────────────────────
YFINANCE_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X",
    "EURAUD": "EURAUD=X",
    "EURCAD": "EURCAD=X",
    "GBPAUD": "GBPAUD=X",
    "AUDCAD": "AUDCAD=X",
    "NZDJPY": "NZDJPY=X",
    "GBPCAD": "GBPCAD=X",
    "GBPNZD": "GBPNZD=X",
    "NZDCAD": "NZDCAD=X",
    "AUDJPY": "AUDJPY=X",
    "AUDNZD": "AUDNZD=X",
    "CHFJPY": "CHFJPY=X",
    "CADJPY": "CADJPY=X",
}

# كاش بيانات yfinance لتجنب الطلبات المتكررة
_yfinance_cache: Dict[str, dict] = {}
_yfinance_cache_time: Dict[str, float] = {}
_CACHE_TTL = 60  # ثانية

# كاش أسعار Tick
_tick_cache: Dict[str, dict] = {}
_tick_cache_time: Dict[str, float] = {}
_TICK_TTL = 5  # ثانية


class MT5Connector:
    """مدير الاتصال بـ MetaTrader 5 مع دعم yfinance كـ fallback حقيقي"""

    def __init__(self):
        self.connected   = False
        self.account_info = {}
        self._simulation_mode = False  # لا محاكاة — نستخدم yfinance
        self._use_yfinance = False
        self._sim_balance = 10_000.0
        self._sim_equity  = 10_000.0
        logger.info(f"MT5Connector initialized | MT5:{MT5_AVAILABLE} | yfinance:{YFINANCE_AVAILABLE}")

    # ─────────────────────────────────────────────────────────────────
    # الاتصال
    # ─────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        # محاولة الاتصال الحقيقي بـ MT5
        if MT5_AVAILABLE:
            success = self._connect_mt5()
            if success:
                return True
            logger.warning("[MT5] فشل الاتصال — التحول لـ yfinance كمصدر بيانات حقيقي")

        # التحول لـ yfinance (بيانات حقيقية، لكن بدون تنفيذ صفقات)
        if YFINANCE_AVAILABLE:
            self._use_yfinance = True
            self._simulation_mode = False  # ليست محاكاة — بيانات حقيقية
            self.connected = True
            self.account_info = {
                "login":        int(os.getenv("MT5_LOGIN", "0")),
                "server":       os.getenv("MT5_SERVER", "ICMarketsSC-Demo"),
                "balance":      float(os.getenv("STARTING_CAPITAL", "5000")),
                "equity":       float(os.getenv("STARTING_CAPITAL", "5000")),
                "margin":       0,
                "free_margin":  float(os.getenv("STARTING_CAPITAL", "5000")),
                "margin_level": 100,
                "currency":     "USD",
                "leverage":     100,
                "company":      "Raw Trading Ltd",
            }
            logger.success("✅ yfinance MODE — بيانات أسعار حقيقية من Yahoo Finance")
            logger.info("⚠️ ملاحظة: تنفيذ الصفقات يتطلب MT5 متصل")
            return True

        # لا محاكاة — خطأ حقيقي
        logger.error("❌ لا MT5 ولا yfinance — النظام لا يمكنه العمل بشكل صحيح")
        self._simulation_mode = True
        self.connected = False
        return False

    def _connect_mt5(self) -> bool:
        """الاتصال الفعلي بـ MetaTrader 5"""
        path = MT5.get("path", "")
        if path:
            path = path.replace("/", "\\")
            success = mt5.initialize(path=path)
        else:
            success = mt5.initialize()

        if not success:
            logger.error(f"❌ فشل تهيئة MT5: {mt5.last_error()}")
            return False

        login_id = MT5.get("login", 0)
        if login_id and login_id > 0:
            authorized = mt5.login(
                login=login_id,
                password=MT5["password"],
                server=MT5["server"],
                timeout=MT5["timeout"],
            )
            if not authorized:
                logger.error(f"❌ فشل تسجيل الدخول MT5: {mt5.last_error()}")
                mt5.shutdown()
                return False

        info = mt5.account_info()
        if info is None:
            logger.error("❌ فشل قراءة بيانات الحساب")
            return False

        self.connected = True
        self._use_yfinance = False
        self.account_info = {
            "login":        info.login,
            "server":       info.server,
            "balance":      info.balance,
            "equity":       info.equity,
            "margin":       info.margin,
            "free_margin":  info.margin_free,
            "margin_level": info.margin_level,
            "currency":     info.currency,
            "leverage":     info.leverage,
            "company":      info.company,
        }
        logger.success(f"✅ MT5 LIVE متصل | {info.login}@{info.server} | Balance: ${info.balance:,.2f}")
        blocked = self.entry_block_reason()
        if blocked:
            logger.warning(f"🔒 {blocked}")
        return True

    def entry_block_reason(self) -> Optional[str]:
        """
        سبب منع فتح صفقة جديدة، أو None إن كان مسموحاً.

        الحساب غير التجريبي لا تُفتح عليه صفقة إلا مع LIVE_TRADING_ENABLED=true.
        يُقرأ نوع الحساب عند كل أمر لأنه قد يُبدَّل من داخل الطرفية، وتعذّر قراءته منع.
        الإغلاق وتعديل الوقف لا يمرّان من هنا.
        """
        if self._use_yfinance or LIVE_TRADING_ENABLED:
            return None
        info = mt5.account_info() if MT5_AVAILABLE else None
        if info is None:
            return "لا تُفتح صفقات: تعذّر التحقق من نوع حساب MT5 و LIVE_TRADING_ENABLED ليس true."
        if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            return "لا تُفتح صفقات: حساب MT5 ليس تجريبياً و LIVE_TRADING_ENABLED ليس true."
        return None

    def _timed_order_send(self, request: dict):
        """order_send مع قياس زمن التنفيذ وتغذية RuntimeResilienceWatchdog (3 طفرات متتالية تستدعي فحص الاتصال)."""
        t0 = time.perf_counter()
        try:
            return mt5.order_send(request)
        finally:
            get_runtime_watchdog().record_execution_latency((time.perf_counter() - t0) * 1000.0)

    def refresh_connection_state(self) -> None:
        """يحدّث `connected` من حالة الطرفية الفعلية (الراية وحدها لا تتغير عند سقوط الاتصال). MT5 الحي فقط."""
        if not MT5_AVAILABLE or self._use_yfinance:
            return
        try:
            info = mt5.terminal_info()
            self.connected = bool(info is not None and info.connected)
        except Exception:
            self.connected = False

    def reconnect(self) -> bool:
        """إعادة اتصال MT5 الحي فقط. بخلاف connect() لا يتحوّل صامتاً إلى yfinance (ذلك كان سيجعل
        الأوامر الحية تُنفَّذ كورقية دون تنبيه)؛ عند الفشل تبقى الراية False ويحكم قاطع الدائرة."""
        if not MT5_AVAILABLE or self._use_yfinance:
            return False
        self.connected = False
        try:
            mt5.shutdown()
        except Exception:
            pass
        return self._connect_mt5()

    def disconnect(self):
        if MT5_AVAILABLE and not self._use_yfinance:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.connected = False
        logger.info("🔌 MT5 قُطع الاتصال")

    # ─────────────────────────────────────────────────────────────────
    # بيانات الحساب
    # ─────────────────────────────────────────────────────────────────
    def get_account(self) -> Dict[str, Any]:
        if self._use_yfinance:
            return self.account_info

        if self._simulation_mode:
            return self.account_info

        info = mt5.account_info()
        if info is None:
            return self.account_info
        self.account_info.update({
            "balance":      info.balance,
            "equity":       info.equity,
            "margin":       info.margin,
            "free_margin":  info.margin_free,
            "margin_level": info.margin_level,
        })
        return self.account_info

    def get_drawdown(self) -> float:
        acc = self.get_account()
        balance = acc.get("balance", 1)
        equity  = acc.get("equity",  balance)
        if balance <= 0:
            return 0.0
        dd = (balance - equity) / balance * 100
        return max(0.0, round(dd, 2))

    # ─────────────────────────────────────────────────────────────────
    # بيانات السوق — الأسعار الحقيقية
    # ─────────────────────────────────────────────────────────────────
    def get_tick(self, symbol: str) -> Optional[Dict]:
        """جلب السعر الحالي الحقيقي"""
        # MT5 مباشر
        if MT5_AVAILABLE and not self._use_yfinance and self.connected:
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                sym_info = mt5.symbol_info(symbol)
                digits   = sym_info.digits if sym_info else 5
                spread   = MT5Connector.compute_spread_pips(symbol, tick.ask, tick.bid, digits)
                return {"symbol": symbol, "ask": tick.ask, "bid": tick.bid,
                        "spread": spread, "time": tick.time}

        # yfinance — أسعار حقيقية
        if self._use_yfinance and YFINANCE_AVAILABLE:
            return self._get_yfinance_tick(symbol)

        return None

    def _get_yfinance_tick(self, symbol: str) -> Optional[Dict]:
        """جلب السعر الحقيقي من yfinance"""
        now = time.time()
        cached = _tick_cache.get(symbol)
        cached_time = _tick_cache_time.get(symbol, 0)

        if cached and (now - cached_time) < _TICK_TTL:
            return cached

        try:
            yf_symbol = YFINANCE_SYMBOL_MAP.get(symbol)
            if not yf_symbol:
                return None

            ticker = yf.Ticker(yf_symbol)
            # جلب آخر دقيقة من البيانات
            hist = ticker.history(period="1d", interval="1m")
            if hist.empty:
                # محاولة بديلة
                hist = ticker.history(period="5d", interval="5m")

            if hist.empty:
                return None

            last_row = hist.iloc[-1]
            close_price = float(last_row["Close"])

            # حساب السبريد التقريبي
            is_jpy = "JPY" in symbol
            spread_pct = 0.0001 if not is_jpy else 0.01
            ask = round(close_price + spread_pct / 2, 5 if not is_jpy else 3)
            bid = round(close_price - spread_pct / 2, 5 if not is_jpy else 3)
            spread = round(spread_pct / (0.0001 if not is_jpy else 0.01), 1)

            result = {
                "symbol": symbol,
                "ask": ask,
                "bid": bid,
                "spread": spread,
                "time": int(time.time()),
                "source": "yfinance_real",
            }
            _tick_cache[symbol] = result
            _tick_cache_time[symbol] = now
            return result

        except Exception as e:
            logger.warning(f"⚠️ yfinance tick {symbol}: {e}")
            return None

    def get_ohlcv(self, symbol: str, timeframe=None, bars: int = 200) -> Optional[pd.DataFrame]:
        """جلب بيانات OHLCV الحقيقية"""
        # MT5 مباشر
        if MT5_AVAILABLE and not self._use_yfinance and self.connected:
            if timeframe is None:
                timeframe = mt5.TIMEFRAME_H1
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df["time"] = pd.to_datetime(df["time"], unit="s")
                df.set_index("time", inplace=True)
                df.rename(columns={"tick_volume": "volume"}, inplace=True)
                return df[["open", "high", "low", "close", "volume"]]

        # yfinance — بيانات تاريخية حقيقية
        if self._use_yfinance and YFINANCE_AVAILABLE:
            return self._get_yfinance_ohlcv(symbol, bars)

        return None

    def _get_yfinance_ohlcv(self, symbol: str, bars: int) -> Optional[pd.DataFrame]:
        """جلب بيانات OHLCV الحقيقية من yfinance"""
        cache_key = f"{symbol}_{bars}"
        now = time.time()
        cached_time = _yfinance_cache_time.get(cache_key, 0)

        if cache_key in _yfinance_cache and (now - cached_time) < _CACHE_TTL:
            return _yfinance_cache[cache_key].copy()

        try:
            yf_symbol = YFINANCE_SYMBOL_MAP.get(symbol)
            if not yf_symbol:
                logger.warning(f"⚠️ لا يوجد رمز yfinance لـ {symbol}")
                return None

            ticker = yf.Ticker(yf_symbol)

            # تحديد الفترة الزمنية
            if bars <= 60:
                period, interval = "5d", "1h"
            elif bars <= 200:
                period, interval = "30d", "1h"
            else:
                period, interval = "60d", "1h"

            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"⚠️ yfinance: لا بيانات لـ {symbol}")
                return None

            # تنظيف وتحضير البيانات
            df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]

            # إزالة الصفوف الفارغة
            df.dropna(inplace=True)

            # أخذ آخر N شمعة
            df = df.tail(bars)

            # تأكد أن الـ index timezone-aware
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")

            _yfinance_cache[cache_key] = df.copy()
            _yfinance_cache_time[cache_key] = now

            logger.debug(f"✅ yfinance REAL data: {symbol} | {len(df)} bars | "
                         f"آخر سعر: {df['close'].iloc[-1]:.5f}")
            return df

        except Exception as e:
            logger.error(f"❌ yfinance OHLCV {symbol}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # الصفقات المفتوحة
    # ─────────────────────────────────────────────────────────────────
    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        if not self._use_yfinance and MT5_AVAILABLE and self.connected:
            positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if positions is None:
                return []

            result = []
            for pos in positions:
                result.append({
                    "ticket":       pos.ticket,
                    "symbol":       pos.symbol,
                    "type":         "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume":       pos.volume,
                    "open_price":   pos.price_open,
                    "current_price":pos.price_current,
                    "sl":           pos.sl,
                    "tp":           pos.tp,
                    "profit":       pos.profit,
                    "swap":         pos.swap,
                    "comment":      pos.comment,
                    "magic":        pos.magic,
                    "open_time":    datetime.fromtimestamp(pos.time, tz=timezone.utc).isoformat(),
                })
            return result
        else:
            # Fallback/Paper mode: retrieve open trades from SQLite and simulate real-time profit
            try:
                from models.database import SessionLocal, Trade, TradeStatus
                db = SessionLocal()
                q = db.query(Trade).filter(Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL]))
                if symbol:
                    q = q.filter(Trade.symbol == symbol)
                open_trades = q.all()
                
                result = []
                for t in open_trades:
                    # Fetch live tick price
                    tick = self.get_tick(t.symbol)
                    curr_price = t.entry_price
                    if tick:
                        curr_price = tick["ask"] if t.type == "BUY" else tick["bid"]
                    
                    # Calculate estimated profit (P0 fix: unified pip_size + removed erroneous 10x multiplier)
                    pip_size = self.get_pip_size(t.symbol)
                    pip_value = self.get_pip_value(t.symbol)
                    t_dir = t.type.value if hasattr(t.type, "value") else str(t.type)
                    pips = (curr_price - t.entry_price) / pip_size if t_dir == "BUY" else (t.entry_price - curr_price) / pip_size
                    profit = pips * pip_value * t.lot_size
                    
                    result.append({
                        "ticket":       t.ticket,
                        "symbol":       t.symbol,
                        "type":         t.type.value if t.type else "BUY",
                        "volume":       t.lot_size,
                        "open_price":   t.entry_price,
                        "current_price":curr_price,
                        "sl":           t.sl_price or 0.0,
                        "tp":           t.tp_price or 0.0,
                        "profit":       profit,
                        "swap":         0.0,
                        "comment":      t.comment or "PAPER",
                        "magic":        MAGIC_NUMBERS.get("live_engine", 112345),
                        "open_time":    t.opened_at.isoformat() if t.opened_at else datetime.utcnow().isoformat(),
                    })
                db.close()
                return result
            except Exception as e:
                logger.error(f"Error getting open positions in fallback: {e}")
                return []

    # ─────────────────────────────────────────────────────────────────
    # تنفيذ الصفقات (MT5 فقط)
    # ─────────────────────────────────────────────────────────────────
    def open_trade(self, symbol: str, direction: str, lot: float,
                   sl: float, tp: float, comment: str = "AI_Agent") -> Dict:
        """فتح صفقة حقيقية — يتطلب MT5 متصل"""
        if self._use_yfinance:
            tick = self._get_yfinance_tick(symbol)
            price = tick["ask"] if direction == "BUY" else tick["bid"] if tick else 0
            logger.warning(f"⚠️ yfinance mode — الصفقات تُحاكى محلياً (MT5 غير متصل)")
            logger.warning(f"   لتنفيذ صفقات حقيقية: افتح MetaTrader 5 وسجّل الدخول")
            import random
            ticket = random.randint(1000000, 9999999)
            return {"success": True, "ticket": ticket, "price": price,
                    "note": "PAPER_TRADE - MT5 required for real execution"}

        if not MT5_AVAILABLE or not self.connected:
            return {"success": False, "error": "MT5 غير متصل"}

        blocked = self.entry_block_reason()
        if blocked:
            logger.warning(f"🔒 {direction} {symbol} | {blocked}")
            return {"success": False, "error": blocked}

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return {"success": False, "error": f"رمز {symbol} غير موجود"}

        if not sym_info.visible:
            mt5.symbol_select(symbol, True)

        tick    = mt5.symbol_info_tick(symbol)
        price   = tick.ask if direction == "BUY" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        filling_mode = sym_info.filling_mode
        if filling_mode & 1:
            filling = mt5.ORDER_FILLING_FOK
        elif filling_mode & 2:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot,
            "type":         order_type,
            "price":        price,
            "sl":           round(sl, sym_info.digits),
            "tp":           round(tp, sym_info.digits),
            "deviation":    10,
            "magic":        MAGIC_NUMBERS.get("live_engine", 112345),
            "comment":      comment,
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        result = self._timed_order_send(request)
        if result is None:
            err = mt5.last_error()
            logger.error(f"❌ فشل إرسال الأمر: {err}")
            return {"success": False, "error": str(err)}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"❌ أمر مرفوض: {result.retcode} — {result.comment}")
            return {"success": False, "error": f"{result.retcode}: {result.comment}"}

        logger.success(f"✅ صفقة LIVE مفتوحة | {direction} {symbol} | Ticket:{result.order} | Price:{result.price}")
        return {"success": True, "ticket": result.order, "price": result.price}

    def modify_sl(self, ticket: int, new_sl: float) -> bool:
        if self._use_yfinance or not MT5_AVAILABLE:
            logger.info(f"[PAPER] تعديل SL | Ticket:{ticket} → {new_sl:.5f}")
            return True
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "ticket": ticket,
            "sl":     new_sl,
            "tp":     pos.tp,
        }
        result = self._timed_order_send(request)
        success = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.info(f"✅ SL معدّل | Ticket:{ticket} → {new_sl:.5f}")
        return success

    def partial_close(self, ticket: int, close_percent: float) -> bool:
        if self._use_yfinance or not MT5_AVAILABLE:
            logger.info(f"[PAPER] إغلاق جزئي {close_percent*100:.0f}% | Ticket:{ticket}")
            return True
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        # P5: كان max(0.01, ...) يُغلق الصفقة كلها (لوت 0.01 × 30% → 0.01) باسم «جزئي».
        info = mt5.symbol_info(pos.symbol)
        v_min = float(getattr(info, "volume_min", 0.01) or 0.01) if info else 0.01
        v_step = float(getattr(info, "volume_step", 0.01) or 0.01) if info else 0.01
        close_volume = MT5Connector.compute_partial_volume(pos.volume, close_percent, v_min, v_step)
        if close_volume is None:
            logger.info(f"⏭️ إغلاق جزئي مرفوض (الحجم {pos.volume} لا يُقسَّم) | Ticket:{ticket}")
            return False
        tick  = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       close_volume,
            "type":         order_type,
            "position":     ticket,
            "price":        price,
            "deviation":    10,
            "magic":        MAGIC_NUMBERS.get("live_engine", 112345),
            "comment":      "AI_PartialClose",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = self._timed_order_send(request)
        success = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.info(f"✅ إغلاق جزئي {close_percent*100:.0f}% | Ticket:{ticket}")
        return success

    def close_position(self, ticket: int, comment: str = "AI_Close") -> bool:
        """
        إغلاق صفقة مفتوحة.
        IMPROVEMENT_PLAN §0: إزالة الحظر المصطنع على إغلاق الصفقات الخاسرة.
        كان الكود يرفض إغلاق أي صفقة خاسرة مما كان يمنع وقف الخسارة وإيقاف الطوارئ من العمل.
        """
        if self._use_yfinance or not MT5_AVAILABLE:
            from models.database import SessionLocal, Trade, TradeStatus
            db = SessionLocal()
            try:
                trade = db.query(Trade).filter(Trade.ticket == ticket).first()
                if trade:
                    trade.status = TradeStatus.CLOSED
                    trade.closed_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.error(f"Error updating closed trade in DB: {e}")
            finally:
                db.close()
            logger.info(f"[PAPER] إغلاق صفقة #{ticket} ({comment})")
            return True

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        tick  = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return False
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         order_type,
            "position":     ticket,
            "price":        price,
            "deviation":    10,
            "magic":        MAGIC_NUMBERS.get("live_engine", 112345),
            "comment":      comment,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = self._timed_order_send(request)
        success = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.success(f"✅ صفقة مغلقة | Ticket:{ticket} ({comment})")
        else:
            err = result.comment if result else mt5.last_error()
            logger.error(f"❌ فشل إغلاق صفقة #{ticket}: {err}")
        return success

    def close_all_positions(
        self,
        symbol: Optional[str] = None,
        reason: str = "AI_Emergency",
        magic_numbers: Optional[set] = None,
    ):
        positions = self.get_open_positions(symbol)
        if magic_numbers is not None:
            allowed = set(magic_numbers)
            positions = [p for p in positions if p.get("magic") in allowed]
        for pos in positions:
            self.close_position(pos["ticket"], comment=reason)
        if positions:
            scope = f" (Magic={sorted(allowed)})" if magic_numbers is not None else ""
            logger.warning(f"🆘 إغلاق {len(positions)} صفقة{scope} | السبب: {reason}")

    def get_pip_value(self, symbol: str) -> float:
        """
        قيمة البيب لكل لوت قياسي (100,000 وحدة) بالدولار الأمريكي.

        IMPROVEMENT_PLAN §0: قيمة النقطة ثابتة 0.00001 لكل الرموز كانت خطأً جوهرياً.
        P3: قيمة البيب تُحسب دائماً لحجم البيب الموحّد get_pip_size (الذهب 0.1، الين/الفضة 0.01،
        الباقي 0.0001) وليس لـ point الخام: pip_value = tick_value × pip_size / tick_size.
        (قبل P3 كانت تُحسب للذهب (خانتان) على 0.01 فتخرج ≈ 1$ بدل 10$ مع أن حجم البيب 0.1).
        """
        # يفضَّل استخدام MT5 الحي للحصول على القيمة الدقيقة
        if not self._use_yfinance and MT5_AVAILABLE and self.connected:
            sym_info = mt5.symbol_info(symbol)
            if sym_info is not None:
                live = MT5Connector.compute_pip_value(
                    symbol, sym_info.trade_tick_value, sym_info.trade_tick_size, sym_info.digits
                )
                if live is not None:
                    return live

        # Fallback محدَّث يدوياً لأهم الرموز (قيم تقريبية لحساب الربح/الخسارة)
        # قيم لكل لوت قياسي (100,000 وحدة) بالدولار
        pip_values = {
            "EURUSD": 10.0,   # 1 pip = $10 / standard lot
            "GBPUSD": 10.0,
            "AUDUSD": 10.0,
            "NZDUSD": 10.0,
            "USDCAD":  7.7,   # تقريبي (يعتمد على سعر USDCAD)
            "USDCHF":  11.2,  # تقريبي
            "USDJPY":  6.7,   # تقريبي (يعتمد على سعر USDJPY ÷ 100)
            "EURJPY":  6.7,
            "GBPJPY":  6.7,
            "EURGBP":  12.8,  # تقريبي
            "XAUUSD":  10.0,  # GOLD (100 oz lot): 1 pip (0.10 price move) = $10 per 1.0 standard lot
            "XAGUSD":  50.0,  # SILVER
        }
        return pip_values.get(symbol, 10.0)

    @staticmethod
    def compute_pip_value(symbol: str, tick_value: float, tick_size: float,
                          digits: Optional[int] = None) -> Optional[float]:
        """P3: قيمة البيب لكل لوت = tick_value × (pip_size / tick_size). None عند بيانات غير صالحة (لا قيمة مُختلقة)."""
        try:
            tv, ts = float(tick_value), float(tick_size)
        except (TypeError, ValueError):
            return None
        if not (tv > 0 and ts > 0):
            return None
        return tv * (MT5Connector.get_pip_size(symbol, digits) / ts)

    @staticmethod
    def compute_partial_volume(volume: float, percent: float, vol_min: float = 0.01,
                               vol_step: float = 0.01) -> Optional[float]:
        """
        P5: حجم الإغلاق الجزئي الصالح أو None. يُقرَّب لأسفل لخطوة الحجم، ويُشترط أن يكون المُغلَق
        ≥ vol_min وأن يبقى ≥ vol_min؛ وإلا فالصفقة لا تُقسَّم (لا نُغلقها كلها بالخطأ).
        """
        try:
            vol, pct = float(volume), float(percent)
            vmin, vstep = float(vol_min), float(vol_step)
        except (TypeError, ValueError):
            return None
        if not (vol > 0 and 0 < pct < 1 and vmin > 0 and vstep > 0):
            return None
        eps = 1e-9
        close_vol = int(vol * pct / vstep + eps) * vstep
        close_vol = round(close_vol, 8)
        if close_vol + eps < vmin or (vol - close_vol) + eps < vmin:
            return None
        return round(close_vol, 2)

    @staticmethod
    def compute_spread_pips(symbol: str, ask: float, bid: float, digits: Optional[int] = None) -> float:
        """P3: السبريد بوحدة البيب الموحّدة (نفس وحدة symbol_spread_limits وatr_pips): (ask − bid) / pip_size."""
        return round((float(ask) - float(bid)) / MT5Connector.get_pip_size(symbol, digits), 1)

    @staticmethod
    def get_pip_size(symbol: str, digits: Optional[int] = None) -> float:
        """حجم البيب الموحّد لكل رمز (P0 fix: يدعم XAUUSD وXAGUSD وJPY وأزواج 5 خانات)."""
        sym = (symbol or "").upper()
        if "XAU" in sym:
            return 0.1
        if "XAG" in sym or "JPY" in sym:
            return 0.01
        if digits is not None:
            if digits == 2:
                return 0.1
            if digits == 3:
                return 0.01
        return 0.0001

    def get_digits(self, symbol: str) -> int:
        if self._use_yfinance or not MT5_AVAILABLE:
            sym = (symbol or "").upper()
            if "XAU" in sym or "XAG" in sym:
                return 2
            return 3 if "JPY" in sym else 5
        sym_info = mt5.symbol_info(symbol)
        return sym_info.digits if sym_info else 5

    def get_history(self, from_date: datetime, to_date: datetime,
                    symbol: Optional[str] = None) -> List[Dict]:
        if self._use_yfinance or not MT5_AVAILABLE:
            return []
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        result = []
        for deal in deals:
            if symbol and deal.symbol != symbol:
                continue
            if deal.entry == mt5.DEAL_ENTRY_OUT:
                result.append({
                    "ticket": deal.ticket,
                    "symbol": deal.symbol,
                    "type":   "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL",
                    "volume": deal.volume,
                    "price":  deal.price,
                    "profit": deal.profit,
                    "swap":   deal.swap,
                    "time":   datetime.fromtimestamp(deal.time, tz=timezone.utc).isoformat(),
                })
        return result

    @property
    def data_source(self) -> str:
        """مصدر البيانات الحالي"""
        if MT5_AVAILABLE and not self._use_yfinance:
            return "MT5_LIVE"
        elif self._use_yfinance:
            return "YFINANCE_REAL"
        else:
            return "SIMULATION"
