import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'

// ── الـ Routes العامة (الزوار يرون فقط الصفحة الرئيسية) ───────
const isPublicRoute = createRouteMatcher([
  '/',                          // الصفحة الرئيسية فقط
  '/sign-in(.*)',               // تسجيل الدخول
  '/sign-up(.*)',               // التسجيل
  '/api/webhooks/(.*)',         // Webhooks (Clerk + Stripe) — بدون Auth
  '/api/mt5/heartbeat',        // Agent heartbeat — يستخدم agent_token
])

export default clerkMiddleware(async (auth, req) => {
  // كل الصفحات الأخرى تحتاج تسجيل دخول
  if (!isPublicRoute(req)) {
    await auth.protect()
  }

  return NextResponse.next()
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}

