import Link from 'next/link'
import { redirect } from 'next/navigation'
import { UserButton, SignedIn } from '@clerk/nextjs'
import { auth } from '@clerk/nextjs/server'
import { LayoutDashboard, Radio, CreditCard, Settings, Compass, Menu } from 'lucide-react'
import { createServerClient } from '@/lib/supabase/server'
import { getUserByClerkId } from '@/lib/services/user-service'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { name: 'لوحة التحكم', href: '/dashboard', icon: LayoutDashboard },
  { name: 'ربط حساب MT5', href: '/connect-mt5', icon: Radio },
  { name: 'الاشتراك والأسعار', href: '/subscription', icon: CreditCard },
  { name: 'الإعدادات', href: '/settings', icon: Settings },
]

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { userId: clerkId } = await auth()

  if (!clerkId) {
    redirect('/sign-in')
  }

  // الحصول على بيانات المستخدم وحساب MT5 للتحقق من الاتصال
  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)

  let isAgentOnline = false
  let loginNumber: number | null = null

  if (user) {
    const { data } = await supabase
      .from('mt5_accounts')
      .select('login, is_connected, last_seen_at')
      .eq('user_id', user.id)
      .eq('is_active', true)
      .single()

    const account = data as any

    if (account) {
      loginNumber = Number(account.login)
      const lastSeen = account.last_seen_at ? new Date(account.last_seen_at) : null
      isAgentOnline = account.is_connected && lastSeen ? (Date.now() - lastSeen.getTime()) < 30_000 : false
    }
  }

  return (
    <div className="min-h-screen bg-[#080b14] text-slate-100 font-sans flex flex-col md:flex-row" style={{ fontFamily: 'Cairo, Tajawal, sans-serif', direction: 'rtl' }}>
      
      {/* ── Sidebar ───────────────────────────────────────────── */}
      <aside className="w-full md:w-64 flex-shrink-0 bg-[#0c0f1d] border-l border-slate-800 flex flex-col">
        {/* Brand/Logo */}
        <div className="h-16 px-6 border-b border-slate-800 flex items-center gap-3">
          <span className="text-2xl text-blue-500 font-bold">⚡</span>
          <span className="font-extrabold text-slate-100 tracking-wide">Quantum Forex AI</span>
        </div>

        {/* User Quick Info */}
        <div className="p-4 border-b border-slate-800/60 bg-slate-900/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SignedIn>
              <UserButton appearance={{ elements: { avatarBox: 'h-9 w-9 border border-slate-700' } }} />
            </SignedIn>
            <div className="flex flex-col text-right">
              <span className="text-xs font-bold text-slate-300 truncate max-w-[120px]">{user?.full_name || 'مستخدم المنصة'}</span>
              <span className="text-[10px] text-slate-500 truncate max-w-[120px]">{user?.email}</span>
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold text-slate-400 hover:text-slate-100 hover:bg-slate-800/40 transition-all duration-200"
            >
              <item.icon className="h-4 w-4 text-slate-500 group-hover:text-slate-200" />
              <span>{item.name}</span>
            </Link>
          ))}
        </nav>

        {/* Agent Connection Indicator */}
        <div className="p-4 border-t border-slate-800 bg-[#060810]">
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/30 p-3 flex items-center justify-between">
            <div className="flex flex-col text-right">
              <span className="text-[11px] text-slate-500">حالة الـ MT5 Agent</span>
              <span className="text-xs font-bold text-slate-300">
                {loginNumber ? `حساب: ${loginNumber}` : 'غير مربوط'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${isAgentOnline ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-rose-500'}`} />
              <span className="text-[10px] font-bold text-slate-400">
                {isAgentOnline ? 'متصل' : 'أوفلاين'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ─────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Top Navbar */}
        <header className="h-16 px-8 border-b border-slate-800 flex items-center justify-between bg-[#080b14]/50 backdrop-blur-md sticky top-0 z-40">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-slate-200">لوحة التحكم</h1>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-xs font-bold text-blue-400 bg-blue-500/10 border border-blue-500/20 px-3.5 py-1.5 rounded-lg hover:bg-blue-500/20 transition-all duration-200"
            >
              الرئيسية
            </Link>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 md:p-8 space-y-8 overflow-y-auto">
          {children}
        </main>
      </div>

    </div>
  )
}
