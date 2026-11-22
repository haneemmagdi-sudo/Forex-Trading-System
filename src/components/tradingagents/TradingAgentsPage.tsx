import React, { useState, useEffect } from 'react';
import { TradingAgentsResult } from './types';
import { BACKEND_URL } from '../../utils/useBackend';

// رموز شائعة للوصول السريع
const QUICK_SYMBOLS = [
  { label: 'EUR/USD', symbol: 'EURUSD', type: 'forex', icon: '💶' },
  { label: 'GBP/USD', symbol: 'GBPUSD', type: 'forex', icon: '💷' },
  { label: 'USD/JPY', symbol: 'USDJPY', type: 'forex', icon: '💴' },
  { label: 'Gold (XAU)', symbol: 'XAUUSD', type: 'forex', icon: '🪙' },
  { label: 'Bitcoin', symbol: 'BTCUSD', type: 'crypto', icon: '₿' },
  { label: 'Ethereum', symbol: 'ETHUSD', type: 'crypto', icon: 'Ξ' },
  { label: 'Apple', symbol: 'AAPL', type: 'stock', icon: '🍎' },
  { label: 'Nvidia', symbol: 'NVDA', type: 'stock', icon: '🟢' },
  { label: 'S&P 500', symbol: 'SPY', type: 'index', icon: '📈' },
];

export default function TradingAgentsPage() {
  const [symbol, setSymbol] = useState('EURUSD');
  const [assetType, setAssetType] = useState('auto');
  const [tradeDate, setTradeDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [llmProvider, setLlmProvider] = useState('auto');
  const [debateRounds, setDebateRounds] = useState(1);
  const [activeTab, setActiveTab] = useState<'debate' | 'risk' | 'analysts' | 'history'>('debate');

  // حالات التنفيذ
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradingAgentsResult | null>(null);
  const [history, setHistory] = useState<TradingAgentsResult[]>([]);

  // حالة موافقة المستخدم لتنفيذ MT5 (Human-in-the-Loop)
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [customLot, setCustomLot] = useState('0.01');
  const [customSl, setCustomSl] = useState('');
  const [customTp, setCustomTp] = useState('');
  const [executingOnMt5, setExecutingOnMt5] = useState(false);
  const [executionResult, setExecutionResult] = useState<{
    success: boolean;
    ticket?: number;
    price?: number;
    note?: string;
    error?: string;
  } | null>(null);

  // جلب سجل التحليلات السابقة
  const fetchHistory = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/tradingagents/history`);
      const data = await res.json();
      if (data.success && Array.isArray(data.history)) {
        setHistory(data.history);
      }
    } catch (err) {
      console.warn('Failed to fetch history:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // تشغيل التحليل والمناظرة
  const handleAnalyze = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError(null);
    setExecutionResult(null);
    setShowApprovalModal(false);

    try {
      const res = await fetch(`${BACKEND_URL}/api/tradingagents/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: symbol.trim(),
          trade_date: tradeDate,
          asset_type: assetType,
          llm_provider: llmProvider,
          max_debate_rounds: Number(debateRounds),
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.error || 'فشل تشغيل تحليل TradingAgents');
      }

      setResult(data.result);
      // ضبط الإعدادات المسبقة لأمر MT5
      if (data.result.decision) {
        setCustomLot(String(data.result.decision.recommended_lot || '0.01'));
        setCustomSl(String(data.result.decision.suggested_sl || ''));
        setCustomTp(String(data.result.decision.suggested_tp || ''));
      }
      fetchHistory();
    } catch (err: any) {
      setError(err.message || 'حدث خطأ أثناء معالجة الطلب');
    } finally {
      setLoading(false);
    }
  };

  // تأكيد موافقة المستخدم على تنفيذ الأمر في MT5
  const handleExecuteApproval = async () => {
    if (!result) return;
    setExecutingOnMt5(true);
    setExecutionResult(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/tradingagents/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: result.mt5_symbol || result.ticker,
          direction: result.decision.action,
          lot_size: parseFloat(customLot) || 0.01,
          sl: customSl ? parseFloat(customSl) : null,
          tp: customTp ? parseFloat(customTp) : null,
          user_confirmed: true,
          comment: `TA-${result.decision.action}-Approved`,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        setExecutionResult({
          success: false,
          error: data.detail || data.error || 'فشل إرسال الصفقة إلى MT5',
        });
      } else {
        setExecutionResult({
          success: true,
          ticket: data.ticket,
          price: data.price,
          note: data.note || 'تم تنفيذ الأمر بنجاح على منصة MT5!',
        });
        setShowApprovalModal(false);
      }
    } catch (err: any) {
      setExecutionResult({
        success: false,
        error: err.message || 'حدث خطأ في الاتصال بالخادم',
      });
    } finally {
      setExecutingOnMt5(false);
    }
  };

  return (
    <div className="space-y-6 text-gray-100 p-2 md:p-6" dir="rtl">
      
      {/* ── العنوان والشعار ────────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-purple-950/80 via-slate-900/90 to-blue-950/80 border border-purple-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden backdrop-blur-xl">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-purple-400 to-transparent" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl p-2 bg-purple-500/20 rounded-xl border border-purple-400/30 shadow-inner">🏛️</span>
              <div>
                <h1 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-200 via-white to-pink-200">
                  شركة تداول TradingAgents (Tauric Research)
                </h1>
                <p className="text-xs md:text-sm text-purple-300/80">
                  إطار عمل ذكاء اصطناعي متعدد الوكلاء مبني فوق LangGraph يحاكي طاقم استثماري متكامل دون استشراف للمستقبل
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-xl text-xs text-emerald-300 font-medium shadow-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>🛡️ حماية Anti-Lookahead مفعلة</span>
            </div>
            <div className="inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 rounded-xl text-xs text-amber-300 font-medium">
              <span>👤 موافقة المستخدم مطلوبة للتنفيذ</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── شريط الإدخال والتحكم ──────────────────────────────────── */}
      <div className="bg-slate-900/70 border border-purple-500/20 rounded-2xl p-5 shadow-xl backdrop-blur-md space-y-4">
        
        {/* أزرار سريعة للأصول الشائعة */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-gray-400 ml-2">أصول سريعة:</span>
          {QUICK_SYMBOLS.map((item) => (
            <button
              key={item.symbol}
              onClick={() => {
                setSymbol(item.symbol);
                setAssetType(item.type);
              }}
              className={`px-3 py-1 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 border ${
                symbol === item.symbol
                  ? 'bg-purple-600 text-white border-purple-400 shadow-md shadow-purple-600/30 scale-105'
                  : 'bg-black/30 text-gray-300 border-white/10 hover:border-purple-400/50 hover:bg-white/5'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        {/* حقول الإدخال والاختيار */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          
          {/* اسم الأصل / الرمز */}
          <div className="md:col-span-2 space-y-1">
            <label className="text-xs font-semibold text-purple-300">رمز الأصل المالي (سهم / عملات / كريبتو / مؤشر)</label>
            <div className="relative">
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="مثال: EURUSD, AAPL, BTCUSD, SPY"
                className="w-full bg-black/40 border border-white/15 rounded-xl px-4 py-2.5 text-white font-mono uppercase focus:border-purple-400 focus:outline-none transition-all placeholder-gray-600 shadow-inner"
              />
            </div>
          </div>

          {/* فئة الأصل */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-purple-300">فئة الأصل</label>
            <select
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2.5 text-white text-sm focus:border-purple-400 focus:outline-none transition-all"
            >
              <option value="auto">تلقائي (Auto-Detect)</option>
              <option value="forex">فوركس (Forex)</option>
              <option value="stock">أسهم (Stocks)</option>
              <option value="crypto">عملات رقمية (Crypto)</option>
              <option value="index">مؤشرات مالية (Index)</option>
            </select>
          </div>

          {/* تاريخ التداول (Anti-Lookahead) */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-purple-300">تاريخ التحليل (قفل البيانات)</label>
            <input
              type="date"
              value={tradeDate}
              max={new Date().toISOString().split('T')[0]}
              onChange={(e) => setTradeDate(e.target.value)}
              className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white text-sm focus:border-purple-400 focus:outline-none transition-all"
            />
          </div>

          {/* زر تشغيل التحليل */}
          <div className="space-y-1 flex flex-col justify-end">
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className={`w-full py-2.5 px-4 rounded-xl font-bold text-sm shadow-lg transition-all flex items-center justify-center gap-2 ${
                loading
                  ? 'bg-purple-900/60 text-purple-300 cursor-wait border border-purple-500/30'
                  : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-purple-600/30 hover:scale-[1.02] active:scale-95'
              }`}
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>انعقاد المجلس والوكلاء...</span>
                </>
              ) : (
                <>
                  <span>🚀</span>
                  <span>بدء التحليل المؤسسي</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* إعدادات متقدمة اختيارية */}
        <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-white/5 text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <span>مزود الذكاء الاصطناعي:</span>
            <select
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              className="bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
            >
              <option value="auto">تلقائي (Gemini / OpenAI / Groq)</option>
              <option value="google">Google Gemini</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span>جولات المناظرة بين الباحثين:</span>
            <select
              value={debateRounds}
              onChange={(e) => setDebateRounds(Number(e.target.value))}
              className="bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
            >
              <option value={1}>جولة واحدة (سريع)</option>
              <option value={2}>جولتان (متعمق)</option>
              <option value={3}>3 جولات (شامل)</option>
            </select>
          </div>

          <div className="mr-auto text-purple-300/80 text-[11px]">
            * النظام لا ينفذ أوامر تلقائياً؛ يمكنك مراجعة النتيجة ثم الضغط على زر الموافقة اليدوية للتنفيذ في MT5.
          </div>
        </div>
      </div>

      {/* رسالة الخطأ إن وُجدت */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-sm flex items-center gap-3">
          <span className="text-xl">⚠️</span>
          <div>
            <div className="font-bold">تنبيه أثناء معالجة التحليل:</div>
            <div>{error}</div>
          </div>
        </div>
      )}

      {/* إشعار نتيجة التنفيذ على MT5 إن وُجدت */}
      {executionResult && (
        <div
          className={`border rounded-xl p-4 text-sm flex items-center justify-between gap-4 transition-all ${
            executionResult.success
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200'
              : 'bg-red-950/60 border-red-500/40 text-red-200'
          }`}
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">{executionResult.success ? '🎉' : '❌'}</span>
            <div>
              <div className="font-bold text-base">
                {executionResult.success ? 'تم إرسال الأمر بنجاح إلى منصة MetaTrader 5' : 'تعذر التنفيذ على منصة MT5'}
              </div>
              <div className="text-xs opacity-90">
                {executionResult.note || executionResult.error}
                {executionResult.ticket && ` | رقم التذكرة (Ticket): #${executionResult.ticket}`}
                {executionResult.price && ` | سعر التنفيذ: ${executionResult.price}`}
              </div>
            </div>
          </div>
          <button
            onClick={() => setExecutionResult(null)}
            className="text-xs px-2.5 py-1 bg-white/10 hover:bg-white/20 rounded-lg"
          >
            إغلاق
          </button>
        </div>
      )}

      {/* ── مراحل خط سير الوكلاء (Workflow Pipeline) ────────────────── */}
      <div className="bg-slate-900/40 border border-white/10 rounded-2xl p-4 backdrop-blur-sm">
        <div className="text-xs font-semibold text-gray-400 mb-3">مراحل التدفق المؤسسي (TradingAgents Pipeline):</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          
          <div className={`p-3 rounded-xl border flex items-center gap-2.5 ${
            loading ? 'bg-purple-500/20 border-purple-500/40 animate-pulse' : (result ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-black/20 border-white/5 text-gray-400')
          }`}>
            <span className="text-lg">📊</span>
            <div>
              <div className="text-xs font-bold text-white">1. فريق المحللين</div>
              <div className="text-[10px]">فني · أساسي · أخبار · مشاعر</div>
            </div>
          </div>

          <div className={`p-3 rounded-xl border flex items-center gap-2.5 ${
            loading ? 'bg-purple-500/10 border-purple-500/30' : (result ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-black/20 border-white/5 text-gray-400')
          }`}>
            <span className="text-lg">🐂</span>
            <div>
              <div className="text-xs font-bold text-white">2. مناظرة الثور والدب</div>
              <div className="text-[10px]">حوار علمي ونقد متبادل للأدلة</div>
            </div>
          </div>

          <div className={`p-3 rounded-xl border flex items-center gap-2.5 ${
            loading ? 'bg-purple-500/10 border-purple-500/30' : (result ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-black/20 border-white/5 text-gray-400')
          }`}>
            <span className="text-lg">🛡️</span>
            <div>
              <div className="text-xs font-bold text-white">3. إدارة المخاطر</div>
              <div className="text-[10px]">تدقيق السيولة ومؤشر التذبذب</div>
            </div>
          </div>

          <div className={`p-3 rounded-xl border flex items-center gap-2.5 ${
            loading ? 'bg-purple-500/10 border-purple-500/30' : (result ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-black/20 border-white/5 text-gray-400')
          }`}>
            <span className="text-lg">🎯</span>
            <div>
              <div className="text-xs font-bold text-white">4. مدير المحفظة</div>
              <div className="text-[10px]">القرار النهائي والتسعير المقترح</div>
            </div>
          </div>

        </div>
      </div>

      {/* ── بطاقة النتيجة والقرار النهائي (Hero Verdict Card) ───────── */}
      {result && (
        <div className="bg-gradient-to-br from-slate-900 via-purple-950/40 to-slate-900 border border-purple-500/30 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
          
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-white/10">
            
            {/* الشارة الكبرى للقرار */}
            <div className="flex items-center gap-4">
              <div
                className={`w-20 h-20 rounded-2xl flex items-center justify-center text-4xl shadow-2xl border ${
                  result.decision.action === 'BUY'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-emerald-500/30'
                    : result.decision.action === 'SELL'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-rose-500/30'
                    : 'bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-amber-500/30'
                }`}
              >
                {result.decision.action === 'BUY' ? '📈' : result.decision.action === 'SELL' ? '📉' : '⚖️'}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-white/10 text-gray-300">
                    {result.ticker} ({result.asset_type})
                  </span>
                  <span className="text-xs text-purple-300">تاريخ: {result.trade_date}</span>
                </div>

                <div className="text-3xl font-black mt-1 flex items-center gap-3">
                  <span
                    className={
                      result.decision.action === 'BUY'
                        ? 'text-emerald-400'
                        : result.decision.action === 'SELL'
                        ? 'text-rose-400'
                        : 'text-amber-400'
                    }
                  >
                    {result.decision.action === 'BUY'
                      ? 'شراء (BUY)'
                      : result.decision.action === 'SELL'
                      ? 'بيع (SELL)'
                      : 'تريث ومراقبة (HOLD)'}
                  </span>
                  <span className="text-sm font-normal text-gray-400 bg-black/40 px-3 py-1 rounded-full border border-white/5">
                    درجة القناعة: {result.decision.conviction}%
                  </span>
                </div>

                <p className="text-xs text-gray-400 mt-1 max-w-xl">
                  {result.decision.rationale}
                </p>
              </div>
            </div>

            {/* بطاقة المستويات السعرية وزر موافقة المستخدم */}
            <div className="flex flex-col sm:flex-row md:flex-col items-end gap-3 justify-center">
              
              <div className="flex items-center gap-4 bg-black/40 px-4 py-2.5 rounded-xl border border-white/10 text-xs font-mono">
                {result.current_price && (
                  <div>
                    <span className="text-gray-400 block text-[10px]">السعر الحالي</span>
                    <span className="font-bold text-white">{result.current_price}</span>
                  </div>
                )}
                {result.decision.suggested_sl && (
                  <div>
                    <span className="text-rose-400 block text-[10px]">وقف الخسارة (SL)</span>
                    <span className="font-bold text-rose-300">{result.decision.suggested_sl}</span>
                  </div>
                )}
                {result.decision.suggested_tp && (
                  <div>
                    <span className="text-emerald-400 block text-[10px]">جني الأرباح (TP)</span>
                    <span className="font-bold text-emerald-300">{result.decision.suggested_tp}</span>
                  </div>
                )}
              </div>

              {/* زر طلب موافقة المستخدم للتنفيذ على MT5 */}
              {result.decision.action !== 'HOLD' && (
                <button
                  onClick={() => setShowApprovalModal(true)}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-600/30 transition-all flex items-center justify-center gap-2 hover:scale-105 active:scale-95"
                >
                  <span>⚡</span>
                  <span>موافقة وتنفيذ الصفقة على منصة MT5</span>
                </button>
              )}

            </div>
          </div>

          {/* ── صندوق تأكيد موافقة المستخدم (Human-in-the-Loop Confirmation Modal / Card) ── */}
          {showApprovalModal && (
            <div className="mt-4 p-5 rounded-2xl bg-black/60 border-2 border-emerald-500/40 shadow-2xl backdrop-blur-xl animate-fade-in space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">⚠️</span>
                  <span className="font-bold text-base text-emerald-300">
                    طلب موافقة المستخدم للتنفيذ على MetaTrader 5
                  </span>
                </div>
                <button
                  onClick={() => setShowApprovalModal(false)}
                  className="text-gray-400 hover:text-white text-sm"
                >
                  ✕ إلغاء
                </button>
              </div>

              <p className="text-xs text-gray-300 leading-relaxed">
                أصدر وكلاء TradingAgents إشارة <strong className="text-white">[{result.decision.action}]</strong> لرمز{' '}
                <strong className="text-purple-300 font-mono">{result.mt5_symbol || result.ticker}</strong>. بصفتك صاحب الحساب، يرجى مراجعة إعدادات الأمر أدناه والموافقة قبل إرسال الصفقة إلى MT5:
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">حجم العقد (Lot Size):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={customLot}
                    onChange={(e) => setCustomLot(e.target.value)}
                    className="w-full bg-slate-900 border border-white/20 rounded-xl px-3 py-1.5 text-white font-mono text-sm focus:border-emerald-400 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-1">وقف الخسارة (Stop Loss):</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customSl}
                    onChange={(e) => setCustomSl(e.target.value)}
                    className="w-full bg-slate-900 border border-white/20 rounded-xl px-3 py-1.5 text-white font-mono text-sm focus:border-rose-400 focus:outline-none"
                    placeholder="اختياري"
                  />
                </div>

                <div>
                  <label className="text-xs text-gray-400 block mb-1">جني الأرباح (Take Profit):</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={customTp}
                    onChange={(e) => setCustomTp(e.target.value)}
                    className="w-full bg-slate-900 border border-white/20 rounded-xl px-3 py-1.5 text-white font-mono text-sm focus:border-emerald-400 focus:outline-none"
                    placeholder="اختياري"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowApprovalModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-white/5 hover:bg-white/10 text-gray-300 transition-all"
                >
                  إلغاء وتجاهل
                </button>

                <button
                  onClick={handleExecuteApproval}
                  disabled={executingOnMt5}
                  className="px-6 py-2 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/40 transition-all flex items-center gap-2"
                >
                  {executingOnMt5 ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>جاري التنفيذ على MT5...</span>
                    </>
                  ) : (
                    <>
                      <span>✅</span>
                      <span>أوافق صراحةً — أرسل الأمر إلى MT5</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ── أزرار التبويبات التفصيلية ──────────────────────────── */}
          <div className="flex items-center gap-2 mt-6 border-b border-white/10 overflow-x-auto pb-2 scrollbar-hide text-xs font-semibold">
            <button
              onClick={() => setActiveTab('debate')}
              className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'debate'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span>🐂 vs 🐻</span>
              <span>مناظرة الثور الصاعد والدب الهابط</span>
            </button>

            <button
              onClick={() => setActiveTab('risk')}
              className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'risk'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span>🛡️</span>
              <span>لجنة إدارة المخاطر</span>
            </button>

            <button
              onClick={() => setActiveTab('analysts')}
              className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'analysts'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span>📊</span>
              <span>تقارير المحللين الأربعة</span>
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${
                activeTab === 'history'
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span>📜</span>
              <span>الأرشيف وسجل التحليلات</span>
            </button>
          </div>

          {/* ── محتويات التبويبات ──────────────────────────────────── */}
          <div className="pt-4">
            
            {/* 1. مناظرة الثيران والدببة */}
            {activeTab === 'debate' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* الباحث الصاعد */}
                  <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-xl p-4 space-y-2">
                    <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                      <span>🐂</span>
                      <span>الباحث الصاعد (Bullish Researcher)</span>
                    </div>
                    {result.debate.bull_history.map((text, i) => (
                      <p key={i} className="text-xs text-gray-300 leading-relaxed bg-black/30 p-3 rounded-lg border border-white/5">
                        {text}
                      </p>
                    ))}
                  </div>

                  {/* الباحث الهابط */}
                  <div className="bg-rose-950/20 border border-rose-500/20 rounded-xl p-4 space-y-2">
                    <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                      <span>🐻</span>
                      <span>الباحث الهابط (Bearish Researcher)</span>
                    </div>
                    {result.debate.bear_history.map((text, i) => (
                      <p key={i} className="text-xs text-gray-300 leading-relaxed bg-black/30 p-3 rounded-lg border border-white/5">
                        {text}
                      </p>
                    ))}
                  </div>
                </div>

                {result.debate.consensus && (
                  <div className="bg-slate-900/60 border border-purple-500/20 rounded-xl p-3 text-xs text-purple-200">
                    <strong className="text-white block mb-1">خلاصة المناظرة وتوافق الآراء:</strong>
                    {result.debate.consensus}
                  </div>
                )}
              </div>
            )}

            {/* 2. لجنة إدارة المخاطر */}
            {activeTab === 'risk' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900/50 border border-blue-500/20 rounded-xl p-4 space-y-2">
                  <div className="text-blue-400 font-bold text-xs flex items-center gap-2">
                    <span>🛡️</span>
                    <span>المحاور المتشدد (Conservative)</span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed bg-black/20 p-2.5 rounded-lg">
                    {result.risk_management.conservative}
                  </p>
                </div>

                <div className="bg-slate-900/50 border border-amber-500/20 rounded-xl p-4 space-y-2">
                  <div className="text-amber-400 font-bold text-xs flex items-center gap-2">
                    <span>⚖️</span>
                    <span>المحاور المحايد (Neutral)</span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed bg-black/20 p-2.5 rounded-lg">
                    {result.risk_management.neutral}
                  </p>
                </div>

                <div className="bg-slate-900/50 border border-red-500/20 rounded-xl p-4 space-y-2">
                  <div className="text-rose-400 font-bold text-xs flex items-center gap-2">
                    <span>⚡</span>
                    <span>المحاور الجريء (Aggressive)</span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed bg-black/20 p-2.5 rounded-lg">
                    {result.risk_management.aggressive}
                  </p>
                </div>
              </div>
            )}

            {/* 3. تقارير المحللين الأربعة */}
            {activeTab === 'analysts' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-900/60 border border-white/10 rounded-xl p-4 space-y-2">
                  <div className="text-xs font-bold text-purple-300 flex items-center gap-2">
                    <span>📈</span>
                    <span>المحلل الفني (Technical Analyst)</span>
                  </div>
                  <div className="text-xs text-gray-300 whitespace-pre-line leading-relaxed font-mono bg-black/30 p-3 rounded-lg">
                    {result.analyst_reports.market}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-white/10 rounded-xl p-4 space-y-2">
                  <div className="text-xs font-bold text-purple-300 flex items-center gap-2">
                    <span>🏢</span>
                    <span>المحلل الأساسي (Fundamentals Analyst)</span>
                  </div>
                  <div className="text-xs text-gray-300 leading-relaxed bg-black/30 p-3 rounded-lg">
                    {result.analyst_reports.fundamentals}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-white/10 rounded-xl p-4 space-y-2">
                  <div className="text-xs font-bold text-purple-300 flex items-center gap-2">
                    <span>📰</span>
                    <span>محلل الأخبار (News Analyst)</span>
                  </div>
                  <div className="text-xs text-gray-300 leading-relaxed bg-black/30 p-3 rounded-lg">
                    {result.analyst_reports.news}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-white/10 rounded-xl p-4 space-y-2">
                  <div className="text-xs font-bold text-purple-300 flex items-center gap-2">
                    <span>🧠</span>
                    <span>محلل المشاعر والتدفق (Sentiment Analyst)</span>
                  </div>
                  <div className="text-xs text-gray-300 leading-relaxed bg-black/30 p-3 rounded-lg">
                    {result.analyst_reports.sentiment}
                  </div>
                </div>
              </div>
            )}

            {/* 4. سجل التحليلات السابقة */}
            {activeTab === 'history' && (
              <div className="space-y-3">
                {history.length === 0 ? (
                  <div className="text-center py-6 text-gray-500 text-xs">لا توجد سجلات سابقة بعد.</div>
                ) : (
                  <div className="divide-y divide-white/5 bg-black/30 rounded-xl border border-white/10 overflow-hidden">
                    {history.map((h, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          setResult(h);
                          setSymbol(h.ticker);
                        }}
                        className="p-3.5 hover:bg-white/5 cursor-pointer flex items-center justify-between transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              h.decision.action === 'BUY'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : h.decision.action === 'SELL'
                                ? 'bg-rose-500/20 text-rose-300'
                                : 'bg-amber-500/20 text-amber-300'
                            }`}
                          >
                            {h.decision.action}
                          </span>
                          <span className="font-mono font-bold text-sm text-white">{h.ticker}</span>
                          <span className="text-xs text-gray-400">({h.asset_type})</span>
                        </div>

                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          <span>قناعة: {h.decision.conviction}%</span>
                          <span>التاريخ: {h.trade_date}</span>
                          <span className="text-purple-400 hover:underline">عرض ◀</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>

        </div>
      )}

    </div>
  );
}
