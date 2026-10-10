export default function IndicatorsSection() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-3xl p-8 border border-blue-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">المؤشرات الفنية المستخدمة</h2>
        <p className="text-xl text-gray-300">
          تم اختيار هذه المؤشرات بعناية لتوفير رؤية شاملة للسوق من زوايا مختلفة
        </p>
      </div>

      {/* Indicators Grid */}
      <div className="space-y-6">
        {/* EMA */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/50">
              <span className="text-4xl">📊</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-3">EMA - Exponential Moving Average</h3>
              <p className="text-gray-300 mb-4 leading-relaxed">
                المتوسط المتحرك الأسي يعطي وزناً أكبر للأسعار الحديثة، مما يجعله أكثر حساسية للتغيرات السعرية.
              </p>
              
              <div className="grid md:grid-cols-3 gap-4 mt-6">
                <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                  <div className="text-emerald-400 font-bold mb-2">EMA السريع (12)</div>
                  <p className="text-sm text-gray-400">يتفاعل بسرعة مع تغيرات السوق</p>
                </div>
                <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/30">
                  <div className="text-blue-400 font-bold mb-2">EMA المتوسط (26)</div>
                  <p className="text-sm text-gray-400">يوازن بين السرعة والاستقرار</p>
                </div>
                <div className="bg-violet-500/10 rounded-xl p-4 border border-violet-400/30">
                  <div className="text-violet-400 font-bold mb-2">EMA البطيء (200)</div>
                  <p className="text-sm text-gray-400">يحدد الاتجاه العام طويل الأمد</p>
                </div>
              </div>

              <div className="mt-6 bg-black/30 rounded-xl p-4">
                <div className="text-yellow-400 font-semibold mb-2">💡 كيفية الاستخدام:</div>
                <ul className="text-gray-300 space-y-2 text-sm">
                  <li>• <strong>إشارة شراء:</strong> EMA(12) يعبر EMA(26) للأعلى والسعر فوق EMA(200)</li>
                  <li>• <strong>إشارة بيع:</strong> EMA(12) يعبر EMA(26) للأسفل والسعر تحت EMA(200)</li>
                  <li>• <strong>تأكيد الترند:</strong> جميع EMAs متوازية في نفس الاتجاه</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* RSI */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/50">
              <span className="text-4xl">📉</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-3">RSI - Relative Strength Index</h3>
              <p className="text-gray-300 mb-4 leading-relaxed">
                مؤشر القوة النسبية يقيس قوة وسرعة حركة السعر، ويحدد مناطق التشبع الشرائي والبيعي.
              </p>
              
              <div className="grid md:grid-cols-3 gap-4 mt-6">
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <div className="text-red-400 font-bold mb-2">فوق 70</div>
                  <p className="text-sm text-gray-400">تشبع شرائي - احتمال تصحيح</p>
                </div>
                <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                  <div className="text-emerald-400 font-bold mb-2">بين 40-60</div>
                  <p className="text-sm text-gray-400">منطقة محايدة - الأفضل للدخول</p>
                </div>
                <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/30">
                  <div className="text-blue-400 font-bold mb-2">تحت 30</div>
                  <p className="text-sm text-gray-400">تشبع بيعي - احتمال ارتداد</p>
                </div>
              </div>

              <div className="mt-6 bg-black/30 rounded-xl p-4">
                <div className="text-yellow-400 font-semibold mb-2">⚙️ الإعدادات:</div>
                <div className="grid md:grid-cols-2 gap-4 mt-3">
                  <div className="text-sm">
                    <span className="text-gray-400">الفترة:</span>
                    <span className="text-white font-bold mr-2">14</span>
                  </div>
                  <div className="text-sm">
                    <span className="text-gray-400">المستويات:</span>
                    <span className="text-white font-bold mr-2">30 / 70</span>
                  </div>
                </div>
                <p className="text-gray-300 mt-3 text-sm">
                  ⚠️ <strong>ملاحظة:</strong> نتجنب الدخول في مناطق التشبع لتقليل الإشارات الكاذبة
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* MACD */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-violet-500 to-purple-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-violet-500/50">
              <span className="text-4xl">〰️</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-3">MACD - Moving Average Convergence Divergence</h3>
              <p className="text-gray-300 mb-4 leading-relaxed">
                يُظهر العلاقة بين متوسطين متحركين للسعر، ويساعد في تحديد قوة واتجاه ومدة الترند.
              </p>
              
              <div className="grid md:grid-cols-2 gap-4 mt-6">
                <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                  <div className="text-emerald-400 font-bold mb-2">🔼 إشارة صعودية</div>
                  <ul className="text-sm text-gray-300 space-y-1 mt-3">
                    <li>• MACD يعبر Signal للأعلى</li>
                    <li>• Histogram إيجابي ومتزايد</li>
                    <li>• MACD فوق خط الصفر</li>
                  </ul>
                </div>
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <div className="text-red-400 font-bold mb-2">🔽 إشارة هبوطية</div>
                  <ul className="text-sm text-gray-300 space-y-1 mt-3">
                    <li>• MACD يعبر Signal للأسفل</li>
                    <li>• Histogram سلبي ومتناقص</li>
                    <li>• MACD تحت خط الصفر</li>
                  </ul>
                </div>
              </div>

              <div className="mt-6 bg-black/30 rounded-xl p-4">
                <div className="text-yellow-400 font-semibold mb-2">⚙️ الإعدادات القياسية:</div>
                <div className="grid grid-cols-3 gap-4 mt-3">
                  <div className="text-sm">
                    <div className="text-gray-400">Fast EMA</div>
                    <div className="text-white font-bold text-lg">12</div>
                  </div>
                  <div className="text-sm">
                    <div className="text-gray-400">Slow EMA</div>
                    <div className="text-white font-bold text-lg">26</div>
                  </div>
                  <div className="text-sm">
                    <div className="text-gray-400">Signal</div>
                    <div className="text-white font-bold text-lg">9</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ADX */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-500/50">
              <span className="text-4xl">⚡</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-3">ADX - Average Directional Index</h3>
              <p className="text-gray-300 mb-4 leading-relaxed">
                يقيس قوة الترند بغض النظر عن اتجاهه، مما يساعد في تجنب الدخول في سوق عرضي.
              </p>
              
              <div className="grid md:grid-cols-3 gap-4 mt-6">
                <div className="bg-gray-500/10 rounded-xl p-4 border border-gray-400/30">
                  <div className="text-gray-400 font-bold mb-2">ADX &lt; 25</div>
                  <p className="text-sm text-gray-400">سوق عرضي - تجنب التداول</p>
                </div>
                <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                  <div className="text-emerald-400 font-bold mb-2">ADX 25-50</div>
                  <p className="text-sm text-gray-400">ترند قوي - أفضل بيئة</p>
                </div>
                <div className="bg-orange-500/10 rounded-xl p-4 border border-orange-400/30">
                  <div className="text-orange-400 font-bold mb-2">ADX &gt; 50</div>
                  <p className="text-sm text-gray-400">ترند قوي جداً - حذر من الانعكاس</p>
                </div>
              </div>

              <div className="mt-6 bg-black/30 rounded-xl p-4">
                <div className="text-yellow-400 font-semibold mb-2">🎯 دور ADX في الاستراتيجية:</div>
                <ul className="text-gray-300 space-y-2 text-sm mt-3">
                  <li>• <strong>فلتر رئيسي:</strong> نتداول فقط عندما ADX &gt; 25</li>
                  <li>• <strong>تأكيد القوة:</strong> ADX المتزايد يعزز إشارة الدخول</li>
                  <li>• <strong>تحذير الخروج:</strong> انخفاض ADX قد يشير لضعف الترند</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* ATR */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-pink-500 to-rose-500 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-pink-500/50">
              <span className="text-4xl">📏</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-3">ATR - Average True Range</h3>
              <p className="text-gray-300 mb-4 leading-relaxed">
                يقيس تقلبات السوق ويستخدم لحساب مستويات Stop Loss و Take Profit الديناميكية.
              </p>
              
              <div className="grid md:grid-cols-2 gap-4 mt-6">
                <div className="bg-pink-500/10 rounded-xl p-4 border border-pink-400/30">
                  <div className="text-pink-400 font-bold mb-2">📉 ATR منخفض</div>
                  <ul className="text-sm text-gray-300 space-y-1 mt-3">
                    <li>• تقلبات قليلة</li>
                    <li>• أهداف ربح أصغر</li>
                    <li>• Stop Loss أضيق</li>
                  </ul>
                </div>
                <div className="bg-rose-500/10 rounded-xl p-4 border border-rose-400/30">
                  <div className="text-rose-400 font-bold mb-2">📈 ATR مرتفع</div>
                  <ul className="text-sm text-gray-300 space-y-1 mt-3">
                    <li>• تقلبات عالية</li>
                    <li>• أهداف ربح أكبر</li>
                    <li>• Stop Loss أوسع</li>
                  </ul>
                </div>
              </div>

              <div className="mt-6 bg-black/30 rounded-xl p-4">
                <div className="text-yellow-400 font-semibold mb-2">💡 الاستخدامات في الاستراتيجية:</div>
                <ul className="text-gray-300 space-y-2 text-sm mt-3">
                  <li>• <strong>Stop Loss:</strong> 1.5 × ATR من نقطة الدخول</li>
                  <li>• <strong>Take Profit:</strong> 3 × ATR (نسبة 1:2)</li>
                  <li>• <strong>حجم اللوت:</strong> يتناسب عكسياً مع ATR (أمان أكبر)</li>
                  <li>• <strong>Trailing Stop:</strong> يتحرك بمقدار 0.5 × ATR</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
          <span>🎓</span>
          خلاصة نظام المؤشرات
        </h3>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-lg font-semibold text-yellow-400 mb-3">مؤشرات الاتجاه (Trend)</h4>
            <ul className="space-y-2 text-gray-300">
              <li>• EMA - تحديد الاتجاه ونقاط الدخول</li>
              <li>• MACD - تأكيد قوة الاتجاه</li>
              <li>• ADX - قياس قوة الترند</li>
            </ul>
          </div>
          <div>
            <h4 className="text-lg font-semibold text-orange-400 mb-3">مؤشرات الزخم والتقلب</h4>
            <ul className="space-y-2 text-gray-300">
              <li>• RSI - تجنب التشبع وتأكيد الإشارات</li>
              <li>• ATR - إدارة المخاطر الديناميكية</li>
            </ul>
          </div>
        </div>
        <div className="mt-6 bg-black/30 rounded-xl p-4">
          <p className="text-gray-300 text-sm">
            💡 <strong className="text-white">ملاحظة مهمة:</strong> يجب توافق جميع المؤشرات للحصول على إشارة قوية. 
            الإشارة المثالية هي التي تؤكدها جميع المؤشرات في نفس الوقت على الأطر الزمنية المختلفة.
          </p>
        </div>
      </div>
    </div>
  );
}
