import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import { createServerClient } from '@/lib/supabase/server'
import { getUserByClerkId, encryptPassword } from '@/lib/services/user-service'

// ============================================================
// POST /api/mt5/connect — ربط حساب MT5
// ============================================================
export async function POST(req: NextRequest) {
  const { userId: clerkId } = await auth()
  if (!clerkId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json()
  const { login, password, server, brokerName, accountType } = body

  if (!login || !password || !server) {
    return NextResponse.json({ error: 'login, password, server are required' }, { status: 400 })
  }

  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  // تشفير كلمة المرور
  const passwordEnc = encryptPassword(password)

  // حذف أي حساب سابق لنفس المستخدم (حساب واحد لكل مستخدم حالياً)
  await supabase.from('mt5_accounts').delete().eq('user_id', user.id)

  // إنشاء حساب MT5 جديد
  const { data: account, error } = await (supabase.from('mt5_accounts') as any)
    .insert({
      user_id:      user.id,
      login:        parseInt(login),
      password_enc: passwordEnc,
      server,
      broker_name:  brokerName || null,
      account_type: accountType || 'demo',
    })
    .select()
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({
    success: true,
    account: {
      id:          account.id,
      login:       account.login,
      server:      account.server,
      broker_name: account.broker_name,
      agent_token: account.agent_token,   // يحتاجه المستخدم لتشغيل الـ Agent
    }
  })
}

// ============================================================
// GET /api/mt5/connect — الحصول على حالة الاتصال
// ============================================================
export async function GET(req: NextRequest) {
  const { userId: clerkId } = await auth()
  if (!clerkId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  const { data } = await supabase
    .from('mt5_accounts')
    .select('id, login, server, broker_name, account_type, is_connected, last_seen_at, agent_token, agent_version')
    .eq('user_id', user.id)
    .eq('is_active', true)
    .single()

  const account = data as any

  if (!account) {
    return NextResponse.json({ connected: false, account: null })
  }

  // حساب آخر ظهور
  const lastSeen = account.last_seen_at ? new Date(account.last_seen_at) : null
  const isOnline = lastSeen ? (Date.now() - lastSeen.getTime()) < 30_000 : false // 30 ثانية

  return NextResponse.json({
    connected: account.is_connected && isOnline,
    account: {
      ...account,
      agent_token: account.agent_token, // للمستخدم فقط
      is_online: isOnline,
      last_seen_ago: lastSeen ? Math.floor((Date.now() - lastSeen.getTime()) / 1000) : null,
    }
  })
}
