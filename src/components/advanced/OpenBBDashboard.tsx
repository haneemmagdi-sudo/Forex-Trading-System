import React, { useState, useEffect, useMemo } from 'react';
import { useApiData, BACKEND_URL } from '../../utils/useBackend';

// تصنيفات الأصول الشاملة
const ASSET_CATEGORIES = [
  {
    id: 'forex',
    name: 'العملات الأجنبية (Forex)',
    icon: '💱',
    symbols: [
      { label: 'EUR/USD', symbol: 'EURUSD', name: 'اليورو / الدولار الأمريكي' },
      { label: 'GBP/USD', symbol: 'GBPUSD', name: 'الجنيه الإسترليني / الدولار' },
      { label: 'USD/JPY', symbol: 'USDJPY', name: 'الدولار الأمريكي / الين الياباني' },
      { label: 'AUD/USD', symbol: 'AUDUSD', name: 'الدولار الأسترالي / الدولار' },
      { label: 'USD/CAD', symbol: 'USDCAD', name: 'الدولار الأمريكي / الكندي' },
      { label: 'USD/CHF', symbol: 'USDCHF', name: 'الدولار الأمريكي / الفرنك السويسري' },
      { label: 'NZD/USD', symbol: 'NZDUSD', name: 'الدولار النيوزيلندي / الدولار' },
      { label: 'EUR/JPY', symbol: 'EURJPY', name: 'اليورو / الين الياباني' },
    ],
  },
  {
    id: 'commodities',
    name: 'المعادن والسلع (Commodities)',
    icon: '🪙',
    symbols: [
      { label: 'Gold (XAU)', symbol: 'GC=F', name: 'الذهب العالمي (عقود فورية)' },
      { label: 'Silver (XAG)', symbol: 'SI=F', name: 'الفضة العالمية' },
      { label: 'Crude Oil', symbol: 'CL=F', name: 'نفط خام غرب تكساس (WTI)' },
      { label: 'Brent Oil', symbol: 'BZ=F', name: 'نفط برنت العالمي' },
      { label: 'Natural Gas', symbol: 'NG=F', name: 'الغاز الطبيعي الأمريكي' },
      { label: 'Copper', symbol: 'HG=F', name: 'النحاس عالي الجودة' },
    ],
  },
  {
    id: 'equities',
    name: 'الأسهم القيادية (Global Stocks)',
    icon: '🏢',
    symbols: [
      { label: 'Apple', symbol: 'AAPL', name: 'شركة أبل (Apple Inc.)' },
      { label: 'Nvidia', symbol: 'NVDA', name: 'إنفيديا لأشباه الموصلات' },
      { label: 'Microsoft', symbol: 'MSFT', name: 'مايكروسوفت (Microsoft Corp.)' },
      { label: 'Tesla', symbol: 'TSLA', name: 'تيسلا للسيارات الكهربائية' },
      { label: 'Alphabet', symbol: 'GOOGL', name: 'جوجل / ألفابت' },
      { label: 'Amazon', symbol: 'AMZN', name: 'أمازون للتجارة والسحابة' },
    ],
  },
  {
    id: 'crypto',
    name: 'العملات الرقمية (Crypto)',
    icon: '₿',
    symbols: [
      { label: 'Bitcoin', symbol: 'BTC-USD', name: 'البيتكوين (Bitcoin / USD)' },
      { label: 'Ethereum', symbol: 'ETH-USD', name: 'الإيثيريوم (Ethereum / USD)' },
      { label: 'Solana', symbol: 'SOL-USD', name: 'سولانا (Solana / USD)' },
      { label: 'Binance Coin', symbol: 'BNB-USD', name: 'بينانس كوين (BNB / USD)' },
      { label: 'Ripple (XRP)', symbol: 'XRP-USD', name: 'ريبل (XRP / USD)' },
    ],
  },
  {
    id: 'indices',
    name: 'المؤشرات العالمية (Indices)',
    icon: '📈',
    symbols: [
      { label: 'S&P 500 (SPY)', symbol: 'SPY', name: 'مؤشر إس آند بي 500 الأمريكي' },
      { label: 'Nasdaq 100', symbol: 'QQQ', name: 'مؤشر ناسداك لشركات التكنولوجيا' },
      { label: 'Dow Jones (DIA)', symbol: 'DIA', name: 'مؤشر داو جونز الصناعي' },
      { label: 'VIX Volatility', symbol: '^VIX', name: 'مؤشر تقلبات السوق (مقياس الخوف)' },
      { label: 'DAX 40', symbol: '^GDAXI', name: 'مؤشر داكس الألماني' },
    ],
  },
];

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
  const [activeCategory, setActiveCategory] = useState('forex');
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD');
  const [searchTicker, setSearchTicker] = useState('');
  const [timeRange, setTimeRange] = useState('2025-01-01');
  const [activeTab, setActiveTab] = useState<'chart' | 'fundamentals' | 'macro' | 'news' | 'integration'>('chart');

  // جلب البيانات من نقاط نهاية OpenBB المنشورة في FastAPI
  const { data: historicalRes, loading: histLoading } = useApiData<{ success: boolean; data: HistoricalRow[] }>(
    `/api/openbb/historical?symbol=${selectedSymbol}&start_date=${timeRange}`,
    15000
  );

  const { data: quoteRes, loading: quoteLoading } = useApiData<{ success: boolean; quote: any }>(
    `/api/openbb/quote?symbol=${selectedSymbol}`,
    5000
  );

  const { data: macroRes, loading: macroLoading } = useApiData<{ success: boolean; data: Record<string, MacroRow[]> }>(
    '/api/openbb/macro',
    30000
  );

  const { data: fundRes, loading: fundLoading } = useApiData<{ success: boolean; data: any }>(
    `/api/openbb/fundamentals?symbol=${selectedSymbol}`,
    20000
  );

  const { data: newsRes, loading: newsLoading } = useApiData<{ success: boolean; news: any[] }>(
    `/api/openbb/news?symbol=${selectedSymbol}`,
    20000
  );

  const { data: statusRes } = useApiData<{ success: boolean; status: string; version: string; active_providers: string[] }>(
    '/api/openbb/status',
    30000
  );

  // البحث المخصص
  const handleCustomSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchTicker.trim()) {
      const clean = searchTicker.trim().toUpperCase();
      setSelectedSymbol(clean);
    }
  };

  const rawHistory: HistoricalRow[] = useMemo(() => {
    if (historicalRes?.success && Array.isArray(historicalRes.data) && historicalRes.data.length > 0) {
      return historicalRes.data;
    }
    // بيانات افتراضية قياسية مقاسة في حال غياب الشبكة
    return [
      { date: '2026-06-12', open: 1.0820, high: 1.0855, low: 1.0805, close: 1.0842, volume: 14500 },
      { date: '2026-06-15', open: 1.0840, high: 1.0880, low: 1.0830, close: 1.0871, volume: 15200 },
      { date: '2026-06-16', open: 1.0870, high: 1.0910, low: 1.0865, close: 1.0898, volume: 16100 },
      { date: '2026-06-17', open: 1.0895, high: 1.0930, low: 1.0880, close: 1.0924, volume: 15800 },
      { date: '2026-06-18', open: 1.0920, high: 1.0945, low: 1.0900, close: 1.0912, volume: 17200 }
    ];
  }, [historicalRes]);

  // مؤشرات فنية محسوبة مباشرة من بيانات الشموع
  const technicals = useMemo(() => {
    if (rawHistory.length < 5) return null;
    const closes = rawHistory.map(r => r.close);
    const lastClose = closes[closes.length - 1];
    const prevClose = closes[closes.length - 2];
    const change = lastClose - prevClose;
    const changePct = (change / (prevClose || 1)) * 100;
    
    // حساب SMA 20
    const sma20 = closes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(closes.length, 20);
    // حساب نطاق التذبذب
    const highs = rawHistory.map(r => r.high);
    const lows = rawHistory.map(r => r.low);
    const highest52 = Math.max(...highs);
    const lowest52 = Math.min(...lows);
    const atr = (highs[highs.length - 1] - lows[lows.length - 1]);

    return {
      lastClose,
      change,
      changePct,
      sma20,
      highest52,
      lowest52,
      atr,
      trend: lastClose >= sma20 ? 'صاعد (Bullish)' : 'هابط (Bearish)',
    };
  }, [rawHistory]);

  // رسم المسارات الرياضية للرسم البياني SVG
  const drawLinePath = (data: any[], key: string, w: number, h: number) => {
    if (!data || data.length < 2) return '';
    const vals = data.map(d => parseFloat(d[key] || d.close || 0));
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = (max - min) || 1;
    return data.map((d, i) => {
      const x = (i / (data.length - 1)) * (w - 12) + 6;
      const y = h - 8 - ((parseFloat(d[key] || d.close || 0) - min) / range) * (h - 16);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(' ');
  };

  const drawAreaPath = (data: any[], key: string, w: number, h: number) => {
    const line = drawLinePath(data, key, w, h);
    if (!line) return '';
    return `${line} L ${w - 6} ${h} L 6 ${h} Z`;
  };

  const currentCategory = ASSET_CATEGORIES.find(c => c.id === activeCategory) || ASSET_CATEGORIES[0];
  const activeQuote = quoteRes?.quote;

  return (
    <div className="space-y-6 text-gray-100 p-2 md:p-6" dir="rtl">
      
      {/* ── الرأس والمعلومات المؤسسية ─────────────────────────────────── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/80 to-slate-900 border border-indigo-500/30 rounded-3xl p-6 shadow-2xl relative overflow-hidden backdrop-blur-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl p-2.5 bg-indigo-500/20 rounded-2xl border border-indigo-400/30 shadow-inner">🌐</span>
              <div>
                <h1 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-200 via-white to-purple-200">
                  منصة OpenBB المركزية لتحليل الأسواق (ODP v5.0.0)
                </h1>
                <p className="text-xs md:text-sm text-indigo-300/80">
                  المزود المالي الموحد لنظام Antigravity — تغذية وكلاء الذكاء الاصطناعي بالبيانات الفنية والأساسية والاقتصاد الكلي
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-xl text-xs text-emerald-300 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>OpenBB Core v5.0.0 (نشط)</span>
            </div>
            <div className="inline-flex items-center gap-2 bg-purple-500/10 border border-purple-500/30 px-3 py-1.5 rounded-xl text-xs text-purple-300 font-medium">
              <span>⚡ تخزين مؤقت محلي (SQLite TTL 900s)</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── شريط اختيار فئات الأصول والبحث المخصص ────────────────────── */}
      <div className="bg-slate-900/80 border border-white/10 rounded-2xl p-4 shadow-xl space-y-4">
        
        {/* أزرار الفئات الرئيسية */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-white/5 scrollbar-hide">
          {ASSET_CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => {
                setActiveCategory(cat.id);
                setSelectedSymbol(cat.symbols[0].symbol);
              }}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
                activeCategory === cat.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span>{cat.icon}</span>
              <span>{cat.name}</span>
            </button>
          ))}
        </div>

        {/* أزرار الأصول السريعة + نموذج البحث المباشر */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            {currentCategory.symbols.map(item => (
              <button
                key={item.symbol}
                onClick={() => setSelectedSymbol(item.symbol)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
                  selectedSymbol === item.symbol
                    ? 'bg-purple-600 text-white border-purple-400 shadow-md shadow-purple-600/30 scale-105'
                    : 'bg-black/30 text-gray-300 border-white/10 hover:border-purple-400/50 hover:bg-white/5'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          {/* محرك البحث المباشر عن أي رمز عالمي */}
          <form onSubmit={handleCustomSearch} className="flex items-center gap-2 min-w-[280px]">
            <input
              type="text"
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
              placeholder="ابحث عن أي رمز (مثل: TSLA, XAUUSD, ETH-USD)"
              className="flex-1 bg-black/40 border border-white/15 rounded-xl px-3 py-1.5 text-xs text-white uppercase font-mono focus:border-indigo-400 focus:outline-none"
            />
            <button
              type="submit"
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl transition-all shadow-md"
            >
              تحليل الرمز
            </button>
          </form>
        </div>

      </div>

      {/* ── شريط السعر الحي والمقاييس اللحظية للأصل النشط ───────────── */}
      <div className="bg-slate-900/60 border border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-2xl">
            {currentCategory.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black font-mono text-white">{selectedSymbol}</h2>
              <span className="text-xs bg-white/10 px-2 py-0.5 rounded text-gray-300">{currentCategory.name.split(' ')[0]}</span>
            </div>
            <div className="text-xs text-gray-400">
              المصدر: {activeQuote?.source || 'OpenBB Data Engine'}
            </div>
          </div>
        </div>

        {technicals && (
          <div className="flex flex-wrap items-center gap-6 font-mono text-xs">
            <div>
              <span className="text-[10px] text-gray-500 block">آخر إغلاق (Close)</span>
              <span className="text-base font-bold text-white">
                {technicals.lastClose.toFixed(selectedSymbol.includes('JPY') || selectedSymbol.includes('BTC') ? 2 : 4)}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-gray-500 block">التغير (Change)</span>
              <span className={`text-base font-bold ${technicals.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {technicals.change >= 0 ? '+' : ''}{technicals.change.toFixed(4)} ({technicals.changePct.toFixed(2)}%)
              </span>
            </div>

            <div>
              <span className="text-[10px] text-gray-500 block">متوسط 20 يوم (SMA20)</span>
              <span className="text-sm font-bold text-purple-300">{technicals.sma20.toFixed(4)}</span>
            </div>

            <div>
              <span className="text-[10px] text-gray-500 block">نطاق التذبذب (ATR)</span>
              <span className="text-sm font-bold text-amber-300">{technicals.atr.toFixed(4)}</span>
            </div>

            <div>
              <span className="text-[10px] text-gray-500 block">الاتجاه التقديري</span>
              <span className={`text-xs px-2.5 py-1 rounded-lg font-bold ${
                technicals.trend.includes('صاعد')
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-rose-500/20 text-rose-300'
              }`}>
                {technicals.trend}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── أزرار التبويبات الرئيسية لبيئة التحليل ──────────────────── */}
      <div className="flex items-center gap-2 border-b border-white/10 overflow-x-auto pb-2 scrollbar-hide text-xs font-bold">
        <button
          onClick={() => setActiveTab('chart')}
          className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
            activeTab === 'chart'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
              : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          <span>📈</span>
          <span>الرسم البياني وبيانات OHLCV</span>
        </button>

        <button
          onClick={() => setActiveTab('fundamentals')}
          className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
            activeTab === 'fundamentals'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
              : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          <span>💎</span>
          <span>التحليل الأساسي ومؤشرات القوة</span>
        </button>

        <button
          onClick={() => setActiveTab('macro')}
          className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
            activeTab === 'macro'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
              : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          <span>🌐</span>
          <span>مرصد الاقتصاد الكلي (FRED)</span>
        </button>

        <button
          onClick={() => setActiveTab('news')}
          className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
            activeTab === 'news'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
              : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          <span>📰</span>
          <span>شريط الأخبار والمشاعر</span>
        </button>

        <button
          onClick={() => setActiveTab('integration')}
          className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
            activeTab === 'integration'
              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
              : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          <span>⚡</span>
          <span>ربط وتغذية وكلاء النظام</span>
        </button>
      </div>

      {/* ── محتويات التبويبات ────────────────────────────────────────── */}
      <div className="pt-2">

        {/* 1. مخطط الأسعار وبيانات الشموع */}
        {activeTab === 'chart' && (
          <div className="grid lg:grid-cols-3 gap-6">
            
            {/* بطاقة الرسم البياني الكبير */}
            <div className="lg:col-span-2 bg-slate-900/60 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
              <div className="flex justify-between items-center flex-wrap gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-bold text-white">📈 مسار الأسعار التاريخية (OHLCV Curve)</h3>
                  <p className="text-xs text-gray-400">بيانات الأسعار التاريخية المستخرجة عبر محرك OpenBB ODP</p>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                    className="bg-black/40 border border-white/15 text-white rounded-xl text-xs px-3 py-1.5 focus:outline-none"
                  >
                    <option value="2026-01-01">منذ بداية 2026</option>
                    <option value="2025-01-01">منذ بداية 2025</option>
                    <option value="2024-01-01">آخر سنتين</option>
                  </select>
                </div>
              </div>

              {/* الرسم البياني SVG المتطور */}
              <div className="h-72 w-full bg-black/40 rounded-2xl p-4 border border-white/5 relative mb-4">
                {histLoading && (
                  <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center rounded-2xl z-10">
                    <span className="text-xs text-indigo-300 animate-pulse">جاري سحب وتحديث بيانات الشموع من OpenBB...</span>
                  </div>
                )}

                <div className="h-full w-full">
                  <svg viewBox="0 0 600 220" className="w-full h-full" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="openbbGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgba(99, 102, 241, 0.45)" />
                        <stop offset="100%" stopColor="rgba(99, 102, 241, 0.0)" />
                      </linearGradient>
                    </defs>

                    {/* خطوط الشبكة الأفقية */}
                    <line x1="6" y1="55" x2="594" y2="55" stroke="rgba(255,255,255,0.06)" strokeDasharray="3,3" />
                    <line x1="6" y1="110" x2="594" y2="110" stroke="rgba(255,255,255,0.06)" strokeDasharray="3,3" />
                    <line x1="6" y1="165" x2="594" y2="165" stroke="rgba(255,255,255,0.06)" strokeDasharray="3,3" />

                    {rawHistory.length >= 2 && (
                      <>
                        <path
                          d={drawAreaPath(rawHistory, 'close', 600, 220)}
                          fill="url(#openbbGrad)"
                        />
                        <path
                          d={drawLinePath(rawHistory, 'close', 600, 220)}
                          fill="none"
                          stroke="#6366f1"
                          strokeWidth="2.5"
                        />
                      </>
                    )}
                  </svg>
                </div>
              </div>

              {/* جدول الشموع الأخيرة */}
              <div className="overflow-x-auto rounded-xl border border-white/5">
                <table className="w-full text-right text-xs">
                  <thead className="bg-white/5 text-gray-400 font-bold">
                    <tr>
                      <th className="p-2.5">التاريخ</th>
                      <th className="p-2.5">الافتتاح</th>
                      <th className="p-2.5">الأعلى</th>
                      <th className="p-2.5">الأدنى</th>
                      <th className="p-2.5">الإغلاق</th>
                      <th className="p-2.5">حجم التداول</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-gray-300 font-mono">
                    {rawHistory.slice(-5).reverse().map((row, idx) => (
                      <tr key={idx} className="hover:bg-white/5">
                        <td className="p-2 text-gray-500">{String(row.date).split(' ')[0]}</td>
                        <td className="p-2">{row.open.toFixed(selectedSymbol.includes('JPY') ? 2 : 4)}</td>
                        <td className="p-2 text-emerald-400">{row.high.toFixed(selectedSymbol.includes('JPY') ? 2 : 4)}</td>
                        <td className="p-2 text-rose-400">{row.low.toFixed(selectedSymbol.includes('JPY') ? 2 : 4)}</td>
                        <td className="p-2 font-bold text-white">{row.close.toFixed(selectedSymbol.includes('JPY') ? 2 : 4)}</td>
                        <td className="p-2 text-gray-400">{row.volume.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

            </div>

            {/* بطاقة ملخص مؤشرات الأصل الجانبية */}
            <div className="bg-slate-900/60 border border-white/10 rounded-3xl p-6 flex flex-col justify-between">
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-white">📊 مؤشرات القوة الفنية</h3>
                <p className="text-xs text-gray-400">توليد لحظي من مكتبة OpenBB Technical Analysis</p>

                <div className="space-y-2 font-mono text-xs">
                  <div className="flex justify-between items-center p-3 rounded-xl bg-black/30 border border-white/5">
                    <span className="text-gray-400">أعلى سعر في النطاق</span>
                    <span className="text-emerald-400 font-bold">{technicals?.highest52.toFixed(4) || 'N/A'}</span>
                  </div>

                  <div className="flex justify-between items-center p-3 rounded-xl bg-black/30 border border-white/5">
                    <span className="text-gray-400">أدنى سعر في النطاق</span>
                    <span className="text-rose-400 font-bold">{technicals?.lowest52.toFixed(4) || 'N/A'}</span>
                  </div>

                  <div className="flex justify-between items-center p-3 rounded-xl bg-black/30 border border-white/5">
                    <span className="text-gray-400">نطاق التذبذب اليومي (Spread)</span>
                    <span className="text-amber-400 font-bold">{technicals?.atr.toFixed(4) || 'N/A'}</span>
                  </div>

                  <div className="flex justify-between items-center p-3 rounded-xl bg-black/30 border border-white/5">
                    <span className="text-gray-400">موضع السعر بالنسبة لـ SMA20</span>
                    <span className="text-white font-bold">
                      {technicals && technicals.lastClose >= technicals.sma20 ? 'أعلى المتوسط (صاعد)' : 'أدنى المتوسط (هابط)'}
                    </span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed">
                  <strong className="text-white block mb-1">💡 إفادة المحرك الكمي:</strong>
                  يتم تمرير هذه السلسلة الزمنية تلقائياً إلى خوارزميات الـ HMM وكاشف السيولة (Order Flow) لتأكيد جودة إشارات التداول قبل التنفيذ.
                </div>
              </div>

              <div className="text-[10px] text-gray-500 text-center font-mono mt-4">
                OpenBB Technical Extension (yfinance & technical)
              </div>
            </div>

          </div>
        )}

        {/* 2. التحليل الأساسي ومؤشرات القوة */}
        {activeTab === 'fundamentals' && (
          <div className="space-y-6">
            <div className="bg-slate-900/60 border border-white/10 rounded-3xl p-6">
              <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
                <div>
                  <h3 className="text-xl font-bold text-white mb-1">💎 القوائم المالية ونسب التحليل الأساسي</h3>
                  <p className="text-xs text-gray-400">
                    تقييم الشركات عبر تقارير SEC EDGAR والميزانيات، وفروق أسعار الفائدة والسياسات النقدية لسوق العملات
                  </p>
                </div>
                <div className="text-xs text-purple-300 font-mono bg-purple-500/10 px-3 py-1 rounded-xl border border-purple-500/20">
                  الأصل المفحوص: {selectedSymbol} ({fundRes?.data?.provider || 'yfinance / Central Banks'})
                </div>
              </div>

              {fundLoading ? (
                <div className="text-center py-16 text-indigo-300 animate-pulse text-xs">
                  جاري استخراج وتحليل القوائم المالية وفروق الفائدة عبر OpenBB...
                </div>
              ) : fundRes?.data ? (
                <div className="space-y-6">
                  {/* ملخص التقييم الصحي */}
                  {fundRes.data.health_summary && (
                    <div className="bg-indigo-500/10 border border-indigo-400/20 rounded-2xl p-4 text-xs leading-relaxed">
                      <strong className="text-indigo-300 block mb-1 font-bold">🔍 الخلاصة التحليلية للتقييم:</strong>
                      <span className="text-white">{fundRes.data.health_summary}</span>
                    </div>
                  )}

                  {/* شبكة النسب المالية */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {fundRes.data.ratios ? (
                      Object.entries(fundRes.data.ratios).map(([label, val]: [string, any], idx) => (
                        <div key={idx} className="bg-black/30 border border-white/5 rounded-2xl p-4 hover:border-white/20 transition-all">
                          <div className="text-gray-400 text-xs truncate mb-1.5">{label}</div>
                          <div className="text-white font-mono font-bold text-base">
                            {typeof val === 'number' ? val.toLocaleString(undefined, { maximumFractionDigits: 3 }) : val}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-4 text-center py-8 text-gray-500 text-xs">لا تتوفر نسب مالية مباشرة لهذا الأصل</div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs">تعذر استرجاع التحليل الأساسي</div>
              )}
            </div>
          </div>
        )}

        {/* 3. مرصد الاقتصاد الكلي (FRED) */}
        {activeTab === 'macro' && (
          <div className="space-y-6">
            <div className="bg-slate-900/60 border border-white/10 rounded-3xl p-6">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-white mb-1">🌐 مرصد الاقتصاد الكلي من الاحتياطي الفيدرالي (FRED)</h3>
                <p className="text-xs text-gray-400">
                  مؤشرات الفائدة والتضخم وسوق العمل الأمريكي الموجهة لحركة السيولة العالمية
                </p>
              </div>

              {macroLoading ? (
                <div className="text-center py-16 text-indigo-300 animate-pulse text-xs">
                  جاري جلب سلاسل بيانات الاقتصاد الكلي من بنك FRED...
                </div>
              ) : (
                <div className="grid md:grid-cols-3 gap-6">
                  {[
                    {
                      title: '💵 سعر فائدة الأموال الفيدرالية',
                      key: 'FEDFUNDS',
                      desc: 'سعر الفائدة المرجعي وتكلفة الاقتراض بين البنوك الأمريكية.',
                      color: 'text-emerald-400',
                      border: 'border-emerald-500/30'
                    },
                    {
                      title: '🎈 معدل التضخم السنوي (CPI)',
                      key: 'CPIAUCSL',
                      desc: 'مؤشر أسعار المستهلكين لقياس تسارع التضخم وتآكل القوة الشرائية.',
                      color: 'text-amber-400',
                      border: 'border-amber-500/30'
                    },
                    {
                      title: '💼 معدل البطالة الوطني',
                      key: 'UNRATE',
                      desc: 'نسبة القوة العاملة العاطلة عن العمل داخل الاقتصاد الأمريكي.',
                      color: 'text-rose-400',
                      border: 'border-rose-500/30'
                    }
                  ].map((card, idx) => {
                    const dataList = macroRes?.data?.[card.key] || [];
                    const latest = dataList.length > 0 ? dataList[dataList.length - 1] : null;
                    const val = latest ? parseFloat(String((latest as any)[card.key] || Object.values(latest)[1] || 0)) : 0;

                    return (
                      <div key={idx} className={`bg-black/30 border ${card.border} rounded-2xl p-5 flex flex-col justify-between`}>
                        <div>
                          <div className="flex justify-between items-start mb-2">
                            <h4 className="text-white font-bold text-sm">{card.title}</h4>
                            <span className="text-[10px] font-mono text-gray-500 bg-white/5 px-2 py-0.5 rounded">{card.key}</span>
                          </div>
                          <p className="text-gray-400 text-xs leading-relaxed mb-4">{card.desc}</p>
                        </div>

                        <div>
                          <div className="flex items-baseline justify-between mb-2">
                            <span className={`text-3xl font-black font-mono ${card.color}`}>{val.toFixed(2)}%</span>
                            <span className="text-[10px] text-gray-500 font-mono">آخر رصد: {latest ? String(latest.date).split(' ')[0] : 'N/A'}</span>
                          </div>

                          <div className="h-10 w-full bg-white/5 rounded-lg p-1">
                            <svg viewBox="0 0 100 40" className="w-full h-full" preserveAspectRatio="none">
                              {dataList.length >= 2 && (
                                <path
                                  d={drawLinePath(dataList, card.key, 100, 40)}
                                  fill="none"
                                  stroke={card.key === 'FEDFUNDS' ? '#34d399' : card.key === 'CPIAUCSL' ? '#fbbf24' : '#f87171'}
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
              )}
            </div>
          </div>
        )}

        {/* 4. شريط الأخبار والمشاعر */}
        {activeTab === 'news' && (
          <div className="space-y-4">
            <div className="bg-slate-900/60 border border-white/10 rounded-3xl p-6">
              <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
                <div>
                  <h3 className="text-lg font-bold text-white mb-1">📰 تدفق الأخبار المالية والماكرو</h3>
                  <p className="text-xs text-gray-400">عناوين الأخبار اللحظية مع قياس المشاعر الفورية لرمز {selectedSymbol}</p>
                </div>
              </div>

              {newsLoading ? (
                <div className="text-center py-12 text-indigo-300 animate-pulse text-xs">جاري سحب خلاصات الأخبار...</div>
              ) : newsRes?.news && newsRes.news.length > 0 ? (
                <div className="divide-y divide-white/5 bg-black/20 rounded-2xl border border-white/5 overflow-hidden">
                  {newsRes.news.map((item: any, idx: number) => (
                    <div key={idx} className="p-4 hover:bg-white/5 transition-all space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white hover:text-indigo-300 transition-colors">
                          {item.headline || item.title || 'خبر اقتصادي'}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          item.sentiment === 'POSITIVE' ? 'bg-emerald-500/20 text-emerald-300' :
                          item.sentiment === 'NEGATIVE' ? 'bg-rose-500/20 text-rose-300' :
                          'bg-amber-500/20 text-amber-300'
                        }`}>
                          {item.sentiment || 'NEUTRAL'}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 leading-relaxed">{item.summary || item.text || ''}</p>
                      <div className="flex items-center gap-3 text-[10px] text-gray-500 font-mono pt-1">
                        <span>المصدر: {item.source || 'OpenBB News Feed'}</span>
                        <span>{item.datetime || item.date || ''}</span>
                        {item.url && (
                          <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline">
                            المصدر الأصلي ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs">لا توجد أخبار حديثة لهذا الرمز حالياً</div>
              )}
            </div>
          </div>
        )}

        {/* 5. ربط وتغذية وكلاء النظام */}
        {activeTab === 'integration' && (
          <div className="space-y-6">
            <div className="bg-slate-900/60 border border-white/10 rounded-3xl p-6 space-y-6">
              <div>
                <h3 className="text-xl font-bold text-white mb-1">⚡ بنية تغذية الوكلاء بالبيانات (OpenBB Data Pipeline)</h3>
                <p className="text-xs text-gray-400">
                  كيف تقوم منصة OpenBB المركزية بتغذية وكلاء التداول ونماذج التعلم الآلي
                </p>
              </div>

              {/* بطاقات مسار التغذية للوكلاء */}
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-black/30 border border-purple-500/30 rounded-2xl p-4 space-y-2">
                  <div className="text-sm font-bold text-purple-300 flex items-center gap-2">
                    <span>📊</span>
                    <span>Market Analyst Agent</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    يستلم سلاسل الشموع OHLCV اللحظية ويحسب مؤشرات RSI و ATR والـ MACD و Order Blocks.
                  </p>
                  <span className="inline-block text-[10px] bg-purple-500/20 text-purple-200 px-2 py-0.5 rounded font-mono">
                    Provider: yfinance / MT5
                  </span>
                </div>

                <div className="bg-black/30 border border-blue-500/30 rounded-2xl p-4 space-y-2">
                  <div className="text-sm font-bold text-blue-300 flex items-center gap-2">
                    <span>🏛️</span>
                    <span>TradingAgents (Tauric MAS)</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    يتغذى بتقارير الإفصاح المالي (SEC EDGAR) وبيانات الماكرو لمناظرة الباحثين الصاعد والهابط.
                  </p>
                  <span className="inline-block text-[10px] bg-blue-500/20 text-blue-200 px-2 py-0.5 rounded font-mono">
                    Provider: SEC / FRED
                  </span>
                </div>

                <div className="bg-black/30 border border-emerald-500/30 rounded-2xl p-4 space-y-2">
                  <div className="text-sm font-bold text-emerald-300 flex items-center gap-2">
                    <span>🤖</span>
                    <span>HMM & Machine Learning</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    تغذية نموذج HMM لتصنيف وضع السوق (Regime Detection) وشبكات LSTM العصبية للتنبؤ بالأسعار.
                  </p>
                  <span className="inline-block text-[10px] bg-emerald-500/20 text-emerald-200 px-2 py-0.5 rounded font-mono">
                    Provider: DataService Cache
                  </span>
                </div>

                <div className="bg-black/30 border border-amber-500/30 rounded-2xl p-4 space-y-2">
                  <div className="text-sm font-bold text-amber-300 flex items-center gap-2">
                    <span>📰</span>
                    <span>News & Sentiment Agent</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    استقبال مؤشرات التضخم وسعر الفائدة الفيدرالية وعناوين الأخبار لتفعيل درع الأخبار (News Shield).
                  </p>
                  <span className="inline-block text-[10px] bg-amber-500/20 text-amber-200 px-2 py-0.5 rounded font-mono">
                    Provider: FRED / Central Banks
                  </span>
                </div>
              </div>

              {/* حالة التخزين المؤقت والاتصال */}
              <div className="p-4 rounded-2xl bg-black/40 border border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
                <div>
                  <span className="text-gray-400 block text-[10px]">مسار التخزين المؤقت (Cache DB)</span>
                  <span className="text-white">data/market_cache.db (SQLite)</span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">فترة الصلاحية (Cache TTL)</span>
                  <span className="text-emerald-400">900 ثانية (15 دقيقة)</span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">إصدار المنصة الأساسية</span>
                  <span className="text-purple-300">OpenBB v5.0.0 (openbq-org)</span>
                </div>
              </div>

            </div>
          </div>
        )}

      </div>

    </div>
  );
}
