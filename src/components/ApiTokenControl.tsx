import { useState, type FormEvent } from 'react';
import { getApiToken, setApiToken } from '../utils/auth';

export default function ApiTokenControl() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [saved, setSaved] = useState(() => Boolean(getApiToken()));

  const store = (token: string) => {
    setApiToken(token);
    setSaved(Boolean(getApiToken()));
    setValue('');
    setOpen(false);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim()) store(value);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-semibold ${
          saved
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
        }`}
      >
        🔑 {saved ? 'رمز الدخول محفوظ' : 'أدخل رمز الدخول'}
      </button>

      {open && (
        <form
          onSubmit={submit}
          className="absolute left-0 top-full mt-2 w-72 z-40 bg-slate-900 border border-purple-500/30 rounded-xl p-3 shadow-2xl space-y-2"
        >
          <label className="block text-xs text-gray-300">
            رمز الدخول (قيمة API_TOKEN في ملف .env)
            <input
              type="password"
              dir="ltr"
              autoComplete="off"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="mt-1 w-full bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-purple-400 focus:outline-none"
            />
          </label>
          <div className="flex items-center gap-2">
            <button type="submit" className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold">
              حفظ
            </button>
            {saved && (
              <button type="button" onClick={() => store('')} className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 text-xs">
                حذف الرمز
              </button>
            )}
          </div>
          <p className="text-[11px] text-gray-500">يُحفظ في هذا المتصفح فقط.</p>
        </form>
      )}
    </div>
  );
}
