import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import { createServerClient } from '@/lib/supabase/server'
import { getUserByClerkId } from '@/lib/services/user-service'

// ============================================================
// POST /api/mt5/command — إرسال أمر للـ Agent
// ============================================================
export async function POST(req: NextRequest) {
  const { userId: clerkId } = await auth()
  if (!clerkId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json()
  const { agentName, action } = body // agentName: MarketAnalyst | ExecutionAgent...  action: pause | resume | stop

  if (!agentName || !action) {
    return NextResponse.json({ error: 'agentName and action are required' }, { status: 400 })
  }

  const validAgents = ['MarketAnalyst', 'ExecutionAgent', 'MonitorAgent', 'LearningAgent']
  const validActions = ['pause', 'resume', 'stop']

  if (!validAgents.includes(agentName) || !validActions.includes(action)) {
    return NextResponse.json({ error: 'Invalid agentName or action' }, { status: 400 })
  }

  const supabase = createServerClient()
  const user = await getUserByClerkId(clerkId)
  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  // الحصول على حساب MT5 النشط للمستخدم
  const { data, error: accError } = await supabase
    .from('mt5_accounts')
    .select('*')
    .eq('user_id', user.id)
    .eq('is_active', true)
    .single()

  const account = data as any

  if (accError || !account) {
    return NextResponse.json({ error: 'Active MT5 account not found' }, { status: 404 })
  }

  // إدراج أمر جديد في قاعدة البيانات بوضع 'pending' ليقوم الـ Agent بسحبه في heartbeat التالي
  const { data: cmd, error: cmdError } = await (supabase.from('agent_commands') as any)
    .insert({
      account_id: account.id,
      agent_name: agentName,
      action:     action,
      status:     'pending',
    })
    .select()
    .single()

  if (cmdError) {
    return NextResponse.json({ error: cmdError.message }, { status: 500 })
  }

  return NextResponse.json({
    success: true,
    command: cmd,
  })
}
