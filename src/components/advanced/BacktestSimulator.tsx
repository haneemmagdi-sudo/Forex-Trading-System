import { useState, useMemo } from 'react';

// بيانات محاكاة واقعية
const PAIRS = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'GBP/JPY'];
const TIMEFRAMES = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1'];
const PERIODS = ['شهر 1', 'شهر 3', 'شهر 6', 'سنة 1', 'سنتان'];
const FSM_STATES = ['جميع الحالات', 'LOW VOL', 'HIGH VOL', 'SLOW TREND', 'STRONG TREND'];

// توليد بيانات واقعية للمحاكاة
function generateTradeData(seed: number, totalTrades: number) {
  const trades: { day: number; pnl: number; type: string; state: string; pips: number }[] = [];
  const random = (n: number) => (Math.sin(seed * n + 1.5) * 0.5 + 0.5);
  const states = ['LOW VOL', 'HIGH VOL', 'SLOW TREND', 'STRONG TREND'];
  let equity = 10000;

  for (let i = 0; i < totalTrades; i++) {
    const r = random(i + 1);
    const stateIdx = Math.floor(random(i + 7) * 4);
    const state = states[stateIdx];
    const isWin = r > 0.3; // ~70% win rate
    const pips = isWin
      ? Math.floor(random(i + 2) * 45 + 10)
      : -Math.floor(random(i + 3) * 20 + 5);
    const pnl = pips * 2.5;
    equity += pnl;

    trades.push({ day: i + 1, pnl, type: pips > 0 ? 'WIN' : 'LOSS', state, pips });
  }
  return trades;
}

function calcStats(trades: ReturnType<typeof generateTradeData>) {
  const wins = trades.filter(t => t.type === 'WIN');
  const losses = trades.filter(t => t.type === 'LOSS');
  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const grossWin = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));

  let peak = 0, maxDD = 0, running = 0;
  trades.forEach(t => {
    running += t.pnl;
    if (running > peak) peak = running;
    const dd = ((peak - running) / (10000 + peak)) * 100;
    if (dd > maxDD) maxDD = dd;
  });

  return {
    totalTrades: trades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: (wins.length / trades.length * 100).toFixed(1),
    totalPnl: totalPnl.toFixed(0),
    profitFactor: grossLoss > 0 ? (grossWin / grossLoss).toFixed(2) : '∞',
    maxDD: maxDD.toFixed(1),
    avgWin: wins.length > 0 ? (grossWin / wins.length).toFixed(1) : '0',
    avgLoss: losses.length > 0 ? (grossLoss / losses.length).toFixed(1) : '0',
    sharpe: (totalPnl / (trades.length * 3.5)).toFixed(2),
  };
}

// رسم بياني بسيط بـ SVG
function EquityCurve({ trades }: { trades: ReturnType<typeof generateTradeData> }) {
  const width = 800;
  const height = 200;
  const padding = 30;

  const cumulative = trades.reduce((acc, t, i) => {
    acc.push((acc[i - 1] ?? 0) + t.pnl);
    return acc;
  }, [] as number[]);

  const minVal = Math.min(...cumulative, 0);
  const maxVal = Math.max(...cumulative, 1);
  const range = maxVal - minVal || 1;

  const points = cumulative.map((v, i) => {
    const x = padding + (i / (cumulative.length - 1)) * (width - padding * 2);
    const y = padding + ((maxVal - v) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const zeroY = padding + ((maxVal - 0) / range) * (height - padding * 2);

  return (
    <div className="bg-black/40 rounded-xl p-4 overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: '400px' }}>
        {/* Zero line */}
        <line x1={padding} y1={Math.max(padding, Math.min(height - padding, zeroY))}
          x2={width - padding} y2={Math.max(padding, Math.min(height - padding, zeroY))}
          stroke="rgba(255,255,255,0.1)" strokeWidth="1" strokeDasharray="4,4" />

        {/* Area fill */}
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(139,92,246,0.6)" />
            <stop offset="100%" stopColor="rgba(139,92,246,0)" />
          </linearGradient>
        </defs>
        <path
          d={`M ${padding},${height - padding} L ${points.join(' L ')} L ${width - padding},${height - padding} Z`}
          fill="url(#equityGrad)"
        />

        {/* Line */}
        <polyline
          points={points.join(' ')}
          fill="none"
          stroke="rgba(139,92,246,1)"
          strokeWidth="2"
        />
      </svg>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>البداية</span>
        <span className="text-purple-400">منحنى الأرباح التراكمية</span>
        <span>النهاية</span>
      </div>
    </div>
  );
}

export default function BacktestSimulator() {
  const [pair, setPair] = useState(PAIRS[0]);
  const [timeframe, setTimeframe] = useState('H1');
  const [period, setPeriod] = useState('شهر 3');
  const [fsmFilter, setFsmFilter] = useState('جميع الحالات');
  const [riskPercent, setRiskPercent] = useState(1.0);
  const [running, setRunning] = useState(false);
  const [ran, setRan] = useState(false);
  const [seed, setSeed] = useState(42);

  const tradeCount = period === 'شهر 1' ? 45 : period === 'شهر 3' ? 135 : period === 'شهر 6' ? 270 : period === 'سنة 1' ? 540 : 1080;

  const allTrades = useMemo(() => generateTradeData(seed + pair.length, tradeCount), [seed, pair, tradeCount]);

  const trades = useMemo(() => {
    if (fsmFilter === 'جميع الحالات') return allTrades;
    return allTrades.filter(t => t.state === fsmFilter);
  }, [allTrades, fsmFilter]);

  const stats = useMemo(() => calcStats(trades), [trades]);

  const handleRun = () => {
    setRunning(true);
    setTimeout(() => {
      setSeed(s => s + 1);
      setRunning(false);
      setRan(true);
    }, 1500);
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-br from-indigo-500/20 to-blue-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h2 className="text-4xl font-bold text-white mb-2">📊 محاكي الاختبار الخلفي</h2>
        <p className="text-indigo-200 text-lg">اختبر الاستراتيجية على بيانات تاريخية وقيّم أداءها</p>
        <div className="mt-2 px-3 py-1 bg-yellow-500/10 border border-yellow-500/20 rounded-lg inline-block">
          <span className="text-yellow-400 text-sm">⚠️ المحاكاة تعليمية — تعتمد على بيانات إحصائية لأغراض التوضيح</span>
        </div>
      </div>

      {/* Settings Panel */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-xl font-bold text-white mb-4">⚙️ إعدادات الاختبار</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          {/* Pair */}
          <div>
            <label className="text-gray-400 text-sm block mb-2">زوج العملة</label>
            <select
              value={pair}
              onChange={e => setPair(e.target.value)}
              className="w-full bg-black/40 border border-white/10 text-white rounded-xl px-3 py-2 focus:outline-none focus:border-purple-400"
            >
              {PAIRS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          {/* Timeframe */}
          <div>
            <label className="text-gray-400 text-sm block mb-2">الإطار الزمني</label>
            <select
              value={timeframe}
              onChange={e => setTimeframe(e.target.value)}
              className="w-full bg-black/40 border border-white/10 text-white rounded-xl px-3 py-2 focus:outline-none focus:border-purple-400"
            >
              {TIMEFRAMES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {/* Period */}
          <div>
            <label className="text-gray-400 text-sm block mb-2">فترة الاختبار</label>
            <select
              value={period}
              onChange={e => setPeriod(e.target.value)}
              className="w-full bg-black/40 border border-white/10 text-white rounded-xl px-3 py-2 focus:outline-none focus:border-purple-400"
            >
              {PERIODS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          {/* FSM Filter */}
          <div>
            <label className="text-gray-400 text-sm block mb-2">تصفية حسب FSM</label>
            <select
              value={fsmFilter}
              onChange={e => setFsmFilter(e.target.value)}
              className="w-full bg-black/40 border border-white/10 text-white rounded-xl px-3 py-2 focus:outline-none focus:border-purple-400"
            >
              {FSM_STATES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {/* Risk */}
          <div>
            <label className="text-gray-400 text-sm block mb-2">المخاطرة % لكل صفقة: <span className="text-purple-400 font-bold">{riskPercent}%</span></label>
            <input
              type="range" min={0.5} max={3} step={0.5} value={riskPercent}
              onChange={e => setRiskPercent(Number(e.target.value))}
              className="w-full accent-purple-500"
            />
          </div>
          {/* Run Button */}
          <div className="flex items-end">
            <button
              onClick={handleRun}
              disabled={running}
              className="w-full py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 text-white font-bold rounded-xl transition-all"
            >
              {running ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  جارٍ الاختبار...
                </span>
              ) : '▶ تشغيل الاختبار'}
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {(ran || true) && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { label: 'Win Rate', value: `${stats.winRate}%`, color: 'text-emerald-400', bg: 'from-emerald-500/10 to-green-500/5', border: 'border-emerald-500/20' },
              { label: 'إجمالي الربح', value: `$${Number(stats.totalPnl).toLocaleString()}`, color: Number(stats.totalPnl) > 0 ? 'text-emerald-400' : 'text-red-400', bg: 'from-blue-500/10 to-cyan-500/5', border: 'border-blue-500/20' },
              { label: 'Profit Factor', value: stats.profitFactor, color: 'text-purple-400', bg: 'from-purple-500/10 to-violet-500/5', border: 'border-purple-500/20' },
              { label: 'Max Drawdown', value: `${stats.maxDD}%`, color: 'text-yellow-400', bg: 'from-yellow-500/10 to-amber-500/5', border: 'border-yellow-500/20' },
              { label: 'Sharpe Ratio', value: stats.sharpe, color: 'text-pink-400', bg: 'from-pink-500/10 to-rose-500/5', border: 'border-pink-500/20' },
            ].map((kpi, i) => (
              <div key={i} className={`bg-gradient-to-br ${kpi.bg} border ${kpi.border} rounded-xl p-4 text-center`}>
                <div className={`text-2xl font-black ${kpi.color}`}>{kpi.value}</div>
                <div className="text-gray-400 text-xs mt-1">{kpi.label}</div>
              </div>
            ))}
          </div>

          {/* Equity Curve */}
          <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
            <h4 className="text-white font-bold mb-4">📈 منحنى الأرباح التراكمية — {pair} {timeframe}</h4>
            <EquityCurve trades={trades} />
          </div>

          {/* Trade Statistics */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
              <h4 className="text-white font-bold mb-4">📋 إحصائيات تفصيلية</h4>
              <table className="w-full text-sm">
                <tbody>
                  {[
                    { label: 'إجمالي الصفقات', val: stats.totalTrades },
                    { label: 'صفقات رابحة', val: `${stats.wins} ✅` },
                    { label: 'صفقات خاسرة', val: `${stats.losses} ❌` },
                    { label: 'متوسط الربح', val: `$${stats.avgWin}` },
                    { label: 'متوسط الخسارة', val: `-$${stats.avgLoss}` },
                  ].map((r, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-2 text-gray-400">{r.label}</td>
                      <td className="py-2 text-white font-semibold text-left">{r.val}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Distribution by FSM State */}
            <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
              <h4 className="text-white font-bold mb-4">🔍 الأداء حسب حالة FSM</h4>
              {['LOW VOL', 'HIGH VOL', 'SLOW TREND', 'STRONG TREND'].map((state, i) => {
                const stateTrades = allTrades.filter(t => t.state === state);
                const stateWins = stateTrades.filter(t => t.type === 'WIN');
                const wr = stateTrades.length > 0 ? (stateWins.length / stateTrades.length * 100).toFixed(0) : '0';
                const colors = ['text-yellow-400', 'text-orange-400', 'text-blue-400', 'text-emerald-400'];
                return (
                  <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5">
                    <span className={`text-xs font-bold ${colors[i]} w-28 flex-shrink-0`}>{state}</span>
                    <div className="flex-1 bg-black/30 rounded-full h-2 overflow-hidden">
                      <div className={`h-2 rounded-full bg-gradient-to-r ${['from-yellow-500 to-yellow-400', 'from-orange-500 to-orange-400', 'from-blue-500 to-blue-400', 'from-emerald-500 to-emerald-400'][i]}`}
                        style={{ width: `${wr}%` }} />
                    </div>
                    <span className={`text-sm font-bold ${colors[i]} w-12 text-right`}>{wr}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Trades */}
          <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
            <h4 className="text-white font-bold mb-4">🗂️ آخر 15 صفقة</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-gray-400">
                    <th className="text-right py-2 px-3">#</th>
                    <th className="text-right py-2 px-3">الحالة FSM</th>
                    <th className="text-right py-2 px-3">النقاط</th>
                    <th className="text-right py-2 px-3">الربح/الخسارة</th>
                    <th className="text-right py-2 px-3">النتيجة</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.slice(-15).reverse().map((t, i) => (
                    <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                      <td className="py-1.5 px-3 text-gray-500">{t.day}</td>
                      <td className="py-1.5 px-3 text-gray-300">{t.state}</td>
                      <td className={`py-1.5 px-3 font-mono ${t.pips > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {t.pips > 0 ? '+' : ''}{t.pips}
                      </td>
                      <td className={`py-1.5 px-3 font-mono ${t.pnl > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(0)}
                      </td>
                      <td className="py-1.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${t.type === 'WIN' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                          {t.type === 'WIN' ? '✓ ربح' : '✗ خسارة'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
