'use client'

import { useState } from 'react'
import { Check, Loader2 } from 'lucide-react'

interface PricingCardsProps {
  currentPlan: string
}

export default function PricingCards({ currentPlan }: PricingCardsProps) {
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)

  const handleSubscribe = async (plan: 'monthly' | 'yearly') => {
    setLoadingPlan(plan)
    try {
      const res = await fetch('/api/subscription/create-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        alert(data.error || 'فشل بدء عملية الدفع')
      }
    } catch (err) {
      console.error(err)
      alert('حدث خطأ أثناء الاتصال بالخادم')
    } finally {
      setLoadingPlan(null)
    }
  }

  const plans = [
    {
      id: 'monthly',
      name: 'الخطة الشهرية',
      price: '$29',
      period: '/ شهرياً',
      description: 'مثالية للمتداولين الذين يفضلون الالتزام قصير الأجل.',
      features: [
        'جميع وكلاء الذكاء الاصطناعي الأربعة',
        'اتصال مباشر بحساب MT5 واحد',
        'مراقبة فورية وتحليل متعدد الأطر الزمنية',
        'لوحة تحكم كاملة الأداء وإشعارات حية',
        'دعم فني سريع عبر البريد والتلجرام',
      ],
      buttonText: currentPlan === 'monthly' ? 'اشتراكك الحالي' : 'اشترك الآن',
      popular: true,
    },
    {
      id: 'yearly',
      name: 'الخطة السنوية',
      price: '$199',
      period: '/ سنوياً',
      description: 'الخيار الأفضل للشركاء طويلي الأجل مع توفير 43%.',
      features: [
        'جميع وكلاء الذكاء الاصطناعي الأربعة',
        'اتصال مباشر بحساب MT5 واحد',
        'مراقبة فورية وتحليل متعدد الأطر الزمنية',
        'لوحة تحكم كاملة الأداء وإشعارات حية',
        'أولوية الدعم الفني 24/7',
        'توفير بقيمة $149 سنوياً مقارنة بالشهري',
      ],
      buttonText: currentPlan === 'yearly' ? 'اشتراكك الحالي' : 'اشترك سنوياً',
      popular: false,
    },
  ]

  return (
    <div className="grid gap-8 md:grid-cols-2">
      {plans.map(plan => {
        const isCurrent = currentPlan === plan.id
        const isLoading = loadingPlan === plan.id

        return (
          <div
            key={plan.id}
            className={`relative flex flex-col rounded-3xl border p-8 backdrop-blur-xl transition-all duration-300 ${
              plan.popular
                ? 'border-blue-500 bg-blue-950/10 shadow-[0_0_40px_rgba(59,130,246,0.15)] md:scale-105'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
            }`}
          >
            {plan.popular && (
              <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-blue-600 to-cyan-600 px-4 py-1 text-xs font-bold text-white shadow-md shadow-blue-500/20">
                الأكثر شيوعاً
              </span>
            )}

            <div className="mb-6">
              <h3 className="text-xl font-bold text-slate-100">{plan.name}</h3>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">{plan.description}</p>
              
              <div className="mt-4 flex items-baseline gap-1 text-right">
                <span className="text-5xl font-black text-slate-100">{plan.price}</span>
                <span className="text-sm text-slate-400">{plan.period}</span>
              </div>
            </div>

            <ul className="mb-8 flex-1 space-y-4 text-right">
              {plan.features.map((feature, idx) => (
                <li key={idx} className="flex gap-3 text-sm text-slate-300">
                  <Check className="h-5 w-5 flex-shrink-0 text-blue-400" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <button
              onClick={() => handleSubscribe(plan.id as 'monthly' | 'yearly')}
              disabled={isCurrent || isLoading || loadingPlan !== null}
              className={`w-full rounded-2xl py-4 text-sm font-bold transition-all duration-300 flex items-center justify-center gap-2 ${
                isCurrent
                  ? 'bg-slate-800 text-slate-400 border border-slate-700 cursor-default'
                  : plan.popular
                  ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-cyan-500 hover:shadow-blue-500/30'
                  : 'bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700'
              }`}
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              {plan.buttonText}
            </button>
          </div>
        )
      })}
    </div>
  )
}
