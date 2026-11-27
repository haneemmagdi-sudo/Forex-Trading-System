/**
 * AgentsDashboard.tsx — لوحة تحكم الوكلاء الخمسة
 * بيانات حقيقية من MT5 / yfinance + أخبار Finnhub
 */
import { useState } from 'react';
import {
  useBackendStatus,
  useApiData,
  agentStatusColor,
  agentStatusBg,
  type AgentState,
  type Signal,
  type Trade,
  type NewsItem,
} from '../../utils/useBackend';

// ── بطاقة وكيل ──────────────────────────────────────────────────────────

function AgentCard({
  label, icon, state, onCommand,
}: {
  label:     string;
  icon:      string;
  state:     AgentState | null;
  onCommand: (action: string) => void;
}) {
  const status = state?.status ?? 'OFFLINE';
  const isRunning = status === 'RUNNING';

  return (
    <div className={`rounded-2xl p-5 border transition-all duration-300 ${agentStatusBg(status)}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <div className="text-white font-bold text-sm">{label}</div>
            <div className={`text-xs font-semibold ${agentStatusColor(status)}`}>{status}</div>
          </div>
        </div>
        <div className={`w-3 h-3 rounded-full ${
          isRunning  ? 'bg-emerald-400 animate-pulse' :
          status === 'ERROR' ? 'bg-red-400 animate-pulse' : 'bg-gray-500'
        }`} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 mb-4 text-center">
        <div className="bg-black/20 rounded-lg py-1.5">
          <div className="text-gray-500 text-xs">الدورات</div>
          <div className="text-white font-bold text-sm">{state?.iteration ?? 0}</div>
        </div>
        <div className="bg-black/20 rounded-lg py-1.5">
          <div className="text-gray-500 text-xs">الأخطاء</div>
          <div className={`font-bold text-sm ${(state?.errors ?? 0) > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {state?.errors ?? 0}
          </div>
        </div>
        <div className="bg-black/20 rounded-lg py-1.5">
          <div className="text-gray-500 text-xs">الفاصل</div>
          <div className="text-white font-bold text-sm">{state?.interval ?? '-'}s</div>
        </div>
      </div>

      {/* Dynamic extra stats */}
      {state && Object.entries(state).filter(([k]) =>
        !['name','status','iteration','errors','last_run','interval'].includes(k)
      ).slice(0, 2).map(([k, v]) => (
        <div key={k} className="flex justify-between text-xs mb-1">
          <span className="text-gray-500">{k.replace(/_/g,' ')}</span>
          <span className="text-purple-300 font-mono truncate max-w-[120px]">
            {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}
          </span>
        </div>
      ))}

      {state?.last_run && (
        <div className="text-gray-600 text-xs mt-2">
          آخر تشغيل: {new Date(state.last_run).toLocaleTimeString('ar-SA')}
        </div>
      )}

      <div className="flex gap-2 mt-4">
        {isRunning ? (
          <button
            onClick={() => onCommand('pause')}
            className="flex-1 py-1.5 rounded-lg bg-yellow-500/20 border border-yellow-500/30 text-yellow-400 text-xs font-semibold hover:bg-yellow-500/30 transition-all"
          >
            ⏸ إيقاف مؤقت
          </button>
        ) : status === 'PAUSED' ? (
          <button
            onClick={() => onCommand('resume')}
            className="flex-1 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/30 transition-all"
          >
            ▶ استئناف
          </button>
        ) : (
          <button
            onClick={() => onCommand('start')}
            className="flex-1 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/30 transition-all"
          >
            ▶ تشغيل
          </button>
        )}
      </div>
    </div>
  );
}

// ── بطاقة خبر ───────────────────────────────────────────────────────────

function NewsCard({ item }: { item: NewsItem }) {
  const impactColor = item.impact === 'HIGH' ? 'border-red-500/40 bg-red-500/10' :
                      item.impact === 'MEDIUM' ? 'border-yellow-500/40 bg-yellow-500/10' :
                      'border-gray-700/40 bg-gray-900/30';
  const sentimentIcon = item.sentiment === 'POSITIVE' ? '📈' :
                        item.sentiment === 'NEGATIVE' ? '📉' : '➡️';
  const impactBadge = item.impact === 'HIGH' ? 'bg-red-500/30 text-red-400' :
                      item.impact === 'MEDIUM' ? 'bg-yellow-500/30 text-yellow-400' :
                      'bg-gray-700/30 text-gray-400';

  return (
    <div className={`rounded-xl p-3 border text-xs ${impactColor} transition-all`}>
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span>{sentimentIcon}</span>
          <span className="text-white font-semibold truncate">{item.headline}</span>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-xs font-bold shrink-0 ${impactBadge}`}>
          {item.impact}
        </span>
      </div>
      <div className="flex justify-between items-center text-gray-500 mt-1">
        <span>{item.source}</span>
        <div className="flex gap-2">
          {item.related_symbols.slice(0,3).map(s => (
            <span key={s} className="text-blue-400 font-mono">{s}</span>
          ))}
        </div>
        <span>{new Date(item.datetime).toLocaleTimeString('ar-SA')}</span>
      </div>
    </div>
  );
}

// ── بادج مصدر البيانات ──────────────────────────────────────────────────

function DataSourceBadge({ source }: { source: string }) {
  const config = {
    MT5_LIVE:     { label: '🔴 LIVE MT5', color: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', pulse: true },
    YFINANCE_REAL:{ label: '📊 REAL DATA (yfinance)', color: 'bg-blue-500/20 border-blue-500/40 text-blue-400', pulse: true },
    SIMULATION:   { label: '⚠️ محاكاة', color: 'bg-orange-500/20 border-orange-500/40 text-orange-400', pulse: false },
    UNKNOWN:      { label: '❓ غير معروف', color: 'bg-gray-500/20 border-gray-500/40 text-gray-400', pulse: false },
  }[source] ?? { label: source, color: 'bg-gray-500/20 border-gray-500/40 text-gray-400', pulse: false };

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold ${config.color}`}>
      {config.pulse && <span className="w-2 h-2 rounded-full bg-current animate-pulse" />}
      {config.label}
    </div>
  );
}

// ── المكون الرئيسي ──────────────────────────────────────────────────────

export default function AgentsDashboard() {
  const { status, connected, messages, wsStatus, sendCommand, commandError } = useBackendStatus();
  const { data: signals }   = useApiData<Signal[]>('/api/signals?limit=10', 8000);
  const { data: trades }    = useApiData<Trade[]>('/api/trades?limit=10', 8000);
  const { data: account }   = useApiData<Record<string, any>>('/api/account', 5000);
  const { data: newsData }  = useApiData<{news: NewsItem[], sentiment: Record<string, string>}>('/api/news', 60000);
  const { data: dataSource }= useApiData<Record<string, any>>('/api/data-source', 15000);
  const { data: agentComm } = useApiData<Record<string, any>>('/api/agent-communications', 10000);
  const [activeLog, setActiveLog] = useState<'all' | 'signal' | 'trade' | 'news' | 'learning'>('all');
  const [activeTab, setActiveTab] = useState<'agents' | 'news' | 'comm'>('agents');

  const agents: [string, string, AgentState | null, string][] = [
    ['محلل السوق',    '🔍', status?.agents.analyst  ?? null, 'MarketAnalyst'],
    ['منفذ الصفقات', '⚡', status?.agents.executor ?? null, 'ExecutionAgent'],
    ['مراقب الصفقات','👁',  status?.agents.monitor  ?? null, 'MonitorAgent'],
    ['التعلم الآلي',  '🧠', status?.agents.learner  ?? null, 'LearningAgent'],
    ['محلل الأخبار', '📰', status?.agents.news     ?? null, 'NewsAgent'],
  ];

  const filteredMessages = messages.filter(m => {
    if (activeLog === 'all') return true;
    if (activeLog === 'signal') return m.topic === 'signal';
    if (activeLog === 'trade')  return ['trade_opened','trade_closed'].includes(m.topic);
    if (activeLog === 'news')   return ['news_alert','news_update'].includes(m.topic);
    if (activeLog === 'learning') return m.topic === 'learning_update';
    return true;
  });

  const logColor = (topic: string) => {
    const map: Record<string, string> = {
      'signal':          'text-yellow-400',
      'trade_opened':    'text-emerald-400',
      'trade_closed':    'text-blue-400',
      'dd_alert':        'text-red-400',
      'agent_log':       'text-purple-400',
      'learning_update': 'text-cyan-400',
      'news_alert':      'text-orange-400',
      'news_update':     'text-sky-400',
      'analysis':        'text-gray-400',
      'system_status':   'text-gray-600',
    };
    return map[topic] ?? 'text-gray-400';
  };

  const currentDataSource = dataSource?.source ?? status?.data_source ?? 'UNKNOWN';
  const newsItems: NewsItem[] = newsData?.news ?? [];
  const marketSentiment: Record<string, string> = newsData?.sentiment ?? {};

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl p-6 border border-cyan-400/30">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-3xl font-bold text-white mb-1">📊 لوحة تحكم الوكلاء</h2>
            <p className="text-cyan-200 text-sm">مراقبة حية للوكلاء الخمسة عبر WebSocket</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {/* مصدر البيانات */}
            <DataSourceBadge source={currentDataSource} />

            {/* حالة الاتصال */}
            <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold ${
              connected
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : wsStatus === 'connecting'
                  ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                  : 'bg-red-500/10 border-red-500/30 text-red-400'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                connected ? 'bg-emerald-400 animate-pulse' :
                wsStatus === 'connecting' ? 'bg-yellow-400 animate-pulse' :
                'bg-red-400'
              }`} />
              {connected ? '🟢 متصل بالـ Backend' :
               wsStatus === 'connecting' ? '🟡 جاري الاتصال...' :
               '🔴 غير متصل'}
            </div>
          </div>
        </div>
      </div>

      {commandError && (
        <div role="alert" className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-sm">
          ⚠️ لم يُنفَّذ الأمر: {commandError}
        </div>
      )}

      {/* Account Summary */}
      {account && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'الرصيد',     value: `$${(account.balance || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`, color: 'text-white' },
            { label: 'الأسهم',     value: `$${(account.equity  || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`, color: 'text-cyan-400' },
            { label: 'الهامش الحر',value: `$${(account.free_margin || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`, color: 'text-blue-400' },
            { label: 'وضع الحساب', value: account.company || 'Raw Trading Ltd', color: 'text-purple-400' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 border border-white/10 rounded-2xl p-4 text-center">
              <div className="text-gray-500 text-xs mb-1">{item.label}</div>
              <div className={`font-bold text-sm ${item.color}`}>{item.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* اتجاه السوق من الأخبار */}
      {Object.keys(marketSentiment).length > 0 && (
        <div className="bg-black/20 border border-white/10 rounded-2xl p-4">
          <div className="text-white font-bold text-sm mb-3 flex items-center gap-2">
            <span>📰</span> اتجاه السوق من الأخبار الحقيقية
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(marketSentiment).map(([sym, sent]) => (
              <div key={sym} className={`px-3 py-1 rounded-lg text-xs font-bold border ${
                sent === 'BULLISH' ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400' :
                sent === 'BEARISH' ? 'bg-red-500/20 border-red-500/30 text-red-400' :
                'bg-gray-700/30 border-gray-700 text-gray-400'
              }`}>
                {sym}: {sent === 'BULLISH' ? '📈' : sent === 'BEARISH' ? '📉' : '➡️'} {sent}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 pb-2">
        {([['agents','🤖 الوكلاء'],['news','📰 الأخبار'],['comm','🔗 التواصل']] as const).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === tab
                ? 'bg-purple-500/30 text-purple-300 border border-purple-500/30'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab: الوكلاء */}
      {activeTab === 'agents' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
            {agents.map(([label, icon, state, agentId]) => (
              <AgentCard
                key={agentId}
                label={label}
                icon={icon}
                state={state}
                onCommand={(action) => sendCommand(agentId, action)}
              />
            ))}
          </div>

          {/* Signals + Trades */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* آخر الإشارات */}
            <div className="bg-black/30 border border-white/10 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4 flex items-center gap-2">
                <span className="text-yellow-400">📡</span> آخر الإشارات
                {currentDataSource !== 'SIMULATION' && (
                  <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">
                    حقيقية
                  </span>
                )}
              </h3>
              <div className="space-y-2">
                {signals && signals.length > 0 ? signals.slice(0, 5).map((s, i) => (
                  <div key={i} className={`rounded-xl p-3 border text-xs ${
                    s.direction === 'BUY'  ? 'bg-emerald-500/10 border-emerald-500/20' :
                    s.direction === 'SELL' ? 'bg-red-500/10 border-red-500/20' :
                    'bg-gray-500/10 border-gray-500/20'
                  }`}>
                    <div className="flex justify-between items-center">
                      <span className="text-white font-bold">{s.symbol}</span>
                      <span className={`font-bold ${
                        s.direction === 'BUY' ? 'text-emerald-400' :
                        s.direction === 'SELL' ? 'text-red-400' : 'text-gray-400'
                      }`}>{s.direction}</span>
                    </div>
                    <div className="flex justify-between mt-1 text-gray-400">
                      <span>Confidence: {(s.confidence || 0).toFixed(1)}%</span>
                      <span>{s.fsm_regime}</span>
                      <span>{s.price ? s.price.toFixed(5) : ''}</span>
                      <span>{s.created_at ? new Date(s.created_at).toLocaleTimeString('ar-SA') : ''}</span>
                    </div>
                  </div>
                )) : (
                  <div className="text-center text-gray-600 py-6">
                    {connected ? 'في انتظار إشارات...' : 'في انتظار الاتصال...'}
                  </div>
                )}
              </div>
            </div>

            {/* آخر الصفقات */}
            <div className="bg-black/30 border border-white/10 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4 flex items-center gap-2">
                <span className="text-purple-400">💼</span> آخر الصفقات
                {currentDataSource !== 'SIMULATION' && (
                  <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">
                    حقيقية
                  </span>
                )}
              </h3>
              <div className="space-y-2">
                {trades && trades.length > 0 ? trades.slice(0, 5).map((t, i) => {
                  const profit = t.profit_usd ?? 0;
                  return (
                    <div key={i} className={`rounded-xl p-3 border text-xs ${
                      t.status === 'OPEN'
                        ? 'bg-blue-500/10 border-blue-500/20'
                        : profit > 0
                          ? 'bg-emerald-500/10 border-emerald-500/20'
                          : 'bg-red-500/10 border-red-500/20'
                    }`}>
                      <div className="flex justify-between items-center">
                        <div>
                          <span className="text-white font-bold">{t.symbol}</span>
                          <span className={`ml-2 font-semibold ${t.type === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {t.type}
                          </span>
                          <span className={`ml-2 text-xs ${
                            t.status === 'OPEN' ? 'text-blue-400' :
                            t.status === 'CLOSED' ? 'text-gray-400' : 'text-yellow-400'
                          }`}>{t.status}</span>
                        </div>
                        <span className={`font-bold ${profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between mt-1 text-gray-500">
                        <span>Lot: {t.lot_size}</span>
                        <span>Entry: {t.entry_price?.toFixed(5)}</span>
                      </div>
                    </div>
                  );
                }) : (
                  <div className="text-center text-gray-600 py-6">
                    {connected ? 'لا توجد صفقات حتى الآن' : 'في انتظار الاتصال...'}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Tab: الأخبار الحقيقية */}
      {activeTab === 'news' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-bold flex items-center gap-2">
              📰 أخبار السوق الحقيقية
              <span className="text-xs text-gray-500">
                ({newsItems.length} خبر | مصدر: Finnhub + Alpha Vantage)
              </span>
            </h3>
            <div className="flex gap-2 text-xs">
              <span className="px-2 py-1 rounded bg-red-500/20 text-red-400">HIGH: {newsItems.filter(n=>n.impact==='HIGH').length}</span>
              <span className="px-2 py-1 rounded bg-yellow-500/20 text-yellow-400">MEDIUM: {newsItems.filter(n=>n.impact==='MEDIUM').length}</span>
              <span className="px-2 py-1 rounded bg-gray-700/30 text-gray-400">LOW: {newsItems.filter(n=>n.impact==='LOW').length}</span>
            </div>
          </div>

          {newsItems.length === 0 ? (
            <div className="text-center py-16 text-gray-500">
              <div className="text-4xl mb-4">📰</div>
              <div>{connected ? '⏳ جاري جلب الأخبار... (يبدأ بعد 5 دقائق)' : '⚠️ يجب تشغيل الـ Backend'}</div>
              <div className="text-xs mt-2 text-gray-700">المصدر: Finnhub API (مفتاحه مُضبّط)</div>
            </div>
          ) : (
            <div className="space-y-2">
              {newsItems.map((item, i) => (
                <NewsCard key={i} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: تواصل الوكلاء */}
      {activeTab === 'comm' && (
        <div className="space-y-4">
          <h3 className="text-white font-bold">🔗 تواصل الوكلاء عبر Signal Bus</h3>

          {agentComm && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* رسائل لكل وكيل */}
              <div className="bg-black/30 border border-white/10 rounded-2xl p-5">
                <h4 className="text-white text-sm font-bold mb-3">📊 إحصاءات الرسائل</h4>
                <div className="space-y-2">
                  {Object.entries(agentComm.messages_per_agent ?? {}).map(([agent, count]) => (
                    <div key={agent} className="flex justify-between items-center">
                      <span className="text-gray-400 text-xs">{agent}</span>
                      <div className="flex items-center gap-2">
                        <div className="bg-purple-500/20 rounded-full h-1.5 w-24">
                          <div
                            className="bg-purple-400 rounded-full h-1.5"
                            style={{ width: `${Math.min(100, (count as number) / Math.max(...Object.values(agentComm.messages_per_agent as Record<string,number>)) * 100)}%` }}
                          />
                        </div>
                        <span className="text-purple-300 text-xs font-mono w-8 text-right">{count as number}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-white/10 text-gray-500 text-xs">
                  إجمالي الرسائل: {agentComm.total_messages ?? 0}
                </div>
              </div>

              {/* المواضيع النشطة */}
              <div className="bg-black/30 border border-white/10 rounded-2xl p-5">
                <h4 className="text-white text-sm font-bold mb-3">📡 القنوات النشطة</h4>
                <div className="space-y-1">
                  {(agentComm.active_topics ?? []).map((topic: string) => (
                    <div key={topic} className="flex items-center gap-2 text-xs">
                      <span className={`w-2 h-2 rounded-full ${logColor(topic).replace('text-','bg-')}`} />
                      <span className={logColor(topic)}>{topic}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* مخطط تدفق الرسائل */}
          <div className="bg-black/30 border border-white/10 rounded-2xl p-5">
            <h4 className="text-white text-sm font-bold mb-4">🔄 مخطط تواصل الوكلاء</h4>
            <div className="grid grid-cols-5 gap-2 text-center text-xs">
              {[
                { name: 'NewsAgent', icon: '📰', color: 'text-orange-400', sends: ['news_alert','news_update'] },
                { name: 'MarketAnalyst', icon: '🔍', color: 'text-cyan-400', sends: ['signal','analysis'] },
                { name: 'ExecutionAgent', icon: '⚡', color: 'text-yellow-400', sends: ['trade_opened'] },
                { name: 'MonitorAgent', icon: '👁', color: 'text-blue-400', sends: ['trade_closed','dd_alert'] },
                { name: 'LearningAgent', icon: '🧠', color: 'text-purple-400', sends: ['learning_update'] },
              ].map(agent => (
                <div key={agent.name} className="bg-black/40 rounded-xl p-3 border border-white/10">
                  <div className="text-2xl mb-1">{agent.icon}</div>
                  <div className={`font-bold ${agent.color} mb-2`}>{agent.name.replace('Agent','').replace('Analyst','')}</div>
                  {agent.sends.map(topic => (
                    <div key={topic} className={`text-xs ${logColor(topic)} bg-black/30 rounded px-1 py-0.5 mb-1 truncate`}>
                      → {topic}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* سجل الأحداث المباشر */}
      <div className="bg-black/40 border border-white/10 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="text-white font-bold text-sm flex items-center gap-2">
            <span className="text-cyan-400">📜</span> سجل الأحداث المباشر
            <span className="text-xs text-gray-500">({messages.length})</span>
          </h3>
          <div className="flex gap-2 flex-wrap">
            {(['all','signal','trade','news','learning'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveLog(tab)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  activeLog === tab
                    ? 'bg-purple-500/30 text-purple-300 border border-purple-500/30'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {tab === 'all' ? '🔵 الكل' :
                 tab === 'signal' ? '🟡 إشارات' :
                 tab === 'trade' ? '🟢 صفقات' :
                 tab === 'news' ? '🟠 أخبار' : '🔵 تعلم'}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-black/50 rounded-xl p-4 font-mono text-xs space-y-1.5 h-64 overflow-y-auto">
          {filteredMessages.length === 0 ? (
            <div className="text-gray-700 text-center pt-10">
              {connected ? 'في انتظار الأحداث...' : '⚠️ يجب تشغيل الـ Backend أولاً'}
            </div>
          ) : filteredMessages.map((m, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-gray-700 flex-shrink-0">
                {new Date(m.timestamp).toLocaleTimeString('ar-SA', { hour12: false })}
              </span>
              <span className="text-gray-600 flex-shrink-0">[{m.sender}]</span>
              <span className={`${logColor(m.topic)} flex-shrink-0`}>{m.topic}:</span>
              <span className="text-gray-400 truncate">
                {JSON.stringify(m.data).slice(0, 120)}
              </span>
            </div>
          ))}
        </div>

        {!connected && (
          <div className="mt-3 p-3 bg-orange-500/10 border border-orange-500/20 rounded-xl text-orange-400 text-xs">
            ⚠️ الـ Backend غير متصل. شغّل: <code className="bg-black/30 px-2 py-0.5 rounded font-mono">cd backend && python main.py</code>
          </div>
        )}
      </div>
    </div>
  );
}
