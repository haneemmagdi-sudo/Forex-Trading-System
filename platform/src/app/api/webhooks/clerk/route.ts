import { NextRequest, NextResponse } from 'next/server'
import { Webhook } from 'svix'
import { createUserWithTrial } from '@/lib/services/user-service'
import { createServerClient } from '@/lib/supabase/server'

// ============================================================
// POST /api/webhooks/clerk
// يُستدعى تلقائياً عند: إنشاء مستخدم، حذفه، تحديثه
// ============================================================
export async function POST(req: NextRequest) {
  const WEBHOOK_SECRET = process.env.CLERK_WEBHOOK_SECRET

  if (!WEBHOOK_SECRET) {
    return NextResponse.json({ error: 'Missing CLERK_WEBHOOK_SECRET' }, { status: 500 })
  }

  // التحقق من توقيع Clerk
  const svix_id        = req.headers.get('svix-id')
  const svix_timestamp = req.headers.get('svix-timestamp')
  const svix_signature = req.headers.get('svix-signature')

  if (!svix_id || !svix_timestamp || !svix_signature) {
    return NextResponse.json({ error: 'Missing svix headers' }, { status: 400 })
  }

  const body = await req.text()
  const wh = new Webhook(WEBHOOK_SECRET)

  let evt: any
  try {
    evt = wh.verify(body, {
      'svix-id': svix_id,
      'svix-timestamp': svix_timestamp,
      'svix-signature': svix_signature,
    })
  } catch (err) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  const { type, data } = evt

  // ── إنشاء مستخدم جديد ─────────────────────────────────────
  if (type === 'user.created') {
    try {
      const primaryEmail = data.email_addresses?.find(
        (e: any) => e.id === data.primary_email_address_id
      )?.email_address

      if (!primaryEmail) {
        return NextResponse.json({ error: 'No email found' }, { status: 400 })
      }

      await createUserWithTrial({
        clerkId:   data.id,
        email:     primaryEmail,
        fullName:  [data.first_name, data.last_name].filter(Boolean).join(' ') || undefined,
        avatarUrl: data.image_url || undefined,
      })

      console.log(`[Clerk Webhook] Created user: ${primaryEmail}`)
    } catch (error: any) {
      console.error('[Clerk Webhook] Error creating user:', error.message)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
  }

  // ── تحديث بيانات المستخدم ──────────────────────────────────
  if (type === 'user.updated') {
    try {
      const supabase = createServerClient()
      const primaryEmail = data.email_addresses?.find(
        (e: any) => e.id === data.primary_email_address_id
      )?.email_address

      await (supabase.from('users') as any)
        .update({
          email:     primaryEmail,
          full_name: [data.first_name, data.last_name].filter(Boolean).join(' ') || null,
          avatar_url: data.image_url || null,
        })
        .eq('clerk_id', data.id)

      console.log(`[Clerk Webhook] Updated user: ${data.id}`)
    } catch (error: any) {
      console.error('[Clerk Webhook] Error updating user:', error.message)
    }
  }

  // ── حذف المستخدم ──────────────────────────────────────────
  if (type === 'user.deleted') {
    try {
      const supabase = createServerClient()
      // ON DELETE CASCADE سيحذف كل البيانات المرتبطة تلقائياً
      await supabase
        .from('users')
        .delete()
        .eq('clerk_id', data.id)

      console.log(`[Clerk Webhook] Deleted user: ${data.id}`)
    } catch (error: any) {
      console.error('[Clerk Webhook] Error deleting user:', error.message)
    }
  }

  return NextResponse.json({ received: true })
}
