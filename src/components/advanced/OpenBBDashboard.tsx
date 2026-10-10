import { useState } from 'react';
import { useApiData } from '../../utils/useBackend';

interface HistoricalRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface MacroRow {
  date: string;
  [key: string]: string | number;
}

export default function OpenBBDashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD');
  const [equitySymbol, setEquitySymbol] = useState('AAPL');
  const [searchEquity, setSearchEquity] = useState('AAPL');
  const [historicalDays, setHistoricalDays] = useState('2025-01-01');

  // Fetch data from FastAPI endpoints
  const { data: historicalRes, loading: histLoading, error: histError } = useApiData<{ success: boolean; data: HistoricalRow[] }>(
    `/api/openbb/historical?symbol=${selectedSymbol}&start_date=${historicalDays}`,
    15000
  );

  const { data: macroRes, loading: macroLoading, error: macroError } = useApiData<{ success: boolean; data: Record<string, MacroRow[]> }>(
    '/api/openbb/macro',
    30000
  );

  const { data: fundRes, loading: fundLoading, error: fundError } = useApiData<{ success: boolean; data: any }>(
    `/api/openbb/fundamentals?symbol=${equitySymbol}`,
    20000
  );

  // Subscribing to live analysis from market analyst agent
  const { data: latestAnalysis } = useApiData<Record<string, any>>(
    '/api/latest-analysis',
    5000
  );

  const isForex = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'].includes(selectedSymbol);
  const currentAnalysis = latestAnalysis?.[selectedSymbol];

  // Status for simulated fallback if API keys / Backend is offline
  const apiOffline = histError || macroError || fundError;

  // Mock static data for visual presentation if API/Backend is offline
  const mockHistoricalData: HistoricalRow[] = [
    { date: '2026-06-11', open: 1.0820, high: 1.0855, low: 1.0805, close: 1.0842, volume: 14500 },
    { date: '2026-06-12', open: 1.0840, high: 1.0880, low: 1.0830, close: 1.0871, volume: 15200 },
    { date: '2026-06-15', open: 1.0870, high: 1.0910, low: 1.0865, close: 1.0898, volume: 16100 },
    { date: '2026-06-16', open: 1.0895, high: 1.0930, low: 1.0880, close: 1.0924, volume: 15800 },
    { date: '2026-06-17', open: 1.0920, high: 1.0945, low: 1.0900, close: 1.0912, volume: 17200 }
  ];

  const mockMacroData = {
    FEDFUNDS: [
      { date: '2025-12', FEDFUNDS: 5.33 },
      { date: '2026-01', FEDFUNDS: 5.33 },
      { date: '2026-02', FEDFUNDS: 5.33 },
      { date: '2026-03', FEDFUNDS: 5.08 },
      { date: '2026-04', FEDFUNDS: 4.83 },
      { date: '2026-05', FEDFUNDS: 4.58 }
    ],
    CPIAUCSL: [
      { date: '2025-12', CPIAUCSL: 3.1 },
      { date: '2026-01', CPIAUCSL: 3.0 },
      { date: '2026-02', CPIAUCSL: 2.8 },
      { date: '2026-03', CPIAUCSL: 2.7 },
      { date: '2026-04', CPIAUCSL: 2.5 },
      { date: '2026-05', FEDFUNDS: 2.4 }
    ],
    UNRATE: [
      { date: '2025-12', UNRATE: 3.8 },
      { date: '2026-01', UNRATE: 3.9 },
      { date: '2026-02', UNRATE: 4.0 },
      { date: '2026-03', UNRATE: 4.1 },
      { date: '2026-04', UNRATE: 4.2 },
      { date: '2026-05', UNRATE: 4.3 }
    ]
  };

  const mockFundamentals = {
    symbol: 'AAPL',
    provider: 'yfinance',
    as_of: '2026-06-18',
    health_summary: 'Valued at 28.5x earnings (moderate); leverage 1.45x D/E (moderate); ROE 143.2% (strong)',
    period: '2025-12-31',
    ratios: {
      'P/E Ratio': 28.52,
      'Price / Book': 38.45,
      'Price / Sales': 7.12,
      'Debt / Equity': 1.45,
      'Current Ratio': 1.04,
      'Quick Ratio': 0.88,
      'ROE (%)': 143.2,
      'ROA (%)': 29.8,
      'Net Profit Margin (%)': 26.12,
      'Gross Profit Margin (%)': 44.85,
      'Dividend Yield (%)': 0.52,
      'Earnings Per Share': 6.16
    }
  };

  const getHistData = () => {
    if (historicalRes?.success && historicalRes.data.length > 0) {
      return historicalRes.data;
    }
    return mockHistoricalData;
  };

  const getMacro = (key: 'FEDFUNDS' | 'CPIAUCSL' | 'UNRATE') => {
    if (macroRes?.success && macroRes.data[key]) {
      return macroRes.data[key];
    }
    return mockMacroData[key];
  };

  const getFunds = () => {
    if (fundRes?.success && fundRes.data) {
      return fundRes.data;
    }
    return mockFundamentals;
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchEquity.trim()) {
      const cleaned = searchEquity.trim().replace('/', '').toUpperCase();
      setEquitySymbol(cleaned);
    }
  };

  const currentHist = getHistData();
  const currentFunds = getFunds();

  // Helper for drawing SVG Chart paths
  const drawLinePath = (data: any[], valKey: string, width: number, height: number) => {
    if (data.length < 2) return '';
    const values = data.map(d => parseFloat(d[valKey] || d.close || 0));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    
    return data.map((d, i) => {
      const x = (i / (data.length - 1)) * (width - 10) + 5;
      const y = height - 5 - ((parseFloat(d[valKey] || d.close || 0) - min) / range) * (height - 10);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    }).join(' ');
  };

  const drawAreaPath = (data: any[], valKey: string, width: number, height: number) => {
    const linePath = drawLinePath(data, valKey, width, height);
    if (!linePath) return '';
    return `${linePath} L ${width - 5} ${height} L 5 ${height} Z`;
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header Banner */}
      <div className="bg-gradient-to-br from-indigo-900/30 to-purple-900/30 rounded-3xl p-6 border border-purple-500/20">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-3xl font-extrabold text-white mb-1">🌐 بوابة بيانات OpenBB</h2>
            <p className="text-purple-300 text-sm">
              مركز البيانات المالي المتكامل — أسعار حقيقية، مؤشرات اقتصادية كلية، ونسب التحليل الأساسي للشركات.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-xl text-xs font-bold border ${
              apiOffline 
                ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400' 
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            }`}>
              {apiOffline ? '⚠️ بيئة تجريبية (Fallback Mode)' : '🟢 اتصال نشط بـ OpenBB'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Left (Historical prices chart), Right (Fundamentals & Search) */}
      <div className="grid lg:grid-cols-3 gap-6">
        
        {/* Historical Price Chart Card (Span 2) */}
        <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
          <div className="flex justify-between items-center flex-wrap gap-3 mb-6">
            <div>
              <h3 className="text-xl font-bold text-white mb-1">📈 مخطط الأسعار التاريخية</h3>
              <p className="text-xs text-gray-400">أسعار الإغلاق التاريخية ومستويات OHLCV</p>
            </div>
            
            <div className="flex items-center gap-2">
              <select 
                value={selectedSymbol} 
                onChange={(e) => setSelectedSymbol(e.target.value)}
                className="bg-black/40 border border-white/10 text-white rounded-xl text-xs px-3 py-1.5 focus:outline-none focus:border-purple-400"
              >
                <option value="EURUSD">EUR/USD (يورو / دولار)</option>
                <option value="GBPUSD">GBP/USD (جنيه / دولار)</option>
                <option value="USDJPY">USD/JPY (دولار / ين)</option>
                <option value="AUDUSD">AUD/USD (أسترالي / دولار)</option>
                <option value="USDCAD">USD/CAD (دولار / كندي)</option>
                <option value="AAPL">Apple (AAPL)</option>
                <option value="MSFT">Microsoft (MSFT)</option>
                <option value="BTC-USD">Bitcoin (BTC-USD)</option>
              </select>

              <select 
                value={historicalDays} 
                onChange={(e) => setHistoricalDays(e.target.value)}
                className="bg-black/40 border border-white/10 text-white rounded-xl text-xs px-3 py-1.5 focus:outline-none focus:border-purple-400"
              >
                <option value="2026-01-01">منذ بداية 2026</option>
                <option value="2025-01-01">منذ بداية 2025</option>
                <option value="2024-01-01">آخر سنتين</option>
              </select>
            </div>
          </div>

          {/* SVG Line/Area Chart */}
          <div className="h-64 w-full bg-black/20 rounded-2xl p-4 border border-white/5 relative mb-4">
            {histLoading && (
              <div className="absolute inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center rounded-2xl">
                <span className="text-sm text-purple-300 animate-pulse">جاري سحب الأسعار التاريخية...</span>
              </div>
            )}
            
            <div className="h-full w-full">
              <svg viewBox="0 0 500 200" className="w-full h-full" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="rgba(168,85,247,0.4)" />
                    <stop offset="100%" stopColor="rgba(168,85,247,0)" />
                  </linearGradient>
                </defs>
                {/* Grid Lines */}
                <line x1="5" y1="50" x2="495" y2="50" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
                <line x1="5" y1="100" x2="495" y2="100" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
                <line x1="5" y1="150" x2="495" y2="150" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
                
                {currentHist.length >= 2 && (
                  <>
                    <path
                      d={drawAreaPath(currentHist, 'close', 500, 200)}
                      fill="url(#chartGrad)"
                    />
                    <path
                      d={drawLinePath(currentHist, 'close', 500, 200)}
                      fill="none"
                      stroke="#a855f7"
                      strokeWidth="2.5"
                    />
                  </>
                )}
              </svg>
            </div>
          </div>

          {/* OHLC Table summary */}
          <div className="overflow-x-auto rounded-xl border border-white/5">
            <table className="w-full text-right text-xs">
              <thead className="bg-white/5 text-gray-400 font-bold">
                <tr>
                  <th className="p-2">التاريخ</th>
                  <th className="p-2">الافتتاح</th>
                  <th className="p-2">الأعلى</th>
                  <th className="p-2">الأدنى</th>
                  <th className="p-2">الإغلاق</th>
                  <th className="p-2">الحجم</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-gray-300 font-mono">
                {currentHist.slice(-5).reverse().map((row, idx) => (
                  <tr key={idx} className="hover:bg-white/5">
                    <td className="p-2 text-gray-500">{row.date.split(' ')[0]}</td>
                    <td className="p-2">{row.open.toFixed(selectedSymbol.includes('JPY') || selectedSymbol.includes('AAPL') ? 2 : 5)}</td>
                    <td className="p-2 text-emerald-400">{row.high.toFixed(selectedSymbol.includes('JPY') || selectedSymbol.includes('AAPL') ? 2 : 5)}</td>
                    <td className="p-2 text-red-400">{row.low.toFixed(selectedSymbol.includes('JPY') || selectedSymbol.includes('AAPL') ? 2 : 5)}</td>
                    <td className="p-2 font-bold text-white">{row.close.toFixed(selectedSymbol.includes('JPY') || selectedSymbol.includes('AAPL') ? 2 : 5)}</td>
                    <td className="p-2 text-gray-400">{row.volume.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Fundamentals Metric Column (Span 1) */}
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">💎 التحليل الأساسي</h3>
            <p className="text-xs text-gray-400 mb-4">بيانات الميزانيات والنسب المالية للشركات</p>

            {/* Search Symbol Form */}
            <form onSubmit={handleSearchSubmit} className="flex gap-2 mb-6">
              <input
                type="text"
                placeholder="رموز الأسهم (مثل: TSLA, AAPL, MSFT)"
                value={searchEquity}
                onChange={(e) => setSearchEquity(e.target.value)}
                className="flex-1 bg-black/40 border border-white/10 text-white rounded-xl text-xs px-3 py-2 focus:outline-none focus:border-purple-400 uppercase font-mono"
              />
              <button 
                type="submit" 
                className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs px-4 py-2 rounded-xl transition-all"
              >
                بحث
              </button>
            </form>

            {/* Health Heuristic Block */}
            {currentFunds?.health_summary && (
              <div className="bg-indigo-500/10 border border-indigo-400/20 rounded-xl p-3 mb-4">
                <div className="text-indigo-400 text-xs font-bold mb-1">🔍 ملخص التقييم:</div>
                <div className="text-white text-xs leading-relaxed font-sans">{currentFunds.health_summary}</div>
              </div>
            )}

            {fundLoading && (
              <div className="text-center py-6 text-purple-300 animate-pulse text-xs">جاري سحب الميزانية والنسب المالية لـ {equitySymbol}...</div>
            )}

            {/* Metrics Ratios Grid */}
            <div className="grid grid-cols-2 gap-2 h-72 overflow-y-auto pr-1">
              {currentFunds?.ratios ? (
                Object.entries(currentFunds.ratios).map(([label, val]: [string, any], idx) => (
                  <div key={idx} className="bg-black/20 border border-white/5 rounded-xl p-3">
                    <div className="text-gray-500 text-[10px] truncate mb-1">{label}</div>
                    <div className="text-white font-mono font-bold text-sm">
                      {typeof val === 'number' ? val.toLocaleString(undefined, { maximumFractionDigits: 3 }) : val}
                    </div>
                  </div>
                ))
              ) : (
                <div className="col-span-2 text-center text-gray-600 py-6 text-xs">لا تتوفر نسب مالية حالياً</div>
              )}
            </div>
          </div>
          
          <div className="text-[10px] text-gray-500 text-center mt-4">
            المصدر: OpenBB Financial Fundamentals API ({currentFunds?.provider || 'yfinance'})
          </div>
        </div>

      </div>

      {/* Bottom Grid: Macro Indicators (2 columns) & Technical Analysis (1 column) */}
      <div className="grid lg:grid-cols-3 gap-6">
        
        {/* US Macro Indicators (Span 2) */}
        <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">📊 المؤشرات الكلية للاقتصاد الأمريكي</h3>
            <p className="text-xs text-gray-400 mb-6">مؤشرات الفيدرالي ومعدلات التضخم والبطالة من قاعدة بيانات (FRED)</p>

            {macroLoading && (
              <div className="text-center py-6 text-purple-300 animate-pulse text-xs">جاري سحب المؤشرات الاقتصادية الكبرى من FRED...</div>
            )}

            <div className="grid md:grid-cols-3 gap-4">
              {[
                { 
                  title: '💵 سعر فائدة الأموال الفيدرالية', 
                  fredKey: 'FEDFUNDS', 
                  desc: 'سعر الفائدة المرجعي لبنك الاحتياطي الفيدرالي وتكلفة التمويل البنكي.',
                  suffix: '%', 
                  color: 'text-emerald-400',
                  borderColor: 'border-emerald-500/20'
                },
                { 
                  title: '🎈 معدل التضخم السنوي (CPI)', 
                  fredKey: 'CPIAUCSL', 
                  desc: 'مؤشر أسعار المستهلكين لقياس سرعة زيادة تكلفة المعيشة الأساسية.',
                  suffix: '%', 
                  color: 'text-amber-400',
                  borderColor: 'border-amber-500/20'
                },
                { 
                  title: '💼 معدل البطالة الوطني', 
                  fredKey: 'UNRATE', 
                  desc: 'نسبة القوة العاملة العاطلة عن العمل وتبحث بنشاط عن فرص عمل.',
                  suffix: '%', 
                  color: 'text-rose-400',
                  borderColor: 'border-rose-500/20'
                }
              ].map((item, idx) => {
                const dataSeries = getMacro(item.fredKey as any);
                const latest = dataSeries.length > 0 ? dataSeries[dataSeries.length - 1] : null;
                // Get the value: it could be directly key or value
                const latestVal = latest ? parseFloat(String((latest as any)[item.fredKey] || Object.values(latest)[1] || 0)) : 0;
                
                return (
                  <div key={idx} className={`bg-black/20 border ${item.borderColor} rounded-2xl p-5 flex flex-col justify-between`}>
                    <div>
                      <div className="flex justify-between items-start mb-3">
                        <h4 className="text-white font-bold text-sm">{item.title}</h4>
                        <span className="text-gray-600 text-[10px] font-mono">{item.fredKey}</span>
                      </div>
                      <p className="text-gray-400 text-xs leading-relaxed mb-4">{item.desc}</p>
                    </div>

                    <div className="flex items-end justify-between mt-2">
                      <div>
                        <span className={`text-3xl font-black ${item.color}`}>{latestVal.toFixed(2)}{item.suffix}</span>
                        <div className="text-[10px] text-gray-600 mt-1 font-mono">آخر تحديث: {latest ? String(latest.date).split(' ')[0] : 'N/A'}</div>
                      </div>

                      {/* Micro sparkline */}
                      <div className="w-24 h-10">
                        <svg viewBox="0 0 100 40" className="w-full h-full" preserveAspectRatio="none">
                          {dataSeries.length >= 2 && (
                            <path
                              d={drawLinePath(dataSeries, item.fredKey, 100, 40)}
                              fill="none"
                              stroke={item.fredKey === 'FEDFUNDS' ? '#34d399' : item.fredKey === 'CPIAUCSL' ? '#fbbf24' : '#f87171'}
                              strokeWidth="2"
                            />
                          )}
                        </svg>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Currency Technical Analysis (Span 1) */}
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">📊 التحليل الفني للعملات</h3>
            <p className="text-xs text-gray-400 mb-6">المؤشرات الفنية الحية وتوصيات مجلس التصويت (مباشر)</p>

            {isForex ? (
              currentAnalysis ? (
                <div className="space-y-4">
                  {/* Recommended Action & Score */}
                  <div className="flex items-center justify-between p-4 rounded-2xl bg-black/30 border border-white/5">
                    <div>
                      <div className="text-[10px] text-gray-500 mb-1">الإجراء المقترح:</div>
                      <span className={`text-sm font-black px-3 py-1.5 rounded-xl border ${
                        currentAnalysis.voting?.direction === 'BUY'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                          : currentAnalysis.voting?.direction === 'SELL'
                          ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                          : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                      }`}>
                        {currentAnalysis.voting?.direction === 'BUY' ? 'شراء (BUY)' : 
                         currentAnalysis.voting?.direction === 'SELL' ? 'بيع (SELL)' : 'مراقبة (WATCH)'}
                      </span>
                    </div>
                    <div className="text-left">
                      <div className="text-[10px] text-gray-500 mb-1">قوة التوصية:</div>
                      <span className="text-lg font-mono font-bold text-white">
                        {currentAnalysis.voting?.confidence ? `${currentAnalysis.voting.confidence.toFixed(1)}%` : 'N/A'}
                      </span>
                    </div>
                  </div>

                  {/* Market Regime */}
                  <div className="p-3.5 rounded-2xl bg-purple-500/5 border border-purple-500/10 flex items-center justify-between">
                    <span className="text-xs text-purple-300">وضع هيكلية السوق (FSM):</span>
                    <span className="text-xs font-mono font-bold text-white bg-purple-500/20 px-2.5 py-1 rounded-lg">
                      {currentAnalysis.fsm?.regime || 'N/A'}
                    </span>
                  </div>

                  {/* Technical Indicators List */}
                  <div className="h-[210px] overflow-y-auto pr-1 space-y-1.5 font-mono text-xs">
                    {[
                      { label: 'RSI (7)', val: currentAnalysis.indicators?.rsi, type: 'oscillator' },
                      { label: 'EMA (50)', val: currentAnalysis.indicators?.ema, type: 'price' },
                      { label: 'MACD', val: currentAnalysis.indicators?.macd, type: 'oscillator_fine' },
                      { label: 'ADX (14)', val: currentAnalysis.indicators?.adx, type: 'strength' },
                      { label: 'ATR (14)', val: currentAnalysis.indicators?.atr, type: 'volatility' },
                      { label: 'Stochastic %K', val: currentAnalysis.indicators?.stoch_k, type: 'oscillator' },
                      { label: 'BB Upper', val: currentAnalysis.indicators?.bb_upper, type: 'price' },
                      { label: 'BB Lower', val: currentAnalysis.indicators?.bb_lower, type: 'price' },
                      { label: 'Ichimoku Tenkan', val: currentAnalysis.indicators?.tenkan, type: 'price' },
                      { label: 'Ichimoku Kijun', val: currentAnalysis.indicators?.kijun, type: 'price' },
                    ].map((ind, idx) => {
                      let formattedVal = 'N/A';
                      if (ind.val !== undefined && ind.val !== null) {
                        formattedVal = ind.type === 'price' ? ind.val.toFixed(5) : 
                                       ind.type === 'oscillator_fine' ? ind.val.toFixed(6) : 
                                       ind.val.toString();
                      }
                      return (
                        <div key={idx} className="flex justify-between items-center py-1.5 border-b border-white/5 hover:bg-white/5 px-2 rounded-lg transition-colors">
                          <span className="text-gray-400">{ind.label}</span>
                          <span className="text-white font-bold">{formattedVal}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs animate-pulse">
                  جاري جلب التحليل الفني الحي من الوكلاء...
                </div>
              )
            ) : (
              <div className="text-center py-12 bg-black/20 rounded-2xl p-4 border border-white/5">
                <span className="text-xl block mb-2">💡</span>
                <p className="text-xs text-gray-400 leading-relaxed">
                  التحليل الفني التلقائي متاح لأزواج العملات الأجنبية فقط (مثل: EUR/USD, GBP/USD). يرجى اختيار زوج عملات من قائمة المخطط لمشاهدة المؤشرات الفنية الحية.
                </p>
              </div>
            )}
          </div>
          
          <div className="text-[10px] text-gray-500 text-center mt-4 font-mono">
            آخر تحديث للوكيل: {currentAnalysis?.timestamp ? new Date(currentAnalysis.timestamp).toLocaleTimeString() : 'N/A'}
          </div>
        </div>

      </div>
    </div>
  );
}
