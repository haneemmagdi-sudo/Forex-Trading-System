import { useState, useEffect, useRef } from 'react';
import { useApiData, useBackendStatus } from '../../utils/useBackend';

// ──────────────────────────────────────────────
// أنواع البيانات
// ──────────────────────────────────────────────
interface PairData {
  symbol: string;
  price: number;
  change: number;      // تغيير السعر %
  regime: string;
  regimeLabel: string;
  sellPct: number;     // نسبة البيع (0-100)
  buyPct: number;      // نسبة الشراء (0-100)
  neutralPct: number;  // نسبة المحايد
  agentDecision: 'BUY' | 'SELL' | 'NO_TRADE';
  confidence: number;
  spread: number;
  atr: number;
  rsi: number;
  lastSignalTime: string;
  tradeCount: number;  // عدد الصفقات اليوم
  dayPnl: number;      // ربح/خسارة اليوم
  isUpdated: boolean;  // هل تحدثت للتو
}

// ──────────────────────────────────────────────
// بيانات المحاكاة
// ──────────────────────────────────────────────
const PAIRS = [
  { symbol: 'EUR/USD', basePrice: 1.0872 },
  { symbol: 'GBP/USD', basePrice: 1.2741 },
  { symbol: 'USD/JPY', basePrice: 157.32 },
  { symbol: 'AUD/USD', basePrice: 0.6583 },
  { symbol: 'USD/CAD', basePrice: 1.3621 },
  { symbol: 'USD/CHF', basePrice: 0.8891 },
  { symbol: 'NZD/USD', basePrice: 0.6102 },
  { symbol: 'EUR/GBP', basePrice: 0.8531 },
  { symbol: 'EUR/JPY', basePrice: 170.91 },
  { symbol: 'GBP/JPY', basePrice: 200.42 },
  { symbol: 'XAU/USD', basePrice: 2312.40 },
  { symbol: 'XAG/USD', basePrice: 29.81 },
];

const REGIMES = [
  { key: 'STRONG_TREND', label: 'اتجاه قوي 🚀', color: '#10b981', bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', text: 'text-emerald-400' },
  { key: 'SLOW_TREND',   label: 'اتجاه هادئ 🔵', color: '#3b82f6', bg: 'bg-blue-500/15',   border: 'border-blue-500/40',   text: 'text-blue-400'    },
  { key: 'LOW_VOL_RANGE',label: 'نطاق هادئ 🟡',  color: '#f59e0b', bg: 'bg-yellow-500/15', border: 'border-yellow-500/40', text: 'text-yellow-400'  },
  { key: 'HIGH_VOL_RANGE',label:'نطاق متقلب ⚠️', color: '#f97316', bg: 'bg-orange-500/15', border: 'border-orange-500/40', text: 'text-orange-400'  },
  { key: 'CHAOS',        label: 'فوضى 🔴',       color: '#ef4444', bg: 'bg-red-500/15',    border: 'border-red-500/40',    text: 'text-red-400'     },
];

function getRegime(key: string) {
  return REGIMES.find(r => r.key === key) ?? REGIMES[1];
}

function generatePairData(p: typeof PAIRS[0], seed: number): PairData {
  const regimeIdx = Math.floor((Math.sin(seed * 0.7 + p.symbol.charCodeAt(0) * 0.1) * 2.5 + 2.5)) % 5;
  const regime = REGIMES[regimeIdx];

  // توليد نسب التصويت بناءً على الـ Regime
  let buyBase = 40, sellBase = 40;
  if (regime.key === 'STRONG_TREND') { buyBase = Math.random() > 0.5 ? 72 : 28; sellBase = 100 - buyBase - 10; }
  else if (regime.key === 'SLOW_TREND') { buyBase = 45 + (Math.random() - 0.3) * 30; sellBase = 100 - buyBase - 15; }
  else if (regime.key === 'CHAOS')  { buyBase = 25 + Math.random() * 20; sellBase = 25 + Math.random() * 20; }
  else { buyBase = 35 + (Math.random() - 0.5) * 20; sellBase = 35 + (Math.random() - 0.5) * 20; }

  const buyPct = Math.max(5, Math.min(90, buyBase));
  const sellPct = Math.max(5, Math.min(90, sellBase));
  const neutralPct = Math.max(0, 100 - buyPct - sellPct);

  // قرار الوكيل
  let decision: 'BUY' | 'SELL' | 'NO_TRADE' = 'NO_TRADE';
  const confidence = Math.round(40 + Math.random() * 50);
  if (regime.key !== 'CHAOS' && regime.key !== 'HIGH_VOL_RANGE') {
    if (buyPct >= 60 && confidence >= 65) decision = 'BUY';
    else if (sellPct >= 60 && confidence >= 65) decision = 'SELL';
  }

  const rsi = Math.round(30 + Math.random() * 40);
  const priceVar = (Math.random() - 0.49) * p.basePrice * 0.003;

  return {
    symbol: p.symbol,
    price: parseFloat((p.basePrice + priceVar).toFixed(p.basePrice > 100 ? 2 : 4)),
    change: parseFloat(((Math.random() - 0.48) * 0.8).toFixed(2)),
    regime: regime.key,
    regimeLabel: regime.label,
    sellPct: Math.round(sellPct),
    buyPct: Math.round(buyPct),
    neutralPct: Math.round(neutralPct),
    agentDecision: decision,
    confidence,
    spread: parseFloat((0.5 + Math.random() * 1.5).toFixed(1)),
    atr: parseFloat((8 + Math.random() * 20).toFixed(1)),
    rsi,
    lastSignalTime: `${Math.floor(Math.random() * 30 + 1)}د مضت`,
    tradeCount: Math.floor(Math.random() * 5),
    dayPnl: parseFloat(((Math.random() - 0.4) * 80).toFixed(2)),
    isUpdated: false,
  };
}

// ──────────────────────────────────────────────
// Hook لبيانات الأزواج
// ──────────────────────────────────────────────
function usePairsData(backendAnalysis: Record<string, any> | null) {
  const tick = useRef(0);
  const [pairs, setPairs] = useState<PairData[]>(() =>
    PAIRS.map((p, i) => generatePairData(p, i * 3))
  );

  useEffect(() => {
    const interval = setInterval(() => {
      tick.current++;
      const t = tick.current;

      // إذا كانت بيانات Backend متوفرة نستخدمها
      if (backendAnalysis && Object.keys(backendAnalysis).length > 0) {
        setPairs(prev => prev.map(p => {
          const backendKey = p.symbol.replace('/', '');
          const backData = backendAnalysis[backendKey] ?? backendAnalysis[p.symbol];
          if (backData) {
            const voting = backData.voting ?? {};
            const fsm = backData.fsm ?? {};
            const buyPct = Math.round((voting.buy_score ?? 0) / 8 * 100);
            const sellPct = Math.round((voting.sell_score ?? 0) / 8 * 100);
            let decision: 'BUY' | 'SELL' | 'NO_TRADE' = 'NO_TRADE';
            if (voting.direction === 'BUY') decision = 'BUY';
            else if (voting.direction === 'SELL') decision = 'SELL';

            return {
              ...p,
              regime: fsm.regime ?? p.regime,
              regimeLabel: getRegime(fsm.regime ?? p.regime).label,
              buyPct: Math.min(95, buyPct),
              sellPct: Math.min(95, sellPct),
              neutralPct: Math.max(0, 100 - buyPct - sellPct),
              agentDecision: decision,
              confidence: Math.round(voting.confidence ?? p.confidence),
              price: parseFloat((backData.price ?? p.price).toFixed(4)),
              isUpdated: true,
            };
          }
          return { ...p, isUpdated: false };
        }));
        return;
      }

      // محاكاة بدون Backend
      setPairs(prev => prev.map((p, i) => {
        if (t % 4 !== i % 4) return { ...p, isUpdated: false };
        const updated = generatePairData(PAIRS[i], t + i);
        return { ...updated, isUpdated: true };
      }));
    }, 1500);

    return () => clearInterval(interval);
  }, [backendAnalysis]);

  return pairs;
}

// ──────────────────────────────────────────────
// مكونات مساعدة
// ──────────────────────────────────────────────
function RegimeBadge({ regime }: { regime: string }) {
  const r = getRegime(regime);
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${r.bg} ${r.border} ${r.text} whitespace-nowrap`}>
      {r.label}
    </span>
  );
}

function VoteBar({ buyPct, sellPct, neutralPct }: { buyPct: number; sellPct: number; neutralPct: number }) {
  return (
    <div className="flex h-3 rounded-full overflow-hidden w-full gap-px" title={`BUY:${buyPct}% SELL:${sellPct}% NEUTRAL:${neutralPct}%`}>
      <div className="bg-emerald-500 transition-all duration-500" style={{ width: `${buyPct}%` }} />
      <div className="bg-gray-600 transition-all duration-500"   style={{ width: `${neutralPct}%` }} />
      <div className="bg-red-500 transition-all duration-500"    style={{ width: `${sellPct}%` }} />
    </div>
  );
}

function DecisionBadge({ decision, confidence }: { decision: string; confidence: number }) {
  if (decision === 'BUY') return (
    <div className="flex flex-col items-center gap-1">
      <span className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 border border-emerald-400/50 text-emerald-400 rounded-lg text-xs font-black">
        <span className="text-base">📈</span> شراء
      </span>
      <span className="text-emerald-400/70 text-xs font-mono">{confidence}%</span>
    </div>
  );
  if (decision === 'SELL') return (
    <div className="flex flex-col items-center gap-1">
      <span className="flex items-center gap-1 px-3 py-1.5 bg-red-500/20 border border-red-400/50 text-red-400 rounded-lg text-xs font-black">
        <span className="text-base">📉</span> بيع
      </span>
      <span className="text-red-400/70 text-xs font-mono">{confidence}%</span>
    </div>
  );
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="flex items-center gap-1 px-3 py-1.5 bg-gray-500/20 border border-gray-400/30 text-gray-500 rounded-lg text-xs font-bold">
        <span className="text-base">⏸️</span> محايد
      </span>
      <span className="text-gray-600 text-xs font-mono">{confidence}%</span>
    </div>
  );
}

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────
type SortKey = 'symbol' | 'regime' | 'buyPct' | 'sellPct' | 'agentDecision' | 'confidence' | 'rsi' | 'dayPnl';
type FilterType = 'all' | 'BUY' | 'SELL' | 'NO_TRADE';

export default function PairsStatusTable() {
  const [sortKey, setSortKey]     = useState<SortKey>('symbol');
  const [sortAsc, setSortAsc]     = useState(true);
  const [filter, setFilter]       = useState<FilterType>('all');
  const [search, setSearch]       = useState('');
  const [highlightNew, setHighlight] = useState(true);
  const [showExtra, setShowExtra] = useState(false);

  const { connected } = useBackendStatus();
  const { data: backendAnalysis } = useApiData<Record<string, any>>('/api/latest-analysis', 5000);

  const pairs = usePairsData(backendAnalysis);

  // ─── فلترة وترتيب ────────────────────────────────────────
  const filtered = pairs
    .filter(p => filter === 'all' || p.agentDecision === filter)
    .filter(p => p.symbol.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      let diff = 0;
      if (sortKey === 'symbol') diff = a.symbol.localeCompare(b.symbol);
      else if (sortKey === 'regime') diff = a.regime.localeCompare(b.regime);
      else if (sortKey === 'buyPct') diff = a.buyPct - b.buyPct;
      else if (sortKey === 'sellPct') diff = a.sellPct - b.sellPct;
      else if (sortKey === 'agentDecision') diff = a.agentDecision.localeCompare(b.agentDecision);
      else if (sortKey === 'confidence') diff = a.confidence - b.confidence;
      else if (sortKey === 'rsi') diff = a.rsi - b.rsi;
      else if (sortKey === 'dayPnl') diff = a.dayPnl - b.dayPnl;
      return sortAsc ? diff : -diff;
    });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const SortIcon = ({ col }: { col: SortKey }) => (
    <span className="mr-1 opacity-40 text-xs">
      {sortKey === col ? (sortAsc ? '↑' : '↓') : '↕'}
    </span>
  );

  // ─── ملخص الإحصائيات ──────────────────────────────────────
  const buyCount   = pairs.filter(p => p.agentDecision === 'BUY').length;
  const sellCount  = pairs.filter(p => p.agentDecision === 'SELL').length;
  const holdCount  = pairs.filter(p => p.agentDecision === 'NO_TRADE').length;
  const avgConf    = Math.round(pairs.reduce((s, p) => s + p.confidence, 0) / pairs.length);
  const trendCount = pairs.filter(p => p.regime.includes('TREND')).length;
  const rangeCount = pairs.filter(p => p.regime.includes('RANGE') || p.regime === 'CHAOS').length;

  return (
    <div className="space-y-4" dir="rtl">

      {/* ═══ Hero ═══════════════════════════════════════════════ */}
      <div className="bg-gradient-to-br from-slate-800/80 via-purple-900/30 to-slate-800/80 rounded-3xl p-6 border border-purple-500/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(139,92,246,0.12),transparent_60%)] pointer-events-none" />
        <div className="relative">
          <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
            <div>
              <h2 className="text-3xl font-black text-white mb-1">📊 جدول حالة الأزواج</h2>
              <p className="text-gray-400 text-sm">
                {connected ? '🟢 بيانات حقيقية من Backend' : '🟡 محاكاة — شغّل الـ Backend لبيانات حقيقية'}
                {' '} • يتحدث كل 1.5 ثانية
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={highlightNew}
                  onChange={e => setHighlight(e.target.checked)}
                  className="accent-purple-500"
                />
                تمييز التحديثات
              </label>
              <button
                onClick={() => setShowExtra(!showExtra)}
                className="px-3 py-1.5 bg-white/5 border border-white/10 text-gray-400 text-xs rounded-lg hover:text-white transition-all"
              >
                {showExtra ? '▲ إخفاء تفاصيل' : '▼ إظهار تفاصيل'}
              </button>
            </div>
          </div>

          {/* ─── ملخص الإحصائيات ─── */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <div className="bg-emerald-500/10 border border-emerald-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-emerald-400">{buyCount}</div>
              <div className="text-xs text-emerald-400/70">📈 شراء</div>
            </div>
            <div className="bg-red-500/10 border border-red-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-red-400">{sellCount}</div>
              <div className="text-xs text-red-400/70">📉 بيع</div>
            </div>
            <div className="bg-gray-500/10 border border-gray-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-gray-400">{holdCount}</div>
              <div className="text-xs text-gray-400/70">⏸️ محايد</div>
            </div>
            <div className="bg-blue-500/10 border border-blue-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-blue-400">{trendCount}</div>
              <div className="text-xs text-blue-400/70">🚀 اتجاه</div>
            </div>
            <div className="bg-yellow-500/10 border border-yellow-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-yellow-400">{rangeCount}</div>
              <div className="text-xs text-yellow-400/70">🔄 نطاق/فوضى</div>
            </div>
            <div className="bg-purple-500/10 border border-purple-400/30 rounded-xl p-3 text-center">
              <div className="text-2xl font-black text-purple-400">{avgConf}%</div>
              <div className="text-xs text-purple-400/70">⚡ متوسط الثقة</div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ شريط التحكم ════════════════════════════════════════ */}
      <div className="flex flex-wrap items-center gap-3">
        {/* بحث */}
        <div className="relative">
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">🔎</span>
          <input
            type="text"
            placeholder="بحث... EUR/USD"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-white/5 border border-white/10 text-white text-sm rounded-xl pr-9 pl-4 py-2 w-40 focus:outline-none focus:border-purple-400 placeholder-gray-600"
          />
        </div>

        {/* فلتر القرار */}
        {(['all', 'BUY', 'SELL', 'NO_TRADE'] as FilterType[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all ${
              filter === f
                ? f === 'BUY'      ? 'bg-emerald-500/30 border-emerald-400/60 text-emerald-300'
                : f === 'SELL'     ? 'bg-red-500/30 border-red-400/60 text-red-300'
                : f === 'NO_TRADE' ? 'bg-gray-500/30 border-gray-400/60 text-gray-300'
                :                    'bg-purple-500/30 border-purple-400/60 text-purple-300'
                : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300 hover:bg-white/8'
            }`}
          >
            {f === 'all' ? '🔍 الكل' : f === 'BUY' ? '📈 شراء' : f === 'SELL' ? '📉 بيع' : '⏸️ محايد'}
            {f !== 'all' && (
              <span className="mr-1.5 opacity-70">
                ({f === 'BUY' ? buyCount : f === 'SELL' ? sellCount : holdCount})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ═══ الجدول الرئيسي ══════════════════════════════════════ */}
      <div className="bg-white/3 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">

            {/* ─── Header ─── */}
            <thead>
              <tr className="bg-gradient-to-r from-purple-900/40 via-slate-800/60 to-purple-900/40 border-b border-white/10">
                <th className="px-4 py-4 text-right">
                  <button
                    onClick={() => handleSort('symbol')}
                    className="flex items-center gap-1 text-gray-300 font-bold text-xs uppercase tracking-wider hover:text-white transition-all"
                  >
                    <SortIcon col="symbol" />
                    💱 الزوج
                  </button>
                </th>
                <th className="px-4 py-4 text-right">
                  <button
                    onClick={() => handleSort('regime')}
                    className="flex items-center gap-1 text-gray-300 font-bold text-xs uppercase tracking-wider hover:text-white transition-all"
                  >
                    <SortIcon col="regime" />
                    🔍 حالة البيئة (FSM)
                  </button>
                </th>
                <th className="px-4 py-4 text-center">
                  <button
                    onClick={() => handleSort('sellPct')}
                    className="flex items-center justify-center gap-1 text-red-400 font-bold text-xs uppercase tracking-wider hover:text-red-300 transition-all w-full"
                  >
                    <SortIcon col="sellPct" />
                    📉 نسبة البيع
                  </button>
                </th>
                <th className="px-4 py-4 text-center">
                  <button
                    onClick={() => handleSort('buyPct')}
                    className="flex items-center justify-center gap-1 text-emerald-400 font-bold text-xs uppercase tracking-wider hover:text-emerald-300 transition-all w-full"
                  >
                    <SortIcon col="buyPct" />
                    📈 نسبة الشراء
                  </button>
                </th>
                <th className="px-4 py-4 text-center">
                  <span className="text-gray-300 font-bold text-xs uppercase tracking-wider">
                    📊 توزيع الأصوات
                  </span>
                </th>
                <th className="px-4 py-4 text-center">
                  <button
                    onClick={() => handleSort('agentDecision')}
                    className="flex items-center justify-center gap-1 text-purple-400 font-bold text-xs uppercase tracking-wider hover:text-purple-300 transition-all w-full"
                  >
                    <SortIcon col="agentDecision" />
                    🤖 قرار الوكلاء
                  </button>
                </th>
                {showExtra && (
                  <>
                    <th className="px-4 py-4 text-center">
                      <button onClick={() => handleSort('rsi')}
                        className="flex items-center justify-center gap-1 text-gray-300 font-bold text-xs uppercase tracking-wider hover:text-white transition-all w-full">
                        <SortIcon col="rsi" />RSI
                      </button>
                    </th>
                    <th className="px-4 py-4 text-center">
                      <span className="text-gray-300 font-bold text-xs">Spread</span>
                    </th>
                    <th className="px-4 py-4 text-center">
                      <button onClick={() => handleSort('dayPnl')}
                        className="flex items-center justify-center gap-1 text-gray-300 font-bold text-xs uppercase tracking-wider hover:text-white transition-all w-full">
                        <SortIcon col="dayPnl" />P&L اليوم
                      </button>
                    </th>
                    <th className="px-4 py-4 text-center">
                      <span className="text-gray-300 font-bold text-xs">آخر إشارة</span>
                    </th>
                  </>
                )}
              </tr>
            </thead>

            {/* ─── Body ─── */}
            <tbody className="divide-y divide-white/5">
              {filtered.map((pair, rowIdx) => {
                const regime = getRegime(pair.regime);
                const isFlash = highlightNew && pair.isUpdated;
                const decColor = pair.agentDecision === 'BUY' ? 'bg-emerald-500/5' : pair.agentDecision === 'SELL' ? 'bg-red-500/5' : '';

                return (
                  <tr
                    key={pair.symbol}
                    className={`transition-all duration-500 hover:bg-white/5 ${decColor} ${
                      isFlash ? 'animate-pulse bg-purple-500/5' : ''
                    }`}
                  >
                    {/* ── الزوج + السعر ── */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl flex items-center justify-center text-white font-black text-xs flex-shrink-0">
                          {rowIdx + 1}
                        </div>
                        <div>
                          <div className="text-white font-bold text-sm">{pair.symbol}</div>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-gray-400 font-mono text-xs">{pair.price}</span>
                            <span className={`text-xs font-bold ${pair.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                              {pair.change >= 0 ? '+' : ''}{pair.change}%
                            </span>
                          </div>
                        </div>
                        {isFlash && (
                          <span className="w-2 h-2 bg-purple-400 rounded-full animate-ping flex-shrink-0" />
                        )}
                      </div>
                    </td>

                    {/* ── FSM Regime ── */}
                    <td className="px-4 py-3">
                      <RegimeBadge regime={pair.regime} />
                    </td>

                    {/* ── نسبة البيع ── */}
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <div className={`text-xl font-black ${pair.sellPct > 55 ? 'text-red-400' : pair.sellPct > 40 ? 'text-orange-400' : 'text-gray-500'}`}>
                          {pair.sellPct}%
                        </div>
                        <div className="w-16 h-1.5 bg-black/30 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-red-500 rounded-full transition-all duration-500"
                            style={{ width: `${pair.sellPct}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* ── نسبة الشراء ── */}
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <div className={`text-xl font-black ${pair.buyPct > 55 ? 'text-emerald-400' : pair.buyPct > 40 ? 'text-teal-400' : 'text-gray-500'}`}>
                          {pair.buyPct}%
                        </div>
                        <div className="w-16 h-1.5 bg-black/30 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                            style={{ width: `${pair.buyPct}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* ── شريط توزيع الأصوات ── */}
                    <td className="px-4 py-3">
                      <div className="space-y-1.5 min-w-[120px]">
                        <VoteBar buyPct={pair.buyPct} sellPct={pair.sellPct} neutralPct={pair.neutralPct} />
                        <div className="flex justify-between text-xs text-gray-600">
                          <span className="text-emerald-500">{pair.buyPct}%</span>
                          <span className="text-gray-600">{pair.neutralPct}%</span>
                          <span className="text-red-500">{pair.sellPct}%</span>
                        </div>
                      </div>
                    </td>

                    {/* ── قرار الوكلاء ── */}
                    <td className="px-4 py-3 text-center">
                      <DecisionBadge decision={pair.agentDecision} confidence={pair.confidence} />
                    </td>

                    {/* ── تفاصيل إضافية ── */}
                    {showExtra && (
                      <>
                        <td className="px-4 py-3 text-center">
                          <div className={`text-sm font-bold font-mono ${
                            pair.rsi > 70 ? 'text-red-400' : pair.rsi < 30 ? 'text-emerald-400' : 'text-gray-300'
                          }`}>
                            {pair.rsi}
                          </div>
                          <div className="text-xs text-gray-600">
                            {pair.rsi > 70 ? 'تشبع شرائي' : pair.rsi < 30 ? 'تشبع بيعي' : 'عادي'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`text-xs font-mono ${pair.spread < 1.2 ? 'text-emerald-400' : 'text-yellow-400'}`}>
                            {pair.spread}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`text-sm font-bold ${pair.dayPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {pair.dayPnl >= 0 ? '+' : ''}${pair.dayPnl.toFixed(2)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center text-xs text-gray-500">
                          {pair.lastSignalTime}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={showExtra ? 10 : 6} className="py-12 text-center text-gray-600">
                    لا توجد أزواج تطابق البحث
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ─── Footer ─── */}
        <div className="px-4 py-3 border-t border-white/10 bg-black/20 flex items-center justify-between text-xs text-gray-600">
          <span>إجمالي الأزواج: {filtered.length} / {pairs.length}</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
            يتحدث كل 1.5 ثانية
          </span>
        </div>
      </div>

      {/* ═══ لوحة الملخص السريع ══════════════════════════════════ */}
      <div className="grid md:grid-cols-3 gap-4">

        {/* أزواج الشراء */}
        <div className="bg-emerald-500/8 rounded-2xl p-5 border border-emerald-500/30">
          <h3 className="text-emerald-400 font-bold mb-3 flex items-center gap-2">
            <span className="text-xl">📈</span> أزواج الشراء ({buyCount})
          </h3>
          <div className="space-y-2">
            {pairs.filter(p => p.agentDecision === 'BUY').map(p => (
              <div key={p.symbol} className="flex items-center justify-between bg-black/20 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold text-sm">{p.symbol}</span>
                  <RegimeBadge regime={p.regime} />
                </div>
                <div className="text-right">
                  <div className="text-emerald-400 font-bold text-sm">{p.buyPct}% BUY</div>
                  <div className="text-gray-500 text-xs">ثقة: {p.confidence}%</div>
                </div>
              </div>
            ))}
            {buyCount === 0 && <div className="text-gray-600 text-sm text-center py-2">لا توجد</div>}
          </div>
        </div>

        {/* أزواج البيع */}
        <div className="bg-red-500/8 rounded-2xl p-5 border border-red-500/30">
          <h3 className="text-red-400 font-bold mb-3 flex items-center gap-2">
            <span className="text-xl">📉</span> أزواج البيع ({sellCount})
          </h3>
          <div className="space-y-2">
            {pairs.filter(p => p.agentDecision === 'SELL').map(p => (
              <div key={p.symbol} className="flex items-center justify-between bg-black/20 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold text-sm">{p.symbol}</span>
                  <RegimeBadge regime={p.regime} />
                </div>
                <div className="text-right">
                  <div className="text-red-400 font-bold text-sm">{p.sellPct}% SELL</div>
                  <div className="text-gray-500 text-xs">ثقة: {p.confidence}%</div>
                </div>
              </div>
            ))}
            {sellCount === 0 && <div className="text-gray-600 text-sm text-center py-2">لا توجد</div>}
          </div>
        </div>

        {/* توزيع الـ Regimes */}
        <div className="bg-purple-500/8 rounded-2xl p-5 border border-purple-500/30">
          <h3 className="text-purple-400 font-bold mb-3 flex items-center gap-2">
            <span className="text-xl">🔍</span> توزيع البيئات
          </h3>
          <div className="space-y-2">
            {REGIMES.map(r => {
              const count = pairs.filter(p => p.regime === r.key).length;
              if (count === 0) return null;
              return (
                <div key={r.key} className="flex items-center gap-3">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: r.color }} />
                  <span className="text-gray-300 text-xs flex-1">{r.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-black/30 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${(count / pairs.length) * 100}%`, background: r.color }}
                      />
                    </div>
                    <span className="text-white font-bold text-xs w-4">{count}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* مؤشر عام */}
          <div className="mt-4 pt-4 border-t border-white/10">
            <div className="text-center">
              <div className="text-gray-400 text-xs mb-1">توجه السوق العام</div>
              <div className={`text-2xl font-black ${
                buyCount > sellCount + 2 ? 'text-emerald-400' :
                sellCount > buyCount + 2 ? 'text-red-400' :
                'text-yellow-400'
              }`}>
                {buyCount > sellCount + 2 ? '📈 صاعد' :
                 sellCount > buyCount + 2 ? '📉 هابط' :
                 '🔄 محايد'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ تفسير الأعمدة ═══════════════════════════════════════ */}
      <div className="bg-white/3 rounded-2xl p-5 border border-white/10">
        <h3 className="text-white font-bold mb-4">📖 دليل قراءة الجدول</h3>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          {[
            { col: '🔍 حالة البيئة (FSM)', desc: 'نظام الكشف عن حالة السوق: اتجاه قوي، هادئ، نطاق، أو فوضى. يحدد ما إذا كان التداول مسموحاً به.' },
            { col: '📉 نسبة البيع / 📈 نسبة الشراء', desc: 'نسبة أصوات مجلس التصويت (5 مؤشرات). كل مؤشر يصوت BUY/SELL/NEUTRAL ثم نحسب النسب المئوية.' },
            { col: '🤖 قرار الوكلاء', desc: 'القرار النهائي: يحتاج ≥60% أصوات + موافقة Heiken Ashi + الـ Regime مناسب + ثقة ≥65%.' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-4">
              <div className="text-purple-400 font-bold mb-2">{item.col}</div>
              <div className="text-gray-400 text-xs leading-relaxed">{item.desc}</div>
            </div>
          ))}
        </div>

        {/* مفتاح الألوان */}
        <div className="mt-4 flex flex-wrap gap-3">
          {REGIMES.map(r => (
            <div key={r.key} className="flex items-center gap-1.5 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: r.color }} />
              <span className="text-gray-400">{r.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
