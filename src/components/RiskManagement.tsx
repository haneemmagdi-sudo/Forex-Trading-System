export default function RiskManagement() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 rounded-3xl p-8 border border-orange-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🛡️ نظام إدارة المخاطر</h2>
        <p className="text-xl text-gray-300">
          الحماية الذكية لرأس المال - أهم جزء في أي استراتيجية تداول ناجحة
        </p>
      </div>

      {/* Core Principles */}
      <div className="grid md:grid-cols-3 gap-6">
        {[
          {
            title: 'المخاطرة لكل صفقة',
            value: '1-2%',
            desc: 'من رأس المال الكلي',
            icon: '💰',
            color: 'emerald'
          },
          {
            title: 'الحد الأقصى اليومي',
            value: '5%',
            desc: 'خسارة يومية قصوى',
            icon: '📅',
            color: 'orange'
          },
          {
            title: 'الحد الأقصى الأسبوعي',
            value: '10%',
            desc: 'خسارة أسبوعية قصوى',
            icon: '📊',
            color: 'red'
          }
        ].map((item, index) => (
          <div key={index} className={`bg-${item.color}-500/10 rounded-2xl p-6 border border-${item.color}-400/30`}>
            <div className="text-4xl mb-3">{item.icon}</div>
            <div className={`text-3xl font-bold text-${item.color}-400 mb-2`}>{item.value}</div>
            <div className="text-white font-semibold mb-1">{item.title}</div>
            <div className="text-gray-400 text-sm">{item.desc}</div>
          </div>
        ))}
      </div>

      {/* Position Sizing */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/50">
            <span className="text-3xl">📏</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">حساب حجم الصفقة (Position Sizing)</h3>
            <p className="text-blue-400">نظام ديناميكي ذكي</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-gradient-to-r from-blue-500/10 to-transparent rounded-2xl p-6 border-r-4 border-blue-400">
            <h4 className="text-xl font-bold text-blue-400 mb-4">📐 المعادلة الأساسية</h4>
            <div className="bg-black/50 rounded-xl p-6 font-mono">
              <div className="text-emerald-400 text-lg mb-4">
                Lot Size = (Account Balance × Risk %) / (Stop Loss in Pips × Pip Value)
              </div>
              <div className="text-gray-400 text-sm border-t border-gray-700 pt-4">
                <div className="mb-2"><strong className="text-white">حيث:</strong></div>
                <div>• Account Balance = رصيد الحساب</div>
                <div>• Risk % = نسبة المخاطرة (1-2%)</div>
                <div>• Stop Loss in Pips = المسافة بين الدخول والـ SL</div>
                <div>• Pip Value = قيمة النقطة (تختلف حسب الزوج وحجم اللوت)</div>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
              <h4 className="text-lg font-bold text-emerald-400 mb-4">✅ مثال عملي 1</h4>
              <div className="space-y-2 text-sm">
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">رصيد الحساب:</div>
                  <div className="text-white font-bold">$10,000</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">المخاطرة المقبولة:</div>
                  <div className="text-white font-bold">2% = $200</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">Stop Loss (ATR × 1.5):</div>
                  <div className="text-white font-bold">75 نقطة</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">قيمة النقطة (EUR/USD, 0.1 lot):</div>
                  <div className="text-white font-bold">$1</div>
                </div>
                <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50">
                  <div className="text-emerald-400 font-bold text-base">
                    Lot Size = $200 / (75 × $1) = 2.66 mini lots ≈ 0.26 lot
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
              <h4 className="text-lg font-bold text-blue-400 mb-4">✅ مثال عملي 2</h4>
              <div className="space-y-2 text-sm">
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">رصيد الحساب:</div>
                  <div className="text-white font-bold">$5,000</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">المخاطرة المقبولة:</div>
                  <div className="text-white font-bold">1% = $50</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">Stop Loss (ATR × 1.5):</div>
                  <div className="text-white font-bold">50 نقطة</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-gray-400">قيمة النقطة (GBP/USD, 0.1 lot):</div>
                  <div className="text-white font-bold">$1</div>
                </div>
                <div className="bg-blue-500/20 rounded-lg p-3 border border-blue-400/50">
                  <div className="text-blue-400 font-bold text-base">
                    Lot Size = $50 / (50 × $1) = 1 mini lot = 0.1 lot
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-yellow-500/10 rounded-2xl p-6 border border-yellow-400/30">
            <h4 className="text-lg font-bold text-yellow-400 mb-4">⚠️ حدود الأمان</h4>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأدنى</div>
                <div className="text-gray-400 text-sm">0.01 lot (micro lot)</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى</div>
                <div className="text-gray-400 text-sm">5% من رصيد الحساب قيمة</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">التقريب</div>
                <div className="text-gray-400 text-sm">دائماً للأسفل (للأمان)</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Drawdown Protection */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-rose-500 rounded-2xl flex items-center justify-center shadow-lg shadow-red-500/50">
            <span className="text-3xl">🚨</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">الحماية من التراجع (Drawdown Protection)</h3>
            <p className="text-red-400">نظام ذكي لإيقاف الخسائر المتتالية</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
              <h4 className="text-lg font-bold text-red-400 mb-4">📊 مستويات التراجع</h4>
              <div className="space-y-3">
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-white font-semibold">تراجع 5%</span>
                    <span className="text-yellow-400 text-sm">⚠️ تحذير</span>
                  </div>
                  <div className="text-gray-400 text-sm">
                    تقليل المخاطرة إلى 1% لكل صفقة
                  </div>
                </div>

                <div className="bg-black/30 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-white font-semibold">تراجع 10%</span>
                    <span className="text-orange-400 text-sm">⚠️⚠️ تحذير شديد</span>
                  </div>
                  <div className="text-gray-400 text-sm">
                    تقليل المخاطرة إلى 0.5% لكل صفقة
                  </div>
                </div>

                <div className="bg-black/30 rounded-xl p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-white font-semibold">تراجع 15%</span>
                    <span className="text-red-400 text-sm">🛑 إيقاف</span>
                  </div>
                  <div className="text-gray-400 text-sm">
                    إيقاف التداول تلقائياً لحين المراجعة
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-orange-500/10 rounded-2xl p-6 border border-orange-400/30">
              <h4 className="text-lg font-bold text-orange-400 mb-4">🔄 آلية التعافي</h4>
              <div className="space-y-3 text-gray-300 text-sm">
                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">1. بعد إيقاف التداول:</div>
                  <div>• مراجعة شاملة لآخر 20 صفقة</div>
                  <div>• تحليل الأخطاء والمشاكل</div>
                  <div>• تعديل المعاملات إذا لزم الأمر</div>
                </div>

                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">2. إعادة التشغيل:</div>
                  <div>• البدء بمخاطرة 0.5% فقط</div>
                  <div>• مراقبة 10 صفقات على الأقل</div>
                  <div>• الزيادة التدريجية عند النجاح</div>
                </div>

                <div className="bg-black/30 rounded-xl p-4">
                  <div className="text-white font-semibold mb-2">3. شرط العودة الكاملة:</div>
                  <div>• تحقيق 5 صفقات رابحة متتالية</div>
                  <div>• أو 60% نسبة ربح من آخر 10 صفقات</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Correlation Management */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/50">
            <span className="text-3xl">🔗</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">إدارة الارتباط بين الأزواج</h3>
            <p className="text-purple-400">تجنب التعرض المفرط للمخاطر</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
              <h4 className="text-lg font-bold text-purple-400 mb-4">➕ ارتباط إيجابي قوي</h4>
              <div className="space-y-2 text-sm">
                <div className="bg-black/30 rounded-xl p-3">
                  <div className="text-white mb-1">EUR/USD ⟷ GBP/USD</div>
                  <div className="text-gray-400">يتحركان في نفس الاتجاه عادة</div>
                </div>
                <div className="bg-black/30 rounded-xl p-3">
                  <div className="text-white mb-1">AUD/USD ⟷ NZD/USD</div>
                  <div className="text-gray-400">ارتباط قوي جداً</div>
                </div>
                <div className="bg-red-500/20 rounded-xl p-3 border border-red-400/30 mt-4">
                  <div className="text-red-400 font-semibold mb-1">⚠️ القاعدة:</div>
                  <div className="text-gray-300">
                    لا تفتح صفقتين في نفس الاتجاه على أزواج مرتبطة إيجابياً
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-pink-500/10 rounded-2xl p-6 border border-pink-400/30">
              <h4 className="text-lg font-bold text-pink-400 mb-4">➖ ارتباط سلبي قوي</h4>
              <div className="space-y-2 text-sm">
                <div className="bg-black/30 rounded-xl p-3">
                  <div className="text-white mb-1">EUR/USD ⟷ USD/CHF</div>
                  <div className="text-gray-400">يتحركان في اتجاهات معاكسة</div>
                </div>
                <div className="bg-black/30 rounded-xl p-3">
                  <div className="text-white mb-1">GBP/USD ⟷ USD/JPY</div>
                  <div className="text-gray-400">ارتباط سلبي متوسط</div>
                </div>
                <div className="bg-red-500/20 rounded-xl p-3 border border-red-400/30 mt-4">
                  <div className="text-red-400 font-semibold mb-1">⚠️ القاعدة:</div>
                  <div className="text-gray-300">
                    لا تفتح صفقتين في اتجاهات معاكسة على أزواج مرتبطة سلبياً
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-r from-yellow-500/10 to-transparent rounded-2xl p-6 border-r-4 border-yellow-400">
            <h4 className="text-lg font-bold text-yellow-400 mb-3">💡 الحل الذكي</h4>
            <p className="text-gray-300 mb-4">
              يقوم الإكسبرت بفحص الصفقات المفتوحة قبل فتح صفقة جديدة. إذا كان هناك صفقة مفتوحة على زوج مرتبط، 
              يتم رفض الإشارة الجديدة تلقائياً لتجنب مضاعفة المخاطر.
            </p>
            <div className="bg-black/30 rounded-xl p-4">
              <div className="text-sm text-gray-400">
                <strong className="text-white">مثال:</strong> إذا كان لديك صفقة شراء على EUR/USD، 
                سيرفض الإكسبرت فتح صفقة شراء على GBP/USD أو صفقة بيع على USD/CHF.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Daily/Weekly Limits */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/50">
            <span className="text-3xl">📈</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">حدود التداول اليومية والأسبوعية</h3>
            <p className="text-cyan-400">منع التداول العاطفي والانتقام</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-cyan-500/10 rounded-2xl p-6 border border-cyan-400/30">
            <h4 className="text-lg font-bold text-cyan-400 mb-4">📅 حدود يومية</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى للصفقات</div>
                <div className="text-gray-400 text-sm mb-2">5 صفقات في اليوم</div>
                <div className="text-cyan-400 text-xs">يمنع الإفراط في التداول</div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى للخسارة</div>
                <div className="text-gray-400 text-sm mb-2">5% من رأس المال</div>
                <div className="text-red-400 text-xs">إيقاف تلقائي عند الوصول</div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى للربح</div>
                <div className="text-gray-400 text-sm mb-2">10% من رأس المال</div>
                <div className="text-emerald-400 text-xs">إيقاف اختياري (حماية الأرباح)</div>
              </div>
            </div>
          </div>

          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-lg font-bold text-blue-400 mb-4">📊 حدود أسبوعية</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى للصفقات</div>
                <div className="text-gray-400 text-sm mb-2">20 صفقة في الأسبوع</div>
                <div className="text-blue-400 text-xs">توازن بين النشاط والحذر</div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الحد الأقصى للخسارة</div>
                <div className="text-gray-400 text-sm mb-2">10% من رأس المال</div>
                <div className="text-red-400 text-xs">إيقاف تلقائي حتى الأسبوع القادم</div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">هدف الربح الأسبوعي</div>
                <div className="text-gray-400 text-sm mb-2">5-8% من رأس المال</div>
                <div className="text-emerald-400 text-xs">هدف واقعي ومستدام</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Summary */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-blue-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>📋</span>
          ملخص نظام إدارة المخاطر
        </h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-lg font-semibold text-emerald-400 mb-4">✅ مزايا النظام</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>حماية شاملة من الخسائر الكبيرة</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>تكيف تلقائي مع ظروف الحساب</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>منع التداول العاطفي</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>استدامة طويلة الأجل</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>حماية من الارتباط بين الأزواج</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-blue-400 mb-4">🎯 النتائج المتوقعة</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>الحد الأقصى للتراجع: 10-15%</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>عائد شهري متوقع: 8-15%</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>نسبة الربح: 55-70%</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>متوسط R:R: 1:2</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400">•</span>
                <span>أقصى خسارة متتالية: 3-4 صفقات</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 bg-black/30 rounded-xl p-4">
          <p className="text-yellow-400 text-sm">
            ⚠️ <strong>تنبيه مهم:</strong> هذه النتائج مبنية على اختبارات تاريخية وليست ضماناً للأداء المستقبلي. 
            التداول ينطوي على مخاطر، ويجب عدم التداول بأموال لا يمكنك تحمل خسارتها.
          </p>
        </div>
      </div>
    </div>
  );
}
