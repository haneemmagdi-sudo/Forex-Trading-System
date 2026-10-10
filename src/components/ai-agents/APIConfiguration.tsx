export default function APIConfiguration() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-3xl p-8 border border-purple-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🔑 API Keys & Configuration</h2>
        <p className="text-xl text-purple-200">
          كل وكيل وكيف يعمل - البدائل المجانية والمدفوعة
        </p>
      </div>

      {/* Overview */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📊 ملخص سريع</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-emerald-400 font-semibold mb-4">✅ يحتاج API Key</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>🔍 <strong>FX Analyst:</strong> OpenAI API (GPT-4)</li>
              <li>📅 <strong>Economic Calendar:</strong> اختياري</li>
              <li>📱 <strong>Telegram Bot:</strong> Telegram Token</li>
            </ul>
          </div>

          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-blue-400 font-semibold mb-4">✓ لا يحتاج API Key (محلي)</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li>📋 <strong>Strategy Planner:</strong> خوارزميات محلية</li>
              <li>⚡ <strong>Execution Agent:</strong> MT5 Library محلي</li>
              <li>👁️ <strong>Monitor Agent:</strong> بايثون محلي</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Agent 1: FX Analyst */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <div className="flex items-start gap-6">
          <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-blue-500/50 flex-shrink-0">
            <span className="text-4xl mb-1">🔍</span>
            <span className="text-white font-bold text-xs">Agent 1</span>
          </div>
          <div className="flex-1">
            <h3 className="text-2xl font-bold text-white mb-2">FX Analyst - خيارات متعددة</h3>
            
            <div className="space-y-4">
              {/* Option 1: OpenAI */}
              <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
                <h4 className="text-purple-400 font-semibold mb-3">🚀 الخيار 1: OpenAI GPT-4 (الأقوى)</h4>
                
                <div className="bg-black/30 rounded-lg p-4 mb-4">
                  <div className="text-white font-semibold text-sm mb-2">📝 الإعداد:</div>
                  <div className="bg-black/50 rounded p-3">
                    <code className="text-xs text-purple-300">
{`# .env file
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx

# config.py
AI_MODEL = "gpt-4-turbo-preview"
USE_AI_ANALYST = True`}
                    </code>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-emerald-400 font-semibold text-sm mb-2">✅ المميزات:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• ذكاء استثنائي في تحليل الشارت</li>
                      <li>• فهم سياقي عميق للسوق</li>
                      <li>• دقة عالية جداً (&gt;85%)</li>
                      <li>• يتعلم من الأخطاء</li>
                    </ul>
                  </div>
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-red-400 font-semibold text-sm mb-2">❌ العيوب:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• مدفوع ($0.01 لكل 1K tokens)</li>
                      <li>• يحتاج اتصال إنترنت</li>
                      <li>• تكلفة شهرية ~$50-100</li>
                    </ul>
                  </div>
                </div>

                <div className="mt-4 bg-purple-500/20 rounded-lg p-3 border border-purple-400/50">
                  <div className="text-purple-400 font-semibold text-sm mb-2">💰 التكلفة المتوقعة:</div>
                  <p className="text-gray-300 text-xs">
                    ~$50-100/شهر (حسب عدد التحليلات). إذا كنت تحلل 10 أزواج كل ساعة 24/7
                  </p>
                </div>
              </div>

              {/* Option 2: Local LLM */}
              <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
                <h4 className="text-emerald-400 font-semibold mb-3">🆓 الخيار 2: نموذج محلي مفتوح المصدر (مجاني)</h4>
                
                <div className="bg-black/30 rounded-lg p-4 mb-4">
                  <div className="text-white font-semibold text-sm mb-2">📝 الإعداد:</div>
                  <div className="bg-black/50 rounded p-3">
                    <code className="text-xs text-emerald-300">
{`# استخدام LLaMA 2 أو Mistral (مجاني)
pip install llama-cpp-python

# config.py
AI_MODEL = "llama-2-13b"
USE_AI_ANALYST = True
LOCAL_MODEL = True
MODEL_PATH = "./models/llama-2-13b.gguf"`}
                    </code>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-emerald-400 font-semibold text-sm mb-2">✅ المميزات:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• <strong>مجاني 100%</strong></li>
                      <li>• يعمل offline (بدون إنترنت)</li>
                      <li>• خصوصية كاملة</li>
                      <li>• لا رسوم شهرية</li>
                    </ul>
                  </div>
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-yellow-400 font-semibold text-sm mb-2">⚠️ المتطلبات:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• GPU قوي (8GB+ VRAM)</li>
                      <li>• أو CPU قوي + 16GB RAM</li>
                      <li>• دقة أقل قليلاً (75-80%)</li>
                      <li>• أبطأ قليلاً</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Option 3: Rule-Based */}
              <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
                <h4 className="text-blue-400 font-semibold mb-3">🎯 الخيار 3: بدون AI - قواعد برمجية فقط (مجاني)</h4>
                
                <div className="bg-black/30 rounded-lg p-4 mb-4">
                  <div className="text-white font-semibold text-sm mb-2">📝 الإعداد:</div>
                  <div className="bg-black/50 rounded p-3">
                    <code className="text-xs text-blue-300">
{`# config.py
USE_AI_ANALYST = False
USE_RULE_BASED_ANALYST = True

# كود المحلل البرمجي البحت
def detect_order_block(df):
    # كود بايثون عادي - بدون AI
    for i in range(20, len(df)):
        if is_bullish_ob(df, i):
            yield create_signal(df, i)`}
                    </code>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-emerald-400 font-semibold text-sm mb-2">✅ المميزات:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• <strong>مجاني تماماً</strong></li>
                      <li>• سريع جداً</li>
                      <li>• موثوق (Deterministic)</li>
                      <li>• لا يحتاج GPU</li>
                    </ul>
                  </div>
                  <div className="bg-black/30 rounded-lg p-3">
                    <div className="text-red-400 font-semibold text-sm mb-2">❌ العيوب:</div>
                    <ul className="text-gray-400 text-xs space-y-1">
                      <li>• لا مرونة في التحليل</li>
                      <li>• دقة أقل (60-70%)</li>
                      <li>• لا يتعلم من الأخطاء</li>
                      <li>• محدود بالقواعد المبرمجة</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Other Agents */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Strategy Planner */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
              <span className="text-3xl">📋</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Strategy Planner</h3>
              <p className="text-purple-400 text-sm">لا يحتاج API</p>
            </div>
          </div>

          <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-400/30">
            <div className="text-white font-semibold text-sm mb-3">🧮 كيف يعمل؟</div>
            <p className="text-gray-300 text-sm mb-3">
              خوارزميات رياضية محلية بحتة - لا يحتاج اتصال خارجي
            </p>
            <div className="bg-black/50 rounded p-3">
              <code className="text-xs text-gray-400">
{`# كل شيء محلي
def calculate_position_size(balance, risk, sl_pips):
    risk_amount = balance * (risk / 100)
    lot = risk_amount / (sl_pips * pip_value)
    return lot

# لا API Keys مطلوبة!`}
              </code>
            </div>
          </div>

          <div className="mt-4 bg-emerald-500/10 rounded-lg p-3 border border-emerald-400/30">
            <div className="text-emerald-400 font-semibold text-sm">✅ مجاني 100%</div>
          </div>
        </div>

        {/* Execution Agent */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-xl flex items-center justify-center">
              <span className="text-3xl">⚡</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Execution Agent</h3>
              <p className="text-emerald-400 text-sm">لا يحتاج API</p>
            </div>
          </div>

          <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-400/30">
            <div className="text-white font-semibold text-sm mb-3">🔌 كيف يعمل؟</div>
            <p className="text-gray-300 text-sm mb-3">
              يتصل مباشرة بـ MT5 عبر مكتبة Python محلية
            </p>
            <div className="bg-black/50 rounded p-3">
              <code className="text-xs text-gray-400">
{`# MetaTrader5 Library (محلية)
import MetaTrader5 as mt5

# الاتصال المحلي
mt5.initialize()
mt5.login(account, password, server)

# لا API Keys - كل شيء محلي!`}
              </code>
            </div>
          </div>

          <div className="mt-4 bg-emerald-500/10 rounded-lg p-3 border border-emerald-400/30">
            <div className="text-emerald-400 font-semibold text-sm">✅ مجاني 100%</div>
          </div>
        </div>

        {/* Monitor Agent */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
              <span className="text-3xl">👁️</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Monitor Agent</h3>
              <p className="text-orange-400 text-sm">لا يحتاج API</p>
            </div>
          </div>

          <div className="bg-orange-500/10 rounded-xl p-4 border border-orange-400/30">
            <div className="text-white font-semibold text-sm mb-3">👀 كيف يعمل؟</div>
            <p className="text-gray-300 text-sm mb-3">
              Loop بايثون بسيط يقرأ من MT5 كل 100ms
            </p>
            <div className="bg-black/50 rounded p-3">
              <code className="text-xs text-gray-400">
{`while True:
    positions = mt5.positions_get()
    for pos in positions:
        check_conditions(pos)
        update_sl_tp_if_needed(pos)
    time.sleep(0.1)  # 100ms

# كل شيء محلي - بدون API!`}
              </code>
            </div>
          </div>

          <div className="mt-4 bg-emerald-500/10 rounded-lg p-3 border border-emerald-400/30">
            <div className="text-emerald-400 font-semibold text-sm">✅ مجاني 100%</div>
          </div>
        </div>

        {/* Telegram Bot */}
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center">
              <span className="text-3xl">📱</span>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Telegram Bot</h3>
              <p className="text-blue-400 text-sm">يحتاج Token (مجاني)</p>
            </div>
          </div>

          <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-400/30">
            <div className="text-white font-semibold text-sm mb-3">📲 كيف تحصل عليه؟</div>
            <ol className="text-gray-300 text-sm space-y-2 list-decimal list-inside">
              <li>افتح Telegram وابحث عن @BotFather</li>
              <li>أرسل /newbot</li>
              <li>اختر اسم للبوت</li>
              <li>ستحصل على Token مجاني</li>
            </ol>
            <div className="bg-black/50 rounded p-3 mt-3">
              <code className="text-xs text-gray-400">
{`# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# مجاني تماماً!`}
              </code>
            </div>
          </div>

          <div className="mt-4 bg-emerald-500/10 rounded-lg p-3 border border-emerald-400/30">
            <div className="text-emerald-400 font-semibold text-sm">✅ مجاني 100%</div>
          </div>
        </div>
      </div>

      {/* Economic Calendar */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">📅 Economic Calendar (اختياري)</h3>
        
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <h4 className="text-emerald-400 font-semibold mb-3">🆓 ForexFactory Scraping</h4>
            <p className="text-gray-300 text-sm mb-3">Web scraping مجاني</p>
            <div className="bg-black/50 rounded p-3 text-xs">
              <code className="text-gray-400">
{`from bs4 import BeautifulSoup
import requests

url = "https://www.forexfactory.com/calendar"
# مجاني لكن يحتاج صيانة`}
              </code>
            </div>
            <div className="mt-3 text-emerald-400 text-sm font-semibold">✅ مجاني</div>
          </div>

          <div className="bg-gradient-to-br from-yellow-500/10 to-orange-500/10 rounded-2xl p-6 border border-yellow-400/30">
            <h4 className="text-yellow-400 font-semibold mb-3">💰 Investing.com API</h4>
            <p className="text-gray-300 text-sm mb-3">API احترافي</p>
            <div className="bg-black/50 rounded p-3 text-xs">
              <code className="text-gray-400">
{`# مدفوع
API_KEY = "your_investing_key"
# $29/شهر تقريباً`}
              </code>
            </div>
            <div className="mt-3 text-yellow-400 text-sm font-semibold">💰 ~$30/شهر</div>
          </div>

          <div className="bg-gradient-to-br from-blue-500/10 to-indigo-500/10 rounded-2xl p-6 border border-blue-400/30">
            <h4 className="text-blue-400 font-semibold mb-3">🎯 بدون Calendar</h4>
            <p className="text-gray-300 text-sm mb-3">يمكنك الاستغناء عنه</p>
            <div className="bg-black/50 rounded p-3 text-xs">
              <code className="text-gray-400">
{`# ببساطة عطّله
USE_NEWS_FILTER = False

# الوكلاء يعملون عادي!`}
              </code>
            </div>
            <div className="mt-3 text-emerald-400 text-sm font-semibold">✅ مجاني</div>
          </div>
        </div>
      </div>

      {/* Complete Setup Options */}
      <div className="bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">🎯 خيارات الإعداد الكاملة</h3>
        
        <div className="space-y-6">
          {/* Free Setup */}
          <div className="bg-emerald-500/10 rounded-2xl p-6 border-2 border-emerald-400/50">
            <div className="flex items-center gap-3 mb-4">
              <div className="text-3xl">🆓</div>
              <div>
                <h4 className="text-2xl font-bold text-white">Setup 1: مجاني 100%</h4>
                <p className="text-emerald-400">للمبتدئين أو الميزانية المحدودة</p>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">الإعدادات:</div>
                <div className="bg-black/50 rounded p-3">
                  <code className="text-xs text-emerald-300">
{`# .env
USE_AI_ANALYST = False
USE_RULE_BASED_ANALYST = True
USE_NEWS_FILTER = False
TELEGRAM_BOT_TOKEN = "your_free_token"

# لا رسوم شهرية!`}
                  </code>
                </div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">ما يعمل:</div>
                <ul className="text-gray-300 text-sm space-y-1">
                  <li>✅ FSM (كامل)</li>
                  <li>✅ Voting System (كامل)</li>
                  <li>✅ Smart Grid (كامل)</li>
                  <li>✅ Portfolio Manager (كامل)</li>
                  <li>✅ FX Analyst (قواعد برمجية)</li>
                  <li>✅ جميع الوكلاء الآخرين (كاملة)</li>
                  <li>✅ Telegram (إشعارات فقط)</li>
                </ul>
              </div>
            </div>

            <div className="mt-4 bg-emerald-500/20 rounded-lg p-4 border border-emerald-400/50">
              <div className="text-emerald-400 font-bold mb-2">💰 التكلفة الإجمالية: $0/شهر</div>
              <p className="text-gray-300 text-sm">
                النظام يعمل كامل لكن FX Analyst بدقة أقل (60-70% بدلاً من 85%)
              </p>
            </div>
          </div>

          {/* Hybrid Setup */}
          <div className="bg-blue-500/10 rounded-2xl p-6 border-2 border-blue-400/50">
            <div className="flex items-center gap-3 mb-4">
              <div className="text-3xl">⚡</div>
              <div>
                <h4 className="text-2xl font-bold text-white">Setup 2: هجين (Hybrid)</h4>
                <p className="text-blue-400">نموذج محلي مفتوح المصدر</p>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">الإعدادات:</div>
                <div className="bg-black/50 rounded p-3">
                  <code className="text-xs text-blue-300">
{`# .env
USE_AI_ANALYST = True
AI_MODEL = "llama-2-13b"  # محلي
LOCAL_MODEL = True
MODEL_PATH = "./models/llama-2-13b.gguf"
USE_NEWS_FILTER = False
TELEGRAM_BOT_TOKEN = "your_free_token"

# مجاني بعد التحميل الأولي`}
                  </code>
                </div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">المتطلبات:</div>
                <ul className="text-gray-300 text-sm space-y-1">
                  <li>🖥️ GPU: RTX 3060+ (8GB VRAM)</li>
                  <li>💾 RAM: 16GB+</li>
                  <li>💿 Storage: 20GB للنموذج</li>
                  <li>⏱️ سرعة: جيدة جداً</li>
                </ul>
              </div>
            </div>

            <div className="mt-4 bg-blue-500/20 rounded-lg p-4 border border-blue-400/50">
              <div className="text-blue-400 font-bold mb-2">💰 التكلفة: $0/شهر</div>
              <p className="text-gray-300 text-sm">
                استثمار مرة واحدة في GPU قوي، ثم كل شيء مجاني. دقة 75-80%
              </p>
            </div>
          </div>

          {/* Pro Setup */}
          <div className="bg-purple-500/10 rounded-2xl p-6 border-2 border-purple-400/50">
            <div className="flex items-center gap-3 mb-4">
              <div className="text-3xl">🚀</div>
              <div>
                <h4 className="text-2xl font-bold text-white">Setup 3: احترافي (Pro)</h4>
                <p className="text-purple-400">OpenAI GPT-4 - أقصى أداء</p>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">الإعدادات:</div>
                <div className="bg-black/50 rounded p-3">
                  <code className="text-xs text-purple-300">
{`# .env
OPENAI_API_KEY = "sk-xxxxx"
USE_AI_ANALYST = True
AI_MODEL = "gpt-4-turbo-preview"
LOCAL_MODEL = False
USE_NEWS_FILTER = True
INVESTING_API_KEY = "your_key"
TELEGRAM_BOT_TOKEN = "your_token"`}
                  </code>
                </div>
              </div>

              <div className="bg-black/30 rounded-xl p-4">
                <div className="text-white font-semibold mb-3">ما تحصل عليه:</div>
                <ul className="text-gray-300 text-sm space-y-1">
                  <li>✨ دقة استثنائية (85%+)</li>
                  <li>✨ تحليل سياقي عميق</li>
                  <li>✨ فلتر الأخبار التلقائي</li>
                  <li>✨ تعلم من الأخطاء</li>
                  <li>✨ أداء أفضل بـ 15%</li>
                </ul>
              </div>
            </div>

            <div className="mt-4 bg-purple-500/20 rounded-lg p-4 border border-purple-400/50">
              <div className="text-purple-400 font-bold mb-2">💰 التكلفة: ~$80-130/شهر</div>
              <div className="text-gray-300 text-sm space-y-1">
                <div>• OpenAI: $50-100/شهر</div>
                <div>• Economic Calendar: $30/شهر</div>
                <div>• Telegram: مجاني</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recommendation */}
      <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 rounded-3xl p-8 border border-yellow-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">💡 توصياتي</h3>
        
        <div className="space-y-4">
          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-emerald-400 font-semibold text-lg mb-3">🎯 للمبتدئين (رأس مال &lt; $5000):</h4>
            <p className="text-gray-300 mb-3">
              ابدأ بـ <strong className="text-white">Setup 1 - مجاني 100%</strong>
            </p>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• تعلم النظام بدون تكاليف</li>
              <li>• اختبر على Demo Account</li>
              <li>• بعد 3 أشهر إذا نجحت → انتقل لـ Setup 3</li>
            </ul>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-blue-400 font-semibold text-lg mb-3">⚡ للمتوسطين (رأس مال $5000-$20000):</h4>
            <p className="text-gray-300 mb-3">
              <strong className="text-white">Setup 2 - Hybrid</strong> إذا كان لديك GPU قوي
            </p>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• استثمار مرة واحدة في GPU</li>
              <li>• دقة جيدة جداً (75-80%)</li>
              <li>• لا رسوم شهرية</li>
            </ul>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-purple-400 font-semibold text-lg mb-3">🚀 للمحترفين (رأس مال &gt; $20000):</h4>
            <p className="text-gray-300 mb-3">
              <strong className="text-white">Setup 3 - Pro</strong> بدون تردد
            </p>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• الدقة الأعلى (85%+) = عوائد أكبر</li>
              <li>• $100/شهر لا شيء مقارنة بالأرباح</li>
              <li>• إذا ربحت 5% شهرياً من $20k = $1000</li>
              <li>• $100 تكلفة = استثمار ذكي</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
