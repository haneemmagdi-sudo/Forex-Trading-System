import { useState, useEffect, useRef } from 'react';

// ──────────────────────────────────────────────
// محاكاة بيانات نموذج LSTM
// ──────────────────────────────────────────────
function useLSTMData() {
  const tick = useRef(0);
  const [state, setState] = useState({
    isRunning: false,
    epoch: 0,
    totalEpochs: 100,
    trainLoss: [] as number[],
    valLoss: [] as number[],
    currentLoss: 0.43,
    rmse: 0.0012,
    mae: 0.0009,
    r2Score: 0.78,
    predictions: Array.from({ length: 50 }, (_, i) => {
      const base = 1.0850 + Math.sin(i * 0.3) * 0.005;
      const actual = base + (Math.random() - 0.5) * 0.002;
      const predicted = actual + (Math.random() - 0.5) * 0.001;
      return { i, actual, predicted };
    }),
    forecastNext: [
      { bars: 1, price: 1.0872, direction: 'UP', confidence: 76 },
      { bars: 3, price: 1.0891, direction: 'UP', confidence: 68 },
      { bars: 5, price: 1.0865, direction: 'DOWN', confidence: 54 },
      { bars: 10, price: 1.0879, direction: 'UP', confidence: 41 },
    ],
    modelConfig: {
      layers: [
        { type: 'Input', units: 60, activation: '—', color: '#3b82f6' },
        { type: 'LSTM', units: 128, activation: 'tanh', color: '#8b5cf6' },
        { type: 'Dropout', units: 0.2, activation: '—', color: '#6b7280' },
        { type: 'LSTM', units: 64, activation: 'tanh', color: '#8b5cf6' },
        { type: 'Dropout', units: 0.2, activation: '—', color: '#6b7280' },
        { type: 'Dense', units: 32, activation: 'relu', color: '#10b981' },
        { type: 'Output', units: 1, activation: 'linear', color: '#f59e0b' },
      ],
    },
  });

  useEffect(() => {
    const interval = setInterval(() => {
      tick.current++;
      setState(s => ({
        ...s,
        forecastNext: s.forecastNext.map(f => ({
          ...f,
          price: parseFloat((f.price + (Math.random() - 0.5) * 0.0002).toFixed(4)),
          confidence: Math.min(95, Math.max(30, f.confidence + (Math.random() - 0.5) * 3)),
        })),
      }));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const startTraining = () => {
    setState(s => ({ ...s, isRunning: true, epoch: 0, trainLoss: [], valLoss: [] }));

    let ep = 0;
    const t = setInterval(() => {
      ep++;
      const noise = Math.random() * 0.02;
      const tl = parseFloat((1.5 * Math.exp(-ep * 0.04) + 0.1 + noise).toFixed(4));
      const vl = parseFloat((1.6 * Math.exp(-ep * 0.035) + 0.15 + noise * 1.2).toFixed(4));

      setState(s => ({
        ...s,
        epoch: ep,
        trainLoss: [...s.trainLoss, tl],
        valLoss: [...s.valLoss, vl],
        currentLoss: tl,
      }));

      if (ep >= 40) {
        clearInterval(t);
        setState(s => ({
          ...s,
          isRunning: false,
          rmse: parseFloat((0.0008 + Math.random() * 0.0005).toFixed(5)),
          mae: parseFloat((0.0006 + Math.random() * 0.0004).toFixed(5)),
          r2Score: parseFloat((0.75 + Math.random() * 0.1).toFixed(3)),
        }));
      }
    }, 200);
  };

  return { ...state, startTraining };
}

// ──────────────────────────────────────────────
// Prediction Chart
// ──────────────────────────────────────────────
function PredictionChart({ data }: { data: { i: number; actual: number; predicted: number }[] }) {
  const w = 600, h = 150;
  const vals = data.flatMap(d => [d.actual, d.predicted]);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 0.001;

  const toX = (i: number) => (i / (data.length - 1)) * (w - 20) + 10;
  const toY = (v: number) => 10 + ((max - v) / range) * (h - 20);

  const actualPts = data.map(d => `${toX(d.i)},${toY(d.actual)}`).join(' ');
  const predPts = data.map(d => `${toX(d.i)},${toY(d.predicted)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <polyline points={actualPts} fill="none" stroke="#3b82f6" strokeWidth="1.5" opacity="0.9" />
      <polyline points={predPts}   fill="none" stroke="#ec4899" strokeWidth="1.5" strokeDasharray="3,2" opacity="0.9" />
    </svg>
  );
}

// ──────────────────────────────────────────────
// Loss Training Chart
// ──────────────────────────────────────────────
function TrainingChart({ trainLoss, valLoss }: { trainLoss: number[]; valLoss: number[] }) {
  if (trainLoss.length < 2) return (
    <div className="flex items-center justify-center h-24 text-gray-600 text-sm">
      ابدأ التدريب لرؤية المنحنيات
    </div>
  );

  const w = 400, h = 100;
  const all = [...trainLoss, ...valLoss];
  const maxV = Math.max(...all), minV = Math.min(...all);
  const range = maxV - minV || 0.1;

  const pts = (arr: number[]) =>
    arr.map((v, i) => {
      const x = (i / (arr.length - 1)) * (w - 20) + 10;
      const y = 10 + ((maxV - v) / range) * (h - 20);
      return `${x},${y}`;
    }).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <polyline points={pts(trainLoss)} fill="none" stroke="#8b5cf6" strokeWidth="2" />
      {valLoss.length > 1 && (
        <polyline points={pts(valLoss)} fill="none" stroke="#06b6d4" strokeWidth="2" strokeDasharray="4,2" />
      )}
    </svg>
  );
}

// ──────────────────────────────────────────────
// Network Architecture Visualization
// ──────────────────────────────────────────────
function NetworkViz({ layers }: { layers: { type: string; units: number | string; activation: string; color: string }[] }) {
  return (
    <div className="flex items-center justify-between gap-1 overflow-x-auto py-2">
      {layers.map((layer, i) => (
        <div key={i} className="flex items-center gap-1">
          <div
            className="rounded-xl border border-white/20 p-3 text-center min-w-[70px] hover:scale-105 transition-all cursor-default"
            style={{ background: `${layer.color}20`, borderColor: `${layer.color}40` }}
          >
            <div className="text-xs font-bold" style={{ color: layer.color }}>{layer.type}</div>
            <div className="text-white text-xs mt-1 font-mono">{layer.units}</div>
            {layer.activation !== '—' && (
              <div className="text-gray-500 text-xs mt-0.5">{layer.activation}</div>
            )}
          </div>
          {i < layers.length - 1 && (
            <div className="text-gray-600 text-sm">→</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ──────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────
export default function LSTMPredictor() {
  const lstm = useLSTMData();
  const [lookback, setLookback] = useState(60);
  const [features, setFeatures] = useState(['close', 'rsi', 'macd', 'ema', 'volume']);

  const availableFeatures = ['close', 'open', 'high', 'low', 'volume', 'rsi', 'macd', 'ema', 'adx', 'atr', 'stoch'];

  const toggleFeature = (f: string) => {
    setFeatures(prev =>
      prev.includes(f) ? prev.filter(x => x !== f) : [...prev, f]
    );
  };

  return (
    <div className="space-y-6" dir="rtl">

      {/* Hero */}
      <div className="bg-gradient-to-br from-purple-600/20 via-indigo-600/20 to-blue-600/20 rounded-3xl p-8 border border-purple-400/30 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative">
          <h2 className="text-4xl font-black text-white mb-3">🧠 نموذج LSTM — التنبؤ بالأسعار</h2>
          <p className="text-purple-200 text-lg mb-4">
            شبكة عصبية متكررة طويلة الذاكرة (Long Short-Term Memory) للتنبؤ بحركة السعر المستقبلية
          </p>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="bg-black/30 rounded-xl px-4 py-2 text-sm">
              <span className="text-gray-400">RMSE: </span>
              <span className="text-purple-300 font-bold">{lstm.rmse}</span>
            </div>
            <div className="bg-black/30 rounded-xl px-4 py-2 text-sm">
              <span className="text-gray-400">MAE: </span>
              <span className="text-purple-300 font-bold">{lstm.mae}</span>
            </div>
            <div className="bg-black/30 rounded-xl px-4 py-2 text-sm">
              <span className="text-gray-400">R²: </span>
              <span className="text-emerald-400 font-bold">{lstm.r2Score}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Architecture */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">🏗️ بنية الشبكة العصبية</h3>
        <NetworkViz layers={lstm.modelConfig.layers} />
        <div className="mt-4 grid md:grid-cols-4 gap-3">
          {[
            { label: 'الطبقات الإجمالية', value: '7', color: 'text-purple-400' },
            { label: 'المعاملات', value: '127,873', color: 'text-blue-400' },
            { label: 'نافذة الإدخال', value: `${lookback} شمعة`, color: 'text-emerald-400' },
            { label: 'الميزات', value: `${features.length} مؤشر`, color: 'text-yellow-400' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-3 text-center">
              <div className={`text-xl font-black ${item.color}`}>{item.value}</div>
              <div className="text-gray-500 text-xs mt-1">{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Training Controls */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">⚙️ إعدادات التدريب</h3>

          <div className="space-y-4">
            <div>
              <label className="text-gray-400 text-sm block mb-2">
                نافذة الاسترجاع (Lookback): <span className="text-white font-bold">{lookback} شمعة</span>
              </label>
              <input
                type="range" min={20} max={120} value={lookback}
                onChange={e => setLookback(+e.target.value)}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>20</span><span>60</span><span>120</span>
              </div>
            </div>

            <div>
              <div className="text-gray-400 text-sm mb-2">الميزات المستخدمة:</div>
              <div className="flex flex-wrap gap-2">
                {availableFeatures.map(f => (
                  <button
                    key={f}
                    onClick={() => toggleFeature(f)}
                    className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
                      features.includes(f)
                        ? 'bg-purple-500/30 border-purple-400/50 text-purple-300'
                        : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={lstm.startTraining}
              disabled={lstm.isRunning}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-bold rounded-xl hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {lstm.isRunning
                ? `⏳ يتدرب... (Epoch ${lstm.epoch}/40)`
                : '🚀 بدء التدريب'}
            </button>

            {lstm.isRunning && (
              <div>
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>التقدم</span>
                  <span>{Math.round((lstm.epoch / 40) * 100)}%</span>
                </div>
                <div className="h-2 bg-black/30 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all"
                    style={{ width: `${(lstm.epoch / 40) * 100}%` }}
                  />
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Train Loss: <span className="text-purple-400">{lstm.currentLoss.toFixed(4)}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Training Curves */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-lg font-bold text-white mb-4">📉 منحنيات التدريب</h3>
          <TrainingChart trainLoss={lstm.trainLoss} valLoss={lstm.valLoss} />
          <div className="flex gap-4 mt-2 text-xs justify-center">
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-purple-500" />
              <span className="text-gray-400">Train Loss</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-6 h-0.5 bg-cyan-500 border-t-2 border-dashed" />
              <span className="text-gray-400">Val Loss</span>
            </div>
          </div>
          {lstm.epoch > 0 && (
            <div className="mt-4 text-center text-gray-500 text-sm">
              آخر epoch: #{lstm.epoch} | Loss: {lstm.currentLoss.toFixed(4)}
            </div>
          )}
        </div>
      </div>

      {/* Predictions vs Actual */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">📊 السعر الفعلي vs التنبؤ</h3>
        <div className="bg-black/30 rounded-2xl p-4 overflow-hidden">
          <PredictionChart data={lstm.predictions} />
        </div>
        <div className="flex gap-4 mt-3 text-xs justify-center">
          <div className="flex items-center gap-1">
            <div className="w-6 h-0.5 bg-blue-500" />
            <span className="text-gray-400">السعر الفعلي</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-6 h-0.5 bg-pink-500 border-t-2 border-dashed" />
            <span className="text-gray-400">التنبؤ</span>
          </div>
        </div>
      </div>

      {/* Future Forecast */}
      <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4">🔮 التنبؤ المستقبلي (EUR/USD)</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {lstm.forecastNext.map((f, i) => {
            const isUp = f.direction === 'UP';
            return (
              <div key={i} className={`rounded-2xl p-5 border text-center ${
                isUp
                  ? 'bg-emerald-500/10 border-emerald-400/30'
                  : 'bg-red-500/10 border-red-400/30'
              }`}>
                <div className="text-gray-400 text-xs mb-2">بعد {f.bars} شمعة</div>
                <div className="text-3xl mb-2">{isUp ? '📈' : '📉'}</div>
                <div className={`text-lg font-black ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
                  {f.price.toFixed(4)}
                </div>
                <div className="mt-2">
                  <div className="h-1.5 bg-black/30 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isUp ? 'bg-emerald-500' : 'bg-red-500'}`}
                      style={{ width: `${f.confidence}%` }}
                    />
                  </div>
                  <div className="text-gray-500 text-xs mt-1">ثقة: {f.confidence.toFixed(0)}%</div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 bg-yellow-500/10 rounded-xl p-4 border border-yellow-400/20 text-sm text-yellow-300">
          ⚠️ تحذير: تنبؤات LSTM هي إرشادية فقط وليست نصيحة استثمارية. استخدمها مع إشارات نظام التصويت لاتخاذ القرار النهائي.
        </div>
      </div>

      {/* LSTM Theory */}
      <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-3xl p-6 border border-indigo-400/30">
        <h3 className="text-lg font-bold text-white mb-4">📚 كيف يعمل LSTM؟</h3>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          {[
            { icon: '🧠', title: 'الذاكرة طويلة الأمد', desc: 'يتذكر النمط الذي حدث منذ 60 شمعة مضت ويستخدمه في التنبؤ' },
            { icon: '🚪', title: 'بوابات التحكم', desc: 'بوابة النسيان (Forget) + الإدخال (Input) + الإخراج (Output) تتحكم في تدفق المعلومات' },
            { icon: '🔄', title: 'التسلسل الزمني', desc: 'يعالج الشموع بترتيب زمني ويبني فهماً تراكمياً للسوق' },
          ].map((item, i) => (
            <div key={i} className="bg-black/30 rounded-xl p-4">
              <div className="text-3xl mb-2">{item.icon}</div>
              <div className="text-white font-bold mb-1">{item.title}</div>
              <div className="text-gray-400">{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
