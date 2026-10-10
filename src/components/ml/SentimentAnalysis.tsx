import { useState, useEffect, useRef } from 'react';
import { useApiData, NewsItem } from '../../utils/useBackend';

// ──────────────────────────────────────────────
// بيانات محاكاة Sentiment Analysis
// ──────────────────────────────────────────────
function useSentimentData() {
  const tick = useRef(0);
  const [state, setState] = useState({
    overallSentiment: 0.62,
    sentimentLabel: 'إيجابي',
    sentimentTrend: 'صاعد',
    newsFeed: [
      { time: '14:32', title: 'Fed يُشير إلى وقف رفع الفائدة في 2025', sentiment: 0.78, impact: 'HIGH', currency: 'USD', direction: 'BEARISH', source: 'Reuters', url: '' },
      { time: '14:15', title: 'بيانات التضخم الأوروبي تتراجع إلى 2.1%', sentiment: 0.71, impact: 'MEDIUM', currency: 'EUR', direction: 'BULLISH', source: 'Bloomberg', url: '' },
      { time: '13:58', title: 'مؤشر PMI البريطاني يفشل في التوقعات', sentiment: 0.28, impact: 'MEDIUM', currency: 'GBP', direction: 'BEARISH', source: 'FT', url: '' },
      { time: '13:42', title: 'بيانات التوظيف الأمريكي أفضل من المتوقع', sentiment: 0.85, impact: 'HIGH', currency: 'USD', direction: 'BULLISH', source: 'WSJ', url: '' },
      { time: '13:10', title: 'الين الياباني يتعرض لضغط مع ارتفاع العائدات', sentiment: 0.35, impact: 'LOW', currency: 'JPY', direction: 'BEARISH', source: 'Nikkei', url: '' },
      { time: '12:45', title: 'الذهب يرتفع مع تراجع الدولار', sentiment: 0.68, impact: 'MEDIUM', currency: 'XAU', direction: 'BULLISH', source: 'Kitco', url: '' },
    ],
    currencySentiment: {
      USD: { score: 0.61, label: 'إيجابي', trades: 24 },
      EUR: { score: 0.73, label: 'إيجابي جداً', trades: 18 },
      GBP: { score: 0.34, label: 'سلبي', trades: 15 },
      JPY: { score: 0.41, label: 'محايد', trades: 21 },
      AUD: { score: 0.58, label: 'إيجابي', trades: 12 },
      CHF: { score: 0.69, label: 'إيجابي', trades: 9 },
    },
    socialBuzz: [
      { platform: 'Twitter/X', mentions: 24820, bullish: 58, bearish: 32, icon: '🐦' },
      { platform: 'Reddit', mentions: 8340, bullish: 62, bearish: 28, icon: '🤖' },
      { platform: 'TradingView', mentions: 15600, bullish: 71, bearish: 19, icon: '📊' },
      { platform: 'Telegram', mentions: 6240, bullish: 54, bearish: 36, icon: '📱' },
    ],
    economicCalendar: [
      { time: '15:30', event: 'CPI (US)', importance: 'HIGH', forecast: '2.8%', previous: '3.1%', actual: '2.7%', impact: 'BULLISH' },
      { time: '16:00', event: 'Core PCE (US)', importance: 'HIGH', forecast: '2.6%', previous: '2.8%', actual: '—', impact: '?' },
      { time: '16:30', event: 'Initial Jobless Claims', importance: 'MEDIUM', forecast: '215K', previous: '218K', actual: '—', impact: '?' },
      { time: '18:00', event: 'ECB Speech', importance: 'HIGH', forecast: '—', previous: '—', actual: '—', impact: '?' },
    ],
    mlPrediction: { direction: 'BUY', confidence: 72, reasoning: 'إيجابية عالية + أخبار USD ضعيفة = EUR/USD صاعد' },
  });

  useEffect(() => {
    const interval = setInterval(() => {
      tick.current++;
      setState(s => ({
        ...s,
        overallSentiment: parseFloat((0.5 + Math.sin(tick.current * 0.3) * 0.3).toFixed(3)),
        sentimentLabel: s.overallSentiment > 0.6 ? 'إيجابي' : s.overallSentiment > 0.4 ? 'محايد' : 'سلبي',
        mlPrediction: {
          ...s.mlPrediction,
          confidence: Math.round(62 + Math.sin(tick.current * 0.4) * 15),
        },
      }));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return state;
}

// ──────────────────────────────────────────────
// Sentiment Gauge
// ──────────────────────────────────────────────
function SentimentGauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(1, score));
  const angle = -135 + pct * 270;

  const color = pct > 0.65 ? '#10b981' : pct > 0.40 ? '#f59e0b' : '#ef4444';

  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="90" viewBox="0 0 140 90">
        {/* Background arc */}
        <path
          d="M 20 80 A 50 50 0 1 1 120 80"
          fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="10" strokeLinecap="round"
        />
        {/* Colored arc */}
        <path
          d="M 20 80 A 50 50 0 1 1 120 80"
          fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${pct * 157} 157`}
          style={{ transition: 'stroke-dasharray 0.5s ease, stroke 0.3s ease' }}
        />
        {/* Needle */}
        <line
          x1="70" y1="80"
          x2={70 + 40 * Math.cos((angle - 90) * Math.PI / 180)}
          y2={80 + 40 * Math.sin((angle - 90) * Math.PI / 180)}
          stroke="white" strokeWidth="3" strokeLinecap="round"
          style={{ transition: 'all 0.5s ease' }}
        />
        <circle cx="70" cy="80" r="5" fill="white" />
      </svg>
      <div className="text-center -mt-2">
        <div className="text-3xl font-black" style={{ color }}>{(pct * 100).toFixed(0)}%</div>
        <div className="text-gray-400 text-sm">{pct > 0.65 ? 'تفاؤل 🟢' : pct > 0.4 ? 'محايد 🟡' : 'تشاؤم 🔴'}</div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
interface CalendarEvent {
  id: string;
  time: string;
  event: string;
  importance: 'HIGH' | 'MEDIUM' | 'LOW';
  forecast: string;
  previous: string;
  actual: string;
  impact: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  date: string;
  country: string;
  currency: string;
}

// Main Component
// ──────────────────────────────────────────────
export default function SentimentAnalysis() {
  const sData = useSentimentData();
  const { data: apiData } = useApiData<{ news: NewsItem[]; sentiment: Record<string, string>; social_buzz?: any[]; status: string }>('/api/news', 10000);
  const { data: apiCalendar } = useApiData<CalendarEvent[]>('/api/news/calendar', 30000);
  const [activeTab, setActiveTab] = useState<'news' | 'social' | 'calendar' | 'pairs'>('news');

  const processedNewsFeed = apiData?.news && apiData.news.length > 0
    ? apiData.news.map(item => {
        let timeStr = '—';
        if (item.datetime) {
          try {
            const dt = new Date(item.datetime);
            timeStr = dt.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit', hour12: false });
          } catch (e) {}
        }
        let score = 0.5;
        let direction = 'NEUTRAL';
        if (item.sentiment === 'POSITIVE') {
          score = 0.85;
          direction = 'BULLISH';
        } else if (item.sentiment === 'NEGATIVE') {
          score = 0.15;
          direction = 'BEARISH';
        }
        const currency = item.related_symbols && item.related_symbols.length > 0 ? item.related_symbols[0] : 'GEN';
        return {
          time: timeStr,
          title: item.headline_ar || item.headline,
          sentiment: score,
          impact: item.impact,
          currency: currency,
          direction: direction,
          source: item.source,
          url: item.url
        };
      })
    : sData.newsFeed;

  const positiveCount = apiData?.news ? apiData.news.filter(n => n.sentiment === 'POSITIVE').length : 0;
  const negativeCount = apiData?.news ? apiData.news.filter(n => n.sentiment === 'NEGATIVE').length : 0;
  const totalSent = positiveCount + negativeCount;
  const processedOverallSentiment = totalSent > 0 ? positiveCount / totalSent : sData.overallSentiment;

  const processedCurrencySentiment = { ...sData.currencySentiment };
  if (apiData?.sentiment) {
    Object.entries(apiData.sentiment).forEach(([currency, sent]) => {
      const code = currency.substring(0, 3).toUpperCase();
      if (code in processedCurrencySentiment) {
        const score = sent === 'BULLISH' ? 0.75 : sent === 'BEARISH' ? 0.25 : 0.5;
        const label = sent === 'BULLISH' ? 'إيجابي' : sent === 'BEARISH' ? 'سلبي' : 'محايد';
        processedCurrencySentiment[code as keyof typeof sData.currencySentiment] = {
          score,
          label,
          trades: processedCurrencySentiment[code as keyof typeof sData.currencySentiment].trades
        };
      }
    });
  }

  const todayStr = new Date().toDateString();
  let filteredCalendar = apiCalendar && apiCalendar.length > 0
    ? apiCalendar.filter(event => {
        if (!event.time) return false;
        try {
          return new Date(event.time).toDateString() === todayStr;
        } catch (e) {
          return false;
        }
      })
    : [];

  if (apiCalendar && apiCalendar.length > 0 && filteredCalendar.length === 0) {
    filteredCalendar = apiCalendar;
  }

  const processedCalendar = filteredCalendar.length > 0
    ? filteredCalendar.map(event => {
        let timeStr = '—';
        if (event.time) {
          try {
            const dt = new Date(event.time);
            timeStr = dt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });
          } catch (e) {}
        }
        const displayEvent = event.currency ? `${event.event} (${event.currency})` : event.event;
        return {
          ...event,
          event: displayEvent,
          time: timeStr
        };
      })
    : sData.economicCalendar;

  const s = {
    ...sData,
    overallSentiment: processedOverallSentiment,
    newsFeed: processedNewsFeed,
    currencySentiment: processedCurrencySentiment,
    economicCalendar: processedCalendar,
    socialBuzz: apiData?.social_buzz || sData.socialBuzz
  };

  const tabs = [
    { id: 'news', label: '📰 الأخبار' },
    { id: 'social', label: '📱 Social Media' },
    { id: 'calendar', label: '📅 التقويم' },
    { id: 'pairs', label: '💱 تحليل الأزواج' },
  ] as const;

  const impactColor = (imp: string) =>
    imp === 'HIGH' ? 'text-red-400 bg-red-500/20' :
    imp === 'MEDIUM' ? 'text-yellow-400 bg-yellow-500/20' :
    'text-gray-400 bg-gray-500/20';

  return (
    <div className="space-y-6" dir="rtl">

      {/* Hero */}
      <div className="bg-gradient-to-br from-cyan-600/20 via-teal-600/20 to-emerald-600/20 rounded-3xl p-8 border border-cyan-400/30 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(6,182,212,0.1),transparent)] pointer-events-none" />
        <div className="relative">
          <h2 className="text-4xl font-black text-white mb-3">🧠 تحليل المشاعر (Sentiment Analysis)</h2>
          <p className="text-cyan-200 text-lg mb-6">
            NLP + أخبار السوق + وسائل التواصل = فهم شامل لنفسية المتداولين
          </p>

          {/* Main Metrics */}
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-black/30 rounded-2xl p-5 text-center flex flex-col items-center">
              <div className="text-gray-400 text-sm mb-3">مؤشر المشاعر الكلي</div>
              <SentimentGauge score={s.overallSentiment} />
            </div>

            <div className="bg-black/30 rounded-2xl p-5">
              <div className="text-gray-400 text-sm mb-3">توزيع المشاعر</div>
              {[
                { label: 'إيجابي (Bullish)', pct: Math.round(s.overallSentiment * 100), color: 'bg-emerald-500' },
                { label: 'محايد (Neutral)', pct: 18, color: 'bg-yellow-500' },
                { label: 'سلبي (Bearish)', pct: Math.round((1 - s.overallSentiment) * 100) - 18, color: 'bg-red-500' },
              ].map((item, i) => (
                <div key={i} className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-400">{item.label}</span>
                    <span className="text-white font-bold">{Math.max(0, item.pct)}%</span>
                  </div>
                  <div className="h-2 bg-black/40 rounded-full overflow-hidden">
                    <div className={`h-full ${item.color} rounded-full transition-all duration-700`}
                      style={{ width: `${Math.max(0, item.pct)}%` }} />
                  </div>
                </div>
              ))}
            </div>

            {/* ML Prediction */}
            <div className={`rounded-2xl p-5 border-2 ${
              s.mlPrediction.direction === 'BUY'
                ? 'bg-emerald-500/10 border-emerald-400/50'
                : 'bg-red-500/10 border-red-400/50'
            }`}>
              <div className="text-gray-400 text-sm mb-2">🤖 تنبؤ نموذج Sentiment</div>
              <div className={`text-4xl font-black mb-2 ${s.mlPrediction.direction === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                {s.mlPrediction.direction}
              </div>
              <div className="h-2 bg-black/30 rounded-full overflow-hidden mb-2">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${s.mlPrediction.direction === 'BUY' ? 'bg-emerald-500' : 'bg-red-500'}`}
                  style={{ width: `${s.mlPrediction.confidence}%` }}
                />
              </div>
              <div className="text-gray-400 text-xs">ثقة: {s.mlPrediction.confidence}%</div>
              <div className="mt-3 text-gray-300 text-xs leading-relaxed">{s.mlPrediction.reasoning}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-shrink-0 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              activeTab === tab.id
                ? 'bg-cyan-500/30 text-cyan-300 border border-cyan-400/50'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── News Tab ── */}
      {activeTab === 'news' && (
        <div className="space-y-3">
          <h3 className="text-lg font-bold text-white">📰 تدفق الأخبار (Real-time NLP)</h3>
          {s.newsFeed.map((news, i) => {
            const sentPct = news.sentiment * 100;
            const sentColor = news.sentiment > 0.6 ? 'text-emerald-400' : news.sentiment > 0.4 ? 'text-yellow-400' : 'text-red-400';
            const sentBg = news.sentiment > 0.6 ? 'border-r-emerald-400' : news.sentiment > 0.4 ? 'border-r-yellow-400' : 'border-r-red-400';

            return (
              <div key={i} className={`bg-white/5 rounded-2xl p-5 border border-white/10 border-r-4 ${sentBg} hover:bg-white/8 transition-all`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="text-white font-semibold mb-1">{news.title}</div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-500">{news.time}</span>
                      <span className="text-gray-600">•</span>
                      <span className="text-gray-500">{news.source}</span>
                      {news.url && (
                        <>
                          <span className="text-gray-600">•</span>
                          <a
                            href={news.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan-400 hover:text-cyan-300 hover:underline transition-all inline-flex items-center gap-0.5"
                          >
                            رابط الخبر 🔗
                          </a>
                        </>
                      )}
                      <span className="text-gray-600">•</span>
                      <span className="text-purple-400 font-bold">{news.currency}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${impactColor(news.impact)}`}>
                        {news.impact}
                      </span>
                    </div>
                  </div>
                  <div className="text-center flex-shrink-0">
                    <div className={`text-2xl font-black ${sentColor}`}>
                      {sentPct.toFixed(0)}%
                    </div>
                    <div className={`text-xs font-bold ${news.direction === 'BULLISH' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {news.direction}
                    </div>
                  </div>
                </div>
                <div className="mt-3 h-1.5 bg-black/30 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${sentPct}%`,
                      background: news.sentiment > 0.6 ? '#10b981' : news.sentiment > 0.4 ? '#f59e0b' : '#ef4444'
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Social Media Tab ── */}
      {activeTab === 'social' && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-white">📱 تحليل وسائل التواصل الاجتماعي</h3>
          <div className="grid md:grid-cols-2 gap-4">
            {s.socialBuzz.map((platform, i) => (
              <div key={i} className="bg-white/5 rounded-2xl p-5 border border-white/10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-3xl">{platform.icon}</span>
                  <div>
                    <div className="text-white font-bold">{platform.platform}</div>
                    <div className="text-gray-500 text-xs">{platform.mentions.toLocaleString()} إشارة</div>
                  </div>
                </div>
                <div className="space-y-2">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-emerald-400">🟢 Bullish</span>
                      <span className="text-emerald-400 font-bold">{platform.bullish}%</span>
                    </div>
                    <div className="h-3 bg-black/30 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${platform.bullish}%` }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-500">⚪ Neutral</span>
                      <span className="text-gray-500 font-bold">{100 - platform.bullish - platform.bearish}%</span>
                    </div>
                    <div className="h-3 bg-black/30 rounded-full overflow-hidden">
                      <div className="h-full bg-gray-500 rounded-full" style={{ width: `${100 - platform.bullish - platform.bearish}%` }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-red-400">🔴 Bearish</span>
                      <span className="text-red-400 font-bold">{platform.bearish}%</span>
                    </div>
                    <div className="h-3 bg-black/30 rounded-full overflow-hidden">
                      <div className="h-full bg-red-500 rounded-full" style={{ width: `${platform.bearish}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Economic Calendar Tab ── */}
      {activeTab === 'calendar' && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-white">📅 التقويم الاقتصادي اليوم</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-white/10">
                  <th className="pb-3 text-right">الوقت</th>
                  <th className="pb-3 text-right">الحدث</th>
                  <th className="pb-3 text-center">الأهمية</th>
                  <th className="pb-3 text-center">التوقع</th>
                  <th className="pb-3 text-center">السابق</th>
                  <th className="pb-3 text-center">الفعلي</th>
                  <th className="pb-3 text-center">التأثير</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {s.economicCalendar.map((event, i) => (
                  <tr key={i} className={`hover:bg-white/3 transition-all ${event.actual !== '—' ? 'bg-white/2' : ''}`}>
                    <td className="py-3 text-white font-mono">{event.time}</td>
                    <td className="py-3">
                      <div className="text-white font-semibold">{event.event}</div>
                    </td>
                    <td className="py-3 text-center">
                      <span className={`px-2 py-1 rounded-full text-xs font-bold ${impactColor(event.importance)}`}>
                        {event.importance}
                      </span>
                    </td>
                    <td className="py-3 text-center text-gray-400 font-mono">{event.forecast}</td>
                    <td className="py-3 text-center text-gray-500 font-mono">{event.previous}</td>
                    <td className="py-3 text-center font-mono font-bold">
                      <span className={event.actual === '—' ? 'text-gray-600' : 'text-white'}>
                        {event.actual}
                      </span>
                    </td>
                    <td className="py-3 text-center">
                      <span className={`text-xs font-bold ${
                        event.impact === 'BULLISH' ? 'text-emerald-400' :
                        event.impact === 'BEARISH' ? 'text-red-400' : 'text-gray-500'
                      }`}>
                        {event.impact === 'BULLISH' ? '📈 صاعد' :
                         event.impact === 'BEARISH' ? '📉 هابط' : '⏳ منتظر'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Currency Pairs Tab ── */}
      {activeTab === 'pairs' && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-white">💱 مشاعر أزواج العملات (مقارنة نسبية)</h3>
          <p className="text-xs text-gray-400 mb-4">
            يتم حساب مشاعر الأزواج استناداً إلى فارق المشاعر النسبي بين العملة الأساسية وعملة المقابلة المستخلصة من الأخبار الحية.
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              { id: 'EURUSD', name: 'EUR/USD', desc: 'يورو / دولار أمريكي' },
              { id: 'GBPUSD', name: 'GBP/USD', desc: 'جنيه إسترليني / دولار أمريكي' },
              { id: 'USDJPY', name: 'USD/JPY', desc: 'دولار أمريكي / ين ياباني' },
              { id: 'AUDUSD', name: 'AUD/USD', desc: 'دولار أسترالي / دولار أمريكي' },
              { id: 'USDCAD', name: 'USD/CAD', desc: 'دولار أمريكي / دولار كندي' },
              { id: 'USDCHF', name: 'USD/CHF', desc: 'دولار أمريكي / فرنك سويسري' },
              { id: 'NZDUSD', name: 'NZD/USD', desc: 'دولار نيوزيلندي / دولار أمريكي' }
            ].map(pair => {
              const base = pair.id.substring(0, 3);
              const quote = pair.id.substring(3, 6);
              
              const baseData = s.currencySentiment[base as keyof typeof s.currencySentiment] || { score: 0.5, label: 'محايد', trades: 10 };
              const quoteData = s.currencySentiment[quote as keyof typeof s.currencySentiment] || { score: 0.5, label: 'محايد', trades: 10 };
              
              const pairScore = (baseData.score - quoteData.score + 1) / 2;
              
              const label = pairScore > 0.65 ? 'شراء قوي (Bullish)' :
                            pairScore > 0.55 ? 'شراء (Bullish)' :
                            pairScore >= 0.45 ? 'محايد (Neutral)' :
                            pairScore >= 0.35 ? 'بيع (Bearish)' : 'بيع قوي (Bearish)';
                            
              const sentColor = pairScore > 0.55 ? 'text-emerald-400' :
                                pairScore >= 0.45 ? 'text-yellow-400' : 'text-red-400';
                                
              const bg = pairScore > 0.55 ? 'bg-emerald-500' :
                         pairScore >= 0.45 ? 'bg-yellow-500' : 'bg-red-500';
                         
              const totalSignals = baseData.trades + quoteData.trades;

              return (
                <div key={pair.id} className="bg-white/5 rounded-2xl p-5 border border-white/10 flex flex-col justify-between hover:bg-white/8 transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-10 bg-gradient-to-br from-cyan-500 to-emerald-500 rounded-xl flex items-center justify-center font-black text-white text-xs">
                        {pair.name}
                      </div>
                      <div>
                        <div className="text-white font-bold">{pair.name}</div>
                        <div className="text-gray-500 text-[10px]">{pair.desc} • {totalSignals} مؤشر مشاعر</div>
                      </div>
                    </div>
                    <div className={`text-2xl font-black ${sentColor}`}>
                      {(pairScore * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="h-3 bg-black/30 rounded-full overflow-hidden">
                    <div className={`h-full ${bg} rounded-full transition-all duration-700`}
                      style={{ width: `${pairScore * 100}%` }} />
                  </div>
                  <div className="flex justify-between items-center mt-2">
                    <div className={`text-xs font-bold ${sentColor}`}>{label}</div>
                    <div className="text-[10px] text-gray-500">
                      {base}: {(baseData.score*100).toFixed(0)}% | {quote}: {(quoteData.score*100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* NLP Methodology */}
      <div className="bg-gradient-to-br from-teal-500/10 to-cyan-500/10 rounded-3xl p-6 border border-teal-400/30">
        <h3 className="text-lg font-bold text-white mb-4">🔬 منهجية التحليل اللغوي (NLP)</h3>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          {[
            { icon: '📡', title: 'جمع البيانات', desc: 'RSS feeds من Reuters, Bloomberg, CNBC + Twitter API + Reddit مباشرة' },
            { icon: '🧹', title: 'معالجة النصوص', desc: 'Tokenization → Stemming → Stop words removal → TF-IDF Vectorization' },
            { icon: '🤖', title: 'نموذج BERT', desc: 'Transformer مُدرَّب على أخبار مالية بالعربية والإنجليزية للتصنيف' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-4">
              <div className="text-3xl mb-2">{item.icon}</div>
              <div className="text-white font-bold mb-1">{item.title}</div>
              <div className="text-gray-400 text-xs">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
