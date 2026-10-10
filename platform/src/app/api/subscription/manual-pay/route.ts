import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import { createServerClient } from '@/lib/supabase/server'
import { getUserByClerkId } from '@/lib/services/user-service'

// ============================================================
// POST /api/subscription/manual-pay — تسجيل دفع يدوي
// ============================================================
export async function POST(req: NextRequest) {
  const { userId: clerkId } = await auth()
  if (!clerkId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json()
  const { method, plan, transferRef, amount } = body

  if (!method || !plan || !transferRef || !amount) {
    return NextResponse.json({ error: 'جميع الحقول مطلوبة' }, { status: 400 })
  }

  if (method !== 'vodafone_cash' && method !== 'instapay') {
    return NextResponse.json({ error: 'طريقة دفع غير صالحة' }, { status: 400 })
  }

  if (plan !== 'monthly' && plan !== 'yearly') {
    return NextResponse.json({ error: 'الخطة المختارة غير صالحة' }, { status: 400 })
  }

  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return NextResponse.json({ error: 'المستخدم غير موجود' }, { status: 404 })
  }

  // تسجيل الطلب في جدول manual_payments بوضع pending
  const { data: payment, error } = await (supabase.from('manual_payments') as any)
    .insert({
      user_id: user.id,
      method,
      plan,
      amount: parseFloat(amount),
      currency: 'EGP',
      transfer_ref: transferRef,
      status: 'pending',
    })
    .select()
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({
    success: true,
    payment,
  })
}
