// ============================================================
// types.ts — أنواع TypeScript لقاعدة بيانات Supabase
// ============================================================

export type Database = {
  public: {
    Tables: {
      users: {
        Row: {
          id: string
          clerk_id: string
          email: string
          full_name: string | null
          avatar_url: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          clerk_id: string
          email: string
          full_name?: string | null
          avatar_url?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          full_name?: string | null
          avatar_url?: string | null
          updated_at?: string
        }
      }
      subscriptions: {
        Row: {
          id: string
          user_id: string
          plan: 'trial' | 'monthly' | 'yearly'
          status: 'active' | 'expired' | 'cancelled' | 'past_due'
          trial_start: string
          trial_end: string
          stripe_customer_id: string | null
          stripe_subscription_id: string | null
          paypal_subscription_id: string | null
          current_period_start: string | null
          current_period_end: string | null
          cancel_at_period_end: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          plan?: 'trial' | 'monthly' | 'yearly'
          status?: 'active' | 'expired' | 'cancelled' | 'past_due'
          trial_start?: string
          trial_end?: string
          stripe_customer_id?: string | null
          stripe_subscription_id?: string | null
          paypal_subscription_id?: string | null
        }
        Update: {
          plan?: 'trial' | 'monthly' | 'yearly'
          status?: 'active' | 'expired' | 'cancelled' | 'past_due'
          stripe_customer_id?: string | null
          stripe_subscription_id?: string | null
          current_period_start?: string | null
          current_period_end?: string | null
          cancel_at_period_end?: boolean
          updated_at?: string
        }
      }
      mt5_accounts: {
        Row: {
          id: string
          user_id: string
          login: number
          password_enc: string
          server: string
          broker_name: string | null
          account_name: string | null
          account_type: 'demo' | 'live'
          currency: string
          is_active: boolean
          is_connected: boolean
          last_seen_at: string | null
          agent_token: string
          agent_version: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          login: number
          password_enc: string
          server: string
          broker_name?: string | null
          account_name?: string | null
          account_type?: 'demo' | 'live'
          currency?: string
        }
        Update: {
          is_connected?: boolean
          last_seen_at?: string | null
          agent_version?: string | null
          is_active?: boolean
          updated_at?: string
        }
      }
      trades: {
        Row: {
          id: string
          user_id: string
          mt5_account_id: string | null
          ticket: number | null
          symbol: string
          type: 'BUY' | 'SELL'
          status: 'OPEN' | 'CLOSED' | 'PARTIAL'
          lot_size: number | null
          entry_price: number | null
          sl_price: number | null
          tp_price: number | null
          close_price: number | null
          profit_usd: number | null
          profit_pips: number | null
          fsm_regime: string | null
          confidence: number | null
          opened_at: string
          closed_at: string | null
          comment: string | null
          created_at: string
        }
        Insert: Omit<Database['public']['Tables']['trades']['Row'], 'id' | 'created_at'>
        Update: Partial<Database['public']['Tables']['trades']['Insert']>
      }
      signals: {
        Row: {
          id: string
          user_id: string
          mt5_account_id: string | null
          symbol: string
          direction: 'BUY' | 'SELL' | 'NO_TRADE'
          fsm_regime: string | null
          buy_score: number | null
          sell_score: number | null
          total_weight: number | null
          confidence: number | null
          executed: boolean
          trade_ticket: number | null
          ema_value: number | null
          rsi_value: number | null
          macd_value: number | null
          adx_value: number | null
          atr_value: number | null
          price: number | null
          created_at: string
        }
        Insert: Omit<Database['public']['Tables']['signals']['Row'], 'id' | 'created_at'>
        Update: Partial<Database['public']['Tables']['signals']['Insert']>
      }
      manual_payments: {
        Row: {
          id: string
          user_id: string
          method: 'vodafone_cash' | 'instapay'
          amount: number
          currency: string
          plan: 'monthly' | 'yearly'
          transfer_ref: string | null
          screenshot_url: string | null
          status: 'pending' | 'approved' | 'rejected'
          admin_note: string | null
          approved_by: string | null
          approved_at: string | null
          created_at: string
        }
        Insert: {
          user_id: string
          method: 'vodafone_cash' | 'instapay'
          amount: number
          currency?: string
          plan: 'monthly' | 'yearly'
          transfer_ref?: string | null
          screenshot_url?: string | null
        }
        Update: {
          status?: 'pending' | 'approved' | 'rejected'
          admin_note?: string | null
          approved_by?: string | null
          approved_at?: string | null
        }
      }
      agent_commands: {
        Row: {
          id: string
          account_id: string
          agent_name: string
          action: string
          status: string
          created_at: string
        }
        Insert: {
          id?: string
          account_id: string
          agent_name: string
          action: string
          status?: string
          created_at?: string
        }
        Update: {
          status?: string
        }
      }
      performance_snapshots: {
        Row: {
          id: string
          user_id: string
          mt5_account_id: string | null
          balance: number
          equity: number
          drawdown_pct: number
          open_trades: number
          daily_pnl: number | null
          win_rate: number | null
          profit_factor: number | null
          recorded_at: string
        }
        Insert: {
          id?: string
          user_id: string
          mt5_account_id?: string | null
          balance: number
          equity: number
          drawdown_pct: number
          open_trades: number
          daily_pnl?: number | null
          win_rate?: number | null
          profit_factor?: number | null
          recorded_at?: string
        }
        Update: {
          balance?: number
          equity?: number
          drawdown_pct?: number
        }
      }
      agent_logs: {
        Row: {
          id: string
          user_id: string
          agent_name: string
          level: string | null
          message: string | null
          symbol: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          agent_name: string
          level?: string | null
          message?: string | null
          symbol?: string | null
        }
        Update: {
          message?: string | null
        }
      }
      learning_logs: {
        Row: {
          id: string
          user_id: string
          iteration: number | null
          trades_analyzed: number | null
          win_rate: number | null
          best_regime: string | null
          worst_regime: string | null
          notes: string | null
          weight_adjustments: any | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          iteration?: number | null
          trades_analyzed?: number | null
          win_rate?: number | null
          best_regime?: string | null
          worst_regime?: string | null
          notes?: string | null
          weight_adjustments?: any | null
        }
        Update: {
          notes?: string | null
        }
      }
    }
    Views: {}
    Functions: {
      get_user_id_from_clerk: {
        Args: {}
        Returns: string
      }
    }
  }
}

// ── Helper Types ──────────────────────────────────────────────
export type User = Database['public']['Tables']['users']['Row']
export type Subscription = Database['public']['Tables']['subscriptions']['Row']
export type MT5Account = Database['public']['Tables']['mt5_accounts']['Row']
export type Trade = Database['public']['Tables']['trades']['Row']
export type Signal = Database['public']['Tables']['signals']['Row']
export type ManualPayment = Database['public']['Tables']['manual_payments']['Row']

// حالة الاشتراك مع معلومات التجربة
export type SubscriptionStatus = {
  isActive: boolean
  plan: string
  isTrial: boolean
  trialDaysLeft: number
  trialEnd: Date | null
  isExpired: boolean
}
