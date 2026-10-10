import { useBackendStatus, useApiData } from '../../utils/useBackend';

export default function MT5Integration() {
  const { connected, status } = useBackendStatus();
  const { data: account } = useApiData<Record<string,any>>('/api/account', 5000);

  const mt5Info = status?.mt5_info ?? account ?? {};
  const isSimulation = status?.mt5_simulation ?? true;

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-3xl p-8 border border-emerald-400/30">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-4xl font-bold text-white mb-4">🔌 التكامل مع MT5</h2>
            <p className="text-xl text-emerald-200">
              اتصال مباشر وفوري بين الذكاء الاصطناعي ومنصة MetaTrader 5
            </p>
          </div>
          {/* Live Connection Status */}
          <div className={`rounded-2xl p-4 border text-sm ${
            connected
              ? isSimulation
                ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-gray-500/10 border-gray-500/30 text-gray-500'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                connected ? (isSimulation ? 'bg-yellow-400' : 'bg-emerald-400') : 'bg-gray-500'
              }`} />
              <span className="font-bold">
                {!connected ? '⬛ Backend غير متصل' :
                 isSimulation ? '🟡 وضع المحاكاة' : '🟢 MT5 متصل'}
              </span>
            </div>
            {mt5Info.login && <div className="text-xs opacity-70">Login: {mt5Info.login}</div>}
            {mt5Info.server && <div className="text-xs opacity-70">Server: {mt5Info.server}</div>}
            {mt5Info.balance && <div className="text-xs opacity-70">Balance: ${mt5Info.balance?.toLocaleString()}</div>}
          </div>
        </div>
      </div>

      {/* Architecture */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">🏗️ معمارية النظام</h3>
        
        <div className="grid md:grid-cols-3 gap-4">
          <div className="bg-blue-500/10 rounded-2xl p-6 border border-blue-400/30">
            <div className="text-3xl mb-3">🤖</div>
            <h4 className="text-white font-semibold mb-2">AI Agents Layer</h4>
            <p className="text-gray-400 text-sm">Python Backend</p>
          </div>
          
          <div className="bg-purple-500/10 rounded-2xl p-6 border border-purple-400/30">
            <div className="text-3xl mb-3">🌉</div>
            <h4 className="text-white font-semibold mb-2">Bridge Layer</h4>
            <p className="text-gray-400 text-sm">MetaTrader5 Python Library</p>
          </div>
          
          <div className="bg-emerald-500/10 rounded-2xl p-6 border border-emerald-400/30">
            <div className="text-3xl mb-3">📊</div>
            <h4 className="text-white font-semibold mb-2">MT5 Platform</h4>
            <p className="text-gray-400 text-sm">IC Markets Account</p>
          </div>
        </div>
      </div>

      {/* Setup Steps */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">⚙️ خطوات الإعداد</h3>
        
        <div className="space-y-4">
          {[
            { step: '1', title: 'تثبيت MT5', desc: 'تحميل وتثبيت MetaTrader 5 من IC Markets', code: 'https://www.icmarkets.com/mt5' },
            { step: '2', title: 'Python Library', desc: 'pip install MetaTrader5', code: 'pip install MetaTrader5' },
            { step: '3', title: 'الاتصال', desc: 'كود الاتصال الأولي', code: 'import MetaTrader5 as mt5\\nmt5.initialize()' },
            { step: '4', title: 'التحقق', desc: 'فحص الاتصال', code: 'if mt5.account_info():\\n    print("✓ Connected")' }
          ].map((item, i) => (
            <div key={i} className="bg-gradient-to-r from-emerald-500/10 to-transparent rounded-xl p-6 border-r-4 border-emerald-400">
              <div className="flex items-center gap-4 mb-3">
                <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center text-white font-bold">
                  {item.step}
                </div>
                <div>
                  <h4 className="text-white font-semibold">{item.title}</h4>
                  <p className="text-gray-400 text-sm">{item.desc}</p>
                </div>
              </div>
              <div className="bg-black/50 rounded-lg p-3">
                <code className="text-xs text-emerald-400">{item.code}</code>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Execution Code */}
      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود التنفيذ الكامل</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300 leading-relaxed">
<code>{`import MetaTrader5 as mt5
from datetime import datetime

class ExecutionAgent:
    def __init__(self):
        self.connected = False
        
    def connect(self, account, password, server):
        """الاتصال بحساب MT5"""
        if not mt5.initialize():
            print("❌ فشل تهيئة MT5")
            return False
            
        authorized = mt5.login(account, password=password, server=server)
        if not authorized:
            print("❌ فشل تسجيل الدخول")
            return False
            
        self.connected = True
        print("✅ متصل بـ MT5")
        return True
    
    def execute_trade(self, strategy):
        """تنفيذ الصفقة"""
        if not self.connected:
            return {"status": "error", "message": "Not connected"}
        
        # بناء الطلب
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": strategy['symbol'],
            "volume": strategy['lot_size'],
            "type": mt5.ORDER_TYPE_BUY if strategy['direction'] == 'BUY' 
                    else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(strategy['symbol']).ask 
                     if strategy['direction'] == 'BUY' 
                     else mt5.symbol_info_tick(strategy['symbol']).bid,
            "sl": strategy['stop_loss'],
            "tp": strategy['take_profit'],
            "deviation": 10,
            "magic": 123456,
            "comment": "AI_Agent_Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # إرسال الطلب
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "status": "error",
                "message": f"فشل التنفيذ: {result.comment}"
            }
        
        # نجح التنفيذ
        return {
            "status": "success",
            "ticket": f"MT5-{result.order}",
            "price": result.price,
            "volume": result.volume,
            "comment": result.comment
        }
    
    def get_open_positions(self):
        """الحصول على الصفقات المفتوحة"""
        positions = mt5.positions_get()
        if positions is None:
            return []
            
        return [{
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "sl": pos.sl,
            "tp": pos.tp,
            "profit": pos.profit
        } for pos in positions]
    
    def close_position(self, ticket):
        """إغلاق صفقة"""
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return {"status": "error", "message": "Position not found"}
        
        position = positions[0]
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY 
                    else mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": mt5.symbol_info_tick(position.symbol).bid 
                     if position.type == mt5.POSITION_TYPE_BUY 
                     else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": 10,
            "magic": 123456,
            "comment": "AI_Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        return {
            "status": "success" if result.retcode == mt5.TRADE_RETCODE_DONE else "error",
            "message": result.comment
        }`}</code>
          </pre>
        </div>
      </div>

      {/* Real-time Monitoring */}
      <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 rounded-3xl p-8 border border-orange-400/30">
        <h3 className="text-2xl font-bold text-white mb-6">👁️ المراقبة الحية</h3>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-orange-400 font-semibold mb-4">📡 WebSocket Stream</h4>
            <p className="text-gray-300 text-sm mb-3">
              اتصال مستمر لتلقي تحديثات الأسعار والصفقات بشكل فوري
            </p>
            <div className="bg-black/50 rounded-lg p-3">
              <code className="text-xs text-gray-400">
{`while True:
    tick = mt5.symbol_info_tick("EURUSD")
    monitor_agent.update(tick)
    time.sleep(0.1)  # 100ms`}
              </code>
            </div>
          </div>

          <div className="bg-black/30 rounded-xl p-6">
            <h4 className="text-red-400 font-semibold mb-4">⚡ Event-Driven</h4>
            <p className="text-gray-300 text-sm mb-3">
              يتفاعل Monitor Agent فوراً عند تحقق شروط معينة
            </p>
            <div className="bg-black/50 rounded-lg p-3">
              <code className="text-xs text-gray-400">
{`if profit >= take_profit_1:
    partial_close(50%)
if price >= breakeven_level:
    move_sl_to_breakeven()`}
              </code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
