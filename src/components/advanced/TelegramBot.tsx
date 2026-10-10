export default function TelegramBot() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-3xl p-8 border border-blue-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">📱 Telegram Bot Integration</h2>
        <p className="text-xl text-blue-200">
          إشعارات فورية ومراقبة كاملة من هاتفك
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-xl font-bold text-white mb-4">📢 الإشعارات التلقائية</h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li>✓ تغيير FSM State</li>
            <li>✓ فتح/إغلاق صفقة</li>
            <li>✓ تفعيل Recovery Mode</li>
            <li>✓ الوصول لأهداف الربح اليومية</li>
            <li>✓ تحذير Drawdown</li>
            <li>✓ تقرير يومي/أسبوعي</li>
          </ul>
        </div>

        <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
          <h3 className="text-xl font-bold text-white mb-4">🎛️ التحكم عن بُعد</h3>
          <div className="space-y-2 text-sm">
            <div className="bg-blue-500/10 p-3 rounded border border-blue-400/30">
              <code>/status</code> - عرض الحالة
            </div>
            <div className="bg-emerald-500/10 p-3 rounded border border-emerald-400/30">
              <code>/pause</code> - إيقاف مؤقت
            </div>
            <div className="bg-red-500/10 p-3 rounded border border-red-400/30">
              <code>/resume</code> - استئناف
            </div>
            <div className="bg-purple-500/10 p-3 rounded border border-purple-400/30">
              <code>/report</code> - تقرير فوري
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود Telegram</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300">
<code>{`#define TELEGRAM_BOT_TOKEN "YOUR_BOT_TOKEN"
#define TELEGRAM_CHAT_ID "YOUR_CHAT_ID"

void SendTelegramAlert(string message) {
    string url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage";
    string params = "chat_id=" + TELEGRAM_CHAT_ID + "&text=" + UrlEncode(message);
    
    char post[], result[];
    string headers = "Content-Type: application/x-www-form-urlencoded\\r\\n";
    
    int res = WebRequest("POST", url, headers, 5000, params, post, result);
    
    if(res == -1) {
        Print("Telegram Error: ", GetLastError());
    }
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
