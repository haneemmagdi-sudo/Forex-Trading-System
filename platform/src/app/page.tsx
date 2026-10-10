import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Quantum Forex AI — نظام التداول الذكي بالذكاء الاصطناعي',
  description: '4 وكلاء ذكاء اصطناعي يعملون على 15 زوجاً في MT5. جرّب مجاناً لمدة 30 يوماً.',
}

export default function LandingPage() {
  return (
    <main style={{ fontFamily: 'Cairo, Tajawal, sans-serif', direction: 'rtl' }}>

      {/* ── Header ───────────────────────────────────────────── */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        background: 'rgba(8,11,20,0.9)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(99,179,237,0.1)',
        padding: '16px 40px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: '1.8rem' }}>⚡</span>
          <span style={{
            fontSize: '1.2rem', fontWeight: 800, color: '#f1f5f9',
          }}>Quantum Forex AI</span>
        </div>
        <nav style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Link href="/sign-in" style={{
            color: '#94a3b8', textDecoration: 'none', padding: '8px 16px',
            borderRadius: 8, transition: 'color 0.2s',
          }}>تسجيل الدخول</Link>
          <Link href="/sign-up" className="btn-primary" style={{
            background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
            color: 'white', padding: '10px 24px', borderRadius: 10,
            textDecoration: 'none', fontWeight: 600, fontSize: '0.95rem',
          }}>ابدأ مجاناً ←</Link>
        </nav>
      </header>

      {/* ── Hero Section ─────────────────────────────────────── */}
      <section style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', flexDirection: 'column',
        textAlign: 'center', padding: '120px 40px 80px',
        background: 'radial-gradient(ellipse at top, rgba(59,130,246,0.08) 0%, transparent 60%), radial-gradient(ellipse at bottom, rgba(6,182,212,0.05) 0%, transparent 60%), #080b14',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* خلفية ديكور */}
        <div style={{
          position: 'absolute', top: '20%', left: '10%',
          width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: '20%', right: '10%',
          width: 300, height: 300, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ maxWidth: 800, position: 'relative', zIndex: 1 }}>
          {/* Badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)',
            borderRadius: 100, padding: '6px 18px', marginBottom: 32, color: '#60a5fa',
            fontSize: '0.9rem', fontWeight: 600,
          }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block', animation: 'pulse 2s infinite' }} />
            نظام الذكاء الاصطناعي — 4 وكلاء | 15 زوجاً
          </div>

          {/* العنوان */}
          <h1 style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontWeight: 900, lineHeight: 1.2, marginBottom: 24, color: '#f1f5f9' }}>
            تداول أذكى مع{' '}
            <span style={{
              background: 'linear-gradient(135deg, #60a5fa, #06b6d4, #10b981)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              الذكاء الاصطناعي
            </span>
          </h1>

          <p style={{
            fontSize: '1.25rem', color: '#94a3b8', lineHeight: 1.8, marginBottom: 48,
            maxWidth: 600, margin: '0 auto 48px',
          }}>
            4 وكلاء ذكاء اصطناعي يعملون على 15 زوجاً في حسابك: محلل السوق، منفذ الصفقات، المراقب، والمتعلم المستمر.
          </p>

          {/* CTAs */}
          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 64 }}>
            <Link href="/sign-up" style={{
              background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
              color: 'white', padding: '16px 36px', borderRadius: 14,
              textDecoration: 'none', fontWeight: 700, fontSize: '1.1rem',
              display: 'inline-flex', alignItems: 'center', gap: 10,
              boxShadow: '0 4px 20px rgba(59,130,246,0.35)',
              transition: 'all 0.3s',
            }}>
              🚀 ابدأ التجربة المجانية (30 يوم)
            </Link>
            <Link href="#how-it-works" style={{
              background: 'transparent', color: '#94a3b8',
              padding: '16px 36px', borderRadius: 14,
              textDecoration: 'none', fontWeight: 600, fontSize: '1.1rem',
              border: '1px solid rgba(148,163,184,0.2)',
              display: 'inline-flex', alignItems: 'center', gap: 10,
            }}>
              كيف يعمل؟ ←
            </Link>
          </div>

          {/* إحصائيات */}
          <div style={{ display: 'flex', gap: 40, justifyContent: 'center', flexWrap: 'wrap' }}>
            {[
              { num: '15', label: 'زوج عملات مدعوم' },
              { num: '30', label: 'يوم تجربة مجانية' },
              { num: '24/7', label: 'تداول مستمر' },
            ].map(stat => (
              <div key={stat.label} style={{ textAlign: 'center' }}>
                <div style={{
                  fontSize: '2.5rem', fontWeight: 900,
                  background: 'linear-gradient(135deg, #60a5fa, #06b6d4)',
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                }}>{stat.num}</div>
                <div style={{ color: '#64748b', fontSize: '0.9rem', marginTop: 4 }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── الوكلاء الأربعة ────────────────────────────────────── */}
      <section style={{ padding: '100px 40px', background: '#0d1117' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <h2 style={{ textAlign: 'center', fontSize: '2.5rem', fontWeight: 800, marginBottom: 16, color: '#f1f5f9' }}>
            الوكلاء الأربعة
          </h2>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: 64, fontSize: '1.1rem' }}>
            كل وكيل مختص في مهمة محددة، يعملون معاً كفريق متكامل
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 24 }}>
            {[
              { icon: '🔍', name: 'محلل السوق', color: '#3b82f6', desc: 'يحلل الأزواج كل 5 ثواني باستخدام 10+ مؤشر فني وآلية FSM للتعرف على حالة السوق' },
              { icon: '⚡', name: 'منفذ الصفقات', color: '#10b981', desc: 'يُنفّذ الصفقات بدقة مع إدارة المخاطر التلقائية، SL/TP ديناميكي، وإغلاق جزئي متعدد المستويات' },
              { icon: '👁️', name: 'وكيل المراقبة', color: '#f59e0b', desc: 'يراقب الصفقات المفتوحة كل ثانية، ينقل SL لنقطة التعادل، ويُفعّل Trailing Stop تلقائياً' },
              { icon: '🧠', name: 'وكيل التعلم', color: '#8b5cf6', desc: 'يحلل أداء الصفقات السابقة كل ساعة ويُعدّل أوزان المؤشرات لتحسين الدقة مع الوقت' },
            ].map(agent => (
              <div key={agent.name} style={{
                background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(99,179,237,0.1)',
                borderRadius: 16, padding: 28, textAlign: 'center',
                transition: 'all 0.3s',
              }}>
                <div style={{ fontSize: '2.5rem', marginBottom: 16 }}>{agent.icon}</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: agent.color, marginBottom: 12 }}>{agent.name}</div>
                <div style={{ color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.7 }}>{agent.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── الأزواج المدعومة ─────────────────────────────────── */}
      <section style={{ padding: '80px 40px', background: '#080b14' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <h2 style={{ textAlign: 'center', fontSize: '2rem', fontWeight: 800, marginBottom: 12, color: '#f1f5f9' }}>
            15 زوج عملات مدعوم
          </h2>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: 48, fontSize: '1rem' }}>
            الوكلاء يعملون على الأزواج الرئيسية والثانوية في آنٍ واحد — أدنى لوت 0.01
          </p>

          <div style={{ display: 'grid', gap: 24, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
            {/* Majors */}
            <div style={{
              background: 'rgba(59,130,246,0.04)', border: '1px solid rgba(59,130,246,0.15)',
              borderRadius: 16, padding: 24,
            }}>
              <div style={{ color: '#60a5fa', fontWeight: 700, marginBottom: 16, fontSize: '1rem' }}>
                🏆 الأزواج الرئيسية (Majors)
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD'].map(p => (
                  <span key={p} style={{
                    background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                    borderRadius: 8, padding: '4px 12px', color: '#93c5fd',
                    fontFamily: 'monospace', fontSize: '0.9rem', fontWeight: 600,
                  }}>{p}</span>
                ))}
              </div>
            </div>

            {/* Crosses */}
            <div style={{
              background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.15)',
              borderRadius: 16, padding: 24,
            }}>
              <div style={{ color: '#34d399', fontWeight: 700, marginBottom: 16, fontSize: '1rem' }}>
                💎 الأزواج الثانوية (Crosses)
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {['EURJPY', 'GBPJPY', 'EURGBP', 'EURAUD', 'EURCAD', 'GBPAUD', 'AUDCAD', 'NZDJPY'].map(p => (
                  <span key={p} style={{
                    background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)',
                    borderRadius: 8, padding: '4px 12px', color: '#6ee7b7',
                    fontFamily: 'monospace', fontSize: '0.9rem', fontWeight: 600,
                  }}>{p}</span>
                ))}
              </div>
            </div>
          </div>

          <p style={{
            textAlign: 'center', marginTop: 32, color: '#475569', fontSize: '0.85rem',
            background: 'rgba(30,41,59,0.5)', borderRadius: 10, padding: '10px 20px',
            display: 'inline-block', width: '100%', boxSizing: 'border-box',
          }}>
            ⚙️ الحد الأدنى للوت: <strong style={{ color: '#94a3b8' }}>0.01</strong> لكل زوج &nbsp;|&nbsp;
            يُفعَّل التداول عند تحقق شروط مجلس التصويت (9 مؤشرات) + FSM
          </p>
        </div>
      </section>

      {/* ── كيف يعمل ─────────────────────────────────────────── */}
      <section id="how-it-works" style={{ padding: '100px 40px', background: '#0d1117' }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <h2 style={{ textAlign: 'center', fontSize: '2.5rem', fontWeight: 800, marginBottom: 16, color: '#f1f5f9' }}>
            ابدأ في 4 خطوات فقط
          </h2>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: 64, fontSize: '1.1rem' }}>
            من التسجيل إلى التداول الفعلي في دقائق
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {[
              { num: '01', title: 'سجّل حساباً مجاناً', desc: 'أنشئ حسابك بالبريد الإلكتروني أو Google. التجربة المجانية 30 يوم تبدأ فوراً.', color: '#3b82f6' },
              { num: '02', title: 'ربط حسابك في MT5', desc: 'أضف بيانات حسابك (رقم الحساب + كلمة المرور + اسم السيرفر). تُحفظ مشفّرة بأمان.', color: '#10b981' },
              { num: '03', title: 'حمّل وشغّل الـ Agent', desc: 'نزّل برنامج صغير على جهازك (Windows) يتصل بـ MT5 محلياً ويرسل البيانات للسحابة.', color: '#f59e0b' },
              { num: '04', title: 'تابع من أي مكان', desc: 'افتح Dashboard الموقع من أي جهاز أو موبايل وتابع الوكلاء والصفقات في الوقت الفعلي.', color: '#8b5cf6' },
            ].map(step => (
              <div key={step.num} style={{
                display: 'flex', gap: 24, alignItems: 'flex-start',
                background: 'rgba(17,24,39,0.6)', border: '1px solid rgba(99,179,237,0.08)',
                borderRadius: 16, padding: 28,
              }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 14, flexShrink: 0,
                  background: `${step.color}22`, border: `2px solid ${step.color}44`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1.1rem', fontWeight: 800, color: step.color,
                }}>{step.num}</div>
                <div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>{step.title}</div>
                  <div style={{ color: '#94a3b8', lineHeight: 1.7 }}>{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── الأسعار ───────────────────────────────────────────── */}
      <section id="pricing" style={{ padding: '100px 40px', background: '#0d1117' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <h2 style={{ textAlign: 'center', fontSize: '2.5rem', fontWeight: 800, marginBottom: 16, color: '#f1f5f9' }}>
            خطط الأسعار
          </h2>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: 64, fontSize: '1.1rem' }}>
            ابدأ مجاناً، ادفع فقط إذا أعجبك
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 24 }}>
            {/* تجربة مجانية */}
            <div style={{
              background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(99,179,237,0.15)',
              borderRadius: 20, padding: 36, textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', marginBottom: 12 }}>🎁</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>تجربة مجانية</div>
              <div style={{ fontSize: '3rem', fontWeight: 900, color: '#10b981', marginBottom: 4 }}>$0</div>
              <div style={{ color: '#64748b', marginBottom: 28 }}>لمدة 30 يوماً</div>
              <ul style={{ listStyle: 'none', textAlign: 'right', marginBottom: 32 }}>
                {['جميع المميزات', '4 وكلاء ذكاء اصطناعي', '15 زوج مدعوم', 'Dashboard كامل'].map(f => (
                  <li key={f} style={{ color: '#94a3b8', padding: '6px 0', borderBottom: '1px solid rgba(99,179,237,0.05)', display: 'flex', gap: 10 }}>
                    <span style={{ color: '#10b981' }}>✓</span> {f}
                  </li>
                ))}
              </ul>
              <Link href="/sign-up" style={{
                display: 'block', background: 'rgba(16,185,129,0.15)', color: '#10b981',
                border: '1px solid rgba(16,185,129,0.3)', padding: '12px',
                borderRadius: 10, textDecoration: 'none', fontWeight: 600,
              }}>ابدأ مجاناً</Link>
            </div>

            {/* شهري */}
            <div style={{
              background: 'rgba(17,24,39,0.8)',
              border: '2px solid rgba(59,130,246,0.5)',
              borderRadius: 20, padding: 36, textAlign: 'center',
              position: 'relative', boxShadow: '0 0 40px rgba(59,130,246,0.15)',
            }}>
              <div style={{
                position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)',
                background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
                color: 'white', padding: '4px 18px', borderRadius: 100,
                fontSize: '0.8rem', fontWeight: 700,
              }}>الأكثر شيوعاً</div>
              <div style={{ fontSize: '2rem', marginBottom: 12 }}>⚡</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>الخطة الشهرية</div>
              <div style={{ fontSize: '3rem', fontWeight: 900, color: '#3b82f6', marginBottom: 4 }}>$29</div>
              <div style={{ color: '#64748b', marginBottom: 28 }}>/ شهرياً</div>
              <ul style={{ listStyle: 'none', textAlign: 'right', marginBottom: 32 }}>
                {['جميع المميزات', '4 وكلاء ذكاء اصطناعي', '15 زوج مدعوم', 'Dashboard كامل', 'دعم فني'].map(f => (
                  <li key={f} style={{ color: '#94a3b8', padding: '6px 0', borderBottom: '1px solid rgba(99,179,237,0.05)', display: 'flex', gap: 10 }}>
                    <span style={{ color: '#3b82f6' }}>✓</span> {f}
                  </li>
                ))}
              </ul>
              <Link href="/sign-up" style={{
                display: 'block',
                background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
                color: 'white', padding: '12px',
                borderRadius: 10, textDecoration: 'none', fontWeight: 600,
              }}>اشترك الآن</Link>
            </div>

            {/* سنوي */}
            <div style={{
              background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(245,158,11,0.3)',
              borderRadius: 20, padding: 36, textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', marginBottom: 12 }}>👑</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>الخطة السنوية</div>
              <div style={{ fontSize: '3rem', fontWeight: 900, color: '#f59e0b', marginBottom: 4 }}>$199</div>
              <div style={{ color: '#64748b', marginBottom: 4 }}>/ سنوياً</div>
              <div style={{ color: '#10b981', fontSize: '0.85rem', marginBottom: 24 }}>وفّر 43% ($149)</div>
              <ul style={{ listStyle: 'none', textAlign: 'right', marginBottom: 32 }}>
                {['جميع المميزات', '4 وكلاء ذكاء اصطناعي', '15 زوج مدعوم', 'Dashboard كامل', 'دعم فني أولوية'].map(f => (
                  <li key={f} style={{ color: '#94a3b8', padding: '6px 0', borderBottom: '1px solid rgba(99,179,237,0.05)', display: 'flex', gap: 10 }}>
                    <span style={{ color: '#f59e0b' }}>✓</span> {f}
                  </li>
                ))}
              </ul>
              <Link href="/sign-up" style={{
                display: 'block', background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                border: '1px solid rgba(245,158,11,0.3)', padding: '12px',
                borderRadius: 10, textDecoration: 'none', fontWeight: 600,
              }}>اشترك سنوياً</Link>
            </div>
          </div>

          {/* طرق الدفع */}
          <div style={{ textAlign: 'center', marginTop: 48 }}>
            <p style={{ color: '#64748b', marginBottom: 16 }}>طرق الدفع المتاحة</p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              {['💳 Stripe', '🅿️ PayPal', '📱 Vodafone Cash', '📲 InstaPay'].map(m => (
                <span key={m} style={{
                  background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(99,179,237,0.1)',
                  borderRadius: 8, padding: '8px 16px', color: '#94a3b8', fontSize: '0.9rem',
                }}>{m}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA Footer ───────────────────────────────────────── */}
      <section style={{
        padding: '100px 40px', textAlign: 'center',
        background: 'radial-gradient(ellipse at center, rgba(59,130,246,0.08) 0%, transparent 60%), #080b14',
      }}>
        <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: '#f1f5f9', marginBottom: 20 }}>
          جاهز للبدء؟
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '1.1rem', marginBottom: 40 }}>
          30 يوماً مجاناً. لا حاجة لبطاقة ائتمان.
        </p>
        <Link href="/sign-up" style={{
          display: 'inline-flex', alignItems: 'center', gap: 12,
          background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
          color: 'white', padding: '18px 48px', borderRadius: 16,
          textDecoration: 'none', fontWeight: 700, fontSize: '1.2rem',
          boxShadow: '0 8px 30px rgba(59,130,246,0.4)',
        }}>
          🚀 ابدأ التجربة المجانية الآن
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer style={{
        background: '#0d1117', borderTop: '1px solid rgba(99,179,237,0.08)',
        padding: '40px', textAlign: 'center', color: '#475569',
      }}>
        <div style={{ marginBottom: 16 }}>
          <span style={{ fontSize: '1.5rem' }}>⚡</span>
          <span style={{ fontWeight: 700, color: '#64748b', marginRight: 8 }}>Quantum Forex AI</span>
        </div>
        <p style={{ fontSize: '0.85rem' }}>
          © 2026 Quantum Forex AI. جميع الحقوق محفوظة.
          &nbsp;|&nbsp; تحذير: التداول ينطوي على مخاطر. لا نضمن أرباحاً.
        </p>
      </footer>
    </main>
  )
}
