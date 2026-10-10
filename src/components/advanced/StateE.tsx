export default function StateE() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-red-500/20 to-orange-500/20 rounded-3xl p-8 border border-red-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🚨 State E - News/Event Mode (الحالة الخامسة)</h2>
        <p className="text-xl text-red-200">
          وضع خاص للأخبار الاقتصادية المهمة - حماية قصوى من التقلبات العنيفة
        </p>
      </div>

      {/* Detection */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">🔍 كيف يتم الكشف؟</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
            <h4 className="text-red-400 font-semibold mb-4">📰 التشخيص التلقائي</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>• ATR يرتفع فجأة بنسبة +200% في 5 دقائق</li>
              <li>• Spread يتضاعف (من 2 إلى 10+ نقاط)</li>
              <li>• شموع طويلة جداً متتالية بذيول كبيرة</li>
              <li>• حجم التداول أعلى من 300% من المتوسط</li>
            </ul>
          </div>

          <div className="bg-orange-500/10 rounded-2xl p-6 border border-orange-400/30">
            <h4 className="text-orange-400 font-semibold mb-4">📅 Calendar Integration</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>• الاتصال بـ ForexFactory API</li>
              <li>• قراءة الأخبار عالية التأثير (High Impact)</li>
              <li>• التفعيل التلقائي قبل 15 دقيقة</li>
              <li>• العودة للوضع الطبيعي بعد 30 دقيقة</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="bg-gradient-to-br from-yellow-500/20 to-red-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">⚙️ إجراءات State E</h3>
        
        <div className="space-y-4">
          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-yellow-400 font-bold text-lg mb-4">🛑 الإجراءات الوقائية (قبل الخبر)</h4>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-red-500/10 rounded-lg p-4 border border-red-400/30">
                <div className="text-white font-semibold mb-2">1. إغلاق الصفقات الضعيفة</div>
                <p className="text-gray-400 text-sm">أي صفقة في خسارة &lt; 0.5 × ATR يتم إغلاقها</p>
              </div>
              <div className="bg-red-500/10 rounded-lg p-4 border border-red-400/30">
                <div className="text-white font-semibold mb-2">2. تشديد SL</div>
                <p className="text-gray-400 text-sm">تحريك SL لأقرب نقطة آمنة</p>
              </div>
              <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-400/30">
                <div className="text-white font-semibold mb-2">3. إيقاف فتح صفقات جديدة</div>
                <p className="text-gray-400 text-sm">حتى لو صوّت المجلس بالإجماع</p>
              </div>
              <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-400/30">
                <div className="text-white font-semibold mb-2">4. إيقاف Grid تماماً</div>
                <p className="text-gray-400 text-sm">لا عقود شبكة جديدة</p>
              </div>
            </div>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-emerald-400 font-bold text-lg mb-4">✅ الإجراءات البديلة (اختيارية)</h4>
            <div className="bg-emerald-500/10 rounded-lg p-4 border border-emerald-400/30">
              <div className="text-white font-semibold mb-2">وضع "Breakout Hunter"</div>
              <p className="text-gray-400 text-sm mb-3">
                للمحترفين فقط: محاولة الاستفادة من الاختراق بعد الخبر مباشرة
              </p>
              <ul className="text-gray-300 text-sm space-y-1">
                <li>• انتظار 2 دقيقة بعد صدور الخبر</li>
                <li>• رصد اتجاه الاختراق (شموع كبيرة متتالية)</li>
                <li>• دخول سريع مع SL ضيق جداً (20 نقطة)</li>
                <li>• TP عدواني (2-3 × SL)</li>
                <li>• خروج فوري عند أي تذبذب عكسي</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Code */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود State E</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
<code>{`enum MarketState {
    STATE_A_LOW_VOLATILITY_RANGE,
    STATE_B_HIGH_VOLATILITY_RANGE,
    STATE_C_SLOW_TREND,
    STATE_D_STRONG_TREND,
    STATE_E_NEWS_EVENT  // جديد!
};

struct NewsEvent {
    datetime time;
    string currency;
    string impact;  // "High", "Medium", "Low"
    string title;
};

NewsEvent upcoming_news[];
bool news_mode_active = false;
datetime news_mode_start = 0;

// فحص الأخبار القادمة
void CheckUpcomingNews() {
    datetime current_time = TimeCurrent();
    
    for(int i = 0; i < ArraySize(upcoming_news); i++) {
        NewsEvent news = upcoming_news[i];
        
        // إذا كان الخبر خلال 15 دقيقة
        int minutes_to_news = (int)((news.time - current_time) / 60);
        
        if(minutes_to_news > 0 && minutes_to_news <= 15 && news.impact == "High") {
            ActivateStateE("Upcoming News: " + news.title);
            return;
        }
    }
}

// كشف تلقائي للتقلبات المفاجئة
bool DetectSuddenVolatility() {
    double atr_current = iATR(14, 0);
    double atr_5min_ago = iATR(14, 5);
    double atr_ratio = atr_current / atr_5min_ago;
    
    double spread_current = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
    double spread_avg = GetAverageSpread(20);
    double spread_ratio = spread_current / spread_avg;
    
    // إذا ارتفع ATR بأكثر من 200% أو Spread تضاعف
    if(atr_ratio > 2.0 || spread_ratio > 2.5) {
        return true;
    }
    
    return false;
}

// تفعيل State E
void ActivateStateE(string reason) {
    Print("🚨 تفعيل State E: ", reason);
    
    current_state = STATE_E_NEWS_EVENT;
    news_mode_active = true;
    news_mode_start = TimeCurrent();
    
    // تنفيذ الإجراءات الوقائية
    CloseWeakPositions();
    TightenStopLosses();
    DisableNewTrades();
    DisableGrid();
    
    // إرسال تنبيه
    SendTelegramAlert("⚠️ State E نشط: " + reason);
}

// إغلاق الصفقات الضعيفة
void CloseWeakPositions() {
    double atr = iATR(14, 0);
    
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        
        double profit = PositionGetDouble(POSITION_PROFIT);
        double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
        
        // إذا كانت الصفقة في خسارة صغيرة
        if(profit < 0 && MathAbs(profit) < (atr * 0.5 * PositionGetDouble(POSITION_VOLUME))) {
            ClosePosition(ticket);
            Print("أغلقت صفقة ضعيفة قبل الخبر: ", ticket);
        }
    }
}

// التحقق من انتهاء State E
void CheckStateE_Exit() {
    if(!news_mode_active) return;
    
    datetime current_time = TimeCurrent();
    int minutes_elapsed = (int)((current_time - news_mode_start) / 60);
    
    // الخروج بعد 30 دقيقة أو عندما يستقر السوق
    if(minutes_elapsed > 30 || !DetectSuddenVolatility()) {
        Print("✅ الخروج من State E - العودة للوضع الطبيعي");
        news_mode_active = false;
        
        // إعادة تقييم FSM State
        current_state = DetectMarketState();
        SendTelegramAlert("✅ State E منتهي - الآن في: " + EnumToString(current_state));
    }
}

// في OnTick()
void OnTick() {
    CheckUpcomingNews();  // فحص الأخبار القادمة
    
    if(DetectSuddenVolatility() && !news_mode_active) {
        ActivateStateE("Sudden Volatility Detected");
    }
    
    if(news_mode_active) {
        CheckStateE_Exit();
        return;  // لا تفعل شيء آخر في State E
    }
    
    // الكود العادي...
}`}</code>
          </pre>
        </div>
      </div>

      {/* News Calendar Integration */}
      <div className="bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-3xl p-8 border border-blue-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">📅 دمج تقويم الأخبار (News Calendar API)</h3>
        
        <div className="space-y-4">
          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-blue-400 font-semibold mb-3">🔗 API Options</h4>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-400/30">
                <div className="text-white font-semibold mb-2">ForexFactory</div>
                <p className="text-gray-400 text-xs">Calendar scraping</p>
                <p className="text-emerald-400 text-xs mt-2">✓ مجاني</p>
              </div>
              <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-400/30">
                <div className="text-white font-semibold mb-2">Investing.com</div>
                <p className="text-gray-400 text-xs">Economic Calendar API</p>
                <p className="text-yellow-400 text-xs mt-2">$ مدفوع</p>
              </div>
              <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-400/30">
                <div className="text-white font-semibold mb-2">TradingEconomics</div>
                <p className="text-gray-400 text-xs">Professional API</p>
                <p className="text-yellow-400 text-xs mt-2">$$ مدفوع</p>
              </div>
            </div>
          </div>

          <div className="bg-yellow-500/10 rounded-xl p-6 border border-yellow-400/30">
            <h4 className="text-yellow-400 font-semibold mb-3">💡 الحل الموصى به</h4>
            <p className="text-gray-300 text-sm mb-3">
              استخدام Python Script يعمل على VPS لجلب الأخبار كل ساعة وحفظها في ملف CSV، 
              ثم قراءة الملف من MQL5
            </p>
            <div className="bg-black/30 rounded-lg p-4 mt-3">
              <code className="text-xs text-gray-400">
                news_calendar.csv:<br/>
                2024-01-15 14:30,USD,High,Non-Farm Payrolls<br/>
                2024-01-15 16:00,EUR,Medium,ECB Speech<br/>
                ...
              </code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
