import { useState } from 'react';

// =============================================
// إعدادات الـ EA مع قيمها الافتراضية
// =============================================
type SettingType = 'bool' | 'double' | 'int' | 'color' | 'enum' | 'string';

interface Setting {
  key: string;
  label: string;
  type: SettingType;
  default: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  desc: string;
}

const SETTING_GROUPS: { title: string; icon: string; settings: Setting[] }[] = [
  {
    title: 'الإعدادات العامة',
    icon: '⚙️',
    settings: [
      { key: 'TradeComment', label: 'تعليق الصفقات', type: 'string', default: 'Blessing_FSM_V42', desc: 'النص الذي يظهر مع كل صفقة' },
      { key: 'EA_Magic_Number', label: 'Magic Number', type: 'int', default: 112345, min: 1000, max: 9999999, step: 1, desc: 'رقم فريد للتمييز بين الـ EAs' },
      { key: 'Lot', label: 'حجم اللوت', type: 'double', default: 0.02, min: 0.01, max: 10, step: 0.01, desc: 'حجم اللوت الأساسي' },
      { key: 'MaxSpread', label: 'أقصى سبريد (نقطة)', type: 'double', default: 25.0, min: 5, max: 100, step: 1, desc: 'السبريد الأقصى المسموح للتداول' },
    ],
  },
  {
    title: 'الشبكة الذكية',
    icon: '🕸️',
    settings: [
      { key: 'UseSmartGrid', label: 'تفعيل الشبكة الذكية', type: 'bool', default: true, desc: 'تشغيل نظام الشبكة التكتيكية' },
      { key: 'MaxTrades', label: 'أقصى عدد صفقات', type: 'int', default: 10, min: 1, max: 30, step: 1, desc: 'الحد الأقصى للصفقات المفتوحة' },
      { key: 'GridDistancePips', label: 'مسافة الشبكة (نقاط)', type: 'int', default: 25, min: 5, max: 200, step: 5, desc: 'المسافة بين صفقات الشبكة' },
      { key: 'ATRMultiplier', label: 'مضاعف ATR', type: 'double', default: 2.0, min: 0.5, max: 5, step: 0.1, desc: 'معامل ضبط المسافة بناءً على ATR' },
    ],
  },
  {
    title: 'إدارة المخاطر',
    icon: '🛡️',
    settings: [
      { key: 'MaxDDPercent', label: 'أقصى تراجع %', type: 'double', default: 5.0, min: 1, max: 30, step: 0.5, desc: 'الإيقاف التلقائي عند هذا التراجع' },
      { key: 'SoftDD_Warning', label: 'تحذير التراجع الناعم %', type: 'double', default: 3.0, min: 0.5, max: 20, step: 0.5, desc: 'تفعيل وضع الحذر عند هذا الحد' },
      { key: 'HedgeDDPercent', label: 'تراجع تفعيل التحوط %', type: 'double', default: 2.5, min: 1, max: 15, step: 0.5, desc: 'تفعيل Smart Hedge عند هذا الحد' },
      { key: 'HedgeLotFactor', label: 'معامل حجم التحوط', type: 'double', default: 0.7, min: 0.1, max: 2, step: 0.1, desc: 'نسبة حجم لوت التحوط من الخسارة' },
    ],
  },
  {
    title: 'وقف الخسارة والهدف',
    icon: '🎯',
    settings: [
      { key: 'SL_ATR_Multiplier', label: 'مضاعف SL من ATR', type: 'double', default: 2.5, min: 0.5, max: 5, step: 0.1, desc: 'حساب SL = ATR × هذا المعامل' },
      { key: 'Trail_ATR_Mult', label: 'مضاعف Trailing من ATR', type: 'double', default: 1.5, min: 0.5, max: 4, step: 0.1, desc: 'مسافة Trailing Stop' },
      { key: 'BaseTargetUSD', label: 'هدف الربح ($)', type: 'double', default: 5.0, min: 1, max: 500, step: 0.5, desc: 'هدف الربح بالدولار للسلة' },
      { key: 'TrailLockPercent', label: 'نسبة تأمين الربح %', type: 'double', default: 60.0, min: 30, max: 90, step: 5, desc: 'قفل هذه النسبة من الربح قبل التراجع' },
    ],
  },
  {
    title: 'الأرباح الجزئية (Partial Ladder)',
    icon: '📊',
    settings: [
      { key: 'UsePartialTP', label: 'تفعيل الإغلاق الجزئي', type: 'bool', default: true, desc: 'إغلاق تدريجي عند الأهداف' },
      { key: 'PartialTP_L1_Pips', label: 'المستوى 1 (نقاط)', type: 'double', default: 10.0, min: 5, max: 50, step: 1, desc: 'إغلاق 30% عند هذه النقاط' },
      { key: 'PartialTP_L2_Pips', label: 'المستوى 2 (نقاط)', type: 'double', default: 20.0, min: 10, max: 100, step: 1, desc: 'إغلاق 50% عند هذه النقاط' },
      { key: 'PartialTP_L3_Pips', label: 'المستوى 3 (نقاط)', type: 'double', default: 35.0, min: 20, max: 150, step: 1, desc: 'إغلاق 70% عند هذه النقاط' },
    ],
  },
  {
    title: 'الحماية المتقدمة',
    icon: '🔒',
    settings: [
      { key: 'UseCascadeProtection', label: 'حماية Cascade', type: 'bool', default: true, desc: 'وقف التداول بعد خسائر متتالية' },
      { key: 'CascadeMaxLosses', label: 'عدد الخسائر قبل الوقف', type: 'int', default: 3, min: 2, max: 10, step: 1, desc: 'عدد الخسائر المتتالية قبل التوقف' },
      { key: 'CascadeCooldownBars', label: 'فترة الراحة (شموع)', type: 'int', default: 20, min: 5, max: 100, step: 5, desc: 'انتظر هذه الشموع قبل العودة' },
      { key: 'UseRegimeLock', label: 'قفل اتجاه الجلسة', type: 'bool', default: true, desc: 'لا تعكس الاتجاه في نفس الجلسة' },
    ],
  },
];

const PRESETS = {
  beginner: { label: '🟢 مبتدئ — محافظ', values: { Lot: 0.01, MaxDDPercent: 3.0, MaxTrades: 5, CascadeMaxLosses: 2, PartialTP_L1_Pips: 8, UseSmartGrid: true, UseCascadeProtection: true } },
  intermediate: { label: '🟡 متوسط — متوازن', values: { Lot: 0.02, MaxDDPercent: 5.0, MaxTrades: 10, CascadeMaxLosses: 3, PartialTP_L1_Pips: 10, UseSmartGrid: true, UseCascadeProtection: true } },
  advanced: { label: '🔴 محترف — عدواني', values: { Lot: 0.05, MaxDDPercent: 8.0, MaxTrades: 15, CascadeMaxLosses: 4, PartialTP_L1_Pips: 12, UseSmartGrid: true, UseCascadeProtection: false } },
};

export default function EAConfigurator() {
  const [values, setValues] = useState<Record<string, string | number | boolean>>(() => {
    const init: Record<string, string | number | boolean> = {};
    SETTING_GROUPS.forEach(g => g.settings.forEach(s => { init[s.key] = s.default; }));
    return init;
  });
  const [activeGroup, setActiveGroup] = useState(0);
  const [copied, setCopied] = useState(false);
  const [appliedPreset, setAppliedPreset] = useState<string | null>(null);

  const applyPreset = (presetKey: keyof typeof PRESETS) => {
    const preset = PRESETS[presetKey];
    setValues(prev => ({ ...prev, ...preset.values }));
    setAppliedPreset(presetKey);
    setTimeout(() => setAppliedPreset(null), 3000);
  };

  const generateSetFile = () => {
    const lines = Object.entries(values).map(([k, v]) => `${k}=${v}`);
    return lines.join('\n');
  };

  const handleCopySet = () => {
    navigator.clipboard.writeText(generateSetFile()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleReset = () => {
    const init: Record<string, string | number | boolean> = {};
    SETTING_GROUPS.forEach(g => g.settings.forEach(s => { init[s.key] = s.default; }));
    setValues(init);
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-br from-teal-500/20 to-cyan-500/20 rounded-3xl p-8 border border-teal-400/30">
        <h2 className="text-4xl font-bold text-white mb-2">⚙️ ضابط إعدادات EA</h2>
        <p className="text-teal-200 text-lg">اضبط جميع إعدادات Blessing Pro V4.2 بصرياً ثم صدّر ملف .set للـ MT5</p>
      </div>

      {/* Presets */}
      <div className="bg-white/5 rounded-2xl p-5 border border-white/10">
        <h3 className="text-white font-bold mb-3">⚡ الإعدادات الجاهزة (Presets)</h3>
        <div className="grid md:grid-cols-3 gap-3">
          {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map(key => (
            <button
              key={key}
              onClick={() => applyPreset(key)}
              className={`py-3 px-4 rounded-xl border font-semibold text-sm transition-all ${
                appliedPreset === key
                  ? 'bg-emerald-500/20 border-emerald-400/60 text-emerald-300'
                  : 'bg-black/20 border-white/10 text-gray-300 hover:border-purple-400/40 hover:text-white'
              }`}
            >
              {PRESETS[key].label}
              {appliedPreset === key && <span className="ml-2">✅</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-4 gap-4">
        {/* Left: Group Navigator */}
        <div className="space-y-2">
          {SETTING_GROUPS.map((group, idx) => (
            <button
              key={idx}
              onClick={() => setActiveGroup(idx)}
              className={`w-full text-right px-4 py-3 rounded-xl border text-sm font-semibold transition-all ${
                activeGroup === idx
                  ? 'bg-purple-500/20 border-purple-400/60 text-purple-300'
                  : 'bg-black/20 border-white/5 text-gray-400 hover:border-white/20 hover:text-white'
              }`}
            >
              <span className="ml-2">{group.icon}</span>
              {group.title}
            </button>
          ))}
        </div>

        {/* Right: Settings Form */}
        <div className="md:col-span-3 bg-white/5 rounded-2xl p-5 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">
            {SETTING_GROUPS[activeGroup].icon} {SETTING_GROUPS[activeGroup].title}
          </h3>
          <div className="space-y-4">
            {SETTING_GROUPS[activeGroup].settings.map(setting => (
              <div key={setting.key} className="bg-black/20 rounded-xl p-4 border border-white/5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="text-white font-semibold text-sm">{setting.label}</div>
                    <div className="text-gray-500 text-xs mt-0.5">{setting.desc}</div>
                    <div className="text-purple-400/50 text-xs font-mono mt-0.5">{setting.key}</div>
                  </div>
                  <div className="flex-shrink-0 w-40">
                    {setting.type === 'bool' ? (
                      <button
                        onClick={() => setValues(prev => ({ ...prev, [setting.key]: !prev[setting.key] }))}
                        className={`w-full py-2 rounded-lg font-bold text-sm transition-all ${
                          values[setting.key]
                            ? 'bg-emerald-500/30 text-emerald-400 border border-emerald-400/40'
                            : 'bg-red-500/20 text-red-400 border border-red-400/30'
                        }`}
                      >
                        {values[setting.key] ? '✅ مفعّل' : '❌ معطّل'}
                      </button>
                    ) : setting.type === 'double' || setting.type === 'int' ? (
                      <div>
                        <input
                          type="range"
                          min={setting.min}
                          max={setting.max}
                          step={setting.step}
                          value={values[setting.key] as number}
                          onChange={e => setValues(prev => ({ ...prev, [setting.key]: setting.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value) }))}
                          className="w-full accent-purple-500 mb-1"
                        />
                        <input
                          type="number"
                          min={setting.min}
                          max={setting.max}
                          step={setting.step}
                          value={values[setting.key] as number}
                          onChange={e => setValues(prev => ({ ...prev, [setting.key]: setting.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value) }))}
                          className="w-full bg-black/40 border border-white/10 text-white rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:border-purple-400"
                        />
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={values[setting.key] as string}
                        onChange={e => setValues(prev => ({ ...prev, [setting.key]: e.target.value }))}
                        className="w-full bg-black/40 border border-white/10 text-white rounded-lg px-2 py-2 text-sm focus:outline-none focus:border-purple-400"
                      />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Export Section */}
      <div className="bg-white/5 rounded-2xl p-5 border border-white/10">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <h3 className="text-lg font-bold text-white">📁 تصدير إعدادات MT5</h3>
          <div className="flex gap-3">
            <button onClick={handleReset} className="px-4 py-2 bg-gray-500/20 hover:bg-gray-500/30 border border-gray-400/30 text-gray-300 text-sm font-semibold rounded-xl transition-all">
              🔄 إعادة تعيين
            </button>
            <button onClick={handleCopySet} className={`px-5 py-2 font-bold text-sm rounded-xl transition-all ${copied ? 'bg-emerald-500/30 text-emerald-400 border border-emerald-400/40' : 'bg-purple-500/20 hover:bg-purple-500/30 border border-purple-400/30 text-purple-300'}`}>
              {copied ? '✅ تم النسخ!' : '📋 نسخ ملف .set'}
            </button>
          </div>
        </div>
        <pre
          className="bg-black/60 rounded-xl p-4 text-xs overflow-x-auto max-h-48"
          style={{ direction: 'ltr', textAlign: 'left', fontFamily: 'monospace' }}
        >
          {generateSetFile()}
        </pre>
        <p className="text-gray-500 text-xs mt-2">
          📌 الصق هذا المحتوى في ملف .set وافتحه من MT5: الإكسبرت → تحميل إعدادات
        </p>
      </div>
    </div>
  );
}
