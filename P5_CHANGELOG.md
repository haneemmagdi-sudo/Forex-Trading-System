# P5 — مفتاحا اللوت في الإكسبرت + إصلاح الوكيل المراقب

## 1) الإكسبرت (mql5_ea) — لم يُترجَم (لا MetaEditor هنا): اضغط Compile عندك أولاً
- `InstitutionalExecutor.mq5`: مدخلان جديدان في مجموعة «2b. Position Sizing»:
  - `InpFixedLotEnabled = true` — true: لوت ثابت | false: حساب بالمخاطرة (السلوك السابق).
  - `InpFixedLot = 0.01` — يُقرَّب لأسفل لخطوة الحجم ثم يُحصر بين SYMBOL_VOLUME_MIN و SYMBOL_VOLUME_MAX.
- `TradeManager.mqh`: `SetLotPolicy()` و`FixedLot()` و`ResolveLots()`؛ `ExecuteSignal` يستدعي `ResolveLots`.
  `CalculateLotSize` (حساب المخاطرة) **كما هي دون أي تغيير**؛ توقيع `Init()` لم يتغيّر.
- ملاحظة: بعض العقود حدّها الأدنى أعلى من 0.01 — حينها يُستخدم حدّ الوسيط الأدنى (لا يمكن أقل منه).

## 2) الوكيل المراقب — الأسباب الجذرية لـ«لا يفعل شيئاً»
1. `use_dynamic_sl=False` (إعدادك) كان يُنهي `_manage_position` مبكراً ⇒ لا Break-even ولا Trailing ولا Partial أبداً،
   ولا يُكتب أي سطر في السجل ⇒ يبدو الوكيل ميتاً.
2. صفقة بلا سجل في DB (فشل الحفظ أو فُتحت من الإكسبرت) كانت تُهمَل بصمت.
3. الإغلاق الجزئي مع لوت 0.01: `max(0.01, 0.01×30%)` = 0.01 ⇒ كان سيُغلق **الصفقة كلها** باسم «جزئي» عند +10 بيب.
4. SELL بلا SL لا ينتقل إلى التعادل أبداً (`be_sl < 0` دائماً خطأ).
5. `db` غير معرّف في `finally` عند فشل فتح الجلسة (NameError).

## الإصلاح (مفاتيح في STRATEGY — لا حذف لأي ميزة)
| المفتاح | الافتراضي | الأثر |
|---|---|---|
| `monitor_breakeven_enabled` | True | SL → +2 بيب عند ربح ≥ `breakeven_pips` (20) |
| `monitor_trailing_enabled`  | True | وقف متحرك عند ≥ `trail_activate_pips` (40)، في اتجاه الربح فقط |
| `monitor_partial_enabled`   | False | الإغلاق الجزئي — لا معنى له بلوت 0.01 |
| `monitor_manage_untracked`  | True | يدير صفقات بلا سجل DB إن كان magic ضمن MAGIC_NUMBERS |
| `monitor_heartbeat_cycles`  | 60 | سطر حالة في السجل: مفتوحة/مُدارة/مُتخطّاة/عائم |
- الإدارة صارت مستقلة عن `use_dynamic_sl` (الذي يبقى يتحكم بتوليد SL/TP عند الفتح فقط).
- `MT5Connector.compute_partial_volume` + حارس في `partial_close`: لا يُغلق أبداً الصفقة كلها، يرفض إن كان الحجم لا يُقسَّم.
- هدف السلة 2$ ووقف السلة 20$ وحماية DD **كما هي**.

## الاختبارات
`tests/test_p5_monitor_agent.py` — 14 اختباراً سلوكياً بـ MT5 وهمي. على الشجرة القديمة: 9 من 14 تفشل. الحزمة الكاملة: 124 اختباراً OK (1 skip).

## لم يُغيَّر عمداً (للعلم)
- مسافة Trailing الفعلية = الخطوة × `trail_atr_multiplier` (1.5): 27 بيب بدل 18 المكتوبة في التعليق (37.5 / 18 للأنظمة الأخرى).
- هدف السلة يغلق **كل** المراكز في الحساب (بما فيها اليدوية) لأن `get_open_positions` لا يفلتر بالـ magic.
