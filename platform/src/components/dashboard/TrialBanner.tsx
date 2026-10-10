'use client'

import Link from 'next/link'
import { Sparkles, Calendar, ArrowLeft } from 'lucide-react'

interface TrialBannerProps {
  daysLeft: number
  isActive: boolean
  isTrial: boolean
}

export default function TrialBanner({ daysLeft, isActive, isTrial }: TrialBannerProps) {
  if (!isTrial) return null

  if (!isActive) {
    return (
      <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 backdrop-blur-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              ⚠️
            </span>
            <div>
              <h3 className="text-lg font-bold text-rose-400">انتهت فترة التجربة المجانية!</h3>
              <p className="text-sm text-slate-400">لقد انتهت فترة الـ 30 يوماً الخاصة بك. يرجى تفعيل اشتراكك للاستمرار في التداول الآلي بالذكاء الاصطناعي.</p>
            </div>
          </div>
          <Link
            href="/subscription"
            className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-cyan-500 transition-all duration-300"
          >
            تفعيل الاشتراك الآن
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-blue-500/20 bg-gradient-to-r from-blue-950/30 to-cyan-950/30 p-5 backdrop-blur-xl">
      <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-blue-500/10 blur-2xl" />
      
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/15 text-blue-400 border border-blue-500/20">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h4 className="font-bold text-slate-200">أنت حالياً في الفترة التجريبية المجانية</h4>
            <p className="text-xs text-slate-400 mt-0.5">تبقت لديك <span className="font-bold text-blue-400 font-mono text-sm">{daysLeft}</span> أيام. جميع الميزات والوكلاء مفعلون بالكامل.</p>
          </div>
        </div>
        <Link
          href="/subscription"
          className="flex items-center justify-center gap-2 rounded-xl border border-blue-500/30 bg-blue-500/10 px-5 py-2 text-xs font-bold text-blue-300 hover:bg-blue-500/25 transition-all duration-300"
        >
          ترقية الحساب
          <ArrowLeft className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  )
}
