# AGENTS.md — دليل تشغيلي سريع لأي وكيل ذكاء اصطناعي

> الخريطة الكاملة في [ARCHITECTURE.md](ARCHITECTURE.md). هذا الملف للعمل السريع.
> **القاعدة الأولى: كل رقم في هذا المستودع يجب أن يكون مقيساً. لا تُضِف وعداً ولا رقماً مُلفَّقاً.**

## أين تبدأ حسب المهمة

| المهمة | الملفات |
|---|---|
| إشارة الدخول / المؤشرات / التصويت | `backend/agents/market_analyst.py` · `backend/core/voting_engine.py` · `backend/core/indicators.py` · `backend/core/fsm_engine.py` |
| التنفيذ / المخاطر / الأوامر | `backend/agents/execution_agent.py` · `backend/core/safe_execution_gateway.py` · `backend/core/risk_manager.py` |
| المخارج / المراقبة | `backend/agents/monitor_agent.py` |
| التعلّم / النموذج / التأمّل | `backend/agents/learning_agent.py` |
| مجلس الوكلاء (ظل) | `backend/core/agent_council.py` + `institutional/` |
| الجسر المؤسسي (HMM/تدفق/مناظرة) | `backend/core/execution_bridge.py` → `institutional/*` |
| فريق المحللين المجدول | `backend/agents/analyst_cycle_agent.py` → `institutional/{fx,equity}_analyst.py` … |
| راوتر LLM | `institutional/llm_router.py` |
| وكيل ترميم الأكواد | `institutional/code_healing_agent.py` + نقاط `/api/healing/*` في `backend/main.py` |
| الإعدادات | `backend/config.py` (**المصدر الوحيد**) · `.env` (غير متتبَّع) |
| قاعدة البيانات والجداول | `backend/models/database.py` |
| المعايرة والقياس | `backend/{council_backfill,order_flow_calibration,cascade_calibration}.py` |

## أوامر لا تتغيّر

```bash
# البيئة الصحيحة (لا تستعمل python العاري)
PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe

# الانحدار قبل أي تسليم (16 اختباراً)
PYTHONPATH=. %PY% tests/test_system_integrity.py
PYTHONPATH=. %PY% tests/test_institutional_mas.py
PYTHONPATH=. %PY% tests/test_code_healing_agent.py

# تحقّق نحوي سريع
%PY% -m py_compile <files>
```

## ثوابت يجب احترامها

1. **مجلس الوكلاء في وضع الظل** (`COUNCIL["mode"]="shadow"`): يحكم ويُسجَّل، **ولا يمنع صفقة**.
   أي تغيير يجعله يفلتر يحتاج **دليلاً من `/api/council/report`** لا رأياً.
2. **الفيتوات معطّلة افتراضياً** في `institutional/order_flow_agent.py`,
   `multi_agent_debate.py`, `market_regime_hmm.py` — بسبب معايرة موثّقة داخل كل ملف.
   إعادة تفعيلها = `veto_enabled=True` **مع** إثبات جديد.
3. **`LLMRouter` يفشل صراحةً** عند غياب مزوّد (`AllProvidersExhaustedError`).
   ممنوع إعادة نمط «قرار JSON مُلفَّق» — كان عطلاً حقيقياً.
4. **`SUGGEST_MODE` إلزامي** لوكيل الترميم عبر HTTP: لا كتابة ملفات من الطلب،
   والمسارات محصورة في جذر المشروع وملفات الكود فقط.
5. **`.env` لا يُتتبَّع ولا يُقرأ في التقارير.** عند إضافة إعداد جديد: أضِفه إلى
   `.env.example` بعنصر نائب، ووثّقه في `backend/config.py`.
6. **التغييرات جراحية**: كل سطر مُعدَّل يجب أن يعود إلى طلب المستخدم. لا تنظيف
   مجاور ولا إعادة هيكلة لما لا يحتاج.

## فخاخ ستُكلّفك وقتاً إن تجاهلتها

- **حزمتان باسم `config`**: من `backend/` تُحلّ إلى `backend/config.py`، ومن الجذر إلى
  حزمة `config/`. القيم في `backend/config.py` فقط.
- **قاعدتا وكيل مختلفتان**: `institutional/base_agent.py` (فريق المحللين، وسيطه الأول
  راوتر LLM) و`backend/agents/base_agent.py` (المحرك الحي، وسيطه الأول الاسم + دورة
  asyncio). الخلط بينهما كان يرفع `TypeError: abstract class`.
- **قاعدة البيانات مسار نسبي** (`sqlite:///./trading.db`): شغّل دائماً من `backend/`
  أو أضف `os.chdir` — وإلا يُنشأ ملف فارغ في المجلد الخطأ.
- **حجم عيّنة صغير**: 400-500 صفقة مربوطة بنتائج. أي «تحسين» بلا تقسيم زمني
  تدريب/اختبار سيبدو رائعاً على الورق وخاسراً في الواقع (مُجرَّب: كل عتبة اختيرت
  على التدريب خسرت على الاختبار).
- **`platform/` غير مربوطة** بأي مشغّل. لا تفترض أنها جزء من النظام.

## عند إضافة ميزة تمسّ القرار

1. اجعلها **مقيسة أولاً** (سجّل حكمها مقابل النتيجة في جدول) — لا تُفعّلها كبوابة.
2. أضِف أداة قياس أو استخدم الموجودة (`*_calibration.py`).
3. لا تُفعّل الفلترة قبل ظهور صافي قيمة موجب **خارج العيّنة**.
4. وثّق الأرقام داخل الكود نفسه (كما في `veto_enabled` docstrings).

## ما أُزيل ولماذا

انظر `_archive/2026-10-cleanup/` (الوحدات غير الموصولة، مدخل مكرر، سكربتات عابرة،
وثائق بأرقام غير مسندة، وبرومبت مسرَّب من مساحة عمل أخرى). كل شيء **قابل للاسترجاع**
من هناك أو من commit اللقطة `00c4f7e`.
