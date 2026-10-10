'use client'

import AgentStatusCard from './AgentStatusCard'

interface AgentState {
  id: string
  name: string
  arabicName: string
  description: string
  status: 'active' | 'paused' | 'stopped' | 'offline'
}

interface AgentGridProps {
  agents: AgentState[]
  isAgentOnline: boolean
}

export default function AgentGrid({ agents, isAgentOnline }: AgentGridProps) {
  const handleCommand = async (agentName: string, action: 'pause' | 'resume' | 'stop') => {
    const res = await fetch('/api/mt5/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agentName, action }),
    })
    const data = await res.json()
    if (!res.ok) {
      alert(data.error || 'فشل إرسال الأمر للوكيل')
      throw new Error(data.error)
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      {agents.map(agent => (
        <AgentStatusCard
          key={agent.id}
          id={agent.id}
          name={agent.name}
          arabicName={agent.arabicName}
          description={agent.description}
          status={isAgentOnline ? agent.status : 'offline'}
          onCommand={handleCommand}
        />
      ))}
    </div>
  )
}
