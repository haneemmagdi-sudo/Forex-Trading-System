import { NextRequest, NextResponse } from 'next/server'
import { createServerClient } from '@/lib/supabase/server'

// ============================================================
// POST /api/mt5/heartbeat
// يُستدعى من MT5 Agent كل 15 ثانية
// لا يحتاج Clerk Auth — يستخدم agent_token
// ============================================================
export async function POST(req: NextRequest) {
  let body: any
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { agent_token, data } = body

  if (!agent_token) {
    return NextResponse.json({ error: 'agent_token required' }, { status: 400 })
  }

  const supabase = createServerClient()

  // التحقق من الـ token
  const { data: accountData, error } = await supabase
    .from('mt5_accounts')
    .select('id, user_id')
    .eq('agent_token', agent_token)
    .eq('is_active', true)
    .single()

  const account = accountData as any

  if (error || !account) {
    return NextResponse.json({ error: 'Invalid agent_token' }, { status: 401 })
  }

  const userId      = account.user_id
  const accountId   = account.id

  // ── تحديث حالة الاتصال وآخر ظهور ────────────────────────
  await (supabase.from('mt5_accounts') as any)
    .update({
      is_connected:  true,
      last_seen_at:  new Date().toISOString(),
      agent_version: data?.version || null,
    })
    .eq('id', accountId)

  // ── حفظ لقطة الأداء ────────────────────────────────────
  if (data?.performance) {
    const perf = data.performance
    await supabase.from('performance_snapshots').insert({
      user_id:        userId,
      mt5_account_id: accountId,
      balance:        perf.balance        ?? 0,
      equity:         perf.equity         ?? 0,
      drawdown_pct:   perf.drawdown_pct   ?? 0,
      open_trades:    perf.open_trades    ?? 0,
    } as any)
  }

  // ── حفظ الصفقات المُرسَلة من الـ Agent ─────────────────
  if (data?.trades?.length) {
    for (const trade of data.trades) {
      try {
        await (supabase.from('trades') as any)
          .upsert({
            user_id:        userId,
            mt5_account_id: accountId,
            ticket:         trade.ticket,
            symbol:         trade.symbol,
            type:           trade.type,
            status:         trade.status || 'OPEN',
            lot_size:       trade.lot_size,
            entry_price:    trade.entry_price,
            sl_price:       trade.sl_price,
            tp_price:       trade.tp_price,
            close_price:    trade.close_price,
            profit_usd:     trade.profit_usd,
            profit_pips:    trade.profit_pips,
            fsm_regime:     trade.fsm_regime,
            confidence:     trade.confidence,
            opened_at:      trade.opened_at || new Date().toISOString(),
            closed_at:      trade.closed_at || null,
            comment:        trade.comment,
          }, { onConflict: 'ticket,user_id' })
      } catch { /* تجاهل أخطاء التكرار */ }
    }
  }

  // ── حفظ الإشارات ────────────────────────────────────────
  if (data?.signals?.length) {
    try {
      await (supabase.from('signals') as any).insert(
        data.signals.map((s: any) => ({
          user_id:        userId,
          mt5_account_id: accountId,
          symbol:         s.symbol,
          direction:      s.direction,
          fsm_regime:     s.fsm_regime,
          buy_score:      s.buy_score,
          sell_score:     s.sell_score,
          confidence:     s.confidence,
        }))
      )
    } catch { /* تجاهل أخطاء التكرار */ }
  }

  // ── حفظ سجلات الوكلاء ──────────────────────────────────
  if (data?.agent_logs?.length) {
    const logsToInsert = data.agent_logs.slice(0, 50).map((log: any) => ({
      user_id:    userId,
      agent_name: log.agent_name,
      level:      log.level,
      message:    log.message,
      symbol:     log.symbol || null,
    }))
    try {
      await (supabase.from('agent_logs') as any).insert(logsToInsert)
    } catch { /* تجاهل */ }
  }

  // ── استقبال الأوامر المعلّقة ────────────────────────────
  const { data: pendingCommandsData, error: cmdError } = await supabase
    .from('agent_commands')
    .select('id, agent_name, action')
    .eq('account_id', accountId)
    .eq('status', 'pending')

  const pendingCommands = pendingCommandsData as any[] | null
  let commandsToSend: any[] = []

  if (!cmdError && pendingCommands && pendingCommands.length > 0) {
    commandsToSend = pendingCommands.map(cmd => ({
      id:     cmd.id,
      agent:  cmd.agent_name,
      action: cmd.action,
    }))

    // تحديث حالة الأوامر إلى sent
    const commandIds = pendingCommands.map(cmd => cmd.id)
    await (supabase.from('agent_commands') as any)
      .update({ status: 'sent' })
      .in('id', commandIds)
  }

  return NextResponse.json({
    ok:        true,
    commands:  commandsToSend,
    timestamp: new Date().toISOString(),
  })
}
