'use client'

import { useState } from 'react'
import { ArrowUpRight, ArrowDownRight, Search, Filter } from 'lucide-react'

interface Trade {
  id: string
  ticket: number
  symbol: string
  type: string
  status: string
  lot_size: number
  entry_price: number
  sl_price: number
  tp_price: number
  close_price: number | null
  profit_usd: number | null
  profit_pips: number | null
  opened_at: string
  closed_at: string | null
}

interface TradesTableProps {
  trades: Trade[]
}

export default function TradesTable({ trades }: TradesTableProps) {
  const [filter, setFilter] = useState<'ALL' | 'OPEN' | 'CLOSED'>('ALL')
  const [search, setSearch] = useState('')

  const filteredTrades = trades
    .filter(trade => {
      if (filter === 'ALL') return true
      return trade.status === filter
    })
    .filter(trade => {
      if (!search) return true
      return (
        trade.symbol.toLowerCase().includes(search.toLowerCase()) ||
        trade.ticket.toString().includes(search)
      )
    })

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr)
    return d.toLocaleString('ar-EG', {
      hour: '2-digit',
      minute: '2-digit',
      day: 'numeric',
      month: 'numeric',
    })
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-xl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">سجل الصفقات الحية</h2>
          <p className="text-sm text-slate-500">مراقبة الصفقات المفتوحة وسجل التداول الفعلي</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="بحث بالزوج أو التذكرة..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950/60 py-2 pl-4 pr-10 text-sm text-slate-200 placeholder-slate-600 outline-none transition-all focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 sm:w-60"
            />
          </div>

          {/* Filters */}
          <div className="flex rounded-xl border border-slate-800 bg-slate-950/40 p-1">
            <button
              onClick={() => setFilter('ALL')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                filter === 'ALL'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/10'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              الكل
            </button>
            <button
              onClick={() => setFilter('OPEN')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                filter === 'OPEN'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/10'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              المفتوحة
            </button>
            <button
              onClick={() => setFilter('CLOSED')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                filter === 'CLOSED'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/10'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              المغلقة
            </button>
          </div>
        </div>
      </div>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full border-collapse text-right text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs font-semibold text-slate-500">
              <th className="pb-3 text-right">التذكرة</th>
              <th className="pb-3 text-right">الزوج</th>
              <th className="pb-3 text-right">النوع</th>
              <th className="pb-3 text-right">الحجم</th>
              <th className="pb-3 text-right">سعر الدخول</th>
              <th className="pb-3 text-right">أخذ الربح / وقف الخسارة</th>
              <th className="pb-3 text-right">السعر الحالي/الإغلاق</th>
              <th className="pb-3 text-right">الربح ($)</th>
              <th className="pb-3 text-right">النقاط (Pips)</th>
              <th className="pb-3 text-right">وقت الفتح</th>
              <th className="pb-3 text-right">الحالة</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 text-slate-300">
            {filteredTrades.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-10 text-center text-slate-500">
                  لا توجد صفقات مطابقة للبحث أو الفلتر المختار.
                </td>
              </tr>
            ) : (
              filteredTrades.map(trade => {
                const profit = trade.profit_usd ?? 0
                const pips = trade.profit_pips ?? 0
                const isBuy = trade.type.toUpperCase() === 'BUY'
                const isPositive = profit >= 0

                return (
                  <tr key={trade.id} className="group transition-colors hover:bg-slate-800/10">
                    <td className="py-4 font-mono text-xs text-slate-500">#{trade.ticket}</td>
                    <td className="py-4 font-bold text-slate-200">{trade.symbol}</td>
                    <td className="py-4">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold ${
                          isBuy
                            ? 'text-emerald-400 bg-emerald-500/10'
                            : 'text-rose-400 bg-rose-500/10'
                        }`}
                      >
                        {isBuy ? 'شراء' : 'بيع'}
                      </span>
                    </td>
                    <td className="py-4 font-mono">{trade.lot_size.toFixed(2)}</td>
                    <td className="py-4 font-mono">{trade.entry_price.toFixed(5)}</td>
                    <td className="py-4 font-mono text-xs text-slate-500">
                      TP: {trade.tp_price > 0 ? trade.tp_price.toFixed(5) : '-'}<br />
                      SL: {trade.sl_price > 0 ? trade.sl_price.toFixed(5) : '-'}
                    </td>
                    <td className="py-4 font-mono">
                      {trade.close_price ? trade.close_price.toFixed(5) : '-'}
                    </td>
                    <td className={`py-4 font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      <span className="flex items-center gap-1">
                        {isPositive ? (
                          <ArrowUpRight className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <ArrowDownRight className="h-3 w-3 text-rose-400" />
                        )}
                        ${profit.toFixed(2)}
                      </span>
                    </td>
                    <td className={`py-4 font-mono ${isPositive ? 'text-emerald-500' : 'text-rose-500'}`}>
                      {pips > 0 ? `+${pips.toFixed(1)}` : pips.toFixed(1)}
                    </td>
                    <td className="py-4 text-xs text-slate-400">{formatDate(trade.opened_at)}</td>
                    <td className="py-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          trade.status === 'OPEN'
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            : 'bg-slate-800 text-slate-400 border border-slate-700/35'
                        }`}
                      >
                        {trade.status === 'OPEN' ? 'مفتوحة' : 'مغلقة'}
                      </span>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
