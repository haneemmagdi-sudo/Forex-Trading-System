export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl p-8 border border-cyan-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">📊 لوحة التحكم الشاملة (Dashboard)</h2>
        <p className="text-xl text-cyan-200">
          رؤية كاملة لكل شيء في مكان واحد - على الشارت مباشرة
        </p>
      </div>

      {/* Dashboard Preview */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 border-2 border-cyan-400/50 shadow-2xl">
        <h3 className="text-2xl font-bold text-white mb-6 text-center">مثال: Dashboard على الشارت</h3>
        
        <div className="grid grid-cols-12 gap-4">
          {/* Top Bar */}
          <div className="col-span-12 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-xl p-4 border border-purple-400/30">
            <div className="grid grid-cols-5 gap-4">
              <div className="text-center">
                <div className="text-purple-400 text-xs mb-1">FSM State</div>
                <div className="text-2xl font-bold text-white">D</div>
                <div className="text-xs text-emerald-400">ترند قوي ↗️</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400 text-xs mb-1">Balance</div>
                <div className="text-2xl font-bold text-white">$10,542</div>
                <div className="text-xs text-emerald-400">+5.4%</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400 text-xs mb-1">Drawdown</div>
                <div className="text-2xl font-bold text-yellow-400">8.2%</div>
                <div className="text-xs text-gray-400">Peak: $11,200</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400 text-xs mb-1">Win Rate</div>
                <div className="text-2xl font-bold text-emerald-400">72%</div>
                <div className="text-xs text-gray-400">18/25 trades</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400 text-xs mb-1">Mode</div>
                <div className="text-xl font-bold text-white">NORMAL</div>
                <div className="text-xs text-emerald-400">✓ Active</div>
              </div>
            </div>
          </div>

          {/* Left Panel - Voting */}
          <div className="col-span-4 bg-black/30 rounded-xl p-4 border border-white/10">
            <div className="text-cyan-400 font-semibold mb-3">🗳️ Voting Status</div>
            <div className="space-y-2">
              {[
                { name: 'EMA', vote: 'BUY', accuracy: '82%', weight: '28%' },
                { name: 'Heiken Ashi', vote: 'BUY', accuracy: '88%', weight: '35%' },
                { name: 'SMC', vote: 'NEUTRAL', accuracy: '75%', weight: '22%' },
                { name: 'RSI', vote: 'SELL', accuracy: '68%', weight: '18%' },
                { name: 'ADR', vote: 'BUY', accuracy: '62%', weight: '12%' }
              ].map((m, i) => (
                <div key={i} className="flex items-center justify-between text-xs bg-white/5 rounded p-2">
                  <span className="text-white">{m.name}</span>
                  <span className={m.vote === 'BUY' ? 'text-emerald-400' : m.vote === 'SELL' ? 'text-red-400' : 'text-gray-400'}>
                    {m.vote}
                  </span>
                  <span className="text-gray-400">{m.accuracy}</span>
                </div>
              ))}
              <div className="mt-3 pt-3 border-t border-white/10">
                <div className="text-emerald-400 font-bold">Decision: BUY (68% confidence)</div>
              </div>
            </div>
          </div>

          {/* Center Panel - Open Positions */}
          <div className="col-span-4 bg-black/30 rounded-xl p-4 border border-white/10">
            <div className="text-cyan-400 font-semibold mb-3">💼 Open Positions (3)</div>
            <div className="space-y-2">
              {[
                { pair: 'EUR/USD', type: 'BUY', profit: '+$45', pips: '+38', color: 'emerald' },
                { pair: 'GBP/USD', type: 'BUY', profit: '+$32', pips: '+28', color: 'emerald' },
                { pair: 'USD/JPY', type: 'SELL', profit: '-$12', pips: '-8', color: 'red' }
              ].map((p, i) => (
                <div key={i} className={`bg-${p.color}-500/10 rounded p-2 border border-${p.color}-400/30`}>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-white font-semibold">{p.pair}</span>
                    <span className={`text-${p.color}-400`}>{p.type}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs mt-1">
                    <span className={`text-${p.color}-400 font-bold`}>{p.profit}</span>
                    <span className="text-gray-400">{p.pips}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Panel - Today Stats */}
          <div className="col-span-4 bg-black/30 rounded-xl p-4 border border-white/10">
            <div className="text-cyan-400 font-semibold mb-3">📈 Today's Stats</div>
            <div className="space-y-3">
              <div className="bg-white/5 rounded p-2">
                <div className="text-xs text-gray-400 mb-1">Trades</div>
                <div className="text-xl font-bold text-white">7 / 10</div>
              </div>
              <div className="bg-emerald-500/10 rounded p-2 border border-emerald-400/30">
                <div className="text-xs text-gray-400 mb-1">Wins</div>
                <div className="text-xl font-bold text-emerald-400">5</div>
              </div>
              <div className="bg-red-500/10 rounded p-2 border border-red-400/30">
                <div className="text-xs text-gray-400 mb-1">Losses</div>
                <div className="text-xl font-bold text-red-400">2</div>
              </div>
              <div className="bg-blue-500/10 rounded p-2 border border-blue-400/30">
                <div className="text-xs text-gray-400 mb-1">Profit</div>
                <div className="text-xl font-bold text-blue-400">+$187</div>
              </div>
            </div>
          </div>

          {/* Bottom Bar - Alerts */}
          <div className="col-span-12 bg-gradient-to-r from-yellow-500/20 to-transparent rounded-xl p-3 border-r-4 border-yellow-400">
            <div className="text-xs text-yellow-400 font-semibold">⚠️ Last Alert: EUR/USD Vote passed - Opening BUY (2 min ago)</div>
          </div>
        </div>
      </div>

      {/* Code */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود Dashboard</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300">
<code>{`#include <ChartObjects\\ChartObjectsPanel.mqh>

void DrawDashboard() {
    int x = 10, y = 30;
    int width = 350, height = 450;
    
    // Main Panel
    ObjectCreate(0, "Dashboard_Panel", OBJ_RECTANGLE_LABEL, 0, 0, 0);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_YDISTANCE, y);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_XSIZE, width);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_YSIZE, height);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_BGCOLOR, clrBlack);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_BORDER_TYPE, BORDER_FLAT);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_COLOR, clrCyan);
    ObjectSetInteger(0, "Dashboard_Panel", OBJPROP_WIDTH, 2);
    
    // FSM State
    CreateLabel("FSM_State", x+10, y+10, "FSM: " + EnumToString(current_state), clrPurple);
    
    // Balance
    string balance_text = "Balance: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2);
    CreateLabel("Balance", x+10, y+35, balance_text, clrWhite);
    
    // Drawdown
    double dd = CalculateDrawdown();
    color dd_color = (dd < 5) ? clrLime : (dd < 10) ? clrYellow : clrRed;
    CreateLabel("Drawdown", x+10, y+60, "DD: " + DoubleToString(dd, 1) + "%", dd_color);
    
    // Voting
    int vote_y = y + 100;
    CreateLabel("Voting_Title", x+10, vote_y, "=== VOTING ===", clrCyan);
    
    VotingResult vote = last_voting_result;
    string[] members = {"EMA", "Heiken Ashi", "SMC", "RSI", "ADR"};
    
    for(int i = 0; i < 5; i++) {
        string vote_text = members[i] + ": " + GetMemberVote(i);
        color vote_color = GetVoteColor(i);
        CreateLabel("Vote_" + IntegerToString(i), x+15, vote_y + 25 + (i*20), vote_text, vote_color);
    }
    
    // Decision
    CreateLabel("Decision", x+10, vote_y + 150, 
                "Decision: " + vote.decision + " (" + DoubleToString(vote.confidence, 0) + "%)", 
                clrLime);
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
