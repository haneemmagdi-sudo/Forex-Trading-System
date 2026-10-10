export default function SmartGrid() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl p-8 border border-cyan-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🕸️ نظام الشبكة الذكية (Smart Grid Recovery)</h2>
        <p className="text-xl text-cyan-200">
          شبكة ديناميكية تفتح فقط بموافقة مجلس التصويت + FSM، وتتكيف مع التراجع
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
          <h3 className="text-2xl font-bold text-white mb-4">🎯 كيف يعمل؟</h3>
          <ul className="space-y-3 text-gray-300">
            <li>✓ شبكة تفتح فقط في اتجاه القرار المُصوّت عليه</li>
            <li>✓ كل عقد شبكة يمر بنفس نظام التصويت</li>
            <li>✓ المسافات ديناميكية حسب FSM State</li>
            <li>✓ Multiplier ذكي (1.2 - 1.8 حسب الحالة)</li>
            <li>✓ إيقاف تلقائي عند تغيير FSM State</li>
          </ul>
        </div>

        <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
          <h3 className="text-2xl font-bold text-white mb-4">⚙️ الإعدادات حسب FSM</h3>
          <div className="space-y-2 text-sm">
            <div className="bg-blue-500/10 p-3 rounded-lg border border-blue-400/30">
              <strong className="text-blue-400">State A:</strong> Grid 15-20 نقطة، Mult 1.2، Max 10
            </div>
            <div className="bg-orange-500/10 p-3 rounded-lg border border-orange-400/30">
              <strong className="text-orange-400">State B:</strong> Grid 60-80 نقطة، Mult 1.5، Max 4
            </div>
            <div className="bg-emerald-500/10 p-3 rounded-lg border border-emerald-400/30">
              <strong className="text-emerald-400">State C:</strong> Grid 30-40 نقطة (اتجاه واحد)، Max 7
            </div>
            <div className="bg-purple-500/10 p-3 rounded-lg border border-purple-400/30">
              <strong className="text-purple-400">State D:</strong> Grid 40 نقطة (مع الترند)، Max 8
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود الشبكة الذكية</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300">
<code>{`void OpenSmartGridOrder(string direction, int level) {
    // التحقق من موافقة المجلس للعقد الجديد
    VotingResult vote = ConductVoting();
    
    if(!vote.consensus_reached || vote.decision != direction) {
        Print("Grid Order مرفوض - لا إجماع");
        return;
    }
    
    // تطبيق المصفوفة
    MarketState state = DetectMarketState();
    if(!ExecuteDecisionMatrix(vote, state)) {
        Print("Grid Order مرفوض - Veto");
        return;
    }
    
    // حساب حجم اللوت بالتبريد
    double base_lot = CalculateLotSize();
    double multiplier = GetMultiplier(state);
    double grid_lot = base_lot * MathPow(multiplier, level);
    
    // حساب المسافة
    double grid_distance = GetGridDistance(state);
    double entry_price = (direction == "BUY") ? 
        Ask - (grid_distance * level * _Point) :
        Bid + (grid_distance * level * _Point);
    
    // فتح العقد
    OpenGridPosition(direction, grid_lot, entry_price, level);
}

double GetGridDistance(MarketState state) {
    switch(state) {
        case STATE_A: return 20;
        case STATE_B: return 70;
        case STATE_C: return 35;
        case STATE_D: return 40;
    }
    return 30;
}

double GetMultiplier(MarketState state) {
    switch(state) {
        case STATE_A: return 1.2;  // حذر
        case STATE_B: return 1.5;  // حذر جداً
        case STATE_C: return 1.3;  // متوازن
        case STATE_D: return 1.4;  // عدواني قليلاً
    }
    return 1.3;
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
