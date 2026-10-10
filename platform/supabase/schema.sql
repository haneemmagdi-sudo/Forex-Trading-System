-- ============================================================
-- Supabase Schema — Quantum Forex AI Platform
-- نفّذ هذا الملف في Supabase → SQL Editor
-- ============================================================

-- ── تفعيل الـ Extensions ──────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. جدول المستخدمين (يُملأ من Clerk Webhook)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_id    TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  full_name   TEXT,
  avatar_url  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. جدول الاشتراكات والتجربة المجانية
-- ============================================================
CREATE TABLE IF NOT EXISTS public.subscriptions (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  plan                    TEXT NOT NULL DEFAULT 'trial',      -- trial | monthly | yearly
  status                  TEXT NOT NULL DEFAULT 'active',    -- active | expired | cancelled | past_due
  trial_start             TIMESTAMPTZ DEFAULT NOW(),
  trial_end               TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
  stripe_customer_id      TEXT,
  stripe_subscription_id  TEXT,
  paypal_subscription_id  TEXT,
  current_period_start    TIMESTAMPTZ,
  current_period_end      TIMESTAMPTZ,
  cancel_at_period_end    BOOLEAN DEFAULT FALSE,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. جدول حسابات MT5 لكل مستخدم
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mt5_accounts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  login           BIGINT NOT NULL,
  password_enc    TEXT NOT NULL,          -- مشفّر بـ AES
  server          TEXT NOT NULL,
  broker_name     TEXT,
  account_name    TEXT,
  account_type    TEXT DEFAULT 'demo',   -- demo | live
  currency        TEXT DEFAULT 'USD',
  is_active       BOOLEAN DEFAULT TRUE,
  is_connected    BOOLEAN DEFAULT FALSE,
  last_seen_at    TIMESTAMPTZ,
  agent_token     TEXT UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
  agent_version   TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. جدول الصفقات
-- ============================================================
CREATE TABLE IF NOT EXISTS public.trades (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  mt5_account_id  UUID REFERENCES public.mt5_accounts(id),
  ticket          BIGINT,
  symbol          TEXT NOT NULL,
  type            TEXT NOT NULL,          -- BUY | SELL
  status          TEXT DEFAULT 'OPEN',    -- OPEN | CLOSED | PARTIAL
  lot_size        FLOAT,
  entry_price     FLOAT,
  sl_price        FLOAT,
  tp_price        FLOAT,
  close_price     FLOAT,
  profit_usd      FLOAT,
  profit_pips     FLOAT,
  fsm_regime      TEXT,
  buy_score       FLOAT,
  sell_score      FLOAT,
  confidence      FLOAT,
  partial_l1_done BOOLEAN DEFAULT FALSE,
  partial_l2_done BOOLEAN DEFAULT FALSE,
  partial_l3_done BOOLEAN DEFAULT FALSE,
  breakeven_done  BOOLEAN DEFAULT FALSE,
  trailing_active BOOLEAN DEFAULT FALSE,
  opened_at       TIMESTAMPTZ DEFAULT NOW(),
  closed_at       TIMESTAMPTZ,
  comment         TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. جدول الإشارات
-- ============================================================
CREATE TABLE IF NOT EXISTS public.signals (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  mt5_account_id UUID REFERENCES public.mt5_accounts(id),
  symbol        TEXT NOT NULL,
  direction     TEXT NOT NULL,            -- BUY | SELL | NO_TRADE
  fsm_regime    TEXT,
  buy_score     FLOAT,
  sell_score    FLOAT,
  total_weight  FLOAT,
  confidence    FLOAT,
  executed      BOOLEAN DEFAULT FALSE,
  trade_ticket  BIGINT,
  ema_value     FLOAT,
  rsi_value     FLOAT,
  macd_value    FLOAT,
  adx_value     FLOAT,
  atr_value     FLOAT,
  price         FLOAT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. جدول لقطات الأداء
-- ============================================================
CREATE TABLE IF NOT EXISTS public.performance_snapshots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  mt5_account_id  UUID REFERENCES public.mt5_accounts(id),
  balance         FLOAT,
  equity          FLOAT,
  drawdown_pct    FLOAT,
  open_trades     INTEGER,
  daily_pnl       FLOAT,
  win_rate        FLOAT,
  profit_factor   FLOAT,
  recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. جدول سجل التعلم
-- ============================================================
CREATE TABLE IF NOT EXISTS public.learning_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  iteration        INTEGER,
  trades_analyzed  INTEGER,
  win_rate         FLOAT,
  best_regime      TEXT,
  worst_regime     TEXT,
  notes            TEXT,
  weight_adjustments JSONB,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8. جدول سجل الوكلاء
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  agent_name  TEXT NOT NULL,
  level       TEXT,                        -- INFO | WARNING | ERROR
  message     TEXT,
  symbol      TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 9. جدول المدفوعات اليدوية (Vodafone Cash / InstaPay)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.manual_payments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  method          TEXT NOT NULL,           -- vodafone_cash | instapay
  amount          FLOAT NOT NULL,
  currency        TEXT DEFAULT 'EGP',
  plan            TEXT NOT NULL,           -- monthly | yearly
  transfer_ref    TEXT,                    -- رقم العملية من المستخدم
  screenshot_url  TEXT,                    -- صورة إثبات الدفع
  status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
  admin_note      TEXT,
  approved_by     TEXT,
  approved_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 10. جدول الأوامر الخاصة بالـ Agent (التحكم بالوكلاء)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_commands (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id  UUID NOT NULL REFERENCES public.mt5_accounts(id) ON DELETE CASCADE,
  agent_name  TEXT NOT NULL,               -- MarketAnalyst | ExecutionAgent | MonitorAgent | LearningAgent
  action      TEXT NOT NULL,               -- pause | resume | stop
  status      TEXT DEFAULT 'pending',      -- pending | sent | completed
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 🔒 Row Level Security (RLS)
-- ============================================================

-- تفعيل RLS على جميع الجداول
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.performance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.manual_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_commands ENABLE ROW LEVEL SECURITY;

-- دالة مساعدة: الحصول على user_id من clerk_id (مخزّن في JWT)
CREATE OR REPLACE FUNCTION public.get_user_id_from_clerk()
RETURNS UUID AS $$
  SELECT id FROM public.users
  WHERE clerk_id = auth.jwt() ->> 'sub'
  LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

-- سياسات الوصول
CREATE POLICY "users_select_own" ON public.users
  FOR SELECT USING (clerk_id = auth.jwt() ->> 'sub');

CREATE POLICY "subscriptions_select_own" ON public.subscriptions
  FOR SELECT USING (user_id = get_user_id_from_clerk());

CREATE POLICY "mt5_accounts_all_own" ON public.mt5_accounts
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "trades_all_own" ON public.trades
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "signals_all_own" ON public.signals
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "performance_all_own" ON public.performance_snapshots
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "learning_logs_all_own" ON public.learning_logs
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "agent_logs_all_own" ON public.agent_logs
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "manual_payments_all_own" ON public.manual_payments
  FOR ALL USING (user_id = get_user_id_from_clerk());

CREATE POLICY "agent_commands_all_own" ON public.agent_commands
  FOR ALL USING (account_id IN (SELECT id FROM public.mt5_accounts WHERE user_id = get_user_id_from_clerk()));

-- ============================================================================
-- 📊 Indexes للأداء
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON public.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_status ON public.trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON public.trades(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_user_id ON public.signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON public.signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_user_id ON public.agent_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_agent_token ON public.mt5_accounts(agent_token);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON public.subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON public.subscriptions(status);

-- ============================================================
-- 🔔 Realtime (تفعيل للجداول المهمة)
-- ============================================================
-- نفّذ هذا في: Supabase → Database → Replication
-- ALTER PUBLICATION supabase_realtime ADD TABLE public.trades;
-- ALTER PUBLICATION supabase_realtime ADD TABLE public.signals;
-- ALTER PUBLICATION supabase_realtime ADD TABLE public.agent_logs;
-- ALTER PUBLICATION supabase_realtime ADD TABLE public.mt5_accounts;

-- ============================================================
-- دالة تحديث updated_at تلقائياً
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_subscriptions_updated_at
  BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_mt5_accounts_updated_at
  BEFORE UPDATE ON public.mt5_accounts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
