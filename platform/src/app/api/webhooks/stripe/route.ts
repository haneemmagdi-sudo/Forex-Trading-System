import { NextRequest, NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { createServerClient } from '@/lib/supabase/server'
import type Stripe from 'stripe'

// ============================================================
// POST /api/webhooks/stripe
// يستقبل أحداث Stripe (دفع ناجح، إلغاء، تجديد...)
// ============================================================
export async function POST(req: NextRequest) {
  const body = await req.text()
  const sig  = req.headers.get('stripe-signature')

  if (!sig) {
    return NextResponse.json({ error: 'No signature' }, { status: 400 })
  }

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!)
  } catch (err: any) {
    return NextResponse.json({ error: `Webhook error: ${err.message}` }, { status: 400 })
  }

  const supabase = createServerClient()

  switch (event.type) {
    // ── دفع ناجح / تجديد ──────────────────────────────────
    case 'invoice.payment_succeeded': {
      const invoice = event.data.object as Stripe.Invoice
      const subscriptionId = invoice.subscription as string
      const stripeSubscription = await stripe.subscriptions.retrieve(subscriptionId)
      const userId = stripeSubscription.metadata.user_id

      if (userId) {
        await (supabase.from('subscriptions') as any).update({
          plan:                   stripeSubscription.metadata.plan || 'monthly',
          status:                 'active',
          stripe_subscription_id: subscriptionId,
          current_period_start:   new Date(stripeSubscription.current_period_start * 1000).toISOString(),
          current_period_end:     new Date(stripeSubscription.current_period_end   * 1000).toISOString(),
        }).eq('user_id', userId)
      }
      break
    }

    // ── فشل الدفع ─────────────────────────────────────────
    case 'invoice.payment_failed': {
      const invoice = event.data.object as Stripe.Invoice
      const subscriptionId = invoice.subscription as string
      const sub = await stripe.subscriptions.retrieve(subscriptionId)
      const userId = sub.metadata.user_id

      if (userId) {
        await (supabase.from('subscriptions') as any).update({
          status: 'past_due',
        }).eq('user_id', userId)
      }
      break
    }

    // ── إلغاء الاشتراك ────────────────────────────────────
    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription
      const userId = sub.metadata.user_id

      if (userId) {
        await (supabase.from('subscriptions') as any).update({
          status: 'cancelled',
          cancel_at_period_end: false,
        }).eq('user_id', userId)
      }
      break
    }

    // ── تحديث الاشتراك (إلغاء مجدوَل) ────────────────────
    case 'customer.subscription.updated': {
      const sub = event.data.object as Stripe.Subscription
      const userId = sub.metadata.user_id

      if (userId) {
        await (supabase.from('subscriptions') as any).update({
          cancel_at_period_end: sub.cancel_at_period_end,
          current_period_end:   new Date(sub.current_period_end * 1000).toISOString(),
        }).eq('user_id', userId)
      }
      break
    }
  }

  return NextResponse.json({ received: true })
}
