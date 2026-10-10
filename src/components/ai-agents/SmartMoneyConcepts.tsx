export default function SmartMoneyConcepts() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">💎 Smart Money Concepts (SMC)</h2>
        <p className="text-xl text-yellow-200">
          استراتيجية الأموال الذكية - كيف يفكر صناع السوق والمؤسسات الكبرى
        </p>
      </div>

      {/* Order Blocks */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/50">
            <span className="text-3xl">📦</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">Order Blocks (كتل الأوامر)</h3>
            <p className="text-emerald-400">المناطق التي تدخل منها المؤسسات الكبرى</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-emerald-400 font-semibold mb-4">📈 Bullish Order Block</h4>
            <p className="text-gray-300 text-sm mb-4">
              آخر شمعة هابطة قبل حركة صاعدة قوية. هنا دخلت المؤسسات بأوامر شراء ضخمة.
            </p>
            <div className="bg-black/30 rounded-lg p-4">
              <div className="text-white font-semibold text-sm mb-2">🔍 كيف يكتشفه AI Agent؟</div>
              <ul className="text-gray-400 text-xs space-y-1">
                <li>1. يبحث عن شمعة حمراء (هابطة)</li>
                <li>2. تليها حركة صاعدة قوية (&gt;100 نقطة)</li>
                <li>3. بدون ارتداد لجسم الشمعة</li>
                <li>4. حجم تداول عالٍ على الشمعة الهابطة</li>
              </ul>
            </div>
            <div className="mt-4 bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50">
              <div className="text-emerald-400 font-semibold text-sm mb-1">💡 الإشارة:</div>
              <p className="text-gray-300 text-xs">
                عندما يعود السعر لهذه المنطقة = فرصة شراء قوية
              </p>
            </div>
          </div>

          <div className="bg-red-500/10 rounded-2xl p-6 border border-red-400/30">
            <h4 className="text-red-400 font-semibold mb-4">📉 Bearish Order Block</h4>
            <p className="text-gray-300 text-sm mb-4">
              آخر شمعة صاعدة قبل حركة هابطة قوية. هنا دخلت المؤسسات بأوامر بيع ضخمة.
            </p>
            <div className="bg-black/30 rounded-lg p-4">
              <div className="text-white font-semibold text-sm mb-2">🔍 كيف يكتشفه AI Agent؟</div>
              <ul className="text-gray-400 text-xs space-y-1">
                <li>1. يبحث عن شمعة خضراء (صاعدة)</li>
                <li>2. تليها حركة هابطة قوية (&gt;100 نقطة)</li>
                <li>3. بدون ارتداد لجسم الشمعة</li>
                <li>4. حجم تداول عالٍ على الشمعة الصاعدة</li>
              </ul>
            </div>
            <div className="mt-4 bg-red-500/20 rounded-lg p-3 border border-red-400/50">
              <div className="text-red-400 font-semibold text-sm mb-1">💡 الإشارة:</div>
              <p className="text-gray-300 text-xs">
                عندما يعود السعر لهذه المنطقة = فرصة بيع قوية
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-gradient-to-r from-yellow-500/10 to-transparent rounded-xl p-6 border-r-4 border-yellow-400">
          <h4 className="text-yellow-400 font-semibold mb-3">🎯 كود الكشف (Python)</h4>
          <div className="bg-black/50 rounded-lg p-4 overflow-x-auto">
            <pre className="text-xs text-gray-300">
<code>{`def detect_order_block(df, lookback=20):
    """كشف Order Blocks باستخدام ML"""
    order_blocks = []
    
    for i in range(lookback, len(df)):
        # Bullish OB: آخر شمعة حمراء قبل صعود قوي
        if (df['close'].iloc[i-1] < df['open'].iloc[i-1] and  # شمعة حمراء
            df['close'].iloc[i] > df['close'].iloc[i-5] + 100 * point and  # صعود قوي
            df['volume'].iloc[i-1] > df['volume'].iloc[i-20:i].mean() * 1.5):  # حجم عالٍ
            
            order_blocks.append({
                'type': 'bullish',
                'high': df['high'].iloc[i-1],
                'low': df['low'].iloc[i-1],
                'time': df['time'].iloc[i-1]
            })
    
    return order_blocks`}</code>
            </pre>
          </div>
        </div>
      </div>

      {/* Fair Value Gap */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/50">
            <span className="text-3xl">🕳️</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">Fair Value Gap (FVG)</h3>
            <p className="text-blue-400">فجوات عدم التوازن - مغناطيس السعر</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-blue-400 font-semibold mb-4">🔍 ما هو FVG؟</h4>
            <p className="text-gray-300 text-sm mb-4">
              فجوة سعرية تحدث عندما تتحرك ثلاث شموع بسرعة، حيث لا يتداخل ذيل الشمعة الأولى 
              مع ذيل الشمعة الثالثة. هذه المنطقة = "ديون" يجب أن يعود السعر لملئها.
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-emerald-400 font-semibold text-sm mb-2">📈 Bullish FVG</div>
                <ul className="text-gray-400 text-xs space-y-1">
                  <li>• 3 شموع صاعدة متتالية</li>
                  <li>• High شمعة 1 &lt; Low شمعة 3</li>
                  <li>• الفجوة = منطقة دعم قوية</li>
                  <li>• السعر يعود لملئها ثم يرتد صعوداً</li>
                </ul>
              </div>

              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-red-400 font-semibold text-sm mb-2">📉 Bearish FVG</div>
                <ul className="text-gray-400 text-xs space-y-1">
                  <li>• 3 شموع هابطة متتالية</li>
                  <li>• Low شمعة 1 &gt; High شمعة 3</li>
                  <li>• الفجوة = منطقة مقاومة قوية</li>
                  <li>• السعر يعود لملئها ثم يرتد هبوطاً</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-r from-blue-500/10 to-transparent rounded-xl p-6 border-r-4 border-blue-400">
            <h4 className="text-blue-400 font-semibold mb-3">🧠 كيف يستخدمه FX Analyst؟</h4>
            <div className="bg-black/50 rounded-lg p-4">
              <code className="text-xs text-gray-300">
{`# كشف FVG تلقائياً
fvg_zones = detect_fvg(df_h1)

for fvg in fvg_zones:
    if fvg['type'] == 'bullish' and price_near_zone(current_price, fvg):
        signal = {
            'action': 'BUY',
            'reason': f'FVG Bullish at {fvg["zone"]}',
            'confidence': calculate_confluence(fvg, order_blocks, liquidity)
        }
        send_to_strategy_planner(signal)`}
              </code>
            </div>
          </div>
        </div>
      </div>

      {/* Liquidity Sweeps */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/50">
            <span className="text-3xl">🎣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">Liquidity Sweeps (صيد السيولة)</h3>
            <p className="text-purple-400">كيف تصطاد المؤسسات المتداولين الصغار</p>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
            <h4 className="text-purple-400 font-semibold mb-4">🪤 الفخ المؤسسي</h4>
            <p className="text-gray-300 text-sm mb-4">
              المؤسسات تحتاج سيولة ضخمة لتنفيذ أوامرها. أين توجد السيولة؟ 
              <strong className="text-white"> عند Stop Loss المتداولين الصغار!</strong>
            </p>

            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold text-sm mb-2">1️⃣ الإغراء</div>
                <p className="text-gray-400 text-xs">
                  السعر يصل لمستوى مقاومة → المتداولون الصغار يبيعون ويضعون SL فوق المقاومة
                </p>
              </div>

              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold text-sm mb-2">2️⃣ الاختراق الكاذب</div>
                <p className="text-gray-400 text-xs">
                  المؤسسات تدفع السعر قليلاً فوق المقاومة → تفعيل جميع Stop Losses
                </p>
              </div>

              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold text-sm mb-2">3️⃣ الانعكاس</div>
                <p className="text-gray-400 text-xs">
                  بعد جمع السيولة → انعكاس عنيف في الاتجاه المعاكس
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-r from-red-500/10 to-transparent rounded-xl p-6 border-r-4 border-red-400">
            <h4 className="text-red-400 font-semibold mb-3">⚠️ كيف نستفيد؟</h4>
            <p className="text-gray-300 text-sm mb-3">
              <strong>FX Analyst</strong> لا يبحث عن "الاختراق" بل عن "<strong>الصيد ثم الانعكاس</strong>"
            </p>
            <div className="bg-black/30 rounded-lg p-4">
              <div className="text-white font-semibold text-sm mb-2">الإشارة المثالية:</div>
              <ol className="text-gray-400 text-xs space-y-1 list-decimal list-inside">
                <li>السعر يخترق مستوى رئيسي (صيد السيولة)</li>
                <li>شمعة Rejection قوية (ذيل كبير)</li>
                <li>العودة داخل المستوى</li>
                <li>وجود Order Block تحت المستوى</li>
                <li>→ <span className="text-emerald-400 font-bold">BUY Signal</span></li>
              </ol>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Timeframe */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/50">
            <span className="text-3xl">⏱️</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">Multi-Timeframe Confluence</h3>
            <p className="text-orange-400">التوافق متعدد الأطر - القوة المضاعفة</p>
          </div>
        </div>

        <div className="bg-orange-500/10 rounded-2xl p-6 border border-orange-400/30">
          <h4 className="text-orange-400 font-semibold mb-4">🎯 القاعدة الذهبية</h4>
          <p className="text-gray-300 text-sm mb-4">
            لا تتداول أبداً ضد الترند الأعلى! حتى لو كانت الإشارة مثالية على H1، 
            إذا كان الترند على H4/D1 معاكس = احتمال الفشل عالٍ جداً.
          </p>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-black/30 rounded-lg p-4 text-center">
              <div className="text-2xl mb-2">📅</div>
              <div className="text-white font-semibold mb-1">D1</div>
              <div className="text-gray-400 text-xs">الترند العام</div>
              <div className="text-emerald-400 text-sm mt-2">Bullish ↗️</div>
            </div>

            <div className="bg-black/30 rounded-lg p-4 text-center">
              <div className="text-2xl mb-2">⏰</div>
              <div className="text-white font-semibold mb-1">H4</div>
              <div className="text-gray-400 text-xs">التأكيد</div>
              <div className="text-emerald-400 text-sm mt-2">Bullish ↗️</div>
            </div>

            <div className="bg-black/30 rounded-lg p-4 text-center">
              <div className="text-2xl mb-2">⏲️</div>
              <div className="text-white font-semibold mb-1">H1</div>
              <div className="text-gray-400 text-xs">التنفيذ</div>
              <div className="text-emerald-400 text-sm mt-2">BUY Setup ✓</div>
            </div>
          </div>

          <div className="mt-6 bg-emerald-500/20 rounded-lg p-4 border border-emerald-400/50">
            <div className="text-emerald-400 font-bold mb-2">✅ Perfect Confluence!</div>
            <p className="text-gray-300 text-sm">
              جميع الأطر متوافقة → احتمال نجاح الصفقة <strong className="text-emerald-400">80-90%</strong>
            </p>
          </div>
        </div>
      </div>

      {/* Session Momentum */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/50">
            <span className="text-3xl">🌍</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">Session Momentum</h3>
            <p className="text-cyan-400">قوة الجلسات - متى تتداول المؤسسات؟</p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {[
            { session: 'لندن', time: '08:00-17:00 GMT', pairs: 'EUR, GBP', strength: 'عالية جداً', color: 'emerald' },
            { session: 'نيويورك', time: '13:00-22:00 GMT', pairs: 'USD, CAD', strength: 'عالية جداً', color: 'blue' },
            { session: 'طوكيو', time: '00:00-09:00 GMT', pairs: 'JPY, AUD', strength: 'متوسطة', color: 'yellow' }
          ].map((s, i) => (
            <div key={i} className={`bg-${s.color}-500/10 rounded-2xl p-6 border border-${s.color}-400/30`}>
              <div className="text-3xl mb-3">🏙️</div>
              <div className={`text-${s.color}-400 font-bold text-xl mb-2`}>{s.session}</div>
              <div className="space-y-2 text-sm">
                <div className="text-gray-400">
                  <span className="text-white font-semibold">الوقت:</span> {s.time}
                </div>
                <div className="text-gray-400">
                  <span className="text-white font-semibold">الأزواج:</span> {s.pairs}
                </div>
                <div className="text-gray-400">
                  <span className="text-white font-semibold">القوة:</span> 
                  <span className={`text-${s.color}-400 font-bold mr-1`}>{s.strength}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 bg-gradient-to-r from-purple-500/10 to-transparent rounded-xl p-6 border-r-4 border-purple-400">
          <h4 className="text-purple-400 font-semibold mb-3">🌟 Golden Hour (الساعة الذهبية)</h4>
          <p className="text-gray-300 text-sm mb-3">
            <strong>13:00-17:00 GMT</strong> - تداخل لندن + نيويورك = أعلى سيولة وحركة
          </p>
          <div className="bg-black/30 rounded-lg p-4">
            <p className="text-emerald-400 text-sm">
              ✅ FX Analyst يعطي أولوية قصوى للإشارات في هذا الوقت
            </p>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">📋 ملخص SMC Strategy</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-indigo-400 font-semibold mb-4">✅ الشروط الإلزامية للصفقة</h4>
            <ol className="space-y-2 text-gray-300 text-sm list-decimal list-inside">
              <li>Order Block تم كسره واختباره</li>
              <li>FVG مُملوء أو قريب من الملء</li>
              <li>Liquidity Sweep حدث مؤخراً</li>
              <li>Multi-Timeframe Confluence موجود</li>
              <li>الوقت = London/NY Session</li>
              <li>لا أخبار عالية التأثير خلال 30 دقيقة</li>
            </ol>
          </div>

          <div>
            <h4 className="text-purple-400 font-semibold mb-4">🎯 مثال صفقة مثالية</h4>
            <div className="bg-black/30 rounded-lg p-4 space-y-2 text-xs">
              <div className="text-white"><strong>الزوج:</strong> EUR/USD</div>
              <div className="text-white"><strong>D1:</strong> Bullish Trend ↗️</div>
              <div className="text-white"><strong>H4:</strong> Bullish OB عند 1.0850</div>
              <div className="text-white"><strong>H1:</strong> FVG Bullish + Liquidity Sweep</div>
              <div className="text-white"><strong>الوقت:</strong> 14:30 GMT (London/NY)</div>
              <div className="text-emerald-400 font-bold mt-3">→ BUY at 1.0855</div>
              <div className="text-gray-400">SL: 1.0820 | TP: 1.0920 | R:R 1:2</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
