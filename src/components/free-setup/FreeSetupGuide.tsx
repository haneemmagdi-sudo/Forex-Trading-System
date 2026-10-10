export default function FreeSetupGuide() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🆓 دليل الإعداد المجاني الكامل</h2>
        <p className="text-xl text-emerald-200 mb-4">
          نظام تداول احترافي بالكامل - بدون أي تكاليف شهرية!
        </p>
        <div className="bg-black/30 rounded-xl p-4">
          <p className="text-gray-300">
            ✨ <strong className="text-white">كل شيء محلي:</strong> بدون OpenAI، بدون رسوم، بدون اشتراكات!
          </p>
        </div>
      </div>

      {/* Step 1: Install Python */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/50">
            <span className="text-3xl">1️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">تثبيت Python</h3>
            <p className="text-blue-400">الخطوة الأولى - البنية التحتية</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-blue-400 font-semibold mb-4">📥 التحميل والتثبيت</h4>
            
            <ol className="space-y-3 text-gray-300">
              <li className="flex items-start gap-3">
                <span className="text-blue-400 font-bold">1.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">تحميل Python 3.11+</div>
                  <div className="bg-black/50 rounded p-3 mt-2">
                    <code className="text-xs text-blue-300">https://www.python.org/downloads/</code>
                  </div>
                  <p className="text-gray-400 text-sm mt-2">اختر "Add Python to PATH" أثناء التثبيت ✓</p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span className="text-blue-400 font-bold">2.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">التحقق من التثبيت</div>
                  <div className="bg-black/50 rounded p-3 mt-2">
                    <code className="text-xs text-gray-400">
python --version<br/>
# يجب أن يظهر: Python 3.11.x
                    </code>
                  </div>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span className="text-blue-400 font-bold">3.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">تثبيت المكتبات الأساسية</div>
                  <div className="bg-black/50 rounded p-3 mt-2">
                    <code className="text-xs text-gray-400">
pip install MetaTrader5<br/>
pip install pandas numpy<br/>
pip install python-telegram-bot<br/>
pip install schedule
                    </code>
                  </div>
                </div>
              </li>
            </ol>
          </div>
        </div>
      </div>

      {/* Step 2: MT5 Setup */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/50">
            <span className="text-3xl">2️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">إعداد MetaTrader 5</h3>
            <p className="text-emerald-400">الاتصال بحسابك</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <ol className="space-y-4 text-gray-300">
              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">1.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">تحميل MT5</div>
                  <div className="bg-black/50 rounded p-3 mt-2">
                    <code className="text-xs text-emerald-300">
https://www.icmarkets.com/mt5<br/>
# أو أي وسيط آخر تفضله
                    </code>
                  </div>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">2.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">فتح حساب Demo</div>
                  <p className="text-gray-400 text-sm mt-1">
                    من MT5 → File → Open an Account → Demo Account<br/>
                    رصيد موصى به: $10,000
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3">
                <span className="text-emerald-400 font-bold">3.</span>
                <div className="flex-1">
                  <div className="text-white font-semibold mb-1">احفظ بيانات الدخول</div>
                  <div className="bg-black/50 rounded p-3 mt-2">
                    <code className="text-xs text-gray-400">
Account: 12345678<br/>
Password: YourPassword123<br/>
Server: ICMarkets-Demo
                    </code>
                  </div>
                </div>
              </li>
            </ol>
          </div>
        </div>
      </div>

      {/* Step 3: Project Structure */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/50">
            <span className="text-3xl">3️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">بناء المشروع</h3>
            <p className="text-purple-400">هيكل الملفات</p>
          </div>
        </div>

        <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
          <h4 className="text-purple-400 font-semibold mb-4">📁 هيكل المجلدات</h4>
          
          <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
            <pre className="text-xs text-gray-300 font-mono">
{`quantum-trading-bot/
├── config/
│   ├── config.py          # الإعدادات الرئيسية
│   └── .env               # بيانات MT5 السرية
├── agents/
│   ├── fx_analyst.py      # الوكيل المحلل (بدون AI)
│   ├── strategy_planner.py
│   ├── execution_agent.py
│   └── monitor_agent.py
├── core/
│   ├── fsm.py             # نظام FSM
│   ├── voting.py          # نظام التصويت
│   └── risk_manager.py
├── utils/
│   ├── indicators.py      # المؤشرات الفنية
│   └── telegram_bot.py
├── logs/
│   └── trading.log
├── requirements.txt
└── main.py                # نقطة البداية`}
            </pre>
          </div>

          <div className="mt-4 bg-yellow-500/10 rounded-lg p-4 border border-yellow-400/30">
            <div className="text-yellow-400 font-semibold mb-2">💡 نصيحة:</div>
            <p className="text-gray-300 text-sm">
              سأعطيك كل الملفات جاهزة - فقط انسخ والصق!
            </p>
          </div>
        </div>
      </div>

      {/* Step 4: Configuration */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/50">
            <span className="text-3xl">4️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">ملفات الإعداد</h3>
            <p className="text-orange-400">جاهزة للنسخ</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* .env file */}
          <div className="bg-orange-500/10 rounded-2xl p-6 border border-orange-400/30">
            <h4 className="text-orange-400 font-semibold mb-4">📄 ملف .env</h4>
            <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
              <pre className="text-xs text-gray-300">
{`# ===== MT5 Configuration =====
MT5_ACCOUNT=12345678
MT5_PASSWORD=YourPassword123
MT5_SERVER=ICMarkets-Demo

# ===== AI Configuration (مجاني - بدون OpenAI) =====
USE_AI_ANALYST=False
USE_RULE_BASED_ANALYST=True

# ===== Trading Settings =====
RISK_PERCENT=2.0
MAX_DAILY_TRADES=5
MAX_OPEN_POSITIONS=3

# ===== Telegram Bot (مجاني) =====
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# ===== Advanced Features =====
USE_NEWS_FILTER=False
USE_FSM=True
USE_VOTING_SYSTEM=True
USE_SMART_GRID=True`}
              </pre>
            </div>
          </div>

          {/* config.py */}
          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-blue-400 font-semibold mb-4">📄 ملف config/config.py</h4>
            <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
              <pre className="text-xs text-gray-300">
{`import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MT5
    MT5_ACCOUNT = int(os.getenv('MT5_ACCOUNT'))
    MT5_PASSWORD = os.getenv('MT5_PASSWORD')
    MT5_SERVER = os.getenv('MT5_SERVER')
    
    # Trading
    RISK_PERCENT = float(os.getenv('RISK_PERCENT', 2.0))
    MAX_DAILY_TRADES = int(os.getenv('MAX_DAILY_TRADES', 5))
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', 3))
    
    # AI (مجاني)
    USE_AI_ANALYST = os.getenv('USE_AI_ANALYST', 'False') == 'True'
    USE_RULE_BASED_ANALYST = os.getenv('USE_RULE_BASED_ANALYST', 'True') == 'True'
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Features
    USE_FSM = True
    USE_VOTING_SYSTEM = True
    USE_SMART_GRID = True
    
    # Pairs
    TRADING_PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY']`}
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* Step 5: Telegram Setup */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/50">
            <span className="text-3xl">5️⃣</span>
          </div>
          <div>
            <h3 className="text-3xl font-bold text-white">إعداد Telegram Bot (اختياري)</h3>
            <p className="text-cyan-400">مجاني 100%</p>
          </div>
        </div>

        <div className="bg-cyan-500/10 rounded-2xl p-6 border border-cyan-400/30">
          <ol className="space-y-4 text-gray-300">
            <li className="flex items-start gap-3">
              <span className="text-cyan-400 font-bold">1.</span>
              <div className="flex-1">
                <div className="text-white font-semibold mb-1">ابحث عن @BotFather في Telegram</div>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <span className="text-cyan-400 font-bold">2.</span>
              <div className="flex-1">
                <div className="text-white font-semibold mb-1">أرسل: /newbot</div>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <span className="text-cyan-400 font-bold">3.</span>
              <div className="flex-1">
                <div className="text-white font-semibold mb-1">اختر اسم للبوت</div>
                <p className="text-gray-400 text-sm">مثال: MyTradingBot</p>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <span className="text-cyan-400 font-bold">4.</span>
              <div className="flex-1">
                <div className="text-white font-semibold mb-1">انسخ الـ Token</div>
                <div className="bg-black/50 rounded p-3 mt-2">
                  <code className="text-xs text-cyan-300">
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
                  </code>
                </div>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <span className="text-cyan-400 font-bold">5.</span>
              <div className="flex-1">
                <div className="text-white font-semibold mb-1">احصل على Chat ID</div>
                <div className="bg-black/50 rounded p-3 mt-2">
                  <code className="text-xs text-gray-400">
# افتح: https://api.telegram.org/bot[TOKEN]/getUpdates<br/>
# ابحث عن "chat":{"{"}"id": 987654321{"}"}
                  </code>
                </div>
              </div>
            </li>
          </ol>
        </div>
      </div>

      {/* Next Steps */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">✅ الخطوات التالية</h3>
        
        <div className="space-y-4">
          <div className="bg-black/30 rounded-xl p-4 flex items-center gap-3">
            <div className="text-3xl">📝</div>
            <div className="flex-1">
              <div className="text-white font-semibold">انتقل لتبويب "الكود الكامل"</div>
              <div className="text-gray-400 text-sm">احصل على جميع ملفات Python الجاهزة</div>
            </div>
          </div>

          <div className="bg-black/30 rounded-xl p-4 flex items-center gap-3">
            <div className="text-3xl">▶️</div>
            <div className="flex-1">
              <div className="text-white font-semibold">شغّل النظام</div>
              <div className="text-gray-400 text-sm">python main.py</div>
            </div>
          </div>

          <div className="bg-black/30 rounded-xl p-4 flex items-center gap-3">
            <div className="text-3xl">📊</div>
            <div className="flex-1">
              <div className="text-white font-semibold">راقب Dashboard</div>
              <div className="text-gray-400 text-sm">تابع أداء الوكلاء في الوقت الفعلي</div>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-emerald-500/20 rounded-xl p-6 border border-emerald-400/50">
          <div className="text-emerald-400 font-bold text-lg mb-2">🎉 مبروك!</div>
          <p className="text-gray-300">
            لديك الآن نظام تداول احترافي كامل - <strong className="text-white">مجاني 100%</strong> بدون أي رسوم شهرية!
          </p>
        </div>
      </div>
    </div>
  );
}
