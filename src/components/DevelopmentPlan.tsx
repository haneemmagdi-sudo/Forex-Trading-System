export default function DevelopmentPlan() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-3xl p-8 border border-purple-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🚀 خطة التطوير المستقبلية</h2>
        <p className="text-xl text-gray-300">
          تحويل الاستراتيجية من جيدة إلى استثنائية - خارطة طريق التحسين والتطوير
        </p>
      </div>

      {/* Phase 1 */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/50">
            <span className="text-3xl">1️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">المرحلة الأولى - التحسينات الأساسية</h3>
            <p className="text-emerald-400">الأسابيع 1-4</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-lg font-bold text-emerald-400 mb-4">📊 تحسين المؤشرات</h4>
            <ul className="space-y-3 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">إضافة Stochastic Oscillator</div>
                  <div className="text-gray-400 text-xs mt-1">لتحسين توقيت الدخول في الأطر الصغيرة</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Bollinger Bands</div>
                  <div className="text-gray-400 text-xs mt-1">لقياس التقلبات وتحديد نقاط الانعكاس</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Volume Analysis</div>
                  <div className="text-gray-400 text-xs mt-1">تحليل أعمق لحجم التداول لتأكيد الإشارات</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Ichimoku Cloud</div>
                  <div className="text-gray-400 text-xs mt-1">للحصول على رؤية شاملة للاتجاه</div>
                </div>
              </li>
            </ul>
          </div>

          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-lg font-bold text-blue-400 mb-4">🎯 تحسين قواعد الدخول</h4>
            <ul className="space-y-3 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Pattern Recognition</div>
                  <div className="text-gray-400 text-xs mt-1">التعرف على أنماط الشموع اليابانية (Candlestick Patterns)</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Support & Resistance</div>
                  <div className="text-gray-400 text-xs mt-1">تحديد المستويات الرئيسية تلقائياً</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Fibonacci Levels</div>
                  <div className="text-gray-400 text-xs mt-1">استخدام مستويات فيبوناتشي لتحديد الأهداف</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">▸</span>
                <div>
                  <div className="text-white font-semibold">Price Action</div>
                  <div className="text-gray-400 text-xs mt-1">تحليل حركة السعر لتأكيد الإشارات</div>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 bg-gradient-to-r from-emerald-500/10 to-transparent rounded-2xl p-6 border-r-4 border-emerald-400">
          <h4 className="text-lg font-bold text-emerald-400 mb-3">🎓 التعلم المطلوب</h4>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="text-sm">
              <div className="text-white font-semibold mb-2">📚 الموارد</div>
              <ul className="text-gray-400 space-y-1 text-xs">
                <li>• كتب التحليل الفني</li>
                <li>• دورات MQL5</li>
                <li>• منتديات التداول</li>
              </ul>
            </div>
            <div className="text-sm">
              <div className="text-white font-semibold mb-2">⏱️ الوقت المتوقع</div>
              <div className="text-gray-400 text-xs">20-30 ساعة دراسة + 40 ساعة برمجة واختبار</div>
            </div>
            <div className="text-sm">
              <div className="text-white font-semibold mb-2">📈 التحسين المتوقع</div>
              <div className="text-emerald-400 text-xs">زيادة نسبة الربح بـ 5-10%</div>
            </div>
          </div>
        </div>
      </div>

      {/* Phase 2 */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/50">
            <span className="text-3xl">2️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">المرحلة الثانية - الذكاء الاصطناعي</h3>
            <p className="text-blue-400">الأسابيع 5-8</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-gradient-to-r from-blue-500/10 to-transparent rounded-2xl p-6 border-r-4 border-blue-400">
            <h4 className="text-xl font-bold text-blue-400 mb-4">🤖 دمج Machine Learning</h4>
            <p className="text-gray-300 mb-4">
              استخدام تقنيات التعلم الآلي لتحسين دقة التنبؤات وتكيف الاستراتيجية مع ظروف السوق المتغيرة
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <h5 className="text-white font-semibold mb-3">📊 Predictive Models</h5>
                <ul className="space-y-2 text-sm text-gray-400">
                  <li>• <strong className="text-white">LSTM Neural Networks:</strong> للتنبؤ بحركة السعر</li>
                  <li>• <strong className="text-white">Random Forest:</strong> لتصنيف جودة الإشارات</li>
                  <li>• <strong className="text-white">Gradient Boosting:</strong> لتحسين نقاط الدخول</li>
                </ul>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <h5 className="text-white font-semibold mb-3">🎯 Adaptive Parameters</h5>
                <ul className="space-y-2 text-sm text-gray-400">
                  <li>• <strong className="text-white">Dynamic Optimization:</strong> تحسين المعاملات تلقائياً</li>
                  <li>• <strong className="text-white">Market Regime Detection:</strong> التعرف على حالة السوق</li>
                  <li>• <strong className="text-white">Self-Learning:</strong> التعلم من الصفقات السابقة</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-purple-500/10 rounded-2xl p-5 border border-purple-400/30">
              <div className="text-2xl mb-3">🧠</div>
              <h5 className="text-white font-semibold mb-2">Sentiment Analysis</h5>
              <p className="text-gray-400 text-sm">تحليل المشاعر من أخبار السوق ومواقع التواصل</p>
            </div>

            <div className="bg-pink-500/10 rounded-2xl p-5 border border-pink-400/30">
              <div className="text-2xl mb-3">📰</div>
              <h5 className="text-white font-semibold mb-2">News Impact</h5>
              <p className="text-gray-400 text-sm">تقييم تأثير الأخبار الاقتصادية تلقائياً</p>
            </div>

            <div className="bg-indigo-500/10 rounded-2xl p-5 border border-indigo-400/30">
              <div className="text-2xl mb-3">🔄</div>
              <h5 className="text-white font-semibold mb-2">Reinforcement Learning</h5>
              <p className="text-gray-400 text-sm">تحسين مستمر من خلال التجربة والخطأ</p>
            </div>
          </div>

          <div className="bg-yellow-500/10 rounded-2xl p-6 border border-yellow-400/30">
            <h4 className="text-lg font-bold text-yellow-400 mb-3">🛠️ الأدوات المطلوبة</h4>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-white font-semibold mb-2">البرمجة:</div>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• Python (TensorFlow, PyTorch, Scikit-learn)</li>
                  <li>• MQL5 + Python Integration</li>
                  <li>• REST API للتواصل بين MT5 و Python</li>
                </ul>
              </div>
              <div>
                <div className="text-white font-semibold mb-2">البيانات:</div>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• بيانات تاريخية عالية الجودة (5-10 سنوات)</li>
                  <li>• News Feeds API</li>
                  <li>• Social Media Analytics</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Phase 3 */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/50">
            <span className="text-3xl">3️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">المرحلة الثالثة - التنويع والتوسع</h3>
            <p className="text-orange-400">الأسابيع 9-12</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-orange-500/10 rounded-2xl p-6 border border-orange-400/30">
            <h4 className="text-lg font-bold text-orange-400 mb-4">🌍 أسواق متعددة</h4>
            <ul className="space-y-3 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-orange-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Major Forex Pairs</div>
                  <div className="text-gray-400 text-xs mt-1">EUR/USD, GBP/USD, USD/JPY, AUD/USD</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-orange-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Cross Pairs</div>
                  <div className="text-gray-400 text-xs mt-1">EUR/GBP, EUR/JPY, GBP/JPY</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-orange-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Commodities</div>
                  <div className="text-gray-400 text-xs mt-1">Gold (XAU/USD), Oil, Silver</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-orange-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Indices</div>
                  <div className="text-gray-400 text-xs mt-1">S&P 500, DAX, FTSE 100</div>
                </div>
              </li>
            </ul>
          </div>

          <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
            <h4 className="text-lg font-bold text-red-400 mb-4">⏰ أطر زمنية متعددة</h4>
            <ul className="space-y-3 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Scalping (M1, M5)</div>
                  <div className="text-gray-400 text-xs mt-1">للمتداولين النشطين - صفقات سريعة</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Intraday (M15, M30, H1)</div>
                  <div className="text-gray-400 text-xs mt-1">الاستراتيجية الحالية - متوازن</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Swing Trading (H4, D1)</div>
                  <div className="text-gray-400 text-xs mt-1">للتداول طويل الأجل - أقل ضغط</div>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-1">✓</span>
                <div>
                  <div className="text-white font-semibold">Position Trading (W1, MN1)</div>
                  <div className="text-gray-400 text-xs mt-1">استثمارات طويلة المدى</div>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 bg-gradient-to-r from-purple-500/10 to-transparent rounded-2xl p-6 border-r-4 border-purple-400">
          <h4 className="text-lg font-bold text-purple-400 mb-4">🎯 Portfolio Management</h4>
          <p className="text-gray-300 mb-4">
            إنشاء محفظة متنوعة من الاستراتيجيات تعمل على أصول مختلفة وأطر زمنية متعددة
          </p>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-black/30 rounded-xl p-4">
              <div className="text-purple-400 font-semibold mb-2">توزيع المخاطر</div>
              <div className="text-gray-400 text-sm">لا أكثر من 30% من رأس المال في استراتيجية واحدة</div>
            </div>
            <div className="bg-black/30 rounded-xl p-4">
              <div className="text-purple-400 font-semibold mb-2">الارتباط</div>
              <div className="text-gray-400 text-sm">اختيار أصول وأطر زمنية ذات ارتباط منخفض</div>
            </div>
            <div className="bg-black/30 rounded-xl p-4">
              <div className="text-purple-400 font-semibold mb-2">إعادة التوازن</div>
              <div className="text-gray-400 text-sm">مراجعة شهرية وتعديل التوزيع</div>
            </div>
          </div>
        </div>
      </div>

      {/* Phase 4 */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-pink-500 to-rose-500 rounded-2xl flex items-center justify-center shadow-lg shadow-pink-500/50">
            <span className="text-3xl">4️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">المرحلة الرابعة - الأتمتة الكاملة</h3>
            <p className="text-pink-400">الأسابيع 13-16</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-pink-500/10 rounded-2xl p-6 border border-pink-400/30">
              <h4 className="text-lg font-bold text-pink-400 mb-4">🖥️ Trading Infrastructure</h4>
              <ul className="space-y-2 text-sm text-gray-300">
                <li>• <strong className="text-white">VPS Redundancy:</strong> خوادم احتياطية متعددة</li>
                <li>• <strong className="text-white">Auto Restart:</strong> إعادة تشغيل تلقائي عند الأعطال</li>
                <li>• <strong className="text-white">Monitoring System:</strong> مراقبة 24/7 للأداء</li>
                <li>• <strong className="text-white">Alert System:</strong> إشعارات فورية للأحداث المهمة</li>
                <li>• <strong className="text-white">Backup Strategy:</strong> نسخ احتياطي يومي</li>
              </ul>
            </div>

            <div className="bg-rose-500/10 rounded-2xl p-6 border border-rose-400/30">
              <h4 className="text-lg font-bold text-rose-400 mb-4">📱 Mobile Integration</h4>
              <ul className="space-y-2 text-sm text-gray-300">
                <li>• <strong className="text-white">Mobile App:</strong> تطبيق للمراقبة والتحكم</li>
                <li>• <strong className="text-white">Push Notifications:</strong> تنبيهات لكل صفقة</li>
                <li>• <strong className="text-white">Remote Control:</strong> إيقاف/تشغيل عن بُعد</li>
                <li>• <strong className="text-white">Dashboard:</strong> لوحة تحكم تفاعلية</li>
                <li>• <strong className="text-white">Telegram Bot:</strong> بوت تليجرام للإشعارات</li>
              </ul>
            </div>
          </div>

          <div className="bg-gradient-to-r from-blue-500/10 to-transparent rounded-2xl p-6 border-r-4 border-blue-400">
            <h4 className="text-lg font-bold text-blue-400 mb-4">📊 Advanced Analytics</h4>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-blue-400 font-semibold mb-2">Real-time Statistics</div>
                <ul className="text-gray-400 text-xs space-y-1">
                  <li>• Win Rate بالوقت الفعلي</li>
                  <li>• Average Profit/Loss</li>
                  <li>• Sharpe Ratio</li>
                  <li>• Maximum Drawdown</li>
                </ul>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-blue-400 font-semibold mb-2">Performance Tracking</div>
                <ul className="text-gray-400 text-xs space-y-1">
                  <li>• رسوم بيانية تفاعلية</li>
                  <li>• مقارنة الأداء</li>
                  <li>• تقارير شهرية</li>
                  <li>• تحليل العوائد</li>
                </ul>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-blue-400 font-semibold mb-2">Risk Monitoring</div>
                <ul className="text-gray-400 text-xs space-y-1">
                  <li>• تتبع التعرض للمخاطر</li>
                  <li>• تحذيرات مبكرة</li>
                  <li>• تحليل الارتباط</li>
                  <li>• Stress Testing</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Features */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>⭐</span>
          ميزات متقدمة للمستقبل
        </h3>

        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              title: 'Copy Trading',
              desc: 'السماح للآخرين بنسخ صفقاتك',
              icon: '👥',
              features: ['Social Trading Platform', 'Performance Leaderboard', 'Revenue Sharing']
            },
            {
              title: 'Basket Trading',
              desc: 'فتح سلة من الصفقات المترابطة',
              icon: '🧺',
              features: ['Correlation Analysis', 'Hedging Strategies', 'Multi-Pair Management']
            },
            {
              title: 'Grid Trading',
              desc: 'استراتيجية الشبكة للأسواق العرضية',
              icon: '📐',
              features: ['Dynamic Grid Levels', 'Martingale Option', 'Recovery Mode']
            },
            {
              title: 'Arbitrage',
              desc: 'استغلال فروق الأسعار بين الوسطاء',
              icon: '⚡',
              features: ['Multi-Broker Monitoring', 'Latency Optimization', 'Auto Execution']
            },
            {
              title: 'Market Making',
              desc: 'توفير السيولة والاستفادة من السبريد',
              icon: '💱',
              features: ['Bid-Ask Management', 'Inventory Control', 'Risk Limits']
            },
            {
              title: 'Options Strategies',
              desc: 'دمج خيارات العملات للتحوط',
              icon: '🎯',
              features: ['Covered Calls', 'Protective Puts', 'Straddles']
            }
          ].map((feature, index) => (
            <div key={index} className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl p-6 border border-purple-400/30 hover:border-purple-400/50 transition-all duration-300">
              <div className="text-4xl mb-3">{feature.icon}</div>
              <h4 className="text-lg font-bold text-white mb-2">{feature.title}</h4>
              <p className="text-gray-400 text-sm mb-4">{feature.desc}</p>
              <ul className="space-y-1">
                {feature.features.map((item, i) => (
                  <li key={i} className="text-xs text-gray-500">• {item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Optimization Techniques */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>🔧</span>
          تقنيات التحسين المستمر
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-lg font-bold text-emerald-400 mb-4">📈 Backtesting المتقدم</h4>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• <strong className="text-white">Walk-Forward Analysis:</strong> اختبار متحرك للأمام</li>
              <li>• <strong className="text-white">Monte Carlo Simulation:</strong> محاكاة احتمالية</li>
              <li>• <strong className="text-white">Out-of-Sample Testing:</strong> بيانات خارج العينة</li>
              <li>• <strong className="text-white">Multi-Market Testing:</strong> اختبار متعدد الأسواق</li>
              <li>• <strong className="text-white">Slippage & Commission:</strong> محاكاة واقعية</li>
            </ul>
          </div>

          <div className="bg-gradient-to-br from-blue-500/10 to-indigo-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-lg font-bold text-blue-400 mb-4">⚙️ Parameter Optimization</h4>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• <strong className="text-white">Genetic Algorithms:</strong> خوارزميات جينية</li>
              <li>• <strong className="text-white">Particle Swarm:</strong> حشد الجسيمات</li>
              <li>• <strong className="text-white">Bayesian Optimization:</strong> تحسين بايزي</li>
              <li>• <strong className="text-white">Grid Search:</strong> البحث الشبكي</li>
              <li>• <strong className="text-white">Random Search:</strong> البحث العشوائي</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Timeline & Budget */}
      <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>📅</span>
          الجدول الزمني والموارد
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-lg font-bold text-yellow-400 mb-4">⏱️ التقدير الزمني الكلي</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-white font-semibold">المرحلة 1 (أساسيات)</span>
                  <span className="text-yellow-400">4 أسابيع</span>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-white font-semibold">المرحلة 2 (AI)</span>
                  <span className="text-yellow-400">4 أسابيع</span>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-white font-semibold">المرحلة 3 (توسع)</span>
                  <span className="text-yellow-400">4 أسابيع</span>
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-white font-semibold">المرحلة 4 (أتمتة)</span>
                  <span className="text-yellow-400">4 أسابيع</span>
                </div>
              </div>
              <div className="bg-yellow-500/20 rounded-xl p-4 border border-yellow-400/50">
                <div className="flex justify-between items-center">
                  <span className="text-white font-bold text-lg">الإجمالي</span>
                  <span className="text-yellow-400 font-bold text-lg">16 أسبوع (4 أشهر)</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-lg font-bold text-orange-400 mb-4">💰 الموارد المطلوبة</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">البرمجيات</div>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• MetaTrader 5 (مجاني)</li>
                  <li>• Python + Libraries (مجاني)</li>
                  <li>• Visual Studio Code (مجاني)</li>
                </ul>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">الخدمات</div>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• VPS: $20-50/شهر</li>
                  <li>• Data Feeds: $50-100/شهر</li>
                  <li>• APIs: $30-80/شهر</li>
                </ul>
              </div>
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-2">التعليم</div>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• دورات أونلاين: $100-500</li>
                  <li>• كتب: $50-150</li>
                  <li>• Mentorship (اختياري): متغير</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Final Tips */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-blue-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>💡</span>
          نصائح ذهبية للنجاح
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-lg font-semibold text-emerald-400 mb-4">✅ افعل</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>ابدأ صغيراً واختبر كل تحسين بدقة</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>احتفظ بسجل مفصل لكل التغييرات والنتائج</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>استخدم حساب تجريبي قبل التطبيق الفعلي</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>تعلم باستمرار من كل صفقة وخطأ</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span>انضم لمجتمعات المطورين والمتداولين</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-red-400 mb-4">❌ لا تفعل</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-red-400">✗</span>
                <span>لا تُفرط في التحسين (Over-optimization)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400">✗</span>
                <span>لا تغير الإعدادات بشكل متكرر ومتسرع</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400">✗</span>
                <span>لا تستخدم استراتيجية غير مختبرة على حساب حقيقي</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400">✗</span>
                <span>لا تتجاهل إدارة المخاطر مهما كانت الثقة</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-red-400">✗</span>
                <span>لا تستثمر أكثر مما تستطيع تحمل خسارته</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-6 bg-black/30 rounded-xl p-6">
          <div className="text-center">
            <div className="text-4xl mb-4">🎯</div>
            <h4 className="text-2xl font-bold text-white mb-3">الهدف النهائي</h4>
            <p className="text-gray-300 text-lg max-w-3xl mx-auto">
              بناء نظام تداول آلي قوي، موثوق، ومربح على المدى الطويل - يجمع بين التحليل الفني المتقدم، 
              الذكاء الاصطناعي، وإدارة المخاطر الذكية لتحقيق عوائد مستدامة مع الحفاظ على رأس المال.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
