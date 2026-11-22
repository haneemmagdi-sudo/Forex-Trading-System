export interface AnalystReports {
  market: string;
  fundamentals: string;
  news: string;
  sentiment: string;
}

export interface DebateState {
  bull_history: string[];
  bear_history: string[];
  rounds?: number;
  consensus: string;
}

export interface RiskManagement {
  conservative: string;
  aggressive: string;
  neutral: string;
  volatility_status?: string;
  recommended_max_risk_pct?: number;
}

export interface DecisionState {
  action: 'BUY' | 'SELL' | 'HOLD';
  rating: string;
  conviction: number;
  entry_price?: number;
  suggested_sl?: number;
  suggested_tp?: number;
  recommended_lot?: number;
  rationale: string;
}

export interface TradingAgentsResult {
  run_id: string;
  ticker: string;
  yf_symbol: string;
  mt5_symbol: string;
  asset_type: 'forex' | 'stock' | 'crypto' | 'index' | string;
  trade_date: string;
  current_price?: number;
  anti_lookahead_active: boolean;
  requires_user_approval: boolean;
  executed_on_mt5: boolean;
  analyst_reports: AnalystReports;
  debate: DebateState;
  risk_management: RiskManagement;
  decision: DecisionState;
  timestamp: string;
}
