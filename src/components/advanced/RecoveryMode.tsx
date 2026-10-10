export default function RecoveryMode() {
  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-red-500/20 to-pink-500/20 rounded-3xl p-8 border border-red-400/30">
        <h2 className="text-4xl font-bold text-white mb-4">🚑 Recovery Mode الذكي</h2>
        <p className="text-xl text-red-200">
          وضع الاستعادة التلقائي - التركيز على State A الأقل مخاطرة
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
          <h3 className="text-2xl font-bold text-white mb-4">🎯 متى يُفعّل؟</h3>
          <ul className="space-y-3 text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-red-400 text-xl">•</span>
              <span>Drawdown يتجاوز 10%</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-400 text-xl">•</span>
              <span>3 صفقات خاسرة متتالية</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-400 text-xl">•</span>
              <span>خسارة يومية تتجاوز 7%</span>
            </li>
          </ul>
        </div>

        <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
          <h3 className="text-2xl font-bold text-white mb-4">⚙️ ماذا يفعل؟</h3>
          <ul className="space-y-3 text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 text-xl">✓</span>
              <span>التداول فقط في State A</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 text-xl">✓</span>
              <span>تخفيض المخاطرة إلى 0.3%</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 text-xl">✓</span>
              <span>أهداف ربح صغيرة (5-10 نقاط)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 text-xl">✓</span>
              <span>زيادة عدد الصفقات (Scalping)</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="bg-white/5 rounded-3xl p-8 border border-white/10">
        <h3 className="text-2xl font-bold text-white mb-6">💻 كود Recovery Mode</h3>
        <div className="bg-black/50 rounded-xl p-6 overflow-x-auto">
          <pre className="text-sm text-gray-300">
<code>{`bool recovery_mode = false;
double recovery_start_balance = 0;
int recovery_wins = 0;

void CheckRecoveryMode() {
    double current_dd = CalculateDrawdown();
    
    if(!recovery_mode && current_dd > 10.0) {
        ActivateRecoveryMode();
    }
    
    if(recovery_mode) {
        // شرط الخروج: استرداد 50% من الخسارة + 5 صفقات رابحة
        double recovered = AccountInfoDouble(ACCOUNT_BALANCE) - recovery_start_balance;
        if(recovered > 0 && recovery_wins >= 5) {
            DeactivateRecoveryMode();
        }
    }
}

void ActivateRecoveryMode() {
    recovery_mode = true;
    recovery_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    recovery_wins = 0;
    
    Print("🚑 Recovery Mode مُفعّل!");
    SendTelegramAlert("🚑 Recovery Mode ON - Drawdown: " + DoubleToString(CalculateDrawdown(), 1) + "%");
    
    // تعديل الإعدادات
    RiskPercent = 0.3;
    Max_Daily_Trades = 15;
    Force_State_A = true;
}`}</code>
          </pre>
        </div>
      </div>
    </div>
  );
}
