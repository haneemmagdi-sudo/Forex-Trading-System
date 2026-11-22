# سجل إصلاحات الدفعة الرابعة (P3) — الاحتمال المعاير الصادق + بوابة التفعيل + وحدات البيب/السبريد + الاستيراد الكسول

تاريخ التجهيز: 2026-11-20
الفرع المستهدف: `chore/baseline-snapshot`
*(مبنية فوق P0 وP1 وP2 — طبّق الحزم الثلاث أولاً.)*

## التطبيق والتحقق
فكّ ضغط `forex_trading_system_p3_fixes.zip` داخل جذر المشروع (`F:\config\Forex Trading System`) مع السماح بالاستبدال، ثم:

```bash
PYTHONPATH=. %LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest tests/test_p3_behavioral.py tests/test_p2_wiring_and_governance.py -v
```
بعدها أعد تشغيل الاختبارات السابقة كاملة (`discover -s tests`).

## ما عالجته (بنود تقرير التدقيق 2 و3 و5 و6 و8)

### 2) احتمال معاير حقيقي أو None
- `MetaLabelingClassifier.predict_calibrated()` يُرجع الاحتمال المعاير أو `None` (غير مدرَّب، طول/أسماء خصائص خاطئة، NaN، فشل تنبؤ). لا يُختلق 0.50.
- `LearningAgent.predict_calibrated()` لا يسقط إلى GBM غير المعاير. `LearningAgent.predict()` بقي كما هو (للمجلس الظلّي والقياس) مع تحذير صريح أنه ليس للتحجيم.
- `ExecutionAgent` لم يعد يمرّر `shadow["ml_prob"]` (مصدره غير مضمون) إلى `SafeExecutionGateway`. يأخذ الاحتمال من `MetaProbabilityProvider` فقط.
- `MarketAnalyst._run_shadow_council` يُرفق متجه الخصائص `ml_features` (نفس ترتيب تدريب LearningAgent) بنتيجة الظل ليستعمله التنفيذ.

### 3) بوابة التفعيل خارج العيّنة (`quant_core/activation_gate.py` + `meta_runtime.py`)
- `MetaLabelingClassifier.fit()` يحفظ الآن تنبؤات OOS الحقيقية (Purged K-Fold) وتُحفظ/تُحمَّل مع `meta_model.pkl`.
- لا يصل الاحتمال إلى التحجيم إلا إذا اجتاز النموذج **كل** الشروط: (1) عيّنات OOS ≥ `min_oos_samples`، (2) الحدّ الأدنى لفترة ثقة AUC (bootstrap بالكتل) > 0.5، (3) Brier Skill > 0 مقابل المتنبّئ الثابت.
- ملف `meta_model.pkl` القديم (بلا OOS) ⇒ البوابة مغلقة حتى أول إعادة تدريب. يُعاد تحميل النموذج تلقائياً عند تغيّر الملف.
- الإعدادات في `backend/config.py` → `META_GATE` (والمسار الوحيد `META_MODEL_PATH`).
- **قياس العتبة (محاكاة مونتي كارلو، n=500، 8 خصائص، Purged K-Fold):**

  | الحالة | ثقة 95% | ثقة 99% (المعتمدة) |
  |---|:---:|:---:|
  | ضجيج بلا ميزة — فتح خاطئ | 1/60 | **0/60** |
  | إشارة ضعيفة (AUC≈0.56) — فتح | 13/20 | 12/20 |
  | إشارة متوسطة (AUC≈0.69) — فتح | 20/20 | 20/20 |
  | إشارة قوية (AUC≈0.90) — فتح | 20/20 | 20/20 |

  ⚠️ 0/60 لا يعني أن المعدل صفر؛ الحدّ الأعلى المعقول ≈ 5% (قاعدة الثلاثة). والنموذج يُعاد تدريبه كل ساعة فتتعدد «النظرات»، لذلك اخترت 99%. `min_oos_samples=200` عتبة سياسة (قرارك) وليست رقماً مقيساً.

### 5) قيمة بيب الذهب في مسار MT5 الحي
- `get_pip_value` الحي صار `tick_value × pip_size / tick_size` بنفس `get_pip_size` المستعمل في `RiskManager` (دالة `MT5Connector.compute_pip_value`).
- قبل P3 للذهب (خانتان): كان يخرج ≈ 1$ بدل 10$ ⇒ عند تعطيل `manual_lot_enabled` يكبر اللوت 10 مرات. اختبار طرفي: خسارة SL الفعلية ÷ المخاطرة المقصودة = **10.0 قبل / 1.0 بعد**.
- بيانات `symbol_info` غير صالحة (tick_size=0…) ترجع الآن إلى الجدول الاحتياطي الموثّق بدل `0.0`.

### 6) وحدة السبريد
- `get_tick` الحي يُرجع السبريد بوحدة **البيب** لكل الرموز: `(ask − bid) / get_pip_size` (دالة `compute_spread_pips`). كان الذهب بوحدة 0.01$.
- `symbol_spread_limits["XAUUSD"]`: `40.0` → `4.0` (نفس الحدّ بالدولار: 0.40$). الفضة والباقي بلا تغيير.
- أثر جانبي مقصود: `spread_ratio` في البوابة (سبريد ÷ ATR بالبيب)، وتكلفة السبريد في `backtest_walkforward`، وشرط `spread > 20` في المناظرة، كلها تصبح متسقة للذهب.

### 8) الاستيراد الكسول في `ml_models`
- حُذف الاستيراد المباشر لـ `risk_adjusted_reward` و`cross_asset_agent` (السطران 68–69) وأُضيف الأسماء الأربعة إلى `_LAZY_IMPORTS`. `ml_models.CrossAssetGraphAgent` وأخواتها تعمل كما كانت عند أول وصول.
- لم أقِس زمن الاستيراد (لا أستطيع على بيئتي). الاختبار يثبت **ما لا يُحمَّل** عند `import ml_models` وليس المدة.

## لم يُغيَّر عمداً
- **البند 1**: `manual_lot_enabled: True` ما زال يتخطى Kelly وسقف 1.5% (قرارك). حتى تغيّره لا يتأثر الحجم الفعلي بكل ما سبق.
- **البند 4** (معادلة Kelly النسبية) و**البند 7** (بوابة M1).

## الملفات (11)
`backend/config.py` · `backend/core/mt5_connector.py` · `backend/agents/{learning,market_analyst,execution}_agent.py` · `ml_models/__init__.py` · `quant_core/meta_model.py` · `quant_core/activation_gate.py` *(جديد)* · `quant_core/meta_runtime.py` *(جديد)* · `tests/test_p3_behavioral.py` *(جديد — 35 اختباراً سلوكياً)* · `tests/test_p2_wiring_and_governance.py` *(تعديل سطر واحد: كان يثبّت تمرير `ml_prob` الخام)*
