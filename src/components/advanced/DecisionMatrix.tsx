export default function DecisionMatrix() {
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="bg-gradient-to-br from-pink-500/20 to-purple-500/20 rounded-3xl p-8 border border-pink-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🧠 مصفوفة القرار المتداخل (FSM × Voting)</h2>
        <p className="text-xl text-pink-200 mb-4">
          السر الذي يمنع خسارة الإكسبرت: FSM يمتلك حق الفيتو (Veto) على قرارات مجلس التصويت
        </p>
        <div className="bg-black/30 rounded-xl p-4">
          <p className="text-gray-300">
            ⚡ <strong className="text-white">العبقرية:</strong> الآلة لا تأخذ تصويت المجلس بشكل أعمى، 
            بل تمرره عبر "مستشعر البيئة" الذي قد يرفضه تماماً لحماية الحساب!
          </p>
        </div>
      </div>

      {/* Decision Flow */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">🔄 تدفق اتخاذ القرار</h3>
        
        <div className="grid md:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-2xl p-6 border border-blue-400/30 text-center">
            <div className="text-4xl mb-3">1️⃣</div>
            <div className="text-white font-semibold mb-2">قراءة السوق</div>
            <div className="text-gray-400 text-sm">FSM يحدد الحالة (A, B, C, D)</div>
          </div>
          
          <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-2xl p-6 border border-purple-400/30 text-center">
            <div className="text-4xl mb-3">2️⃣</div>
            <div className="text-white font-semibold mb-2">التصويت</div>
            <div className="text-gray-400 text-sm">المجلس يعقد جلسة ويصوّت</div>
          </div>
          
          <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 rounded-2xl p-6 border border-orange-400/30 text-center">
            <div className="text-4xl mb-3">3️⃣</div>
            <div className="text-white font-semibold mb-2">المصفوفة</div>
            <div className="text-gray-400 text-sm">FSM يراجع قرار المجلس</div>
          </div>
          
          <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-2xl p-6 border border-emerald-400/30 text-center">
            <div className="text-4xl mb-3">4️⃣</div>
            <div className="text-white font-semibold mb-2">التنفيذ</div>
            <div className="text-gray-400 text-sm">موافقة نهائية أو فيتو</div>
          </div>
        </div>
      </div>

      {/* Decision Matrix Table */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📊 جدول مصفوفة القرار الكامل</h3>
        
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b-2 border-purple-500">
                <th className="text-right py-4 px-4 text-purple-400 font-bold">حالة FSM</th>
                <th className="text-right py-4 px-4 text-purple-400 font-bold">قرار المجلس</th>
                <th className="text-right py-4 px-4 text-purple-400 font-bold">القرار النهائي</th>
                <th className="text-right py-4 px-4 text-purple-400 font-bold">التعديلات</th>
              </tr>
            </thead>
            <tbody>
              {/* State A */}
              <tr className="border-b border-gray-800 hover:bg-blue-500/5">
                <td className="py-4 px-4 text-blue-400 font-semibold" rowSpan={3}>A - تذبذب بطيء</td>
                <td className="py-4 px-4 text-emerald-400">BUY (3+ أصوات)</td>
                <td className="py-4 px-4 text-emerald-400">✅ تنفيذ BUY</td>
                <td className="py-4 px-4 text-gray-300 text-sm">
                  Grid: 15-20 نقطة<br/>
                  TP: 0.5 × ATR<br/>
                  Multiplier: 1.2
                </td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-blue-500/5">
                <td className="py-4 px-4 text-red-400">SELL (3+ أصوات)</td>
                <td className="py-4 px-4 text-red-400">✅ تنفيذ SELL</td>
                <td className="py-4 px-4 text-gray-300 text-sm">نفس الإعدادات</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-blue-500/5">
                <td className="py-4 px-4 text-gray-400">&lt; 3 أصوات</td>
                <td className="py-4 px-4 text-gray-400">⏸️ لا صفقة</td>
                <td className="py-4 px-4 text-gray-300 text-sm">انتظار</td>
              </tr>

              {/* State B */}
              <tr className="border-b border-gray-800 hover:bg-orange-500/5">
                <td className="py-4 px-4 text-orange-400 font-semibold" rowSpan={3}>B - تذبذب سريع</td>
                <td className="py-4 px-4 text-emerald-400">BUY (3+ أصوات)</td>
                <td className="py-4 px-4 text-yellow-400">⚠️ تنفيذ حذر</td>
                <td className="py-4 px-4 text-gray-300 text-sm">
                  Grid: 60-80 نقطة<br/>
                  TP: 2.0 × ATR<br/>
                  Lot: -30%
                </td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-orange-500/5">
                <td className="py-4 px-4 text-red-400">SELL (3+ أصوات)</td>
                <td className="py-4 px-4 text-yellow-400">⚠️ تنفيذ حذر</td>
                <td className="py-4 px-4 text-gray-300 text-sm">نفس الإعدادات</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-orange-500/5">
                <td className="py-4 px-4 text-gray-400">&lt; 3 أصوات</td>
                <td className="py-4 px-4 text-gray-400">⏸️ لا صفقة</td>
                <td className="py-4 px-4 text-gray-300 text-sm">تجنب التذبذبات</td>
              </tr>

              {/* State C */}
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5">
                <td className="py-4 px-4 text-emerald-400 font-semibold" rowSpan={3}>C - ترند بطيء</td>
                <td className="py-4 px-4 text-emerald-400">BUY (3+ أصوات)</td>
                <td className="py-4 px-4 text-emerald-400">✅ تنفيذ + Trailing</td>
                <td className="py-4 px-4 text-gray-300 text-sm">
                  Grid: 30-40 نقطة (مع الاتجاه فقط)<br/>
                  Trailing: 0.8 × ATR<br/>
                  TP: 1.5 × ATR
                </td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5">
                <td className="py-4 px-4 text-red-400">SELL (3+ أصوات)</td>
                <td className="py-4 px-4 text-red-400">✅ تنفيذ + Trailing</td>
                <td className="py-4 px-4 text-gray-300 text-sm">نفس الإعدادات</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5">
                <td className="py-4 px-4 text-gray-400">&lt; 3 أصوات</td>
                <td className="py-4 px-4 text-gray-400">⏸️ لا صفقة</td>
                <td className="py-4 px-4 text-gray-300 text-sm">انتظار تأكيد</td>
              </tr>

              {/* State D - الأهم */}
              <tr className="border-b border-gray-800 hover:bg-purple-500/5 bg-purple-500/5">
                <td className="py-4 px-4 text-purple-400 font-bold" rowSpan={3}>D - ترند قوي ⭐</td>
                <td className="py-4 px-4 text-emerald-400 font-semibold">BUY مع الترند</td>
                <td className="py-4 px-4 text-emerald-400 font-bold">✅ هجوم كامل!</td>
                <td className="py-4 px-4 text-gray-300 text-sm">
                  <span className="text-emerald-400">Grid: مفعّل بقوة<br/>
                  Lot: +50%<br/>
                  No SL (فقط Trailing)</span>
                </td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-purple-500/5 bg-red-500/5">
                <td className="py-4 px-4 text-red-400 font-semibold">BUY عكس الترند</td>
                <td className="py-4 px-4 text-red-400 font-bold">❌ VETO (فيتو)</td>
                <td className="py-4 px-4 text-gray-300 text-sm">
                  <span className="text-red-400">رفض تام!<br/>
                  لا يمكن البيع في قطار صاعد<br/>
                  حماية من الانتحار</span>
                </td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-purple-500/5">
                <td className="py-4 px-4 text-gray-400">NEUTRAL</td>
                <td className="py-4 px-4 text-gray-400">⏸️ لا صفقة</td>
                <td className="py-4 px-4 text-gray-300 text-sm">انتظار وضوح</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Veto Power Examples */}
      <div className="bg-gradient-to-br from-red-500/20 to-orange-500/20 rounded-3xl p-8 border border-red-400/30">
        <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>🛑</span>
          قوة الفيتو (Veto Power) - أمثلة حقيقية
        </h3>

        <div className="space-y-6">
          {/* Example 1 */}
          <div className="bg-black/30 rounded-2xl p-6">
            <h4 className="text-xl font-bold text-red-400 mb-4">مثال 1: إنقاذ من كارثة</h4>
            
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <div className="text-white font-semibold mb-3">📊 الموقف:</div>
                <ul className="space-y-2 text-gray-300 text-sm">
                  <li>• <strong>FSM State:</strong> D - ترند صاعد قوي جداً</li>
                  <li>• <strong>EMA:</strong> زاوية 52 درجة للأعلى</li>
                  <li>• <strong>ADX:</strong> 48 (قوة عالية)</li>
                  <li>• <strong>Heiken Ashi:</strong> 8 شموع خضراء متصلة</li>
                </ul>
              </div>

              <div>
                <div className="text-white font-semibold mb-3">🗳️ قرار المجلس:</div>
                <ul className="space-y-2 text-sm">
                  <li className="text-red-400">• EMA: SELL (تشبع شرائي)</li>
                  <li className="text-red-400">• RSI: SELL (فوق 70)</li>
                  <li className="text-red-400">• SMC: SELL (منطقة عرض)</li>
                  <li className="text-emerald-400">• Heiken Ashi: BUY</li>
                  <li className="text-red-400">• ADR: NEUTRAL</li>
                  <li className="text-red-400 font-bold mt-2">→ النتيجة: 3 أصوات SELL ✓</li>
                </ul>
              </div>
            </div>

            <div className="mt-6 bg-red-500/20 rounded-xl p-6 border-2 border-red-400">
              <div className="flex items-center gap-4 mb-4">
                <div className="text-5xl">🛑</div>
                <div>
                  <div className="text-red-400 font-bold text-xl">FSM يستخدم حق الفيتو!</div>
                  <div className="text-gray-300 text-sm mt-1">
                    "نحن في State D - ترند قوي صاعد. محاولة البيع الآن = انتحار. أرفض القرار تماماً."
                  </div>
                </div>
              </div>
              
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-emerald-400 font-semibold mb-2">✅ النتيجة:</div>
                <p className="text-gray-300 text-sm">
                  الصفقة لم تُفتح. بعد 2 ساعة، السعر ارتفع 150 نقطة إضافية. 
                  FSM أنقذ الحساب من خسارة محتملة كبيرة!
                </p>
              </div>
            </div>
          </div>

          {/* Example 2 */}
          <div className="bg-black/30 rounded-2xl p-6">
            <h4 className="text-xl font-bold text-emerald-400 mb-4">مثال 2: موافقة مع تعديلات</h4>
            
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <div className="text-white font-semibold mb-3">📊 الموقف:</div>
                <ul className="space-y-2 text-gray-300 text-sm">
                  <li>• <strong>FSM State:</strong> B - تذبذب سريع (أخبار NFP)</li>
                  <li>• <strong>ATR:</strong> 180% من المتوسط</li>
                  <li>• <strong>Volatility:</strong> عالية جداً</li>
                </ul>
              </div>

              <div>
                <div className="text-white font-semibold mb-3">🗳️ قرار المجلس:</div>
                <ul className="space-y-2 text-sm">
                  <li className="text-emerald-400">• EMA: BUY</li>
                  <li className="text-emerald-400">• Heiken Ashi: BUY ✓</li>
                  <li className="text-emerald-400">• SMC: BUY</li>
                  <li className="text-gray-400">• RSI: NEUTRAL</li>
                  <li className="text-emerald-400">• ADR: BUY</li>
                  <li className="text-emerald-400 font-bold mt-2">→ النتيجة: 4 أصوات BUY ✓</li>
                </ul>
              </div>
            </div>

            <div className="mt-6 bg-yellow-500/20 rounded-xl p-6 border-2 border-yellow-400">
              <div className="flex items-center gap-4 mb-4">
                <div className="text-5xl">⚠️</div>
                <div>
                  <div className="text-yellow-400 font-bold text-xl">FSM يوافق مع تعديلات</div>
                  <div className="text-gray-300 text-sm mt-1">
                    "موافق، لكن نحن في State B - تذبذب خطير. سأعدل الإعدادات للحماية."
                  </div>
                </div>
              </div>
              
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-yellow-400 font-semibold mb-2">⚙️ التعديلات التلقائية:</div>
                <ul className="text-gray-300 text-sm space-y-1">
                  <li>• Lot Size: تخفيض بنسبة 40%</li>
                  <li>• Grid Distance: توسيع من 30 إلى 70 نقطة</li>
                  <li>• Take Profit: زيادة إلى 2 × ATR</li>
                  <li>• Max Grid Orders: تقليل من 10 إلى 4</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Code Implementation */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 تطبيق المصفوفة في الكود</h3>
        
        <div className="bg-black/50 rounded-2xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
            <code>{`bool ExecuteDecisionMatrix(VotingResult voting, MarketState fsm_state) {
    // إذا لم يتحقق الإجماع، لا تفعل شيء
    if(!voting.consensus_reached) {
        Print("لا إجماع - لا صفقة");
        return false;
    }
    
    string decision = voting.decision;
    
    // State D - الأهم: حق الفيتو
    if(fsm_state == STATE_D_STRONG_TREND) {
        bool is_uptrend = (ema50 > ema200);
        
        if(is_uptrend && decision == "SELL") {
            Print("🛑 VETO: رفض SELL في ترند صاعد قوي!");
            return false;  // فيتو!
        }
        else if(!is_uptrend && decision == "BUY") {
            Print("🛑 VETO: رفض BUY في ترند هابط قوي!");
            return false;  // فيتو!
        }
        else {
            // موافقة بتعديلات عدوانية
            AdjustSettings_StateD(decision);
            return OpenTrade(decision);
        }
    }
    
    // State B: تذبذب سريع - موافقة مع حذر
    else if(fsm_state == STATE_B_HIGH_VOLATILITY_RANGE) {
        Print("⚠️ State B: تنفيذ حذر");
        AdjustSettings_StateB(decision);
        return OpenTrade(decision);
    }
    
    // State A: تذبذب بطيء - موافقة مباشرة
    else if(fsm_state == STATE_A_LOW_VOLATILITY_RANGE) {
        Print("✅ State A: تنفيذ Grid");
        AdjustSettings_StateA(decision);
        return OpenTrade(decision);
    }
    
    // State C: ترند بطيء - موافقة مع Trailing
    else if(fsm_state == STATE_C_SLOW_TREND) {
        Print("✅ State C: تنفيذ Trending");
        AdjustSettings_StateC(decision);
        return OpenTrade(decision);
    }
    
    return false;
}

// تعديلات State D - عدواني
void AdjustSettings_StateD(string direction) {
    Lot_Size = Lot_Size * 1.5;  // زيادة 50%
    Grid_Distance = 40;
    Use_StopLoss = false;  // بدون SL، فقط Trailing
    Use_Trailing = true;
    Trailing_Distance = ATR * 1.5;
    Max_Grid_Orders = 8;
    Grid_Direction = direction;  // فقط في الاتجاه
}

// تعديلات State B - حذر
void AdjustSettings_StateB(string direction) {
    Lot_Size = Lot_Size * 0.6;  // تخفيض 40%
    Grid_Distance = 70;
    Take_Profit = ATR * 2.0;
    Max_Grid_Orders = 4;
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
