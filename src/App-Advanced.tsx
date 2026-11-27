import { useState } from 'react';
import DecisionMatrix from './components/advanced/DecisionMatrix';
import LiveDashboard from './components/advanced/LiveDashboard';
import AdvancedAnalytics from './components/advanced/AdvancedAnalytics';
import PairsStatusTable from './components/advanced/PairsStatusTable';
import OpenBBDashboard from './components/advanced/OpenBBDashboard';
import AgentsOverview from './components/ai-agents/AgentsOverview';
import SmartMoneyConcepts from './components/ai-agents/SmartMoneyConcepts';
import MT5Integration from './components/ai-agents/MT5Integration';
import AgentsDashboard from './components/ai-agents/AgentsDashboard';
import CommandCenter from './components/ai-agents/CommandCenter';
import AgentCommunication from './components/ai-agents/AgentCommunication';
import HomePage from './components/HomePage';
import MLDashboard from './components/ml/MLDashboard';
import LSTMPredictor from './components/ml/LSTMPredictor';
import ReinforcementLearning from './components/ml/ReinforcementLearning';
import SentimentAnalysis from './components/ml/SentimentAnalysis';
import TradingAgentsPage from './components/tradingagents/TradingAgentsPage';
import ApiTokenControl from './components/ApiTokenControl';
import { useApiData, type Features } from './utils/useBackend';

// =====================================================================
// تعريف مجموعات التبويبات (النظام المؤسسي السريع)
// =====================================================================
const TAB_GROUPS = [
  {
    group: '🏠 الرئيسية',
    tabs: [
      { id: 'home', label: 'الصفحة الرئيسية', icon: '🏠' },
    ],
  },
  {
    group: '🏛️ شركة TradingAgents (Tauric Research)',
    tabs: [
      { id: 'tradingAgents', label: 'TradingAgents — شركة تداول LangGraph', icon: '🏛️', isNew: true },
    ],
  },
  {
    group: '📊 التحليل والإشارات',
    tabs: [
      { id: 'liveDash', label: 'لوحة المراقبة الحية', icon: '📈', isNew: true },
      { id: 'pairsTable', label: 'جدول حالة الأزواج', icon: '📋', isNew: true },
      { id: 'advancedAnalytics', label: 'التحليل المتقدم', icon: '🔬', isNew: true },
      { id: 'openbb', label: 'بوابة بيانات OpenBB', icon: '🌐', isNew: true },
    ],
  },
  {
    group: '🔍 نظام FSM',
    tabs: [
      { id: 'matrix', label: 'مصفوفة القرار', icon: '🧠' },
    ],
  },
  {
    group: '🤖 وكلاء الذكاء الاصطناعي',
    tabs: [
      { id: 'commandCenter', label: 'مركز القيادة', icon: '🎯', isNew: true },
      { id: 'aiAgents', label: 'وكلاء AI', icon: '🤖' },
      { id: 'agentCommTab', label: 'التواصل مع الوكلاء', icon: '💬', isNew: true },
      { id: 'smc', label: 'Smart Money Concepts', icon: '💎' },
      { id: 'mt5', label: 'MT5 Integration', icon: '🔌' },
      { id: 'aiDashboard', label: 'AI Dashboard', icon: '🖥️' },
    ],
  },
  {
    group: '🧠 التعلم الآلي (المرحلة 5)',
    tabs: [
      { id: 'mlDashboard', label: 'لوحة ML', icon: '🤖', isNew: true },
      { id: 'lstm', label: 'LSTM — التنبؤ بالأسعار', icon: '📡', isNew: true },
      { id: 'rl', label: 'Reinforcement Learning', icon: '🎮', isNew: true },
      { id: 'sentiment', label: 'تحليل المشاعر', icon: '🧪', isNew: true },
    ],
  },
];

export default function AppAdvanced() {
  const [activeTab, setActiveTab] = useState('home');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // صفحتان تبقيان مخفيتين حتى يُشغَّل مفتاحهما في الخادم
  const { data: features } = useApiData<Features>('/api/features', 30_000);
  const hiddenTabs: Record<string, boolean> = { lstm: !features?.lstm_page, rl: !features?.rl_page };
  const tabGroups = TAB_GROUPS.map(g => ({ ...g, tabs: g.tabs.filter(t => !hiddenTabs[t.id]) }));

  const allTabs = tabGroups.flatMap(g => g.tabs);

  const filteredGroups = searchQuery
    ? [{
        group: '🔎 نتائج البحث',
        tabs: allTabs.filter(t =>
          t.label.includes(searchQuery) || t.id.toLowerCase().includes(searchQuery.toLowerCase())
        ),
      }]
    : tabGroups;

  const activeTabInfo = allTabs.find(t => t.id === activeTab);

  const renderContent = () => {
    switch (activeTab) {
      case 'home': return <HomePage onNavigate={setActiveTab} />;
      case 'tradingAgents': return <TradingAgentsPage />;
      case 'liveDash': return <LiveDashboard />;
      case 'pairsTable': return <PairsStatusTable />;
      case 'advancedAnalytics': return <AdvancedAnalytics />;
      case 'openbb': return <OpenBBDashboard />;
      case 'matrix': return <DecisionMatrix />;
      case 'commandCenter': return <CommandCenter />;
      case 'aiAgents': return <AgentsOverview />;
      case 'agentCommTab': return <AgentCommunication />;
      case 'smc': return <SmartMoneyConcepts />;
      case 'mt5': return <MT5Integration />;
      case 'aiDashboard': return <AgentsDashboard />;
      case 'mlDashboard': return <MLDashboard />;
      case 'lstm': return <LSTMPredictor />;
      case 'rl': return <ReinforcementLearning />;
      case 'sentiment': return <SentimentAnalysis />;
      default: return <HomePage onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950 flex" dir="rtl">

      {/* ====================================================
          SIDEBAR
      ==================================================== */}
      <aside className={`flex-shrink-0 bg-black/60 backdrop-blur-xl border-l border-purple-500/20 flex flex-col transition-all duration-300 ${sidebarOpen ? 'w-64' : 'w-16'} sticky top-0 h-screen overflow-hidden`}>

        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-4 border-b border-purple-500/20 flex-shrink-0">
          {sidebarOpen && (
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-purple-500/30">
                <span className="text-sm">🧠</span>
              </div>
              <div className="min-w-0">
                <div className="text-white font-bold text-sm truncate">Quantum FSM Pro</div>
                <div className="text-purple-400 text-xs">V4.2 Elite</div>
              </div>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-all flex-shrink-0"
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        {/* Search */}
        {sidebarOpen && (
          <div className="p-3 border-b border-white/5 flex-shrink-0">
            <input
              type="text"
              placeholder="🔎 بحث..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-black/30 border border-white/10 text-white text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-purple-400 placeholder-gray-600"
            />
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 scrollbar-hide">
          {filteredGroups.map((group, gi) => (
            <div key={gi} className="mb-1">
              {/* Group Header */}
              {sidebarOpen && (
                <div className="px-3 py-1.5 text-xs font-bold text-gray-600 uppercase tracking-wider">
                  {group.group}
                </div>
              )}

              {/* Tabs */}
              {group.tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setSearchQuery(''); }}
                  title={!sidebarOpen ? tab.label : undefined}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 transition-all duration-200 relative ${
                    activeTab === tab.id
                      ? 'bg-purple-500/20 text-purple-300'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {/* Active Indicator */}
                  {activeTab === tab.id && (
                    <div className="absolute right-0 top-1 bottom-1 w-0.5 bg-purple-400 rounded-full" />
                  )}

                  <span className="text-base flex-shrink-0">{tab.icon}</span>

                  {sidebarOpen && (
                    <span className="text-sm font-medium truncate flex-1 text-right">{tab.label}</span>
                  )}

                  {sidebarOpen && (tab as any).isNew && (
                    <span className="text-xs bg-purple-500/30 text-purple-300 px-1.5 py-0.5 rounded-full flex-shrink-0">جديد</span>
                  )}
                </button>
              ))}

              {/* Group Separator */}
              {gi < filteredGroups.length - 1 && (
                <div className="mx-3 my-1 border-b border-white/5" />
              )}
            </div>
          ))}
        </nav>

        {/* Sidebar Footer */}
        {sidebarOpen && (
          <div className="p-3 border-t border-white/5 flex-shrink-0">
            <div className="text-center text-gray-600 text-xs">
              ⚡ Blessing Pro V4.2 Elite Fixed
            </div>
          </div>
        )}
      </aside>

      {/* ====================================================
          MAIN CONTENT
      ==================================================== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Top Bar */}
        <header className="bg-black/30 backdrop-blur-xl border-b border-purple-500/20 flex-shrink-0 sticky top-0 z-30">
          <div className="px-6 py-3 flex items-center justify-between gap-4">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-gray-600 text-sm hidden md:block">Quantum FSM Pro</span>
              <span className="text-gray-700 hidden md:block">/</span>
              <span className="text-white text-sm font-semibold truncate">
                {activeTabInfo?.icon} {activeTabInfo?.label || 'الصفحة الرئيسية'}
              </span>
            </div>

            {/* Status Badges */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <ApiTokenControl />
              <div className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-emerald-400 text-xs font-semibold">V4.2 Elite</span>
              </div>
              <div className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                <span className="text-purple-400 text-xs font-semibold">🏅 1884 سطر</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto animate-fadeIn">
            {renderContent()}
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-black/20 border-t border-purple-500/10 py-3 px-6 flex-shrink-0">
          <p className="text-center text-gray-600 text-xs">
            ⚡ Quantum FSM Grid Pro — نظام تداول متقدم من الجيل الثالث | FSM + AI Voting + Smart Grid + AI Agents
          </p>
        </footer>
      </div>
    </div>
  );
}
