import { useState, useRef, useEffect, useCallback } from 'react';
import { BACKEND_URL } from '../../utils/useBackend';
import { authHeaders } from '../../utils/auth';

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: Date;
  attachment?: {
    name: string;
    type: string;
    size: number;
  };
}

interface UploadedFile {
  name: string;
  type: string;
  size: number;
  content: string; // text content for the agent
}

const AGENT_PROFILES = {
  MarketAnalyst: {
    id: 'MarketAnalyst',
    name: 'الوكيل المحلل',
    role: 'Market Analyst',
    icon: '🔍',
    color: 'blue',
    desc: 'مراقب حركة السعر، كتل الأوامر (Order Blocks)، الفجوات السعرية (FVG)، وتوليد إشارات الدخول.',
    bgColor: 'from-blue-500/10 to-cyan-500/5',
    borderColor: 'border-blue-500/30',
    textColor: 'text-blue-300',
    accentColor: 'bg-blue-500',
    badgeBg: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    suggestions: [
      'ما هو التحليل الفني لزوج EURUSD حالياً؟',
      'هل توجد أي كتل أوامر (Order Blocks) قوية مرصودة؟',
      'ما هي حالة اتجاه السوق العام والـ FSM Regime؟'
    ]
  },
  ExecutionAgent: {
    id: 'ExecutionAgent',
    name: 'الوكيل المنفذ',
    role: 'Execution Agent',
    icon: '⚡',
    color: 'emerald',
    desc: 'المسؤول عن إرسال الأوامر لـ MetaTrader 5، حساب حجم اللوت الأمثل، وإدارة سبريد الدخول.',
    bgColor: 'from-emerald-500/10 to-teal-500/5',
    borderColor: 'border-emerald-500/30',
    textColor: 'text-emerald-300',
    accentColor: 'bg-emerald-500',
    badgeBg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    suggestions: [
      'ما هي قواعد إدارة المخاطر وحجم اللوت المطبقة الآن؟',
      'هل هناك عوائق أو انزلاقات سعرية تمنع التنفيذ حالياً؟',
      'كيف تحسب وقف الخسارة وجني الأرباح ديناميكياً؟'
    ]
  },
  MonitorAgent: {
    id: 'MonitorAgent',
    name: 'الوكيل المراقب',
    role: 'Monitor Agent',
    icon: '👁️',
    color: 'orange',
    desc: 'الحارس الأمين للصفقات المفتوحة، تعديل الستوب لوس ديناميكياً (Trailing Stop) وتأمين الربح.',
    bgColor: 'from-orange-500/10 to-amber-500/5',
    borderColor: 'border-orange-500/30',
    textColor: 'text-orange-300',
    accentColor: 'bg-orange-500',
    badgeBg: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    suggestions: [
      'ما هي حالة التراجع (Drawdown) الحالية للحساب؟',
      'هل قمت بتفعيل وقف الخسارة المتحرك (Trailing Stop) لأي صفقة؟',
      'كيف تتعامل مع الصفقات العاكسة لتأمين الحساب من التسييل؟'
    ]
  },
  LearningAgent: {
    id: 'LearningAgent',
    name: 'الوكيل المتعلم',
    role: 'Learning Agent',
    icon: '🧠',
    color: 'purple',
    desc: 'محلل صفقات المحفظة التاريخية باستخدام التعلم الآلي وتحديث أوزان المؤشرات.',
    bgColor: 'from-purple-500/10 to-violet-500/5',
    borderColor: 'border-purple-500/30',
    textColor: 'text-purple-300',
    accentColor: 'bg-purple-500',
    badgeBg: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    suggestions: [
      'ما هي دقة نموذج التعلم الآلي (GradientBoosting) الأخيرة؟',
      'ما هو Regime السوق الأكثر ربحية بناءً على تحليلك التاريخي؟',
      'هل قمت بتعديل أوزان تصويت المؤشرات الفنية مؤخراً؟'
    ]
  },
  NewsAgent: {
    id: 'NewsAgent',
    name: 'وكيل الأخبار',
    role: 'News Agent',
    icon: '📰',
    color: 'pink',
    desc: 'فاحص البيانات الاقتصادية الكبرى، تفعيل درع الأخبار لحظر التداول وقت التقلبات الحادة.',
    bgColor: 'from-pink-500/10 to-rose-500/5',
    borderColor: 'border-pink-500/30',
    textColor: 'text-pink-300',
    accentColor: 'bg-pink-500',
    badgeBg: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
    suggestions: [
      'هل توجد أخبار عالية التأثير (HIGH Impact) مرتقبة اليوم؟',
      'ما هو مؤشر معنويات الأخبار الحالي لزوج EURUSD؟',
      'هل درع حماية الأخبار (News Shield) نشط حالياً؟'
    ]
  },
  StrategyPlanner: {
    id: 'StrategyPlanner',
    name: 'المخطط الاستراتيجي',
    role: 'Strategy Planner',
    icon: '🎯',
    color: 'teal',
    desc: 'تصميم استراتيجيات دخول دقيقة باستخدام SMC، حساب حجم اللوت الأمثل، وتحديد SL/TP هندسياً.',
    bgColor: 'from-teal-500/10 to-cyan-500/5',
    borderColor: 'border-teal-500/30',
    textColor: 'text-teal-300',
    accentColor: 'bg-teal-500',
    badgeBg: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
    suggestions: [
      'صمّم لي استراتيجية دخول كاملة لأفضل زوج عملات الآن مع SL وTP محددين.',
      'ما هو حجم اللوت الأمثل للصفقة القادمة بناءً على رصيدي الحالي؟',
      'حدد لي Order Block أو FVG نشط يمكن الدخول عنده الآن بنسبة R:R ≥ 1.5؟'
    ]
  }
} as const;

type AgentKey = keyof typeof AGENT_PROFILES;

// ── Accepted file types ──────────────────────────────────────────────────
const ACCEPTED_TYPES = [
  '.txt', '.md', '.csv', '.json', '.pdf',
  '.doc', '.docx', '.xls', '.xlsx',
  '.py', '.js', '.ts', '.html', '.xml'
].join(',');

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileEmoji(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    pdf: '📄', doc: '📝', docx: '📝',
    xls: '📊', xlsx: '📊', csv: '📊',
    txt: '📃', md: '📃',
    py: '🐍', js: '⚙️', ts: '⚙️',
    json: '🗂️', xml: '🗂️', html: '🌐',
  };
  return map[ext] || '📎';
}

// ── Attempt to read file content as text ─────────────────────────────────
function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve) => {
    const textTypes = [
      'text/', 'application/json', 'application/xml',
      'application/javascript',
    ];
    const isText = textTypes.some(t => file.type.startsWith(t))
      || /\.(txt|md|csv|json|xml|py|js|ts|html)$/i.test(file.name);

    if (!isText || file.size > 500_000) {
      // For binary / large files just return metadata
      resolve(`[ملف: ${file.name} | الحجم: ${formatBytes(file.size)} | النوع: ${file.type || 'غير معروف'}]`);
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target?.result as string || '');
    reader.onerror = () => resolve(`[تعذّر قراءة الملف: ${file.name}]`);
    reader.readAsText(file, 'utf-8');
  });
}

export default function AgentCommunication() {
  const [selectedAgent, setSelectedAgent] = useState<AgentKey>('MarketAnalyst');
  const [inputMessage, setInputMessage] = useState('');
  const [conversations, setConversations] = useState<Record<AgentKey, Message[]>>({
    MarketAnalyst: [{
      id: 'welcome-analyst', sender: 'agent', timestamp: new Date(),
      text: 'أهلاً بك! أنا الوكيل المحلل المالي الخاص بك. أقوم بفحص الأسواق ورصد كتل الأوامر والمؤشرات الفنية لمساعدتك. يمكنك أيضاً رفع تقارير أو ملفات بيانات لأراجعها. كيف يمكنني إفادتك اليوم؟'
    }],
    ExecutionAgent: [{
      id: 'welcome-executor', sender: 'agent', timestamp: new Date(),
      text: 'مرحباً. أنا الوكيل المنفذ. مهمتي إدارة الصفقات المنفذة وحجم اللوت وتنسيق الأوامر مع خادم MetaTrader 5 بدقة وأمان. يمكنك رفع ملفات الاستراتيجية أو التقارير لأراجعها.'
    }],
    MonitorAgent: [{
      id: 'welcome-monitor', sender: 'agent', timestamp: new Date(),
      text: 'أهلاً. أنا الوكيل المراقب. مهمتي تأمين محفظتك ومراقبة الصفقات المفتوحة 24/7. يمكنك رفع تقارير أداء أو ملفات بيانات لأحللها.'
    }],
    LearningAgent: [{
      id: 'welcome-learner', sender: 'agent', timestamp: new Date(),
      text: 'أهلاً بك. أنا وكيل التعلم المستمر. أقوم بتحليل البيانات وإحصائيات التداول. ارفع مقالات تعليمية أو تقارير بحثية أو ملفات CSV للصفقات لأتعلم منها وأحسّن قراراتي!'
    }],
    StrategyPlanner: [
      {
        id: 'welcome-planner', sender: 'agent', timestamp: new Date(),
        text: 'أهلاً بك! أنا المخطط الاستراتيجي. مهمتي تصميم خطط تداول دقيقة بناءً على بيانات السوق الحية. أستطيع تحديد نقاط الدخول الأمثل، حساب SL/TP هندسياً، ورصد Order Blocks و Fair Value Gaps (FVG). شاركني أي زوج أو سهم لأصمم لك الاستراتيجية الأمثل الآن!'
      }
    ],
    NewsAgent: [{
      id: 'welcome-news', sender: 'agent', timestamp: new Date(),
      text: 'مرحباً. أنا وكيل الأخبار. أتابع التقويم الاقتصادي ومصادر الأخبار العالمية وأقوم بفرض حظر التداول لتأمين حسابك أثناء الأحداث العنيفة. اسألني عن الأخبار الحالية.'
    }]
  });
  const [loading, setLoading] = useState(false);

  // ── File Upload State ────────────────────────────────────────────────
  const [pendingFile, setPendingFile] = useState<UploadedFile | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeProfile = AGENT_PROFILES[selectedAgent];
  const activeChat = conversations[selectedAgent];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat, loading]);

  // ── File processing ──────────────────────────────────────────────────
  const processFile = useCallback(async (file: File) => {
    setUploadError(null);
    const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
    if (file.size > MAX_SIZE) {
      setUploadError(`حجم الملف ${formatBytes(file.size)} يتجاوز الحد الأقصى (10 MB)`);
      return;
    }
    const content = await readFileAsText(file);
    setPendingFile({ name: file.name, type: file.type, size: file.size, content });
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await processFile(file);
    // Reset input so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [processFile]);

  // ── Drag & Drop ──────────────────────────────────────────────────────
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) await processFile(file);
  }, [processFile]);

  const removePendingFile = () => {
    setPendingFile(null);
    setUploadError(null);
  };

  // ── Send Message ─────────────────────────────────────────────────────
  const handleSendMessage = async (textToSend: string, file?: UploadedFile | null) => {
    const hasText = textToSend.trim().length > 0;
    const hasFile = !!file;
    if ((!hasText && !hasFile) || loading) return;

    // Build the combined message text
    let combinedText = textToSend.trim();
    let fullMessageForAPI = textToSend.trim();

    if (hasFile) {
      // UI label
      combinedText = combinedText
        ? `${combinedText}\n\n📎 ${file!.name}`
        : `📎 ${file!.name}`;

      // API payload includes file content (truncated to 8000 chars to fit LLM)
      const preview = file!.content.length > 8000
        ? file!.content.slice(0, 8000) + '\n\n[... تم قطع المحتوى لتجاوزه الحد المسموح ...]'
        : file!.content;

      fullMessageForAPI = fullMessageForAPI
        ? `${fullMessageForAPI}\n\n---\n📎 محتوى الملف المرفق (${file!.name}):\n\n${preview}`
        : `راجع الملف التالي وقدّم تحليلك:\n\n📎 اسم الملف: ${file!.name}\n\n${preview}`;
    }

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: combinedText,
      timestamp: new Date(),
      ...(hasFile ? { attachment: { name: file!.name, type: file!.type, size: file!.size } } : {})
    };

    setConversations(prev => ({
      ...prev,
      [selectedAgent]: [...prev[selectedAgent], userMsg]
    }));
    setInputMessage('');
    setPendingFile(null);
    setUploadError(null);
    setLoading(true);

    let rejection = '';
    try {
      const res = await fetch(`${BACKEND_URL}/api/agents/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ agent: selectedAgent, message: fullMessageForAPI })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        if (typeof body?.detail === 'string') rejection = body.detail;
        throw new Error(`HTTP Error ${res.status}`);
      }
      const data = await res.json();
      const replyText = data.response || 'عذراً، لم أتمكن من الحصول على رد مناسب.';
      setConversations(prev => ({
        ...prev,
        [selectedAgent]: [...prev[selectedAgent], {
          id: `agent-${Date.now()}`, sender: 'agent', text: replyText, timestamp: new Date()
        }]
      }));
    } catch (error) {
      console.error(error);
      setConversations(prev => ({
        ...prev,
        [selectedAgent]: [...prev[selectedAgent], {
          id: `error-${Date.now()}`, sender: 'agent', timestamp: new Date(),
          text: rejection
            ? `⚠️ ${rejection}`
            : '⚠️ فشل الاتصال بالخادم. تأكد من تشغيل الـ Backend وعمل خادم التطبيق بنجاح لتتمكن من محادثة الوكلاء.'
        }]
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[calc(100vh-140px)] animate-fadeIn"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* ── Drag-Over Overlay ──────────────────────────────────────── */}
      {isDragOver && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-purple-900/40 backdrop-blur-sm border-4 border-dashed border-purple-400/60 pointer-events-none">
          <div className="text-center">
            <div className="text-6xl mb-4">📂</div>
            <p className="text-white font-bold text-2xl">أفلت الملف هنا لرفعه</p>
            <p className="text-purple-300 text-sm mt-2">سيتم إرساله إلى {activeProfile.name} للمراجعة</p>
          </div>
        </div>
      )}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={handleFileSelect}
        className="hidden"
        id="agent-file-upload"
      />

      {/* ── Agent Sidebar ──────────────────────────────────────────── */}
      <div className="lg:col-span-4 flex flex-col gap-3">
        <div className="bg-black/40 border border-purple-500/20 rounded-2xl p-5 backdrop-blur-xl">
          <h3 className="text-white font-bold text-lg mb-2 flex items-center gap-2">
            <span>🤖</span> فريق الوكلاء الذكي
          </h3>
          <p className="text-gray-400 text-xs leading-relaxed">
            اضغط على أي وكيل لبدء محادثة مباشرة معه. يمكنك أيضاً رفع تقارير أو مقالات أو ملفات بيانات ليقوموا بمراجعتها والتعلم منها.
          </p>
          {/* Upload hint box */}
          <div className="mt-3 p-3 rounded-xl bg-purple-500/5 border border-purple-500/15 flex items-start gap-2">
            <span className="text-purple-400 text-lg mt-0.5">📎</span>
            <div>
              <p className="text-purple-300 text-xs font-semibold mb-0.5">رفع ملفات للوكلاء</p>
              <p className="text-gray-500 text-[10px] leading-relaxed">
                PDF، Word، Excel، CSV، TXT، Markdown، Python، JSON وغيرها.
                اسحب وأفلت الملف في أي مكان أو اضغط على أيقونة 📎 في شريط الإرسال.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          {Object.entries(AGENT_PROFILES).map(([key, p]) => {
            const isSelected = selectedAgent === key;
            return (
              <button
                key={key}
                onClick={() => setSelectedAgent(key as AgentKey)}
                className={`w-full text-right p-4 rounded-2xl border transition-all duration-300 flex items-start gap-4 ${
                  isSelected
                    ? `${p.bgColor} ${p.borderColor} shadow-lg shadow-${p.color}-500/5`
                    : 'bg-black/20 border-white/5 hover:bg-white/5 text-gray-400 hover:text-white'
                }`}
              >
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br from-black/40 to-black/80 border ${isSelected ? p.borderColor : 'border-white/10'} flex items-center justify-center text-2xl flex-shrink-0 shadow-inner`}>
                  {p.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-white font-bold text-sm">{p.name}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${p.badgeBg}`}>{p.role}</span>
                  </div>
                  <p className="text-gray-500 text-xs truncate mt-1 leading-normal">{p.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Chat Area ──────────────────────────────────────────────── */}
      <div className="lg:col-span-8 bg-black/40 border border-purple-500/20 rounded-3xl flex flex-col backdrop-blur-xl overflow-hidden relative min-h-[500px]">

        {/* Chat Header */}
        <div className={`p-4 border-b border-purple-500/20 flex items-center justify-between bg-gradient-to-l ${activeProfile.bgColor}`}>
          <div className="flex items-center gap-3">
            <span className="text-3xl">{activeProfile.icon}</span>
            <div>
              <h4 className="text-white font-bold text-sm flex items-center gap-2">
                {activeProfile.name}
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              </h4>
              <p className="text-gray-400 text-xs mt-0.5">{activeProfile.role} · متصل حالياً</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Upload button in header */}
            <button
              onClick={() => fileInputRef.current?.click()}
              title="رفع ملف للوكيل (PDF، Word، CSV، TXT، ...)"
              className="px-3 py-1.5 rounded-xl border border-white/10 bg-white/5 hover:bg-purple-500/20 hover:border-purple-500/30 text-xs text-gray-400 hover:text-purple-300 transition-all flex items-center gap-1.5 group"
            >
              <svg className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              رفع ملف
            </button>
            <button
              onClick={() => setConversations(prev => ({ ...prev, [selectedAgent]: [prev[selectedAgent][0]] }))}
              className="px-3 py-1.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs text-gray-400 hover:text-white transition-all flex items-center gap-1.5"
              title="مسح سجل المحادثة"
            >
              🧹 مسح
            </button>
          </div>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 max-h-[460px]">
          {activeChat.map((msg) => {
            const isUser = msg.sender === 'user';
            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-[85%] ${isUser ? 'mr-auto flex-row-reverse' : 'ml-auto'}`}
              >
                {/* Avatar */}
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${
                  isUser ? 'bg-purple-600/30 border border-purple-500/30' : `bg-black/35 border ${activeProfile.borderColor}`
                }`}>
                  {isUser ? '👤' : activeProfile.icon}
                </div>

                {/* Bubble */}
                <div className={`rounded-2xl p-4 text-sm leading-relaxed ${
                  isUser
                    ? 'bg-purple-600/20 border border-purple-500/30 text-purple-100 rounded-tr-none'
                    : 'bg-white/5 border border-white/10 text-gray-200 rounded-tl-none'
                }`}>
                  <p className="whitespace-pre-line">{msg.text}</p>

                  {/* Attachment badge */}
                  {msg.attachment && (
                    <div className="mt-2.5 flex items-center gap-2 px-3 py-2 rounded-xl bg-black/30 border border-white/10 w-fit">
                      <span className="text-base">{getFileEmoji(msg.attachment.name)}</span>
                      <div>
                        <p className="text-xs text-gray-300 font-medium truncate max-w-[180px]">{msg.attachment.name}</p>
                        <p className="text-[10px] text-gray-500">{formatBytes(msg.attachment.size)}</p>
                      </div>
                    </div>
                  )}

                  <span className="text-[9px] text-gray-500 block text-left mt-2 font-mono">
                    {msg.timestamp.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            );
          })}

          {/* Thinking Indicator */}
          {loading && (
            <div className="flex gap-3 max-w-[85%] ml-auto">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-lg flex-shrink-0 bg-black/35 border ${activeProfile.borderColor}`}>
                {activeProfile.icon}
              </div>
              <div className="bg-white/5 border border-white/10 rounded-2xl rounded-tl-none p-4 text-sm text-gray-400 flex items-center gap-2">
                <span>جاري معالجة طلبك وكتابة الرد</span>
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-100" />
                  <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-200" />
                  <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-300" />
                </span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Questions */}
        <div className="px-4 pt-3 pb-2 bg-black/20 border-t border-purple-500/10">
          <div className="text-gray-500 text-xs font-bold mb-2">💡 أسئلة مقترحة سريعة:</div>
          <div className="flex flex-wrap gap-2">
            {activeProfile.suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(s, pendingFile)}
                disabled={loading}
                className="px-3 py-2 rounded-xl bg-white/5 hover:bg-purple-500/10 border border-white/5 hover:border-purple-500/20 text-gray-300 hover:text-purple-300 text-xs text-right transition-all duration-200 disabled:opacity-40 disabled:pointer-events-none"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* ── Pending File Preview ─────────────────────────────────── */}
        {(pendingFile || uploadError) && (
          <div className="px-4 py-2 bg-black/30 border-t border-purple-500/10">
            {uploadError && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
                <span>⚠️</span>
                <span className="flex-1">{uploadError}</span>
                <button onClick={() => setUploadError(null)} className="hover:text-red-200">✕</button>
              </div>
            )}
            {pendingFile && !uploadError && (
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-purple-500/10 border border-purple-500/25 animate-fadeIn">
                <span className="text-2xl">{getFileEmoji(pendingFile.name)}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-purple-200 text-xs font-semibold truncate">{pendingFile.name}</p>
                  <p className="text-gray-500 text-[10px]">
                    {formatBytes(pendingFile.size)} · جاهز للإرسال إلى {activeProfile.name}
                  </p>
                </div>
                <button
                  onClick={removePendingFile}
                  title="إلغاء الملف"
                  className="w-6 h-6 rounded-full bg-red-500/20 hover:bg-red-500/40 border border-red-500/30 text-red-300 flex items-center justify-center text-xs transition-all flex-shrink-0"
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Chat Input ───────────────────────────────────────────── */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(inputMessage, pendingFile);
          }}
          className="p-4 border-t border-purple-500/20 bg-black/50 flex gap-2 items-center"
        >
          {/* 📎 File Upload Icon Button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            title="رفع ملف أو تقرير أو مقال للوكيل (PDF، Word، CSV، TXT، Markdown، Python، JSON...)"
            className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 transition-all duration-200 group ${
              pendingFile
                ? 'bg-purple-500/25 border-purple-400/50 text-purple-300 shadow-md shadow-purple-500/10'
                : 'bg-white/5 border-white/10 text-gray-400 hover:bg-purple-500/15 hover:border-purple-500/30 hover:text-purple-300'
            }`}
          >
            {pendingFile ? (
              /* Filled paperclip when file is attached */
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/>
              </svg>
            ) : (
              /* Outline paperclip when no file */
              <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            )}
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={loading}
            placeholder={
              pendingFile
                ? `أضف تعليقاً على "${pendingFile.name}" أو اضغط إرسال مباشرة...`
                : `اكتب رسالتك إلى ${activeProfile.name} هنا...`
            }
            className="flex-1 bg-black/40 border border-white/10 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-purple-500 placeholder-gray-600 disabled:opacity-50 transition-colors"
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={(!inputMessage.trim() && !pendingFile) || loading}
            className={`px-5 h-10 rounded-xl text-white font-bold text-sm flex items-center gap-1.5 transition-all flex-shrink-0 ${
              (!inputMessage.trim() && !pendingFile) || loading
                ? 'bg-purple-900/30 text-gray-500 border border-purple-500/10 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-500 border border-purple-400/30 hover:scale-105 active:scale-95 shadow-lg shadow-purple-500/20'
            }`}
          >
            <span>ارسل</span>
            <span>{pendingFile && !inputMessage.trim() ? '📎' : '🚀'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
