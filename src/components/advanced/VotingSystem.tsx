export default function VotingSystem() {
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="bg-gradient-to-br from-indigo-500/20 to-blue-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">⚖️ مجلس التصويت (The Voting Council)</h2>
        <p className="text-xl text-indigo-200 mb-4">
          نظام ديمقراطي ذكي: 5 مؤشرات تصوّت، و3 أصوات مطلوبة للإجماع
        </p>
        <div className="bg-black/30 rounded-xl p-4">
          <p className="text-gray-300">
            💡 <strong className="text-white">لا ديكتاتورية!</strong> بدلاً من الاعتماد على مؤشر واحد، 
            يجب موافقة أغلبية المجلس (60%) قبل فتح أي صفقة.
          </p>
        </div>
      </div>

      {/* Consensus Protocol */}
      <div className="bg-gradient-to-r from-purple-500/10 to-transparent rounded-3xl p-8 border-r-4 border-purple-400">
        <h3 className="text-2xl font-bold text-white mb-4">🎯 بروتوكول الإجماع (Consensus Protocol)</h3>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-black/30 rounded-xl p-6 text-center">
            <div className="text-5xl font-bold text-purple-400 mb-2">5</div>
            <div className="text-white font-semibold mb-1">أعضاء المجلس</div>
            <div className="text-gray-400 text-sm">مؤشرات مستقلة</div>
          </div>
          <div className="bg-black/30 rounded-xl p-6 text-center border-2 border-emerald-400/50">
            <div className="text-5xl font-bold text-emerald-400 mb-2">3</div>
            <div className="text-white font-semibold mb-1">الحد الأدنى للموافقة</div>
            <div className="text-gray-400 text-sm">60% نسبة أمان</div>
          </div>
          <div className="bg-black/30 rounded-xl p-6 text-center">
            <div className="text-5xl font-bold text-blue-400 mb-2">1</div>
            <div className="text-white font-semibold mb-1">عضو إلزامي</div>
            <div className="text-gray-400 text-sm">Heiken Ashi</div>
          </div>
        </div>
      </div>

      {/* Council Members */}
      <div className="space-y-6">
        <h3 className="text-2xl font-bold text-white">👥 أعضاء المجلس الخمسة</h3>

        {/* Member 1: EMA */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-blue-500/50 flex-shrink-0">
              <span className="text-3xl mb-1">📊</span>
              <span className="text-white font-bold text-sm">عضو 1</span>
            </div>
            <div className="flex-1">
              <h4 className="text-2xl font-bold text-white mb-2">عضو الاتجاه - EMA Trend</h4>
              <p className="text-blue-400 mb-4">المسؤول عن تحديد الاتجاه العام طويل الأجل</p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/30">
                  <h5 className="text-white font-semibold mb-3">✅ يصوت بـ BUY عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• EMA(50) &gt; EMA(200)</li>
                    <li>• السعر فوق EMA(50)</li>
                    <li>• زاوية EMA موجبة</li>
                  </ul>
                </div>
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <h5 className="text-white font-semibold mb-3">❌ يصوت بـ SELL عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• EMA(50) &lt; EMA(200)</li>
                    <li>• السعر تحت EMA(50)</li>
                    <li>• زاوية EMA سالبة</li>
                  </ul>
                </div>
              </div>
              
              <div className="mt-4 bg-black/30 rounded-xl p-4">
                <code className="text-sm text-gray-300">
                  Vote vote_EMA = (ema50 &gt; ema200 && close &gt; ema50) ? VOTE_BUY : (ema50 &lt; ema200 && close &lt; ema50) ? VOTE_SELL : VOTE_NEUTRAL;
                </code>
              </div>
            </div>
          </div>
        </div>

        {/* Member 2: Heiken Ashi */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border-2 border-emerald-400/50">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-emerald-500/50 flex-shrink-0 ring-2 ring-emerald-400">
              <span className="text-3xl mb-1">🕯️</span>
              <span className="text-white font-bold text-sm">عضو 2</span>
              <span className="text-xs text-emerald-300">إلزامي</span>
            </div>
            <div className="flex-1">
              <h4 className="text-2xl font-bold text-white mb-2">عضو الزخم - Heiken Ashi ⭐</h4>
              <p className="text-emerald-400 mb-4">المسؤول عن استمرار الزخم اللحظي (عضو إلزامي ثابت)</p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                  <h5 className="text-white font-semibold mb-3">✅ يصوت بـ BUY عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• 3 شموع خضراء متتالية</li>
                    <li>• لا ذيول سفلية طويلة</li>
                    <li>• جسم الشمعة &gt; 70% من النطاق</li>
                  </ul>
                </div>
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <h5 className="text-white font-semibold mb-3">❌ يصوت بـ SELL عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• 3 شموع حمراء متتالية</li>
                    <li>• لا ذيول علوية طويلة</li>
                    <li>• جسم الشمعة &gt; 70% من النطاق</li>
                  </ul>
                </div>
              </div>
              
              <div className="mt-4 bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
                <div className="text-emerald-400 font-semibold mb-2">⚠️ لماذا هو إلزامي؟</div>
                <p className="text-gray-300 text-sm">
                  Heiken Ashi يمثل "البوصلة اللحظية" للسوق. بدون موافقته، حتى لو صوّت الجميع، 
                  لا يمكن فتح الصفقة لأنه يحمينا من الدخول ضد الزخم الحالي.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Member 3: SMC */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-purple-500/50 flex-shrink-0">
              <span className="text-3xl mb-1">💎</span>
              <span className="text-white font-bold text-sm">عضو 3</span>
            </div>
            <div className="flex-1">
              <h4 className="text-2xl font-bold text-white mb-2">عضو السيولة - True SMC</h4>
              <p className="text-purple-400 mb-4">المسؤول عن مناطق العرض والطلب المؤسسية</p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-400/30">
                  <h5 className="text-white font-semibold mb-3">✅ يصوت بـ BUY عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• السعر داخل منطقة طلب قوية</li>
                    <li>• وجود Order Block صاعد</li>
                    <li>• Fair Value Gap للأسفل مُملأ</li>
                  </ul>
                </div>
                <div className="bg-pink-500/10 rounded-xl p-4 border border-pink-400/30">
                  <h5 className="text-white font-semibold mb-3">❌ يصوت بـ SELL عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• السعر داخل منطقة عرض قوية</li>
                    <li>• وجود Order Block هابط</li>
                    <li>• Fair Value Gap للأعلى مُملأ</li>
                  </ul>
                </div>
              </div>
              
              <div className="mt-4 bg-black/30 rounded-xl p-4">
                <div className="text-purple-400 font-semibold mb-2">📊 كيف يعمل SMC؟</div>
                <p className="text-gray-300 text-sm">
                  يحلل آخر 100 شمعة لإيجاد مناطق "تجميع السيولة" التي تُركت خلفها من قبل المؤسسات. 
                  هذه المناطق غالباً ما تكون نقاط انعكاس قوية.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Member 4: RSI/Stochastic */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-orange-500/50 flex-shrink-0">
              <span className="text-3xl mb-1">📉</span>
              <span className="text-white font-bold text-sm">عضو 4</span>
            </div>
            <div className="flex-1">
              <h4 className="text-2xl font-bold text-white mb-2">عضو التشبع - RSI + Stochastic</h4>
              <p className="text-orange-400 mb-4">المسؤول عن تجنب المناطق المتشبعة</p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-orange-500/10 rounded-xl p-4 border border-orange-400/30">
                  <h5 className="text-white font-semibold mb-3">✅ يصوت بـ BUY عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• RSI بين 30-50 (قادم من تشبع بيعي)</li>
                    <li>• Stochastic عبر للأعلى من 20</li>
                    <li>• لا تشبع شرائي</li>
                  </ul>
                </div>
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <h5 className="text-white font-semibold mb-3">❌ يصوت بـ SELL عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• RSI بين 50-70 (قادم من تشبع شرائي)</li>
                    <li>• Stochastic عبر للأسفل من 80</li>
                    <li>• لا تشبع بيعي</li>
                  </ul>
                </div>
              </div>
              
              <div className="mt-4 bg-yellow-500/10 rounded-xl p-4 border border-yellow-400/30">
                <div className="text-yellow-400 font-semibold mb-2">⚠️ دوره الحيوي:</div>
                <p className="text-gray-300 text-sm">
                  يمنع الشراء في القمم والبيع في القيعان. حتى لو كانت جميع الإشارات إيجابية، 
                  يحمينا من الدخول في نهاية الموجة.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Member 5: ADR */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-cyan-500/50 flex-shrink-0">
              <span className="text-3xl mb-1">📏</span>
              <span className="text-white font-bold text-sm">عضو 5</span>
            </div>
            <div className="flex-1">
              <h4 className="text-2xl font-bold text-white mb-2">عضو المدى - ADR (Average Daily Range)</h4>
              <p className="text-cyan-400 mb-4">المسؤول عن قياس استنفاد الحركة اليومية</p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-cyan-500/10 rounded-xl p-4 border border-cyan-400/30">
                  <h5 className="text-white font-semibold mb-3">✅ يصوت بالموافقة عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• الحركة اليومية الحالية &lt; 70% من ADR</li>
                    <li>• لا يزال هناك مجال للحركة</li>
                    <li>• الزوج لم يستنفد طاقته</li>
                  </ul>
                </div>
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
                  <h5 className="text-white font-semibold mb-3">❌ يرفض التصويت عندما:</h5>
                  <ul className="space-y-1 text-gray-300 text-sm">
                    <li>• الحركة اليومية &gt; 90% من ADR</li>
                    <li>• الزوج قد قطع مداه شبه الكامل</li>
                    <li>• احتمال انعكاس أو استراحة</li>
                  </ul>
                </div>
              </div>
              
              <div className="mt-4 bg-cyan-500/10 rounded-xl p-4 border border-cyan-400/30">
                <div className="text-cyan-400 font-semibold mb-2">📊 حساب ADR:</div>
                <code className="text-sm text-gray-300 block mt-2">
                  ADR = متوسط(High - Low) آخر 20 يوم<br />
                  Current_Range = High_Today - Low_Today<br />
                  Percent_Used = (Current_Range / ADR) × 100
                </code>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Voting Examples */}
      <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-3xl p-8 border border-purple-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>🗳️</span>
          أمثلة على عملية التصويت
        </h3>

        <div className="space-y-6">
          {/* Example 1: Pass */}
          <div className="bg-black/30 rounded-2xl p-6">
            <h4 className="text-xl font-bold text-emerald-400 mb-4">✅ مثال 1: قرار مُوافق عليه (BUY)</h4>
            <div className="grid md:grid-cols-5 gap-3 mb-4">
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">EMA Trend</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border-2 border-emerald-400 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">Heiken Ashi</div>
                <div className="text-xs text-emerald-400">BUY (إلزامي)</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">SMC</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-gray-500/20 rounded-lg p-3 border border-gray-400/50 text-center">
                <div className="text-2xl mb-1">○</div>
                <div className="text-xs text-white">RSI</div>
                <div className="text-xs text-gray-400">NEUTRAL</div>
              </div>
              <div className="bg-red-500/20 rounded-lg p-3 border border-red-400/50 text-center">
                <div className="text-2xl mb-1">✗</div>
                <div className="text-xs text-white">ADR</div>
                <div className="text-xs text-red-400">SELL</div>
              </div>
            </div>
            <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
              <div className="text-emerald-400 font-semibold mb-2">النتيجة: ✅ موافقة</div>
              <p className="text-gray-300 text-sm">
                3 أصوات BUY من أصل 5 (60%) + موافقة العضو الإلزامي (Heiken Ashi) → صفقة شراء تُنفذ
              </p>
            </div>
          </div>

          {/* Example 2: Reject */}
          <div className="bg-black/30 rounded-2xl p-6">
            <h4 className="text-xl font-bold text-red-400 mb-4">❌ مثال 2: قرار مرفوض</h4>
            <div className="grid md:grid-cols-5 gap-3 mb-4">
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">EMA Trend</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-red-500/20 rounded-lg p-3 border-2 border-red-400 text-center">
                <div className="text-2xl mb-1">✗</div>
                <div className="text-xs text-white">Heiken Ashi</div>
                <div className="text-xs text-red-400">SELL (إلزامي)</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">SMC</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">RSI</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">ADR</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
            </div>
            <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
              <div className="text-red-400 font-semibold mb-2">النتيجة: ❌ رفض</div>
              <p className="text-gray-300 text-sm">
                على الرغم من 4 أصوات BUY، لكن العضو الإلزامي (Heiken Ashi) صوّت SELL → 
                الصفقة مرفوضة لأننا ضد الزخم اللحظي
              </p>
            </div>
          </div>

          {/* Example 3: Weak Consensus */}
          <div className="bg-black/30 rounded-2xl p-6">
            <h4 className="text-xl font-bold text-yellow-400 mb-4">⚠️ مثال 3: إجماع ضعيف</h4>
            <div className="grid md:grid-cols-5 gap-3 mb-4">
              <div className="bg-emerald-500/20 rounded-lg p-3 border border-emerald-400/50 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">EMA Trend</div>
                <div className="text-xs text-emerald-400">BUY</div>
              </div>
              <div className="bg-emerald-500/20 rounded-lg p-3 border-2 border-emerald-400 text-center">
                <div className="text-2xl mb-1">✓</div>
                <div className="text-xs text-white">Heiken Ashi</div>
                <div className="text-xs text-emerald-400">BUY (إلزامي)</div>
              </div>
              <div className="bg-gray-500/20 rounded-lg p-3 border border-gray-400/50 text-center">
                <div className="text-2xl mb-1">○</div>
                <div className="text-xs text-white">SMC</div>
                <div className="text-xs text-gray-400">NEUTRAL</div>
              </div>
              <div className="bg-red-500/20 rounded-lg p-3 border border-red-400/50 text-center">
                <div className="text-2xl mb-1">✗</div>
                <div className="text-xs text-white">RSI</div>
                <div className="text-xs text-red-400">SELL</div>
              </div>
              <div className="bg-red-500/20 rounded-lg p-3 border border-red-400/50 text-center">
                <div className="text-2xl mb-1">✗</div>
                <div className="text-xs text-white">ADR</div>
                <div className="text-xs text-red-400">SELL</div>
              </div>
            </div>
            <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-400/30">
              <div className="text-yellow-400 font-semibold mb-2">النتيجة: ❌ رفض (إجماع ضعيف)</div>
              <p className="text-gray-300 text-sm">
                2 أصوات BUY فقط (40%) → لم يتحقق الحد الأدنى للإجماع (60%) → الصفقة مرفوضة
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Voting Code */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود نظام التصويت</h3>
        
        <div className="bg-black/50 rounded-2xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
            <code>{`enum Vote {
    VOTE_BUY,
    VOTE_SELL,
    VOTE_NEUTRAL
};

struct VotingResult {
    int buy_votes;
    int sell_votes;
    int neutral_votes;
    bool heiken_ashi_approved;
    bool consensus_reached;
    string decision;
};

VotingResult ConductVoting() {
    VotingResult result;
    result.buy_votes = 0;
    result.sell_votes = 0;
    result.neutral_votes = 0;
    
    // عضو 1: EMA Trend
    Vote vote_ema = GetEMA_Vote();
    if(vote_ema == VOTE_BUY) result.buy_votes++;
    else if(vote_ema == VOTE_SELL) result.sell_votes++;
    else result.neutral_votes++;
    
    // عضو 2: Heiken Ashi (إلزامي)
    Vote vote_ha = GetHeikenAshi_Vote();
    result.heiken_ashi_approved = (vote_ha == VOTE_BUY || vote_ha == VOTE_SELL);
    if(vote_ha == VOTE_BUY) result.buy_votes++;
    else if(vote_ha == VOTE_SELL) result.sell_votes++;
    else result.neutral_votes++;
    
    // عضو 3: SMC
    Vote vote_smc = GetSMC_Vote();
    if(vote_smc == VOTE_BUY) result.buy_votes++;
    else if(vote_smc == VOTE_SELL) result.sell_votes++;
    else result.neutral_votes++;
    
    // عضو 4: RSI/Stochastic
    Vote vote_rsi = GetRSI_Vote();
    if(vote_rsi == VOTE_BUY) result.buy_votes++;
    else if(vote_rsi == VOTE_SELL) result.sell_votes++;
    else result.neutral_votes++;
    
    // عضو 5: ADR
    Vote vote_adr = GetADR_Vote();
    if(vote_adr == VOTE_BUY) result.buy_votes++;
    else if(vote_adr == VOTE_SELL) result.sell_votes++;
    else result.neutral_votes++;
    
    // قرار الإجماع
    int total_votes = 5;
    int required_votes = 3;  // 60%
    
    if(result.buy_votes >= required_votes && result.heiken_ashi_approved) {
        result.consensus_reached = true;
        result.decision = "BUY";
    }
    else if(result.sell_votes >= required_votes && result.heiken_ashi_approved) {
        result.consensus_reached = true;
        result.decision = "SELL";
    }
    else {
        result.consensus_reached = false;
        result.decision = "NO_TRADE";
    }
    
    return result;
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
