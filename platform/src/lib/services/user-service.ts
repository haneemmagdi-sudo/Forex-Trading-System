import { createServerClient } from '@/lib/supabase/server'
import type { User, SubscriptionStatus } from '@/lib/supabase/types'

// ── الحصول على user_id من clerk_id ────────────────────────────
export async function getUserByClerkId(clerkId: string): Promise<User | null> {
  const supabase = createServerClient()
  const { data, error } = await supabase
    .from('users')
    .select('*')
    .eq('clerk_id', clerkId)
    .single()

  if (error) return null
  return data as User | null
}

// ── حالة الاشتراك الكاملة ──────────────────────────────────────
export async function getSubscriptionStatus(userId: string): Promise<SubscriptionStatus> {
  const supabase = createServerClient()

  const { data: subData } = await supabase
    .from('subscriptions')
    .select('*')
    .eq('user_id', userId)
    .single()

  const sub = subData as any

  if (!sub) {
    return { isActive: false, plan: 'none', isTrial: false, trialDaysLeft: 0, trialEnd: null, isExpired: true }
  }

  const now = new Date()
  const trialEnd = sub.trial_end ? new Date(sub.trial_end) : null
  const isTrial = sub.plan === 'trial'
  const trialDaysLeft = trialEnd ? Math.max(0, Math.ceil((trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))) : 0

  let isActive = sub.status === 'active'

  // إذا كانت تجربة مجانية، تحقق من انتهاء المدة
  if (isTrial && trialEnd && now > trialEnd) {
    isActive = false
    // تحديث الحالة في قاعدة البيانات
    await (supabase.from('subscriptions') as any)
      .update({ status: 'expired' })
      .eq('id', sub.id)
  }

  // إذا كانت اشتراك مدفوع، تحقق من current_period_end
  if (!isTrial && sub.current_period_end) {
    const periodEnd = new Date(sub.current_period_end)
    if (now > periodEnd) {
      isActive = false
    }
  }

  return {
    isActive,
    plan: sub.plan,
    isTrial,
    trialDaysLeft,
    trialEnd,
    isExpired: !isActive,
  }
}

// ── إنشاء مستخدم جديد بعد Clerk Webhook ───────────────────────
export async function createUserWithTrial(params: {
  clerkId: string
  email: string
  fullName?: string
  avatarUrl?: string
}) {
  const supabase = createServerClient()

  // 1. إنشاء المستخدم
  const { data: userData, error: userError } = await (supabase.from('users') as any)
    .insert({
      clerk_id: params.clerkId,
      email: params.email,
      full_name: params.fullName ?? null,
      avatar_url: params.avatarUrl ?? null,
    })
    .select()
    .single()

  const user = userData as any

  if (userError || !user) {
    throw new Error(`Failed to create user: ${userError?.message}`)
  }

  // 2. إنشاء اشتراك تجريبي مجاني (30 يوم)
  const { error: subError } = await (supabase.from('subscriptions') as any)
    .insert({
      user_id: user.id,
      plan: 'trial',
      status: 'active',
    })

  if (subError) {
    throw new Error(`Failed to create subscription: ${subError?.message}`)
  }

  return user
}

// ── تشفير/فك تشفير كلمة مرور MT5 ─────────────────────────────
// نستخدم تشفير بسيط على الـ server
function getEncryptionKey() {
  const key = process.env.ENCRYPTION_KEY
  if (!key || key.length < 32) throw new Error('ENCRYPTION_KEY must be at least 32 characters')
  return key.substring(0, 32)
}

export function encryptPassword(password: string): string {
  // XOR بسيط مع المفتاح + base64 (للإنتاج: استخدم AES-256)
  const key = getEncryptionKey()
  let result = ''
  for (let i = 0; i < password.length; i++) {
    result += String.fromCharCode(password.charCodeAt(i) ^ key.charCodeAt(i % key.length))
  }
  return Buffer.from(result).toString('base64')
}

export function decryptPassword(encrypted: string): string {
  const key = getEncryptionKey()
  const decoded = Buffer.from(encrypted, 'base64').toString()
  let result = ''
  for (let i = 0; i < decoded.length; i++) {
    result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length))
  }
  return result
}
