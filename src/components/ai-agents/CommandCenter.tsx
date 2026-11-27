/**
 * CommandCenter.tsx — مركز القيادة (متصل بالـ Backend الحقيقي)
 * ─────────────────────────────────────────────────────────────
 * ✅ WebSocket حقيقي → ws://localhost:8000/ws
 * ✅ أخبار حقيقية   → GET /api/news
 * ✅ حالة الوكلاء   → GET /api/status
 * ✅ سجل الصفقات   → GET /api/trades
 * ✅ التعلم الآلي   → GET /api/ml/info + POST /api/ml/train-now
 * ✅ التحكم بالوكلاء → WS {action: "pause"/"resume", agent: "..."}
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { authHeaders, getApiToken } from '../../utils/auth';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────
interface NewsItem {
  headline: string;
  summary: string;
  source: string;
  datetime: string;
  url: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  related_symbols: string[];
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
}

interface AgentState {
  status: string;
  cycles?: number;
  errors?: number;
  last_cycle?: string;
  iterations?: number;
  model_trained?: boolean;
  model_accuracy?: number;
  current_win_rate?: number;
  news_fetched?: number;
}

interface SystemStatus {
  mt5_connected: boolean;
  mt5_simulation: boolean;
  data_source: string;
  mt5_info: Record<string, any>;
  agents: {
    analyst: AgentState;
    executor: AgentState;
    monitor: AgentState;
    learner: AgentState;
    news: AgentState;
  };
}

interface Trade {
  id: number;
  ticket?: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  status: 'OPEN' | 'CLOSED' | 'PARTIAL';
  lot_size: number;
  entry_price: number;
  sl_price: number;
  tp_price: number;
  close_price: number | null;
  profit_usd: number | null;
  confidence: number | null;
  opened_at: string;
  closed_at?: string | null;
}

interface MLInfo {
  status: string;
  model_trained: boolean;
  model_accuracy: number;
  iterations: number;
  trades_analyzed: number;
  best_regime: string | null;
  worst_regime: string | null;
  current_win_rate: number | null;
  weight_updates: number;
  last_analysis: string | null;
}

// ─────────────────────────────────────────────────────────────
const isDev = window.location.port === '5173' || window.location.port === '5174';
const API_BASE = isDev ? 'http://localhost:8000' : window.location.origin;
const WS_URL   = isDev ? 'ws://localhost:8000/ws' : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

const AGENT_META = {
  analyst:  { icon: '🔍', nameAr: 'المحلل',   color: 'blue',   apiName: 'MarketAnalyst' },
  executor: { icon: '⚡', nameAr: 'المنفذ',   color: 'emerald', apiName: 'ExecutionAgent' },
  monitor:  { icon: '👁️', nameAr: 'المراقب',  color: 'orange', apiName: 'MonitorAgent' },
  learner:  { icon: '🧠', nameAr: 'المتعلم',  color: 'purple', apiName: 'LearningAgent' },
  news:     { icon: '📰', nameAr: 'الأخبار',  color: 'pink',   apiName: 'NewsAgent' },
};

const SECTION_TABS = [
  { id: 'agents',   label: 'حالة الوكلاء',   icon: '🤖' },
  { id: 'news',     label: 'الأخبار الحقيقية', icon: '📰' },
  { id: 'trades',   label: 'سجل الصفقات',    icon: '📊' },
  { id: 'ml',       label: 'التعلم الآلي',    icon: '🧠' },
] as const;

type SectionId = typeof SECTION_TABS[number]['id'];

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────
const fmtTime  = (d: string) => d ? new Date(d).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }) : '';
const fmtDate  = (d: string) => d ? new Date(d).toLocaleDateString('ar-EG', { month: 'short', day: 'numeric' }) : '';
const colorMap: Record<string, string> = {
  blue:    'from-blue-500 to-cyan-500',
  emerald: 'from-emerald-500 to-green-500',
  orange:  'from-orange-500 to-amber-500',
  purple:  'from-purple-500 to-violet-500',
  pink:    'from-pink-500 to-rose-500',
};
const borderMap: Record<string, string> = {
  blue:    'border-blue-500/30',
  emerald: 'border-emerald-500/30',
  orange:  'border-orange-500/30',
  purple:  'border-purple-500/30',
  pink:    'border-pink-500/30',
};
const textMap: Record<string, string> = {
  blue:    'text-blue-300',
  emerald: 'text-emerald-300',
  orange:  'text-orange-300',
  purple:  'text-purple-300',
  pink:    'text-pink-300',
};
const bgMap: Record<string, string> = {
  blue:    'bg-blue-500/10',
  emerald: 'bg-emerald-500/10',
  orange:  'bg-orange-500/10',
  purple:  'bg-purple-500/10',
  pink:    'bg-pink-500/10',
};
// eslint-disable-next-line @typescript-eslint/no-unused-vars
void bgMap;

// ─────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────

function ConnectionBadge({ connected, label }: { connected: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-semibold ${
      connected
        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
        : 'bg-red-500/10 border-red-500/30 text-red-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
      {label}: {connected ? 'متصل' : 'منقطع'}
    </div>
  );
}

function ImpactBadge({ impact }: { impact: string }) {
  const map: Record<string, string> = {
    HIGH:   'bg-red-500/20 border-red-500/40 text-red-300',
    MEDIUM: 'bg-amber-500/20 border-amber-500/40 text-amber-300',
    LOW:    'bg-gray-500/20 border-gray-500/30 text-gray-400',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${map[impact] || map.LOW}`}>
      {impact}
    </span>
  );
}

function SentimentIcon({ sentiment }: { sentiment: string }) {
  if (sentiment === 'POSITIVE') return <span className="text-emerald-400 text-sm">↑ إيجابي</span>;
  if (sentiment === 'NEGATIVE') return <span className="text-red-400 text-sm">↓ سلبي</span>;
  return <span className="text-gray-500 text-sm">→ محايد</span>;
}

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────
export default function CommandCenter() {
  const [section, setSection]         = useState<SectionId>('agents');
  const [wsConnected, setWsConnected] = useState(false);
  const [apiReachable, setApiReachable] = useState(false);
  const [status, setStatus]           = useState<SystemStatus | null>(null);
  const [news, setNews]               = useState<NewsItem[]>([]);
  const [trades, setTrades]           = useState<Trade[]>([]);
  const [mlInfo, setMlInfo]           = useState<MLInfo | null>(null);
  const [newsFilter, setNewsFilter]   = useState<'ALL' | 'HIGH' | 'MEDIUM'>('ALL');
  const [lastUpdate, setLastUpdate]   = useState<Date | null>(null);
  const [mlTraining, setMlTraining]   = useState(false);
  const [agentAction, setAgentAction] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── fetch REST data ───────────────────────────────────────
  const fetchAll = useCallback(async () => {
    try {
      // Test if API is reachable
      const statusRes = await fetch(`${API_BASE}/api/status`, { signal: AbortSignal.timeout(3000) });
      if (!statusRes.ok) throw new Error('API unreachable');
      setApiReachable(true);

      const statusData = await statusRes.json();
      // Extract agents from nested structure
      const agentsData = statusData.agents || {};
      const mt5Data    = statusData.mt5    || {};
      setStatus({
        mt5_connected:  mt5Data.connected   ?? statusData.mt5_connected  ?? false,
        mt5_simulation: mt5Data.simulation  ?? statusData.mt5_simulation ?? true,
        data_source:    mt5Data.data_source ?? statusData.data_source    ?? 'UNKNOWN',
        mt5_info:       mt5Data.account     ?? statusData.mt5_info       ?? {},
        agents:         agentsData,
      });

      // News
      const newsRes = await fetch(`${API_BASE}/api/news`);
      if (newsRes.ok) {
        const nd = await newsRes.json();
        setNews(nd.news || []);
      }

      // Trades
      const tradesRes = await fetch(`${API_BASE}/api/trades?limit=50`);
      if (tradesRes.ok) setTrades(await tradesRes.json());

      // ML
      const mlRes = await fetch(`${API_BASE}/api/ml/info`);
      if (mlRes.ok) setMlInfo(await mlRes.json());

      setLastUpdate(new Date());
    } catch {
      setApiReachable(false);
    }
  }, []);

  const [actionError, setActionError] = useState<string | null>(null);

  // ── WebSocket connection ──────────────────────────────────
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.topic === 'command_rejected') {
          setActionError(msg.data?.reason ?? 'رُفض الأمر');
        }
        if (msg.topic === 'system_status' && msg.data) {
          const d = msg.data;
          setStatus({
            mt5_connected:  d.mt5_connected  ?? false,
            mt5_simulation: d.mt5_simulation ?? true,
            data_source:    d.data_source    ?? 'UNKNOWN',
            mt5_info:       d.mt5_info       ?? {},
            agents:         d.agents         ?? {},
          });
          setLastUpdate(new Date());
        }
        if (msg.topic === 'news_update' && msg.data?.news) {
          setNews(msg.data.news);
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      setWsConnected(false);
      // Reconnect after 5s
      setTimeout(connectWS, 5000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    fetchAll();
    connectWS();
    const interval = setInterval(fetchAll, 15000); // refresh every 15s
    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [fetchAll, connectWS]);

  // ── Agent control ─────────────────────────────────────────
  const sendAgentCommand = (agentKey: string, action: 'pause' | 'resume') => {
    const meta = AGENT_META[agentKey as keyof typeof AGENT_META];
    if (!meta || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setAgentAction(`${action}_${agentKey}`);
    setActionError(null);
    wsRef.current.send(JSON.stringify({ action, agent: meta.apiName, token: getApiToken() }));
    setTimeout(() => setAgentAction(null), 2000);
  };

  // ── ML train now ──────────────────────────────────────────
  const triggerMLTrain = async () => {
    setMlTraining(true);
    setActionError(null);
    try {
      const res = await fetch(`${API_BASE}/api/ml/train-now`, { method: 'POST', headers: authHeaders() });
      if (res.ok) {
        await fetchAll();
      } else {
        const body = await res.json().catch(() => null);
        setActionError(body?.detail ?? `HTTP ${res.status}`);
      }
    } catch {
      setActionError('تعذر الاتصال بالخادم');
    }
    setMlTraining(false);
  };

  // ── filtered news ─────────────────────────────────────────
  const filteredNews = newsFilter === 'ALL' ? news
    : news.filter(n => n.impact === newsFilter);

  // ─────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────
  const agents = status?.agents ?? {};

  return (
    <div className="space-y-5 animate-fadeIn" dir="rtl">

      {/* ══════════════════ HEADER ══════════════════ */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span className="text-3xl">🎯</span>
            مركز القيادة الحقيقي
            <span className="text-xs font-normal bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 px-2 py-0.5 rounded-lg">
              LIVE
            </span>
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            بيانات حقيقية · أخبار مباشرة · تعلم آلي فعّال
            {lastUpdate && (
              <span className="text-gray-600 mr-2">
                · آخر تحديث: {lastUpdate.toLocaleTimeString('ar-EG')}
              </span>
            )}
          </p>
        </div>

        {/* Connection badges */}
        <div className="flex flex-wrap gap-2">
          <ConnectionBadge connected={apiReachable} label="Backend API" />
          <ConnectionBadge connected={wsConnected}  label="WebSocket" />
          {status && (
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-semibold ${
              status.mt5_connected && !status.mt5_simulation
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : status.mt5_connected
                ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            }`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              {status.data_source === 'MT5_LIVE' ? '🏦 MT5 Live'
               : status.data_source === 'YFINANCE_REAL' ? '📡 yfinance Real'
               : '⚠️ No Data'}
            </div>
          )}
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-xs text-gray-300 transition-all"
          >
            🔄 تحديث
          </button>
        </div>
      </div>

      {/* ══════════════════ NOT CONNECTED WARNING ══════════════════ */}
      {!apiReachable && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <p className="text-amber-300 font-bold text-sm">الخادم غير متصل</p>
            <p className="text-amber-400/70 text-xs mt-1">
              شغّل الـ backend أولاً:
              <code className="bg-black/30 rounded px-2 py-0.5 mx-1 font-mono">
                cd backend && python main.py
              </code>
              أو افتح <code className="bg-black/30 rounded px-1 font-mono">start_backend.bat</code>
            </p>
          </div>
        </div>
      )}

      {actionError && (
        <div role="alert" className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-sm">
          ⚠️ لم تُنفَّذ العملية: {actionError}
        </div>
      )}

      {/* ══════════════════ ACCOUNT OVERVIEW ══════════════════ */}
      {status?.mt5_info && Object.keys(status.mt5_info).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'الرصيد',      value: `$${(status.mt5_info.balance ?? 0).toLocaleString()}`, icon: '💰', c: 'emerald' },
            { label: 'الإكويتي',   value: `$${(status.mt5_info.equity  ?? 0).toLocaleString()}`, icon: '📊', c: 'blue' },
            { label: 'الرافعة',     value: `1:${status.mt5_info.leverage ?? '?'}`,                icon: '⚡', c: 'purple' },
            { label: 'العملة',      value: status.mt5_info.currency ?? 'USD',                     icon: '🌐', c: 'orange' },
          ].map((card, i) => (
            <div key={i} className={`bg-black/40 border ${borderMap[card.c]} rounded-xl p-4 backdrop-blur-sm`}>
              <div className={`text-xs ${textMap[card.c]} mb-1`}>{card.icon} {card.label}</div>
              <div className="text-white font-black text-xl">{card.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ══════════════════ SECTION TABS ══════════════════ */}
      <div className="flex gap-2 flex-wrap">
        {SECTION_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setSection(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              section === tab.id
                ? 'bg-purple-500/20 border border-purple-500/40 text-purple-300 shadow-lg shadow-purple-500/10'
                : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10'
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
            {tab.id === 'news' && news.length > 0 && (
              <span className="text-xs bg-red-500/30 text-red-300 px-1.5 py-0.5 rounded-full">
                {news.filter(n => n.impact === 'HIGH').length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ══════════════════ AGENTS SECTION ══════════════════ */}
      {section === 'agents' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Object.entries(AGENT_META).map(([key, meta]) => {
              const state = agents[key as keyof typeof agents] as AgentState | undefined;
              const isRunning = state?.status === 'RUNNING';
              const isPaused  = state?.status === 'PAUSED';
              const actionKey = agentAction?.split('_').slice(1).join('_');

              return (
                <div
                  key={key}
                  className={`bg-black/40 border ${borderMap[meta.color]} rounded-2xl p-5 backdrop-blur-sm transition-all hover:shadow-lg`}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${colorMap[meta.color]} flex items-center justify-center text-xl shadow-lg`}>
                        {meta.icon}
                      </div>
                      <div>
                        <div className={`font-bold text-sm ${textMap[meta.color]}`}>{meta.nameAr}</div>
                        <div className="text-gray-600 text-xs">{meta.apiName}</div>
                      </div>
                    </div>

                    {/* Status badge */}
                    <div className={`text-xs px-2.5 py-1 rounded-lg border font-semibold ${
                      isRunning ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : isPaused ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : state?.status === 'OFFLINE' ? 'bg-red-500/10 border-red-500/30 text-red-400'
                      : 'bg-gray-500/10 border-gray-500/20 text-gray-500'
                    }`}>
                      {isRunning ? '● يعمل' : isPaused ? '⏸ مؤقت' : state?.status ?? '—'}
                    </div>
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
                    {[
                      { label: 'دورات',   value: state?.cycles ?? '—' },
                      { label: 'أخطاء',   value: state?.errors ?? '—' },
                      ...(key === 'learner' ? [
                        { label: 'دقة ML', value: state?.model_accuracy ? `${state.model_accuracy.toFixed(0)}%` : '—' },
                        { label: 'Win Rate', value: state?.current_win_rate ? `${state.current_win_rate.toFixed(0)}%` : '—' },
                      ] : []),
                      ...(key === 'news' ? [
                        { label: 'أخبار', value: state?.news_fetched ?? '—' },
                      ] : []),
                    ].map((stat, i) => (
                      <div key={i} className="bg-white/5 rounded-lg p-2">
                        <div className="text-gray-500">{stat.label}</div>
                        <div className="text-white font-bold mt-0.5">{stat.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Last cycle */}
                  {state?.last_cycle && (
                    <div className="text-gray-600 text-xs mb-3">
                      آخر دورة: {fmtTime(state.last_cycle)}
                    </div>
                  )}

                  {/* Control buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => sendAgentCommand(key, 'pause')}
                      disabled={!wsConnected || isPaused || !isRunning || actionKey === key}
                      className="flex-1 py-1.5 text-xs rounded-lg border border-amber-500/30 text-amber-400 hover:bg-amber-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                    >
                      ⏸ إيقاف مؤقت
                    </button>
                    <button
                      onClick={() => sendAgentCommand(key, 'resume')}
                      disabled={!wsConnected || isRunning || actionKey === key}
                      className="flex-1 py-1.5 text-xs rounded-lg border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                    >
                      ▶ استئناف
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* MT5 account details */}
          {status?.mt5_info && Object.keys(status.mt5_info).length > 0 && (
            <div className="bg-black/40 border border-white/10 rounded-xl p-5 backdrop-blur-sm">
              <h3 className="text-white font-bold text-sm mb-3 flex items-center gap-2">
                <span>🔌</span> تفاصيل حساب MT5
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                {Object.entries(status.mt5_info).map(([k, v]) => (
                  <div key={k} className="bg-white/5 rounded-lg p-2">
                    <div className="text-gray-500 capitalize">{k.replace(/_/g, ' ')}</div>
                    <div className="text-white font-semibold mt-0.5 truncate">{String(v)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ NEWS SECTION ══════════════════ */}
      {section === 'news' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="text-white font-bold text-lg flex items-center gap-2">
              <span>📰</span>
              الأخبار الحقيقية
              <span className="text-xs font-normal text-gray-500">
                ({news.length} خبر — محدّث كل 5 دقائق)
              </span>
            </h2>
            <div className="flex gap-2">
              {(['ALL', 'HIGH', 'MEDIUM'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setNewsFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    newsFilter === f
                      ? f === 'HIGH'   ? 'bg-red-500/20 border border-red-500/40 text-red-300'
                        : f === 'MEDIUM' ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300'
                        : 'bg-purple-500/20 border border-purple-500/40 text-purple-300'
                      : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white'
                  }`}
                >
                  {f === 'ALL' ? 'الكل' : f}
                  <span className="mr-1">
                    ({f === 'ALL' ? news.length : news.filter(n => n.impact === f).length})
                  </span>
                </button>
              ))}
            </div>
          </div>

          {filteredNews.length === 0 ? (
            <div className="text-center py-16 text-gray-600">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-sm">
                {apiReachable
                  ? 'جاري جلب الأخبار... (قد يستغرق دقيقة)'
                  : 'الخادم غير متصل — شغّل backend أولاً'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNews.map((item, i) => (
                <div
                  key={i}
                  className={`bg-black/40 border rounded-xl p-4 backdrop-blur-sm transition-all hover:shadow-lg group ${
                    item.impact === 'HIGH'   ? 'border-red-500/30 hover:border-red-500/50'
                    : item.impact === 'MEDIUM' ? 'border-amber-500/30 hover:border-amber-500/50'
                    : 'border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <ImpactBadge impact={item.impact} />
                        <SentimentIcon sentiment={item.sentiment} />
                        <span className="text-gray-600 text-xs">{item.source}</span>
                        <span className="text-gray-700 text-xs">{fmtDate(item.datetime)} {fmtTime(item.datetime)}</span>
                      </div>
                      <h3 className={`font-semibold text-sm leading-relaxed mb-1 group-hover:text-white transition-colors ${
                        item.impact === 'HIGH' ? 'text-red-200' : 'text-gray-200'
                      }`}>
                        {item.headline}
                      </h3>
                      {item.summary && (
                        <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{item.summary}</p>
                      )}
                      {item.related_symbols.length > 0 && (
                        <div className="flex gap-1.5 mt-2 flex-wrap">
                          {item.related_symbols.map(sym => (
                            <span key={sym} className="text-xs bg-blue-500/15 text-blue-400 px-2 py-0.5 rounded-full">
                              {sym}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 text-gray-600 hover:text-purple-400 transition-colors text-lg"
                      >
                        🔗
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ TRADES SECTION ══════════════════ */}
      {section === 'trades' && (
        <div className="space-y-4">
          <h2 className="text-white font-bold text-lg flex items-center gap-2">
            <span>📊</span> سجل الصفقات الحقيقية
            <span className="text-xs font-normal text-gray-500">({trades.length} صفقة)</span>
          </h2>

          {trades.length === 0 ? (
            <div className="text-center py-16 text-gray-600">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-sm">{apiReachable ? 'لا توجد صفقات بعد' : 'الخادم غير متصل'}</p>
            </div>
          ) : (
            <div className="bg-black/40 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-white/5 text-gray-400 text-xs">
                      {['الزوج', 'الاتجاه', 'اللوت', 'سعر الدخول', 'SL', 'TP', 'P&L', 'الثقة', 'الحالة', 'التاريخ'].map(h => (
                        <th key={h} className="text-right px-3 py-3 font-semibold whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade, i) => (
                      <tr key={trade.id ?? i} className="border-t border-white/5 hover:bg-white/5 transition-colors">
                        <td className="px-3 py-3 text-white font-bold">{trade.symbol}</td>
                        <td className={`px-3 py-3 font-semibold ${trade.type === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {trade.type === 'BUY' ? '↑ شراء' : '↓ بيع'}
                        </td>
                        <td className="px-3 py-3 text-gray-300">{trade.lot_size}</td>
                        <td className="px-3 py-3 text-gray-300 font-mono text-xs">{trade.entry_price}</td>
                        <td className="px-3 py-3 text-red-400 font-mono text-xs">{trade.sl_price}</td>
                        <td className="px-3 py-3 text-emerald-400 font-mono text-xs">{trade.tp_price}</td>
                        <td className={`px-3 py-3 font-bold ${(trade.profit_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {(trade.profit_usd ?? 0) >= 0 ? '+' : ''}{(trade.profit_usd ?? 0).toFixed(2)}$
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1">
                            <div className="h-1.5 w-16 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-purple-600 to-purple-400 rounded-full"
                                style={{ width: `${trade.confidence ?? 0}%` }}
                              />
                            </div>
                            <span className="text-gray-400 text-xs">{trade.confidence ?? 0}%</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            trade.status === 'OPEN'   ? 'bg-emerald-500/20 text-emerald-400'
                            : trade.status === 'CLOSED' ? 'bg-gray-500/20 text-gray-400'
                            : 'bg-blue-500/20 text-blue-400'
                          }`}>
                            {trade.status}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-gray-500 text-xs whitespace-nowrap">
                          {fmtDate(trade.opened_at)} {fmtTime(trade.opened_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════ ML SECTION ══════════════════ */}
      {section === 'ml' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="text-white font-bold text-lg flex items-center gap-2">
              <span>🧠</span> التعلم الآلي الحقيقي
            </h2>
            <button
              onClick={triggerMLTrain}
              disabled={mlTraining || !apiReachable}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                mlTraining || !apiReachable
                  ? 'bg-white/10 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white shadow-lg hover:shadow-purple-500/30 hover:scale-105'
              }`}
            >
              {mlTraining ? (
                <>
                  <span className="animate-spin">⏳</span> جاري التدريب...
                </>
              ) : (
                <><span>🚀</span> تدريب الآن</>
              )}
            </button>
          </div>

          {/* ML Stats cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              {
                label: 'دقة النموذج',
                value: mlInfo?.model_accuracy ? `${mlInfo.model_accuracy.toFixed(1)}%` : '—',
                icon: '🎯',
                color: 'purple',
                sub: mlInfo?.model_trained ? '✅ مدرَّب' : '⚠️ بحاجة لبيانات',
              },
              {
                label: 'صفقات مُحللة',
                value: mlInfo?.trades_analyzed ?? '—',
                icon: '📊',
                color: 'blue',
                sub: `${mlInfo?.iterations ?? 0} دورة تعلم`,
              },
              {
                label: 'Win Rate',
                value: mlInfo?.current_win_rate ? `${mlInfo.current_win_rate.toFixed(1)}%` : '—',
                icon: '🏆',
                color: 'emerald',
                sub: `أفضل: ${mlInfo?.best_regime ?? '—'}`,
              },
              {
                label: 'تحديث الأوزان',
                value: mlInfo?.weight_updates ?? '—',
                icon: '⚖️',
                color: 'orange',
                sub: mlInfo?.last_analysis ? `آخر: ${fmtTime(mlInfo.last_analysis)}` : 'لم يبدأ',
              },
            ].map((card, i) => (
              <div key={i} className={`bg-black/40 border ${borderMap[card.color]} rounded-2xl p-5 backdrop-blur-sm`}>
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorMap[card.color]} flex items-center justify-center text-xl mb-3`}>
                  {card.icon}
                </div>
                <div className={`text-2xl font-black ${textMap[card.color]} mb-1`}>{card.value}</div>
                <div className="text-gray-400 text-xs font-medium">{card.label}</div>
                <div className="text-gray-600 text-xs mt-1">{card.sub}</div>
              </div>
            ))}
          </div>

          {/* Model status panel */}
          <div className="bg-black/40 border border-purple-500/20 rounded-2xl p-6 backdrop-blur-sm">
            <h3 className="text-white font-bold mb-4 flex items-center gap-2">
              <span>🤖</span> حالة نموذج GradientBoosting
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">حالة النموذج</span>
                <span className={`font-bold text-sm ${
                  mlInfo?.model_trained ? 'text-emerald-400' : 'text-amber-400'
                }`}>
                  {mlInfo?.model_trained ? '✅ نموذج مدرَّب وجاهز' : '⏳ يحتاج بيانات للتدريب'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">الحد الأدنى للتدريب</span>
                <span className="text-white font-bold text-sm">5 صفقات مغلقة</span>
              </div>

              {mlInfo?.model_accuracy != null && mlInfo.model_accuracy > 0 && (
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-400">دقة التحقق المتقاطع (CV)</span>
                    <span className="text-purple-300 font-bold">{mlInfo.model_accuracy.toFixed(1)}%</span>
                  </div>
                  <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-700 to-purple-400 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(mlInfo.model_accuracy, 100)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Regimes */}
              {mlInfo?.best_regime && (
                <div className="grid grid-cols-2 gap-3 mt-2">
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-center">
                    <div className="text-emerald-400 text-xs mb-1">🏆 أفضل Regime</div>
                    <div className="text-white font-bold text-sm">{mlInfo.best_regime}</div>
                  </div>
                  <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-center">
                    <div className="text-red-400 text-xs mb-1">⚠️ أسوأ Regime</div>
                    <div className="text-white font-bold text-sm">{mlInfo.worst_regime ?? '—'}</div>
                  </div>
                </div>
              )}

              {/* How it works */}
              <div className="bg-white/5 rounded-xl p-4 text-xs text-gray-400 leading-relaxed mt-2">
                <p className="font-semibold text-gray-300 mb-2">🔬 كيف يعمل التعلم الآلي الحقيقي:</p>
                <ol className="space-y-1 list-decimal list-inside">
                  <li>يجمع سجل الصفقات الحقيقية المغلقة من قاعدة البيانات</li>
                  <li>يستخرج مؤشرات كل صفقة (RSI, EMA, MACD, ADX, ATR...)</li>
                  <li>يدرب نموذج <strong className="text-purple-300">GradientBoosting</strong> + <strong className="text-blue-300">RandomForest</strong></li>
                  <li>يقيّم الدقة بـ Cross-Validation (k-folds)</li>
                  <li>يحفظ النموذج على القرص للاستمرارية</li>
                  <li>يُعدّل أوزان الـ Voting Engine بناءً على نتائج التعلم</li>
                  <li>يُكرر كل 60 دقيقة تلقائياً</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
