import { UserProfile } from '@clerk/nextjs'

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">إعدادات الحساب</h1>
        <p className="text-sm text-slate-500">إدارة تفاصيل حسابك الشخصي، الأمان، وكلمة المرور عبر Clerk.</p>
      </div>

      <div className="flex justify-center rounded-3xl border border-slate-800 bg-[#0c0f1d]/20 p-6 backdrop-blur-xl">
        <UserProfile
          appearance={{
            variables: {
              colorPrimary: '#3b82f6',
              colorBackground: '#0c0f1d',
              colorInputBackground: '#080b14',
              colorInputText: '#f1f5f9',
              colorText: '#f1f5f9',
              colorTextSecondary: '#94a3b8',
              colorBorder: '#1e293b',
            },
            elements: {
              card: 'shadow-none bg-transparent w-full max-w-none border-none p-0',
              navbar: 'hidden md:flex', // hides navigation bar if desired or keep it
              pageScrollBox: 'p-0',
            }
          }}
        />
      </div>
    </div>
  )
}
