import { useState, useEffect, useRef } from 'react';

function AnimatedCounter({ target, suffix = '', prefix = '' }: { target: number; suffix?: string; prefix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !started.current) {
        started.current = true;
        const duration = 2000;
        const steps = 60;
        const increment = target / steps;
        let current = 0;
        const timer = setInterval(() => {
          current += increment;
          if (current >= target) {
            setCount(target);
            clearInterval(timer);
          } else {
            setCount(Math.floor(current));
          }
        }, duration / steps);
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

export default function HomePage({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const [glowActive, setGlowActive] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => setGlowActive(p => !p), 3000);
    return () => clearInterval(interval);
  }, []);

  const features = [
    { icon: '🏛️', title: 'شركة تداول TradingAgents (Tauric)', desc: 'محاكاة شركة تداول كاملة: محللون ومناظرة ثور/دب وإدارة مخاطر وموافقة يدوية لـ MT5', tab: 'tradingAgents', color: 'from-purple-600/30 to-pink-600/30', border: 'border-purple-400/50' },
    { icon: '📈', title: 'لوحة المراقبة الحية', desc: 'مراقبة حية للأداء ولحظية للسوق والصفقات', tab: 'liveDash', color: 'from-blue-500/20 to-cyan-500/20', border: 'border-blue-500/30' },
    { icon: '📋', title: 'جدول حالة الأزواج', desc: 'متابعة شاملة لكافة أزواج العملات وحالتها الفنية', tab: 'pairsTable', color: 'from-emerald-500/20 to-teal-500/20', border: 'border-emerald-500/30' },
    { icon: '🎯', title: 'مركز القيادة', desc: 'إدارة تشغيل الوكلاء ومتابعة القرارات في الوقت الحقيقي', tab: 'commandCenter', color: 'from-purple-500/20 to-pink-500/20', border: 'border-purple-500/30' },
    { icon: '🤖', title: 'وكلاء الذكاء الاصطناعي', desc: 'وكلاء متخصصون يعملون 24/5 لتحليل وتنفيذ الصفقات', tab: 'aiAgents', color: 'from-orange-500/20 to-red-500/20', border: 'border-orange-500/30' },
    { icon: '💬', title: 'التواصل مع الوكلاء', desc: 'محادثة تفاعلية مباشرة مع الوكلاء للاستفسارات وتحليل السوق', tab: 'agentCommTab', color: 'from-pink-500/20 to-rose-500/20', border: 'border-pink-500/30' },
    { icon: '💎', title: 'Smart Money Concepts', desc: 'Order Blocks، Fair Value Gaps، و Liquidity Sweeps', tab: 'smc', color: 'from-yellow-500/20 to-amber-500/20', border: 'border-yellow-500/30' },
    { icon: '🧠', title: 'مصفوفة القرار', desc: 'تكامل الفيتو المؤسسي لاتخاذ قرارات عالية الدقة', tab: 'matrix', color: 'from-violet-500/20 to-indigo-500/20', border: 'border-violet-500/30' },
    { icon: '🔬', title: 'التحليل المتقدم', desc: 'تحليلات عميقة للمؤشرات الفنية والسيولة والاتجاهات', tab: 'advancedAnalytics', color: 'from-cyan-500/20 to-blue-500/20', border: 'border-cyan-500/30' },
    { icon: '🤖', title: 'لوحة التعلم الآلي', desc: 'نماذج ML المتقدمة والتنبؤات الاحتمالية للاتجاه', tab: 'mlDashboard', color: 'from-indigo-500/20 to-purple-500/20', border: 'border-indigo-500/30' },
  ];

  const stats = [
    { label: 'نسبة الربح', value: 82, suffix: '%', color: 'text-emerald-400' },
    { label: 'Max Drawdown', value: 8, suffix: '%', color: 'text-yellow-400' },
    { label: 'Profit Factor', value: 28, suffix: 'x', prefix: '', display: '2.8', color: 'text-purple-400' },
    { label: 'Sharpe Ratio', value: 23, suffix: '', prefix: '', display: '2.3', color: 'text-blue-400' },
  ];

  const timeline = [
    { phase: 'المرحلة 1', title: 'الأساسيات', items: ['FSM Engine', 'Voting System', 'Decision Matrix', 'Smart Grid'], done: true },
    { phase: 'المرحلة 2', title: 'التحسينات', items: ['State E (News)', 'Member Rating', 'Portfolio Manager', 'Magic Number'], done: true },
    { phase: 'المرحلة 3', title: 'الأتمتة', items: ['Recovery Mode', 'Dashboard', 'Telegram Bot', 'AI Agents'], done: true },
    { phase: 'المرحلة 4', title: 'المستقبل', items: ['Backtester', 'Signal Generator', 'EA Configurator', 'ML Optimization'], done: false },
  ];

  return (
    <div className="space-y-16" dir="rtl">

      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl">
        <div className={`absolute inset-0 bg-gradient-to-br from-purple-900/80 via-violet-900/60 to-slate-900/80 transition-all duration-3000`} />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(139,92,246,0.3)_0%,_transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_rgba(236,72,153,0.2)_0%,_transparent_60%)]" />

        {/* Animated grid background */}
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'linear-gradient(rgba(139,92,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(139,92,246,0.5) 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }} />

        <div className="relative z-10 px-8 py-16 md:py-24 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-400/40 rounded-full text-purple-300 text-sm font-semibold mb-6">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            نظام الجيل الثالث — V4.2 Elite Fixed
          </div>

          {/* Title */}
          <h1 className="text-5xl md:text-7xl font-black mb-6">
            <span className="bg-gradient-to-r from-white via-purple-200 to-pink-200 bg-clip-text text-transparent">
              Quantum FSM
            </span>
            <br />
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-red-400 bg-clip-text text-transparent">
              Grid Pro
            </span>
          </h1>

          <p className="text-xl md:text-2xl text-gray-300 mb-4 max-w-3xl mx-auto leading-relaxed">
            نظام تداول فوركس من الجيل الثالث — يجمع الذكاء الاصطناعي، الشبكة الذكية، ومفاهيم Smart Money في منظومة واحدة متكاملة
          </p>
          <p className="text-base text-gray-400 mb-10">
            مبني على MetaTrader 5 | 1884 سطر برمجي احترافي | اختبرها مجاناً
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-wrap gap-4 justify-center">
            <button
              onClick={() => onNavigate('liveDash')}
              className="px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold rounded-2xl text-lg shadow-2xl shadow-purple-500/40 hover:shadow-purple-500/60 hover:-translate-y-1 transition-all duration-300"
            >
              📈 لوحة المراقبة الحية
            </button>
            <button
              onClick={() => onNavigate('commandCenter')}
              className="px-8 py-4 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-bold rounded-2xl text-lg hover:-translate-y-1 transition-all duration-300"
            >
              🎯 مركز القيادة
            </button>
            <button
              onClick={() => onNavigate('agentCommTab')}
              className="px-8 py-4 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/30 text-emerald-300 font-bold rounded-2xl text-lg hover:-translate-y-1 transition-all duration-300"
            >
              💬 التواصل مع الوكلاء
            </button>
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Win Rate المتوقع', value: 82, suffix: '%', color: 'text-emerald-400', bg: 'from-emerald-500/10 to-green-500/10', border: 'border-emerald-500/20' },
          { label: 'Max Drawdown', value: 8, suffix: '%', color: 'text-yellow-400', bg: 'from-yellow-500/10 to-amber-500/10', border: 'border-yellow-500/20' },
          { label: 'Profit Factor', value: 280, suffix: '', color: 'text-purple-400', bg: 'from-purple-500/10 to-violet-500/10', border: 'border-purple-500/20', display: '2.8×' },
          { label: 'Sharpe Ratio', value: 230, suffix: '', color: 'text-blue-400', bg: 'from-blue-500/10 to-cyan-500/10', border: 'border-blue-500/20', display: '2.3' },
        ].map((stat, i) => (
          <div key={i} className={`bg-gradient-to-br ${stat.bg} border ${stat.border} rounded-2xl p-6 text-center hover:scale-105 transition-all duration-300`}>
            <div className={`text-4xl md:text-5xl font-black ${stat.color} mb-2`}>
              {stat.display ? stat.display : <><AnimatedCounter target={stat.value} suffix={stat.suffix} /></>}
            </div>
            <div className="text-gray-400 text-sm font-medium">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Features Grid */}
      <div>
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">🔥 مكونات النظام</h2>
          <p className="text-gray-400 text-lg">اضغط على أي مكوّن للاطلاع على التفاصيل الكاملة</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f, i) => (
            <button
              key={i}
              onClick={() => onNavigate(f.tab)}
              className={`bg-gradient-to-br ${f.color} border ${f.border} rounded-2xl p-6 text-right hover:scale-[1.02] hover:shadow-2xl transition-all duration-300 group`}
            >
              <div className="flex items-start gap-4">
                <div className="text-4xl group-hover:scale-110 transition-transform duration-300">{f.icon}</div>
                <div>
                  <h3 className="text-white font-bold text-lg mb-1">{f.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Development Timeline */}
      <div>
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">🗺️ خارطة التطوير</h2>
          <p className="text-gray-400 text-lg">رحلة التطوير من الأساسيات إلى الذكاء الاصطناعي الكامل</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {timeline.map((phase, i) => (
            <div key={i} className={`relative rounded-2xl p-6 border ${phase.done ? 'bg-gradient-to-br from-emerald-500/10 to-green-500/5 border-emerald-500/30' : 'bg-gradient-to-br from-purple-500/10 to-violet-500/5 border-purple-500/30'}`}>
              {/* Connection line */}
              {i < timeline.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -left-2 w-4 h-0.5 bg-gray-600 z-10" />
              )}
              <div className={`text-xs font-bold mb-2 ${phase.done ? 'text-emerald-400' : 'text-purple-400'}`}>
                {phase.done ? '✅' : '🔄'} {phase.phase}
              </div>
              <h3 className="text-white font-bold text-base mb-3">{phase.title}</h3>
              <ul className="space-y-1">
                {phase.items.map((item, j) => (
                  <li key={j} className={`text-sm flex items-center gap-2 ${phase.done ? 'text-emerald-300' : 'text-purple-300'}`}>
                    <span>{phase.done ? '✓' : '○'}</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Start */}
      <div className="bg-gradient-to-br from-slate-800/60 to-slate-900/60 border border-white/10 rounded-3xl p-8">
        <h2 className="text-3xl font-bold text-white mb-8 text-center">⚡ البدء السريع</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { step: '1', icon: '📥', title: 'تحميل الكود', desc: 'اذهب إلى تبويب "الكود المجاني" وحمّل ملف MQL5', action: 'freeCode', btn: 'تحميل الآن' },
            { step: '2', icon: '⚙️', title: 'ضبط الإعدادات', desc: 'استخدم EA Configurator لضبط إعداداتك بسهولة', action: 'eaConfig', btn: 'ضبط الإعدادات' },
            { step: '3', icon: '🚀', title: 'اختبر وانطلق', desc: 'شغّل على حساب Demo شهراً قبل Live', action: 'backtester', btn: 'ابدأ الاختبار' },
          ].map((s, i) => (
            <div key={i} className="text-center">
              <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-2xl mx-auto mb-4 shadow-lg shadow-purple-500/30">
                {s.icon}
              </div>
              <div className="text-purple-400 text-xs font-bold mb-1">الخطوة {s.step}</div>
              <h3 className="text-white font-bold text-lg mb-2">{s.title}</h3>
              <p className="text-gray-400 text-sm mb-4">{s.desc}</p>
              <button
                onClick={() => onNavigate(s.action)}
                className="px-5 py-2 bg-purple-500/20 hover:bg-purple-500/40 border border-purple-400/30 text-purple-300 text-sm font-semibold rounded-xl transition-all duration-200"
              >
                {s.btn}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Warning Banner */}
      <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/30 rounded-2xl p-6 flex gap-4 items-start">
        <span className="text-3xl flex-shrink-0">⚠️</span>
        <div>
          <h3 className="text-yellow-300 font-bold text-lg mb-1">تحذير مهم</h3>
          <p className="text-gray-300 text-sm leading-relaxed">
            التداول في الفوركس ينطوي على مخاطر عالية وقد تخسر كل رأس مالك. هذا النظام للأغراض التعليمية. اختبر دائماً على حساب تجريبي أولاً لمدة لا تقل عن شهر قبل الانتقال للحساب الحقيقي. لا تستثمر أموالاً لا تستطيع تحمل خسارتها.
          </p>
        </div>
      </div>

    </div>
  );
}
