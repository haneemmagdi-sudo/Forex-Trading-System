"""
============================================================
voting_engine.py — مجلس التصويت (9 مؤشرات)
============================================================
كل مؤشر يُصوّت BUY / SELL / NEUTRAL
النتيجة: BUY | SELL | NO_TRADE
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
from dataclasses import dataclass, field
from typing import Dict
from core.indicators import IndicatorValues
from core.fsm_engine import FSMResult, Regime
import config as _cfg
from config import INDICATORS as IND_CFG, STRATEGY
ENTRY_UPGRADES_2026 = getattr(_cfg, 'ENTRY_UPGRADES_2026', {})


class VoteValue:
    BUY     = "BUY"
    SELL    = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class MemberVote:
    name:      str
    vote:      str    # BUY | SELL | NEUTRAL
    weight:    float
    weighted_buy:  float = 0.0
    weighted_sell: float = 0.0
    reason:    str = ""


@dataclass
class VotingResult:
    direction:    str    # BUY | SELL | NO_TRADE | WEAK_BUY | WEAK_SELL
    buy_score:    float
    sell_score:   float
    total_weight: float
    confidence:   float  # 0-100%
    votes:           Dict[str, MemberVote] = field(default_factory=dict)
    regime:          str = ""
    signal_strong:   bool = False   # إشارة قوية تستوجب الفتح
    pillar_scores:   Dict[str, Dict[str, float]] = field(default_factory=dict)
    pillars_agreeing:int = 0        # عدد المحاور المتعامدة المتوافقة (حد أدنى 2 للإشارة القوية)
    opposing_pillars:int = 0        # عدد المحاور المتعامدة المعاكسة بقوة (Conflict Guard)
    pillar_entropy:  float = 0.0    # إنتروبيا التشتت بين المحاور [0.0=إجماع تام, 1.0=تضارب كامل]

    def to_dict(self):
        return {
            "direction":        self.direction,
            "buy_score":        round(self.buy_score, 3),
            "sell_score":       round(self.sell_score, 3),
            "total_weight":     round(self.total_weight, 3),
            "confidence":       round(self.confidence, 1),
            "signal_strong":    self.signal_strong,
            "regime":           self.regime,
            "pillars_agreeing": self.pillars_agreeing,
            "opposing_pillars": self.opposing_pillars,
            "pillar_entropy":   round(self.pillar_entropy, 4),
            "pillar_scores":    self.pillar_scores,
            "votes": {
                k: {
                    "vote":   v.vote,
                    "weight": round(v.weight, 2),
                    "reason": v.reason,
                }
                for k, v in self.votes.items()
            },
        }


class VotingEngine:
    """
    محرك التصويت — يجمع 9 أصوات من المؤشرات
    بأوزان تتغير تلقائياً حسب حالة FSM
    """

    def __init__(self):
        # أوزان المؤشرات الأساسية (تُضرب في معامل FSM)
        self.base_weights = {
            "ema":      1.0,
            "ha":       2.0,
            "macd":     0.6,
            "rsi":      0.8,
            "adx":      0.7,
            "ichi":     0.8,
            "smc":      1.0,
            "momentum": 0.5,
            "st":       1.0,
        }

        # عتبة التصويت من الإعدادات
        self.min_score = STRATEGY.get("min_vote_score", 3.5)

        # أوزان محدَّثة من التعلم الآلي (تُحدَّث بواسطة Learning Agent)
        self.learned_multipliers: Dict[str, float] = {}

    def vote(self, iv: IndicatorValues, fsm: FSMResult) -> VotingResult:
        """حساب تصويت مجلس الـ 9 مؤشرات"""
        regime_weights = fsm.vote_weights

        votes: Dict[str, MemberVote] = {}
        buy_score  = 0.0
        sell_score = 0.0
        total_weight = 0.0

        # ── 1. EMA Trend ─────────────────────────────────────────────
        ema_w = self.base_weights["ema"] * regime_weights.get("ema", 1.0)
        ema_w *= self.learned_multipliers.get("ema", 1.0)
        if iv.close > iv.ema and iv.ema_angle > 2:
            ema_vote, ema_reason = VoteValue.BUY,  f"السعر فوق EMA ({iv.ema:.5f}) ↑ زاوية:{iv.ema_angle:.1f}°"
        elif iv.close < iv.ema and iv.ema_angle < -2:
            ema_vote, ema_reason = VoteValue.SELL, f"السعر دون EMA ({iv.ema:.5f}) ↓ زاوية:{iv.ema_angle:.1f}°"
        else:
            ema_vote, ema_reason = VoteValue.NEUTRAL, "السعر قريب من EMA"
        votes["ema"] = self._make_vote("EMA Trend", ema_vote, ema_w, ema_reason)

        # ── 2. Heiken Ashi ───────────────────────────────────────────
        ha_w = self.base_weights["ha"] * regime_weights.get("ha", 1.0)
        ha_w *= self.learned_multipliers.get("ha", 1.0)
        if iv.ha_bullish and iv.ha_low == min(iv.ha_open, iv.ha_close):
            ha_vote, ha_reason = VoteValue.BUY,  "شمعة HA صاعدة بدون ذيل سفلي"
        elif iv.ha_bearish and iv.ha_high == max(iv.ha_open, iv.ha_close):
            ha_vote, ha_reason = VoteValue.SELL, "شمعة HA هابطة بدون ذيل علوي"
        elif iv.ha_bullish:
            ha_vote, ha_reason = VoteValue.BUY,  "شمعة HA صاعدة"
        elif iv.ha_bearish:
            ha_vote, ha_reason = VoteValue.SELL, "شمعة HA هابطة"
        else:
            ha_vote, ha_reason = VoteValue.NEUTRAL, "شمعة HA محايدة"
        votes["ha"] = self._make_vote("Heiken Ashi", ha_vote, ha_w, ha_reason)

        # ── 3. MACD ──────────────────────────────────────────────────
        macd_w = self.base_weights["macd"] * regime_weights.get("macd", 1.0)
        macd_w *= self.learned_multipliers.get("macd", 1.0)
        if iv.macd > iv.macd_signal and iv.macd_hist > 0:
            macd_vote, macd_reason = VoteValue.BUY,  f"MACD فوق الـ Signal | Hist:{iv.macd_hist:.6f}"
        elif iv.macd < iv.macd_signal and iv.macd_hist < 0:
            macd_vote, macd_reason = VoteValue.SELL, f"MACD دون الـ Signal | Hist:{iv.macd_hist:.6f}"
        else:
            macd_vote, macd_reason = VoteValue.NEUTRAL, "MACD غير حاسم"
        votes["macd"] = self._make_vote("MACD", macd_vote, macd_w, macd_reason)

        # ── 4. RSI ───────────────────────────────────────────────────
        rsi_w = self.base_weights["rsi"] * regime_weights.get("rsi", 1.0)
        rsi_w *= self.learned_multipliers.get("rsi", 1.0)
        rsi_ob = IND_CFG["rsi_overbought"]
        rsi_os = IND_CFG["rsi_oversold"]
        if iv.rsi < rsi_os:
            rsi_vote, rsi_reason = VoteValue.BUY,  f"RSI={iv.rsi:.1f} ذروة البيع < {rsi_os}"
        elif iv.rsi > rsi_ob:
            rsi_vote, rsi_reason = VoteValue.SELL, f"RSI={iv.rsi:.1f} ذروة الشراء > {rsi_ob}"
        elif 45 <= iv.rsi <= 55:
            rsi_vote, rsi_reason = VoteValue.NEUTRAL, f"RSI={iv.rsi:.1f} محايد"
        elif iv.rsi > 55:
            rsi_vote, rsi_reason = VoteValue.BUY,  f"RSI={iv.rsi:.1f} مرتفع > 55"
        else:
            rsi_vote, rsi_reason = VoteValue.SELL, f"RSI={iv.rsi:.1f} منخفض < 45"
        votes["rsi"] = self._make_vote("RSI", rsi_vote, rsi_w, rsi_reason)

        # ── 5. ADX + DI ──────────────────────────────────────────────
        adx_w = self.base_weights["adx"] * regime_weights.get("adx", 1.0)
        adx_w *= self.learned_multipliers.get("adx", 1.0)
        if iv.adx >= IND_CFG["adx_threshold"] and iv.di_plus > iv.di_minus:
            adx_vote, adx_reason = VoteValue.BUY,  f"ADX={iv.adx:.1f} | DI+{iv.di_plus:.1f} > DI-{iv.di_minus:.1f}"
        elif iv.adx >= IND_CFG["adx_threshold"] and iv.di_minus > iv.di_plus:
            adx_vote, adx_reason = VoteValue.SELL, f"ADX={iv.adx:.1f} | DI-{iv.di_minus:.1f} > DI+{iv.di_plus:.1f}"
        else:
            adx_vote, adx_reason = VoteValue.NEUTRAL, f"ADX={iv.adx:.1f} ضعيف < {IND_CFG['adx_threshold']}"
        votes["adx"] = self._make_vote("ADX+DI", adx_vote, adx_w, adx_reason)

        # ── 6. Ichimoku ───────────────────────────────────────────────
        ichi_w = self.base_weights["ichi"] * regime_weights.get("ichi", 1.0)
        ichi_w *= self.learned_multipliers.get("ichi", 1.0)
        cloud_top = max(iv.senkou_a, iv.senkou_b)
        cloud_bot = min(iv.senkou_a, iv.senkou_b)
        if iv.close > cloud_top and iv.tenkan > iv.kijun:
            ichi_vote, ichi_reason = VoteValue.BUY,  "السعر فوق السحابة + Tenkan > Kijun"
        elif iv.close < cloud_bot and iv.tenkan < iv.kijun:
            ichi_vote, ichi_reason = VoteValue.SELL, "السعر دون السحابة + Tenkan < Kijun"
        else:
            ichi_vote, ichi_reason = VoteValue.NEUTRAL, "السعر داخل السحابة"
        votes["ichi"] = self._make_vote("Ichimoku", ichi_vote, ichi_w, ichi_reason)

        # ── 7. SMC (Smart Money Concepts) ──────────────────────────
        smc_w = self.base_weights["smc"] * regime_weights.get("smc", 1.0)
        smc_w *= self.learned_multipliers.get("smc", 1.0)

        if getattr(iv, 'smc_bullish_ob', False) or getattr(iv, 'smc_bullish_fvg', False):
            confluence = []
            if getattr(iv, 'smc_bullish_ob', False): confluence.append("Bullish OB")
            if getattr(iv, 'smc_bullish_fvg', False): confluence.append("Bullish FVG")
            smc_vote, smc_reason = VoteValue.BUY, f"SMC: رصد {', '.join(confluence)}"
        elif getattr(iv, 'smc_bearish_ob', False) or getattr(iv, 'smc_bearish_fvg', False):
            confluence = []
            if getattr(iv, 'smc_bearish_ob', False): confluence.append("Bearish OB")
            if getattr(iv, 'smc_bearish_fvg', False): confluence.append("Bearish FVG")
            smc_vote, smc_reason = VoteValue.SELL, f"SMC: رصد {', '.join(confluence)}"
        else:
            bb_range = iv.bb_upper - iv.bb_lower
            if bb_range > 0:
                bb_pos = (iv.close - iv.bb_lower) / bb_range
                if bb_pos < 0.2 and iv.rsi < 45:
                    smc_vote, smc_reason = VoteValue.BUY,  f"SMC: دعم قيعان | BB_pos={bb_pos:.2f}"
                elif bb_pos > 0.8 and iv.rsi > 55:
                    smc_vote, smc_reason = VoteValue.SELL, f"SMC: مقاومة قمم | BB_pos={bb_pos:.2f}"
                else:
                    smc_vote, smc_reason = VoteValue.NEUTRAL, f"SMC: منطقة محايدة | BB_pos={bb_pos:.2f}"
            else:
                smc_vote, smc_reason = VoteValue.NEUTRAL, "SMC: محايد"
        votes["smc"] = self._make_vote("SMC", smc_vote, smc_w, smc_reason)

        # ── 8. Momentum ───────────────────────────────────────────────
        mom_w = self.base_weights["momentum"] * regime_weights.get("momentum", 1.0)
        mom_w *= self.learned_multipliers.get("momentum", 1.0)
        if iv.momentum > 102:
            mom_vote, mom_reason = VoteValue.BUY,  f"Momentum={iv.momentum:.1f} > 102"
        elif iv.momentum < 98:
            mom_vote, mom_reason = VoteValue.SELL, f"Momentum={iv.momentum:.1f} < 98"
        else:
            mom_vote, mom_reason = VoteValue.NEUTRAL, f"Momentum={iv.momentum:.1f} محايد"
        votes["momentum"] = self._make_vote("Momentum", mom_vote, mom_w, mom_reason)

        # ── 9. SuperTrend (مبسط عبر ATR + EMA) ──────────────────────
        st_w = self.base_weights["st"] * regime_weights.get("st", 1.0)
        st_w *= self.learned_multipliers.get("st", 1.0)
        st_upper = iv.ema + 2.5 * iv.atr
        st_lower = iv.ema - 2.5 * iv.atr
        if iv.close > iv.ema and iv.close > st_lower + 0.3 * iv.atr:
            st_vote, st_reason = VoteValue.BUY,  f"SuperTrend: Bullish | {iv.close:.5f} > {st_lower:.5f}"
        elif iv.close < iv.ema and iv.close < st_upper - 0.3 * iv.atr:
            st_vote, st_reason = VoteValue.SELL, f"SuperTrend: Bearish | {iv.close:.5f} < {st_upper:.5f}"
        else:
            st_vote, st_reason = VoteValue.NEUTRAL, "SuperTrend: محايد"
        votes["st"] = self._make_vote("SuperTrend", st_vote, st_w, st_reason)

        # ── تجميع النتائج عبر 4 محاور متعامدة بسقوف متكيفة مع نظام FSM (2026 Upgrade v2) ──
        # يمنع تكرار عدّ نفس الاتجاه عبر (EMA + HA + Ichi + SuperTrend) ويعيد توزيع السقوف حسب النظام
        caps_table = ENTRY_UPGRADES_2026.get("regime_pillar_caps", {})
        regime_key = fsm.regime.value if hasattr(fsm.regime, "value") else str(fsm.regime)
        caps = caps_table.get(regime_key, caps_table.get("DEFAULT", {
            "trend": 2.5, "momentum": 2.0, "strength": 1.5, "structure": 1.5,
        }))

        PILLARS = {
            "trend":     (["ema", "ha", "ichi", "st"], float(caps.get("trend", 2.5))),
            "momentum":  (["macd", "rsi", "momentum"], float(caps.get("momentum", 2.0))),
            "strength":  (["adx"],                     float(caps.get("strength", 1.5))),
            "structure": (["smc"],                     float(caps.get("structure", 1.5))),
        }

        pillar_scores: Dict[str, Dict[str, float]] = {}
        buy_pillars_agree  = 0
        sell_pillars_agree = 0
        neutral_pillars    = 0

        for p_name, (members, cap_weight) in PILLARS.items():
            raw_w = sum(votes[m].weight for m in members if m in votes)
            raw_b = sum(votes[m].weighted_buy for m in members if m in votes)
            raw_s = sum(votes[m].weighted_sell for m in members if m in votes)
            # تطبيع مساهمة المحور داخل سقفه cap_weight لمنع تضخيم المؤشرات المترابطة
            if raw_w > 0:
                p_buy  = (raw_b / raw_w) * cap_weight
                p_sell = (raw_s / raw_w) * cap_weight
            else:
                p_buy, p_sell = 0.0, 0.0

            buy_score    += p_buy
            sell_score   += p_sell
            total_weight += cap_weight

            if p_buy > p_sell and p_buy >= cap_weight * 0.4:
                buy_pillars_agree += 1
            elif p_sell > p_buy and p_sell >= cap_weight * 0.4:
                sell_pillars_agree += 1
            else:
                neutral_pillars += 1

            pillar_scores[p_name] = {
                "buy": round(p_buy, 3),
                "sell": round(p_sell, 3),
                "cap": cap_weight,
            }

        # إنتروبيا شانون المطبّعة لتشتت آراء المحاور (Anti-Groupthink / Disagreement Telemetry)
        n_pillars = float(len(PILLARS))
        probs = [c / n_pillars for c in (buy_pillars_agree, sell_pillars_agree, neutral_pillars) if c > 0]
        raw_entropy = -sum(p * math.log(p) for p in probs)
        pillar_entropy = raw_entropy / math.log(3.0) if len(probs) > 1 else 0.0

        raw_confidence = (max(buy_score, sell_score) / total_weight * 100) if total_weight > 0 else 0.0
        conflict_mult = float(ENTRY_UPGRADES_2026.get("conflict_strong_multiplier", 1.55))

        # تحديد الاتجاه النهائي مع شرط توافق محورَين متعامدَين وحارس التعارض (Conflict Guard)
        pillars_agreeing = 0
        opposing_pillars = 0
        if buy_score >= self.min_score and buy_score > sell_score * 1.3:
            direction        = "BUY"
            pillars_agreeing = buy_pillars_agree
            opposing_pillars = sell_pillars_agree
            no_conflict_or_dominant = (opposing_pillars == 0) or (buy_score >= self.min_score * conflict_mult)
            signal_strong    = (buy_score >= self.min_score * 1.3) and (buy_pillars_agree >= 2) and no_conflict_or_dominant
        elif sell_score >= self.min_score and sell_score > buy_score * 1.3:
            direction        = "SELL"
            pillars_agreeing = sell_pillars_agree
            opposing_pillars = buy_pillars_agree
            no_conflict_or_dominant = (opposing_pillars == 0) or (sell_score >= self.min_score * conflict_mult)
            signal_strong    = (sell_score >= self.min_score * 1.3) and (sell_pillars_agree >= 2) and no_conflict_or_dominant
        elif buy_score > sell_score:
            direction, signal_strong = "WEAK_BUY", False
            pillars_agreeing, opposing_pillars = buy_pillars_agree, sell_pillars_agree
        elif sell_score > buy_score:
            direction, signal_strong = "WEAK_SELL", False
            pillars_agreeing, opposing_pillars = sell_pillars_agree, buy_pillars_agree
        else:
            direction, signal_strong, pillars_agreeing, opposing_pillars = "NO_TRADE", False, 0, 0

        # خصم الثقة عند وجود محور متعامد معاكس بقوة (يحدّ من الثقة المفرطة)
        confidence = max(0.0, raw_confidence - (opposing_pillars * 8.0))

        # إلغاء الإشارة إذا الـ Regime غير مسموح
        if not fsm.trade_allowed:
            direction     = "NO_TRADE"
            signal_strong = False

        return VotingResult(
            direction        = direction,
            buy_score        = buy_score,
            sell_score       = sell_score,
            total_weight     = total_weight,
            confidence       = confidence,
            votes            = votes,
            regime           = fsm.regime.value,
            signal_strong    = signal_strong,
            pillar_scores    = pillar_scores,
            pillars_agreeing = pillars_agreeing,
            opposing_pillars = opposing_pillars,
            pillar_entropy   = round(pillar_entropy, 4),
        )

    def _make_vote(self, name: str, vote: str, weight: float, reason: str) -> MemberVote:
        mv = MemberVote(name=name, vote=vote, weight=weight, reason=reason)
        if vote == VoteValue.BUY:
            mv.weighted_buy  = weight
        elif vote == VoteValue.SELL:
            mv.weighted_sell = weight
        return mv

    def update_weights(self, new_multipliers: Dict[str, float]):
        """تحديث الأوزان من Learning Agent (مع تقييد الحدود)"""
        for key, val in new_multipliers.items():
            # الحدود: 0.3 → 3.0 لضمان استقرار التصويت
            self.learned_multipliers[key] = max(0.3, min(3.0, float(val)))
