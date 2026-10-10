"""
============================================================
indicators.py — حساب المؤشرات الفنية الكاملة
============================================================
9 مؤشرات لمجلس التصويت + ATR للإدارة
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from dataclasses import dataclass
from config import INDICATORS as IND_CFG


@dataclass
class IndicatorValues:
    """نتيجة حساب جميع المؤشرات"""
    # السعر
    close:   float = 0.0
    high:    float = 0.0
    low:     float = 0.0
    open:    float = 0.0

    # المؤشرات
    ema:        float = 0.0
    rsi:        float = 50.0
    macd:       float = 0.0
    macd_signal:float = 0.0
    macd_hist:  float = 0.0
    adx:        float = 0.0
    di_plus:    float = 0.0
    di_minus:   float = 0.0
    bb_upper:   float = 0.0
    bb_middle:  float = 0.0
    bb_lower:   float = 0.0
    atr:        float = 0.0
    atr_daily:  float = 0.0
    momentum:   float = 100.0
    stoch_k:    float = 50.0
    stoch_d:    float = 50.0

    # Heiken Ashi
    ha_open:    float = 0.0
    ha_close:   float = 0.0
    ha_high:    float = 0.0
    ha_low:     float = 0.0
    ha_bullish: bool  = False
    ha_bearish: bool  = False

    # Ichimoku
    tenkan:     float = 0.0
    kijun:      float = 0.0
    senkou_a:   float = 0.0
    senkou_b:   float = 0.0

    # SMC (Smart Money Concepts)
    smc_bullish_ob:  bool = False
    smc_bearish_ob:  bool = False
    smc_bullish_fvg: bool = False
    smc_bearish_fvg: bool = False

    # معلومات إضافية
    ema_angle:  float = 0.0
    spread:     float = 0.0

    def is_valid(self) -> bool:
        return self.close > 0 and self.atr > 0


class TechnicalIndicators:
    """محرك حساب المؤشرات الفنية الكاملة"""

    def __init__(self):
        self.cfg = IND_CFG

    def calculate(self, df: pd.DataFrame, spread: float = 0.0) -> IndicatorValues:
        """حساب جميع المؤشرات من بيانات OHLCV"""
        if df is None or len(df) < 60:
            return IndicatorValues()

        iv = IndicatorValues()
        iv.spread = spread

        try:
            close = df["close"]
            high  = df["high"]
            low   = df["low"]
            op    = df["open"]

            # آخر سعر
            iv.close = float(close.iloc[-1])
            iv.high  = float(high.iloc[-1])
            iv.low   = float(low.iloc[-1])
            iv.open  = float(op.iloc[-1])

            # ── 1. EMA ──────────────────────────────────────────────
            ema = close.ewm(span=self.cfg["ema_period"], adjust=False).mean()
            iv.ema = float(ema.iloc[-1])
            # زاوية EMA (التغيير على 5 شموع)
            if len(ema) >= 6:
                angle_val = (float(ema.iloc[-1]) - float(ema.iloc[-6])) / (5 * max(iv.close * 0.0001, 1e-10))
                iv.ema_angle = float(np.degrees(np.arctan(angle_val)))

            # ── 2. RSI ──────────────────────────────────────────────
            iv.rsi = float(self._calc_rsi(close, self.cfg["rsi_period"]).iloc[-1])

            # ── 3. MACD ─────────────────────────────────────────────
            ema_fast = close.ewm(span=self.cfg["macd_fast"],   adjust=False).mean()
            ema_slow = close.ewm(span=self.cfg["macd_slow"],   adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.cfg["macd_signal"], adjust=False).mean()
            iv.macd        = float(macd_line.iloc[-1])
            iv.macd_signal = float(signal_line.iloc[-1])
            iv.macd_hist   = iv.macd - iv.macd_signal

            # ── 4. Bollinger Bands ───────────────────────────────────
            bb_mid = close.rolling(self.cfg["bb_period"]).mean()
            bb_std = close.rolling(self.cfg["bb_period"]).std()
            iv.bb_upper  = float((bb_mid + self.cfg["bb_dev"] * bb_std).iloc[-1])
            iv.bb_middle = float(bb_mid.iloc[-1])
            iv.bb_lower  = float((bb_mid - self.cfg["bb_dev"] * bb_std).iloc[-1])

            # ── 5. ATR ──────────────────────────────────────────────
            iv.atr       = float(self._calc_atr(high, low, close, self.cfg["atr_period"]).iloc[-1])
            iv.atr_daily = iv.atr  # يُحدَّث بـ ATR اليومي لاحقاً

            # ── 6. ADX + DI ─────────────────────────────────────────
            adx_vals = self._calc_adx(high, low, close, self.cfg["adx_period"])
            iv.adx      = float(adx_vals["adx"].iloc[-1])
            iv.di_plus  = float(adx_vals["di+"].iloc[-1])
            iv.di_minus = float(adx_vals["di-"].iloc[-1])

            # ── 7. Momentum ─────────────────────────────────────────
            mom_period = self.cfg["momentum_period"]
            if len(close) > mom_period:
                iv.momentum = float((close / close.shift(mom_period) * 100).iloc[-1])

            # ── 8. Stochastic ───────────────────────────────────────
            stoch = self._calc_stochastic(high, low, close, self.cfg["stoch_k"], self.cfg["stoch_d"])
            iv.stoch_k = float(stoch["k"].iloc[-1])
            iv.stoch_d = float(stoch["d"].iloc[-1])

            # ── 9. Heiken Ashi ───────────────────────────────────────
            ha = self._calc_heiken_ashi(op, high, low, close)
            iv.ha_open    = float(ha["open"].iloc[-1])
            iv.ha_close   = float(ha["close"].iloc[-1])
            iv.ha_high    = float(ha["high"].iloc[-1])
            iv.ha_low     = float(ha["low"].iloc[-1])
            iv.ha_bullish = iv.ha_close > iv.ha_open
            iv.ha_bearish = iv.ha_close < iv.ha_open

            # ── 10. Ichimoku ─────────────────────────────────────────
            ichi = self._calc_ichimoku(high, low)
            iv.tenkan   = float(ichi["tenkan"].iloc[-1])
            iv.kijun    = float(ichi["kijun"].iloc[-1])
            iv.senkou_a = float(ichi["senkou_a"].iloc[-1]) if not pd.isna(ichi["senkou_a"].iloc[-1]) else iv.close
            iv.senkou_b = float(ichi["senkou_b"].iloc[-1]) if not pd.isna(ichi["senkou_b"].iloc[-1]) else iv.close

            # ── 11. SMC (Smart Money Concepts) ────────────────────────
            smc = self._calc_smc(df)
            iv.smc_bullish_ob  = smc["bullish_ob"]
            iv.smc_bearish_ob  = smc["bearish_ob"]
            iv.smc_bullish_fvg = smc["bullish_fvg"]
            iv.smc_bearish_fvg = smc["bearish_fvg"]

        except Exception as e:
            from loguru import logger
            logger.error(f"❌ خطأ في حساب المؤشرات: {e}")

        return iv

    # ────────────────────────────────────────────────────────────────
    # دوال مساعدة
    # ────────────────────────────────────────────────────────────────
    def _calc_rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs    = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _calc_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        prev_close = close.shift(1)
        tr = pd.DataFrame({
            "hl":  high - low,
            "hpc": (high - prev_close).abs(),
            "lpc": (low  - prev_close).abs(),
        }).max(axis=1)
        return tr.rolling(period).mean()

    def _calc_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.DataFrame:
        plus_dm  = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        mask = plus_dm < minus_dm; plus_dm[mask] = 0
        mask = minus_dm <= plus_dm; minus_dm[mask] = 0

        atr = self._calc_atr(high, low, close, period)
        eps = 1e-10
        di_plus  = 100 * plus_dm.rolling(period).mean()  / (atr + eps)
        di_minus = 100 * minus_dm.rolling(period).mean() / (atr + eps)
        dx  = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + eps)
        adx = dx.rolling(period).mean()
        return pd.DataFrame({"adx": adx, "di+": di_plus, "di-": di_minus})

    def _calc_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k: int, d: int) -> pd.DataFrame:
        lowest_low  = low.rolling(k).min()
        highest_high= high.rolling(k).max()
        k_line = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        d_line = k_line.rolling(d).mean()
        return pd.DataFrame({"k": k_line, "d": d_line})

    def _calc_heiken_ashi(self, op, high, low, close) -> pd.DataFrame:
        ha_close = (op + high + low + close) / 4
        ha_open  = pd.Series(index=op.index, dtype=float)
        ha_open.iloc[0] = (float(op.iloc[0]) + float(close.iloc[0])) / 2
        for i in range(1, len(ha_open)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([high, ha_open, ha_close], axis=1).max(axis=1)
        ha_low  = pd.concat([low,  ha_open, ha_close], axis=1).min(axis=1)
        return pd.DataFrame({"open":ha_open,"close":ha_close,"high":ha_high,"low":ha_low})

    def _calc_ichimoku(self, high: pd.Series, low: pd.Series) -> pd.DataFrame:
        t = self.cfg["ichi_tenkan"]
        k = self.cfg["ichi_kijun"]
        s = self.cfg["ichi_senkou"]
        tenkan  = (high.rolling(t).max() + low.rolling(t).min()) / 2
        kijun   = (high.rolling(k).max() + low.rolling(k).min()) / 2
        senkou_a= (tenkan + kijun) / 2
        senkou_b= (high.rolling(s).max() + low.rolling(s).min()) / 2
        return pd.DataFrame({"tenkan":tenkan,"kijun":kijun,"senkou_a":senkou_a,"senkou_b":senkou_b})

    def _calc_smc(self, df: pd.DataFrame) -> dict:
        """كشف Order Blocks و Fair Value Gaps (FVG) من بيانات الشموع"""
        res = {"bullish_ob": False, "bearish_ob": False, "bullish_fvg": False, "bearish_fvg": False}
        if df is None or len(df) < 5:
            return res

        try:
            close = df["close"]
            high  = df["high"]
            low   = df["low"]
            op    = df["open"]

            # 1. FVG Detection (على آخر 3 شموع مكتملة)
            if float(low.iloc[-1]) > float(high.iloc[-3]):
                res["bullish_fvg"] = True
            if float(high.iloc[-1]) < float(low.iloc[-3]):
                res["bearish_fvg"] = True

            # 2. Order Block Detection (على آخر 5 شموع)
            recent_body = (close - op).abs()
            avg_body = float(recent_body.tail(14).mean()) if len(recent_body) >= 14 else float(recent_body.mean())

            # صعود قوي (Bullish OB)
            if (float(close.iloc[-1]) > float(op.iloc[-1])) and ((float(close.iloc[-1]) - float(op.iloc[-1])) > 1.1 * avg_body):
                if float(close.iloc[-2]) < float(op.iloc[-2]):
                    res["bullish_ob"] = True

            # هبوط قوي (Bearish OB)
            if (float(close.iloc[-1]) < float(op.iloc[-1])) and ((float(op.iloc[-1]) - float(close.iloc[-1])) > 1.1 * avg_body):
                if float(close.iloc[-2]) > float(op.iloc[-2]):
                    res["bearish_ob"] = True

        except Exception:
            pass

        return res
