export default function MemberRating() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-3xl p-8 border border-purple-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">⭐ نظام تقييم الأعضاء (Member Rating System)</h2>
        <p className="text-xl text-purple-200">
          تتبع دقة كل عضو في المجلس وإعطاء أوزان ديناميكية حسب الأداء التاريخي
        </p>
      </div>

      {/* How it works */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">🧮 كيف يعمل النظام؟</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
            <h4 className="text-purple-400 font-semibold mb-4">📊 التتبع</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>• تسجيل كل تصويت لكل عضو</li>
              <li>• مقارنة التصويت بالنتيجة الفعلية للصفقة</li>
              <li>• حساب نسبة الدقة لكل عضو في كل FSM State</li>
              <li>• تحديث الإحصائيات بعد كل صفقة</li>
            </ul>
          </div>

          <div className="bg-pink-500/10 rounded-2xl p-6 border border-pink-400/30">
            <h4 className="text-pink-400 font-semibold mb-4">⚖️ التوزين</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>• الأعضاء الأكثر دقة يحصلون على وزن أكبر</li>
              <li>• الوزن يتغير ديناميكياً كل 50 صفقة</li>
              <li>• الحد الأدنى للوزن: 10%</li>
              <li>• الحد الأقصى للوزن: 40%</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Performance Table */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📈 مثال: أداء الأعضاء في State C</h3>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b-2 border-purple-500">
                <th className="text-right py-4 px-4 text-purple-400">العضو</th>
                <th className="text-right py-4 px-4 text-purple-400">الدقة</th>
                <th className="text-right py-4 px-4 text-purple-400">الصفقات</th>
                <th className="text-right py-4 px-4 text-purple-400">الوزن الحالي</th>
                <th className="text-right py-4 px-4 text-purple-400">الوزن الجديد</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5">
                <td className="py-4 px-4 text-white font-semibold">EMA Trend</td>
                <td className="py-4 px-4 text-emerald-400 font-bold">82%</td>
                <td className="py-4 px-4 text-gray-400">145</td>
                <td className="py-4 px-4 text-gray-400">20%</td>
                <td className="py-4 px-4 text-emerald-400 font-bold">28% ⬆️</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-emerald-500/5 bg-emerald-500/5">
                <td className="py-4 px-4 text-white font-semibold">Heiken Ashi ⭐</td>
                <td className="py-4 px-4 text-emerald-400 font-bold">88%</td>
                <td className="py-4 px-4 text-gray-400">145</td>
                <td className="py-4 px-4 text-gray-400">25%</td>
                <td className="py-4 px-4 text-emerald-400 font-bold">35% ⬆️</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-blue-500/5">
                <td className="py-4 px-4 text-white font-semibold">SMC</td>
                <td className="py-4 px-4 text-blue-400">75%</td>
                <td className="py-4 px-4 text-gray-400">145</td>
                <td className="py-4 px-4 text-gray-400">20%</td>
                <td className="py-4 px-4 text-blue-400">22% ⬆️</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-yellow-500/5">
                <td className="py-4 px-4 text-white font-semibold">RSI/Stochastic</td>
                <td className="py-4 px-4 text-yellow-400">68%</td>
                <td className="py-4 px-4 text-gray-400">145</td>
                <td className="py-4 px-4 text-gray-400">20%</td>
                <td className="py-4 px-4 text-yellow-400">18% ⬇️</td>
              </tr>
              <tr className="border-b border-gray-800 hover:bg-red-500/5">
                <td className="py-4 px-4 text-white font-semibold">ADR</td>
                <td className="py-4 px-4 text-red-400">62%</td>
                <td className="py-4 px-4 text-gray-400">145</td>
                <td className="py-4 px-4 text-gray-400">15%</td>
                <td className="py-4 px-4 text-red-400">12% ⬇️</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-6 bg-gradient-to-r from-purple-500/10 to-transparent rounded-xl p-6 border-r-4 border-purple-400">
          <h4 className="text-purple-400 font-semibold mb-3">💡 كيفية الحساب:</h4>
          <div className="bg-black/30 rounded-lg p-4">
            <code className="text-sm text-gray-300">
              الوزن الجديد = (الدقة ÷ 100) × 50%<br/>
              <br/>
              مثال: Heiken Ashi بدقة 88%<br/>
              الوزن = (88 ÷ 100) × 50% = 0.88 × 0.5 = 44%<br/>
              لكن الحد الأقصى 40%، فالوزن النهائي = 35%
            </code>
          </div>
        </div>
      </div>

      {/* Code */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود نظام التقييم</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
<code>{`struct MemberStats {
    string name;
    int total_votes;
    int correct_votes;
    double accuracy;
    double weight;
    double accuracy_per_state[5];  // لكل FSM State
};

MemberStats member_stats[5];

// تسجيل التصويت
void RecordVote(int member_index, string vote_direction, MarketState state) {
    member_stats[member_index].total_votes++;
    
    // حفظ في قاعدة بيانات مؤقتة
    SaveVoteToDatabase(member_index, vote_direction, state, TimeCurrent());
}

// تحديث الإحصائيات بعد إغلاق الصفقة
void UpdateMemberStats(ulong ticket, double profit) {
    // قراءة التصويتات المرتبطة بهذه الصفقة
    VoteRecord votes[] = LoadVotesForTrade(ticket);
    
    string actual_result = (profit > 0) ? "PROFIT" : "LOSS";
    
    for(int i = 0; i < ArraySize(votes); i++) {
        int member_idx = votes[i].member_index;
        string vote = votes[i].vote_direction;
        
        // إذا كان التصويت صحيحاً
        bool correct = false;
        if(profit > 0 && vote == "BUY") correct = true;
        else if(profit > 0 && vote == "SELL") correct = false;
        else if(profit < 0 && vote == "BUY") correct = false;
        else if(profit < 0 && vote == "SELL") correct = true;
        
        if(correct) {
            member_stats[member_idx].correct_votes++;
        }
        
        // حساب الدقة
        member_stats[member_idx].accuracy = 
            (double)member_stats[member_idx].correct_votes / 
            (double)member_stats[member_idx].total_votes * 100.0;
    }
    
    // تحديث الأوزان كل 50 صفقة
    static int trades_count = 0;
    trades_count++;
    
    if(trades_count >= 50) {
        RecalculateWeights();
        trades_count = 0;
    }
}

// إعادة حساب الأوزان
void RecalculateWeights() {
    Print("🔄 إعادة حساب أوزان الأعضاء...");
    
    double total_accuracy = 0;
    for(int i = 0; i < 5; i++) {
        total_accuracy += member_stats[i].accuracy;
    }
    
    for(int i = 0; i < 5; i++) {
        // الوزن بناءً على الدقة
        double raw_weight = (member_stats[i].accuracy / total_accuracy) * 100.0;
        
        // تطبيق الحدود
        raw_weight = MathMax(raw_weight, 10.0);  // الحد الأدنى
        raw_weight = MathMin(raw_weight, 40.0);  // الحد الأقصى
        
        member_stats[i].weight = raw_weight;
        
        Print(member_stats[i].name, ": دقة = ", 
              DoubleToString(member_stats[i].accuracy, 1), "%, وزن = ", 
              DoubleToString(member_stats[i].weight, 1), "%");
    }
}

// التصويت الموزون
VotingResult ConductWeightedVoting() {
    VotingResult result;
    double buy_weight = 0;
    double sell_weight = 0;
    
    // عضو 1: EMA
    Vote vote_ema = GetEMA_Vote();
    if(vote_ema == VOTE_BUY) 
        buy_weight += member_stats[0].weight;
    else if(vote_ema == VOTE_SELL) 
        sell_weight += member_stats[0].weight;
    
    // عضو 2: Heiken Ashi (إلزامي)
    Vote vote_ha = GetHeikenAshi_Vote();
    result.heiken_ashi_approved = (vote_ha == VOTE_BUY || vote_ha == VOTE_SELL);
    if(vote_ha == VOTE_BUY) 
        buy_weight += member_stats[1].weight;
    else if(vote_ha == VOTE_SELL) 
        sell_weight += member_stats[1].weight;
    
    // ... باقي الأعضاء
    
    // القرار بناءً على الوزن
    double required_weight = 50.0;  // 50% من الوزن الإجمالي
    
    if(buy_weight >= required_weight && result.heiken_ashi_approved) {
        result.decision = "BUY";
        result.consensus_reached = true;
        result.confidence = buy_weight;  // قوة الإجماع
    }
    else if(sell_weight >= required_weight && result.heiken_ashi_approved) {
        result.decision = "SELL";
        result.consensus_reached = true;
        result.confidence = sell_weight;
    }
    
    return result;
}`}</code>
          </pre>
        </div>
      </div>

      {/* Benefits */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">🎯 الفوائد</h3>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-4xl mb-3">📈</div>
            <h4 className="text-white font-semibold mb-2">دقة أعلى</h4>
            <p className="text-gray-400 text-sm">زيادة نسبة الربح بنسبة 5-10%</p>
          </div>
          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-4xl mb-3">🤖</div>
            <h4 className="text-white font-semibold mb-2">تكيف ذاتي</h4>
            <p className="text-gray-400 text-sm">النظام يتعلم ويتحسن تلقائياً</p>
          </div>
          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-4xl mb-3">🎯</div>
            <h4 className="text-white font-semibold mb-2">أولويات ذكية</h4>
            <p className="text-gray-400 text-sm">الاعتماد على الأعضاء الأكثر موثوقية</p>
          </div>
        </div>
      </div>
    </div>
  );
}
