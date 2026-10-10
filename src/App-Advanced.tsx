import { useState } from 'react';
import FSMExplainer from './components/advanced/FSMExplainer';
import VotingSystem from './components/advanced/VotingSystem';
import DecisionMatrix from './components/advanced/DecisionMatrix';
import SmartGrid from './components/advanced/SmartGrid';
import AdvancedCode from './components/advanced/AdvancedCode';
import Improvements from './components/advanced/Improvements';
import StateE from './components/advanced/StateE';
import MemberRating from './components/advanced/MemberRating';
import PortfolioManager from './components/advanced/PortfolioManager';
import RecoveryMode from './components/advanced/RecoveryMode';
import Dashboard from './components/advanced/Dashboard';
import TelegramBot from './components/advanced/TelegramBot';
import BacktestSimulator from './components/advanced/BacktestSimulator';
import SignalGenerator from './components/advanced/SignalGenerator';
import LiveDashboard from './components/advanced/LiveDashboard';
import EAConfigurator from './components/advanced/EAConfigurator';
import PerformanceReport from './components/advanced/PerformanceReport';
import AdvancedAnalytics from './components/advanced/AdvancedAnalytics';
import PairsStatusTable from './components/advanced/PairsStatusTable';
import AgentsOverview from './components/ai-agents/AgentsOverview';
import SmartMoneyConcepts from './components/ai-agents/SmartMoneyConcepts';
import MT5Integration from './components/ai-agents/MT5Integration';
import AgentsDashboard from './components/ai-agents/AgentsDashboard';
import APIConfiguration from './components/ai-agents/APIConfiguration';
import CommandCenter from './components/ai-agents/CommandCenter';
import AgentCommunication from './components/ai-agents/AgentCommunication';
import FreeSetupGuide from './components/free-setup/FreeSetupGuide';
import CompleteCode from './components/free-setup/CompleteCode';
import HomePage from './components/HomePage';
import MLDashboard from './components/ml/MLDashboard';
import LSTMPredictor from './components/ml/LSTMPredictor';
import ReinforcementLearning from './components/ml/ReinforcementLearning';
import SentimentAnalysis from './components/ml/SentimentAnalysis';
import OpenBBDashboard from './components/advanced/OpenBBDashboard';

// =====================================================================
// تعريف مجموعات التبويبات
// =====================================================================
const TAB_GROUPS = [
  {
    group: '🏠 الرئيسية',
    tabs: [
      { id: 'home', label: 'الصفحة الرئيسية', icon: '🏠' },
    ],
  },
  {
    group: '📊 التحليل والإشارات',
    tabs: [
      { id: 'liveDash', label: 'لوحة المراقبة الحية', icon: '📈', isNew: true },
      { id: 'pairsTable', label: 'جدول حالة الأزواج', icon: '📋', isNew: true },
      { id: 'signalGenerator', label: 'مولّد الإشارات', icon: '🎯', isNew: true },
      { id: 'backtester', label: 'محاكي الاختبار', icon: '📊', isNew: true },
      { id: 'performanceReport', label: 'تقرير الأداء', icon: '🏆', isNew: true },
      { id: 'advancedAnalytics', label: 'التحليل المتقدم', icon: '🔬', isNew: true },
      { id: 'openbb', label: 'بوابة بيانات OpenBB', icon: '🌐', isNew: true },
    ],
  },
  {
    group: '🔍 نظام FSM',
    tabs: [
      { id: 'fsm', label: 'مستشعر البيئة FSM', icon: '🔍' },
      { id: 'voting', label: 'مجلس التصويت', icon: '⚖️' },
      { id: 'matrix', label: 'مصفوفة القرار', icon: '🧠' },
      { id: 'grid', label: 'الشبكة الذكية', icon: '🕸️' },
      { id: 'stateE', label: 'State E — أخبار', icon: '🚨' },
    ],
  },
  {
    group: '🌐 إدارة المحفظة',
    tabs: [
      { id: 'rating', label: 'تقييم الأعضاء', icon: '⭐' },
      { id: 'portfolio', label: 'Portfolio & Magic', icon: '🌐' },
      { id: 'recovery', label: 'Recovery Mode', icon: '🚑' },
      { id: 'dashboard', label: 'لوحة MT5', icon: '📊' },
      { id: 'telegram', label: 'Telegram Bot', icon: '📱' },
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
      { id: 'apiConfig', label: 'API Keys & Setup', icon: '🔑' },
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
  {
    group: '💻 الكود والإعداد',
    tabs: [
      { id: 'eaConfig', label: 'ضابط الإعدادات', icon: '⚙️', isNew: true },
      { id: 'freeSetup', label: 'الإعداد المجاني', icon: '✨' },
      { id: 'freeCode', label: 'الكود المجاني', icon: '📝' },
      { id: 'code', label: 'كود MQL5 كامل', icon: '💻' },
      { id: 'improvements', label: 'خارطة الطريق', icon: '🚀' },
    ],
  },
];

export default function AppAdvanced() {
  const [activeTab, setActiveTab] = useState('home');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const allTabs = TAB_GROUPS.flatMap(g => g.tabs);

  const filteredGroups = searchQuery
    ? [{
        group: '🔎 نتائج البحث',
        tabs: allTabs.filter(t =>
          t.label.includes(searchQuery) || t.id.toLowerCase().includes(searchQuery.toLowerCase())
        ),
      }]
    : TAB_GROUPS;

  const activeTabInfo = allTabs.find(t => t.id === activeTab);

  const renderContent = () => {
    switch (activeTab) {
      case 'home': return <HomePage onNavigate={setActiveTab} />;
      case 'commandCenter': return <CommandCenter />;
      case 'liveDash': return <LiveDashboard />;
      case 'pairsTable': return <PairsStatusTable />;
      case 'signalGenerator': return <SignalGenerator />;
      case 'backtester': return <BacktestSimulator />;
      case 'performanceReport': return <PerformanceReport />;
      case 'advancedAnalytics': return <AdvancedAnalytics />;
      case 'openbb': return <OpenBBDashboard />;
      case 'eaConfig': return <EAConfigurator />;
      case 'fsm': return <FSMExplainer />;
      case 'voting': return <VotingSystem />;
      case 'matrix': return <DecisionMatrix />;
      case 'grid': return <SmartGrid />;
      case 'stateE': return <StateE />;
      case 'rating': return <MemberRating />;
      case 'portfolio': return <PortfolioManager />;
      case 'recovery': return <RecoveryMode />;
      case 'dashboard': return <Dashboard />;
      case 'telegram': return <TelegramBot />;
      case 'aiAgents': return <AgentsOverview />;
      case 'agentCommTab': return <AgentCommunication />;
      case 'smc': return <SmartMoneyConcepts />;
      case 'mt5': return <MT5Integration />;
      case 'aiDashboard': return <AgentsDashboard />;
      case 'apiConfig': return <APIConfiguration />;
      case 'mlDashboard': return <MLDashboard />;
      case 'lstm': return <LSTMPredictor />;
      case 'rl': return <ReinforcementLearning />;
      case 'sentiment': return <SentimentAnalysis />;
      case 'freeSetup': return <FreeSetupGuide />;
      case 'freeCode': return <CompleteCode />;
      case 'code': return <AdvancedCode />;
      case 'improvements': return <Improvements />;
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
