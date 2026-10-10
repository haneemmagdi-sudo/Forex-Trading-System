import { useState } from 'react';

// بيانات تقرير الأداء المحاكاة
const MONTHLY_DATA = [
  { month: 'يناير', pnl: 420, winRate: 72, trades: 48, dd: 3.1 },
  { month: 'فبراير', pnl: 680, winRate: 78, trades: 52, dd: 2.4 },
  { month: 'مارس', pnl: -120, winRate: 61, trades: 45, dd: 5.8 },
  { month: 'أبريل', pnl: 890, winRate: 81, trades: 60, dd: 1.9 },
  { month: 'مايو', pnl: 1100, winRate: 85, trades: 55, dd: 1.5 },
  { month: 'يونيو', pnl: 740, winRate: 76, trades: 50, dd: 2.8 },
];

const SESSION_DATA = [
  { session: 'لندن 🇬🇧', winRate: 78, trades: 142, pnl: 1240, color: 'from-blue-500 to-blue-400' },
  { session: 'نيويورك 🇺🇸', winRate: 74, trades: 118, pnl: 980, color: 'from-green-500 to-green-400' },
  { session: 'التداخل 🌍', winRate: 83, trades: 85, pnl: 1450, color: 'from-purple-500 to-purple-400' },
  { session: 'طوكيو 🇯🇵', winRate: 65, trades: 67, pnl: 340, color: 'from-red-500 to-orange-400' },
];

const FSM_DATA = [
  { state: 'STRONG TREND 🚀', winRate: 86, trades: 85, avgPips: 45, color: 'text-emerald-400', barColor: 'bg-emerald-500' },
  { state: 'LOW VOL 🟡', winRate: 79, trades: 148, avgPips: 18, color: 'text-yellow-400', barColor: 'bg-yellow-500' },
  { state: 'SLOW TREND 🔵', winRate: 74, trades: 112, avgPips: 32, color: 'text-blue-400', barColor: 'bg-blue-500' },
  { state: 'HIGH VOL ⚠️', winRate: 62, trades: 67, avgPips: 58, color: 'text-orange-400', barColor: 'bg-orange-500' },
  { state: 'CHAOS 🔴', winRate: 0, trades: 0, avgPips: 0, color: 'text-red-400', barColor: 'bg-red-500' },
];

const PAIR_DATA = [
  { pair: 'EUR/USD', winRate: 78, trades: 145, pnl: 1380, spread: 0.8 },
  { pair: 'GBP/USD', winRate: 72, trades: 98, pnl: 870, spread: 1.2 },
  { pair: 'USD/JPY', winRate: 75, trades: 112, pnl: 940, spread: 0.9 },
  { pair: 'AUD/USD', winRate: 68, trades: 57, pnl: 420, spread: 1.0 },
];

// Bar Chart SVG
function BarChart({ data, height = 160 }: { data: { label: string; value: number; color: string }[]; height?: number }) {
  const max = Math.max(...data.map(d => d.value), 1);
  const width = data.length * 60 + 20;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${Math.max(width, 300)} ${height + 30}`} className="w-full" style={{ minWidth: '300px' }}>
        {data.map((d, i) => {
          const barHeight = (d.value / max) * height;
          const x = i * 60 + 20;
          const y = height - barHeight;
          return (
            <g key={i}>
              <rect x={x} y={y} width={40} height={barHeight} rx={4}
                fill={d.color} opacity={0.8} />
              <text x={x + 20} y={height + 20} textAnchor="middle" fontSize="9" fill="#9ca3af">
                {d.label}
              </text>
              <text x={x + 20} y={y - 4} textAnchor="middle" fontSize="9" fill="#e5e7eb">
                {d.value}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function PerformanceReport() {
  const [activeView, setActiveView] = useState<'overview' | 'monthly' | 'session' | 'pair' | 'fsm'>('overview');
  const [copiedReport, setCopiedReport] = useState(false);

  const totalPnl = MONTHLY_DATA.reduce((s, m) => s + m.pnl, 0);
  const avgWinRate = (MONTHLY_DATA.reduce((s, m) => s + m.winRate, 0) / MONTHLY_DATA.length).toFixed(1);
  const maxDD = Math.max(...MONTHLY_DATA.map(m => m.dd));
  const totalTrades = MONTHLY_DATA.reduce((s, m) => s + m.trades, 0);

  const handleCopyReport = () => {
    const report = `📊 تقرير أداء Blessing Pro V4.2\n\n` +
      `💰 إجمالي الربح: $${totalPnl.toLocaleString()}\n` +
      `🎯 Win Rate: ${avgWinRate}%\n` +
      `📉 Max Drawdown: ${maxDD}%\n` +
      `📋 إجمالي الصفقات: ${totalTrades}\n\n` +
      `الأداء الشهري:\n` +
      MONTHLY_DATA.map(m => `${m.month}: $${m.pnl} | WR: ${m.winRate}%`).join('\n');
    navigator.clipboard.writeText(report).then(() => {
      setCopiedReport(true);
      setTimeout(() => setCopiedReport(false), 2000);
    });
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-br from-amber-500/20 to-orange-500/20 rounded-3xl p-8 border border-amber-400/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-4xl font-bold text-white mb-2">🏆 تقرير الأداء الشامل</h2>
            <p className="text-amber-200 text-lg">تحليل مفصل للأداء حسب الشهر، الجلسة، الزوج، وحالة FSM</p>
          </div>
          <button
            onClick={handleCopyReport}
            className={`px-5 py-3 font-bold text-sm rounded-xl transition-all ${copiedReport ? 'bg-emerald-500/30 text-emerald-400 border border-emerald-400/40' : 'bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/30 text-amber-300'}`}
          >
            {copiedReport ? '✅ تم نسخ التقرير!' : '📋 نسخ التقرير'}
          </button>
        </div>
      </div>

      {/* KPI Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'إجمالي الربح (6 أشهر)', value: `$${totalPnl.toLocaleString()}`, icon: '💰', color: 'text-emerald-400', bg: 'from-emerald-500/10 to-green-500/5', border: 'border-emerald-500/20' },
          { label: 'متوسط Win Rate', value: `${avgWinRate}%`, icon: '🎯', color: 'text-purple-400', bg: 'from-purple-500/10 to-violet-500/5', border: 'border-purple-500/20' },
          { label: 'أقصى Drawdown', value: `${maxDD}%`, icon: '📉', color: 'text-yellow-400', bg: 'from-yellow-500/10 to-amber-500/5', border: 'border-yellow-500/20' },
          { label: 'إجمالي الصفقات', value: totalTrades, icon: '📋', color: 'text-blue-400', bg: 'from-blue-500/10 to-cyan-500/5', border: 'border-blue-500/20' },
        ].map((kpi, i) => (
          <div key={i} className={`bg-gradient-to-br ${kpi.bg} border ${kpi.border} rounded-2xl p-5 text-center`}>
            <div className="text-2xl mb-2">{kpi.icon}</div>
            <div className={`text-2xl font-black ${kpi.color}`}>{kpi.value}</div>
            <div className="text-gray-500 text-xs mt-1">{kpi.label}</div>
          </div>
        ))}
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 overflow-x-auto scrollbar-hide">
        {[
          { key: 'overview', label: '📊 نظرة عامة' },
          { key: 'monthly', label: '📅 شهري' },
          { key: 'session', label: '⏰ الجلسات' },
          { key: 'pair', label: '💱 الأزواج' },
          { key: 'fsm', label: '🔍 حسب FSM' },
        ].map(v => (
          <button
            key={v.key}
            onClick={() => setActiveView(v.key as any)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${activeView === v.key ? 'bg-amber-500/20 border border-amber-400/40 text-amber-300' : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white'}`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {activeView === 'overview' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
            <h4 className="text-white font-bold mb-4">📈 الربح الشهري</h4>
            <BarChart
              data={MONTHLY_DATA.map(m => ({
                label: m.month.slice(0, 3),
                value: Math.max(m.pnl, 0),
                color: m.pnl >= 0 ? '#10b981' : '#ef4444'
              }))}
            />
          </div>
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
            <h4 className="text-white font-bold mb-4">🎯 Win Rate الشهري</h4>
            <BarChart
              data={MONTHLY_DATA.map(m => ({ label: m.month.slice(0, 3), value: m.winRate, color: '#8b5cf6' }))}
            />
          </div>
        </div>
      )}

      {/* Monthly Detail */}
      {activeView === 'monthly' && (
        <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-white/10">
              <tr>
                {['الشهر', 'الربح/الخسارة', 'Win Rate', 'الصفقات', 'Max DD'].map(h => (
                  <th key={h} className="text-right py-3 px-4 text-gray-400 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MONTHLY_DATA.map((m, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-3 px-4 text-white font-medium">{m.month}</td>
                  <td className={`py-3 px-4 font-bold font-mono ${m.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {m.pnl >= 0 ? '+' : ''}${m.pnl}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-black/30 rounded-full h-1.5">
                        <div className="bg-purple-500 h-1.5 rounded-full" style={{ width: `${m.winRate}%` }} />
                      </div>
                      <span className="text-purple-400">{m.winRate}%</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-white">{m.trades}</td>
                  <td className={`py-3 px-4 ${m.dd > 4 ? 'text-red-400' : m.dd > 2.5 ? 'text-yellow-400' : 'text-emerald-400'}`}>{m.dd}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sessions */}
      {activeView === 'session' && (
        <div className="grid md:grid-cols-2 gap-4">
          {SESSION_DATA.map((s, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-5">
              <h4 className="text-white font-bold text-lg mb-3">{s.session}</h4>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Win Rate</span>
                  <span className="text-purple-400 font-bold">{s.winRate}%</span>
                </div>
                <div className="w-full bg-black/30 rounded-full h-2">
                  <div className={`h-2 rounded-full bg-gradient-to-r ${s.color}`} style={{ width: `${s.winRate}%` }} />
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-gray-400">الصفقات</span><span className="text-white">{s.trades}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">الربح</span><span className="text-emerald-400 font-bold">+${s.pnl}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pairs */}
      {activeView === 'pair' && (
        <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-white/10">
              <tr>
                {['الزوج', 'Win Rate', 'الصفقات', 'الربح', 'السبريد'].map(h => (
                  <th key={h} className="text-right py-3 px-4 text-gray-400 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PAIR_DATA.map((p, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-3 px-4 text-white font-bold">{p.pair}</td>
                  <td className="py-3 px-4 text-purple-400">{p.winRate}%</td>
                  <td className="py-3 px-4 text-white">{p.trades}</td>
                  <td className="py-3 px-4 text-emerald-400 font-bold">+${p.pnl}</td>
                  <td className="py-3 px-4 text-gray-400">{p.spread}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* FSM Performance */}
      {activeView === 'fsm' && (
        <div className="space-y-3">
          {FSM_DATA.map((f, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h4 className={`font-bold text-lg ${f.color}`}>{f.state}</h4>
                <div className="flex gap-4 text-sm text-right">
                  <span className="text-gray-400">{f.trades} صفقة</span>
                  <span className="text-white font-bold">متوسط: {f.avgPips} pip</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-gray-400 text-xs w-16">Win Rate</span>
                <div className="flex-1 bg-black/30 rounded-full h-3 overflow-hidden">
                  <div className={`h-3 rounded-full ${f.barColor} transition-all duration-500`} style={{ width: `${f.winRate}%` }} />
                </div>
                <span className={`font-bold text-sm ${f.color} w-10 text-right`}>{f.winRate}%</span>
              </div>
            </div>
          ))}
          <div className="bg-gradient-to-r from-emerald-500/10 to-green-500/5 border border-emerald-500/20 rounded-2xl p-4 text-sm text-emerald-300">
            💡 <strong>التوصية:</strong> STRONG TREND هو أفضل حالة للتداول (86% Win Rate). تجنب HIGH VOL قدر الإمكان.
          </div>
        </div>
      )}
    </div>
  );
}
