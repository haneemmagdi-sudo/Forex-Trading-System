import { useState, useEffect, useRef } from 'react';

// ──────────────────────────────────────────────
// بيانات محاكاة Reinforcement Learning
// ──────────────────────────────────────────────
function useRLData() {
  const tick = useRef(0);
  const [state, setState] = useState({
    isTraining: false,
    episode: 0,
    totalEpisodes: 500,
    episodeReward: [] as number[],
    avgReward: [] as number[],
    epsilon: 1.0,
    winRate: 0,
    totalTrades: 0,
    totalReward: 0,
    currentAction: 'HOLD' as 'BUY' | 'SELL' | 'HOLD',
    currentReward: 0,
    qValues: { BUY: 0.45, SELL: 0.32, HOLD: 0.61 },
    policy: 'ε-greedy' as string,
    stateSpace: 12,
    actionSpace: 3,
    // شبكة Q (DQN)
    layers: [
      { name: 'State Input', units: 12, color: '#3b82f6' },
      { name: 'Hidden 1', units: 64, color: '#8b5cf6' },
      { name: 'Hidden 2', units: 64, color: '#8b5cf6' },
      { name: 'Q-Values', units: 3, color: '#10b981' },
    ],
    replayBuffer: 847,
    explorationRate: 0.15,
    learningRate: 0.001,
    gamma: 0.95,
    bestReward: -Infinity,
    tradeLog: [] as { episode: number; action: string; reward: number; profit: number }[],
  });

  const startTraining = () => {
    setState(s => ({ ...s, isTraining: true, episode: 0, episodeReward: [], avgReward: [], epsilon: 1.0 }));
    let ep = 0;
    const t = setInterval(() => {
      ep++;
      const reward = -50 + ep * 0.4 + (Math.random() - 0.3) * 30;
      const avgR = -45 + ep * 0.38 + (Math.random() - 0.3) * 15;

      setState(s => {
        const newRewards = [...s.episodeReward, parseFloat(reward.toFixed(2))];
        const newAvg = [...s.avgReward, parseFloat(avgR.toFixed(2))];
        const eps = Math.max(0.05, 1.0 - ep * 0.022);
        const wr = Math.min(78, 45 + ep * 0.6 + (Math.random() - 0.3) * 5);

        return {
          ...s,
          episode: ep,
          episodeReward: newRewards,
          avgReward: newAvg,
          epsilon: parseFloat(eps.toFixed(3)),
          winRate: parseFloat(wr.toFixed(1)),
          totalReward: s.totalReward + reward,
          replayBuffer: Math.min(10000, s.replayBuffer + Math.floor(Math.random() * 50)),
          bestReward: Math.max(s.bestReward, reward),
        };
      });

      if (ep >= 30) {
        clearInterval(t);
        setState(s => ({ ...s, isTraining: false, explorationRate: 0.05 }));
      }
    }, 150);
  };

  useEffect(() => {
    const interval = setInterval(() => {
      tick.current++;
      const actions = ['BUY', 'SELL', 'HOLD'] as const;
      const action = actions[tick.current % 3];
      setState(s => ({
        ...s,
        currentAction: action,
        currentReward: parseFloat(((Math.random() - 0.45) * 20).toFixed(2)),
        qValues: {
          BUY:  parseFloat((Math.random() * 0.8 + 0.1).toFixed(3)),
          SELL: parseFloat((Math.random() * 0.8 + 0.1).toFixed(3)),
          HOLD: parseFloat((Math.random() * 0.8 + 0.1).toFixed(3)),
        },
      }));
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return { ...state, startTraining };
}

// ──────────────────────────────────────────────
// Reward Chart
// ──────────────────────────────────────────────
function RewardChart({ episodeReward, avgReward }: { episodeReward: number[]; avgReward: number[] }) {
  if (episodeReward.length < 2) return (
    <div className="flex items-center justify-center h-28 text-gray-600 text-sm">
      ابدأ التدريب لرؤية منحنى المكافأة
    </div>
  );

  const w = 500, h = 110;
  const all = [...episodeReward, ...avgReward];
  const maxV = Math.max(...all);
  const minV = Math.min(...all);
  const range = maxV - minV || 1;
  const n = episodeReward.length;

  const pts = (arr: number[]) =>
    arr.map((v, i) => {
      const x = (i / (n - 1)) * (w - 20) + 10;
      const y = 10 + ((maxV - v) / range) * (h - 20);
      return `${x},${y}`;
    }).join(' ');

  // منطقة الصفر
  const zeroY = 10 + (maxV / range) * (h - 20);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <line x1="10" y1={zeroY} x2={w - 10} y2={zeroY} stroke="rgba(255,255,255,0.1)" strokeWidth="1" strokeDasharray="3,3" />
      <polyline points={pts(episodeReward)} fill="none" stroke="rgba(139,92,246,0.6)" strokeWidth="1.5" />
      {avgReward.length > 1 && (
        <polyline points={pts(avgReward)} fill="none" stroke="#10b981" strokeWidth="2.5" />
      )}
    </svg>
  );
}

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────
export default function ReinforcementLearning() {
  const rl = useRLData();

  const actionColor = (a: string) =>
    a === 'BUY' ? 'text-emerald-400' : a === 'SELL' ? 'text-red-400' : 'text-yellow-400';
  const actionBg = (a: string) =>
    a === 'BUY' ? 'bg-emerald-500/20 border-emerald-400/30' : a === 'SELL' ? 'bg-red-500/20 border-red-400/30' : 'bg-yellow-500/20 border-yellow-400/30';

  const maxQ = Math.max(rl.qValues.BUY, rl.qValues.SELL, rl.qValues.HOLD);
  const bestAction = Object.entries(rl.qValues).sort(([, a], [, b]) => b - a)[0][0];

  return (
    <div className="space-y-6" dir="rtl">

      {/* Hero */}
      <div className="bg-gradient-to-br from-orange-600/20 via-red-600/20 to-pink-600/20 rounded-3xl p-8 border border-orange-400/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-l from-pink-500/5 to-transparent pointer-events-none" />
        <div className="relative">
          <h2 className="text-4xl font-black text-white mb-3">🎮 التعلم بالتعزيز (Deep Q-Network)</h2>
          <p className="text-orange-200 text-lg mb-4">
            الوكيل يتعلم التداول من خلال التجربة والخطأ بدون بيانات تدريب مسبقة — DQN with Experience Replay
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'حالة الـ Agent', value: rl.isTraining ? '⚡ يتدرب' : '✅ جاهز', color: rl.isTraining ? 'text-yellow-400' : 'text-emerald-400' },
              { label: 'Episode الحالي', value: `${rl.episode}/${rl.totalEpisodes}`, color: 'text-blue-400' },
              { label: 'Epsilon (ε)', value: rl.epsilon.toFixed(3), color: 'text-purple-400' },
              { label: 'Win Rate', value: `${rl.winRate}%`, color: rl.winRate > 60 ? 'text-emerald-400' : 'text-yellow-400' },
            ].map((m, i) => (
              <div key={i} className="bg-black/30 rounded-xl p-3 text-center">
                <div className={`text-xl font-black ${m.color}`}>{m.value}</div>
                <div className="text-gray-500 text-xs mt-1">{m.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live Q-Values */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">🎯 Q-Values الحالية (قيم الجودة)</h3>
        <div className="grid md:grid-cols-3 gap-4 mb-4">
          {Object.entries(rl.qValues).map(([action, qval]) => {
            const isBest = action === bestAction;
            return (
              <div
                key={action}
                className={`rounded-2xl p-5 border-2 text-center transition-all ${
                  isBest
                    ? actionBg(action)
                    : 'bg-white/3 border-white/10'
                }`}
              >
                <div className="text-2xl mb-2">
                  {action === 'BUY' ? '📈' : action === 'SELL' ? '📉' : '⏸️'}
                </div>
                <div className={`text-2xl font-black ${isBest ? actionColor(action) : 'text-gray-400'}`}>
                  {action}
                </div>
                <div className="text-white font-bold text-xl mt-1">{qval.toFixed(3)}</div>
                <div className="mt-2 h-2 bg-black/30 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${(qval / maxQ) * 100}%`,
                      background: action === 'BUY' ? '#10b981' : action === 'SELL' ? '#ef4444' : '#f59e0b'
                    }}
                  />
                </div>
                {isBest && <div className="text-xs text-white mt-1 font-bold">⭐ الأفضل</div>}
              </div>
            );
          })}
        </div>

        <div className={`rounded-xl p-4 border ${actionBg(rl.currentAction)}`}>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-gray-400 text-sm">القرار المُتخذ: </span>
              <span className={`text-2xl font-black ${actionColor(rl.currentAction)}`}>{rl.currentAction}</span>
            </div>
            <div className={`text-lg font-bold ${rl.currentReward >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              مكافأة: {rl.currentReward >= 0 ? '+' : ''}{rl.currentReward}
            </div>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Training Controls */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">⚙️ معاملات DQN</h3>
          <div className="space-y-3">
            {[
              { label: 'Learning Rate (α)', value: rl.learningRate, icon: '📚' },
              { label: 'Discount Factor (γ)', value: rl.gamma, icon: '⏳' },
              { label: 'Exploration Rate (ε)', value: rl.explorationRate, icon: '🎲' },
              { label: 'Replay Buffer', value: rl.replayBuffer.toLocaleString(), icon: '💾' },
              { label: 'State Space', value: `${rl.stateSpace} متغير`, icon: '🔢' },
              { label: 'Action Space', value: `${rl.actionSpace} (BUY/SELL/HOLD)`, icon: '🎯' },
            ].map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <div className="flex items-center gap-2">
                  <span>{item.icon}</span>
                  <span className="text-gray-400 text-sm">{item.label}</span>
                </div>
                <span className="text-white font-mono text-sm">{item.value}</span>
              </div>
            ))}
          </div>

          <button
            onClick={rl.startTraining}
            disabled={rl.isTraining}
            className="w-full mt-4 py-3 bg-gradient-to-r from-orange-600 to-red-600 text-white font-bold rounded-xl hover:opacity-90 transition-all disabled:opacity-50"
          >
            {rl.isTraining ? `⏳ تدريب... Episode ${rl.episode}/30` : '🚀 بدء تدريب الـ Agent'}
          </button>

          {rl.isTraining && (
            <div className="mt-3">
              <div className="h-2 bg-black/30 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-orange-500 to-red-500 rounded-full transition-all"
                  style={{ width: `${(rl.episode / 30) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Reward Curve */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">📈 منحنى المكافأة</h3>
          <RewardChart episodeReward={rl.episodeReward} avgReward={rl.avgReward} />
          <div className="flex gap-4 mt-2 text-xs justify-center">
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-purple-500 opacity-60" />
              <span className="text-gray-400">مكافأة كل Episode</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-emerald-500" />
              <span className="text-gray-400">المتوسط المتحرك</span>
            </div>
          </div>
          {rl.episode > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="bg-black/30 rounded-xl p-3 text-center">
                <div className="text-xs text-gray-500">إجمالي المكافأة</div>
                <div className={`font-bold ${rl.totalReward >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {rl.totalReward.toFixed(0)}
                </div>
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-center">
                <div className="text-xs text-gray-500">أفضل مكافأة</div>
                <div className="text-purple-400 font-bold">{rl.bestReward.toFixed(1)}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* DQN Architecture */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">🏗️ بنية شبكة DQN</h3>
        <div className="flex items-center justify-center gap-4 overflow-x-auto py-4">
          {rl.layers.map((layer, i) => (
            <div key={i} className="flex items-center gap-4">
              <div
                className="rounded-xl p-4 text-center border border-white/20 min-w-[90px] hover:scale-105 transition-all"
                style={{ background: `${layer.color}15`, borderColor: `${layer.color}40` }}
              >
                <div className="text-xs font-bold" style={{ color: layer.color }}>{layer.name}</div>
                <div className="text-white text-lg font-black mt-1">{layer.units}</div>
                <div className="text-gray-500 text-xs mt-0.5">units</div>

                {/* النقاط */}
                <div className="flex justify-center gap-1 mt-2">
                  {Array.from({ length: Math.min(layer.units as number, 5) }, (_, j) => (
                    <div
                      key={j}
                      className="w-2 h-2 rounded-full"
                      style={{ background: layer.color, opacity: 0.6 + j * 0.1 }}
                    />
                  ))}
                </div>
              </div>
              {i < rl.layers.length - 1 && (
                <div className="text-gray-600 text-xl">→</div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/20">
            <h4 className="text-blue-400 font-bold mb-2">📥 متغيرات الحالة (State)</h4>
            <div className="grid grid-cols-2 gap-1 text-xs text-gray-400">
              {['RSI', 'MACD', 'EMA Trend', 'ADX', 'ATR', 'Stoch', 'Regime', 'DD%', 'Spread', 'Hour', 'DayofWeek', 'BuyScore'].map(s => (
                <span key={s} className="flex items-center gap-1">
                  <span className="text-blue-400">•</span> {s}
                </span>
              ))}
            </div>
          </div>
          <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/20">
            <h4 className="text-emerald-400 font-bold mb-2">🎯 نظام المكافآت (Rewards)</h4>
            <div className="space-y-1 text-xs text-gray-400">
              <div className="flex justify-between"><span>صفقة رابحة:</span><span className="text-emerald-400">+profit × 100</span></div>
              <div className="flex justify-between"><span>صفقة خاسرة:</span><span className="text-red-400">+loss × 100</span></div>
              <div className="flex justify-between"><span>التداول في CHAOS:</span><span className="text-red-400">-10</span></div>
              <div className="flex justify-between"><span>HOLD في السوق الهادئ:</span><span className="text-yellow-400">-1</span></div>
              <div className="flex justify-between"><span>تجاوز حد الـ DD:</span><span className="text-red-400">-50</span></div>
              <div className="flex justify-between"><span>إشارة عالية الثقة:</span><span className="text-emerald-400">+5</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* RL vs Traditional */}
      <div className="bg-gradient-to-br from-orange-500/10 to-red-500/10 rounded-3xl p-6 border border-orange-400/30">
        <h3 className="text-lg font-bold text-white mb-4">🔄 RL vs التداول التقليدي</h3>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          {[
            { icon: '🧠', title: 'التكيف الذاتي', desc: 'يتكيف تلقائياً مع تغيرات السوق بدون إعادة برمجة يدوية' },
            { icon: '🎓', title: 'التعلم من الأخطاء', desc: 'كل خسارة هي درس يُحسّن قرارات المستقبل عبر Experience Replay' },
            { icon: '🏆', title: 'تحسين مستمر', desc: 'الـ Agent يتحسن مع كل episode ويصل لسياسة تداول مثلى' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-4">
              <div className="text-3xl mb-2">{item.icon}</div>
              <div className="text-white font-bold mb-1">{item.title}</div>
              <div className="text-gray-400">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
