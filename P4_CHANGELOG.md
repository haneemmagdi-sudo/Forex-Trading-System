# سجل P4 — إعادة تسمية `agents/` الجذرية إلى `council/` + حارس تعارض الأسماء

تاريخ التجهيز: 2026-11-21 · مبنية فوق P0 وP1 وP2 **وP3** (طبّقها أولاً: `tests/test_p2_wiring_and_governance.py` هنا يبني على نسخة P3).

## المشكلة
حزمتان بنفس الاسم `agents`: الجذرية (مجلس الوكلاء الخماسي) و`backend/agents/` (المحرك الحي). Python يحمّل الأولى ويخزّنها في `sys.modules`، فتنجح ملفات الاختبار منفردة (كل ملف في عملية، كما تفعل ملفات `.bat`) ويفشل التشغيل المشترك.
القياس قبل P4: `python -m unittest discover -s tests` ← 97 اختباراً، خطأ واحد (`test_phase0_safety`: `No module named 'agents.base_agent'`)، وتخطّي صامت لثلاثة اختبارات P3.
وكانت الاختبارات تتحايل عليه (تحميل ملف المجلس بالمسار، وتبديل `sys.modules["agents"]`).

## خطوات التطبيق (بهذا الترتيب)
المجلد لا يُنقل بملف zip، فالنقل أنت تفعله (يحفظ تاريخ git ولا يخاطر بنسخة أقدم من ملفاتك):
```powershell
cd "F:\config\Forex Trading System"
git mv agents council                       # أو: Rename-Item agents council
Remove-Item -Recurse -Force agents -ErrorAction SilentlyContinue      # بقايا __pycache__ إن بقي المجلد
Get-ChildItem council -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
# ثم فكّ forex_trading_system_p4_fixes.zip في الجذر مع الاستبدال
$env:PYTHONPATH="."; python -m unittest discover -s tests
```
⚠️ لا تُعد تطبيق حزم P0/P2 القديمة بعد الآن: ملفاها `agents/beta_orderflow_agent.py` و`agents/omega_risk_governor.py` يعيدان إنشاء `agents/` (سيكتشفه الحارس).

## ما تغيّر (10 ملفات + هذا السجل)
- `main_orchestrator.py` و`autonomous_master_orchestrator.py`: `from agents import …` ← `from council import …`؛ في الثاني أيضاً استيراد `omega_risk_governor` ومسارات الملفات الأربعة التي يفحصها `audit_and_verify`.
- `backend/agents/__init__.py`: تعليق صحيح بدل التعليق القديم الذي ادّعى أن الشجرة نُقلت إلى `institutional/`.
- اختبارات: `test_autonomous_master` و`test_phase0_safety` و`test_p0_critical_fixes` ← استيراد عادي من `council` وحُذف التحايل؛ `test_p2_wiring_and_governance` ← المسار الجديد.
- **`tests/test_no_package_name_collision.py` (جديد — الحارس، 6 فحوص):**
  1. لا اسم استيراد مشترك بين الجذر و`backend/` (مع استثناء مقصود موثّق: `config`).
  2. `council` و`backend/agents` يُستوردان معاً في عملية واحدة وبكلا ترتيبي `sys.path`، وكل حزمة تُحلّ من مكانها.
  3. لا ملفات مجلس ولا `__init__.py` داخل `agents/` الجذرية (يكشف نسيان الحذف/النقل).
  4. فحص AST: لا استيراد قديم `from agents import <مجلس>` أو `agents.<وحدة مجلس>` في أي ملف بايثون.
  5. إن وُجدت `config/__init__.py` جذرية: تعطي `STRATEGY` و`META_GATE` بالقيم نفسها بكلا الترتيبين (يُتخطّى إن لم توجد).
- `.antigravityrules` (سطران: شجرة المجلدات والسطر 62) و`ARCHITECTURE.md` (بند جديد في §6): تحديث مسارات فقط. إن عدّلتَ هذين الملفين بعد رفعهما إليّ فطبّق التعديلات يدوياً (الأسطر محددة أعلاه) بدل استبدال الملف.

## القياس بعد P4
- `discover` في عملية واحدة: **110 اختبارات ناجحة** (تخطٍّ واحد: فحص `config` لأن نسختي لا تحوي `config/` الجذرية — سيُشغَّل عندك).
- الحارس على الشجرة القديمة (قبل النقل): **فشلت 5 من 6** فحوص، فهو يمسك التعارض فعلاً.
- الاختبارات كل ملف على حدة (كما في `.bat`): كلها ناجحة.

## لم أغيّره / يحتاج منك
- تعليقات رأس ملفات المجلس نفسها قد تذكر `agents/…` (تجميلي، لم أرفع ملفاتك لأتجنب استبدال نسخة أحدث).
- ملفات لم أرها (`docs/` وسكربتات أخرى ونحوها). تحقق بهذا الأمر وأرسل لي النتيجة إن ظهر شيء:
```powershell
Get-ChildItem -Recurse -File -Include *.py,*.bat,*.md,*.mq5,*.mqh,*.json,*.ps1 | Where-Object { $_.FullName -notmatch 'node_modules|\\.git\\|__pycache__|openbb_source|tradingagents_source|dist' } | Select-String -Pattern 'from agents import|import agents|agents[\\/](alpha|beta|gamma|delta|omega)'
```
- اقتراح: أضف `tests\test_no_package_name_collision.py` إلى `Run_Autonomous_System.bat` ضمن اختبارات الانحدار (لم أعدّل ملفات `.bat`).
- إن أخفق الفحص 1 عندك باسم غير `agents` فهو تعارض حقيقي آخر (حزمة جذرية وأخرى في `backend/` بنفس الاسم) وليس خللاً في الحارس.
