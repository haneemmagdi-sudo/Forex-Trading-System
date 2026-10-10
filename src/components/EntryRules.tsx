export default function EntryRules() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">قواعد الدخول والخروج</h2>
        <p className="text-xl text-gray-300">
          نظام دقيق ومُختبر لتحديد نقاط الدخول والخروج المثالية
        </p>
      </div>

      {/* Buy Signal */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-green-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/50">
            <span className="text-3xl">🔼</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">إشارة الشراء (BUY)</h3>
            <p className="text-emerald-400">شروط فتح صفقة شراء</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-xl font-bold text-emerald-400 mb-4">✅ الشروط الإلزامية (يجب توفرها جميعاً)</h4>
            <div className="grid md:grid-cols-2 gap-4">
              {[
                { condition: 'EMA(12) &gt; EMA(26)', desc: 'المتوسط السريع فوق المتوسط البطيء' },
                { condition: 'السعر &gt; EMA(200)', desc: 'السعر فوق الترند طويل الأجل' },
                { condition: 'RSI بين 40-60', desc: 'تجنب التشبع الشرائي' },
                { condition: 'MACD &gt; Signal', desc: 'MACD فوق خط الإشارة' },
                { condition: 'MACD &gt; 0', desc: 'في المنطقة الإيجابية' },
                { condition: 'ADX &gt; 25', desc: 'قوة ترند كافية' }
              ].map((item, index) => (
                <div key={index} className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-mono text-sm mb-2">{item.condition}</div>
                  <div className="text-gray-400 text-sm">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-xl font-bold text-blue-400 mb-4">🎯 شروط تأكيدية إضافية (اختيارية لكن مُحسِّنة)</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-blue-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">تأكيد على إطار H4</div>
                    <div className="text-gray-400 text-sm">نفس الإشارة موجودة على الإطار الزمني الأكبر</div>
                  </div>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-blue-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">حجم التداول متزايد</div>
                    <div className="text-gray-400 text-sm">Volume الحالي أكبر من متوسط آخر 20 شمعة</div>
                  </div>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-blue-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">الشمعة صاعدة قوية</div>
                    <div className="text-gray-400 text-sm">جسم الشمعة &gt; 60% من نطاقها الكلي</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-yellow-500/10 rounded-2xl p-6 border border-yellow-400/30">
            <h4 className="text-xl font-bold text-yellow-400 mb-4">⏱️ توقيت التنفيذ</h4>
            <div className="space-y-3 text-gray-300">
              <div className="flex items-start gap-3">
                <span className="text-yellow-400">1.</span>
                <span>انتظار إغلاق الشمعة الحالية بتوافر جميع الشروط</span>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-yellow-400">2.</span>
                <span>فتح الصفقة عند افتتاح الشمعة الجديدة مباشرة</span>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-yellow-400">3.</span>
                <span>أو الدخول على M15 عند أول pullback بسيط (تحسين السعر)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Sell Signal */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-rose-500 rounded-2xl flex items-center justify-center shadow-lg shadow-red-500/50">
            <span className="text-3xl">🔽</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">إشارة البيع (SELL)</h3>
            <p className="text-red-400">شروط فتح صفقة بيع</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
            <h4 className="text-xl font-bold text-red-400 mb-4">✅ الشروط الإلزامية (يجب توفرها جميعاً)</h4>
            <div className="grid md:grid-cols-2 gap-4">
              {[
                { condition: 'EMA(12) &lt; EMA(26)', desc: 'المتوسط السريع تحت المتوسط البطيء' },
                { condition: 'السعر &lt; EMA(200)', desc: 'السعر تحت الترند طويل الأجل' },
                { condition: 'RSI بين 40-60', desc: 'تجنب التشبع البيعي' },
                { condition: 'MACD &lt; Signal', desc: 'MACD تحت خط الإشارة' },
                { condition: 'MACD &lt; 0', desc: 'في المنطقة السلبية' },
                { condition: 'ADX &gt; 25', desc: 'قوة ترند كافية' }
              ].map((item, index) => (
                <div key={index} className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-mono text-sm mb-2">{item.condition}</div>
                  <div className="text-gray-400 text-sm">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
            <h4 className="text-xl font-bold text-purple-400 mb-4">🎯 شروط تأكيدية إضافية</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-purple-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">تأكيد على إطار H4</div>
                    <div className="text-gray-400 text-sm">نفس الإشارة موجودة على الإطار الزمني الأكبر</div>
                  </div>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-purple-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">حجم التداول متزايد</div>
                    <div className="text-gray-400 text-sm">Volume الحالي أكبر من متوسط آخر 20 شمعة</div>
                  </div>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <span className="text-purple-400 text-lg">•</span>
                  <div>
                    <div className="text-white font-semibold mb-1">الشمعة هابطة قوية</div>
                    <div className="text-gray-400 text-sm">جسم الشمعة &gt; 60% من نطاقها الكلي</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Exit Rules */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-amber-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/50">
            <span className="text-3xl">🚪</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">قواعد الخروج</h3>
            <p className="text-orange-400">متى وكيف نغلق الصفقة</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
              <h4 className="text-lg font-bold text-emerald-400 mb-4">✅ خروج بربح</h4>
              <div className="space-y-3">
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">🎯 Take Profit 1</div>
                  <div className="text-sm text-gray-400 mb-2">عند 2 × ATR</div>
                  <div className="text-sm text-emerald-400">إغلاق 50% من الصفقة</div>
                </div>
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">🎯 Take Profit 2</div>
                  <div className="text-sm text-gray-400 mb-2">عند 3 × ATR</div>
                  <div className="text-sm text-emerald-400">إغلاق 30% من الصفقة</div>
                </div>
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">🎯 Trailing Stop</div>
                  <div className="text-sm text-gray-400 mb-2">للـ 20% المتبقية</div>
                  <div className="text-sm text-emerald-400">يتتبع السعر بمسافة 1 × ATR</div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
              <h4 className="text-lg font-bold text-red-400 mb-4">❌ خروج بخسارة</h4>
              <div className="space-y-3">
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">🛑 Stop Loss</div>
                  <div className="text-sm text-gray-400 mb-2">عند 1.5 × ATR</div>
                  <div className="text-sm text-red-400">من نقطة الدخول</div>
                </div>
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">⚠️ إشارة عكسية</div>
                  <div className="text-sm text-gray-400 mb-2">ظهور إشارة معاكسة قوية</div>
                  <div className="text-sm text-red-400">إغلاق فوري للصفقة</div>
                </div>
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">📉 انهيار الترند</div>
                  <div className="text-sm text-gray-400 mb-2">ADX ينخفض تحت 20</div>
                  <div className="text-sm text-red-400">خروج بأفضل سعر متاح</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-2xl p-6 border border-blue-400/30">
          <h4 className="text-lg font-bold text-blue-400 mb-3">🔄 Break-Even (تعادل)</h4>
          <p className="text-gray-300 mb-4">
            عندما تتحرك الصفقة في صالحك بمقدار 1 × ATR، يتم تحريك Stop Loss تلقائياً إلى نقطة الدخول (Break-even) 
            مع إضافة spread + عمولة صغيرة لضمان عدم الخروج بخسارة.
          </p>
          <div className="bg-black/30 rounded-xl p-4 mt-3">
            <div className="text-sm text-gray-400">
              <strong className="text-white">مثال:</strong> صفقة شراء على EUR/USD بسعر 1.1000
            </div>
            <div className="text-sm text-emerald-400 mt-2">
              • ATR = 50 نقطة<br />
              • عند وصول السعر إلى 1.1050 (ربح 50 نقطة = 1 × ATR)<br />
              • يتحرك SL تلقائياً إلى 1.1005 (نقطة الدخول + 5 نقاط أمان)
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-violet-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg shadow-violet-500/50">
            <span className="text-3xl">🔍</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">فلاتر الإشارات</h3>
            <p className="text-violet-400">تنقية وتحسين جودة الإشارات</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-violet-500/10 rounded-2xl p-6 border border-violet-400/30">
            <h4 className="text-lg font-bold text-violet-400 mb-4">🕐 فلتر الوقت</h4>
            <div className="space-y-3 text-gray-300">
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-white font-semibold">ساعات التداول المفضلة:</span><br />
                8:00 - 17:00 GMT (السوق الأوروبي والأمريكي)
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-red-400 font-semibold">تجنب:</span><br />
                • آخر ساعة قبل إغلاق السوق الأسبوعي<br />
                • أول 30 دقيقة بعد الأخبار الاقتصادية المهمة
              </div>
            </div>
          </div>

          <div className="bg-pink-500/10 rounded-2xl p-6 border border-pink-400/30">
            <h4 className="text-lg font-bold text-pink-400 mb-4">📰 فلتر الأخبار</h4>
            <div className="space-y-3 text-gray-300">
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-white font-semibold">إيقاف التداول قبل:</span><br />
                • أخبار عالية التأثير (High Impact): 30 دقيقة<br />
                • أخبار متوسطة التأثير: 15 دقيقة
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-emerald-400 font-semibold">العودة للتداول:</span><br />
                بعد 15 دقيقة من صدور الخبر واستقرار السوق
              </div>
            </div>
          </div>

          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-lg font-bold text-blue-400 mb-4">📊 فلتر السبريد</h4>
            <div className="space-y-3 text-gray-300">
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-white font-semibold">الحد الأقصى للسبريد:</span><br />
                • EUR/USD, GBP/USD: 2 نقطة<br />
                • USD/JPY: 2 نقطة<br />
                • Gold: 30 سنت
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-sm text-red-400">
                إذا تجاوز السبريد الحد، يتم تجاهل الإشارة
              </div>
            </div>
          </div>

          <div className="bg-teal-500/10 rounded-2xl p-6 border border-teal-400/30">
            <h4 className="text-lg font-bold text-teal-400 mb-4">💰 فلتر عدد الصفقات</h4>
            <div className="space-y-3 text-gray-300">
              <div className="bg-black/30 rounded-xl p-3 text-sm">
                <span className="text-white font-semibold">الحد الأقصى:</span><br />
                • صفقة واحدة لكل زوج عملات<br />
                • 3 صفقات مفتوحة كحد أقصى
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-sm text-yellow-400">
                يمنع الإفراط في التداول والتعرض الزائد للمخاطر
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Example Scenario */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-blue-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>📝</span>
          مثال عملي كامل - صفقة شراء على EUR/USD
        </h3>
        
        <div className="space-y-4">
          <div className="bg-black/30 rounded-2xl p-6">
            <div className="text-emerald-400 font-bold mb-3">📊 الإطار الزمني: H1 | التوقيت: 14:00 GMT</div>
            
            <div className="grid md:grid-cols-2 gap-4 mt-4">
              <div>
                <div className="text-white font-semibold mb-2">✅ الشروط المتحققة:</div>
                <ul className="space-y-1 text-sm text-gray-300">
                  <li>• EMA(12) = 1.1050 &gt; EMA(26) = 1.1030</li>
                  <li>• السعر = 1.1055 &gt; EMA(200) = 1.0980</li>
                  <li>• RSI = 52 (منطقة محايدة)</li>
                  <li>• MACD = 0.0015 &gt; Signal = 0.0010</li>
                  <li>• ADX = 32 (ترند قوي)</li>
                  <li>• ATR = 50 نقطة</li>
                </ul>
              </div>
              
              <div>
                <div className="text-white font-semibold mb-2">🎯 إعدادات الصفقة:</div>
                <ul className="space-y-1 text-sm text-emerald-300">
                  <li>• <strong>Entry:</strong> 1.1055</li>
                  <li>• <strong>Stop Loss:</strong> 1.1055 - (1.5 × 50) = 1.0980</li>
                  <li>• <strong>TP1 (50%):</strong> 1.1055 + (2 × 50) = 1.1155</li>
                  <li>• <strong>TP2 (30%):</strong> 1.1055 + (3 × 50) = 1.1205</li>
                  <li>• <strong>Trailing (20%):</strong> ATR = 50 نقطة</li>
                  <li>• <strong>Break-Even:</strong> عند 1.1105 (ربح 50 نقطة)</li>
                </ul>
              </div>
            </div>

            <div className="mt-6 bg-gradient-to-r from-emerald-500/10 to-transparent rounded-xl p-4 border-r-4 border-emerald-400">
              <div className="text-emerald-400 font-semibold mb-2">💡 النتيجة المتوقعة:</div>
              <div className="text-gray-300 text-sm">
                • Risk = 75 نقاط | Reward = 100-150 نقطة | R:R = 1:2 إلى 1:3<br />
                • مع حجم لوت 0.1: خسارة محتملة = $75 | ربح محتمل = $100-$150
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
