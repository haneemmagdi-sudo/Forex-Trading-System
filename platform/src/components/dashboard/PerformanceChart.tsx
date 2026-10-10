'use client'

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface Snapshot {
  id: string
  balance: number
  equity: number
  drawdown_pct: number
  recorded_at: string
}

interface PerformanceChartProps {
  data: Snapshot[]
}

export default function PerformanceChart({ data }: PerformanceChartProps) {
  const chartData = data
    .map(snapshot => ({
      name: new Date(snapshot.recorded_at).toLocaleDateString('ar-EG', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
      }),
      balance: snapshot.balance,
      equity: snapshot.equity,
      drawdown: snapshot.drawdown_pct,
    }))
    .reverse() // ensure chronological order

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value)
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-xl">
      <div>
        <h2 className="text-xl font-bold text-slate-100">تحليل منحنى النمو</h2>
        <p className="text-sm text-slate-500">مراقبة الرصيد (Balance) وصافي القيمة (Equity) مع التغيير في الزمن</p>
      </div>

      <div className="mt-8 h-80 w-full font-mono text-xs">
        {chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-500">
            لا توجد لقطات أداء مسجلة حتى الآن. يجب تشغيل الـ Agent لتوليد لقطات الأداء.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{ top: 10, right: 0, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
              <XAxis
                dataKey="name"
                stroke="#64748b"
                tickLine={false}
                axisLine={false}
                dy={10}
              />
              <YAxis
                stroke="#64748b"
                tickLine={false}
                axisLine={false}
                tickFormatter={formatCurrency}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '12px',
                  color: '#f1f5f9',
                  textAlign: 'right',
                }}
                labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
              />
              <Area
                name="رصيد الحساب (Balance)"
                type="monotone"
                dataKey="balance"
                stroke="#3b82f6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorBalance)"
              />
              <Area
                name="صافي القيمة (Equity)"
                type="monotone"
                dataKey="equity"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorEquity)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
