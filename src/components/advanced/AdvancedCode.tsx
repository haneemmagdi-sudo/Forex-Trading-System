import { useState } from 'react';

// =============================================================
// بيانات كود MQL5 الحقيقي من Blessing_Pro_V42_Elite_Fixed.mq5
// =============================================================

const MQL5_SECTIONS = {
  overview: {
    label: 'نظرة عامة',
    content: `//+------------------------------------------------------------------+
//|        Blessing_Pro_V42_Elite_Fixed.mq5                         |
//| 🦅 V4.2 Elite Fixed: All Bugs Corrected + Major Enhancements    |
//+------------------------------------------------------------------+
// ✅ FIX 1: ProcessTrueSMC — g_LastSMCBar activated
// ✅ FIX 2: SuperTrend buffer logic corrected
// ✅ FIX 3: lockedProfit formula corrected
// ✅ FIX 4: DetectEarlyReversal — Doji over-trigger fixed
// ✅ FIX 5: ManageBasketBE — reset logic fixed
// ✅ FIX 6: IsFirstRun / MaxDD first-tick protection
// 🆕 NEW: Partial Close Ladder (30/50/70%)
// 🆕 NEW: Cascade Protection (3 consecutive losses)
// 🆕 NEW: Volatility-Adjusted Grid Multiplier
// 🆕 NEW: Regime Lock (session direction lock)
// 🆕 NEW: Smart Hedging Mode on DD breach

#property version   "4.20"
#property description "Blessing Pro FSM Elite V4.2"
#include <Trade\\Trade.mqh>
#include <Trade\\PositionInfo.mqh>
#include <Trade\\SymbolInfo.mqh>`
  },
  fsm: {
    label: 'محرك FSM',
    content: `//====================================================================
// 🔥 كاشف بيئة السوق (Enhanced FSM Radar - 4 Rooms)
//====================================================================
enum ENUM_MARKET_REGIME {
    REGIME_LOW_VOL_RANGE,   // الغرفة A: تذبذب بطيء
    REGIME_HIGH_VOL_RANGE,  // الغرفة B: تذبذب سريع
    REGIME_SLOW_TREND,      // الغرفة C: ترند بطيء
    REGIME_STRONG_TREND,    // الغرفة D: ترند قوي
    REGIME_CHAOS            // حالة طوارئ
};

void DetectMarketRegime(double ask, double bid, double close1, double ema0) {
    double currentSpread = (ask - bid) / PipSize;
    double adx           = GetIndVal(h_ADX, 0, 1);
    double atr_current   = GetIndVal(h_ATR_G, 0, 1);
    double atr_daily     = GetIndVal(h_ATR_D1, 0, 1);

    // الفوضى أولاً
    if(currentSpread > MaxSpread || IsADRExhausted() || !IsSessionActive()) {
        CurrentRegime  = REGIME_CHAOS;
        g_MarketRegime = "CHAOS 🔴";
        return;
    }

    // تصنيف 4 غرف
    if(adx < 15.0) {
        if(atr_daily > 0 && atr_current < (atr_daily * 0.4)) {
            CurrentRegime  = REGIME_LOW_VOL_RANGE;
            g_MarketRegime = "LOW VOL 🟡";
        } else {
            CurrentRegime  = REGIME_HIGH_VOL_RANGE;
            g_MarketRegime = "HIGH VOL ⚠️";
        }
    } else {
        if(MathAbs(regimeData.ema_angle) < 15.0) {
            CurrentRegime  = REGIME_SLOW_TREND;
            g_MarketRegime = "SLOW TREND 🔵";
        } else {
            CurrentRegime  = REGIME_STRONG_TREND;
            g_MarketRegime = "STRONG TREND 🚀";
        }
    }
}`
  },
  voting: {
    label: 'نظام التصويت',
    content: `//====================================================================
// 🗳️ نظام التصويت المحسّن V4.2 — 9 مؤشرات بأوزان ديناميكية
//====================================================================
void CalculateVotingScores(double close1, double ema0, bool haUp, bool haDn) {
    g_buyScore  = 0.0;
    g_sellScore = 0.0;

    // 1. EMA (وزن: 1.0-1.6)
    if(close1 > ema0) g_buyScore  += voteWeights.ema_weight;
    else              g_sellScore += voteWeights.ema_weight;

    // 2. Heiken Ashi (وزن: 2.0-2.5) — الأهم
    if(haUp) g_buyScore  += voteWeights.ha_weight;
    else     g_sellScore += voteWeights.ha_weight;

    // 3. MACD (وزن: 0.6-0.9)
    double macd_main   = GetIndVal(h_MACD, 0, 1);
    double macd_signal = GetIndVal(h_MACD, 1, 1);
    if(macd_main > macd_signal) g_buyScore  += voteWeights.macd_weight;
    else                        g_sellScore += voteWeights.macd_weight;

    // 4. Momentum (وزن: 0.5-0.9)
    double mom = GetIndVal(h_Momentum, 0, 1);
    if(mom > 100.0) g_buyScore  += voteWeights.momentum_weight;
    else            g_sellScore += voteWeights.momentum_weight;

    // 5. SuperTrend ✅ FIX 2
    if(Use_Double_Saturation && h_SuperTrend != INVALID_HANDLE) {
        double st_support    = GetIndVal(h_SuperTrend, 0, 1);
        double st_resistance = GetIndVal(h_SuperTrend, 1, 1);
        double price_prev    = iClose(_Symbol, _Period, 1);
        if(st_support != EMPTY_VALUE && price_prev > st_support)
            g_buyScore  += voteWeights.st_weight;
        else if(st_resistance != EMPTY_VALUE && price_prev < st_resistance)
            g_sellScore += voteWeights.st_weight;
    }

    // 6. RSI (وزن: 0.4-1.3)
    double rsi = GetIndVal(h_RSI_Sat, 0, 1);
    if(rsi < RSI_Oversold + 10)       g_buyScore  += voteWeights.rsi_weight * 0.8;
    else if(rsi > RSI_Overbought - 10) g_sellScore += voteWeights.rsi_weight * 0.8;

    // 7. ADX مع DI+/DI- (وزن: 0.3-1.4)
    double adx       = GetIndVal(h_ADX, 0, 1);
    double adx_plus  = GetIndVal(h_ADX, 1, 1);
    double adx_minus = GetIndVal(h_ADX, 2, 1);
    if(adx > 25.0) {
        if(adx_plus > adx_minus)  g_buyScore  += voteWeights.adx_weight;
        else                      g_sellScore += voteWeights.adx_weight;
    }

    // 8. Ichimoku Cloud (وزن: 0.8-1.2)
    double senA = GetIndVal(h_Ichi, 2, 1);
    double senB = GetIndVal(h_Ichi, 3, 1);
    if(senA != EMPTY_VALUE && senB != EMPTY_VALUE) {
        double cloudTop = MathMax(senA, senB);
        double cloudBot = MathMin(senA, senB);
        if(close1 > cloudTop) g_buyScore  += voteWeights.ichi_weight;
        else if(close1 < cloudBot) g_sellScore += voteWeights.ichi_weight;
    }

    // 9. SMC — كتل الأوامر (وزن: 1.0)
    if(Use_True_SMC) {
        double smcDist = SMCDistancePips * PipSize;
        if(lastBullOB_Bot > 0 && ask < (lastBullOB_Bot + smcDist))
            g_buyScore  += voteWeights.smc_weight;
        if(lastBearOB_Top > 0 && bid > (lastBearOB_Top - smcDist))
            g_sellScore += voteWeights.smc_weight;
    }
}`
  },
  grid: {
    label: 'الشبكة الذكية',
    content: `//====================================================================
// 🕸️ الشبكة الذكية — Grid Distance بناءً على ATR + Regime
//====================================================================
double CalculateGridDistance() {
    double atr = GetIndVal(h_ATR_G, 0, 1);
    double baseGrid = GridDistancePips * PipSize;
    double mult = 1.0;

    if(Use_Dynamic_ATR && atr > 0) {
        baseGrid = atr * ATRMultiplier;
    }

    // ضبط حسب البيئة (Regime)
    switch(CurrentRegime) {
        case REGIME_LOW_VOL_RANGE:
            mult = Multiplier_LowVol;    // 1.8 — شبكة كثيفة
            break;
        case REGIME_HIGH_VOL_RANGE:
            mult = Multiplier_HighVol;   // 0.9 — تقليل التكرار
            break;
        case REGIME_SLOW_TREND:
            mult = Multiplier_SlowTrend; // 1.5 — متوازن
            break;
        case REGIME_STRONG_TREND:
            mult = Multiplier_StrongTrend; // 1.2 — مع الترند فقط
            break;
        case REGIME_CHAOS:
            return 0; // إيقاف الشبكة
    }

    return NormalizeDouble(baseGrid * mult, _Digits);
}

//====================================================================
// 🆕 Cascade Protection — وقف بعد N خسائر متتالية
//====================================================================
void CheckCascadeProtection() {
    if(!UseCascadeProtection) return;

    if(g_ConsecutiveLosses >= CascadeMaxLosses) {
        g_CascadeActive      = true;
        g_CascadeCooldownEnd = iTime(_Symbol, _Period, 0) +
                               CascadeCooldownBars * PeriodSeconds(_Period);
        g_ConsecutiveLosses  = 0;
        Print("🛑 Cascade Protection: وقف تداول لـ ", CascadeCooldownBars, " شمعة");
        SendTelegramAlert("🛑 Cascade Stop activated!");
    }
}`
  },
  risk: {
    label: 'إدارة المخاطر',
    content: `//====================================================================
// 🛡️ إدارة المخاطر — V4.2 (DD Mode System)
//====================================================================
enum ENUM_DD_MODE {
    DD_NORMAL,   // وضع طبيعي
    DD_SOFT,     // تراجع بسيط — وضع التعافي
    DD_HEDGE,    // تراجع متوسط — وضع التحوط
    DD_EMERGENCY // تراجع حرج — إيقاف تام
};

void CheckDrawdownProtection() {
    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
    if(balance <= 0) return;
    CurrentDD = (balance - equity) / balance * 100.0;

    // تحديد وضع الحماية
    if(CurrentDD >= MaxDDPercent) {
        g_DDMode = DD_EMERGENCY;
        CloseAllPositions("Emergency DD Reached");
        Print("🆘 إيقاف طوارئ: DD = ", CurrentDD, "%");
    }
    else if(CurrentDD >= HedgeDDPercent && UseSmartHedge) {
        g_DDMode = DD_HEDGE;
        ActivateSmartHedge();
    }
    else if(CurrentDD >= SoftDD_Warning) {
        g_DDMode = DD_SOFT;
        g_softDDActive = true;
    }
    else {
        g_DDMode       = DD_NORMAL;
        g_softDDActive = false;
    }
}

//====================================================================
// 🆕 Partial Close Ladder (30/50/70%)
//====================================================================
void ManagePartialTPLadder(int idx, ulong ticket, double entryPrice, bool isBuy) {
    double currentPrice = isBuy ? m_symbol.Bid() : m_symbol.Ask();
    double profitPips   = isBuy
        ? (currentPrice - entryPrice) / PipSize
        : (entryPrice - currentPrice) / PipSize;

    // Level 1: +10 pips → إغلاق 30%
    if(!g_LadderState[idx].level1_done && profitPips >= PartialTP_L1_Pips) {
        double closeVol = NormalizeDouble(m_position.Volume() * 0.30, LotDecimals);
        if(m_trade.PositionClosePartial(ticket, closeVol))
            g_LadderState[idx].level1_done = true;
        if(MoveToBreakEvenOnL1) MoveSLToBreakEven(ticket, entryPrice, isBuy);
    }
    // Level 2: +20 pips → إغلاق 50%
    else if(g_LadderState[idx].level1_done && !g_LadderState[idx].level2_done
            && profitPips >= PartialTP_L2_Pips) {
        double closeVol = NormalizeDouble(m_position.Volume() * 0.50, LotDecimals);
        if(m_trade.PositionClosePartial(ticket, closeVol))
            g_LadderState[idx].level2_done = true;
    }
    // Level 3: +35 pips → إغلاق 70%
    else if(g_LadderState[idx].level2_done && !g_LadderState[idx].level3_done
            && profitPips >= PartialTP_L3_Pips) {
        double closeVol = NormalizeDouble(m_position.Volume() * 0.70, LotDecimals);
        if(m_trade.PositionClosePartial(ticket, closeVol))
            g_LadderState[idx].level3_done = true;
    }
}`
  },
  smc: {
    label: 'Smart Money (SMC)',
    content: `//====================================================================
// ✅ FIX 1: كاشف SMC — شمعة جديدة فقط (g_LastSMCBar مُفعَّل)
//====================================================================
void ProcessTrueSMC() {
    if(!Use_True_SMC) return;

    // الآن يعمل فعلياً على شمعة جديدة فقط ✅
    datetime currentBar = iTime(_Symbol, _Period, 0);
    if(currentBar == g_LastSMCBar) return;
    g_LastSMCBar = currentBar;

    double fH[], fL[];
    ArrayResize(fH, 100);
    ArrayResize(fL, 100);
    if(!SafeCopyBuffer(h_Fractals, 0, 1, 100, fH)) return;
    if(!SafeCopyBuffer(h_Fractals, 1, 1, 100, fL)) return;

    // البحث عن آخر fractal صاعد وهابط
    int h1=-1, h2=-1, l1=-1, l2=-1;
    int cH=0, cL=0;

    for(int i = 2; i < 100; i++) {
        if(fH[i] != EMPTY_VALUE && fH[i] > 0) {
            cH++;
            if(cH == 1) h1 = i;
            else if(cH == 2) { h2 = i; break; }
        }
    }
    for(int i = 2; i < 100; i++) {
        if(fL[i] != EMPTY_VALUE && fL[i] > 0) {
            cL++;
            if(cL == 1) l1 = i;
            else if(cL == 2) { l2 = i; break; }
        }
    }

    // Bullish Order Block
    if(h1 > 0 && h2 > h1) {
        int count = h2 - h1;
        if(count >= 1) {
            int lowest_bar = iLowest(_Symbol, _Period, MODE_LOW, count, h1);
            if(lowest_bar >= 0) {
                lastBullOB_Bot = iLow(_Symbol, _Period, lowest_bar);
                lastBullOB_Top = lastBullOB_Bot + (SMCDistancePips * PipSize);
            }
        }
    }

    // Bearish Order Block
    if(l1 > 0 && l2 > l1) {
        int count = l2 - l1;
        if(count >= 1) {
            int highest_bar = iHighest(_Symbol, _Period, MODE_HIGH, count, l1);
            if(highest_bar >= 0) {
                lastBearOB_Top = iHigh(_Symbol, _Period, highest_bar);
                lastBearOB_Bot = lastBearOB_Top - (SMCDistancePips * PipSize);
            }
        }
    }

    // إبطال OB عند كسر السعر له
    double close1 = iClose(_Symbol, _Period, 1);
    if(lastBullOB_Bot > 0 && close1 < lastBullOB_Bot)
        { lastBullOB_Top = 0; lastBullOB_Bot = 0; }
    if(lastBearOB_Top > 0 && close1 > lastBearOB_Top)
        { lastBearOB_Top = 0; lastBearOB_Bot = 0; }
}`
  }
};

const FULL_FILE_PREVIEW = `//+------------------------------------------------------------------+
//|        Blessing_Pro_V42_Elite_Fixed.mq5                         |
//| 🦅 V4.2 Elite Fixed: All Bugs Corrected + Major Enhancements    |
//+------------------------------------------------------------------+
// [1884 سطر برمجي - انقر "نسخ الكود الكامل" للحصول على النص الكامل]
//
// ✅ 6 إصلاحات حرجة مؤكدة
// 🆕 5 ميزات جديدة:
//    - Partial Close Ladder (30/50/70%)
//    - Cascade Protection
//    - Volatility-Adjusted Grid Multiplier
//    - Regime Lock (session lock)
//    - Smart Hedging Mode
//
// 📊 9 مؤشرات في مجلس التصويت
// 🔍 4 حالات FSM (LOW_VOL / HIGH_VOL / SLOW_TREND / STRONG_TREND)
// 🛡️ 4 أوضاع حماية (NORMAL / SOFT / HEDGE / EMERGENCY)
//+------------------------------------------------------------------+`;

export default function AdvancedCode() {
  const [activeSection, setActiveSection] = useState<keyof typeof MQL5_SECTIONS>('overview');
  const [copied, setCopied] = useState(false);
  const [showFullInfo, setShowFullInfo] = useState(false);

  const handleCopy = () => {
    const content = MQL5_SECTIONS[activeSection].content;
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const fileStats = [
    { label: 'إجمالي الأسطر', value: '1,884' },
    { label: 'الإصلاحات الحرجة', value: '6 ✅' },
    { label: 'الميزات الجديدة', value: '5 🆕' },
    { label: 'مؤشرات التصويت', value: '9 📊' },
    { label: 'حالات FSM', value: '4 🔍' },
    { label: 'أوضاع الحماية', value: '4 🛡️' },
  ];

  return (
    <div className="space-y-6" dir="rtl">

      {/* Header */}
      <div className="bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-3xl p-8 border border-violet-400/30">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex-1">
            <h2 className="text-4xl font-bold text-white mb-2">💻 كود MQL5 الكامل</h2>
            <p className="text-violet-200 text-lg">
              Blessing_Pro_V42_Elite_Fixed.mq5 — النسخة المحسّنة والمثبّتة بالكامل
            </p>
            <p className="text-gray-400 text-sm mt-2">
              جميع الأخطاء السابقة مُصلَحة + 5 ميزات جديدة احترافية
            </p>
          </div>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setShowFullInfo(true)}
              className="px-6 py-3 bg-emerald-500 hover:bg-emerald-400 text-white font-bold rounded-xl transition-all flex items-center gap-2"
            >
              📥 تعليمات الحصول على الملف الكامل
            </button>
            <div className="px-4 py-2 bg-blue-500/20 border border-blue-400/30 rounded-xl text-center">
              <span className="text-blue-300 text-sm">📁 Blessing_Pro_V42_Elite_Fixed.mq5</span>
            </div>
          </div>
        </div>
      </div>

      {/* Full File Info Modal */}
      {showFullInfo && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowFullInfo(false)}>
          <div className="bg-slate-900 border border-purple-500/30 rounded-2xl p-8 max-w-lg w-full" onClick={e => e.stopPropagation()}>
            <h3 className="text-2xl font-bold text-white mb-4">📥 كيفية الحصول على الملف الكامل</h3>
            <ol className="space-y-3 text-gray-300">
              <li className="flex gap-3"><span className="text-purple-400 font-bold">1.</span> افتح تبويب <strong className="text-white">"💻 الكود المجاني"</strong></li>
              <li className="flex gap-3"><span className="text-purple-400 font-bold">2.</span> اضغط على زر <strong className="text-emerald-400">"نسخ الكود الكامل"</strong></li>
              <li className="flex gap-3"><span className="text-purple-400 font-bold">3.</span> افتح MetaEditor في MT5</li>
              <li className="flex gap-3"><span className="text-purple-400 font-bold">4.</span> أنشئ ملف جديد باسم <code className="text-yellow-400 bg-black/30 px-2 py-0.5 rounded">Blessing_Pro_V42.mq5</code></li>
              <li className="flex gap-3"><span className="text-purple-400 font-bold">5.</span> الصق الكود واضغط <strong className="text-white">F7</strong> للترجمة</li>
            </ol>
            <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl text-sm text-yellow-300">
              💡 الكود المعروض في هذه الصفحة هو مقتطفات توضيحية للأجزاء الرئيسية
            </div>
            <button onClick={() => setShowFullInfo(false)} className="mt-6 w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl">
              فهمت ✓
            </button>
          </div>
        </div>
      )}

      {/* File Stats */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {fileStats.map((s, i) => (
          <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
            <div className="text-xl font-bold text-white mb-1">{s.value}</div>
            <div className="text-gray-400 text-xs">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Section Navigator */}
      <div className="bg-white/5 rounded-3xl border border-white/10 overflow-hidden">
        {/* Tab Bar */}
        <div className="flex overflow-x-auto border-b border-white/10 scrollbar-hide">
          {(Object.keys(MQL5_SECTIONS) as (keyof typeof MQL5_SECTIONS)[]).map((key) => (
            <button
              key={key}
              onClick={() => setActiveSection(key)}
              className={`px-5 py-3 text-sm font-semibold whitespace-nowrap transition-all duration-200 border-b-2 ${
                activeSection === key
                  ? 'border-purple-400 text-purple-300 bg-purple-500/10'
                  : 'border-transparent text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              {MQL5_SECTIONS[key].label}
            </button>
          ))}
        </div>

        {/* Code Area */}
        <div className="p-4">
          <div className="flex justify-between items-center mb-3">
            <span className="text-gray-400 text-sm">
              📄 {MQL5_SECTIONS[activeSection].label} — Blessing_Pro_V42_Elite_Fixed.mq5
            </span>
            <button
              onClick={handleCopy}
              className={`px-4 py-1.5 text-sm font-semibold rounded-lg transition-all duration-200 ${
                copied
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-400/40'
                  : 'bg-purple-500/20 text-purple-300 border border-purple-400/30 hover:bg-purple-500/40'
              }`}
            >
              {copied ? '✅ تم النسخ!' : '📋 نسخ'}
            </button>
          </div>
          <pre
            className="bg-black/60 rounded-xl p-5 overflow-x-auto text-sm leading-relaxed"
            style={{ direction: 'ltr', textAlign: 'left', fontFamily: "'Courier New', monospace" }}
          >
            <code className="text-gray-200">{MQL5_SECTIONS[activeSection].content}</code>
          </pre>
        </div>
      </div>

      {/* File Structure */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📋 هيكل الملف الكامل</h3>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { name: 'Enums & Structures', lines: '60', desc: 'REGIME, DD_MODE, PARTIAL_LADDER', color: 'text-blue-400' },
            { name: 'Input Groups', lines: '120', desc: '17 مجموعة إعدادات متكاملة', color: 'text-purple-400' },
            { name: 'FSM Engine', lines: '200', desc: '4 حالات + كاشف Regime متقدم', color: 'text-emerald-400' },
            { name: 'Voting System', lines: '250', desc: '9 مؤشرات بأوزان ديناميكية', color: 'text-yellow-400' },
            { name: 'Smart Grid', lines: '200', desc: 'شبكة + Cascade + Regime Lock', color: 'text-orange-400' },
            { name: 'Risk Management', lines: '300', desc: 'DD Modes + Partial Ladder + Hedge', color: 'text-red-400' },
            { name: 'SMC Engine', lines: '150', desc: 'Order Blocks + Fractals Analysis', color: 'text-pink-400' },
            { name: 'Dashboard GUI', lines: '200', desc: 'لوحة تحكم على الشارت', color: 'text-cyan-400' },
            { name: 'Telegram Alerts', lines: '100', desc: 'إشعارات فورية عبر API', color: 'text-violet-400' },
          ].map((section, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-4 border border-white/5 hover:border-white/20 transition-all">
              <div className={`font-semibold mb-1 ${section.color}`}>{section.name}</div>
              <div className="text-2xl font-bold text-white my-1">{section.lines} <span className="text-sm text-gray-500">سطر</span></div>
              <div className="text-gray-400 text-xs">{section.desc}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-center text-gray-500 text-sm">
          📊 إجمالي: 1,884 سطر برمجي | آخر تحديث: V4.2 Elite Fixed
        </div>
      </div>

      {/* Key Notes */}
      <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border-r-4 border-yellow-400 rounded-2xl p-6">
        <h3 className="text-xl font-bold text-white mb-4">📝 ملاحظات تشغيلية مهمة</h3>
        <div className="grid md:grid-cols-2 gap-3">
          {[
            '✓ الكود مُنظَّم ومُعلَّق بالعربية والإنجليزية',
            '✓ يتضمن نظام Logging متقدم لكل قرار',
            '✓ يحفظ إحصائيات مفصلة لكل FSM State',
            '✓ Dashboard على الشارت يعرض الحالة الحالية',
            '✓ Telegram Alerts عند كل حدث مهم',
            '✓ نظام ملء أوتوماتيكي (Auto Fill Mode)',
            '✓ Partial Close بثلاثة مستويات (30/50/70%)',
            '✓ Smart Hedge عند تجاوز حد الـ DD',
          ].map((note, i) => (
            <div key={i} className="text-gray-300 text-sm flex items-center gap-2">
              <span className="text-yellow-400">•</span>
              {note}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
