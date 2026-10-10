import Stripe from 'stripe'

const stripeSecretKey = process.env.STRIPE_SECRET_KEY || 'dummy_key_for_build'

export const stripe = new Stripe(stripeSecretKey, {
  apiVersion: '2025-04-30.basil' as any,
  typescript: true,
})

// خطط الأسعار
export const STRIPE_PLANS = {
  monthly: {
    priceId: process.env.STRIPE_MONTHLY_PRICE_ID!,
    name: 'الخطة الشهرية',
    price: 29,
    currency: 'usd',
    interval: 'month' as const,
  },
  yearly: {
    priceId: process.env.STRIPE_YEARLY_PRICE_ID!,
    name: 'الخطة السنوية',
    price: 199,
    currency: 'usd',
    interval: 'year' as const,
  },
}
