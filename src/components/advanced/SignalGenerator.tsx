import { useState, useEffect, useRef } from 'react';

const INDICATORS = [
  { key: 'ema', label: 'EMA Trend', weight: 1.0 },
  { key: 'ha', label: 'Heiken Ashi', weight: 2.0 },
  { key: 'macd', label: 'MACD', weight: 0.6 },
  { key: 'rsi', label: 'RSI', weight: 0.8 },
  { key: 'adx', label: 'ADX + DI±', weight: 0.7 },
  { key: 'ichi', label: 'Ichimoku', weight: 0.8 },
  { key: 'smc', label: 'SMC Order Block', weight: 1.0 },
  { key: 'momentum', label: 'Momentum', weight: 0.5 },
  { key: 'st', label: 'SuperTrend', weight: 1.0 },
];

const FSM_REGIMES = ['LOW_VOL_RANGE', 'HIGH_VOL_RANGE', 'SLOW_TREND', 'STRONG_TREND', 'CHAOS'];

const regimeWeightMultipliers: Record<string, Record<string, number>> = {
  LOW_VOL_RANGE:  { ema: 1.0, ha: 1.5, macd: 0.5, rsi: 1.3, adx: 0.4, ichi: 0.8, smc: 1.0, momentum: 0.5, st: 1.0 },
  HIGH_VOL_RANGE: { ema: 1.0, ha: 2.0, macd: 0.6, rsi: 0.5, adx: 1.4, ichi: 0.8, smc: 1.0, momentum: 0.7, st: 1.0 },
  SLOW_TREND:     { ema: 1.3, ha: 2.0, macd: 0.9, rsi: 0.8, adx: 0.7, ichi: 1.2, smc: 1.0, momentum: 0.5, st: 1.0 },
  STRONG_TREND:   { ema: 1.6, ha: 2.5, macd: 0.6, rsi: 0.4, adx: 0.7, ichi: 1.0, smc: 1.0, momentum: 0.9, st: 1.0 },
  CHAOS:          { ema: 0.4, ha: 1.0, macd: 0.2, rsi: 0.3, adx: 0.3, ichi: 0.8, smc: 1.0, momentum: 0.2, st: 1.0 },
};

type VoteValue = 'buy' | 'sell' | 'neutral';

export default function SignalGenerator() {
  const [regime, setRegime] = useState('STRONG_TREND');
  const [votes, setVotes] = useState<Record<string, VoteValue>>(
    Object.fromEntries(INDICATORS.map(i => [i.key, 'buy']))
  );
  const [running, setRunning] = useState(false);
  const [signal, setSignal] = useState<null | { direction: string; confidence: number; buyScore: number; sellScore: number; totalWeight: number }>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const audioRef = useRef<AudioContext | null>(null);

  function playBeep(type: 'buy' | 'sell') {
    try {
      if (!audioRef.current) audioRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      const ctx = audioRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = type === 'buy' ? 880 : 440;
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.4);
    } catch { /* silent */ }
  }

  function calcSignal() {
    const mults = regimeWeightMultipliers[regime];
    let buyScore = 0, sellScore = 0, totalWeight = 0;

    INDICATORS.forEach(ind => {
      const w = ind.weight * (mults[ind.key] ?? 1.0);
      totalWeight += w;
      if (votes[ind.key] === 'buy') buyScore += w;
      else if (votes[ind.key] === 'sell') sellScore += w;
    });

    const direction = buyScore > sellScore
      ? (buyScore / totalWeight > 0.5 ? 'BUY' : 'WEAK BUY')
      : sellScore > buyScore
        ? (sellScore / totalWeight > 0.5 ? 'SELL' : 'WEAK SELL')
        : 'NO TRADE';

    const confidence = (Math.max(buyScore, sellScore) / totalWeight) * 100;

    return { direction, confidence, buyScore, sellScore, totalWeight };
  }

  const handleGenerate = () => {
    setRunning(true);
    setTimeout(() => {
      const result = calcSignal();
      setSignal(result);
      setRunning(false);

      if (result.direction.includes('BUY')) {
        playBeep('buy');
        setNotification('✅ إشارة شراء قوية! تحقق من السبريد والوقت قبل الدخول.');
      } else if (result.direction.includes('SELL')) {
        playBeep('sell');
        setNotification('🔴 إشارة بيع! انتبه لمستويات الدعم القريبة.');
      } else {
        setNotification('⚪ لا توجد إشارة واضحة — انتظر تحسن الظروف.');
      }
      setTimeout(() => setNotification(null), 5000);
    }, 1000);
  };

  const handleAutoVote = () => {
    const randomVotes: Record<string, VoteValue> = {};
    const options: VoteValue[] = ['buy', 'sell', 'neutral'];
    INDICATORS.forEach(ind => {
      const r = Math.random();
      randomVotes[ind.key] = r > 0.55 ? 'buy' : r > 0.25 ? 'sell' : 'neutral';
    });
    setVotes(randomVotes);
  };

  const signalColors = {
    'BUY': { text: 'text-emerald-400', bg: 'from-emerald-500/20 to-green-500/10', border: 'border-emerald-500/40', emoji: '🟢' },
    'WEAK BUY': { text: 'text-teal-400', bg: 'from-teal-500/20 to-green-500/10', border: 'border-teal-500/40', emoji: '🟡' },
    'SELL': { text: 'text-red-400', bg: 'from-red-500/20 to-rose-500/10', border: 'border-red-500/40', emoji: '🔴' },
    'WEAK SELL': { text: 'text-orange-400', bg: 'from-orange-500/20 to-yellow-500/10', border: 'border-orange-500/40', emoji: '🟠' },
    'NO TRADE': { text: 'text-gray-400', bg: 'from-gray-500/10 to-slate-500/5', border: 'border-gray-500/30', emoji: '⚪' },
  };

  const regimeLabels: Record<string, string> = {
    LOW_VOL_RANGE: '🟡 LOW VOL — تذبذب بطيء',
    HIGH_VOL_RANGE: '⚠️ HIGH VOL — تذبذب سريع',
    SLOW_TREND: '🔵 SLOW TREND — ترند بطيء',
    STRONG_TREND: '🚀 STRONG TREND — ترند قوي',
    CHAOS: '🔴 CHAOS — لا تداول',
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-br from-pink-500/20 to-rose-500/20 rounded-3xl p-8 border border-pink-400/30">
        <h2 className="text-4xl font-bold text-white mb-2">🎯 مولّد الإشارات التفاعلي</h2>
        <p className="text-pink-200 text-lg">حدد حالة السوق وتصويت كل مؤشر لتوليد إشارة BUY/SELL</p>
      </div>

      {/* Notification */}
      {notification && (
        <div className="bg-purple-500/20 border border-purple-400/40 rounded-xl p-4 text-purple-200 font-medium animate-pulse">
          🔔 {notification}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Left: Controls */}
        <div className="space-y-4">
          {/* FSM Regime Selector */}
          <div className="bg-white/5 rounded-2xl p-5 border border-white/10">
            <h3 className="text-lg font-bold text-white mb-3">🔍 حالة السوق (FSM Regime)</h3>
            <div className="space-y-2">
              {FSM_REGIMES.map(r => (
                <button
                  key={r}
                  onClick={() => setRegime(r)}
                  className={`w-full text-right px-4 py-2.5 rounded-xl border transition-all text-sm font-semibold ${
                    regime === r
                      ? 'bg-purple-500/20 border-purple-400/60 text-purple-300'
                      : 'bg-black/20 border-white/5 text-gray-400 hover:border-white/20 hover:text-white'
                  }`}
                >
                  {regimeLabels[r]}
                </button>
              ))}
            </div>
          </div>

          {/* Auto Vote Button */}
          <button
            onClick={handleAutoVote}
            className="w-full py-2.5 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-400/30 text-blue-300 font-semibold rounded-xl transition-all"
          >
            🎲 محاكاة عشوائية للتصويت
          </button>
        </div>

        {/* Right: Voting Panel */}
        <div className="bg-white/5 rounded-2xl p-5 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-3">⚖️ مجلس التصويت</h3>
          <div className="space-y-2">
            {INDICATORS.map(ind => {
              const mults = regimeWeightMultipliers[regime];
              const w = ind.weight * (mults[ind.key] ?? 1.0);
              return (
                <div key={ind.key} className="flex items-center gap-2">
                  <span className="text-gray-300 text-xs w-28 flex-shrink-0">{ind.label}</span>
                  <span className="text-gray-600 text-xs w-8 flex-shrink-0 text-center">{w.toFixed(1)}×</span>
                  <div className="flex gap-1 flex-1">
                    {(['buy', 'neutral', 'sell'] as VoteValue[]).map(v => (
                      <button
                        key={v}
                        onClick={() => setVotes(prev => ({ ...prev, [ind.key]: v }))}
                        className={`flex-1 py-1 rounded-lg text-xs font-bold transition-all ${
                          votes[ind.key] === v
                            ? v === 'buy' ? 'bg-emerald-500/40 text-emerald-300 border border-emerald-400/60'
                              : v === 'sell' ? 'bg-red-500/40 text-red-300 border border-red-400/60'
                              : 'bg-gray-500/40 text-gray-300 border border-gray-400/60'
                            : 'bg-black/20 text-gray-600 border border-white/5 hover:border-white/20'
                        }`}
                      >
                        {v === 'buy' ? '▲' : v === 'sell' ? '▼' : '—'}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Generate Button */}
      <button
        onClick={handleGenerate}
        disabled={running}
        className="w-full py-4 text-xl font-bold bg-gradient-to-r from-purple-600 via-pink-600 to-red-600 hover:from-purple-500 hover:via-pink-500 hover:to-red-500 disabled:opacity-50 text-white rounded-2xl shadow-2xl shadow-purple-500/30 hover:shadow-purple-500/50 hover:-translate-y-1 transition-all duration-300"
      >
        {running ? (
          <span className="flex items-center justify-center gap-3">
            <span className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            جارٍ التحليل...
          </span>
        ) : '⚡ توليد الإشارة الآن'}
      </button>

      {/* Signal Result */}
      {signal && (
        <div className={`bg-gradient-to-br ${(signalColors[signal.direction as keyof typeof signalColors] || signalColors['NO TRADE']).bg} border ${(signalColors[signal.direction as keyof typeof signalColors] || signalColors['NO TRADE']).border} rounded-3xl p-8`}>
          <div className="text-center mb-6">
            <div className="text-6xl mb-3">{(signalColors[signal.direction as keyof typeof signalColors] || signalColors['NO TRADE']).emoji}</div>
            <div className={`text-5xl font-black ${(signalColors[signal.direction as keyof typeof signalColors] || signalColors['NO TRADE']).text} mb-2`}>
              {signal.direction}
            </div>
            <div className="text-gray-400 text-lg">
              الثقة: <span className={`font-bold text-xl ${(signalColors[signal.direction as keyof typeof signalColors] || signalColors['NO TRADE']).text}`}>{signal.confidence.toFixed(1)}%</span>
            </div>
          </div>

          {/* Score Bar */}
          <div className="space-y-2 mb-6">
            <div className="flex justify-between text-sm text-gray-400">
              <span>🟢 شراء: {signal.buyScore.toFixed(2)}</span>
              <span>🔴 بيع: {signal.sellScore.toFixed(2)}</span>
            </div>
            <div className="h-4 bg-black/40 rounded-full overflow-hidden flex">
              <div
                className="bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-500"
                style={{ width: `${(signal.buyScore / signal.totalWeight) * 100}%` }}
              />
              <div
                className="bg-gradient-to-r from-red-400 to-red-600 transition-all duration-500"
                style={{ width: `${(signal.sellScore / signal.totalWeight) * 100}%` }}
              />
            </div>
            <div className="text-center text-gray-500 text-xs">من إجمالي وزن {signal.totalWeight.toFixed(2)}</div>
          </div>

          {/* Voting Breakdown */}
          <div className="grid grid-cols-3 gap-2">
            {INDICATORS.map(ind => {
              const mults = regimeWeightMultipliers[regime];
              const w = ind.weight * (mults[ind.key] ?? 1.0);
              const v = votes[ind.key];
              return (
                <div key={ind.key} className={`bg-black/20 rounded-xl p-3 text-center border ${v === 'buy' ? 'border-emerald-500/30' : v === 'sell' ? 'border-red-500/30' : 'border-white/5'}`}>
                  <div className={`text-lg font-bold ${v === 'buy' ? 'text-emerald-400' : v === 'sell' ? 'text-red-400' : 'text-gray-500'}`}>
                    {v === 'buy' ? '▲' : v === 'sell' ? '▼' : '—'}
                  </div>
                  <div className="text-white text-xs font-semibold mt-1">{ind.label}</div>
                  <div className="text-gray-500 text-xs">{w.toFixed(1)}×</div>
                </div>
              );
            })}
          </div>

          {/* Regime Impact */}
          <div className="mt-4 p-4 bg-black/20 rounded-xl">
            <div className="text-sm text-gray-400">
              🔍 حالة FSM المحددة: <span className="text-white font-bold">{regimeLabels[regime]}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              الأوزان مُعدَّلة تلقائياً بناءً على الـ Regime الحالي
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
