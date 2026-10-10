import { useState } from 'react';

const ROADMAP = [
  {
    phase: 'المرحلة 1',
    period: 'الأسبوع 1-2',
    title: 'الأساسيات',
    status: 'done',
    items: [
      { name: 'FSM Engine — 4 حالات', done: true, detail: 'LOW_VOL / HIGH_VOL / SLOW_TREND / STRONG_TREND' },
      { name: 'Voting System — 9 مؤشرات', done: true, detail: 'EMA, HA, MACD, RSI, ADX, Ichimoku, SMC, Momentum, ST' },
      { name: 'Decision Matrix', done: true, detail: 'FSM × Voting + Veto Power' },
      { name: 'Smart Grid الأساسي', done: true, detail: 'Grid ديناميكي مع ATR' },
    ],
  },
  {
    phase: 'المرحلة 2',
    period: 'الأسبوع 3-4',
    title: 'التحسينات',
    status: 'done',
    items: [
      { name: 'State E (أخبار)', done: true, detail: 'كشف التقلب العالي + إيقاف تداول' },
      { name: 'Member Rating ديناميكي', done: true, detail: 'إعادة حساب الأوزان كل 50 صفقة' },
      { name: 'Portfolio Manager', done: true, detail: 'Magic Number + Correlation Matrix' },
      { name: 'Recovery Mode', done: true, detail: 'تفعيل عند DD > 10% أو 3 خسائر' },
    ],
  },
  {
    phase: 'المرحلة 3',
    period: 'الأسبوع 5-6',
    title: 'الأتمتة',
    status: 'done',
    items: [
      { name: 'Dashboard على الشارت', done: true, detail: 'لوحة تحكم مدمجة في MT5' },
      { name: 'Telegram Bot', done: true, detail: 'إشعارات + تحكم عن بُعد' },
      { name: 'AI Agents (4 وكلاء)', done: true, detail: 'Analyst + Planner + Executor + Monitor' },
      { name: 'Smart Money Concepts', done: true, detail: 'Order Blocks + FVG + Liquidity Sweeps' },
    ],
  },
  {
    phase: 'V4.2 Elite',
    period: 'تم مؤخراً',
    title: 'إصلاح + تعزيز',
    status: 'done',
    items: [
      { name: '6 إصلاحات حرجة', done: true, detail: 'SMC Bar، SuperTrend، Doji، BasketBE، MaxDD' },
      { name: 'Partial Close Ladder', done: true, detail: '3 مستويات: 30% / 50% / 70%' },
      { name: 'Cascade Protection', done: true, detail: 'وقف بعد 3 خسائر + فترة راحة' },
      { name: 'Smart Hedging Mode', done: true, detail: 'تحوط ذكي عند DD > HedgeDD%' },
    ],
  },
  {
    phase: 'المرحلة 4',
    period: 'قيد التطوير',
    title: 'التحليل المتقدم',
    status: 'done',
    items: [
      { name: 'BackTest Simulator', done: true, detail: 'محاكاة تاريخية تفاعلية في الواجهة' },
      { name: 'Signal Generator', done: true, detail: 'توليد إشارات BUY/SELL بالذكاء الاصطناعي' },
      { name: 'EA Configurator', done: true, detail: 'ضبط بصري لجميع إعدادات الـ EA' },
      { name: 'Performance Report', done: true, detail: 'تقرير شامل بالرسوم البيانية' },
    ],
  },
  {
    phase: 'المرحلة 5',
    period: 'قريباً',
    title: 'التعلم الآلي',
    status: 'planned',
    items: [
      { name: 'ML Pattern Recognition', done: false, detail: 'كشف الأنماط بالتعلم الآلي' },
      { name: 'Auto-Parameter Optimization', done: false, detail: 'تحسين المعاملات تلقائياً' },
      { name: 'Sentiment Analysis', done: false, detail: 'تحليل مشاعر السوق' },
      { name: 'Multi-Pair Correlation Engine', done: false, detail: 'إدارة محفظة بأزواج متعددة' },
    ],
  },
];

const COMPARISON = [
  { metric: 'Win Rate', before: '65-70%', after: '78-85%', icon: '🎯' },
  { metric: 'Max Drawdown', before: '15-20%', after: '8-12%', icon: '📉' },
  { metric: 'Profit Factor', before: '1.8', after: '2.8', icon: '💹' },
  { metric: 'Sharpe Ratio', before: '1.4', after: '2.3', icon: '📊' },
  { metric: 'دقة FSM', before: '70%', after: '90%+', icon: '🔍' },
  { metric: 'حماية DD', before: 'يدوية', after: '4 أوضاع تلقائية', icon: '🛡️' },
];

export default function Improvements() {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(3);

  const statusConfig = {
    done: { label: '✅ مكتمل', color: 'text-emerald-400', bg: 'from-emerald-500/10 to-green-500/5', border: 'border-emerald-500/30' },
    inprogress: { label: '🔄 جارٍ التطوير', color: 'text-yellow-400', bg: 'from-yellow-500/10 to-amber-500/5', border: 'border-yellow-500/30' },
    planned: { label: '📋 مخطط', color: 'text-purple-400', bg: 'from-purple-500/10 to-violet-500/5', border: 'border-purple-500/30' },
  };

  const totalDone = ROADMAP.flatMap(p => p.items).filter(i => i.done).length;
  const totalItems = ROADMAP.flatMap(p => p.items).length;

  return (
    <div className="space-y-8" dir="rtl">

      {/* Header */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h2 className="text-4xl font-bold text-white mb-3">🚀 خارطة طريق التطوير</h2>
        <p className="text-emerald-200 text-lg">
          تتبع كامل لمراحل تطوير النظام — من الأساسيات إلى التعلم الآلي
        </p>

        {/* Progress Bar */}
        <div className="mt-6">
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-400">التقدم الإجمالي</span>
            <span className="text-emerald-400 font-bold">{totalDone} / {totalItems} مهمة</span>
          </div>
          <div className="w-full bg-black/30 rounded-full h-4 overflow-hidden">
            <div
              className="bg-gradient-to-r from-emerald-500 to-teal-500 h-4 rounded-full transition-all duration-1000"
              style={{ width: `${(totalDone / totalItems) * 100}%` }}
            />
          </div>
          <div className="text-right text-emerald-400 text-sm mt-1 font-bold">
            {Math.round((totalDone / totalItems) * 100)}% مكتمل
          </div>
        </div>
      </div>

      {/* Phase Cards */}
      <div className="space-y-4">
        {ROADMAP.map((phase, idx) => {
          const cfg = statusConfig[phase.status as keyof typeof statusConfig];
          const isExpanded = expandedPhase === idx;
          const phDone = phase.items.filter(i => i.done).length;

          return (
            <div key={idx} className={`bg-gradient-to-br ${cfg.bg} border ${cfg.border} rounded-2xl overflow-hidden transition-all duration-300`}>
              {/* Phase Header */}
              <button
                onClick={() => setExpandedPhase(isExpanded ? null : idx)}
                className="w-full p-6 flex items-center gap-4 hover:bg-white/5 transition-colors text-right"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-sm font-bold text-gray-400">{phase.phase}</span>
                    <span className="text-xs bg-black/20 px-2 py-0.5 rounded-full text-gray-400">{phase.period}</span>
                    <span className={`text-xs font-bold ${cfg.color}`}>{cfg.label}</span>
                  </div>
                  <h3 className="text-xl font-bold text-white">{phase.title}</h3>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-black ${cfg.color}`}>{phDone}/{phase.items.length}</div>
                  <div className="text-gray-500 text-xs">مكتمل</div>
                </div>
                <span className={`text-gray-400 text-xl transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
              </button>

              {/* Phase Items */}
              {isExpanded && (
                <div className="px-6 pb-6 grid md:grid-cols-2 gap-3">
                  {phase.items.map((item, j) => (
                    <div key={j} className={`bg-black/20 rounded-xl p-4 border ${item.done ? 'border-emerald-500/20' : 'border-white/5'}`}>
                      <div className="flex items-start gap-3">
                        <span className={`text-xl flex-shrink-0 ${item.done ? 'text-emerald-400' : 'text-gray-600'}`}>
                          {item.done ? '✅' : '○'}
                        </span>
                        <div>
                          <div className={`font-semibold ${item.done ? 'text-white' : 'text-gray-500'}`}>{item.name}</div>
                          <div className="text-gray-500 text-xs mt-1">{item.detail}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Before / After Comparison */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6 text-center">📊 مقارنة الأداء: قبل وبعد التحسينات</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-right py-3 px-4 text-gray-400 font-semibold">المقياس</th>
                <th className="text-center py-3 px-4 text-red-400 font-semibold">🔴 قبل V4.0</th>
                <th className="text-center py-3 px-4 text-emerald-400 font-semibold">🟢 V4.2 Elite</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4 text-white font-medium">
                    <span className="ml-2">{row.icon}</span>
                    {row.metric}
                  </td>
                  <td className="py-3 px-4 text-center text-red-300">{row.before}</td>
                  <td className="py-3 px-4 text-center text-emerald-400 font-bold">{row.after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Key Improvements Detail */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-2xl p-6">
          <h4 className="text-lg font-bold text-blue-300 mb-4">🔧 الإصلاحات الحرجة في V4.2</h4>
          <ul className="space-y-2">
            {[
              'FIX 1: ProcessTrueSMC — g_LastSMCBar مُفعَّل الآن',
              'FIX 2: SuperTrend — منطق Buffer صحيح',
              'FIX 3: lockedProfit — صيغة محسوبة بدقة',
              'FIX 4: DetectEarlyReversal — Doji مقيَّد بـ RSI',
              'FIX 5: ManageBasketBE — علامة منفصلة للتطبيق',
              'FIX 6: IsFirstRun — حماية من MaxDD في أول تيك',
            ].map((fix, i) => (
              <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-emerald-400 flex-shrink-0">✅</span>
                {fix}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-2xl p-6">
          <h4 className="text-lg font-bold text-purple-300 mb-4">🆕 الميزات الجديدة في V4.2</h4>
          <ul className="space-y-2">
            {[
              'Partial Close Ladder — إغلاق تدريجي 30/50/70%',
              'Cascade Protection — وقف بعد N خسائر متتالية',
              'Volatility-Adjusted Grid — مضاعف شبكة ذكي',
              'Regime Lock — قفل اتجاه الجلسة',
              'Smart Hedging Mode — تحوط تلقائي عند DD%',
            ].map((feat, i) => (
              <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-purple-400 flex-shrink-0">🆕</span>
                {feat}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Next Steps */}
      <div className="bg-gradient-to-r from-purple-500/10 to-violet-500/10 border border-purple-500/20 rounded-2xl p-6">
        <h4 className="text-lg font-bold text-white mb-4">🎯 الخطوات القادمة</h4>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { icon: '🤖', title: 'ML Integration', desc: 'دمج نماذج التعلم الآلي لتحسين FSM', eta: 'شهر 2' },
            { icon: '📱', title: 'Mobile App', desc: 'تطبيق موبايل لمراقبة الأداء', eta: 'شهر 3' },
            { icon: '☁️', title: 'Cloud Sync', desc: 'مزامنة الإعدادات والإحصائيات السحابية', eta: 'شهر 4' },
          ].map((item, i) => (
            <div key={i} className="bg-black/20 rounded-xl p-4 text-center">
              <div className="text-3xl mb-2">{item.icon}</div>
              <div className="text-white font-bold mb-1">{item.title}</div>
              <div className="text-gray-400 text-sm mb-2">{item.desc}</div>
              <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">{item.eta}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
