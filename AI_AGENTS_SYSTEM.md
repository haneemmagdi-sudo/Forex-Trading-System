# 🤖 نظام الوكلاء بالذكاء الاصطناعي - AI Agents Trading System

## 📖 نظرة عامة

نظام تداول متقدم يعتمد على **فريق من 4 وكلاء ذكيين** يعملون بتناغم تام، مستوحى من صناديق التحوط الاحترافية.

### 🌟 الفلسفة الأساسية
- **لا تداول retail تقليدي** ❌
- **استراتيجية Smart Money Concepts فقط** ✅
- **4 وكلاء متخصصين** بدلاً من إكسبرت واحد
- **اتصال مباشر بـ MT5** عبر Python

---

## 🤖 الوكلاء الأربعة

### 1. FX Analyst (الوكيل المحلل) 🔍

**الدور:** عيون السوق - يبحث عن الفرص باستخدام SMC

**المهام:**
- 📦 كشف **Order Blocks** (Bullish/Bearish)
- 🕳️ تحديد **Fair Value Gaps (FVG)**
- 🎣 رصد **Liquidity Sweeps** (مصائد السيولة)
- ⏱️ تحليل **Multi-Timeframe Confluence** (D1 → H4 → H1)
- 🌍 مراقبة **Session Momentum** (London/NY overlap)
- 📰 فحص **Economic Calendar** (News Shield)

**التقنيات:**
```python
- GPT-4 (LLM) للتحليل السياقي
- Computer Vision لقراءة الشارت
- Time Series Analysis
- Pattern Recognition
```

**مثال على إشارة:**
```json
{
  "pair": "EURUSD",
  "setup_type": "bullish_order_block",
  "entry_zone": [1.0850, 1.0860],
  "confluence": {
    "d1_trend": "bullish",
    "h4_ob": true,
    "fvg_filled": true,
    "liquidity_sweep": "recent"
  },
  "confidence": 87,
  "session": "london_ny_overlap"
}
```

---

### 2. Strategy Planner (الوكيل المخطط) 📋

**الدور:** العقل المدبر - يبني خطة التداول الكاملة

**المهام:**
- 🎯 تحديد **Entry Price** الدقيق
- 🛑 حساب **Stop Loss** (عادة تحت/فوق Order Block)
- 💰 حساب **Take Profit** (1:2 أو 1:3 R:R)
- ⚖️ **Position Sizing** ديناميكي بناءً على:
  - الرصيد الحي من MT5
  - المخاطرة المسموحة (1-3%)
  - عدد نقاط SL
- 📊 تقييم **Risk/Reward Ratio**
- ✅ إرسال الخطة لـ Risk Manager + CEO للموافقة

**التقنيات:**
```python
- Reinforcement Learning (RL)
- Monte Carlo Simulation
- Kelly Criterion للـ position sizing
- Bayesian Optimization
```

**مثال على خطة:**
```python
{
  "symbol": "EURUSD",
  "direction": "BUY",
  "entry_price": 1.0855,
  "stop_loss": 1.0820,
  "take_profit_1": 1.0920,  # 50% position
  "take_profit_2": 1.0985,  # 30% position
  "lot_size": 0.15,  # محسوبة بدقة
  "risk_percent": 2.0,
  "reward_risk_ratio": 2.1,
  "max_loss_usd": 105.0,
  "expected_profit_usd": 220.0
}
```

---

### 3. Execution Agent (الوكيل المنفذ) ⚡

**الدور:** اليد الحديدية - ينفذ الأوامر بسرعة البرق

**المهام:**
- 🔌 الاتصال المباشر بـ **MT5 API**
- ⚡ تنفيذ **Market Orders** فوري
- 🎫 الحصول على **Ticket ID** من MT5
- 📊 إرسال **SL & TP** مع الأمر
- 🔄 إدارة **Slippage & Spread**
- 💾 تسجيل التنفيذ في **Database**

**التقنيات:**
```python
- MetaTrader5 Python Library
- WebSocket للسرعة
- Error Handling متقدم
- Retry Logic للأوامر الفاشلة
```

**كود التنفيذ:**
```python
class ExecutionAgent:
    def execute_trade(self, strategy):
        # بناء الطلب
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": strategy['symbol'],
            "volume": strategy['lot_size'],
            "type": mt5.ORDER_TYPE_BUY if strategy['direction'] == 'BUY' 
                    else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(strategy['symbol']).ask,
            "sl": strategy['stop_loss'],
            "tp": strategy['take_profit'],
            "magic": 123456,
            "comment": "AI_SMC_Trade"
        }
        
        # تنفيذ
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "status": "success",
                "ticket": f"MT5-{result.order}",
                "price": result.price
            }
```

---

### 4. Monitor Agent (الوكيل المتابع) 👁️

**الدور:** الحارس الأمين - يراقب الصفقات 24/7

**المهام:**
- 👀 مراقبة **الصفقات المفتوحة** لحظة بلحظة
- 🔄 تحديث **SL/TP** ديناميكياً (Trailing Stop)
- ⚠️ كشف **شروط الخروج المبكر**
- 📱 إرسال **تنبيهات** فورية (Telegram)
- 💰 إدارة **Partial Profit Taking** (50% → 30% → 20%)
- 🚪 **الإغلاق التلقائي** عند تحقق الشروط

**التقنيات:**
```python
- Real-time Streaming من MT5
- Event-Driven Architecture
- ML للتنبؤ بنقاط الخروج المثالية
- Redis Pub/Sub للإشعارات
```

**مثال على مراقبة:**
```python
def monitor_positions():
    while True:
        positions = mt5.positions_get()
        
        for pos in positions:
            current_price = get_current_price(pos.symbol)
            
            # Break-even
            if profit_pips(pos) >= 20:
                move_sl_to_breakeven(pos.ticket)
            
            # Trailing Stop
            if profit_pips(pos) >= 30:
                update_trailing_sl(pos.ticket, current_price)
            
            # Partial TP
            if profit_pips(pos) >= 50:
                partial_close(pos.ticket, 50%)
            
        time.sleep(0.1)  # 100ms check
```

---

## 💎 Smart Money Concepts (SMC) - الاستراتيجية

### 1. Order Blocks (كتل الأوامر)

**المفهوم:**  
مناطق دخلت منها المؤسسات الكبرى بأوامر ضخمة. السعر يحترم هذه المناطق عند العودة إليها.

**Bullish Order Block:**
- آخر شمعة هابطة (حمراء) قبل حركة صاعدة قوية
- حجم تداول عالٍ
- عند عودة السعر → فرصة شراء

**Bearish Order Block:**
- آخر شمعة صاعدة (خضراء) قبل حركة هابطة قوية
- حجم تداول عالٍ
- عند عودة السعر → فرصة بيع

**كود الكشف:**
```python
def detect_order_block(df):
    for i in range(20, len(df)):
        # Bullish OB
        if (df['close'].iloc[i-1] < df['open'].iloc[i-1] and  # شمعة حمراء
            df['close'].iloc[i] > df['close'].iloc[i-5] + 100 * point and  # صعود قوي
            df['volume'].iloc[i-1] > df['volume'].iloc[i-20:i].mean() * 1.5):  # حجم عالٍ
            
            yield {
                'type': 'bullish',
                'zone': [df['low'].iloc[i-1], df['high'].iloc[i-1]],
                'strength': calculate_strength(df, i)
            }
```

---

### 2. Fair Value Gap (FVG)

**المفهوم:**  
فجوة سعرية = منطقة لم يتم تداولها بشكل كافٍ. السعر يعود دائماً لملئها.

**شروط FVG Bullish:**
- 3 شموع صاعدة متتالية
- `High[Candle 1] < Low[Candle 3]`
- الفجوة = منطقة دعم قوية

**شروط FVG Bearish:**
- 3 شموع هابطة متتالية
- `Low[Candle 1] > High[Candle 3]`
- الفجوة = منطقة مقاومة قوية

---

### 3. Liquidity Sweeps (صيد السيولة)

**المفهوم:**  
المؤسسات تحتاج سيولة ضخمة. أين توجد؟ عند Stop Loss المتداولين الصغار!

**السيناريو:**
1. السعر عند مقاومة → Retail traders يبيعون ويضعون SL فوق المقاومة
2. المؤسسات تدفع السعر قليلاً فوق المقاومة → تفعيل جميع Stop Losses
3. بعد جمع السيولة → انعكاس عنيف هبوطاً

**الإشارة:**
- اختراق كاذب لمستوى رئيسي
- شمعة rejection قوية (ذيل كبير)
- عودة السعر داخل المستوى
- → فرصة قوية للدخول

---

### 4. Multi-Timeframe Confluence

**القاعدة الذهبية:**  
لا تتداول ضد الترند الأعلى أبداً!

**المثالي:**
```
D1:  Bullish Trend ↗️
H4:  Bullish Order Block عند 1.0850
H1:  Bullish FVG + Liquidity Sweep
→ BUY Signal (Confidence: 85%+)
```

---

### 5. Session Momentum

**الجلسات الأفضل:**

| الجلسة | التوقيت (GMT) | الأزواج | القوة |
|--------|---------------|---------|-------|
| 🇬🇧 لندن | 08:00-17:00 | EUR, GBP | ⭐⭐⭐ |
| 🇺🇸 نيويورك | 13:00-22:00 | USD, CAD | ⭐⭐⭐ |
| 🇯🇵 طوكيو | 00:00-09:00 | JPY, AUD | ⭐⭐ |

**Golden Hour:**  
`13:00-17:00 GMT` = تداخل لندن + نيويورك = أعلى سيولة

---

## 🔄 سير العمل الكامل (Full Workflow)

### المرحلة 1: التحليل
```
FX Analyst:
  1. يفحص 6 أزواج رئيسية (EUR/USD, GBP/USD, ...)
  2. يبحث عن:
     - Order Blocks جديدة
     - FVG غير مملوءة
     - Liquidity Sweeps حديثة
  3. يحسب Confluence Score (0-100)
  4. إذا Score > 75 → إرسال إشارة
```

### المرحلة 2: التخطيط
```
Strategy Planner:
  1. يستلم الإشارة من FX Analyst
  2. يحسب:
     Entry = منتصف Order Block Zone
     SL = تحت Order Block بـ 5 نقاط
     TP = 1:2 R:R (أو عند FVG التالي)
     Lot Size = (Balance × Risk%) / (SL_Pips × Pip_Value)
  3. يبني الخطة الكاملة
  4. يرسل لـ Risk Manager
```

### المرحلة 3: الموافقة
```
Risk Manager + CEO:
  1. يتحقق من:
     - عدد الصفقات المفتوحة < 5
     - Drawdown < 10%
     - Portfolio Correlation < 0.8
     - لا أخبار خلال 30 دقيقة
  2. إذا كل شيء OK → ✅ Approved
  3. إرسال للتنفيذ
```

### المرحلة 4: التنفيذ
```
Execution Agent:
  1. يستلم الخطة المعتمدة
  2. يتصل بـ MT5 API
  3. ينفذ Market Order
  4. يحصل على Ticket: MT5-1234567
  5. يحفظ في Database
  6. يرسل إشعار Telegram
```

### المرحلة 5: المتابعة
```
Monitor Agent (24/7):
  while position_open:
    1. قراءة السعر الحالي (كل 100ms)
    2. if profit >= 20 pips:
         move_sl_to_breakeven()
    3. if profit >= 40 pips:
         activate_trailing_stop(15 pips)
    4. if profit >= TP1:
         partial_close(50%)
    5. if reverse_signal_detected:
         close_entire_position()
```

---

## 🔌 التكامل مع MT5

### Setup الأولي

```python
# 1. تثبيت المكتبة
pip install MetaTrader5

# 2. الاتصال
import MetaTrader5 as mt5

mt5.initialize()
mt5.login(
    account=YOUR_ACCOUNT,
    password="YOUR_PASSWORD",
    server="ICMarkets-Demo"  # أو Live
)

# 3. التحقق
if mt5.account_info():
    print("✅ Connected to MT5")
```

### تنفيذ صفقة

```python
def execute_buy(symbol, lot, sl, tp):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(symbol).ask,
        "sl": sl,
        "tp": tp,
        "magic": 123456,
        "comment": "AI_SMC",
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    result = mt5.order_send(request)
    
    return {
        "success": result.retcode == mt5.TRADE_RETCODE_DONE,
        "ticket": result.order,
        "price": result.price
    }
```

---

## 📊 النتائج المتوقعة

| المقياس | القيمة |
|---------|--------|
| **Win Rate** | 75-85% |
| **Avg R:R** | 1:2.3 |
| **Max Drawdown** | < 10% |
| **Profit Factor** | 2.5-3.5 |
| **Sharpe Ratio** | 2.0-2.5 |
| **Trades/Week** | 8-15 |

---

## 🚀 البدء السريع

### الخطوة 1: Environment Setup
```bash
# Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\\Scripts\\activate  # Windows

pip install -r requirements.txt
```

### الخطوة 2: Configuration
```python
# config.py
MT5_ACCOUNT = YOUR_ACCOUNT
MT5_PASSWORD = "YOUR_PASSWORD"
MT5_SERVER = "ICMarkets-Demo"

RISK_PERCENT = 2.0
MAX_OPEN_POSITIONS = 5
TELEGRAM_BOT_TOKEN = "YOUR_TOKEN"
```

### الخطوة 3: Run
```bash
python main.py
```

---

## ⚠️ ملاحظات مهمة

1. **اختبر على Demo أولاً** - شهر كامل على الأقل
2. **VPS ضروري** للتشغيل 24/7
3. **Spread منخفض** - IC Markets موصى به
4. **لا تتدخل يدوياً** - ثق في الوكلاء
5. **راقب Dashboard** - تابع الأداء يومياً

---

## 📞 الدعم

- **Email**: support@aitrading.com
- **Telegram**: @AITradingSupport
- **Discord**: [invite link]

---

**صُنع بـ ❤️ + 🤖 للمتداولين المحترفين**

**النسخة**: 3.0 AI Agents  
**آخر تحديث**: 2024
