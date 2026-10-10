import { SignIn } from '@clerk/nextjs'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'تسجيل الدخول — Quantum Forex AI',
}

export default function SignInPage() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at top, rgba(59,130,246,0.08) 0%, transparent 60%), #080b14',
      fontFamily: 'Cairo, Tajawal, sans-serif',
      flexDirection: 'column',
      gap: 32,
      padding: '40px 20px',
    }}>
      {/* الشعار */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3rem', marginBottom: 8 }}>⚡</div>
        <h1 style={{ color: '#f1f5f9', fontSize: '1.8rem', fontWeight: 800, margin: 0 }}>Quantum Forex AI</h1>
        <p style={{ color: '#94a3b8', marginTop: 8 }}>مرحباً بعودتك</p>
      </div>

      {/* Clerk Sign In Component */}
      <SignIn
        appearance={{
          variables: {
            colorPrimary: '#3b82f6',
            colorBackground: '#111827',
            colorText: '#f1f5f9',
            colorInputBackground: '#1e293b',
            colorInputText: '#f1f5f9',
            borderRadius: '12px',
            fontFamily: 'Cairo, Tajawal, sans-serif',
          },
          elements: {
            card: {
              background: '#111827',
              border: '1px solid rgba(99,179,237,0.15)',
              boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
            },
            headerTitle: { color: '#f1f5f9', fontFamily: 'Cairo' },
            headerSubtitle: { color: '#94a3b8' },
          },
        }}
      />
    </div>
  )
}
