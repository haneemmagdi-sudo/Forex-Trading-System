import { useState, useEffect, useRef } from 'react';
import { useBackendStatus, useApiData } from '../../utils/useBackend';


function useLiveData() {
  const [data, setData] = useState({
    balance: 10000,
    equity: 10000,
    profit: 0,
    dd: 0,
    winRate: 73.5,
    openTrades: 0,
    regime: 'SLOW_TREND',
    regimeLabel: 'SLOW TREND 🔵',
    buyScore: 4.2,
    sellScore: 2.1,
    direction: 'BUY',
    spreadEURUSD: 0.8,
    atr: 14.5,
    lastSignal: 'BUY — EUR/USD — 4 دقائق مضت',
    positions: [] as { pair: string; type: string; pnl: number; pips: number; lots: number }[],
    equityCurve: [0, 1.2, 0.8, 2.1, 1.5, 3.0, 2.5, 4.1, 3.8, 5.2] as number[],
    dailyPnl: 0,
    totalTrades: 0,
    consecutiveLosses: 0,
  });

  const tick = useRef(0);

  useEffect(() => {
    const interval = setInterval(() => {
      tick.current += 1;
      const t = tick.current;

      setData(prev => {
        const random = (Math.sin(t * 1.7 + 2.3) * 0.5 + 0.5);
        const variation = (random - 0.48) * 40;
        const newEquity = Math.max(9500, prev.balance + variation * 0.5 + (prev.profit || 0));
        const dd = Math.max(0, (prev.balance - newEquity) / prev.balance * 100);

        const regimes = [
          { key: 'LOW_VOL_RANGE', label: 'LOW VOL 🟡' },
          { key: 'SLOW_TREND', label: 'SLOW TREND 🔵' },
          { key: 'HIGH_VOL_RANGE', label: 'HIGH VOL ⚠️' },
          { key: 'STRONG_TREND', label: 'STRONG TREND 🚀' },
        ];
        const regime = regimes[Math.floor(t / 20) % 4];

        const positions = t % 15 < 8
          ? [
              { pair: 'EUR/USD', type: 'BUY', pnl: variation * 1.2, pips: Math.floor(variation * 0.8), lots: 0.02 },
              { pair: 'GBP/USD', type: 'SELL', pnl: -variation * 0.5, pips: Math.floor(-variation * 0.4), lots: 0.01 },
            ]
          : [{ pair: 'USD/JPY', type: 'BUY', pnl: variation * 0.7, pips: Math.floor(variation * 0.5), lots: 0.02 }];

        const totalProfit = positions.reduce((s, p) => s + p.pnl, 0);
        const newCurve = [...prev.equityCurve, totalProfit].slice(-30);

        return {
          ...prev,
          equity: parseFloat(newEquity.toFixed(2)),
          profit: parseFloat(totalProfit.toFixed(2)),
          dd: parseFloat(dd.toFixed(2)),
          regime: regime.key,
          regimeLabel: regime.label,
          buyScore: parseFloat((Math.sin(t * 0.5) * 1.5 + 3.5).toFixed(2)),
          sellScore: parseFloat((Math.cos(t * 0.5) * 1.5 + 2.0).toFixed(2)),
          spreadEURUSD: parseFloat((Math.random() * 0.4 + 0.6).toFixed(1)),
          atr: parseFloat((Math.sin(t * 0.3) * 3 + 14).toFixed(1)),
          openTrades: positions.length,
          positions,
          equityCurve: newCurve,
          dailyPnl: parseFloat((totalProfit + prev.dailyPnl * 0.98).toFixed(2)),
          totalTrades: prev.totalTrades + (t % 40 === 0 ? 1 : 0),
        };
      });
    }, 800);

    return () => clearInterval(interval);
  }, []);

  return data;
}

export default function LiveDashboard() {
  const simData = useLiveData();
  const { status, connected } = useBackendStatus();
  const { data: account }   = useApiData<Record<string,any>>('/api/account', 5000);
  const { data: signals }   = useApiData<any[]>('/api/signals?limit=5', 8000);
  const { data: perf }      = useApiData<Record<string,any>>('/api/performance', 10000);
  const { data: positions } = useApiData<any[]>('/api/open-positions', 5000);

  // استخدام بيانات حقيقية عند الاتصال، وإلا المحاكاة
  const balance    = account?.balance    ?? simData.balance;
  const equity     = account?.equity     ?? simData.equity;
  const dd = account ? Math.max(0, (balance - equity) / balance * 100) : simData.dd;

  const winRate    = perf?.win_rate      ?? simData.winRate;
  const totalTrades= perf?.total_trades  ?? simData.totalTrades;
  const openTrades = positions ? positions.length : simData.openTrades;

  // آخر إشارة من الـ Backend
  const lastSignalStr = signals && signals.length > 0
    ? `${signals[0].direction} — ${signals[0].symbol} — ${new Date(signals[0].created_at).toLocaleTimeString('ar-SA')}`
    : simData.lastSignal;

  // حالة Regime من الوكيل
  const analystState = status?.agents?.analyst as any;
  const regimes = analystState?.current_regimes ?? {};
  const firstRegime = Object.values(regimes)[0] as string ?? simData.regime;
  const regimeMap: Record<string, string> = {
    LOW_VOL_RANGE:  'LOW VOL 🟡',
    SLOW_TREND:     'SLOW TREND 🔵',
    HIGH_VOL_RANGE: 'HIGH VOL ⚠️',
    STRONG_TREND:   'STRONG TREND 🚀',
    CHAOS:          'CHAOS 🔴',
  };

  const [showAlert, setShowAlert] = useState(false);
  useEffect(() => {
    setShowAlert(dd > 3);
  }, [dd]);



  const regimeColors: Record<string, string> = {
    LOW_VOL_RANGE: 'text-yellow-400',
    SLOW_TREND: 'text-blue-400',
    HIGH_VOL_RANGE: 'text-orange-400',
    STRONG_TREND: 'text-emerald-400',
    CHAOS: 'text-red-400',
  };

  const ddColor = dd < 2 ? 'text-emerald-400' : dd < 4 ? 'text-yellow-400' : 'text-red-400';
  const profit = equity - balance;

  return (
    <div className="space-y-4" dir="rtl">
      {/* Header */}
      <div className="bg-gradient-to-br from-cyan-500/20 to-teal-500/20 rounded-3xl p-6 border border-cyan-400/30">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-3xl font-bold text-white mb-1">📈 لوحة المراقبة الحية</h2>
            <p className="text-cyan-200 text-sm">
              {connected ? '🟢 متصل بالـ Backend — بيانات حقيقية' : '🟡 محاكاة — شغّل الـ Backend للبيانات الحقيقية'}
            </p>
          </div>
          <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-bold ${
            connected
              ? 'bg-emerald-500/20 border-emerald-400/30 text-emerald-400'
              : 'bg-yellow-500/20 border-yellow-400/30 text-yellow-400'
          }`}>
            <span className={`w-2 h-2 rounded-full animate-pulse ${
              connected ? 'bg-emerald-400' : 'bg-yellow-400'
            }`} />
            {connected ? 'LIVE BACKEND' : 'SIMULATION'}
          </div>
        </div>
      </div>

      {/* DD Alert */}
      {showAlert && (
        <div className="bg-red-500/20 border border-red-400/40 rounded-xl p-4 flex items-center gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <div className="text-red-300 font-bold">تحذير: التراجع تجاوز 3%</div>
            <div className="text-red-400/70 text-sm">تم تفعيل وضع الحذر (Soft DD Mode)</div>
          </div>
        </div>
      )}

      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'الرصيد', value: `$${balance.toLocaleString()}`, sub: 'Balance', icon: '💰', color: 'text-white' },
          { label: 'Equity', value: `$${equity.toLocaleString()}`, sub: `P&L: ${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}`, icon: '📊', color: profit >= 0 ? 'text-emerald-400' : 'text-red-400' },
          { label: 'Drawdown', value: `${dd.toFixed(2)}%`, sub: dd < 2 ? '🟢 آمن' : dd < 4 ? '🟡 تحذير' : '🔴 خطر', icon: '📉', color: ddColor },
          { label: 'Win Rate', value: `${(winRate || 0).toFixed(1)}%`, sub: `${totalTrades} صفقة`, icon: '🎯', color: 'text-purple-400' },
        ].map((m, i) => (
          <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-500 text-xs">{m.label}</span>
              <span className="text-lg">{m.icon}</span>
            </div>
            <div className={`text-2xl font-black ${m.color}`}>{m.value}</div>
            <div className="text-gray-500 text-xs mt-1">{m.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {/* FSM Status */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <h3 className="text-white font-bold mb-4">🔍 حالة FSM الحالية</h3>
          <div className={`text-2xl font-black mb-3 ${regimeColors[firstRegime] || 'text-gray-400'}`}>
            {regimeMap[firstRegime] || firstRegime || 'UNKNOWN'}
          </div>

          {/* Vote Scores */}
          <div className="space-y-2">
            <div className="text-gray-500 text-xs mb-2">نتيجة مجلس التصويت</div>
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 text-xs w-12">BUY</span>
              <div className="flex-1 bg-black/30 rounded-full h-2">
                <div className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${(simData.buyScore / 8) * 100}%` }} />
            </div>
            <span className="text-emerald-400 text-xs font-mono w-8">{simData.buyScore}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-red-400 text-xs w-12">SELL</span>
              <div className="flex-1 bg-black/30 rounded-full h-2">
                <div className="bg-red-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${(simData.sellScore / 8) * 100}%` }} />
            </div>
            <span className="text-red-400 text-xs font-mono w-8">{simData.sellScore}</span>
            </div>
          </div>

          {/* Market Info */}
          <div className="mt-4 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">EUR/USD Spread</span>
              <span className={`font-mono ${simData.spreadEURUSD < 1.5 ? 'text-emerald-400' : 'text-yellow-400'}`}>{simData.spreadEURUSD}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">ATR (Current)</span>
              <span className="text-white font-mono">{simData.atr} نقطة</span>
            </div>
          </div>
        </div>

        {/* Open Positions */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-bold">💼 الصفقات المفتوحة</h3>
            <span className="text-purple-400 text-sm font-bold">{openTrades} صفقة</span>
          </div>
          {(positions && positions.length > 0 ? positions : simData.positions).length > 0 ? (
            <div className="space-y-3">
              {(positions && positions.length > 0 ? positions.map((p: any) => ({
                pair: p.symbol, type: p.type, pnl: p.profit ?? 0, pips: 0, lots: p.volume
              })) : simData.positions).map((pos: any, i: number) => (
                <div key={i} className={`bg-black/20 rounded-xl p-3 border ${pos.pnl >= 0 ? 'border-emerald-500/20' : 'border-red-500/20'}`}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-white font-bold text-sm">{pos.pair}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${pos.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                      {pos.type}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>Lots: {pos.lots}</span>
                    <span className={pos.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                      {pos.pnl >= 0 ? '+' : ''}${(pos.pnl || 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-600 py-6">لا توجد صفقات مفتوحة</div>
          )}

          <div className="mt-3 pt-3 border-t border-white/5">
            <div className="text-xs text-gray-500">آخر إشارة:</div>
            <div className="text-white text-sm mt-1">{lastSignalStr}</div>
          </div>
        </div>

        {/* Equity Sparkline + Daily Stats */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <h3 className="text-white font-bold mb-3">📊 الأداء اليومي</h3>

          {/* Equity Mini Chart */}
          <div className="mb-4">
            <div className="text-gray-500 text-xs mb-2">منحنى الـ Equity (آخر 30 شموع)</div>
            <div className="overflow-hidden">
              <svg viewBox={`0 0 300 80`} className="w-full">
                <defs>
                  <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(139,92,246,0.5)" />
                    <stop offset="100%" stopColor="rgba(139,92,246,0)" />
                  </linearGradient>
                </defs>
                {simData.equityCurve.length >= 2 && (() => {
                  const vals = simData.equityCurve;
                  const min = Math.min(...vals), max = Math.max(...vals);
                  const range = max - min || 1;
                  const pts = vals.map((v, i) => {
                    const x = (i / (vals.length - 1)) * 290 + 5;
                    const y = 5 + ((max - v) / range) * 65;
                    return `${x},${y}`;
                  });
                  return (
                    <>
                      <path
                        d={`M 5,75 L ${pts.join(' L ')} L 295,75 Z`}
                        fill="url(#sparkGrad)"
                      />
                      <polyline
                        points={pts.join(' ')}
                        fill="none"
                        stroke="#8b5cf6"
                        strokeWidth="2"
                      />
                    </>
                  );
                })()}
              </svg>
            </div>
          </div>

          {/* Daily Stats */}
          <div className="space-y-2">
            {[
              { label: 'P&L اليوم', value: `${simData.dailyPnl >= 0 ? '+' : ''}$${simData.dailyPnl.toFixed(2)}`, color: simData.dailyPnl >= 0 ? 'text-emerald-400' : 'text-red-400' },
              { label: 'صفقات اليوم', value: totalTrades, color: 'text-white' },
              { label: 'Drawdown الحالي', value: `${dd.toFixed(2)}%`, color: ddColor },
              { label: 'صفقات مفتوحة', value: openTrades, color: 'text-purple-400' },
            ].map((s, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-gray-500">{s.label}</span>
                <span className={`font-bold ${s.color}`}>{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* DD Gauge */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
        <h3 className="text-white font-bold mb-3">🛡️ مقياس الحماية</h3>
        <div className="space-y-3">
          {[
            { label: 'Soft DD Warning', threshold: 3.0, color: 'bg-yellow-500' },
            { label: 'Smart Hedge Trigger', threshold: 2.5, color: 'bg-orange-500' },
            { label: 'Emergency Stop', threshold: 5.0, color: 'bg-red-500' },
          ].map((zone, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="text-gray-400 text-xs w-36 flex-shrink-0">{zone.label}</span>
              <div className="flex-1 bg-black/30 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-3 rounded-full transition-all duration-300 ${zone.color} opacity-70`}
                  style={{ width: `${(zone.threshold / 6) * 100}%` }}
                />
                <div
                  className="h-3 rounded-full -mt-3 bg-purple-500 transition-all duration-500"
                  style={{ width: `${Math.min((dd / 6) * 100, 100)}%` }}
                />
              </div>
              <span className="text-gray-500 text-xs w-10 text-right">{zone.threshold}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
