export default function PortfolioManager() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-indigo-500/20 to-blue-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🌐 Portfolio Correlation Matrix</h2>
        <p className="text-xl text-indigo-200">
          إدارة ذكية لعدة أزواج عملات مع تجنب الارتباط العالي
        </p>
      </div>

      {/* Correlation Matrix */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📊 مصفوفة الارتباط (Correlation Matrix)</h3>
        
        <div className="overflow-x-auto">
          <table className="w-full text-center text-sm">
            <thead>
              <tr className="border-b-2 border-indigo-500">
                <th className="py-3 px-2 text-indigo-400">الزوج</th>
                <th className="py-3 px-2 text-indigo-400">EUR/USD</th>
                <th className="py-3 px-2 text-indigo-400">GBP/USD</th>
                <th className="py-3 px-2 text-indigo-400">USD/JPY</th>
                <th className="py-3 px-2 text-indigo-400">AUD/USD</th>
                <th className="py-3 px-2 text-indigo-400">USD/CHF</th>
                <th className="py-3 px-2 text-indigo-400">NZD/USD</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800">
                <td className="py-3 px-2 text-white font-semibold">EUR/USD</td>
                <td className="py-3 px-2 bg-gray-500/20">1.00</td>
                <td className="py-3 px-2 bg-emerald-500/20 text-emerald-400 font-bold">+0.85</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400 font-bold">-0.72</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.62</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400 font-bold">-0.91</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.58</td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="py-3 px-2 text-white font-semibold">GBP/USD</td>
                <td className="py-3 px-2 bg-emerald-500/20 text-emerald-400 font-bold">+0.85</td>
                <td className="py-3 px-2 bg-gray-500/20">1.00</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.65</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.55</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400 font-bold">-0.82</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.52</td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="py-3 px-2 text-white font-semibold">USD/JPY</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400 font-bold">-0.72</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.65</td>
                <td className="py-3 px-2 bg-gray-500/20">1.00</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.48</td>
                <td className="py-3 px-2 bg-emerald-500/20 text-emerald-400">+0.68</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.45</td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="py-3 px-2 text-white font-semibold">AUD/USD</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.62</td>
                <td className="py-3 px-2 bg-blue-500/20 text-blue-400">+0.55</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.48</td>
                <td className="py-3 px-2 bg-gray-500/20">1.00</td>
                <td className="py-3 px-2 bg-red-500/20 text-red-400">-0.70</td>
                <td className="py-3 px-2 bg-emerald-500/20 text-emerald-400 font-bold">+0.88</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
            <div className="text-emerald-400 font-semibold mb-2">ارتباط موجب قوي (&gt; +0.8)</div>
            <p className="text-gray-400 text-sm">يتحركان في نفس الاتجاه - تجنب الجمع</p>
          </div>
          <div className="bg-red-500/10 rounded-xl p-4 border border-red-400/30">
            <div className="text-red-400 font-semibold mb-2">ارتباط سالب قوي (&lt; -0.8)</div>
            <p className="text-gray-400 text-sm">يتحركان عكسياً - تجنب الجمع</p>
          </div>
          <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/30">
            <div className="text-blue-400 font-semibold mb-2">ارتباط ضعيف (-0.6 to +0.6)</div>
            <p className="text-gray-400 text-sm">آمن للتداول معاً</p>
          </div>
        </div>
      </div>

      {/* Portfolio Rules */}
      <div className="bg-gradient-to-r from-purple-500/10 to-transparent rounded-3xl p-8 border-r-4 border-purple-400">
        <h3 className="text-2xl font-bold text-white mb-6">📜 قواعد المحفظة</h3>
        
        <div className="space-y-4">
          {[
            { rule: 'لا تفتح صفقات BUY على EUR/USD و GBP/USD معاً', reason: 'ارتباط +0.85', color: 'red' },
            { rule: 'لا تفتح BUY EUR/USD و SELL USD/CHF معاً', reason: 'ارتباط -0.91 (نفس التعرض)', color: 'red' },
            { rule: 'AUD/USD + NZD/USD = مخاطرة مضاعفة', reason: 'ارتباط +0.88', color: 'orange' },
            { rule: 'EUR/USD + USD/JPY = تنويع جيد', reason: 'ارتباط -0.72 (عكسي معتدل)', color: 'emerald' },
            { rule: 'الحد الأقصى: 30% من رأس المال لكل زوج', reason: 'تنويع المخاطر', color: 'blue' }
          ].map((item, i) => (
            <div key={i} className={`bg-${item.color}-500/10 rounded-xl p-4 border border-${item.color}-400/30`}>
              <div className="flex items-start gap-3">
                <div className={`text-${item.color}-400 text-xl mt-1`}>
                  {item.color === 'emerald' ? '✓' : item.color === 'blue' ? '!' : '⚠️'}
                </div>
                <div className="flex-1">
                  <div className={`text-${item.color}-400 font-semibold mb-1`}>{item.rule}</div>
                  <div className="text-gray-400 text-sm">{item.reason}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Magic Number System */}
      <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">🔢 نظام Magic Number للمحفظة</h3>
        
        <div className="space-y-6">
          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-yellow-400 font-semibold mb-4">🎯 البنية المقترحة</h4>
            <div className="bg-black/30 rounded-lg p-4">
              <code className="text-sm text-gray-300">
                Magic Number = [Strategy ID][Pair ID][FSM State]<br/>
                <br/>
                Strategy ID: 1-9 (مثلاً: 1 = FSM+Voting, 2 = Grid Only)<br/>
                Pair ID: 01-99<br/>
                FSM State: 1-5 (A, B, C, D, E)<br/>
                <br/>
                مثال: 10241 = Strategy 1, EUR/USD (02), State D (4)
              </code>
            </div>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            {[
              { pair: 'EUR/USD', base: 102, desc: 'الزوج الرئيسي' },
              { pair: 'GBP/USD', base: 103, desc: 'تجنب مع EUR/USD' },
              { pair: 'USD/JPY', base: 104, desc: 'تنويع جيد' },
              { pair: 'AUD/USD', base: 105, desc: 'تنويع جيد' },
              { pair: 'USD/CHF', base: 106, desc: 'تجنب مع EUR/USD' },
              { pair: 'NZD/USD', base: 107, desc: 'تجنب مع AUD/USD' }
            ].map((item, i) => (
              <div key={i} className="bg-orange-500/10 rounded-xl p-4 border border-orange-400/30">
                <div className="text-white font-semibold mb-2">{item.pair}</div>
                <div className="text-2xl font-bold text-orange-400 mb-2">{item.base}XX</div>
                <div className="text-gray-400 text-xs">{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Code */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود Portfolio Manager</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
<code>{`// مصفوفة الارتباط
double correlation_matrix[6][6] = {
    {1.00, 0.85, -0.72, 0.62, -0.91, 0.58},  // EUR/USD
    {0.85, 1.00, -0.65, 0.55, -0.82, 0.52},  // GBP/USD
    {-0.72, -0.65, 1.00, -0.48, 0.68, -0.45}, // USD/JPY
    {0.62, 0.55, -0.48, 1.00, -0.70, 0.88},  // AUD/USD
    {-0.91, -0.82, 0.68, -0.70, 1.00, -0.65}, // USD/CHF
    {0.58, 0.52, -0.45, 0.88, -0.65, 1.00}   // NZD/USD
};

string pairs[] = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"};

// التحقق من السماح بفتح الصفقة
bool CheckPortfolioCorrelation(string new_pair, string direction) {
    int new_pair_idx = GetPairIndex(new_pair);
    
    // فحص جميع الصفقات المفتوحة
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        
        string open_pair = PositionGetString(POSITION_SYMBOL);
        int open_pair_idx = GetPairIndex(open_pair);
        
        if(open_pair_idx == -1) continue;
        
        ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        string open_direction = (pos_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
        
        // حساب الارتباط
        double corr = correlation_matrix[new_pair_idx][open_pair_idx];
        
        // قاعدة 1: ارتباط موجب قوي + نفس الاتجاه
        if(corr > 0.8 && direction == open_direction) {
            Print("⛔ رفض: ارتباط موجب قوي مع ", open_pair, 
                  " (", DoubleToString(corr, 2), ")");
            return false;
        }
        
        // قاعدة 2: ارتباط سالب قوي + اتجاه معاكس
        if(corr < -0.8 && direction != open_direction) {
            Print("⛔ رفض: ارتباط سالب قوي مع ", open_pair, 
                  " (", DoubleToString(corr, 2), ")");
            return false;
        }
    }
    
    return true;
}

// حساب التعرض الكلي للمحفظة
double CalculatePortfolioExposure() {
    double total_exposure = 0;
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    
    for(int i = 0; i < PositionsTotal(); i++) {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        
        double volume = PositionGetDouble(POSITION_VOLUME);
        double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
        
        double position_value = volume * 100000 * open_price;  // تقريبي
        total_exposure += position_value;
    }
    
    return (total_exposure / balance) * 100.0;
}

// Magic Number Generator
long GenerateMagicNumber(string pair, MarketState state) {
    int strategy_id = 1;  // FSM+Voting
    int pair_id = GetPairID(pair);
    int state_id = (int)state + 1;
    
    // Format: [Strategy][Pair][State]
    long magic = strategy_id * 10000 + pair_id * 10 + state_id;
    
    return magic;
}

int GetPairID(string pair) {
    if(pair == "EURUSD") return 2;
    if(pair == "GBPUSD") return 3;
    if(pair == "USDJPY") return 4;
    if(pair == "AUDUSD") return 5;
    if(pair == "USDCHF") return 6;
    if(pair == "NZDUSD") return 7;
    return 99;
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
