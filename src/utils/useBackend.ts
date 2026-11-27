/**
 * useBackend.ts — Hook مشترك لإدارة الاتصال بالـ Backend
 * يوفر: WebSocket، حالة الوكلاء، الإشارات، والصفقات
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { getApiToken } from './auth';

const isDev = window.location.port === '5173' || window.location.port === '5174';
export const BACKEND_URL = isDev ? 'http://localhost:8000' : window.location.origin;
export const WS_URL      = isDev ? 'ws://localhost:8000/ws' : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

// ── أنواع البيانات ──────────────────────────────────────────────────

export interface AgentState {
  name:       string;
  status:     'IDLE' | 'RUNNING' | 'PAUSED' | 'STOPPED' | 'ERROR';
  iteration:  number;
  errors:     number;
  last_run:   string | null;
  interval:   number;
  [key: string]: any;
}

export interface SystemStatus {
  mt5_connected:  boolean;
  mt5_simulation: boolean;
  data_source:    string;
  mt5_info:       Record<string, any>;
  agents: {
    analyst:  AgentState | null;
    executor: AgentState | null;
    monitor:  AgentState | null;
    learner:  AgentState | null;
    news:     AgentState | null;
  };
}

export interface BusMessage {
  topic:     string;
  sender:    string;
  data:      Record<string, any>;
  timestamp: string;
  priority:  number;
}

export interface Trade {
  id:          number;
  ticket:      number;
  symbol:      string;
  type:        'BUY' | 'SELL';
  status:      'OPEN' | 'CLOSED' | 'PARTIAL';
  lot_size:    number;
  entry_price: number;
  sl_price:    number;
  tp_price:    number;
  close_price: number | null;
  profit_usd:  number | null;
  confidence:  number | null;
  fsm_regime:  string | null;
  opened_at:   string;
  closed_at:   string | null;
}

export interface Signal {
  id:         number;
  symbol:     string;
  direction:  'BUY' | 'SELL' | 'NO_TRADE';
  fsm_regime: string;
  buy_score:  number;
  sell_score: number;
  confidence: number;
  price:      number;
  created_at: string;
}

export interface NewsItem {
  headline:        string;
  headline_ar?:    string;
  summary:         string;
  source:          string;
  datetime:        string;
  url:             string;
  impact:          'HIGH' | 'MEDIUM' | 'LOW';
  related_symbols: string[];
  sentiment:       'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
}

export interface Features {
  tradingagents_execution: boolean;
  lstm_page:               boolean;
  rl_page:                 boolean;
  paper_mode:              boolean;
  api_token_configured:    boolean;
}

// ── useBackendStatus ────────────────────────────────────────────────

export function useBackendStatus() {
  const [status, setStatus]           = useState<SystemStatus | null>(null);
  const [connected, setConnected]     = useState(false);
  const [messages, setMessages]       = useState<BusMessage[]>([]);
  const [wsStatus, setWsStatus]       = useState<'connecting' | 'open' | 'closed'>('connecting');
  const [commandError, setCommandError] = useState<string | null>(null);
  const wsRef                          = useRef<WebSocket | null>(null);
  const reconnectTimer                 = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setWsStatus('connecting');
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setWsStatus('open');
    };

    ws.onmessage = (ev) => {
      try {
        const msg: BusMessage = JSON.parse(ev.data);
        if (msg.topic === 'command_rejected') {
          setCommandError(msg.data.reason);
          return;
        }
        // تحديث الحالة من system_status
        if (msg.topic === 'system_status') {
          setStatus(msg.data as any);
        }
        // إضافة الرسالة إلى السجل (آخر 100 رسالة)
        setMessages(prev => [msg, ...prev].slice(0, 100));
      } catch { /* تجاهل الرسائل غير الصالحة */ }
    };

    ws.onclose = () => {
      setConnected(false);
      setWsStatus('closed');
      // إعادة الاتصال بعد 3 ثوانٍ
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      reconnectTimer.current && clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((agent: string, action: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setCommandError(null);
      wsRef.current.send(JSON.stringify({ agent, action, token: getApiToken() }));
    }
  }, []);

  return { status, connected, messages, wsStatus, sendCommand, commandError };
}

// ── useApiData ──────────────────────────────────────────────────────

export function useApiData<T>(endpoint: string, refreshMs = 10_000) {
  const [data, setData]     = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}${endpoint}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetch_();
    const timer = setInterval(fetch_, refreshMs);
    return () => clearInterval(timer);
  }, [fetch_, refreshMs]);

  return { data, loading, error, refresh: fetch_ };
}

// ── Helper: status badge color ──────────────────────────────────────

export function agentStatusColor(status: string): string {
  const map: Record<string, string> = {
    RUNNING: 'text-emerald-400',
    IDLE:    'text-yellow-400',
    PAUSED:  'text-blue-400',
    STOPPED: 'text-gray-400',
    ERROR:   'text-red-400',
    OFFLINE: 'text-gray-600',
  };
  return map[status] ?? 'text-gray-400';
}

export function agentStatusBg(status: string): string {
  const map: Record<string, string> = {
    RUNNING: 'bg-emerald-500/10 border-emerald-500/30',
    IDLE:    'bg-yellow-500/10 border-yellow-500/30',
    PAUSED:  'bg-blue-500/10 border-blue-500/30',
    STOPPED: 'bg-gray-500/10 border-gray-500/30',
    ERROR:   'bg-red-500/10 border-red-500/30',
    OFFLINE: 'bg-gray-900/50 border-gray-700/30',
  };
  return map[status] ?? 'bg-gray-500/10 border-gray-500/30';
}
