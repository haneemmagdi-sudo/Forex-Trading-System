//+------------------------------------------------------------------+
//|        Blessing_Pro_V42_Elite_Fixed.mq5                         |
//| 🦅 V4.2 Elite Fixed: All Bugs Corrected + Major Enhancements    |
//| ✅ FIX 1: ProcessTrueSMC — g_LastSMCBar activated               |
//| ✅ FIX 2: SuperTrend buffer logic corrected                      |
//| ✅ FIX 3: lockedProfit formula corrected                         |
//| ✅ FIX 4: DetectEarlyReversal — Doji over-trigger fixed          |
//| ✅ FIX 5: ManageBasketBE — reset logic fixed                     |
//| ✅ FIX 6: IsFirstRun / MaxDD first-tick protection               |
//| 🆕 NEW: Partial Close Ladder (30/50/70%)                        |
//| 🆕 NEW: Cascade Protection (3 consecutive losses)               |
//| 🆕 NEW: Volatility-Adjusted Grid Multiplier                     |
//| 🆕 NEW: Regime Lock (session direction lock)                    |
//| 🆕 NEW: Smart Hedging Mode on DD breach                         |
//+------------------------------------------------------------------+
#property copyright "Strategic Trading Lab - Elite Edition V4.2"
#property version   "4.20"
#property description "Blessing Pro FSM Elite V4.2 - Fixed & Enhanced Adaptive Grid System"
#property tester_indicator "Examples\\Heiken Ashi.ex5"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\OrderInfo.mqh>

//====================================================================
// ⚙️ تعريفات النظام (System Defines)
//====================================================================
#define VERSION_STRING         "V4.2 Elite Fixed"
#define ERR_BUFFER_COPY_FAIL   1002
#define ERR_NO_RATES           1003
#define MAX_BUFFER_SIZE        500
#define STABILIZATION_BARS     3

//====================================================================
// 🏗️ تعريفات الأنواع (Enums - Must be BEFORE inputs)
//====================================================================
enum ENUM_MARKET_REGIME {
    REGIME_LOW_VOL_RANGE,      // الغرفة A: تذبذب بطيء
    REGIME_HIGH_VOL_RANGE,     // الغرفة B: تذبذب سريع
    REGIME_SLOW_TREND,         // الغرفة C: ترند بطيء
    REGIME_STRONG_TREND,       // الغرفة D: ترند قوي
    REGIME_CHAOS               // حالة طوارئ
};

enum ENUM_DASH_POS {
    POS_TOP_LEFT,
    POS_TOP_RIGHT,
    POS_BOTTOM_LEFT,
    POS_BOTTOM_RIGHT
};

// ✅ NEW V4.2: أوضاع الحماية من التراجع
enum ENUM_DD_MODE {
    DD_NORMAL,      // وضع طبيعي
    DD_SOFT,        // تراجع بسيط — وضع التعافي
    DD_HEDGE,       // تراجع متوسط — وضع التحوط
    DD_EMERGENCY    // تراجع حرج — إيقاف تام
};

//====================================================================
// 📥 مجموعات الإدخال (Input Groups)
//====================================================================

input group "=== 1. الإعدادات العامة (General Settings) ==="
input string   TradeComment       = "Blessing_FSM_V42";
input ulong    EA_Magic_Number    = 112345;
input double   Lot                = 0.01;
input double   MaxSpread          = 25.0;

input group "=== 2. تبني الصفقات (Adopt Trades Pro) ==="
input bool     ManageManualTrades = true;   // تبني الصفقات اليدوية (Magic=0)
input bool     Adopt_Other_EA     = true;   // تبني صفقات إكسبرت آخر
input ulong    Other_EA_Magic     = 123456;
input bool     ManageAdoptedSL    = true;   // تطبيق SL ديناميكي على المتبناة
input bool     ManageAdoptedTrail = true;   // تطبيق Trailing على المتبناة

input group "=== 3. البوابات الحديدية (Iron Gates) ==="
input int      EMA_Trend_Period   = 50;

input group "=== 4. مجلس التصويت (Enhanced Voting Council) ==="
input double   Required_Council_Points = 3.0;  // ✅ FIXED: double
input int      BB_Period          = 20;
input double   BB_Dev             = 2.0;
input int      Ichi_Tenkan        = 2;
input int      Ichi_Kijun         = 5;
input int      Ichi_Senkou        = 8;

input group "=== 5. فلاتر السياق (ADR & News Filters) ==="
input double   MaxADR_Percent     = 80.0;
input bool     UseNewsFilter      = false;
input int      NewsBlockStart     = 13;
input int      NewsBlockEnd       = 16;

input group "=== 6. فلتر الجلسات (Session Filter) ==="
input bool     UseSessionFilter   = true;
input bool     TradeLondonSession = true;   // 07:00-16:00 GMT
input bool     TradeNYSession     = true;   // 13:00-22:00 GMT
input bool     TradeAsiaSession   = true;  // 22:00-07:00 GMT

input group "=== 7. الشبكة التكتيكية (Smart Grid) ==="
input bool     UseSmartGrid         = true;
input int      MaxTrades            = 10;
input double   Multiplier_LowVol    = 1.8;
input double   Multiplier_HighVol   = 0.9;
input double   Multiplier_SlowTrend = 1.5;
input double   Multiplier_StrongTrend = 1.2;
input int      GridDistancePips     = 25;
input bool     Use_Dynamic_ATR      = true;
input double   ATRMultiplier        = 2.0;

input group "=== 8. وقف الخسارة الديناميكي (Dynamic SL) ==="
input bool     UseDynamicSL         = false;
input double   SL_ATR_Multiplier    = 2.5;
input bool     UseTrailingStop      = true;
input double   Trail_ATR_Mult       = 1.5;

input group "=== 9. درع الحماية (Pending Shield) ==="
input bool     UsePendingShield     = true;
input double   EmergencyFreezeDD    = 3.0;
input int      PendingShieldDist    = 20;
input int      Shield_StopLoss_Pips = 30;
input int      Shield_BE_Pips       = 10;

input group "=== 10. الهدف والدفاع النهائي (Quantum Target) ==="
input double   BaseTargetUSD        = 2.0;
input bool     UseBasketTrailing    = true;
input double   TrailLockPercent     = 60.0;   // ✅ V4.2: نسبة تأمين الربح
input double   MaxDDPercent         = 5.0;
input double   SoftDD_Warning       = 3.0;

input group "=== 11. التعافي الذكي (Smart Recovery) ==="
input bool     UseSmartRecovery        = true;
input double   RecoveryLotFactor       = 0.5;
input double   RecoveryCloseThreshold  = 1.0;

input group "=== 12. اللوحة (Dashboard) ==="
input ENUM_DASH_POS DashboardPosition  = POS_TOP_LEFT;
input int      Panel_X                 = 20;
input int      Panel_Y                 = 20;
input color    BgColor                 = clrBlack;
input color    BorderColor             = clrDimGray;
input color    TextColor               = clrLightGray;
input color    BullColor               = clrLimeGreen;
input color    BearColor               = clrOrangeRed;

input group "=== 13. الأرباح الجزئية المتدرجة (Partial Close Ladder) ==="
input bool     UsePartialTP            = true;
input double   PartialTP_L1_Pips       = 10.0;  // 🆕 المستوى 1: إغلاق 30%
input double   PartialTP_L2_Pips       = 20.0;  // 🆕 المستوى 2: إغلاق 50%
input double   PartialTP_L3_Pips       = 35.0;  // 🆕 المستوى 3: إغلاق 70%
input bool     MoveToBreakEvenOnL1     = true;   // 🆕 نقل SL لنقطة التعادل بعد L1

input group "=== 14. بنية السوق (True SMC) ==="
input bool     Use_True_SMC            = true;
input int      SMCDistancePips         = 10;

input group "=== 15. الفلتر الذهبي (Double Saturation) ==="
input bool     Use_Double_Saturation   = true;
input int      RSI_Fast                = 7;
input int      RSI_Overbought          = 70;
input int      RSI_Oversold            = 30;
input int      ST_Period               = 10;
input double   ST_Multiplier           = 3.0;
input int      Momentum_Period         = 10;

input group "=== 16. تقليل التراجع - Anti-DD Suite ==="
input bool     GridOnlyWithHTF         = true;
input ENUM_TIMEFRAMES HTF_TF           = PERIOD_H4;
input bool     UseBasketBE             = true;
input double   BasketBE_TriggerUSD     = 3.0;
input double   BasketBE_PadPips        = 2.0;

input group "=== 17. 🆕 الحماية المتقدمة (Advanced Protection V4.2) ==="
input bool     UseCascadeProtection    = true;   // 🆕 وقف بعد 3 خسائر متتالية
input int      CascadeMaxLosses        = 3;       // 🆕 عدد الخسائر المتتالية
input int      CascadeCooldownBars     = 20;      // 🆕 فترة راحة (شموع) بعد Cascade
input bool     UseRegimeLock           = true;    // 🆕 قفل اتجاه الشبكة لنفس الجلسة
input bool     UseSmartHedge           = true;    // 🆕 تحوط ذكي عند DD > HedgeDD
input double   HedgeDDPercent          = 2.5;     // 🆕 تفعيل التحوط عند هذا الـ DD%
input double   HedgeLotFactor          = 0.7;     // 🆕 حجم التحوط (نسبة من الخسارة)

//====================================================================
// 📊 هياكل البيانات (Data Structures)
//====================================================================
struct REGIME_DATA {
    double atr_current;
    double atr_daily;
    double ema_angle;
    int    adx_level;
    double range_percent;
    bool   ha_trend_confirmed;
};
REGIME_DATA regimeData;

struct VOTE_WEIGHTS {
    double ema_weight;
    double ha_weight;
    double smc_weight;
    double rsi_weight;
    double adx_weight;
    double macd_weight;
    double momentum_weight;
    double st_weight;
    double ichi_weight;
    double total_weight;
};
VOTE_WEIGHTS voteWeights;

//====================================================================
// 📌 متغيرات عامة (Global Variables)
//====================================================================
CTrade         m_trade;
CPositionInfo  m_position;
COrderInfo     m_order;
CSymbolInfo    m_symbol;

ulong  MagicNumber, ShieldMagic, RecovMagic, HedgeMagic;
double PipSize;
int    LotDecimals;
string prefix;

// Indicator Handles
int h_EMA, h_HA, h_BB, h_MACD, h_Ichi;
int h_ATR_D1, h_ATR_G, h_Fractals, h_ADX;
int h_RSI_Sat, h_SuperTrend, h_Momentum;

// SMC Data
double lastBullOB_Top = 0, lastBullOB_Bot = 0;
double lastBearOB_Top = 0, lastBearOB_Bot = 0;
datetime g_LastSMCBar = 0;  // ✅ FIX 1: الآن يُستخدم فعلياً

// HTF Bias
enum ENUM_HTF_BIAS_EA { HTF_BULL, HTF_BEAR, HTF_NEUTRAL };
ENUM_HTF_BIAS_EA g_HTF_Bias_EA = HTF_NEUTRAL;
bool             g_BasketBE_Done        = false;
bool             g_BasketBE_Applied     = false;  // ✅ FIX 5: علامة منفصلة

// Portfolio Stats
int    OldGridCount, ShieldActiveCount, ShieldPendingCount;
int    AdoptedCount = 0;
double OldGridProfit, ShieldProfit, CurrentDD, GlobalDD;
double MaxBasketProfit = 0.0;

// FSM State
ENUM_MARKET_REGIME CurrentRegime = REGIME_LOW_VOL_RANGE;
string g_MarketRegime = "INITIALIZING...";
color  g_RegimeColor  = clrYellow;

// Voting Scores
double g_buyScore  = 0.0;
double g_sellScore = 0.0;

// Status Flags
bool   IsFirstRun     = true;
bool   g_softDDActive = false;
bool   g_earlyReversal= false;

// DD Protection Mode
ENUM_DD_MODE g_DDMode = DD_NORMAL;

// Trend Tracker
int    consecutiveBullBars = 0;
int    consecutiveBearBars = 0;
datetime lastBarTime = 0;

// ✅ FIX 6: IsFirstRun — حماية من MaxDD في أول تيك
bool g_InitComplete = false;

// 🆕 V4.2: Cascade Protection
int      g_ConsecutiveLosses  = 0;
datetime g_CascadeCooldownEnd = 0;
bool     g_CascadeActive      = false;

// 🆕 V4.2: Regime Lock (تأمين اتجاه الجلسة)
bool     g_RegimeLockBuy  = false;  // مسموح بالشراء في هذه الجلسة؟
bool     g_RegimeLockSell = false;  // مسموح بالبيع في هذه الجلسة؟
int      g_RegimeLockHour = -1;     // ساعة بدء الجلسة الحالية

// 🆕 V4.2: Partial Ladder tracking
struct PARTIAL_LADDER {
    bool level1_done;
    bool level2_done;
    bool level3_done;
};

// حالة Ladder لكل صفقة (بحد أقصى MaxTrades)
PARTIAL_LADDER g_LadderState[];

// 🆕 V4.2: Smart Hedge
bool   g_HedgeActive  = false;
ulong  g_HedgeTicket  = 0;

int    last_regime_bars = 0;
datetime last_regime_time = 0;

//====================================================================
// 🛠️ دوال مساعدة (Helper Functions)
//====================================================================

bool IsSameSymbol(string sym1, string sym2) {
    return (StringCompare(sym1, sym2, false) == 0);
}

bool IsMainPosition(ulong m) {
    if(m == MagicNumber) return true;
    if(ManageManualTrades && m == 0) return true;
    if(Adopt_Other_EA && m == Other_EA_Magic) return true;
    return false;
}

bool IsAdoptedPosition(ulong m) {
    if(ManageManualTrades && m == 0) return true;
    if(Adopt_Other_EA && m == Other_EA_Magic) return true;
    return false;
}

bool ValidateHandle(int handle) {
    return (handle != INVALID_HANDLE);
}

bool SafeCopyBuffer(int handle, int buffer, int shift, int count, double &arr[]) {
    if(!ValidateHandle(handle)) return false;
    ArraySetAsSeries(arr, true);
    int result = CopyBuffer(handle, buffer, shift, count, arr);
    if(result <= 0) {
        PrintFormat("⚠️ SafeCopyBuffer fail: buf=%d shift=%d err=%d", buffer, shift, GetLastError());
        return false;
    }
    return true;
}

double CalculateEMAAngle(int period = 5) {
    double ema_arr[];
    ArrayResize(ema_arr, period + 2);
    if(!SafeCopyBuffer(h_EMA, 0, 0, period + 2, ema_arr)) return 0.0;
    if(period < 2 || PipSize <= 0) return 0.0;
    double numerator   = ema_arr[0] - ema_arr[period];
    double denominator = period * PipSize;
    if(denominator == 0) return 0.0;
    return atan(numerator / denominator) * (180.0 / M_PI);
}

//====================================================================
// 🚀 OnInit
//====================================================================
int OnInit() {
    IsFirstRun    = true;
    g_InitComplete= false;
    m_symbol.Name(_Symbol);
    MagicNumber = EA_Magic_Number;
    ShieldMagic = MagicNumber + 100;
    RecovMagic  = MagicNumber + 200;
    HedgeMagic  = MagicNumber + 300;  // 🆕 Magic للتحوط الذكي
    prefix      = "BLS_GUI_" + _Symbol + "_";

    // حساب PipSize
    PipSize = m_symbol.Point();
    if(PipSize <= 0.0) PipSize = _Point;
    if(PipSize <= 0.0) PipSize = 0.0001;
    if(m_symbol.Digits() == 3 || m_symbol.Digits() == 5) PipSize *= 10.0;

    // حساب دقة حجم الصفقة
    double lotStep = m_symbol.LotsStep();
    if(lotStep <= 0.0) lotStep = 0.01;
    if(lotStep <= 0.00001)     LotDecimals = 5;
    else if(lotStep <= 0.0001) LotDecimals = 4;
    else if(lotStep <= 0.001)  LotDecimals = 3;
    else if(lotStep <= 0.01)   LotDecimals = 2;
    else if(lotStep <= 0.1)    LotDecimals = 1;
    else                       LotDecimals = 0;

    // ضبط نمط التعبئة تلقائياً
    long fillModeRaw = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
    if((fillModeRaw & SYMBOL_FILLING_FOK) != 0)
        m_trade.SetTypeFilling(ORDER_FILLING_FOK);
    else if((fillModeRaw & SYMBOL_FILLING_IOC) != 0)
        m_trade.SetTypeFilling(ORDER_FILLING_IOC);
    else
        m_trade.SetTypeFilling(ORDER_FILLING_RETURN);

    m_trade.SetDeviationInPoints(10);

    // 🆕 تهيئة مصفوفة Ladder
    // ✅ FIX: ArrayInitialize لا تعمل مع struct في MQL5 — نُهيئ يدوياً
    ArrayResize(g_LadderState, MaxTrades + 1);
    for(int i = 0; i < ArraySize(g_LadderState); i++) {
        g_LadderState[i].level1_done = false;
        g_LadderState[i].level2_done = false;
        g_LadderState[i].level3_done = false;
    }

    // ── تهيئة المؤشرات ──────────────────────────────────────────────
    h_EMA = iMA(_Symbol, _Period, EMA_Trend_Period, 0, MODE_EMA, PRICE_CLOSE);
    if(!ValidateHandle(h_EMA)) { Print("❌ فشل EMA"); return INIT_FAILED; }

    h_HA = iCustom(_Symbol, _Period, "Examples\\Heiken Ashi");
    if(!ValidateHandle(h_HA))
        Print("⚠️ Heiken Ashi غير موجود - سنستخدم الشموع العادية كبديل");

    h_BB = iBands(_Symbol, _Period, BB_Period, 0, BB_Dev, PRICE_CLOSE);
    if(!ValidateHandle(h_BB)) { Print("❌ فشل Bollinger Bands"); return INIT_FAILED; }

    h_MACD = iMACD(_Symbol, _Period, 12, 26, 9, PRICE_CLOSE);
    if(!ValidateHandle(h_MACD)) { Print("❌ فشل MACD"); return INIT_FAILED; }

    h_Ichi = iIchimoku(_Symbol, _Period, Ichi_Tenkan, Ichi_Kijun, Ichi_Senkou);
    if(!ValidateHandle(h_Ichi)) { Print("❌ فشل Ichimoku"); return INIT_FAILED; }

    h_ATR_D1 = iATR(_Symbol, PERIOD_D1, 14);
    if(!ValidateHandle(h_ATR_D1)) { Print("❌ فشل ATR D1"); return INIT_FAILED; }

    h_ATR_G = iATR(_Symbol, _Period, 14);
    if(!ValidateHandle(h_ATR_G)) { Print("❌ فشل ATR Current"); return INIT_FAILED; }

    h_Fractals = iFractals(_Symbol, _Period);
    if(!ValidateHandle(h_Fractals)) { Print("❌ فشل Fractals"); return INIT_FAILED; }

    h_ADX = iADX(_Symbol, _Period, 14);
    if(!ValidateHandle(h_ADX)) { Print("❌ فشل ADX"); return INIT_FAILED; }

    h_RSI_Sat = iRSI(_Symbol, _Period, RSI_Fast, PRICE_CLOSE);
    if(!ValidateHandle(h_RSI_Sat)) { Print("❌ فشل RSI"); return INIT_FAILED; }

    h_Momentum = iMomentum(_Symbol, _Period, Momentum_Period, PRICE_CLOSE);
    if(!ValidateHandle(h_Momentum)) { Print("❌ فشل Momentum"); return INIT_FAILED; }

    h_SuperTrend = INVALID_HANDLE;
    if(Use_Double_Saturation) {
        h_SuperTrend = iCustom(_Symbol, _Period, "SuperTrend", ST_Period, ST_Multiplier);
        if(!ValidateHandle(h_SuperTrend))
            Print("⚠️ SuperTrend غير موجود - سيُتجاهل في التصويت");
    }

    CreateGUI_Objects();
    EventSetTimer(1);

    PrintFormat("✅ %s | %s | %s نجح التحميل",
                VERSION_STRING, _Symbol, EnumToString(_Period));
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
    EventKillTimer();
    ObjectsDeleteAll(0, prefix);
    ChartRedraw();
    PrintFormat("✅ أُوقف الإكسبرت | السبب: %d", reason);
}

//====================================================================
// قراءة آمنة لقيمة مؤشر
//====================================================================
double GetIndVal(int handle, int buffer, int shift) {
    if(!ValidateHandle(handle)) return 0.0;
    double val[];
    ArrayResize(val, 1);
    if(!SafeCopyBuffer(handle, buffer, shift, 1, val)) return 0.0;
    return val[0];
}

//====================================================================
// فلاتر البيئة (Environment Filters)
//====================================================================
bool IsADRExhausted() {
    double atrD1 = GetIndVal(h_ATR_D1, 0, 1);
    if(atrD1 <= 0 || atrD1 == EMPTY_VALUE) return false;
    double dH = iHigh(_Symbol, PERIOD_D1, 0);
    double dL = iLow(_Symbol, PERIOD_D1, 0);
    return ((dH - dL) >= atrD1 * (MaxADR_Percent / 100.0));
}

bool IsNewsTime() {
    if(!UseNewsFilter) return false;
    MqlDateTime dt;
    TimeCurrent(dt);
    return (dt.hour >= NewsBlockStart && dt.hour <= NewsBlockEnd);
}

bool IsSessionActive() {
    if(!UseSessionFilter) return true;
    MqlDateTime dt;
    TimeGMT(dt);
    int h = dt.hour;
    bool london = (h >= 7 && h < 16);
    bool ny     = (h >= 13 && h < 22);
    bool asia   = (h >= 22 || h < 7);
    if(TradeLondonSession && london) return true;
    if(TradeNYSession     && ny)     return true;
    if(TradeAsiaSession   && asia)   return true;
    return false;
}

//====================================================================
// 🔥 كاشف بيئة السوق (Enhanced FSM Radar - 4 Rooms)
//====================================================================
void DetectMarketRegime(double ask, double bid, double close1, double ema0) {
    double currentSpread = (ask - bid) / PipSize;
    double adx           = GetIndVal(h_ADX, 0, 1);
    double atr_current   = GetIndVal(h_ATR_G, 0, 1);
    double atr_daily     = GetIndVal(h_ATR_D1, 0, 1);

    regimeData.adx_level   = (int)adx;
    regimeData.atr_current = atr_current;
    regimeData.atr_daily   = atr_daily;
    regimeData.ema_angle   = CalculateEMAAngle(5);

    // الفوضى أولاً
    if(currentSpread > MaxSpread || IsADRExhausted() || !IsSessionActive()) {
        CurrentRegime  = REGIME_CHAOS;
        g_MarketRegime = "CHAOS 🔴";
        g_RegimeColor  = clrRed;
        return;
    }

    if(atr_daily > 0)
        regimeData.range_percent = (atr_current / close1) * 100.0;

    // تصنيف 4 غرف
    if(adx < 15.0) {
        if(atr_daily > 0 && atr_current < (atr_daily * 0.4)) {
            CurrentRegime  = REGIME_LOW_VOL_RANGE;
            g_MarketRegime = "LOW VOL 🟡";
            g_RegimeColor  = clrYellow;
        } else {
            CurrentRegime  = REGIME_HIGH_VOL_RANGE;
            g_MarketRegime = "HIGH VOL ⚠️";
            g_RegimeColor  = clrOrange;
        }
    } else {
        if(MathAbs(regimeData.ema_angle) < 15.0) {
            CurrentRegime  = REGIME_SLOW_TREND;
            g_MarketRegime = "SLOW TREND 🔵";
            g_RegimeColor  = clrDodgerBlue;
        } else {
            CurrentRegime  = REGIME_STRONG_TREND;
            g_MarketRegime = "STRONG TREND 🚀";
            g_RegimeColor  = clrLimeGreen;
        }
    }
}

//====================================================================
// تحديث أوزان التصويت حسب البيئة
//====================================================================
void UpdateVoteWeights() {
    voteWeights.ema_weight      = 1.0;
    voteWeights.ha_weight       = 2.0;
    voteWeights.smc_weight      = 1.0;
    voteWeights.rsi_weight      = 0.8;
    voteWeights.adx_weight      = 0.7;
    voteWeights.macd_weight     = 0.6;
    voteWeights.momentum_weight = 0.5;
    voteWeights.st_weight       = 1.0;
    voteWeights.ichi_weight     = 0.8;

    switch(CurrentRegime) {
        case REGIME_LOW_VOL_RANGE:
            voteWeights.rsi_weight      = 1.3;
            voteWeights.adx_weight      = 0.4;
            voteWeights.ha_weight       = 1.5;
            voteWeights.macd_weight     = 0.5;
            break;
        case REGIME_HIGH_VOL_RANGE:
            voteWeights.adx_weight      = 1.4;
            voteWeights.rsi_weight      = 0.5;
            voteWeights.ha_weight       = 2.0;
            voteWeights.momentum_weight = 0.7;
            break;
        case REGIME_SLOW_TREND:
            voteWeights.ema_weight      = 1.3;
            voteWeights.ichi_weight     = 1.2;
            voteWeights.macd_weight     = 0.9;
            voteWeights.rsi_weight      = 0.8;
            break;
        case REGIME_STRONG_TREND:
            voteWeights.ema_weight      = 1.6;
            voteWeights.ha_weight       = 2.5;
            voteWeights.momentum_weight = 0.9;
            voteWeights.rsi_weight      = 0.4;
            voteWeights.ichi_weight     = 1.0;
            break;
        case REGIME_CHAOS:
            voteWeights.ema_weight      = 0.4;
            voteWeights.ha_weight       = 1.0;
            voteWeights.rsi_weight      = 0.3;
            voteWeights.adx_weight      = 0.3;
            voteWeights.macd_weight     = 0.2;
            voteWeights.momentum_weight = 0.2;
            break;
    }

    voteWeights.total_weight =
        voteWeights.ema_weight + voteWeights.ha_weight   +
        voteWeights.smc_weight + voteWeights.rsi_weight  +
        voteWeights.adx_weight + voteWeights.macd_weight +
        voteWeights.momentum_weight + voteWeights.st_weight +
        voteWeights.ichi_weight;
}

//====================================================================
// 🗳️ نظام التصويت المحسّن V4.2
//====================================================================
void CalculateVotingScores(double close1, double ema0, bool haUp, bool haDn) {
    g_buyScore  = 0.0;
    g_sellScore = 0.0;

    // ── 1. EMA ────────────────────────────────────────────────────
    if(close1 > ema0)
        g_buyScore  += voteWeights.ema_weight;
    else if(close1 < ema0)
        g_sellScore += voteWeights.ema_weight;

    // ── 2. Heiken Ashi ────────────────────────────────────────────
    if(haUp)
        g_buyScore  += voteWeights.ha_weight;
    else if(haDn)
        g_sellScore += voteWeights.ha_weight;

    // ── 3. MACD ───────────────────────────────────────────────────
    double macd_main   = GetIndVal(h_MACD, 0, 1);
    double macd_signal = GetIndVal(h_MACD, 1, 1);
    if(macd_main > macd_signal)
        g_buyScore  += voteWeights.macd_weight;
    else if(macd_main < macd_signal)
        g_sellScore += voteWeights.macd_weight;

    // ── 4. Momentum ───────────────────────────────────────────────
    double mom = GetIndVal(h_Momentum, 0, 1);
    if(mom > 100.0)
        g_buyScore  += voteWeights.momentum_weight;
    else if(mom < 100.0)
        g_sellScore += voteWeights.momentum_weight;

    // ── 5. SuperTrend ✅ FIX 2: منطق صحيح ──────────────────────
    // في SuperTrend القياسي:
    //   Buffer 0 = خط الدعم (نشط عندما الاتجاه صاعد) ← إشارة شراء
    //   Buffer 1 = خط المقاومة (نشط عندما الاتجاه هابط) ← إشارة بيع
    // الحل: مقارنة السعر مع القيمة غير الفارغة
    if(Use_Double_Saturation && h_SuperTrend != INVALID_HANDLE) {
        double st_support    = GetIndVal(h_SuperTrend, 0, 1);  // دعم (صعود)
        double st_resistance = GetIndVal(h_SuperTrend, 1, 1);  // مقاومة (هبوط)
        double price_prev    = iClose(_Symbol, _Period, 1);

        // الاتجاه صاعد: Buffer 0 نشط (≠ EMPTY_VALUE) والسعر فوقه
        if(st_support != EMPTY_VALUE && st_support > 0 && price_prev > st_support)
            g_buyScore  += voteWeights.st_weight;
        // الاتجاه هابط: Buffer 1 نشط (≠ EMPTY_VALUE) والسعر تحته
        else if(st_resistance != EMPTY_VALUE && st_resistance > 0 && price_prev < st_resistance)
            g_sellScore += voteWeights.st_weight;
    }

    // ── 6. RSI ────────────────────────────────────────────────────
    double rsi = GetIndVal(h_RSI_Sat, 0, 1);
    if(rsi < RSI_Oversold + 10)
        g_buyScore  += voteWeights.rsi_weight * 0.8;
    else if(rsi > RSI_Overbought - 10)
        g_sellScore += voteWeights.rsi_weight * 0.8;

    // ── 7. ADX مع DI+/DI- ────────────────────────────────────────
    double adx       = GetIndVal(h_ADX, 0, 1);
    double adx_plus  = GetIndVal(h_ADX, 1, 1);  // +DI
    double adx_minus = GetIndVal(h_ADX, 2, 1);  // -DI
    if(adx > 25.0) {
        if(adx_plus > adx_minus)
            g_buyScore  += voteWeights.adx_weight;
        else if(adx_minus > adx_plus)
            g_sellScore += voteWeights.adx_weight;
    }

    // ── 8. Ichimoku Cloud ─────────────────────────────────────────
    double senA = GetIndVal(h_Ichi, 2, 1);
    double senB = GetIndVal(h_Ichi, 3, 1);
    if(senA != EMPTY_VALUE && senB != EMPTY_VALUE) {
        double cloudTop = MathMax(senA, senB);
        double cloudBot = MathMin(senA, senB);
        if(close1 > cloudTop)
            g_buyScore  += voteWeights.ichi_weight;
        else if(close1 < cloudBot)
            g_sellScore += voteWeights.ichi_weight;
    }

    // ── 9. SMC ───────────────────────────────────────────────────
    if(Use_True_SMC) {
        double smcDist = SMCDistancePips * PipSize;
        double ask = m_symbol.Ask();
        double bid = m_symbol.Bid();
        if(lastBullOB_Bot > 0 && ask < (lastBullOB_Bot + smcDist))
            g_buyScore  += voteWeights.smc_weight;
        if(lastBearOB_Top > 0 && bid > (lastBearOB_Top - smcDist))
            g_sellScore += voteWeights.smc_weight;
    }
}

//====================================================================
// ✅ FIX 1: معالجة True SMC — شمعة جديدة فقط
//====================================================================
void ProcessTrueSMC() {
    if(!Use_True_SMC) return;

    // ✅ FIX 1: الآن يعمل فعلياً على شمعة جديدة فقط
    datetime currentBar = iTime(_Symbol, _Period, 0);
    if(currentBar == g_LastSMCBar) return;  // نفس الشمعة - تخطَّ
    g_LastSMCBar = currentBar;

    double fH[], fL[];
    ArrayResize(fH, 100);
    ArrayResize(fL, 100);
    if(!SafeCopyBuffer(h_Fractals, 0, 1, 100, fH)) return;
    if(!SafeCopyBuffer(h_Fractals, 1, 1, 100, fL)) return;

    int h1 = -1, h2 = -1, l1 = -1, l2 = -1;
    int cH = 0, cL = 0;

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

    // ✅ تحقق من صحة النطاق قبل iLowest/iHighest
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

    double close1 = iClose(_Symbol, _Period, 1);
    if(lastBullOB_Bot > 0 && close1 < lastBullOB_Bot) { lastBullOB_Top = 0; lastBullOB_Bot = 0; }
    if(lastBearOB_Top > 0 && close1 > lastBearOB_Top) { lastBearOB_Top = 0; lastBearOB_Bot = 0; }
}

//====================================================================
// ✅ FIX 4: كاشف الانعكاس المبكر — الدوجي مقيَّد
//====================================================================
bool DetectEarlyReversal() {
    double rsi_now  = GetIndVal(h_RSI_Sat, 0, 1);
    double rsi_prev = GetIndVal(h_RSI_Sat, 0, 5);
    double close1   = iClose(_Symbol, _Period, 1);
    double close5   = iClose(_Symbol, _Period, 5);

    // Divergence صعودي
    bool bullDiv = (close1 < close5) && (rsi_now > rsi_prev) && (rsi_now < RSI_Oversold + 20);
    // Divergence هبوطي
    bool bearDiv = (close1 > close5) && (rsi_now < rsi_prev) && (rsi_now > RSI_Overbought - 20);
    if(bullDiv || bearDiv) return true;

    // ✅ FIX 4: الدوجي يُفعَّل فقط عند مناطق تشبع (RSI خارج 40-60)
    // هذا يمنع الإيقاف المفرط خلال التداول العادي
    bool rsiInExtreme = (rsi_now < RSI_Oversold + 15) || (rsi_now > RSI_Overbought - 15);
    if(rsiInExtreme) {
        double open1  = iOpen(_Symbol, _Period, 1);
        double high1  = iHigh(_Symbol, _Period, 1);
        double low1   = iLow(_Symbol, _Period, 1);
        double body   = MathAbs(close1 - open1);
        double range  = high1 - low1;
        if(range > 0 && body / range < 0.1) return true;
    }

    return false;
}

//====================================================================
// حساب SL الديناميكي (ATR-based)
//====================================================================
double CalculateDynamicSL(bool isBuy, double entryPrice, double atrValue) {
    if(!UseDynamicSL || atrValue <= 0) return 0;
    double sl_dist    = atrValue * SL_ATR_Multiplier;
    double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
    sl_dist = MathMax(sl_dist, stopsLevel + PipSize);
    double sl = isBuy ? (entryPrice - sl_dist) : (entryPrice + sl_dist);
    return NormalizeDouble(sl, _Digits);
}

//====================================================================
// تطبيق Trailing Stop (ATR-based)
//====================================================================
void ApplyTrailingStop(ulong ticket, long posType, double openPrice,
                       double currentPrice, double currentSL, double atrValue) {
    if(!UseTrailingStop || atrValue <= 0) return;
    double trailDist  = atrValue * Trail_ATR_Mult;
    double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
    trailDist = MathMax(trailDist, stopsLevel + PipSize);

    if(posType == POSITION_TYPE_BUY) {
        double newSL = NormalizeDouble(currentPrice - trailDist, _Digits);
        if(newSL > openPrice + stopsLevel && newSL > currentSL + stopsLevel)
            m_trade.PositionModify(ticket, newSL, 0);
    } else {
        double newSL = NormalizeDouble(currentPrice + trailDist, _Digits);
        if((currentSL == 0 || newSL < currentSL - stopsLevel) &&
           newSL < openPrice - stopsLevel)
            m_trade.PositionModify(ticket, newSL, 0);
    }
}

//====================================================================
// إدارة الصفقات المتبناة (Adopt Trades Pro)
//====================================================================
void ManageAdoptedTrades() {
    if(!ManageManualTrades && !Adopt_Other_EA) return;

    AdoptedCount = 0;
    double atrValue = GetIndVal(h_ATR_G, 0, 1);

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

        ulong m = m_position.Magic();
        if(!IsAdoptedPosition(m)) continue;

        AdoptedCount++;
        ulong  ticket       = m_position.Ticket();
        long   posType      = m_position.PositionType();
        double openPrice    = m_position.PriceOpen();
        double currentPrice = m_position.PriceCurrent();
        double currentSL    = m_position.StopLoss();

        // الخطوة 1: تطبيق SL ابتدائي
        if(ManageAdoptedSL && currentSL == 0 && atrValue > 0) {
            double sl = CalculateDynamicSL(posType == POSITION_TYPE_BUY, openPrice, atrValue);
            if(sl > 0) {
                m_trade.PositionModify(ticket, sl, m_position.TakeProfit());
                PrintFormat("📌 تبني: وضع SL=%.5f على صفقة #%I64u", sl, ticket);
            }
        }

        // الخطوة 2: Trailing Stop
        if(ManageAdoptedTrail && atrValue > 0) {
            ApplyTrailingStop(ticket, posType, openPrice,
                              currentPrice, currentSL, atrValue);
        }
    }
}

//====================================================================
// Break Even لصفقات الدرع
//====================================================================
void ManageShieldBreakEven() {
    if(Shield_BE_Pips <= 0) return;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(m_position.Magic() != ShieldMagic) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

        double op       = m_position.PriceOpen();
        double cp       = m_position.PriceCurrent();
        double sl       = m_position.StopLoss();
        long   type     = m_position.PositionType();
        double pipProfit= (type == POSITION_TYPE_BUY) ?
                          (cp - op) / PipSize : (op - cp) / PipSize;

        if(pipProfit >= Shield_BE_Pips) {
            double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
            double safeDist   = MathMax(stopsLevel + PipSize, 2 * PipSize);

            if(type == POSITION_TYPE_BUY && sl < op) {
                double newSL = NormalizeDouble(op + safeDist, _Digits);
                m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
            } else if(type == POSITION_TYPE_SELL && (sl > op || sl == 0)) {
                double newSL = NormalizeDouble(op - safeDist, _Digits);
                m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
            }
        }
    }
}

//====================================================================
// 🆕 V4.2: الأرباح الجزئية المتدرجة (Partial Close Ladder)
// L1: 30% عند PartialTP_L1_Pips
// L2: 50% من الباقي عند PartialTP_L2_Pips
// L3: 70% من الباقي عند PartialTP_L3_Pips
//====================================================================
void ManagePartialProfit() {
    if(!UsePartialTP) return;

    double minLot = MathMax(m_symbol.LotsMin(), 0.01);
    double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

    int lIdx = 0; // مؤشر Ladder
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;
        // تجاهل صفقات التحوط والدرع
        if(m_position.Magic() == ShieldMagic || m_position.Magic() == HedgeMagic) continue;

        double op   = m_position.PriceOpen();
        double cp   = m_position.PriceCurrent();
        double vol  = m_position.Volume();
        long   type = m_position.PositionType();
        ulong  tkt  = m_position.Ticket();
        double pips = (type == POSITION_TYPE_BUY) ?
                      (cp - op) / PipSize : (op - cp) / PipSize;

        if(lIdx >= ArraySize(g_LadderState)) break;
        PARTIAL_LADDER ladder = g_LadderState[lIdx];

        // ── المستوى 1: 30% عند L1_Pips ───────────────────────────
        if(!ladder.level1_done && pips >= PartialTP_L1_Pips && vol > minLot * 1.5) {
            double closeVol = NormalizeDouble(vol * 0.30, LotDecimals);
            if(closeVol < minLot) closeVol = minLot;
            if(closeVol < vol) {
                if(m_trade.PositionClosePartial(tkt, closeVol)) {
                    g_LadderState[lIdx].level1_done = true;
                    // نقل SL لنقطة التعادل + هامش
                    if(MoveToBreakEvenOnL1) {
                        double safeDist = MathMax(2 * PipSize, stopsLevel + PipSize);
                        double newSL = (type == POSITION_TYPE_BUY) ?
                                       NormalizeDouble(op + safeDist, _Digits) :
                                       NormalizeDouble(op - safeDist, _Digits);
                        m_trade.PositionModify(tkt, newSL, m_position.TakeProfit());
                    }
                    PrintFormat("💰 Ladder L1 (30%%): %.2f lots | %.1f pips", closeVol, pips);
                }
            }
        }
        // ── المستوى 2: 50% من الباقي عند L2_Pips ─────────────────
        else if(ladder.level1_done && !ladder.level2_done &&
                pips >= PartialTP_L2_Pips && vol > minLot * 1.5) {
            double closeVol = NormalizeDouble(vol * 0.50, LotDecimals);
            if(closeVol < minLot) closeVol = minLot;
            if(closeVol < vol) {
                if(m_trade.PositionClosePartial(tkt, closeVol)) {
                    g_LadderState[lIdx].level2_done = true;
                    PrintFormat("💰 Ladder L2 (50%%): %.2f lots | %.1f pips", closeVol, pips);
                }
            }
        }
        // ── المستوى 3: 70% من الباقي عند L3_Pips ─────────────────
        else if(ladder.level1_done && ladder.level2_done && !ladder.level3_done &&
                pips >= PartialTP_L3_Pips && vol > minLot * 1.5) {
            double closeVol = NormalizeDouble(vol * 0.70, LotDecimals);
            if(closeVol < minLot) closeVol = minLot;
            if(closeVol < vol) {
                if(m_trade.PositionClosePartial(tkt, closeVol)) {
                    g_LadderState[lIdx].level3_done = true;
                    PrintFormat("💰 Ladder L3 (70%%): %.2f lots | %.1f pips", closeVol, pips);
                }
            }
        }

        lIdx++;
    }
}

// إعادة تعيين حالة Ladder عند إغلاق الشبكة
void ResetLadderState() {
    for(int i = 0; i < ArraySize(g_LadderState); i++) {
        g_LadderState[i].level1_done = false;
        g_LadderState[i].level2_done = false;
        g_LadderState[i].level3_done = false;
    }
}

//====================================================================
// وحدة التعافي الذكي (Smart Recovery)
//====================================================================
void SmartRecoveryModule() {
    if(!UseSmartRecovery) return;
    if(GlobalDD < SoftDD_Warning) return;

    double maxLoss    = -DBL_MAX;
    ulong  bestTicket = 0;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

        double profit = m_position.Profit() + m_position.Swap();
        if(profit < 0 && profit > maxLoss) {
            maxLoss    = profit;
            bestTicket = m_position.Ticket();
        }
    }

    if(bestTicket > 0 && MathAbs(maxLoss) <= RecoveryCloseThreshold) {
        m_trade.PositionClose(bestTicket);
        PrintFormat("🔄 التعافي: إغلاق صفقة #%I64u | خسارة: $%.2f", bestTicket, maxLoss);
    }
}

//====================================================================
// 📡 كشف اتجاه الفريم الكبير (HTF Bias)
//====================================================================
void UpdateHTFBias() {
    double hH[], hL[];
    ArraySetAsSeries(hH, true); ArraySetAsSeries(hL, true);
    if(CopyHigh(_Symbol, HTF_TF, 0, 10, hH) <= 0 ||
       CopyLow (_Symbol, HTF_TF, 0, 10, hL) <= 0) {
        g_HTF_Bias_EA = HTF_NEUTRAL; return;
    }
    bool hh = (hH[2] > hH[5] && hH[5] > hH[8]);
    bool hl = (hL[2] > hL[5] && hL[5] > hL[8]);
    bool lh = (hH[2] < hH[5] && hH[5] < hH[8]);
    bool ll = (hL[2] < hL[5] && hL[5] < hL[8]);
    if(hh && hl)      g_HTF_Bias_EA = HTF_BULL;
    else if(lh && ll) g_HTF_Bias_EA = HTF_BEAR;
    else              g_HTF_Bias_EA = HTF_NEUTRAL;
}

//====================================================================
// 🆕 V4.2: Regime Lock — تأمين اتجاه الجلسة
// يمنع الشبكة من التبديل بين الشراء والبيع في نفس الجلسة
//====================================================================
void UpdateRegimeLock() {
    if(!UseRegimeLock) return;

    MqlDateTime dt;
    TimeGMT(dt);
    int currentHour = dt.hour;

    // تحديد ساعة الجلسة الحالية
    int sessionStartHour = -1;
    if(TradeLondonSession && currentHour >= 7 && currentHour < 16)  sessionStartHour = 7;
    else if(TradeNYSession && currentHour >= 13 && currentHour < 22) sessionStartHour = 13;
    else if(TradeAsiaSession && (currentHour >= 22 || currentHour < 7)) sessionStartHour = 22;

    // جلسة جديدة — إعادة تعيين القفل
    if(sessionStartHour != g_RegimeLockHour) {
        g_RegimeLockHour = sessionStartHour;
        g_RegimeLockBuy  = true;  // مبدئياً كلا الاتجاهين مسموحان
        g_RegimeLockSell = true;
        PrintFormat("🔒 Regime Lock: جلسة جديدة (ساعة %d GMT)", sessionStartHour);
    }

    // إذا كان HTF صاعداً: اقفل البيع بعد أول دخول شراء
    if(OldGridCount > 0) {
        if(g_HTF_Bias_EA == HTF_BULL) {
            g_RegimeLockSell = false;
        } else if(g_HTF_Bias_EA == HTF_BEAR) {
            g_RegimeLockBuy = false;
        }
    }
}

//====================================================================
// 🆕 V4.2: Cascade Protection — حماية من الخسائر المتتالية
//====================================================================
void CheckCascadeProtection() {
    if(!UseCascadeProtection) return;

    // فحص إذا كنا في فترة تبريد
    if(g_CascadeActive && TimeCurrent() < g_CascadeCooldownEnd) return;

    if(g_CascadeActive && TimeCurrent() >= g_CascadeCooldownEnd) {
        g_CascadeActive      = false;
        g_ConsecutiveLosses  = 0;
        Print("✅ Cascade: انتهت فترة التبريد - استئناف التداول");
    }
}

// يُستدعى عند إغلاق صفقة خاسرة
void OnPositionLoss() {
    if(!UseCascadeProtection) return;
    g_ConsecutiveLosses++;
    PrintFormat("⚠️ Cascade: خسارة #%d من %d", g_ConsecutiveLosses, CascadeMaxLosses);

    if(g_ConsecutiveLosses >= CascadeMaxLosses) {
        g_CascadeActive     = true;
        g_CascadeCooldownEnd= iTime(_Symbol, _Period, 0) +
                              (datetime)(CascadeCooldownBars * PeriodSeconds(_Period));
        PrintFormat("🛑 Cascade: إيقاف مؤقت لـ %d شمعة", CascadeCooldownBars);
    }
}

//====================================================================
// 🆕 V4.2: Smart Hedge — تحوط ذكي عند DD متوسط
//====================================================================
void ManageSmartHedge() {
    if(!UseSmartHedge) return;
    if(GlobalDD < HedgeDDPercent) {
        // إلغاء التحوط إذا تعافى الحساب
        if(g_HedgeActive && g_HedgeTicket > 0) {
            if(m_position.SelectByTicket(g_HedgeTicket)) {
                if(m_position.Profit() > 0) {
                    m_trade.PositionClose(g_HedgeTicket);
                    g_HedgeActive = false;
                    g_HedgeTicket = 0;
                    Print("✅ Hedge: أُغلق التحوط بربح");
                }
            } else {
                g_HedgeActive = false;
                g_HedgeTicket = 0;
            }
        }
        return;
    }

    // DD وصل لمستوى التحوط
    if(g_HedgeActive) return;  // تحوط موجود بالفعل
    if(OldGridCount == 0) return;  // لا صفقات للتحوط ضدها

    // حساب صافي الوضع
    double netBuyLots  = 0, netSellLots = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;
        if(m_position.PositionType() == POSITION_TYPE_BUY) netBuyLots  += m_position.Volume();
        else                                                 netSellLots += m_position.Volume();
    }

    double netExposure = netBuyLots - netSellLots;
    if(MathAbs(netExposure) < m_symbol.LotsMin()) return;

    // حجم التحوط
    double hedgeLot = NormalizeDouble(MathAbs(netExposure) * HedgeLotFactor, LotDecimals);
    hedgeLot = MathMax(hedgeLot, m_symbol.LotsMin());
    hedgeLot = MathMin(hedgeLot, m_symbol.LotsMax());

    m_trade.SetExpertMagicNumber(HedgeMagic);
    bool hedgeResult = false;

    if(netExposure > 0) {
        // صافي شراء → فتح بيع للتحوط
        hedgeResult = m_trade.Sell(hedgeLot, _Symbol, m_symbol.Bid(), 0, 0, "SmartHedge");
    } else {
        // صافي بيع → فتح شراء للتحوط
        hedgeResult = m_trade.Buy(hedgeLot, _Symbol, m_symbol.Ask(), 0, 0, "SmartHedge");
    }

    if(hedgeResult) {
        g_HedgeActive = true;
        g_HedgeTicket = m_trade.ResultOrder();
        PrintFormat("🛡️ Hedge: تحوط %.2f lots | DD=%.2f%%", hedgeLot, GlobalDD);
    }
}

//====================================================================
// 🛡️ إدارة Basket BreakEven ✅ FIX 5: منطق محسَّن
//====================================================================
void ManageBasketBE() {
    // ✅ FIX 5: إعادة التعيين فقط عند إغلاق كامل الشبكة
    if(OldGridCount == 0) {
        // الشبكة أُغلقت — أعِد التعيين للشبكة القادمة
        if(g_BasketBE_Applied) {
            g_BasketBE_Applied = false;
            g_BasketBE_Done    = false;
        }
        return;
    }

    if(!UseBasketBE) return;
    if(g_BasketBE_Applied) return;  // ✅ FIX 5: طُبِّق بالفعل لهذه الشبكة

    // لم يتجاوز الربح الحد بعد
    if(OldGridProfit < BasketBE_TriggerUSD) return;

    // حساب المتوسط المرجح
    double totalBuyLots = 0, totalSellLots = 0;
    double wBuyPrice   = 0, wSellPrice   = 0;
    int    nBuy = 0, nSell = 0;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

        double vol = m_position.Volume();
        double op  = m_position.PriceOpen();
        if(m_position.PositionType() == POSITION_TYPE_BUY) {
            wBuyPrice   += op * vol;
            totalBuyLots += vol;
            nBuy++;
        } else {
            wSellPrice    += op * vol;
            totalSellLots += vol;
            nSell++;
        }
    }

    double pad = BasketBE_PadPips * PipSize;
    bool applied = false;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

        ulong  tkt   = m_position.Ticket();
        double curSL = m_position.StopLoss();
        double curTP = m_position.TakeProfit();

        if(m_position.PositionType() == POSITION_TYPE_BUY && nBuy > 0) {
            double avgBuy = wBuyPrice / totalBuyLots;
            double beSL   = NormalizeDouble(avgBuy + pad, _Digits);
            if(curSL < beSL) {
                m_trade.PositionModify(tkt, beSL, curTP);
                applied = true;
            }
        } else if(m_position.PositionType() == POSITION_TYPE_SELL && nSell > 0) {
            double avgSell = wSellPrice / totalSellLots;
            double beSL    = NormalizeDouble(avgSell - pad, _Digits);
            if(curSL == 0 || curSL > beSL) {
                m_trade.PositionModify(tkt, beSL, curTP);
                applied = true;
            }
        }
    }

    if(applied) {
        g_BasketBE_Applied = true;  // ✅ FIX 5: علامة منفصلة تمنع التكرار
        g_BasketBE_Done    = true;
        PrintFormat("✅ Basket BE: نقطة تعادل مطبَّقة | ربح: $%.2f", OldGridProfit);
    }
}

//====================================================================
// ✅ FIX 3 + 🆕 V4.2: تنفيذ الشبكة مع مُضاعِف ATR الديناميكي
//====================================================================
void ExecuteConstitution(ulong magic, int currentTrades, bool buySignal, bool sellSignal) {
    if(currentTrades >= MaxTrades) return;

    // 🆕 Cascade Protection
    if(g_CascadeActive) {
        PrintFormat("🛑 Cascade: تداول موقوف حتى %s", TimeToString(g_CascadeCooldownEnd));
        return;
    }

    double ask = m_symbol.Ask();
    double bid = m_symbol.Bid();
    double atrValue = GetIndVal(h_ATR_G, 0, 1);

    // ── الفلاتر الإجبارية ──────────────────────────────────────────
    if(IsADRExhausted() || IsNewsTime() || CurrentRegime == REGIME_CHAOS ||
       !IsSessionActive()) {
        buySignal  = false;
        sellSignal = false;
    }

    // فلتر SoftDD
    if(g_softDDActive) {
        buySignal  = false;
        sellSignal = false;
    }

    // فلتر الانعكاس المبكر
    if(g_earlyReversal && currentTrades > 0) {
        buySignal  = false;
        sellSignal = false;
    }

    // ── فلتر الشبكة مع الاتجاه الكبير ─────────────────────────────
    if(GridOnlyWithHTF && currentTrades > 0) {
        if(g_HTF_Bias_EA == HTF_BEAR)    buySignal  = false;
        if(g_HTF_Bias_EA == HTF_BULL)    sellSignal = false;
        if(g_HTF_Bias_EA == HTF_NEUTRAL && currentTrades >= MaxTrades/2) {
            buySignal  = false;
            sellSignal = false;
        }
    }

    // 🆕 Regime Lock Filter
    if(UseRegimeLock) {
        if(!g_RegimeLockBuy)  buySignal  = false;
        if(!g_RegimeLockSell) sellSignal = false;
    }

    // ── فلتر SMC ────────────────────────────────────────────────────
    if(Use_True_SMC) {
        double smcDist = SMCDistancePips * PipSize;
        if(lastBearOB_Bot > 0 && ask >= (lastBearOB_Bot - smcDist)) buySignal  = false;
        if(lastBullOB_Top > 0 && bid <= (lastBullOB_Top + smcDist)) sellSignal = false;
    }

    // ── فلتر الانتشار ──────────────────────────────────────────────
    if((ask - bid) / PipSize > MaxSpread) {
        buySignal  = false;
        sellSignal = false;
    }

    if(!buySignal && !sellSignal) return;

    // ── حجم الصفقة ─────────────────────────────────────────────────
    double nLot = Lot;
    if(g_softDDActive)
        nLot = NormalizeDouble(nLot * RecoveryLotFactor, LotDecimals);
    nLot = MathMax(nLot, m_symbol.LotsMin());

    if(currentTrades > 0) {
        double ext_buy  = DBL_MAX;
        double ext_sell = -1.0;
        double lastLot_buy  = 0;
        double lastLot_sell = 0;

        for(int i = PositionsTotal() - 1; i >= 0; i--) {
            if(!m_position.SelectByIndex(i)) continue;
            if(!IsMainPosition(m_position.Magic())) continue;
            if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;

            double op  = m_position.PriceOpen();
            double vol = m_position.Volume();

            if(m_position.PositionType() == POSITION_TYPE_BUY) {
                if(op < ext_buy) { ext_buy = op; lastLot_buy = vol; }
            } else {
                if(ext_sell < 0 || op > ext_sell) { ext_sell = op; lastLot_sell = vol; }
            }
        }

        // 🆕 FIX 3 + مُضاعِف ATR الديناميكي:
        // استخدام ATR النسبي (ATR الحالي / ATR اليومي) لتعديل المُضاعِف
        double mult = Multiplier_SlowTrend;
        switch(CurrentRegime) {
            case REGIME_LOW_VOL_RANGE:   mult = Multiplier_LowVol;      break;
            case REGIME_HIGH_VOL_RANGE:  mult = Multiplier_HighVol;     break;
            case REGIME_SLOW_TREND:      mult = Multiplier_SlowTrend;   break;
            case REGIME_STRONG_TREND:    mult = Multiplier_StrongTrend; break;
            default:                     mult = 0.8;
        }

        // 🆕 V4.2: تعديل المُضاعِف بالتقلب اللحظي
        if(atrValue > 0 && regimeData.atr_daily > 0) {
            double volRatio = atrValue / regimeData.atr_daily;
            // إذا كانت التقلبات عالية: قلّص المُضاعِف
            if(volRatio > 0.6) mult *= 0.8;
            // إذا كانت التقلبات منخفضة: يمكن زيادته قليلاً
            else if(volRatio < 0.2) mult *= 1.1;
        }
        mult = MathMax(0.6, MathMin(mult, 2.5));  // حدود آمنة

        double ls = m_symbol.LotsStep();
        if(ls <= 0.0) ls = 0.01;

        double dist = GridDistancePips * PipSize;
        if(Use_Dynamic_ATR && atrValue > 0)
            dist = atrValue * ATRMultiplier;

        // ── غريد الشراء ─────────────────────────────────────────────
        if(buySignal && ext_buy < DBL_MAX && lastLot_buy > 0 && ask <= (ext_buy - dist)) {
            double nLotBuy = MathRound((lastLot_buy * mult) / ls) * ls;
            if(nLotBuy <= lastLot_buy) nLotBuy = lastLot_buy + ls;
            nLotBuy = MathMin(nLotBuy, m_symbol.LotsMax());
            if(AccountInfoDouble(ACCOUNT_MARGIN_FREE) > 0) {
                m_trade.SetExpertMagicNumber(magic);
                double sl = CalculateDynamicSL(true, ask, atrValue);
                m_trade.Buy(NormalizeDouble(nLotBuy, LotDecimals), _Symbol, ask, sl, 0, "Grid Buy");
            }
        }

        // ── غريد البيع ──────────────────────────────────────────────
        if(sellSignal && ext_sell > 0 && lastLot_sell > 0 && bid >= (ext_sell + dist)) {
            double nLotSell = MathRound((lastLot_sell * mult) / ls) * ls;
            if(nLotSell <= lastLot_sell) nLotSell = lastLot_sell + ls;
            nLotSell = MathMin(nLotSell, m_symbol.LotsMax());
            if(AccountInfoDouble(ACCOUNT_MARGIN_FREE) > 0) {
                m_trade.SetExpertMagicNumber(magic);
                double sl = CalculateDynamicSL(false, bid, atrValue);
                m_trade.Sell(NormalizeDouble(nLotSell, LotDecimals), _Symbol, bid, sl, 0, "Grid Sell");
            }
        }

    } else {
        // ── الدخول الأول (Sniper Entry) ─────────────────────────────
        m_trade.SetExpertMagicNumber(magic);
        if(buySignal) {
            double sl = CalculateDynamicSL(true, ask, atrValue);
            m_trade.Buy(NormalizeDouble(nLot, LotDecimals), _Symbol, ask, sl, 0, "Sniper Buy");
            // بعد الدخول الأول: قفل البيع في حال Regime Lock صاعد
            if(UseRegimeLock && g_HTF_Bias_EA == HTF_BULL) g_RegimeLockSell = false;
        } else if(sellSignal) {
            double sl = CalculateDynamicSL(false, bid, atrValue);
            m_trade.Sell(NormalizeDouble(nLot, LotDecimals), _Symbol, bid, sl, 0, "Sniper Sell");
            if(UseRegimeLock && g_HTF_Bias_EA == HTF_BEAR) g_RegimeLockBuy = false;
        }
    }
}

//====================================================================
// إدارة الصفقات (Trade Management)
//====================================================================
void CloseAllByMagic(ulong targetMagic) {
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;
        ulong m = m_position.Magic();
        if((targetMagic == MagicNumber && IsMainPosition(m)) || (m == targetMagic))
            m_trade.PositionClose(m_position.Ticket());
    }
}

void DeletePendingOrdersByMagic(ulong targetMagic) {
    for(int i = OrdersTotal() - 1; i >= 0; i--) {
        if(!m_order.SelectByIndex(i)) continue;
        if(!IsSameSymbol(m_order.Symbol(), _Symbol)) continue;
        ulong m = m_order.Magic();
        if((targetMagic == MagicNumber && IsMainPosition(m)) || (m == targetMagic))
            m_trade.OrderDelete(m_order.Ticket());
    }
}

void CloseEverything() {
    CloseAllByMagic(MagicNumber);
    CloseAllByMagic(ShieldMagic);
    CloseAllByMagic(HedgeMagic);  // 🆕 إغلاق التحوط أيضاً
    DeletePendingOrdersByMagic(ShieldMagic);
    MaxBasketProfit = 0.0;
    g_HedgeActive   = false;
    g_HedgeTicket   = 0;
    ResetLadderState();
}

//====================================================================
// 🎨 لوحة التحكم المحسّنة V4.2 (Dashboard Pro)
//====================================================================
void CreateLabel(string name, int size = 9) {
    string objName = prefix + name;
    ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
    ObjectSetInteger(0, objName, OBJPROP_CORNER,     CORNER_LEFT_UPPER);
    ObjectSetString(0, objName, OBJPROP_FONT,        "Trebuchet MS");
    ObjectSetInteger(0, objName, OBJPROP_FONTSIZE,   size);
    ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
    ObjectSetInteger(0, objName, OBJPROP_BACK,       false);
    ObjectSetInteger(0, objName, OBJPROP_ZORDER,     1);
}

void CreateGUI_Objects() {
    string bgName = prefix + "BG";
    ObjectCreate(0, bgName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
    ObjectSetInteger(0, bgName, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
    ObjectSetInteger(0, bgName, OBJPROP_BGCOLOR,      BgColor);
    ObjectSetInteger(0, bgName, OBJPROP_BORDER_COLOR, BorderColor);
    ObjectSetInteger(0, bgName, OBJPROP_BORDER_TYPE,  BORDER_FLAT);
    ObjectSetInteger(0, bgName, OBJPROP_BACK,         false);
    ObjectSetInteger(0, bgName, OBJPROP_ZORDER,       0);
    ObjectSetInteger(0, bgName, OBJPROP_SELECTABLE,   false);

    CreateLabel("Title", 10);
    CreateLabel("Subtitle", 8);
    CreateLabel("Line1");
    // 12 صفاً بدل 10 لاستيعاب المعلومات الجديدة
    for(int i = 1; i <= 12; i++) {
        CreateLabel("Row" + IntegerToString(i) + "L");
        CreateLabel("Row" + IntegerToString(i) + "V", 9);
    }
    CreateLabel("Line2");
    CreateLabel("Line3");
    CreateLabel("Line4");
}

void MoveObj(string name, int x, int y) {
    ObjectSetInteger(0, prefix + name, OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, prefix + name, OBJPROP_YDISTANCE, y);
}

void SetTxt(string name, string text, color clr) {
    ObjectSetString(0, prefix + name,  OBJPROP_TEXT,  text);
    ObjectSetInteger(0, prefix + name, OBJPROP_COLOR, clr);
}

void UpdateDashboard(string adrStat, string smcStat, double netLots) {
    long chartW = ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
    long chartH = ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);

    int  w  = 275;   // أوسع قليلاً
    int  h  = 340;   // أطول للصفوف الإضافية
    int  x  = Panel_X;
    int  y  = Panel_Y;

    if(DashboardPosition == POS_TOP_RIGHT)
        x = (int)chartW - w - Panel_X;
    else if(DashboardPosition == POS_BOTTOM_LEFT)
        y = (int)chartH - h - Panel_Y;
    else if(DashboardPosition == POS_BOTTOM_RIGHT) {
        x = (int)chartW - w - Panel_X;
        y = (int)chartH - h - Panel_Y;
    }

    ObjectSetInteger(0, prefix + "BG", OBJPROP_XSIZE, w);
    ObjectSetInteger(0, prefix + "BG", OBJPROP_YSIZE, h);
    MoveObj("BG", x, y);

    int col1 = x + 10;
    int col2 = x + 135;
    int rowY = y + 8;
    int step = 22;

    MoveObj("Title",    col1, rowY); rowY += step;
    MoveObj("Subtitle", col1, rowY); rowY += 4;
    MoveObj("Line1",    col1, rowY); rowY += step;

    for(int i = 1; i <= 4; i++) {
        MoveObj("Row" + IntegerToString(i) + "L", col1, rowY);
        MoveObj("Row" + IntegerToString(i) + "V", col2, rowY);
        rowY += step;
    }
    MoveObj("Line2", col1, rowY); rowY += step;
    for(int i = 5; i <= 8; i++) {
        MoveObj("Row" + IntegerToString(i) + "L", col1, rowY);
        MoveObj("Row" + IntegerToString(i) + "V", col2, rowY);
        rowY += step;
    }
    MoveObj("Line3", col1, rowY); rowY += step;
    for(int i = 9; i <= 12; i++) {
        MoveObj("Row" + IntegerToString(i) + "L", col1, rowY);
        MoveObj("Row" + IntegerToString(i) + "V", col2, rowY);
        rowY += step;
    }
    MoveObj("Line4", col1, rowY);

    // ── النصوص ─────────────────────────────────────────────────────
    SetTxt("Title",    "🦅 BLESSING PRO " + VERSION_STRING, clrGold);
    SetTxt("Subtitle", _Symbol + " | " + EnumToString(CurrentRegime), clrDimGray);
    SetTxt("Line1",    "═══════════════════════════", BorderColor);
    SetTxt("Line2",    "═══════════════════════════", BorderColor);
    SetTxt("Line3",    "═══════════════════════════", BorderColor);
    SetTxt("Line4",    "═══════════════════════════", BorderColor);

    string dir = (netLots > 0) ? "📈 BUY " + DoubleToString(netLots, 2) :
                 (netLots < 0) ? "📉 SELL " + DoubleToString(MathAbs(netLots), 2) :
                                 "⚪ FLAT";

    string ddModeStr = "NORMAL ✅";
    color  ddColor   = BullColor;
    switch(g_DDMode) {
        case DD_SOFT:      ddModeStr = "SOFT DD 🟡";   ddColor = clrYellow;    break;
        case DD_HEDGE:     ddModeStr = "HEDGE 🛡️";     ddColor = clrOrange;    break;
        case DD_EMERGENCY: ddModeStr = "EMERGENCY 🔴"; ddColor = clrOrangeRed; break;
        default: break;
    }

    // ── القسم 1: البيئة ────────────────────────────────────────────
    SetTxt("Row1L", "Regime:",    TextColor);
    SetTxt("Row1V", g_MarketRegime, g_RegimeColor);
    SetTxt("Row2L", "Session:",   TextColor);
    SetTxt("Row2V", IsSessionActive() ? "✅ ACTIVE" : "⏸ CLOSED",
           IsSessionActive() ? BullColor : clrGray);
    SetTxt("Row3L", "ADR:",       TextColor);
    SetTxt("Row3V", adrStat,      clrGold);
    SetTxt("Row4L", "SMC Zone:",  TextColor);
    SetTxt("Row4V", smcStat,      clrSkyBlue);

    // ── القسم 2: الصفقات ───────────────────────────────────────────
    SetTxt("Row5L", "Basket:",    TextColor);
    SetTxt("Row5V", IntegerToString(OldGridCount) + " | " + dir, clrSkyBlue);
    SetTxt("Row6L", "Adopted:",   TextColor);
    SetTxt("Row6V", IntegerToString(AdoptedCount) + " managed",
           AdoptedCount > 0 ? clrAqua : clrDimGray);
    SetTxt("Row7L", "GlobalDD:",  TextColor);
    SetTxt("Row7V", DoubleToString(GlobalDD, 2) + "% / " + DoubleToString(MaxDDPercent, 1) + "%",
           (GlobalDD >= SoftDD_Warning) ? BearColor : BullColor);
    SetTxt("Row8L", "Council:",   TextColor);
    SetTxt("Row8V", "B:" + DoubleToString(g_buyScore, 1) +
                    " S:" + DoubleToString(g_sellScore, 1) +
                    " [" + DoubleToString(Required_Council_Points, 1) + "]", clrAqua);

    // ── القسم 3: الحماية (جديد V4.2) ─────────────────────────────
    SetTxt("Row9L",  "DD Mode:",    TextColor);
    SetTxt("Row9V",  ddModeStr,     ddColor);
    SetTxt("Row10L", "Hedge:",      TextColor);
    SetTxt("Row10V", g_HedgeActive ? "🛡️ ACTIVE" : "✅ OFF",
           g_HedgeActive ? clrOrange : BullColor);
    SetTxt("Row11L", "Cascade:",    TextColor);
    SetTxt("Row11V", g_CascadeActive ? "🛑 COOLING" : (g_ConsecutiveLosses > 0 ?
           "⚠️ " + IntegerToString(g_ConsecutiveLosses) + "/" + IntegerToString(CascadeMaxLosses) : "✅ CLEAR"),
           g_CascadeActive ? BearColor : (g_ConsecutiveLosses > 0 ? clrOrange : BullColor));
    SetTxt("Row12L", "HTF Bias:",   TextColor);
    string htfStr = (g_HTF_Bias_EA == HTF_BULL) ? "📈 BULL" :
                    (g_HTF_Bias_EA == HTF_BEAR) ? "📉 BEAR" : "⚪ NEUTRAL";
    color htfClr  = (g_HTF_Bias_EA == HTF_BULL) ? BullColor :
                    (g_HTF_Bias_EA == HTF_BEAR) ? BearColor : clrGray;
    SetTxt("Row12V", htfStr, htfClr);
}

//====================================================================
// 💓 دالة النبض المركزية (OnTick - The Main Engine)
//====================================================================
void OnTick() {
    if(!m_symbol.RefreshRates()) return;

    // ── تتبع الشمعة الجديدة (Trend Tracker) ─────────────────────
    datetime currentBarTime = iTime(_Symbol, _Period, 0);
    if(currentBarTime != lastBarTime) {
        lastBarTime = currentBarTime;
        double barOpen  = iOpen(_Symbol, _Period, 1);
        double barClose = iClose(_Symbol, _Period, 1);
        if(barClose > barOpen) { consecutiveBullBars++; consecutiveBearBars = 0; }
        else if(barClose < barOpen) { consecutiveBearBars++; consecutiveBullBars = 0; }
    }

    // ── المعالجة الدورية ─────────────────────────────────────────
    ProcessTrueSMC();           // ✅ FIX 1: شمعة جديدة فقط
    ManageShieldBreakEven();
    UpdateHTFBias();
    UpdateRegimeLock();         // 🆕 Regime Lock
    ManageBasketBE();           // ✅ FIX 5: منطق محسَّن
    ManagePartialProfit();      // 🆕 Ladder
    ManageAdoptedTrades();
    CheckCascadeProtection();   // 🆕 Cascade check

    // ── قراءة المؤشرات الأساسية ──────────────────────────────────
    double ema0    = GetIndVal(h_EMA, 0, 1);
    double haOpen  = 0, haClose = 0;
    bool   haUp    = false, haDn = false;

    if(h_HA != INVALID_HANDLE) {
        haOpen  = GetIndVal(h_HA, 0, 1);  // Buffer 0 = HA Open
        haClose = GetIndVal(h_HA, 3, 1);  // Buffer 3 = HA Close
    } else {
        haOpen  = iOpen(_Symbol, _Period, 1);
        haClose = iClose(_Symbol, _Period, 1);
    }
    haUp = (haClose > haOpen);
    haDn = (haClose < haOpen);

    double close1 = iClose(_Symbol, _Period, 1);
    double ask    = m_symbol.Ask();
    double bid    = m_symbol.Bid();

    // ── 1. تصنيف البيئة (FSM) ───────────────────────────────────
    DetectMarketRegime(ask, bid, close1, ema0);

    // ── 2. تحديث أوزان التصويت ──────────────────────────────────
    UpdateVoteWeights();

    // ── 3. حساب التصويت المرجح ──────────────────────────────────
    CalculateVotingScores(close1, ema0, haUp, haDn);

    // ── 4. كشف الانعكاس المبكر (✅ FIX 4: مقيَّد) ──────────────
    g_earlyReversal = DetectEarlyReversal();

    // ── 5. FSM Switchboard ──────────────────────────────────────
    bool masterBuySignal  = false;
    bool masterSellSignal = false;

    switch(CurrentRegime) {
        case REGIME_LOW_VOL_RANGE:
            if(haUp && g_buyScore  >= Required_Council_Points) masterBuySignal  = true;
            if(haDn && g_sellScore >= Required_Council_Points) masterSellSignal = true;
            break;
        case REGIME_HIGH_VOL_RANGE:
            if(haUp && g_buyScore  >= Required_Council_Points + 1.0) masterBuySignal  = true;
            if(haDn && g_sellScore >= Required_Council_Points + 1.0) masterSellSignal = true;
            break;
        case REGIME_SLOW_TREND:
            if(haUp && g_buyScore  >= Required_Council_Points) masterBuySignal  = true;
            if(haDn && g_sellScore >= Required_Council_Points) masterSellSignal = true;
            break;
        case REGIME_STRONG_TREND:
            if(haUp && g_buyScore  >= Required_Council_Points) masterBuySignal  = true;
            if(haDn && g_sellScore >= Required_Council_Points) masterSellSignal = true;
            // لا عكس الاتجاه القوي
            if(close1 > ema0) masterSellSignal = false;
            if(close1 < ema0) masterBuySignal  = false;
            break;
        case REGIME_CHAOS:
            break;
    }

    // ── 6. إحصاء المحفظة ─────────────────────────────────────────
    OldGridCount      = 0;
    ShieldActiveCount = 0;
    ShieldPendingCount= 0;
    OldGridProfit     = 0;
    ShieldProfit      = 0;
    double oldLotsBuy = 0, oldLotsSell = 0;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        ulong  mag   = m_position.Magic();
        double pVol  = m_position.Volume();
        double pProf = m_position.Profit() + m_position.Swap();

        if(IsMainPosition(mag) && IsSameSymbol(m_position.Symbol(), _Symbol)) {
            OldGridCount++;
            OldGridProfit += pProf;
            if(m_position.PositionType() == POSITION_TYPE_BUY) oldLotsBuy  += pVol;
            else                                                 oldLotsSell += pVol;
        } else if(mag == ShieldMagic && IsSameSymbol(m_position.Symbol(), _Symbol)) {
            ShieldActiveCount++;
            ShieldProfit += pProf;
        }
    }
    for(int i = OrdersTotal() - 1; i >= 0; i--) {
        if(m_order.SelectByIndex(i) && IsSameSymbol(m_order.Symbol(), _Symbol) &&
           m_order.Magic() == ShieldMagic)
            ShieldPendingCount++;
    }

    // إعادة تعيين Ladder إذا أُغلقت الشبكة
    if(OldGridCount == 0) ResetLadderState();

    // ── 7. حساب Drawdown ─────────────────────────────────────────
    double bal    = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    GlobalDD = (bal > 0 && equity < bal) ? ((bal - equity) / bal) * 100.0 : 0.0;
    double totalFloating = OldGridProfit + ShieldProfit;
    CurrentDD = (totalFloating < 0 && bal > 0) ?
                (MathAbs(totalFloating) / bal) * 100.0 : 0.0;

    // ── 8. تحديث وضع الحماية (DD Mode) ──────────────────────────
    if(GlobalDD >= MaxDDPercent) {
        g_DDMode       = DD_EMERGENCY;
        g_softDDActive = true;
    } else if(UseSmartHedge && GlobalDD >= HedgeDDPercent) {
        g_DDMode       = DD_HEDGE;
        g_softDDActive = true;
    } else if(GlobalDD >= SoftDD_Warning) {
        g_DDMode       = DD_SOFT;
        g_softDDActive = true;
    } else {
        g_DDMode       = DD_NORMAL;
        g_softDDActive = false;
    }

    // ── 9. التعافي الذكي ─────────────────────────────────────────
    if(g_softDDActive && UseSmartRecovery)
        SmartRecoveryModule();

    // ── 10. Smart Hedge (🆕 V4.2) ────────────────────────────────
    if(UseSmartHedge && g_DDMode == DD_HEDGE)
        ManageSmartHedge();

    // ── 11. ✅ FIX 6: إغلاق إجباري عند MaxDD ─────────────────────
    // إزالة الاعتماد على IsFirstRun — حماية فورية من أول تيك
    if(GlobalDD >= MaxDDPercent) {
        PrintFormat("🛑 إغلاق قسري: DD=%.2f%% >= %.2f%%", GlobalDD, MaxDDPercent);
        CloseEverything();
        return;
    }

    // ── 12. معلومات اللوحة ───────────────────────────────────────
    string adrStat = IsADRExhausted() ? "EXHAUSTED 🛑" : "SAFE 🟢";
    string smcStat = "CLEAR 🟢";
    double smcDist = SMCDistancePips * PipSize;
    if(lastBearOB_Bot > 0 && ask >= (lastBearOB_Bot - smcDist)) smcStat = "NEAR SUPPLY ⚠️";
    if(lastBullOB_Top > 0 && bid <= (lastBullOB_Top + smcDist)) smcStat = "NEAR DEMAND ⚠️";
    double netLots = oldLotsBuy - oldLotsSell;

    // ── 13. تنفيذ الاستراتيجية ───────────────────────────────────
    if(OldGridCount == 0) {
        MaxBasketProfit = 0.0;
        if(ShieldActiveCount > 0 || ShieldPendingCount > 0) {
            CloseAllByMagic(ShieldMagic);
            DeletePendingOrdersByMagic(ShieldMagic);
        }
        ExecuteConstitution(MagicNumber, 0, masterBuySignal, masterSellSignal);

    } else {
        // ── درع الطوارئ (Pending Shield) ─────────────────────────
        if(UsePendingShield && CurrentDD >= EmergencyFreezeDD &&
           ShieldActiveCount == 0 && ShieldPendingCount == 0 &&
           MathAbs(netLots) > 0) {

            m_trade.SetExpertMagicNumber(ShieldMagic);
            double sDist      = PendingShieldDist * PipSize;
            double sl_dist    = Shield_StopLoss_Pips * PipSize;
            double hedgeVol   = NormalizeDouble(MathAbs(netLots), LotDecimals);
            double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) *
                                m_symbol.Point();
            if(sDist < stopsLevel) sDist = stopsLevel + PipSize;

            if(netLots > 0) {
                double openP = NormalizeDouble(m_symbol.Bid() - sDist, _Digits);
                double slP   = (Shield_StopLoss_Pips > 0) ?
                               NormalizeDouble(openP + sl_dist, _Digits) : 0;
                m_trade.SellStop(hedgeVol, openP, _Symbol, slP, 0, 0, 0, "[SHIELD]");
            } else {
                double openP = NormalizeDouble(m_symbol.Ask() + sDist, _Digits);
                double slP   = (Shield_StopLoss_Pips > 0) ?
                               NormalizeDouble(openP - sl_dist, _Digits) : 0;
                m_trade.BuyStop(hedgeVol, openP, _Symbol, slP, 0, 0, 0, "[SHIELD]");
            }
        }

        if(ShieldActiveCount > 0) {
            if(totalFloating >= 0.0) {
                CloseEverything();
                return;
            }
        } else {
            // ── ✅ FIX 3: Basket Trailing — صيغة صحيحة ───────────
            if(UseBasketTrailing) {
                if(OldGridProfit > MaxBasketProfit) MaxBasketProfit = OldGridProfit;
                if(MaxBasketProfit >= BaseTargetUSD) {
                    // ✅ FIX 3: تأمين TrailLockPercent% من الربح الأقصى
                    // مثال: MaxBasketProfit=$10, TrailLockPercent=60%
                    // → أغلق إذا تراجع الربح عن 60% من الذروة ($6)
                    double lockLevel = MaxBasketProfit * (TrailLockPercent / 100.0);
                    if(OldGridProfit <= lockLevel) {
                        PrintFormat("🎯 Basket Trail: إغلاق عند $%.2f (ذروة $%.2f، تأمين %.0f%%)",
                                    OldGridProfit, MaxBasketProfit, TrailLockPercent);
                        CloseAllByMagic(MagicNumber);
                        if(ShieldPendingCount > 0) DeletePendingOrdersByMagic(ShieldMagic);
                        return;
                    }
                }
            } else if(OldGridProfit >= BaseTargetUSD) {
                CloseAllByMagic(MagicNumber);
                if(ShieldPendingCount > 0) DeletePendingOrdersByMagic(ShieldMagic);
                return;
            }
            ExecuteConstitution(MagicNumber, OldGridCount, masterBuySignal, masterSellSignal);
        }
    }

    UpdateDashboard(adrStat, smcStat, netLots);
    IsFirstRun   = false;
    g_InitComplete = true;
}

//====================================================================
void OnTimer() {
    string adrStat = IsADRExhausted() ? "EXHAUSTED 🛑" : "SAFE 🟢";
    string smcStat = "CLEAR 🟢";
    double smcDist = SMCDistancePips * PipSize;

    if(!m_symbol.RefreshRates()) { ChartRedraw(); return; }
    double ask = m_symbol.Ask();
    double bid = m_symbol.Bid();
    if(lastBearOB_Bot > 0 && ask >= (lastBearOB_Bot - smcDist)) smcStat = "NEAR SUPPLY ⚠️";
    if(lastBullOB_Top > 0 && bid <= (lastBullOB_Top + smcDist)) smcStat = "NEAR DEMAND ⚠️";

    double buyLots = 0, sellLots = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!m_position.SelectByIndex(i)) continue;
        if(!IsMainPosition(m_position.Magic())) continue;
        if(!IsSameSymbol(m_position.Symbol(), _Symbol)) continue;
        if(m_position.PositionType() == POSITION_TYPE_BUY) buyLots  += m_position.Volume();
        else                                                sellLots += m_position.Volume();
    }

    UpdateDashboard(adrStat, smcStat, buyLots - sellLots);
    ChartRedraw();
}

//====================================================================
// معالجة أحداث OnTrade (للـ Cascade Protection)
//====================================================================
void OnTrade() {
    // فحص إذا كانت هناك صفقة أُغلقت بخسارة
    if(!UseCascadeProtection) return;

    HistorySelect(TimeCurrent() - 60, TimeCurrent());
    int deals = HistoryDealsTotal();
    for(int i = deals - 1; i >= 0; i--) {
        ulong ticket = HistoryDealGetTicket(i);
        if(ticket == 0) continue;

        long  entry  = (long)HistoryDealGetInteger(ticket, DEAL_ENTRY);
        ulong magic  = (ulong)HistoryDealGetInteger(ticket, DEAL_MAGIC);
        double profit= HistoryDealGetDouble(ticket, DEAL_PROFIT);
        string sym   = HistoryDealGetString(ticket, DEAL_SYMBOL);

        if(entry == DEAL_ENTRY_OUT && IsMainPosition(magic) &&
           IsSameSymbol(sym, _Symbol) && profit < 0) {
            OnPositionLoss();
            break;
        }
    }
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam) {
    if(id == CHARTEVENT_CHART_CHANGE) ChartRedraw();
}
//+------------------------------------------------------------------+
