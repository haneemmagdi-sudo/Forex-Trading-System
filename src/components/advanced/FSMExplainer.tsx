export default function FSMExplainer() {
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-3xl p-8 border border-purple-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🔍 مستشعر البيئة - FSM (Finite State Machine)</h2>
        <p className="text-xl text-purple-200 mb-4">
          محرك ذكي يراقب "نبض السوق" ويصنف البيئة الحالية إلى 4 غرف تشغيلية مختلفة
        </p>
        <div className="bg-black/30 rounded-xl p-4">
          <p className="text-gray-300">
            💡 <strong className="text-white">الفكرة الرئيسية:</strong> بدلاً من معاملة كل الأسواق بنفس الطريقة، 
            يتكيف الإكسبرت تلقائياً مع البيئة الحالية ويغير سلوكه بالكامل!
          </p>
        </div>
      </div>

      {/* FSM States */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* State A */}
        <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-3xl p-8 border border-blue-400/30 hover:border-blue-400/60 transition-all duration-300">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/50">
              <span className="text-4xl font-bold text-white">A</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">التذبذب البطيء</h3>
              <p className="text-blue-400">Low Volatility Range</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-black/30 rounded-xl p-4">
              <h4 className="text-white font-semibold mb-3">📊 التشخيص الخوارزمي:</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• ATR منخفض جداً (تحت 60% من المتوسط)</li>
                <li>• السعر يعبر EMA صعوداً/هبوطاً بدون اتجاه واضح</li>
                <li>• شموع صغيرة ومتقاربة</li>
                <li>• ADX أقل من 20 (سوق عرضي)</li>
              </ul>
            </div>

            <div className="bg-blue-500/20 rounded-xl p-4 border border-blue-400/50">
              <h4 className="text-blue-400 font-semibold mb-3">⚙️ أمر الآلة: "وضع التجميع"</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• <strong className="text-white">Grid Distance:</strong> 15-20 نقطة (قريب جداً)</li>
                <li>• <strong className="text-white">Take Profit:</strong> 0.5 × ATR (أهداف صغيرة)</li>
                <li>• <strong className="text-white">Lot Multiplier:</strong> 1.2 (تبريد خفيف)</li>
                <li>• <strong className="text-white">Strategy:</strong> Scalping + Grid</li>
                <li>• <strong className="text-white">Max Positions:</strong> 10 (كثافة عالية)</li>
              </ul>
            </div>

            <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-400/30">
              <div className="text-yellow-400 font-semibold mb-2">💡 الفلسفة:</div>
              <p className="text-gray-300 text-sm">
                في السوق العرضي، السعر يتحرك ذهاباً وإياباً. نستفيد من هذا بفتح شبكة كثيفة 
                وجني أرباح صغيرة متكررة من كل تذبذب.
              </p>
            </div>
          </div>
        </div>

        {/* State B */}
        <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 rounded-3xl p-8 border border-orange-400/30 hover:border-orange-400/60 transition-all duration-300">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/50">
              <span className="text-4xl font-bold text-white">B</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">التذبذب السريع</h3>
              <p className="text-orange-400">High Volatility Range</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-black/30 rounded-xl p-4">
              <h4 className="text-white font-semibold mb-3">📊 التشخيص الخوارزمي:</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• ATR مرتفع جداً (فوق 140% من المتوسط)</li>
                <li>• شموع طويلة بذيول كبيرة</li>
                <li>• EMA أفقي تقريباً (لا اتجاه)</li>
                <li>• أخبار اقتصادية أو صراع سيولة</li>
              </ul>
            </div>

            <div className="bg-orange-500/20 rounded-xl p-4 border border-orange-400/50">
              <h4 className="text-orange-400 font-semibold mb-3">⚙️ أمر الآلة: "وضع القناص الحذر"</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• <strong className="text-white">Grid Distance:</strong> 60-80 نقطة (واسع جداً)</li>
                <li>• <strong className="text-white">Take Profit:</strong> 2.0 × ATR (أهداف كبيرة)</li>
                <li>• <strong className="text-white">Lot Multiplier:</strong> 1.5 (تبريد متوسط)</li>
                <li>• <strong className="text-white">Strategy:</strong> Wait & Snipe</li>
                <li>• <strong className="text-white">Max Positions:</strong> 5 (كثافة منخفضة)</li>
              </ul>
            </div>

            <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
              <div className="text-red-400 font-semibold mb-2">⚠️ الخطر:</div>
              <p className="text-gray-300 text-sm">
                التقلبات العنيفة قد تسبب انعكاسات حادة. نوسع المسافات لتجنب الوقوع في فخ 
                التذبذبات الكاذبة ونقلل عدد الصفقات.
              </p>
            </div>
          </div>
        </div>

        {/* State C */}
        <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-3xl p-8 border border-emerald-400/30 hover:border-emerald-400/60 transition-all duration-300">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/50">
              <span className="text-4xl font-bold text-white">C</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">الترند البطيء</h3>
              <p className="text-emerald-400">Slow Trend / Creeping</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-black/30 rounded-xl p-4">
              <h4 className="text-white font-semibold mb-3">📊 التشخيص الخوارزمي:</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• زاوية EMA واضحة لكن ليست حادة (15-35 درجة)</li>
                <li>• ATR متوسط (80-120% من المتوسط)</li>
                <li>• قمم وقيعان متدرجة باستمرار</li>
                <li>• ADX بين 20-30 (ترند معتدل)</li>
              </ul>
            </div>

            <div className="bg-emerald-500/20 rounded-xl p-4 border border-emerald-400/50">
              <h4 className="text-emerald-400 font-semibold mb-3">⚙️ أمر الآلة: "وضع المرافقة"</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• <strong className="text-white">Grid Distance:</strong> 30-40 نقطة (متوسط)</li>
                <li>• <strong className="text-white">Take Profit:</strong> 1.5 × ATR</li>
                <li>• <strong className="text-white">Trailing Stop:</strong> مفعّل (0.8 × ATR)</li>
                <li>• <strong className="text-white">Strategy:</strong> Trend Following</li>
                <li>• <strong className="text-white">Grid:</strong> في اتجاه واحد فقط</li>
              </ul>
            </div>

            <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
              <div className="text-emerald-400 font-semibold mb-2">🎯 الاستراتيجية:</div>
              <p className="text-gray-300 text-sm">
                نركب الموجة ونستخدم Trailing Stop لحجز الأرباح تدريجياً. الشبكة تفتح فقط 
                في اتجاه الترند لتعزيز الموقف.
              </p>
            </div>
          </div>
        </div>

        {/* State D */}
        <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-3xl p-8 border border-purple-400/30 hover:border-purple-400/60 transition-all duration-300">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/50 animate-pulse">
              <span className="text-4xl font-bold text-white">D</span>
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">الترند القوي</h3>
              <p className="text-purple-400">Strong Trend / Momentum Burst</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-black/30 rounded-xl p-4">
              <h4 className="text-white font-semibold mb-3">📊 التشخيص الخوارزمي:</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• زاوية EMA حادة جداً (فوق 45 درجة)</li>
                <li>• شموع Heiken Ashi بلون واحد متصل</li>
                <li>• لا ذيول سفلية/علوية (زخم نقي)</li>
                <li>• ADX فوق 35 (ترند قوي جداً)</li>
              </ul>
            </div>

            <div className="bg-purple-500/20 rounded-xl p-4 border border-purple-400/50">
              <h4 className="text-purple-400 font-semibold mb-3">⚙️ أمر الآلة: "وضع الهجوم الصارم"</h4>
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• <strong className="text-white">Direction:</strong> اتجاه واحد فقط (مع الترند)</li>
                <li>• <strong className="text-white">Counter-Trades:</strong> ممنوع تماماً ❌</li>
                <li>• <strong className="text-white">Lot Size:</strong> مضاعف 1.5× (عدواني)</li>
                <li>• <strong className="text-white">Grid:</strong> مُعطّل في العكس، مفعّل مع الاتجاه</li>
                <li>• <strong className="text-white">Veto Power:</strong> نشط (رفض أي إشارة عكسية)</li>
              </ul>
            </div>

            <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-xl p-4 border border-purple-400/30">
              <div className="text-purple-400 font-semibold mb-2">🚀 القوة القصوى:</div>
              <p className="text-gray-300 text-sm">
                في القطار السريع، محاولة البيع في ترند صاعد قوي = انتحار. نمنع تماماً أي 
                صفقات عكسية ونستثمر بقوة في الاتجاه الساحق.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* FSM Detection Code */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>🧮</span>
          خوارزمية الكشف عن الحالة
        </h3>

        <div className="bg-black/50 rounded-2xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
            <code>{`// FSM State Detection Algorithm

enum MarketState {
    STATE_A_LOW_VOLATILITY_RANGE,    // تذبذب بطيء
    STATE_B_HIGH_VOLATILITY_RANGE,   // تذبذب سريع
    STATE_C_SLOW_TREND,              // ترند بطيء
    STATE_D_STRONG_TREND             // ترند قوي
};

MarketState DetectMarketState() {
    // حساب المؤشرات
    double atr_current = iATR(ATR_Period);
    double atr_avg = iMA(atr_values, 20);  // متوسط آخر 20 قراءة
    double atr_ratio = atr_current / atr_avg;
    
    double ema_angle = CalculateEMAAngle(50);  // زاوية EMA
    double adx = iADX(ADX_Period);
    
    int ha_same_color = CountConsecutiveHeikenAshi();
    
    // قرار الحالة
    if (atr_ratio < 0.6 && adx < 20) {
        return STATE_A_LOW_VOLATILITY_RANGE;
    }
    else if (atr_ratio > 1.4 && MathAbs(ema_angle) < 15) {
        return STATE_B_HIGH_VOLATILITY_RANGE;
    }
    else if (ema_angle > 15 && ema_angle < 35 && adx >= 20 && adx < 30) {
        return STATE_C_SLOW_TREND;
    }
    else if (ema_angle >= 35 && adx >= 35 && ha_same_color >= 5) {
        return STATE_D_STRONG_TREND;
    }
    
    return STATE_C_SLOW_TREND; // Default
}

// حساب زاوية EMA
double CalculateEMAAngle(int period) {
    double ema_now = iMA(period, 0);
    double ema_prev = iMA(period, 10);
    double price_change = ema_now - ema_prev;
    double angle = MathArctan(price_change / (10 * _Point)) * 180 / M_PI;
    return angle;
}`}</code>
          </pre>
        </div>
      </div>

      {/* State Transition */}
      <div className="bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>🔄</span>
          انتقالات الحالة (State Transitions)
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-lg font-semibold text-indigo-400 mb-4">📊 مخطط الانتقالات</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">A → B</div>
                <div className="text-gray-400 text-sm">عندما يرتفع ATR فجأة (أخبار)</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">A → C</div>
                <div className="text-gray-400 text-sm">عندما يظهر اتجاه تدريجي</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">C → D</div>
                <div className="text-gray-400 text-sm">عندما يتسارع الترند بقوة</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">D → A</div>
                <div className="text-gray-400 text-sm">بعد استنفاد الزخم والدخول في تماسك</div>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-purple-400 mb-4">⚙️ سلوك الانتقال</h4>
            <div className="bg-black/30 rounded-xl p-4">
              <ul className="space-y-2 text-gray-300 text-sm">
                <li>• <strong className="text-white">فحص كل شمعة:</strong> يتم تقييم الحالة عند إغلاق كل شمعة</li>
                <li>• <strong className="text-white">فترة تأكيد:</strong> يجب بقاء الشروط لـ 3 شموع متتالية</li>
                <li>• <strong className="text-white">إعادة ضبط تلقائي:</strong> عند الانتقال، يتم إعادة حساب جميع المعاملات</li>
                <li>• <strong className="text-white">حماية الصفقات:</strong> الصفقات المفتوحة لا تُغلق فوراً</li>
                <li>• <strong className="text-white">تسجيل:</strong> كل انتقال يُسجل في اللوج للتحليل</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Table */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📈 مقارنة أداء الحالات</h3>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-right py-4 px-4 text-gray-400">الحالة</th>
                <th className="text-right py-4 px-4 text-gray-400">نسبة الربح المتوقعة</th>
                <th className="text-right py-4 px-4 text-gray-400">متوسط الربح/الصفقة</th>
                <th className="text-right py-4 px-4 text-gray-400">المخاطرة</th>
                <th className="text-right py-4 px-4 text-gray-400">عدد الصفقات/اليوم</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800 hover:bg-blue-500/5">
                <td className="py-4 px-4 text-blue-400 font-semibold">A - تذبذب بطيء</td>
                <td className="py-4 px-4 text-white">75-85%</td>
                <td className="py-4 px-4 text-emerald-400">صغير (10-20 نقطة)</td>
                <td className="py-4 px-4 text-yellow-400">منخفضة</td>
                <td className="py-4 px-4 text-white">15-25</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-orange-500/5">
                <td className="py-4 px-4 text-orange-400 font-semibold">B - تذبذب سريع</td>
                <td className="py-4 px-4 text-white">55-65%</td>
                <td className="py-4 px-4 text-emerald-400">كبير (50-100 نقطة)</td>
                <td className="py-4 px-4 text-red-400">عالية</td>
                <td className="py-4 px-4 text-white">2-5</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5">
                <td className="py-4 px-4 text-emerald-400 font-semibold">C - ترند بطيء</td>
                <td className="py-4 px-4 text-white">65-75%</td>
                <td className="py-4 px-4 text-emerald-400">متوسط (30-50 نقطة)</td>
                <td className="py-4 px-4 text-yellow-400">متوسطة</td>
                <td className="py-4 px-4 text-white">8-12</td>
              </tr>
              <tr className="hover:bg-purple-500/5">
                <td className="py-4 px-4 text-purple-400 font-semibold">D - ترند قوي</td>
                <td className="py-4 px-4 text-white">80-90%</td>
                <td className="py-4 px-4 text-emerald-400">كبير جداً (100-200 نقطة)</td>
                <td className="py-4 px-4 text-emerald-400">منخفضة (مع الاتجاه)</td>
                <td className="py-4 px-4 text-white">3-6</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
