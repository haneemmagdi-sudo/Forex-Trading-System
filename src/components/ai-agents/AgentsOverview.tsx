export default function AgentsOverview() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-3xl p-8 border border-indigo-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🤖 نظام الوكلاء بالذكاء الاصطناعي</h2>
        <p className="text-xl text-indigo-200 mb-4">
          فريق عمل متكامل من 4 وكلاء ذكيين يعملون بتناغم تام - مثل صندوق التحوط الاحترافي
        </p>
        <div className="bg-black/30 rounded-xl p-4">
          <p className="text-gray-300">
            💡 <strong className="text-white">الفكرة:</strong> بدلاً من إكسبرت واحد يفعل كل شيء، 
            لديك فريق متخصص: محلل يبحث، مخطط يقرر، منفذ ينفذ، ومتابع يراقب!
          </p>
        </div>
      </div>

      {/* Agents Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Agent 1: FX Analyst */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10 hover:border-blue-400/50 transition-all duration-300">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-blue-500/50 flex-shrink-0">
              <span className="text-4xl mb-1">🔍</span>
              <span className="text-white font-bold text-xs">Agent 1</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">FX Analyst</h3>
              <p className="text-blue-400 mb-4">الوكيل المحلل - عيون السوق</p>
              
              <div className="space-y-2">
                <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-400/30">
                  <div className="text-white font-semibold text-sm mb-2">🎯 المهام:</div>
                  <ul className="text-gray-300 text-xs space-y-1">
                    <li>• رصد Order Blocks (كتل الأوامر المؤسسية)</li>
                    <li>• اكتشاف Fair Value Gaps (FVG)</li>
                    <li>• تحديد Liquidity Sweeps (مصائد السيولة)</li>
                    <li>• تحليل Multi-Timeframe Confluence</li>
                    <li>• مراقبة Session Momentum</li>
                    <li>• فحص Economic Calendar (News Shield)</li>
                  </ul>
                </div>

                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-blue-400 font-semibold text-sm mb-2">🧠 التقنية:</div>
                  <p className="text-gray-400 text-xs">
                    LLM (GPT-4) + Computer Vision لتحليل الشارت + Time Series Analysis
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Agent 2: Strategy Planner */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10 hover:border-purple-400/50 transition-all duration-300">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-purple-500/50 flex-shrink-0">
              <span className="text-4xl mb-1">📋</span>
              <span className="text-white font-bold text-xs">Agent 2</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">Strategy Planner</h3>
              <p className="text-purple-400 mb-4">الوكيل المخطط - العقل المدبر</p>
              
              <div className="space-y-2">
                <div className="bg-purple-500/10 rounded-lg p-3 border border-purple-400/30">
                  <div className="text-white font-semibold text-sm mb-2">🎯 المهام:</div>
                  <ul className="text-gray-300 text-xs space-y-1">
                    <li>• بناء خطة التداول الكاملة</li>
                    <li>• حساب Position Sizing الأمثل</li>
                    <li>• تحديد Entry Price الدقيق</li>
                    <li>• حساب Stop Loss & Take Profit</li>
                    <li>• تقييم Risk/Reward Ratio</li>
                    <li>• إرسال الخطة للموافقة (Risk Manager + CEO)</li>
                  </ul>
                </div>

                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-purple-400 font-semibold text-sm mb-2">🧠 التقنية:</div>
                  <p className="text-gray-400 text-xs">
                    Reinforcement Learning + Monte Carlo Simulation + Kelly Criterion
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Agent 3: Execution Agent */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10 hover:border-emerald-400/50 transition-all duration-300">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-emerald-500/50 flex-shrink-0">
              <span className="text-4xl mb-1">⚡</span>
              <span className="text-white font-bold text-xs">Agent 3</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">Execution Agent</h3>
              <p className="text-emerald-400 mb-4">الوكيل المنفذ - اليد الحديدية</p>
              
              <div className="space-y-2">
                <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-400/30">
                  <div className="text-white font-semibold text-sm mb-2">🎯 المهام:</div>
                  <ul className="text-gray-300 text-xs space-y-1">
                    <li>• الاتصال المباشر بـ MT5 API</li>
                    <li>• تنفيذ Market Orders بسرعة فائقة</li>
                    <li>• إرسال SL & TP مع الأمر</li>
                    <li>• الحصول على Ticket ID</li>
                    <li>• إدارة Slippage & Spread</li>
                    <li>• تسجيل التنفيذ في Database</li>
                  </ul>
                </div>

                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-emerald-400 font-semibold text-sm mb-2">🧠 التقنية:</div>
                  <p className="text-gray-400 text-xs">
                    Python-MT5 Bridge + WebSocket للسرعة + Error Handling متقدم
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Agent 4: Monitor Agent */}
        <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10 hover:border-orange-400/50 transition-all duration-300">
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex flex-col items-center justify-center shadow-lg shadow-orange-500/50 flex-shrink-0">
              <span className="text-4xl mb-1">👁️</span>
              <span className="text-white font-bold text-xs">Agent 4</span>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">Monitor Agent</h3>
              <p className="text-orange-400 mb-4">الوكيل المتابع - الحارس الأمين</p>
              
              <div className="space-y-2">
                <div className="bg-orange-500/10 rounded-lg p-3 border border-orange-400/30">
                  <div className="text-white font-semibold text-sm mb-2">🎯 المهام:</div>
                  <ul className="text-gray-300 text-xs space-y-1">
                    <li>• مراقبة الصفقات المفتوحة 24/7</li>
                    <li>• تحديث SL/TP ديناميكياً (Trailing)</li>
                    <li>• كشف شروط الخروج المبكر</li>
                    <li>• إرسال تنبيهات فورية</li>
                    <li>• إدارة Partial Profit Taking</li>
                    <li>• الإغلاق التلقائي عند الشروط</li>
                  </ul>
                </div>

                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-orange-400 font-semibold text-sm mb-2">🧠 التقنية:</div>
                  <p className="text-gray-400 text-xs">
                    Real-time Streaming + Event-Driven Architecture + ML للتنبؤ
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow */}
      <div className="bg-gradient-to-r from-purple-500/10 to-transparent rounded-3xl p-8 border-r-4 border-purple-400">
        <h3 className="text-2xl font-bold text-white mb-6">🔄 سير العمل (Workflow)</h3>
        
        <div className="space-y-4">
          {[
            {
              step: '1',
              agent: 'FX Analyst',
              action: 'تحليل السوق',
              desc: 'يبحث عن Order Block صاعد + FVG مملوء على H1',
              result: '"وجدت فرصة على EUR/USD - Order Block عند 1.0850"',
              color: 'blue'
            },
            {
              step: '2',
              agent: 'Strategy Planner',
              action: 'بناء الخطة',
              desc: 'يحسب: Entry 1.0855, SL 1.0820, TP 1.0920, Lot 0.15',
              result: '"الخطة جاهزة - Risk 2%, R:R = 1:2"',
              color: 'purple'
            },
            {
              step: '3',
              agent: 'Risk Manager + CEO',
              action: 'الموافقة',
              desc: 'يتحقق من: عدد الصفقات، Drawdown، توافق Portfolio',
              result: '"✅ موافقة - تنفيذ الصفقة"',
              color: 'yellow'
            },
            {
              step: '4',
              agent: 'Execution Agent',
              action: 'التنفيذ',
              desc: 'يرسل الأمر لـ MT5 ويحصل على Ticket #1234567',
              result: '"✅ تم التنفيذ - Ticket: MT5-1234567"',
              color: 'emerald'
            },
            {
              step: '5',
              agent: 'Monitor Agent',
              action: 'المتابعة',
              desc: 'يراقب الصفقة ويحدث SL لـ Break-Even عند +20 نقطة',
              result: '"🔄 تحديث SL → 1.0855 (Break-even)"',
              color: 'orange'
            }
          ].map((item, i) => (
            <div key={i} className={`bg-${item.color}-500/10 rounded-2xl p-6 border border-${item.color}-400/30`}>
              <div className="flex items-start gap-4">
                <div className={`w-12 h-12 bg-${item.color}-500 rounded-xl flex items-center justify-center text-white font-bold text-xl flex-shrink-0`}>
                  {item.step}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className={`text-${item.color}-400 font-bold text-lg`}>{item.agent}</h4>
                    <span className="text-gray-400 text-sm">→ {item.action}</span>
                  </div>
                  <p className="text-gray-300 text-sm mb-2">{item.desc}</p>
                  <div className="bg-black/30 rounded-lg p-3">
                    <code className={`text-${item.color}-400 text-xs`}>{item.result}</code>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Communication */}
      <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💬 التواصل بين الوكلاء</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-2xl p-6 border border-indigo-400/30">
            <h4 className="text-indigo-400 font-semibold mb-4">🔗 Message Queue System</h4>
            <p className="text-gray-300 text-sm mb-4">
              الوكلاء يتواصلون عبر نظام رسائل متقدم (مثل RabbitMQ أو Redis Pub/Sub)
            </p>
            <div className="bg-black/30 rounded-lg p-4">
              <code className="text-xs text-gray-400">
                FX Analyst → Strategy Planner:<br/>
                {`{"type": "opportunity", "pair": "EURUSD", "setup": "bullish_ob"}`}<br/>
                <br/>
                Strategy Planner → Risk Manager:<br/>
                {`{"type": "approval_request", "plan": {...}}`}
              </code>
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl p-6 border border-purple-400/30">
            <h4 className="text-purple-400 font-semibold mb-4">🧠 Shared Memory</h4>
            <p className="text-gray-300 text-sm mb-4">
              قاعدة بيانات مشتركة (PostgreSQL) تحتوي على:
            </p>
            <ul className="text-gray-400 text-xs space-y-1">
              <li>• Market State (حالة السوق الحالية)</li>
              <li>• Open Positions (الصفقات المفتوحة)</li>
              <li>• Historical Performance (الأداء التاريخي)</li>
              <li>• Agent Logs (سجلات الوكلاء)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl p-8 border border-cyan-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">🛠️ التقنيات المستخدمة</h3>
        
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-3xl mb-3">🤖</div>
            <h4 className="text-white font-semibold mb-3">AI/ML</h4>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• OpenAI GPT-4 (LLM)</li>
              <li>• TensorFlow/PyTorch</li>
              <li>• Scikit-learn</li>
              <li>• Prophet (Time Series)</li>
            </ul>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-3xl mb-3">⚡</div>
            <h4 className="text-white font-semibold mb-3">Backend</h4>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• Python 3.11+</li>
              <li>• FastAPI</li>
              <li>• PostgreSQL</li>
              <li>• Redis</li>
              <li>• MetaTrader 5 API</li>
            </ul>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <div className="text-3xl mb-3">📊</div>
            <h4 className="text-white font-semibold mb-3">Analysis</h4>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• pandas & NumPy</li>
              <li>• TA-Lib</li>
              <li>• mplfinance</li>
              <li>• yfinance</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Benefits */}
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">🎯 لماذا نظام الوكلاء أفضل؟</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-emerald-400 font-semibold mb-4">✅ المميزات</h4>
            <ul className="space-y-2 text-gray-300 text-sm">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span><strong>التخصص:</strong> كل وكيل خبير في مجاله</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span><strong>التوازي:</strong> العمل في نفس الوقت</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span><strong>المرونة:</strong> سهل تطوير وكيل دون التأثير على الباقي</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span><strong>الشفافية:</strong> تتبع قرار كل وكيل</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400">✓</span>
                <span><strong>الموثوقية:</strong> إذا فشل وكيل، الباقي يعملون</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-orange-400 font-semibold mb-4">📈 النتائج المتوقعة</h4>
            <div className="space-y-3">
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold mb-1">Win Rate</div>
                <div className="text-emerald-400 text-2xl font-bold">75-85%</div>
                <div className="text-gray-400 text-xs">مع SMC + AI</div>
              </div>
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold mb-1">Avg R:R</div>
                <div className="text-blue-400 text-2xl font-bold">1:2.5</div>
                <div className="text-gray-400 text-xs">نسبة ممتازة</div>
              </div>
              <div className="bg-black/30 rounded-lg p-4">
                <div className="text-white font-semibold mb-1">Max DD</div>
                <div className="text-yellow-400 text-2xl font-bold">&lt; 10%</div>
                <div className="text-gray-400 text-xs">مع Risk Manager</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
