import { useState, useEffect, useRef } from 'react';
import { useApiData, useBackendStatus } from '../../utils/useBackend';

// ──────────────────────────────────────────────
// بيانات محاكاة النموذج
// ──────────────────────────────────────────────
function useMLMetrics() {
  const tick = useRef(0);
  const [state, setState] = useState({
    modelStatus: 'trained' as 'training' | 'trained' | 'idle',
    trainProgress: 100,
    accuracy: 79.3,
    precision: 81.2,
    recall: 76.8,
    f1Score: 78.9,
    trainLoss: [1.42, 1.28, 1.11, 0.98, 0.87, 0.78, 0.72, 0.68, 0.65, 0.63],
    valLoss:   [1.51, 1.38, 1.24, 1.12, 1.04, 0.99, 0.97, 0.96, 0.95, 0.94],
    trainAcc:  [51, 58, 63, 68, 72, 75, 77, 78, 79, 79.3],
    valAcc:    [49, 55, 60, 65, 68, 71, 73, 74, 75, 75.8],
    confMatrix: [[342, 78], [91, 289]],
    featureImportance: [
      { name: 'RSI', importance: 0.28, color: '#10b981' },
      { name: 'MACD', importance: 0.22, color: '#3b82f6' },
      { name: 'EMA Trend', importance: 0.19, color: '#8b5cf6' },
      { name: 'ADX', importance: 0.14, color: '#f59e0b' },
      { name: 'ATR', importance: 0.11, color: '#ec4899' },
      { name: 'Stoch', importance: 0.06, color: '#06b6d4' },
    ],
    predictions: [] as { time: string; actual: string; predicted: string; confidence: number; correct: boolean }[],
    currentPrediction: { direction: 'BUY', confidence: 81.4, regime: 'SLOW_TREND' },
  });

  useEffect(() => {
    // توليد التنبؤات
    const preds = Array.from({ length: 15 }, (_, i) => {
      const actual = Math.random() > 0.45 ? 'BUY' : 'SELL';
      const predicted = Math.random() > 0.22 ? actual : (actual === 'BUY' ? 'SELL' : 'BUY');
      const correct = actual === predicted;
      const minutes = (15 - i) * 5;
      return {
        time: `${minutes}د مضت`,
        actual,
        predicted,
        confidence: parseFloat((55 + Math.random() * 40).toFixed(1)),
        correct,
      };
    });
    setState(s => ({ ...s, predictions: preds }));

    const interval = setInterval(() => {
      tick.current++;
      setState(s => ({
        ...s,
        currentPrediction: {
          direction: Math.sin(tick.current * 0.3) > 0 ? 'BUY' : 'SELL',
          confidence: parseFloat((72 + Math.sin(tick.current * 0.5) * 12).toFixed(1)),
          regime: ['SLOW_TREND', 'STRONG_TREND', 'LOW_VOL_RANGE'][tick.current % 3],
        },
      }));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return state;
}

// ──────────────────────────────────────────────
// Loss Chart
// ──────────────────────────────────────────────
function LossChart({ trainLoss, valLoss }: { trainLoss: number[]; valLoss: number[] }) {
  const w = 400, h = 120;
  const maxV = Math.max(...trainLoss, ...valLoss);
  const minV = Math.min(...trainLoss, ...valLoss);
  const range = maxV - minV || 1;

  const toPoint = (vals: number[]) =>
    vals.map((v, i) => {
      const x = (i / (vals.length - 1)) * (w - 20) + 10;
      const y = 10 + ((maxV - v) / range) * (h - 20);
      return `${x},${y}`;
    }).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <polyline points={toPoint(trainLoss)} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="none" />
      <polyline points={toPoint(valLoss)}   fill="none" stroke="#06b6d4" strokeWidth="2" strokeDasharray="4,2" />
      {[0, 5, 9].map(i => (
        <g key={i}>
          <circle cx={(i / 9) * (w - 20) + 10} cy={10 + ((maxV - trainLoss[i]) / range) * (h - 20)}
            r="3" fill="#8b5cf6" />
          <circle cx={(i / 9) * (w - 20) + 10} cy={10 + ((maxV - valLoss[i]) / range) * (h - 20)}
            r="3" fill="#06b6d4" />
        </g>
      ))}
    </svg>
  );
}

// ──────────────────────────────────────────────
// Confusion Matrix Visual
// ──────────────────────────────────────────────
function ConfusionMatrix({ matrix }: { matrix: number[][] }) {
  const total = matrix.flat().reduce((a, b) => a + b, 0);
  const labels = ['BUY', 'SELL'];
  const colors = [
    ['rgba(16,185,129,0.5)', 'rgba(239,68,68,0.3)'],
    ['rgba(239,68,68,0.3)', 'rgba(16,185,129,0.5)'],
  ];

  return (
    <div className="space-y-2">
      <div className="text-gray-400 text-xs text-center mb-3">التنبؤ ←</div>
      <div className="flex justify-center gap-1">
        <div className="w-12" />
        {labels.map(l => <div key={l} className="w-20 text-center text-xs text-gray-400 font-bold">{l}</div>)}
      </div>
      {matrix.map((row, ri) => (
        <div key={ri} className="flex items-center gap-1 justify-center">
          <div className="w-12 text-xs text-gray-400 font-bold text-center">{labels[ri]}</div>
          {row.map((val, ci) => (
            <div
              key={ci}
              className="w-20 h-16 rounded-xl flex flex-col items-center justify-center border border-white/10"
              style={{ background: colors[ri][ci] }}
            >
              <div className="text-white font-black text-lg">{val}</div>
              <div className="text-gray-400 text-xs">{((val / total) * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      ))}
      <div className="text-gray-400 text-xs text-center mt-1">↑ الفعلي</div>
    </div>
  );
}

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────
export default function MLDashboard() {
  const ml = useMLMetrics();
  const { connected } = useBackendStatus();
  const { data: weights } = useApiData<Record<string, any>>('/api/voting-weights', 10000);
  const { data: learningLogs } = useApiData<any[]>('/api/learning-logs?limit=5', 15000);
  const [isRetraining, setIsRetraining] = useState(false);

  const handleRetrain = () => {
    setIsRetraining(true);
    setTimeout(() => setIsRetraining(false), 3000);
  };

  const directionColor = ml.currentPrediction.direction === 'BUY' ? 'text-emerald-400' : 'text-red-400';
  const directionBg = ml.currentPrediction.direction === 'BUY'
    ? 'from-emerald-500/20 to-teal-500/20 border-emerald-400/30'
    : 'from-red-500/20 to-pink-500/20 border-red-400/30';

  return (
    <div className="space-y-6" dir="rtl">

      {/* Hero */}
      <div className="bg-gradient-to-br from-blue-600/20 via-indigo-600/20 to-purple-600/20 rounded-3xl p-8 border border-blue-400/30 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative">
          <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
            <div>
              <h2 className="text-4xl font-black text-white mb-2">🤖 لوحة التعلم الآلي</h2>
              <p className="text-blue-200 text-lg">Random Forest + نظام التعلم المستمر</p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-bold ${
                connected
                  ? 'bg-emerald-500/20 border-emerald-400/30 text-emerald-400'
                  : 'bg-yellow-500/20 border-yellow-400/30 text-yellow-400'
              }`}>
                <span className={`w-2 h-2 rounded-full animate-pulse ${connected ? 'bg-emerald-400' : 'bg-yellow-400'}`} />
                {connected ? 'ML Agent متصل' : 'محاكاة'}
              </div>
              <button
                onClick={handleRetrain}
                disabled={isRetraining}
                className="px-5 py-2 bg-blue-500/20 border border-blue-400/50 text-blue-300 rounded-xl text-sm font-bold hover:bg-blue-500/30 transition-all disabled:opacity-50"
              >
                {isRetraining ? '⏳ يتدرب...' : '🔄 إعادة تدريب'}
              </button>
            </div>
          </div>

          {/* Live Prediction Banner */}
          <div className={`bg-gradient-to-br ${directionBg} rounded-2xl p-5 border`}>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <div className="text-gray-400 text-sm mb-1">🤖 تنبؤ النموذج الحالي</div>
                <div className={`text-5xl font-black ${directionColor}`}>{ml.currentPrediction.direction}</div>
                <div className="text-gray-400 text-sm mt-1">
                  Regime: <span className="text-white">{ml.currentPrediction.regime.replace(/_/g, ' ')}</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-sm mb-1">الثقة</div>
                <div className={`text-4xl font-black ${ml.currentPrediction.confidence > 75 ? 'text-emerald-400' : ml.currentPrediction.confidence > 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {ml.currentPrediction.confidence}%
                </div>
                <div className="text-gray-500 text-xs mt-1">
                  {ml.currentPrediction.confidence > 75 ? '✅ إشارة قوية' : ml.currentPrediction.confidence > 60 ? '⚠️ إشارة متوسطة' : '❌ إشارة ضعيفة'}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-gray-400 text-xs">مستوى الثقة</div>
                <div className="w-40 h-3 bg-black/30 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${ml.currentPrediction.confidence}%`,
                      background: ml.currentPrediction.confidence > 75 ? '#10b981' : ml.currentPrediction.confidence > 60 ? '#f59e0b' : '#ef4444'
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Model Performance */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: '🎯', label: 'Accuracy', value: `${ml.accuracy}%`, color: 'text-violet-400' },
          { icon: '🔍', label: 'Precision', value: `${ml.precision}%`, color: 'text-blue-400' },
          { icon: '📡', label: 'Recall', value: `${ml.recall}%`, color: 'text-emerald-400' },
          { icon: '⚡', label: 'F1 Score', value: `${ml.f1Score}%`, color: 'text-yellow-400' },
        ].map((m2, i) => (
          <div key={i} className="bg-white/5 rounded-2xl p-5 border border-white/10 text-center">
            <div className="text-3xl mb-2">{m2.icon}</div>
            <div className={`text-2xl font-black ${m2.color}`}>{m2.value}</div>
            <div className="text-gray-500 text-sm mt-1">{m2.label}</div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Training Curves */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">📉 منحنيات التدريب</h3>
          <LossChart trainLoss={ml.trainLoss} valLoss={ml.valLoss} />
          <div className="flex items-center gap-4 mt-3 text-xs justify-center">
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-purple-500" />
              <span className="text-gray-400">Train Loss</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 border-t-2 border-dashed border-cyan-500" />
              <span className="text-gray-400">Val Loss</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="bg-black/30 rounded-xl p-3 text-center">
              <div className="text-gray-500 text-xs">Train Accuracy</div>
              <div className="text-purple-400 font-bold">{ml.trainAcc[ml.trainAcc.length - 1]}%</div>
            </div>
            <div className="bg-black/30 rounded-xl p-3 text-center">
              <div className="text-gray-500 text-xs">Val Accuracy</div>
              <div className="text-cyan-400 font-bold">{ml.valAcc[ml.valAcc.length - 1]}%</div>
            </div>
          </div>
        </div>

        {/* Confusion Matrix */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">🔲 Confusion Matrix</h3>
          <ConfusionMatrix matrix={ml.confMatrix} />
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <div className="bg-emerald-500/10 rounded-lg p-2 border border-emerald-400/20">
              <div className="text-emerald-400 font-bold">True BUY: {ml.confMatrix[0][0]}</div>
              <div className="text-gray-500">تنبؤ صحيح بالشراء</div>
            </div>
            <div className="bg-emerald-500/10 rounded-lg p-2 border border-emerald-400/20">
              <div className="text-emerald-400 font-bold">True SELL: {ml.confMatrix[1][1]}</div>
              <div className="text-gray-500">تنبؤ صحيح بالبيع</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-2 border border-red-400/20">
              <div className="text-red-400 font-bold">False BUY: {ml.confMatrix[0][1]}</div>
              <div className="text-gray-500">خطأ في الشراء</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-2 border border-red-400/20">
              <div className="text-red-400 font-bold">False SELL: {ml.confMatrix[1][0]}</div>
              <div className="text-gray-500">خطأ في البيع</div>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Importance */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">📊 أهمية الميزات (Feature Importance)</h3>
        <div className="space-y-3">
          {ml.featureImportance.map((f, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="w-16 text-right text-gray-400 text-sm font-medium">{f.name}</div>
              <div className="flex-1 h-6 bg-black/30 rounded-full overflow-hidden relative">
                <div
                  className="h-full rounded-full flex items-center justify-end pr-3 transition-all duration-700"
                  style={{ width: `${f.importance * 100}%`, background: f.color }}
                >
                  <span className="text-white text-xs font-bold">{(f.importance * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="text-xs text-gray-500 w-12">
                {f.importance > 0.2 ? '🔥 عالي' : f.importance > 0.1 ? '✅ متوسط' : '💡 منخفض'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Predictions */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">📋 آخر التنبؤات</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs border-b border-white/10">
                <th className="pb-2 text-right">الوقت</th>
                <th className="pb-2 text-center">الفعلي</th>
                <th className="pb-2 text-center">المتنبأ</th>
                <th className="pb-2 text-center">الثقة</th>
                <th className="pb-2 text-center">النتيجة</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {ml.predictions.slice(0, 10).map((p, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-white/2' : ''}>
                  <td className="py-2 text-gray-500 text-xs">{p.time}</td>
                  <td className="py-2 text-center">
                    <span className={`text-xs font-bold ${p.actual === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {p.actual}
                    </span>
                  </td>
                  <td className="py-2 text-center">
                    <span className={`text-xs font-bold ${p.predicted === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {p.predicted}
                    </span>
                  </td>
                  <td className="py-2 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-12 h-1.5 bg-black/40 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${p.confidence}%`,
                            background: p.confidence > 75 ? '#10b981' : p.confidence > 60 ? '#f59e0b' : '#ef4444'
                          }}
                        />
                      </div>
                      <span className="text-gray-400 text-xs">{p.confidence}%</span>
                    </div>
                  </td>
                  <td className="py-2 text-center">
                    <span className={`text-lg ${p.correct ? '✅' : '❌'}`}>
                      {p.correct ? '✅' : '❌'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Voting Weights from Learning Agent */}
      {weights && (
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">⚖️ أوزان التصويت المحدَّثة بالـ ML</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-gray-400 text-sm mb-3">الأوزان الأساسية</h4>
              <div className="space-y-2">
                {Object.entries(weights.base_weights || {}).map(([key, val]: any) => (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-gray-400 text-xs w-16 uppercase">{key}</span>
                    <div className="flex-1 h-2 bg-black/40 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(val / 3) * 100}%` }} />
                    </div>
                    <span className="text-blue-400 text-xs font-mono w-8">{val.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-gray-400 text-sm mb-3">معاملات التعلم</h4>
              <div className="space-y-2">
                {Object.entries(weights.learned_multipliers || {}).map(([key, val]: any) => (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-gray-400 text-xs w-16 uppercase">{key}</span>
                    <div className="flex-1 h-2 bg-black/40 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 rounded-full" style={{ width: `${(val / 3) * 100}%` }} />
                    </div>
                    <span className="text-purple-400 text-xs font-mono w-8">×{val.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
