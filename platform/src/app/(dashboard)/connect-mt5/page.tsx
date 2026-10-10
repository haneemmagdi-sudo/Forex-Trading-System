'use client'

import { useState, useEffect } from 'react'
import { Radio, ShieldCheck, Key, Copy, Check, Info, Server, HelpCircle, Loader2 } from 'lucide-react'

export default function ConnectMT5Page() {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [server, setServer] = useState('ICMarketsSC-Demo')
  const [brokerName, setBrokerName] = useState('IC Markets')
  const [accountType, setAccountType] = useState('demo')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [agentToken, setAgentToken] = useState('')
  
  const [copied, setCopied] = useState(false)
  const [existingAccount, setExistingAccount] = useState<any>(null)
  const [fetchingExisting, setFetchingExisting] = useState(true)

  // جلب معلومات الاتصال الحالية إن وجدت
  useEffect(() => {
    async function checkConnection() {
      try {
        const res = await fetch('/api/mt5/connect')
        const data = await res.json()
        if (data.account) {
          setExistingAccount(data.account)
          setAgentToken(data.account.agent_token)
          setLogin(data.account.login.toString())
          setServer(data.account.server)
          setBrokerName(data.account.broker_name || 'IC Markets')
          setAccountType(data.account.account_type || 'demo')
        }
      } catch (err) {
        console.error(err)
      } finally {
        setFetchingExisting(false)
      }
    }
    checkConnection()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccess(false)

    try {
      const res = await fetch('/api/mt5/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          password,
          server,
          brokerName,
          accountType,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'فشل حفظ الإعدادات')
      }

      setAgentToken(data.account.agent_token)
      setSuccess(true)
      setExistingAccount(data.account)
    } catch (err: any) {
      setError(err.message || 'حدث خطأ غير متوقع')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyToken = () => {
    navigator.clipboard.writeText(agentToken)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (fetchingExisting) {
    return (
      <div className="flex h-60 items-center justify-center text-slate-400">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">ربط منصة MetaTrader 5</h1>
        <p className="text-sm text-slate-500">قم بربط حساب التداول الخاص بك بـ Next.js Cloud لتشغيل وكلاء الذكاء الاصطناعي على المنصة.</p>
      </div>

      <div className="grid gap-8 md:grid-cols-5">
        
        {/* Connection Form */}
        <div className="md:col-span-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-xl space-y-6">
          <div>
            <h2 className="text-lg font-bold text-slate-200">بيانات حساب MT5</h2>
            <p className="text-xs text-slate-500">يجب أن تكون هذه البيانات مطابقة تماماً للمنصة في جهازك.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">رقم حساب التداول (Login)</label>
                <input
                  type="number"
                  required
                  value={login}
                  onChange={e => setLogin(e.target.value)}
                  placeholder="مثال: 52763636"
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                />
              </div>

              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">كلمة مرور التداول (Password)</label>
                <input
                  type="password"
                  required={!existingAccount}
                  placeholder={existingAccount ? '••••••••••••' : 'أدخل كلمة المرور'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">خادم التداول (Server)</label>
                <input
                  type="text"
                  required
                  value={server}
                  onChange={e => setServer(e.target.value)}
                  placeholder="مثال: ICMarketsSC-Demo"
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                />
              </div>

              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">نوع الحساب</label>
                <select
                  value={accountType}
                  onChange={e => setAccountType(e.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                >
                  <option value="demo">حساب تجريبي (Demo)</option>
                  <option value="live">حساب حقيقي (Live)</option>
                </select>
              </div>
            </div>

            <div className="space-y-1 text-right">
              <label className="text-xs font-semibold text-slate-400">اسم البروكر (إختياري)</label>
              <input
                type="text"
                value={brokerName}
                onChange={e => setBrokerName(e.target.value)}
                placeholder="مثال: IC Markets"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
              />
            </div>

            {error && <p className="text-xs font-semibold text-rose-400">{error}</p>}
            {success && <p className="text-xs font-semibold text-emerald-400">تم حفظ الإعدادات وتوليد رمز التوكن بنجاح!</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 py-3 text-sm font-bold text-white shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-cyan-500 transition-all duration-300 flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {existingAccount ? 'تحديث إعدادات الحساب' : 'حفظ وإنشاء توكن الـ Agent'}
            </button>
          </form>

          {existingAccount && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <div className="text-right">
                <h4 className="text-xs font-bold text-slate-200">حسابك مربوط حالياً</h4>
                <p className="text-[10px] text-slate-400 mt-0.5">الحساب النشط: {existingAccount.login} على السيرفر {existingAccount.server}</p>
              </div>
            </div>
          )}
        </div>

        {/* Instructions / Agent Token Box */}
        <div className="md:col-span-2 space-y-6">
          
          {/* Agent Token Panel */}
          {agentToken && (
            <div className="rounded-2xl border border-blue-500/20 bg-blue-950/10 p-6 backdrop-blur-xl space-y-4">
              <div className="flex items-center gap-2.5">
                <Key className="h-5 w-5 text-blue-400" />
                <h3 className="font-bold text-slate-200">توكن الاتصال بالـ Agent</h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                تحتاج لوضع هذا الرمز السري في ملف إعدادات الـ Agent على جهازك حتى يتمكن من إرسال البيانات بشكل آمن.
              </p>

              <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/80 p-2.5">
                <span className="flex-1 font-mono text-xs text-slate-300 truncate text-left dir-ltr pl-2">
                  {agentToken}
                </span>
                <button
                  onClick={handleCopyToken}
                  className="rounded-lg p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-all"
                  title="نسخ التوكن"
                >
                  {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
          )}

          {/* Running Instructions */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/20 p-6 backdrop-blur-xl space-y-4">
            <div className="flex items-center gap-2.5">
              <Info className="h-5 w-5 text-slate-400" />
              <h3 className="font-bold text-slate-200">خطوات تشغيل الـ Agent</h3>
            </div>
            
            <ul className="text-xs space-y-3.5 text-slate-400 text-right pr-1">
              <li className="flex gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-800 font-bold text-slate-300">١</span>
                <span>تأكد من تنزيل مجلد `mt5-agent` على جهاز الـ Windows الخاص بك.</span>
              </li>
              <li className="flex gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-800 font-bold text-slate-300">٢</span>
                <span>افتح ملف `config_agent.py` داخل الفلدر واكتب رمز التوكن الخاص بك في متغير `AGENT_TOKEN`.</span>
              </li>
              <li className="flex gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-800 font-bold text-slate-300">٣</span>
                <span>اضبط مسار MT5 في ملف `config.py` بالخلفية ليتصل محلياً بـ MetaTrader 5.</span>
              </li>
              <li className="flex gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-800 font-bold text-slate-300">٤</span>
                <span>شغل ملف `setup.bat` (لمرة واحدة لتثبيت بايثون والمكتبات) ثم شغل `start_agent.bat` لبدء الاتصال.</span>
              </li>
            </ul>
          </div>

        </div>

      </div>
    </div>
  )
}
