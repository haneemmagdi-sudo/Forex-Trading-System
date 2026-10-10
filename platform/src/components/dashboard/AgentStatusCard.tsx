'use client'

import { useState } from 'react'
import { Play, Pause, AlertTriangle, ShieldCheck, Cpu } from 'lucide-react'

interface AgentStatusCardProps {
  id: string
  name: string
  arabicName: string
  description: string
  status: 'active' | 'paused' | 'stopped' | 'offline'
  onCommand: (agentName: string, action: 'pause' | 'resume' | 'stop') => Promise<void>
}

export default function AgentStatusCard({
  id,
  name,
  arabicName,
  description,
  status: initialStatus,
  onCommand,
}: AgentStatusCardProps) {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState(initialStatus)

  const handleAction = async (action: 'pause' | 'resume' | 'stop') => {
    setLoading(true)
    try {
      await onCommand(id, action)
      if (action === 'pause') setStatus('paused')
      else if (action === 'resume') setStatus('active')
      else if (action === 'stop') setStatus('stopped')
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusDetails = () => {
    switch (status) {
      case 'active':
        return {
          label: 'يعمل بنشاط',
          color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
          dot: 'bg-emerald-500 shadow-[0_0_10px_#10b981]',
        }
      case 'paused':
        return {
          label: 'موقوف مؤقتاً',
          color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
          dot: 'bg-amber-500 shadow-[0_0_10px_#f59e0b]',
        }
      case 'stopped':
        return {
          label: 'متوقف',
          color: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
          dot: 'bg-rose-500 shadow-[0_0_10px_#ef4444]',
        }
      default:
        return {
          label: 'غير متصل بالخادم',
          color: 'text-slate-400 bg-slate-500/10 border-slate-500/20',
          dot: 'bg-slate-500',
        }
    }
  }

  const details = getStatusDetails()

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl transition-all duration-300 hover:border-slate-700 hover:shadow-[0_8px_30px_rgb(0,0,0,0.4)]">
      {/* Decorative gradient overlay */}
      <div className="absolute -right-20 -top-20 -z-10 h-40 w-40 rounded-full bg-blue-500/5 blur-3xl" />

      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800/80 text-blue-400 border border-slate-700/50">
            <Cpu className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100">{arabicName}</h3>
            <span className="text-xs text-slate-500">{name}</span>
          </div>
        </div>

        <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${details.color}`}>
          <span className={`h-2 w-2 rounded-full ${details.dot}`} />
          {details.label}
        </div>
      </div>

      <p className="mt-4 text-sm leading-relaxed text-slate-400 min-h-[48px]">
        {description}
      </p>

      <div className="mt-6 flex gap-2">
        {status === 'paused' || status === 'stopped' || status === 'offline' ? (
          <button
            onClick={() => handleAction('resume')}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all duration-300 hover:from-blue-500 hover:to-cyan-500 hover:shadow-blue-500/30 disabled:opacity-50"
          >
            <Play className="h-4 w-4 fill-current" />
            تفعيل الوكيل
          </button>
        ) : (
          <button
            onClick={() => handleAction('pause')}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-2.5 text-sm font-semibold text-slate-200 transition-all duration-300 hover:bg-slate-800 hover:border-slate-600 disabled:opacity-50"
          >
            <Pause className="h-4 w-4 fill-current" />
            إيقاف مؤقت
          </button>
        )}

        {status !== 'stopped' && status !== 'offline' && (
          <button
            onClick={() => handleAction('stop')}
            disabled={loading}
            className="flex items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/5 p-2.5 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/30 transition-all duration-300 disabled:opacity-50"
            title="إيقاف كامل"
          >
            <AlertTriangle className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
