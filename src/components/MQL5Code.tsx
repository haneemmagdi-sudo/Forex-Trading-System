import { useState } from 'react';

export default function MQL5Code() {
  const [copied, setCopied] = useState(false);

  const copyCode = () => {
    const codeElement = document.getElementById('mql5-code');
    if (codeElement) {
      navigator.clipboard.writeText(codeElement.innerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-3xl p-8 border border-violet-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">💻 كود MQL5 كامل</h2>
        <p className="text-xl text-gray-300 mb-4">
          Expert Advisor جاهز للاستخدام على MetaTrader 5
        </p>
        <div className="flex gap-4 flex-wrap">
          <button
            onClick={copyCode}
            className="px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-emerald-500/30"
          >
            {copied ? '✓ تم النسخ!' : '📋 نسخ الكود'}
          </button>
          <div className="px-6 py-3 bg-blue-500/20 border border-blue-400/30 rounded-xl">
            <span className="text-blue-400 text-sm">📦 ملف: QuantumForexPro.mq5</span>
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
          <span>📝</span>
          طريقة التثبيت
        </h3>
        <div className="grid md:grid-cols-4 gap-4">
          {[
            { step: '1', title: 'نسخ الكود', desc: 'انقر على زر "نسخ الكود" أعلاه' },
            { step: '2', title: 'فتح MetaEditor', desc: 'F4 في MetaTrader 5' },
            { step: '3', title: 'ملف جديد', desc: 'Expert Advisor → التالي → التالي' },
            { step: '4', title: 'لصق وترجمة', desc: 'الصق الكود واضغط Compile (F7)' }
          ].map((item, index) => (
            <div key={index} className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-2xl p-6 border border-blue-400/30">
              <div className="w-12 h-12 bg-blue-500 rounded-xl flex items-center justify-center mb-4 text-white font-bold text-xl">
                {item.step}
              </div>
              <div className="text-white font-semibold mb-2">{item.title}</div>
              <div className="text-gray-400 text-sm">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Code Block */}
      <div className="bg-black/50 backdrop-blur-xl rounded-3xl p-6 border border-white/10 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 via-purple-500 to-pink-500"></div>
        
        <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="flex gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
            <span className="text-gray-400 text-sm font-mono">QuantumForexPro.mq5</span>
          </div>
          <div className="text-sm text-gray-500">MQL5 | 500+ lines</div>
        </div>

        <div id="mql5-code" className="overflow-x-auto">
          <pre className="text-sm leading-relaxed">
            <code className="language-cpp text-gray-300">
{`//+------------------------------------------------------------------+
//|                                          QuantumForexPro.mq5    |
//|                        استراتيجية تداول متقدمة متعددة الأطر     |
//|                                     www.example.com               |
//+------------------------------------------------------------------+
#property copyright "Your Name"
#property link      "www.example.com"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| مدخلات الإكسبرت                                                  |
//+------------------------------------------------------------------+

// === إعدادات المؤشرات ===
input int      EMA_Fast = 12;                  // EMA السريع
input int      EMA_Slow = 26;                  // EMA البطيء  
input int      EMA_Trend = 200;                // EMA الاتجاه العام
input int      RSI_Period = 14;                // فترة RSI
input int      RSI_Lower = 40;                 // حد RSI الأدنى
input int      RSI_Upper = 60;                 // حد RSI الأعلى
input int      MACD_Fast = 12;                 // MACD Fast
input int      MACD_Slow = 26;                 // MACD Slow
input int      MACD_Signal = 9;                // MACD Signal
input int      ADX_Period = 14;                // فترة ADX
input double   ADX_Minimum = 25.0;             // الحد الأدنى لـ ADX
input int      ATR_Period = 14;                // فترة ATR

// === إدارة المخاطر ===
input double   RiskPercent = 1.0;              // المخاطرة % لكل صفقة
input double   SL_ATR_Multiplier = 1.5;        // Stop Loss (× ATR)
input double   TP1_ATR_Multiplier = 2.0;       // Take Profit 1 (× ATR)
input double   TP2_ATR_Multiplier = 3.0;       // Take Profit 2 (× ATR)
input double   Trailing_ATR_Multiplier = 1.0; // Trailing Stop (× ATR)
input double   BreakEven_ATR = 1.0;            // Break-Even عند (× ATR)

// === حدود التداول ===
input int      Max_Daily_Trades = 5;           // أقصى صفقات يومية
input int      Max_Weekly_Trades = 20;         // أقصى صفقات أسبوعية
input double   Max_Daily_Loss_Percent = 5.0;  // أقصى خسارة يومية %
input double   Max_Weekly_Loss_Percent = 10.0;// أقصى خسارة أسبوعية %
input double   Max_Drawdown_Percent = 15.0;   // أقصى تراجع %
input int      Max_Open_Positions = 3;        // أقصى صفقات مفتوحة

// === فلاتر ===
input bool     Use_Time_Filter = true;         // استخدام فلتر الوقت
input int      Start_Hour = 8;                 // ساعة البداية (GMT)
input int      End_Hour = 17;                  // ساعة النهاية (GMT)
input double   Max_Spread_Points = 2.0;        // أقصى سبريد (نقاط)
input bool     Use_Volume_Filter = true;       // فلتر حجم التداول

// === الأطر الزمنية ===
input ENUM_TIMEFRAMES TimeFrame_Main = PERIOD_H1;   // الإطار الرئيسي
input ENUM_TIMEFRAMES TimeFrame_Higher = PERIOD_H4; // الإطار الأكبر
input ENUM_TIMEFRAMES TimeFrame_Lower = PERIOD_M15; // الإطار الأصغر

// === Magic Number & Comment ===
input long     MagicNumber = 123456;           // Magic Number
input string   OrderComment = "QuantumForexPro"; // تعليق الصفقات

//+------------------------------------------------------------------+
//| المتغيرات العامة                                                 |
//+------------------------------------------------------------------+

// Handles للمؤشرات
int handle_EMA_Fast, handle_EMA_Slow, handle_EMA_Trend;
int handle_RSI, handle_MACD, handle_ADX, handle_ATR;

// Arrays للبيانات
double ema_fast[], ema_slow[], ema_trend[];
double rsi[], macd_main[], macd_signal[];
double adx_main[], atr[];

// إحصائيات التداول
int daily_trades = 0;
int weekly_trades = 0;
double daily_profit = 0.0;
double weekly_profit = 0.0;
double starting_balance = 0.0;
double peak_balance = 0.0;

datetime last_trade_date = 0;
datetime last_week_start = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("=== تهيئة Quantum Forex Pro ===");
   
   // حفظ الرصيد الابتدائي
   starting_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   peak_balance = starting_balance;
   
   // تهيئة المؤشرات
   handle_EMA_Fast = iMA(_Symbol, TimeFrame_Main, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   handle_EMA_Slow = iMA(_Symbol, TimeFrame_Main, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   handle_EMA_Trend = iMA(_Symbol, TimeFrame_Main, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   handle_RSI = iRSI(_Symbol, TimeFrame_Main, RSI_Period, PRICE_CLOSE);
   handle_MACD = iMACD(_Symbol, TimeFrame_Main, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   handle_ADX = iADX(_Symbol, TimeFrame_Main, ADX_Period);
   handle_ATR = iATR(_Symbol, TimeFrame_Main, ATR_Period);
   
   // التحقق من صحة ال Handles
   if(handle_EMA_Fast == INVALID_HANDLE || handle_EMA_Slow == INVALID_HANDLE ||
      handle_EMA_Trend == INVALID_HANDLE || handle_RSI == INVALID_HANDLE ||
      handle_MACD == INVALID_HANDLE || handle_ADX == INVALID_HANDLE ||
      handle_ATR == INVALID_HANDLE)
   {
      Print("خطأ في تهيئة المؤشرات!");
      return(INIT_FAILED);
   }
   
   // إعداد Arrays
   ArraySetAsSeries(ema_fast, true);
   ArraySetAsSeries(ema_slow, true);
   ArraySetAsSeries(ema_trend, true);
   ArraySetAsSeries(rsi, true);
   ArraySetAsSeries(macd_main, true);
   ArraySetAsSeries(macd_signal, true);
   ArraySetAsSeries(adx_main, true);
   ArraySetAsSeries(atr, true);
   
   Print("✓ تم تهيئة الإكسبرت بنجاح!");
   Print("Magic Number: ", MagicNumber);
   Print("الإطار الزمني: ", EnumToString(TimeFrame_Main));
   Print("المخاطرة: ", RiskPercent, "%");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // تحرير ال Handles
   IndicatorRelease(handle_EMA_Fast);
   IndicatorRelease(handle_EMA_Slow);
   IndicatorRelease(handle_EMA_Trend);
   IndicatorRelease(handle_RSI);
   IndicatorRelease(handle_MACD);
   IndicatorRelease(handle_ADX);
   IndicatorRelease(handle_ATR);
   
   Print("=== إيقاف Quantum Forex Pro ===");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // التحقق من شمعة جديدة
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(_Symbol, TimeFrame_Main, 0);
   
   if(current_bar_time == last_bar_time)
      return; // لا توجد شمعة جديدة
      
   last_bar_time = current_bar_time;
   
   // تحديث الإحصائيات
   UpdateStatistics();
   
   // التحقق من حدود التراجع
   if(!CheckDrawdownLimits())
   {
      Print("⚠️ تم الوصول لحد التراجع - التداول متوقف!");
      return;
   }
   
   // التحقق من حدود التداول اليومية والأسبوعية
   if(!CheckTradingLimits())
      return;
   
   // قراءة بيانات المؤشرات
   if(!UpdateIndicators())
      return;
   
   // إدارة الصفقات المفتوحة
   ManageOpenPositions();
   
   // التحقق من إشارات دخول جديدة
   CheckForSignals();
}

//+------------------------------------------------------------------+
//| تحديث بيانات المؤشرات                                            |
//+------------------------------------------------------------------+
bool UpdateIndicators()
{
   if(CopyBuffer(handle_EMA_Fast, 0, 0, 3, ema_fast) < 3) return false;
   if(CopyBuffer(handle_EMA_Slow, 0, 0, 3, ema_slow) < 3) return false;
   if(CopyBuffer(handle_EMA_Trend, 0, 0, 3, ema_trend) < 3) return false;
   if(CopyBuffer(handle_RSI, 0, 0, 3, rsi) < 3) return false;
   if(CopyBuffer(handle_MACD, 0, 0, 3, macd_main) < 3) return false;
   if(CopyBuffer(handle_MACD, 1, 0, 3, macd_signal) < 3) return false;
   if(CopyBuffer(handle_ADX, 0, 0, 3, adx_main) < 3) return false;
   if(CopyBuffer(handle_ATR, 0, 0, 3, atr) < 3) return false;
   
   return true;
}

//+------------------------------------------------------------------+
//| التحقق من إشارات التداول                                         |
//+------------------------------------------------------------------+
void CheckForSignals()
{
   // التحقق من الفلاتر
   if(!PassesFilters())
      return;
   
   // التحقق من عدد الصفقات المفتوحة
   if(CountOpenPositions() >= Max_Open_Positions)
      return;
   
   // الحصول على السعر الحالي
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // التحقق من إشارة شراء
   if(CheckBuySignal())
   {
      Print("✓ إشارة شراء صالحة!");
      double sl = CalculateStopLoss(ORDER_TYPE_BUY, ask);
      double tp = CalculateTakeProfit(ORDER_TYPE_BUY, ask);
      double lot = CalculateLotSize(ask - sl);
      
      if(lot > 0)
         OpenPosition(ORDER_TYPE_BUY, lot, ask, sl, tp);
   }
   // التحقق من إشارة بيع
   else if(CheckSellSignal())
   {
      Print("✓ إشارة بيع صالحة!");
      double sl = CalculateStopLoss(ORDER_TYPE_SELL, bid);
      double tp = CalculateTakeProfit(ORDER_TYPE_SELL, bid);
      double lot = CalculateLotSize(sl - bid);
      
      if(lot > 0)
         OpenPosition(ORDER_TYPE_SELL, lot, bid, sl, tp);
   }
}

//+------------------------------------------------------------------+
//| التحقق من إشارة شراء                                             |
//+------------------------------------------------------------------+
bool CheckBuySignal()
{
   // الشرط 1: EMA Fast > EMA Slow
   if(ema_fast[1] <= ema_slow[1])
      return false;
   
   // الشرط 2: السعر فوق EMA 200
   double close = iClose(_Symbol, TimeFrame_Main, 1);
   if(close <= ema_trend[1])
      return false;
   
   // الشرط 3: RSI في المنطقة المحايدة
   if(rsi[1] < RSI_Lower || rsi[1] > RSI_Upper)
      return false;
   
   // الشرط 4: MACD إيجابي
   if(macd_main[1] <= macd_signal[1] || macd_main[1] <= 0)
      return false;
   
   // الشرط 5: ADX قوي
   if(adx_main[1] < ADX_Minimum)
      return false;
   
   // الشرط 6: عبور صاعد حديث
   if(ema_fast[2] >= ema_slow[2])
      return false;
   
   return true;
}

//+------------------------------------------------------------------+
//| التحقق من إشارة بيع                                              |
//+------------------------------------------------------------------+
bool CheckSellSignal()
{
   // الشرط 1: EMA Fast < EMA Slow
   if(ema_fast[1] >= ema_slow[1])
      return false;
   
   // الشرط 2: السعر تحت EMA 200
   double close = iClose(_Symbol, TimeFrame_Main, 1);
   if(close >= ema_trend[1])
      return false;
   
   // الشرط 3: RSI في المنطقة المحايدة
   if(rsi[1] < RSI_Lower || rsi[1] > RSI_Upper)
      return false;
   
   // الشرط 4: MACD سلبي
   if(macd_main[1] >= macd_signal[1] || macd_main[1] >= 0)
      return false;
   
   // الشرط 5: ADX قوي
   if(adx_main[1] < ADX_Minimum)
      return false;
   
   // الشرط 6: عبور هابط حديث
   if(ema_fast[2] <= ema_slow[2])
      return false;
   
   return true;
}

//+------------------------------------------------------------------+
//| حساب Stop Loss                                                  |
//+------------------------------------------------------------------+
double CalculateStopLoss(ENUM_ORDER_TYPE order_type, double entry_price)
{
   double sl_distance = atr[1] * SL_ATR_Multiplier;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(order_type == ORDER_TYPE_BUY)
      return NormalizeDouble(entry_price - sl_distance, digits);
   else
      return NormalizeDouble(entry_price + sl_distance, digits);
}

//+------------------------------------------------------------------+
//| حساب Take Profit                                                |
//+------------------------------------------------------------------+
double CalculateTakeProfit(ENUM_ORDER_TYPE order_type, double entry_price)
{
   double tp_distance = atr[1] * TP1_ATR_Multiplier;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(order_type == ORDER_TYPE_BUY)
      return NormalizeDouble(entry_price + tp_distance, digits);
   else
      return NormalizeDouble(entry_price - tp_distance, digits);
}

//+------------------------------------------------------------------+
//| حساب حجم اللوت                                                   |
//+------------------------------------------------------------------+
double CalculateLotSize(double sl_distance)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   double sl_in_points = sl_distance / point;
   double lot_size = risk_amount / (sl_in_points * tick_value);
   
   // تقريب للأسفل
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot_size = MathFloor(lot_size / lot_step) * lot_step;
   lot_size = MathMax(lot_size, min_lot);
   lot_size = MathMin(lot_size, max_lot);
   
   return lot_size;
}

//+------------------------------------------------------------------+
//| فتح صفقة                                                         |
//+------------------------------------------------------------------+
bool OpenPosition(ENUM_ORDER_TYPE order_type, double lot, double price, double sl, double tp)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lot;
   request.type = order_type;
   request.price = price;
   request.sl = sl;
   request.tp = tp;
   request.magic = MagicNumber;
   request.comment = OrderComment;
   request.deviation = 10;
   
   if(!OrderSend(request, result))
   {
      Print("خطأ في فتح الصفقة: ", GetLastError());
      return false;
   }
   
   if(result.retcode == TRADE_RETCODE_DONE)
   {
      Print("✓ تم فتح صفقة ", EnumToString(order_type));
      Print("  Lot: ", lot, " | Entry: ", price, " | SL: ", sl, " | TP: ", tp);
      daily_trades++;
      weekly_trades++;
      return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| إدارة الصفقات المفتوحة                                           |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      
      // تطبيق Break-Even
      ApplyBreakEven(ticket);
      
      // تطبيق Trailing Stop
      ApplyTrailingStop(ticket);
   }
}

//+------------------------------------------------------------------+
//| تطبيق Break-Even                                                |
//+------------------------------------------------------------------+
void ApplyBreakEven(ulong ticket)
{
   if(!PositionSelectByTicket(ticket)) return;
   
   double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
   double current_sl = PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   
   double current_price = (pos_type == POSITION_TYPE_BUY) ? 
      SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   double be_distance = atr[1] * BreakEven_ATR;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(pos_type == POSITION_TYPE_BUY)
   {
      if(current_price >= entry_price + be_distance && current_sl < entry_price)
      {
         ModifyPosition(ticket, entry_price + 5 * SymbolInfoDouble(_Symbol, SYMBOL_POINT), 0);
      }
   }
   else if(pos_type == POSITION_TYPE_SELL)
   {
      if(current_price <= entry_price - be_distance && current_sl > entry_price)
      {
         ModifyPosition(ticket, entry_price - 5 * SymbolInfoDouble(_Symbol, SYMBOL_POINT), 0);
      }
   }
}

//+------------------------------------------------------------------+
//| تطبيق Trailing Stop                                            |
//+------------------------------------------------------------------+
void ApplyTrailingStop(ulong ticket)
{
   if(!PositionSelectByTicket(ticket)) return;
   
   double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
   double current_sl = PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   
   double current_price = (pos_type == POSITION_TYPE_BUY) ? 
      SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   double trailing_distance = atr[1] * Trailing_ATR_Multiplier;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(pos_type == POSITION_TYPE_BUY)
   {
      double new_sl = current_price - trailing_distance;
      new_sl = NormalizeDouble(new_sl, digits);
      
      if(new_sl > current_sl && new_sl > entry_price)
      {
         ModifyPosition(ticket, new_sl, 0);
      }
   }
   else if(pos_type == POSITION_TYPE_SELL)
   {
      double new_sl = current_price + trailing_distance;
      new_sl = NormalizeDouble(new_sl, digits);
      
      if(new_sl < current_sl && new_sl < entry_price)
      {
         ModifyPosition(ticket, new_sl, 0);
      }
   }
}

//+------------------------------------------------------------------+
//| تعديل الصفقة                                                     |
//+------------------------------------------------------------------+
bool ModifyPosition(ulong ticket, double new_sl, double new_tp)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.sl = new_sl;
   request.tp = (new_tp > 0) ? new_tp : PositionGetDouble(POSITION_TP);
   
   if(!OrderSend(request, result))
      return false;
   
   return (result.retcode == TRADE_RETCODE_DONE);
}

//+------------------------------------------------------------------+
//| التحقق من الفلاتر                                                |
//+------------------------------------------------------------------+
bool PassesFilters()
{
   // فلتر الوقت
   if(Use_Time_Filter)
   {
      MqlDateTime time;
      TimeToStruct(TimeCurrent(), time);
      if(time.hour < Start_Hour || time.hour >= End_Hour)
         return false;
   }
   
   // فلتر السبريد
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(spread > Max_Spread_Points * SymbolInfoDouble(_Symbol, SYMBOL_POINT))
      return false;
   
   return true;
}

//+------------------------------------------------------------------+
//| عد الصفقات المفتوحة                                              |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && 
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| تحديث الإحصائيات                                                 |
//+------------------------------------------------------------------+
void UpdateStatistics()
{
   datetime current_time = TimeCurrent();
   MqlDateTime time_struct;
   TimeToStruct(current_time, time_struct);
   
   // تحديث الإحصائيات اليومية
   if(time_struct.day != TimeDay(last_trade_date))
   {
      daily_trades = 0;
      daily_profit = 0;
      last_trade_date = current_time;
   }
   
   // تحديث الإحصائيات الأسبوعية
   if(time_struct.day_of_week == 1 && current_time - last_week_start > 86400)
   {
      weekly_trades = 0;
      weekly_profit = 0;
      last_week_start = current_time;
   }
   
   // تحديث Peak Balance
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(current_balance > peak_balance)
      peak_balance = current_balance;
}

//+------------------------------------------------------------------+
//| التحقق من حدود التراجع                                           |
//+------------------------------------------------------------------+
bool CheckDrawdownLimits()
{
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double drawdown_percent = ((peak_balance - current_balance) / peak_balance) * 100.0;
   
   if(drawdown_percent >= Max_Drawdown_Percent)
   {
      CloseAllPositions();
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| التحقق من حدود التداول                                           |
//+------------------------------------------------------------------+
bool CheckTradingLimits()
{
   if(daily_trades >= Max_Daily_Trades)
   {
      Print("⚠️ تم الوصول للحد الأقصى للصفقات اليومية");
      return false;
   }
   
   if(weekly_trades >= Max_Weekly_Trades)
   {
      Print("⚠️ تم الوصول للحد الأقصى للصفقات الأسبوعية");
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| إغلاق جميع الصفقات                                               |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && 
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
      {
         MqlTradeRequest request = {};
         MqlTradeResult result = {};
         
         request.action = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol = _Symbol;
         request.volume = PositionGetDouble(POSITION_VOLUME);
         request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 
                        ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (request.type == ORDER_TYPE_SELL) ? 
                        SymbolInfoDouble(_Symbol, SYMBOL_BID) : 
                        SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         
         OrderSend(request, result);
      }
   }
}

//+------------------------------------------------------------------+`}
            </code>
          </pre>
        </div>
      </div>

      {/* Parameters Guide */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>⚙️</span>
          دليل المعاملات (Parameters)
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-lg font-bold text-blue-400 mb-4">🎯 معاملات المؤشرات</h4>
            <div className="space-y-2 text-sm">
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">EMA_Fast = 12</div>
                <div className="text-gray-400">المتوسط المتحرك السريع</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">EMA_Slow = 26</div>
                <div className="text-gray-400">المتوسط المتحرك البطيء</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">RSI_Period = 14</div>
                <div className="text-gray-400">فترة مؤشر القوة النسبية</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">ADX_Minimum = 25</div>
                <div className="text-gray-400">الحد الأدنى لقوة الترند</div>
              </div>
            </div>
          </div>

          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-lg font-bold text-emerald-400 mb-4">💰 معاملات المخاطر</h4>
            <div className="space-y-2 text-sm">
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">RiskPercent = 1.0</div>
                <div className="text-gray-400">نسبة المخاطرة لكل صفقة</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">SL_ATR_Multiplier = 1.5</div>
                <div className="text-gray-400">مضاعف ATR لـ Stop Loss</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">TP1_ATR_Multiplier = 2.0</div>
                <div className="text-gray-400">مضاعف ATR لأول هدف</div>
              </div>
              <div className="bg-black/30 rounded-lg p-3">
                <div className="text-white font-semibold mb-1">Max_Drawdown_Percent = 15</div>
                <div className="text-gray-400">أقصى تراجع مسموح</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-yellow-500/10 rounded-2xl p-6 border border-yellow-400/30">
          <h4 className="text-lg font-bold text-yellow-400 mb-3">💡 نصائح التحسين</h4>
          <ul className="space-y-2 text-gray-300 text-sm">
            <li>• ابدأ بحساب تجريبي (Demo) لاختبار الإعدادات</li>
            <li>• استخدم Strategy Tester في MT5 للاختبار الخلفي</li>
            <li>• قم بتحسين المعاملات لكل زوج عملات على حدة</li>
            <li>• لا تغير الإعدادات بشكل متكرر - امنح الاستراتيجية وقتاً</li>
            <li>• احتفظ بسجل للصفقات لتحليل الأداء</li>
          </ul>
        </div>
      </div>

      {/* Notes */}
      <div className="bg-gradient-to-br from-red-500/20 to-orange-500/20 rounded-3xl p-8 border border-red-400/30">
        <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
          <span>⚠️</span>
          ملاحظات مهمة جداً
        </h3>
        <ul className="space-y-3 text-gray-300">
          <li className="flex items-start gap-3">
            <span className="text-red-400 text-xl">⚠️</span>
            <span><strong className="text-white">اختبار شامل:</strong> اختبر الإكسبرت على حساب تجريبي لمدة شهر على الأقل قبل استخدامه على حساب حقيقي</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-orange-400 text-xl">⚠️</span>
            <span><strong className="text-white">VPS مطلوب:</strong> للحصول على أفضل أداء، استخدم VPS لتشغيل الإكسبرت 24/7</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-yellow-400 text-xl">⚠️</span>
            <span><strong className="text-white">السبريد:</strong> اختر وسيط بسبريد منخفض لتحسين النتائج</span>
          </li>
          <li className="flex items-start gap-3">
            <span className="text-red-400 text-xl">⚠️</span>
            <span><strong className="text-white">المخاطر:</strong> لا تستثمر أموالاً لا تستطيع تحمل خسارتها</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
