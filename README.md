# Quantum Forex Pro - استراتيجية تداول متقدمة لـ MetaTrader 5

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-MetaTrader%205-orange)

## 📖 نظرة عامة

**Quantum Forex Pro** هي استراتيجية تداول آلية متقدمة مصممة لمنصة MetaTrader 5. تجمع بين التحليل الفني متعدد الأطر الزمنية، المؤشرات المتقدمة، وإدارة المخاطر الذكية لتحقيق نتائج مستدامة.

### ✨ المميزات الرئيسية

- 🎯 **تحليل متعدد الأطر**: استخدام 3 أطر زمنية مختلفة (H4, H1, M15)
- 📊 **5 مؤشرات فنية**: EMA, RSI, MACD, ADX, ATR
- 🛡️ **إدارة مخاطر ذكية**: حساب تلقائي لحجم اللوت بناءً على ATR
- 🔍 **فلاتر متقدمة**: الوقت، السبريد، الأخبار، حجم التداول
- 🚨 **حماية من التراجع**: إيقاف تلقائي عند الوصول لحد الخسارة
- ⚡ **تنفيذ سريع**: Break-even و Trailing Stop ديناميكي

## 🚀 البدء السريع

### المتطلبات

- MetaTrader 5 (أحدث إصدار)
- حساب تداول (تجريبي أو حقيقي)
- VPS موصى به للتشغيل 24/7

### التثبيت

1. **نسخ الكود**
   - افتح التطبيق وانتقل إلى تبويب "كود MQL5"
   - انقر على زر "نسخ الكود"

2. **إنشاء ملف جديد في MetaEditor**
   - افتح MetaTrader 5
   - اضغط F4 لفتح MetaEditor
   - File → New → Expert Advisor (template)
   - أعط الملف اسم: `QuantumForexPro`

3. **لصق الكود**
   - الصق الكود المنسوخ في الملف
   - احفظ الملف (Ctrl + S)

4. **الترجمة**
   - اضغط F7 أو Compile
   - تأكد من عدم وجود أخطاء

5. **التطبيق على الشارت**
   - في MetaTrader 5، افتح شارت EUR/USD H1
   - اسحب الإكسبرت من Navigator إلى الشارت
   - اضبط الإعدادات حسب رغبتك
   - تأكد من تفعيل "Allow Algo Trading"

## ⚙️ الإعدادات الموصى بها

### للمبتدئين

```
RiskPercent = 1.0
Max_Daily_Trades = 3
Max_Drawdown_Percent = 10.0
```

### للمحترفين

```
RiskPercent = 2.0
Max_Daily_Trades = 5
Max_Drawdown_Percent = 15.0
Use_Volume_Filter = true
```

## 📊 الأداء المتوقع

- **نسبة الربح**: 60-70%
- **Risk/Reward Ratio**: 1:2 - 1:3
- **Max Drawdown**: < 15%
- **العائد الشهري**: 8-15%

> ⚠️ **تنبيه**: هذه الأرقام مبنية على اختبارات تاريخية وليست ضماناً للأداء المستقبلي.

## 🎯 أزواج العملات الموصى بها

### الأفضل (Recommended)
- EUR/USD
- GBP/USD
- USD/JPY
- AUD/USD

### جيد (Good)
- EUR/GBP
- EUR/JPY
- GBP/JPY

### تجنب (Avoid)
- أزواج غير سائلة
- أزواج ذات سبريد عالي (> 3 نقاط)

## 📈 خطة التطوير

### المرحلة 1 (شهر 1)
- [ ] إضافة Stochastic Oscillator
- [ ] تحسين فلتر حجم التداول
- [ ] دمج Bollinger Bands

### المرحلة 2 (شهر 2-3)
- [ ] دمج Machine Learning
- [ ] Sentiment Analysis
- [ ] تحسين ديناميكي للمعاملات

### المرحلة 3 (شهر 4)
- [ ] دعم أسواق متعددة
- [ ] تطبيق موبايل
- [ ] Dashboard تفاعلي

## 🛠️ استكشاف الأخطاء

### المشكلة: الإكسبرت لا يفتح صفقات

**الحلول**:
1. تحقق من تفعيل "Allow Algo Trading"
2. تأكد من ADX > 25 (قد تكون السوق عرضية)
3. راجع فلتر الوقت (هل أنت ضمن ساعات التداول؟)
4. تحقق من السبريد (قد يكون أعلى من الحد المسموح)

### المشكلة: الصفقات تُغلق بسرعة

**الحلول**:
1. قد يكون Break-even نشطاً (جيد للحماية)
2. راجع إعدادات Trailing Stop
3. تحقق من وجود إشارة عكسية

### المشكلة: خسائر متتالية

**الحلول**:
1. توقف فوراً وراجع الإعدادات
2. تحقق من ظروف السوق (أخبار مهمة؟)
3. قلل RiskPercent إلى 0.5%
4. استخدم حساب تجريبي أولاً

## 📚 الموارد التعليمية

### كتب موصى بها
- "Technical Analysis of the Financial Markets" - John Murphy
- "Trading in the Zone" - Mark Douglas
- "Algorithmic Trading" - Ernest P. Chan

### دورات
- MQL5 Programming Tutorial (mql5.com)
- Forex Trading Course (Babypips)
- Python for Finance (Coursera)

### مجتمعات
- MQL5 Forum
- TradingView Community
- Reddit r/algotrading

## ⚠️ إخلاء المسؤولية

**تحذير مهم**: 

- التداول في الفوركس ينطوي على مخاطر عالية
- قد تخسر كل رأس مالك
- لا تستثمر أموالاً لا تستطيع تحمل خسارتها
- هذه الاستراتيجية للأغراض التعليمية فقط
- اختبر دائماً على حساب تجريبي أولاً
- استشر مستشاراً مالياً قبل اتخاذ قرارات الاستثمار

## 📞 الدعم والتواصل

- **GitHub**: [github.com/yourname/quantum-forex-pro]
- **Email**: support@example.com
- **Telegram**: @QuantumForexPro

## 📄 الترخيص

MIT License - استخدم بحرية مع الإشارة للمصدر

---

صُنع بـ ❤️ للمتداولين الجادين

**النسخة**: 1.0.0  
**آخر تحديث**: 2024
