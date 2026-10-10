export default function StrategyOverview() {
  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-blue-500/20 rounded-3xl p-8 border border-emerald-400/30 backdrop-blur-xl">
        <h2 className="text-4xl font-bold text-white mb-4">استراتيجية Quantum Forex Pro</h2>
        <p className="text-xl text-gray-300 leading-relaxed">
          استراتيجية تداول متقدمة مبنية على تحليل متعدد الأطر الزمنية، تجمع بين القوة التنبؤية للمؤشرات الفنية 
          والذكاء الاصطناعي في إدارة المخاطر. مصممة خصيصاً للتداول الآلي على منصة MetaTrader 5.
        </p>
      </div>

      {/* Key Features */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[
          {
            title: 'تحليل متعدد الأطر',
            desc: 'استخدام 3 أطر زمنية مختلفة للتأكد من اتجاه السوق',
            icon: '🎯',
            color: 'from-blue-500 to-cyan-500'
          },
          {
            title: 'إدارة مخاطر ذكية',
            desc: 'نظام ديناميكي لحساب حجم اللوت بناءً على التقلبات',
            icon: '🛡️',
            color: 'from-emerald-500 to-teal-500'
          },
          {
            title: 'فلاتر متقدمة',
            desc: 'تصفية الإشارات الكاذبة باستخدام حجم التداول والتقلبات',
            icon: '🔍',
            color: 'from-violet-500 to-purple-500'
          },
          {
            title: 'تحسين تلقائي',
            desc: 'تكيف ذاتي مع ظروف السوق المتغيرة',
            icon: '⚙️',
            color: 'from-orange-500 to-red-500'
          },
          {
            title: 'إدارة الصفقات',
            desc: 'Trailing Stop ديناميكي و Break-even تلقائي',
            icon: '📊',
            color: 'from-pink-500 to-rose-500'
          },
          {
            title: 'حماية من التراجع',
            desc: 'إيقاف التداول التلقائي عند الوصول لحد معين من الخسارة',
            icon: '🚨',
            color: 'from-yellow-500 to-amber-500'
          }
        ].map((feature, index) => (
          <div key={index} className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-emerald-400/50 transition-all duration-300 hover:scale-105">
            <div className={`w-14 h-14 bg-gradient-to-br ${feature.color} rounded-xl flex items-center justify-center mb-4 shadow-lg`}>
              <span className="text-2xl">{feature.icon}</span>
            </div>
            <h3 className="text-xl font-bold text-white mb-2">{feature.title}</h3>
            <p className="text-gray-400">{feature.desc}</p>
          </div>
        ))}
      </div>

      {/* Strategy Logic */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
          <span className="text-3xl">🧠</span>
          المنطق الأساسي للاستراتيجية
        </h3>
        
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-emerald-500/10 to-transparent rounded-2xl p-6 border-r-4 border-emerald-400">
            <h4 className="text-xl font-bold text-emerald-400 mb-3">المبدأ الرئيسي</h4>
            <p className="text-gray-300 leading-relaxed">
              تعتمد الاستراتيجية على مبدأ <strong className="text-white">التقاء الإشارات</strong> - حيث لا يتم فتح صفقة 
              إلا عند توافق عدة مؤشرات وفلاتر في نفس الوقت. هذا يقلل من الإشارات الكاذبة بنسبة تصل إلى 70%.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
              <h4 className="text-xl font-bold text-blue-400 mb-4">🔼 إشارة الشراء (Buy)</h4>
              <ul className="space-y-3 text-gray-300">
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 text-lg">✓</span>
                  <span>EMA السريع يعبر EMA البطيء للأعلى</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 text-lg">✓</span>
                  <span>RSI بين 40-60 (منطقة محايدة)</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 text-lg">✓</span>
                  <span>MACD إيجابي ويتزايد</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 text-lg">✓</span>
                  <span>السعر فوق EMA 200 (ترند صاعد)</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 text-lg">✓</span>
                  <span>ADX أكبر من 25 (ترند قوي)</span>
                </li>
              </ul>
            </div>

            <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
              <h4 className="text-xl font-bold text-red-400 mb-4">🔽 إشارة البيع (Sell)</h4>
              <ul className="space-y-3 text-gray-300">
                <li className="flex items-start gap-3">
                  <span className="text-red-400 text-lg">✓</span>
                  <span>EMA السريع يعبر EMA البطيء للأسفل</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-red-400 text-lg">✓</span>
                  <span>RSI بين 40-60 (منطقة محايدة)</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-red-400 text-lg">✓</span>
                  <span>MACD سلبي ويتناقص</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-red-400 text-lg">✓</span>
                  <span>السعر تحت EMA 200 (ترند هابط)</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-red-400 text-lg">✓</span>
                  <span>ADX أكبر من 25 (ترند قوي)</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Timeframes */}
      <div className="bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-3xl p-8 border border-violet-400/30">
        <h3 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
          <span className="text-3xl">⏱️</span>
          الأطر الزمنية المستخدمة
        </h3>
        
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-black/30 rounded-2xl p-6 border border-white/10">
            <div className="text-center mb-4">
              <div className="text-4xl mb-2">📅</div>
              <h4 className="text-xl font-bold text-violet-400">H4 - الإطار الكبير</h4>
            </div>
            <p className="text-gray-300 text-center">
              تحديد الاتجاه العام للسوق والترند الرئيسي
            </p>
          </div>

          <div className="bg-black/30 rounded-2xl p-6 border border-emerald-400/50 ring-2 ring-emerald-400/30">
            <div className="text-center mb-4">
              <div className="text-4xl mb-2">⏰</div>
              <h4 className="text-xl font-bold text-emerald-400">H1 - إطار التنفيذ</h4>
            </div>
            <p className="text-gray-300 text-center">
              الإطار الرئيسي لتنفيذ الصفقات وتأكيد الإشارات
            </p>
          </div>

          <div className="bg-black/30 rounded-2xl p-6 border border-white/10">
            <div className="text-center mb-4">
              <div className="text-4xl mb-2">⏲️</div>
              <h4 className="text-xl font-bold text-blue-400">M15 - التوقيت الدقيق</h4>
            </div>
            <p className="text-gray-300 text-center">
              تحديد نقطة الدخول المثالية وتحسين السعر
            </p>
          </div>
        </div>
      </div>

      {/* Performance Stats */}
      <div className="grid md:grid-cols-4 gap-6">
        {[
          { label: 'نسبة الربح المتوقعة', value: '60-70%', icon: '📈', color: 'emerald' },
          { label: 'Risk/Reward Ratio', value: '1:2 - 1:3', icon: '⚖️', color: 'blue' },
          { label: 'Max Drawdown', value: '< 15%', icon: '📉', color: 'yellow' },
          { label: 'أزواج العملات', value: 'Major Pairs', icon: '💱', color: 'violet' }
        ].map((stat, index) => (
          <div key={index} className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 text-center">
            <div className="text-3xl mb-3">{stat.icon}</div>
            <div className={`text-3xl font-bold text-${stat.color}-400 mb-2`}>{stat.value}</div>
            <div className="text-gray-400 text-sm">{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
