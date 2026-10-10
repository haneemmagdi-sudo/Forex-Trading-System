'use client'

import { useState, useEffect } from 'react'
import PricingCards from '@/components/subscription/PricingCards'
import { CreditCard, Shield, Landmark, PhoneCall, CheckCircle2, History, Loader2, Sparkles } from 'lucide-react'

export default function SubscriptionPage() {
  const [subStatus, setSubStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [manualHistory, setManualHistory] = useState<any[]>([])
  
  // Manual Payment Form States
  const [method, setMethod] = useState<'vodafone_cash' | 'instapay'>('vodafone_cash')
  const [plan, setPlan] = useState<'monthly' | 'yearly'>('monthly')
  const [transferRef, setTransferRef] = useState('')
  const [formLoading, setFormLoading] = useState(false)
  const [formSuccess, setFormSuccess] = useState(false)
  const [formError, setFormError] = useState('')

  const fetchStatus = async () => {
    try {
      // سنستدعي مسار MT5 connect لأنه يُرجع بيانات الـ user والاشتراك بشكل غير مباشر، 
      // أو نكتب مسار جلب اشتراك بسيط. دعنا نكتب endpoint للاشتراك في المستقبل أو نستدعيها من Supabase مباشرة.
      // لكن كحل سريع وآمن سنقوم بالاستعلام مباشرة من Supabase في المكون أو عبر api.
      // من أجل الـ RLS وحماية البيانات، دعنا نقوم بالاستعلام عبر fetch من api.
      // انتظر، هل هناك api لجلب حالة الاشتراك؟
      // نعم! دعنا نستعلم من مسار mt5 connect فهو يُرجع معلومات حساب MT5.
      // أو دعنا نستعمل Supabase client مباشرة للمتصفح بما أننا قمنا بتهيئته!
      const res = await fetch('/api/mt5/connect') // للتحقق من الاتصال
      
      // لنقم بجلب حالة الاشتراك عبر API مخصص أو مباشرة من Supabase client.
      // دعنا نستخدم supabase browser client!
      const { createBrowserClient } = await import('@/lib/supabase/client')
      const supabase = createBrowserClient()
      
      const { data: { user: clerkUser } } = await supabase.auth.getUser()
      
      // جلب بيانات المستخدم من جدول users المطابق لـ clerkId
      const { data: dbUserData } = await supabase
        .from('users')
        .select('id')
        .single()
      const dbUser = dbUserData as any
        
      if (dbUser) {
        // جلب الاشتراك
        const { data: subData } = await supabase
          .from('subscriptions')
          .select('*')
          .eq('user_id', dbUser.id)
          .single()
        const sub = subData as any
          
        if (sub) {
          const now = new Date()
          const trialEnd = sub.trial_end ? new Date(sub.trial_end) : null
          const isTrial = sub.plan === 'trial'
          const trialDaysLeft = trialEnd ? Math.max(0, Math.ceil((trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))) : 0
          
          setSubStatus({
            plan: sub.plan,
            status: sub.status,
            trialDaysLeft,
            trialEnd: trialEnd?.toLocaleDateString('ar-EG'),
            isActive: sub.status === 'active' && (!isTrial || (trialEnd && now < trialEnd)),
          })
        }

        // جلب سجل المدفوعات اليدوية
        const { data: payments } = await supabase
          .from('manual_payments')
          .select('*')
          .eq('user_id', dbUser.id)
          .order('created_at', { ascending: false })
          
        if (payments) {
          setManualHistory(payments)
        }
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormLoading(true)
    setFormError('')
    setFormSuccess(false)

    // حساب المبلغ المطلوب بالجنيه المصري EGP
    const amount = plan === 'monthly' ? '1500' : '10000'

    try {
      const res = await fetch('/api/subscription/manual-pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          method,
          plan,
          transferRef,
          amount,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'فشل تسجيل الطلب')
      }

      setFormSuccess(true)
      setTransferRef('')
      fetchStatus() // تحديث السجل
    } catch (err: any) {
      setFormError(err.message || 'حدث خطأ أثناء الاتصال بالخادم')
    } finally {
      setFormLoading(false)
    }
  }

  const getPlanName = (p: string) => {
    if (p === 'trial') return 'الفترة التجريبية'
    if (p === 'monthly') return 'الخطة الشهرية'
    if (p === 'yearly') return 'الخطة السنوية'
    return 'لا يوجد اشتراك نشط'
  }

  const getStatusLabel = (s: string) => {
    if (s === 'active') return 'نشط ✅'
    if (s === 'expired') return 'منتهي ❌'
    if (s === 'cancelled') return 'ملغي ⚠️'
    if (s === 'pending') return 'قيد الانتظار ⏳'
    if (s === 'approved') return 'مقبول ✅'
    if (s === 'rejected') return 'مرفوض ❌'
    return s
  }

  if (loading) {
    return (
      <div className="flex h-60 items-center justify-center text-slate-400">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-12">
      
      {/* Current Subscription Status */}
      <div className="rounded-3xl border border-slate-800 bg-[#0c0f1d]/40 p-8 backdrop-blur-xl flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-5">
          <div className="h-14 w-14 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-2xl flex items-center justify-center text-2xl">
            👑
          </div>
          <div className="space-y-1 text-right">
            <h2 className="text-xl font-bold text-slate-100">اشتراكك الحالي</h2>
            <p className="text-sm text-slate-400">
              أنت مشترك حالياً في: <span className="font-extrabold text-blue-400">{getPlanName(subStatus?.plan)}</span>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-6 items-center text-right md:border-r md:border-slate-800 md:pr-8">
          <div>
            <span className="text-xs text-slate-500">حالة الاشتراك</span>
            <div className="text-sm font-bold text-slate-200 mt-0.5">{getStatusLabel(subStatus?.status)}</div>
          </div>
          {subStatus?.plan === 'trial' && subStatus?.isActive && (
            <div>
              <span className="text-xs text-slate-500">الأيام المتبقية للتجربة</span>
              <div className="text-sm font-bold text-emerald-400 mt-0.5">{subStatus?.trialDaysLeft} أيام (حتى {subStatus?.trialEnd})</div>
            </div>
          )}
        </div>
      </div>

      {/* Stripe Payment Option */}
      <div>
        <div className="mb-6 text-center md:text-right">
          <h2 className="text-xl font-bold text-slate-100">ترقية الاشتراك والدفع الإلكتروني</h2>
          <p className="text-sm text-slate-500">اختر الخطة المناسبة لك وادفع بأمان عبر Stripe بالفيزا أو كرت الدفع المباشر.</p>
        </div>
        <PricingCards currentPlan={subStatus?.plan} />
      </div>

      {/* Vodafone Cash & InstaPay Manual Payment */}
      <div className="grid gap-8 md:grid-cols-5">
        
        {/* Manual Payment Form */}
        <div className="md:col-span-3 rounded-3xl border border-slate-800 bg-[#0c0f1d]/20 p-8 space-y-6">
          <div>
            <h3 className="text-lg font-bold text-slate-200">تحويل يدوي (المصريين داخل مصر)</h3>
            <p className="text-xs text-slate-500 mt-1">تسهيلاً على مستخدمينا في مصر، نوفر التحويل المباشر عبر فودافون كاش أو إنستا باي.</p>
          </div>

          {/* Payment Account Details */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-right">
              <div className="flex items-center gap-2 text-rose-400">
                <PhoneCall className="h-4 w-4" />
                <span className="text-xs font-bold">فودافون كاش (Vodafone Cash)</span>
              </div>
              <p className="text-lg font-black text-slate-100 font-mono">01012345678</p>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                الشهري: 1,500 جنيه مصري<br />
                السنوي: 10,000 جنيه مصري
              </p>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-right">
              <div className="flex items-center gap-2 text-emerald-400">
                <Landmark className="h-4 w-4" />
                <span className="text-xs font-bold">إنستا باي (InstaPay)</span>
              </div>
              <p className="text-sm font-black text-slate-100 font-mono text-left select-all">quantum@instapay</p>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                الشهري: 1,500 جنيه مصري<br />
                السنوي: 10,000 جنيه مصري
              </p>
            </div>
          </div>

          <form onSubmit={handleManualSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">طريقة التحويل المستخدمة</label>
                <select
                  value={method}
                  onChange={e => setMethod(e.target.value as any)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                >
                  <option value="vodafone_cash">فودافون كاش</option>
                  <option value="instapay">إنستا باي</option>
                </select>
              </div>

              <div className="space-y-1 text-right">
                <label className="text-xs font-semibold text-slate-400">الخطة المطلوبة</label>
                <select
                  value={plan}
                  onChange={e => setPlan(e.target.value as any)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
                >
                  <option value="monthly">الخطة الشهرية (1,500 EGP)</option>
                  <option value="yearly">الخطة السنوية (10,000 EGP)</option>
                </select>
              </div>
            </div>

            <div className="space-y-1 text-right">
              <label className="text-xs font-semibold text-slate-400">رقم التحويل أو الكود المرجعي للعملية</label>
              <input
                type="text"
                required
                value={transferRef}
                onChange={e => setTransferRef(e.target.value)}
                placeholder="أدخل الرقم الذي قمت بالتحويل منه أو رقم العملية"
                className="w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200 outline-none focus:border-blue-500/50"
              />
            </div>

            {formError && <p className="text-xs font-semibold text-rose-400">{formError}</p>}
            {formSuccess && <p className="text-xs font-semibold text-emerald-400">تم إرسال طلب الدفع اليدوي بنجاح. سيقوم المسؤول بمراجعة التحويل وتفعيل اشتراكك خلال 24 ساعة.</p>}

            <button
              type="submit"
              disabled={formLoading}
              className="w-full rounded-xl border border-slate-700 bg-slate-800 px-6 py-3.5 text-sm font-bold text-slate-200 hover:bg-slate-700 transition-all duration-300 flex items-center justify-center gap-2"
            >
              {formLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              تأكيد التحويل وإرسال الطلب
            </button>
          </form>
        </div>

        {/* Manual Payment History */}
        <div className="md:col-span-2 rounded-3xl border border-slate-800 bg-slate-900/10 p-8 space-y-6">
          <div className="flex items-center gap-2.5">
            <History className="h-5 w-5 text-slate-400" />
            <h3 className="font-bold text-slate-200">سجل الدفع اليدوي</h3>
          </div>

          {manualHistory.length === 0 ? (
            <p className="text-xs text-slate-500 leading-relaxed text-center py-10">
              لا توجد طلبات دفع يدوية سابقة.
            </p>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {manualHistory.map(pay => (
                <div key={pay.id} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 space-y-2 text-right">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] text-slate-500">{new Date(pay.created_at).toLocaleDateString('ar-EG')}</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      pay.status === 'pending'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : pay.status === 'approved'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}>
                      {getStatusLabel(pay.status)}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-slate-300">
                    {pay.method === 'vodafone_cash' ? 'فودافون كاش' : 'إنستا باي'} - {pay.plan === 'monthly' ? 'شهر' : 'سنة'}
                  </div>
                  <div className="text-[10px] font-mono text-slate-500">
                    المرجع: {pay.transfer_ref}<br />
                    المبلغ: {pay.amount} EGP
                  </div>
                  {pay.admin_note && (
                    <div className="text-[10px] border-t border-slate-800 pt-1.5 text-slate-400">
                      ملاحظة الأدمن: {pay.admin_note}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

    </div>
  )
}
