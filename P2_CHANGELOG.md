# سجل إصلاحات الدفعة الثالثة (P2: ربط Meta-Model الحي و`SUGGEST_MODE` والامتثال لـ `AGENTS.md`)

تاريخ التجهيز: 2026-11-20  
الفرع المستهدف: `chore/baseline-snapshot`  
*(ملاحظة: هذه الحزمة مبنية فوق الدفعتين الأولى P0 والثانية P1 — فكّ ضغطها مباشرة داخل جذر المشروع بعدهما).*

## كيفية التطبيق والتحقق الشامل
فكّ ضغط `forex_trading_system_p2_fixes.zip` داخل جذر المشروع (`F:\config\Forex Trading System`) مع السماح بالاستبدال، ثم شغّل جميع اختبارات الدفعات الثلاث معاً:

```bash
PYTHONPATH=. %LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest tests/test_p0_critical_fixes.py tests/test_p1_closed_loop_and_quant.py tests/test_p2_wiring_and_governance.py tests/test_code_healing_agent.py tests/test_phase0_safety.py -v
```

## قائمة الملفات المعدّلة (10 ملفات)

1. **`backend/agents/learning_agent.py`**
   - حفظ نموذج `MetaLabelingClassifier` المعاير على القرص (`backend/models/meta_model.pkl`) وإعادة تحميله تلقائياً في `_load_model()`.
   - إزالة الدقة الافتراضية المُلفقة `70.0%` عند تحميل النموذج (التزاماً بقاعدة `AGENTS.md`).
2. **`backend/core/safe_execution_gateway.py`**
   - إضافة الوسيط `meta_probability` وحصر تشغيل `CalibratedKellySizer` فقط عند توفر احتمال معاير حقيقي من `MetaLabelingClassifier` (منع تمرير نسبة التصويت الخام غير المعايرة إلى معادلة Kelly).
3. **`backend/agents/execution_agent.py`**
   - تمرير `ml_prob` القادم من مجلس الظل (والمتصل بـ `LearningAgent.predict`) إلى `SafeExecutionGateway.execute_signal(..., meta_probability=meta_prob)`.
4. **`agents/omega_risk_governor.py`**
   - استيراد ودمج `CalibratedKellySizer` فعلياً داخل `OmegaRiskGovernor.adjudicate()` عبر الوسيط الاختياري `calibrated_p_win`.
5. **`institutional/code_healing_agent.py`**
   - تثبيت الوضع الافتراضي على `AgentExecutionMode.SUGGEST_MODE` بدلاً من `AUTONOMOUS_SANDBOX`.
   - إضافة مصنع `CodeHealingAgent.for_http_api(project_root)` مع قفل مسارات صارم `_is_path_allowed()` يمنع أي وصول خارج جذر المشروع.
6. **`backend/agents/news_agent.py`**
   - إزالة الأرقام العشوائية المُلفقة (`24820` + `random.uniform`) من `get_social_buzz()` واستبدالها بتوزيع المشاعر المقيس فعلياً من مصادر الأخبار المتصلة فقط.
7. **`backend/agents/tradingagents_bridge.py`**
   - إزالة السعر الاحتياطي المُلفق (`1.0850` / `RSI 52.4`) عند انقطاع الشبكة، وإزالة نص `"54/100 (Neutral to Greed)"` المصطنع.
8. **`tests/test_autonomous_master.py`**
   - دمج التعريفَين المكررين لـ `tearDownClass` في دالة واحدة تستعيد `delta._try_fetch_forex_factory` وتنظّف المجلد المؤقت معاً.
9. **`tests/test_p2_wiring_and_governance.py`** *(ملف اختبار جديد)*
   - 6 اختبارات تحقق تغطي `SUGGEST_MODE` وقفل المسارات وربط `Meta-Model` و`OmegaRiskGovernor` وخلوّ الكود من الأرقام المُلفقة.
10. **`P2_CHANGELOG.md`** — هذا الملف التوثيقي.
