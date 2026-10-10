import Link from 'next/link'
import { auth } from '@clerk/nextjs/server'
import { createServerClient } from '@/lib/supabase/server'
import { getUserByClerkId, getSubscriptionStatus } from '@/lib/services/user-service'
import type { MT5Account } from '@/lib/supabase/types'
import TrialBanner from '@/components/dashboard/TrialBanner'
import AgentGrid from '@/components/dashboard/AgentGrid'
import PerformanceChart from '@/components/dashboard/PerformanceChart'
import TradesTable from '@/components/dashboard/TradesTable'
import { TrendingUp, DollarSign, Wallet, ShieldAlert, BarChart3 } from 'lucide-react'

export default async function DashboardPage() {
  const { userId: clerkId } = await auth()
  if (!clerkId) return null

  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return <div className="text-center py-20 text-slate-400">جاري تحميل حسابك...</div>
  }

  // 1. جلب حساب MT5 النشط
  const { data } = await supabase
    .from('mt5_accounts')
    .select('*')
    .eq('user_id', user.id)
    .eq('is_active', true)
    .single()

  const account = data as MT5Account | null

  if (!account) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center space-y-6 max-w-lg mx-auto">
        <div className="h-16 w-16 bg-blue-500/10 text-blue-400 rounded-2xl flex items-center justify-center border border-blue-500/20 text-3xl">
          🔌
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-100">يرجى ربط حساب MT5 أولاً</h2>
          <p className="text-slate-400 mt-2">لتشغيل وكلاء الذكاء الاصطناعي ومراقبة صفقاتك، يجب عليك إدخال إعدادات حساب التداول وتثبيت الـ Agent.</p>
        </div>
        <Link
          href="/connect-mt5"
          className="bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-bold px-8 py-3.5 rounded-xl shadow-lg shadow-blue-500/25 hover:from-blue-500 hover:to-cyan-500 transition-all duration-350"
        >
          اذهب لصفحة الربط الآن
        </Link>
      </div>
    )
  }

  // 2. التحقق من حالة اتصال الـ Agent
  const lastSeen = account.last_seen_at ? new Date(account.last_seen_at) : null
  const isAgentOnline = account.is_connected && lastSeen ? (Date.now() - lastSeen.getTime()) < 30_000 : false

  // 3. جلب حالة الاشتراك
  const subStatus = await getSubscriptionStatus(user.id)

  // 4. جلب الصفقات
  const { data: tradesData } = await supabase
    .from('trades')
    .select('*')
    .eq('user_id', user.id)
    .order('opened_at', { ascending: false })
    .limit(100)
  const trades = (tradesData || []) as any[]

  // 5. جلب لقطات الأداء
  const { data: snapshotsData } = await supabase
    .from('performance_snapshots')
    .select('*')
    .eq('user_id', user.id)
    .order('recorded_at', { ascending: false })
    .limit(50)
  const snapshots = (snapshotsData || []) as any[]

  // 6. تحديد حالة الوكلاء الأربعة
  const getLatestAgentAction = async (agentName: string) => {
    const { data } = await supabase
      .from('agent_commands')
      .select('action')
      .eq('account_id', account.id)
      .eq('agent_name', agentName)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()
    return data ? (data as any).action : 'resume'
  }

  const analystAction = await getLatestAgentAction('MarketAnalyst')
  const executorAction = await getLatestAgentAction('ExecutionAgent')
  const monitorAction = await getLatestAgentAction('MonitorAgent')
  const learnerAction = await getLatestAgentAction('LearningAgent')

  const mapActionToStatus = (action: string): 'active' | 'paused' | 'stopped' | 'offline' => {
    if (action === 'pause') return 'paused'
    if (action === 'stop') return 'stopped'
    return 'active'
  }

  const agents = [
    {
      id: 'MarketAnalyst',
      name: 'Market Analyst Agent',
      arabicName: 'محلل السوق AI',
      description: 'يحلل الأزواج كل 5 ثواني باستخدام المؤشرات الفنية وآليات الـ FSM لتحديد اتجاه السوق.',
      status: mapActionToStatus(analystAction),
    },
    {
      id: 'ExecutionAgent',
      name: 'Execution Agent',
      arabicName: 'منفّذ الصفقات AI',
      description: 'يفتح ويغلق الصفقات بناءً على إشارات المحلل مع إدارة اللوت وحساب المخاطرة التلقائي.',
      status: mapActionToStatus(executorAction),
    },
    {
      id: 'MonitorAgent',
      name: 'Monitor Agent',
      arabicName: 'مراقب الصفقات AI',
      description: 'يراقب الصفقات المفتوحة كل ثانية، يطبق الـ Trailing Stop وينقل الـ SL لنقطة التعادل.',
      status: mapActionToStatus(monitorAction),
    },
    {
      id: 'LearningAgent',
      name: 'Learning Agent',
      arabicName: 'وكيل التعلم المستمر AI',
      description: 'يحلل صفقاتك السابقة كل ساعة ويقوم بتعديل أوزان المؤشرات لتحسين دقة استراتيجيتك.',
      status: mapActionToStatus(learnerAction),
    },
  ]

  // إحصائيات سريعة
  const latestSnapshot = snapshots[0]
  const balance = latestSnapshot?.balance || 0
  const equity = latestSnapshot?.equity || 0
  const drawdown = latestSnapshot?.drawdown_pct || 0
  const openTradesCount = trades.filter(t => t.status === 'OPEN').length

  const closedTrades = trades.filter(t => t.status === 'CLOSED')
  const winTradesCount = closedTrades.filter(t => (t.profit_usd || 0) > 0).length
  const winRate = closedTrades.length > 0 ? (winTradesCount / closedTrades.length) * 100 : 0

  return (
    <div className="space-y-8">
      {/* Trial Banner */}
      <TrialBanner
        daysLeft={subStatus.trialDaysLeft}
        isActive={subStatus.isActive}
        isTrial={subStatus.isTrial}
      />

      {/* == Quick Stats Grid == */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
        {/* Balance */}
        <div className="rounded-2xl border border-slate-800 bg-[#0c0f1d]/40 p-5 flex items-center justify-between">
          <div className="space-y-1.5 text-right">
            <span className="text-xs text-slate-500">رصيد الحساب (Balance)</span>
            <h3 className="text-xl font-bold text-slate-100 font-mono">${balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</h3>
          </div>
          <div className="h-10 w-10 bg-blue-500/10 text-blue-400 rounded-xl flex items-center justify-center border border-blue-500/20">
            <Wallet className="h-5 w-5" />
          </div>
        </div>

        {/* Equity */}
        <div className="rounded-2xl border border-slate-800 bg-[#0c0f1d]/40 p-5 flex items-center justify-between">
          <div className="space-y-1.5 text-right">
            <span className="text-xs text-slate-500">صافي الأصول (Equity)</span>
            <h3 className="text-xl font-bold text-slate-100 font-mono">${equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}</h3>
          </div>
          <div className="h-10 w-10 bg-emerald-500/10 text-emerald-400 rounded-xl flex items-center justify-center border border-emerald-500/20">
            <DollarSign className="h-5 w-5" />
          </div>
        </div>

        {/* Open Trades */}
        <div className="rounded-2xl border border-slate-800 bg-[#0c0f1d]/40 p-5 flex items-center justify-between">
          <div className="space-y-1.5 text-right">
            <span className="text-xs text-slate-500">الصفقات المفتوحة</span>
            <h3 className="text-xl font-bold text-slate-100 font-mono">{openTradesCount} صفقات</h3>
          </div>
          <div className="h-10 w-10 bg-cyan-500/10 text-cyan-400 rounded-xl flex items-center justify-center border border-cyan-500/20">
            <TrendingUp className="h-5 w-5" />
          </div>
        </div>

        {/* Win Rate */}
        <div className="rounded-2xl border border-slate-800 bg-[#0c0f1d]/40 p-5 flex items-center justify-between">
          <div className="space-y-1.5 text-right">
            <span className="text-xs text-slate-500">معدل الصفقات الرابحة</span>
            <h3 className="text-xl font-bold text-slate-100 font-mono">{winRate.toFixed(1)}%</h3>
          </div>
          <div className="h-10 w-10 bg-purple-500/10 text-purple-400 rounded-xl flex items-center justify-center border border-purple-500/20">
            <BarChart3 className="h-5 w-5" />
          </div>
        </div>

        {/* Max Drawdown */}
        <div className="rounded-2xl border border-slate-800 bg-[#0c0f1d]/40 p-5 flex items-center justify-between">
          <div className="space-y-1.5 text-right">
            <span className="text-xs text-slate-500">التراجع الحالي (Drawdown)</span>
            <h3 className="text-xl font-bold text-rose-400 font-mono">{drawdown.toFixed(2)}%</h3>
          </div>
          <div className="h-10 w-10 bg-rose-500/10 text-rose-400 rounded-xl flex items-center justify-center border border-rose-500/20">
            <ShieldAlert className="h-5 w-5" />
          </div>
        </div>
      </div>

      {/* == Agents Control Grid == */}
      <div>
        <div className="mb-4">
          <h2 className="text-xl font-bold text-slate-200">التحكم في وكلاء الذكاء الاصطناعي</h2>
          <p className="text-xs text-slate-500">تحكم بالوكلاء الأربعة كفريق متكامل أو قم بتخصيص تشغيل كل وكيل على حدة.</p>
        </div>
        <AgentGrid agents={agents} isAgentOnline={isAgentOnline} />
      </div>

      {/* == Charts & Tables == */}
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TradesTable trades={trades} />
        </div>
        <div>
          <PerformanceChart data={snapshots} />
        </div>
      </div>
    </div>
  )
}
