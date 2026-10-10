import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import { stripe, STRIPE_PLANS } from '@/lib/stripe'
import { getUserByClerkId, getSubscriptionStatus } from '@/lib/services/user-service'
import { createServerClient } from '@/lib/supabase/server'

// ============================================================
// POST /api/subscription/create-checkout
// إنشاء Stripe Checkout Session
// ============================================================
export async function POST(req: NextRequest) {
  const { userId: clerkId } = await auth()
  if (!clerkId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { plan } = await req.json() // 'monthly' | 'yearly'

  if (!plan || !STRIPE_PLANS[plan as keyof typeof STRIPE_PLANS]) {
    return NextResponse.json({ error: 'Invalid plan' }, { status: 400 })
  }

  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  const supabase = createServerClient()

  // الحصول على أو إنشاء Stripe Customer
  const { data: subData } = await supabase
    .from('subscriptions')
    .select('*')
    .eq('user_id', user.id)
    .single()

  const sub = subData as any
  let customerId = sub?.stripe_customer_id

  if (!customerId) {
    const customer = await stripe.customers.create({
      email: user.email,
      name:  user.full_name || undefined,
      metadata: {
        clerk_id: clerkId,
        user_id:  user.id,
      },
    })
    customerId = customer.id

    // حفظ Customer ID
    await (supabase.from('subscriptions') as any)
      .update({ stripe_customer_id: customerId })
      .eq('user_id', user.id)
  }

  const selectedPlan = STRIPE_PLANS[plan as keyof typeof STRIPE_PLANS]

  // إنشاء Checkout Session
  const session = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: 'subscription',
    line_items: [{ price: selectedPlan.priceId, quantity: 1 }],
    success_url: `${process.env.APP_URL}/dashboard?payment=success`,
    cancel_url:  `${process.env.APP_URL}/subscription?payment=cancelled`,
    metadata: {
      user_id: user.id,
      plan,
    },
    subscription_data: {
      metadata: { user_id: user.id, plan },
    },
    allow_promotion_codes: true,
    billing_address_collection: 'required',
  })

  return NextResponse.json({ url: session.url })
}
