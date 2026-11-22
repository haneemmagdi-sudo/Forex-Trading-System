# سجل الدفعة الثانية: توحيد SignalBus بأولويات حقيقية وربط ذاكرة التأمّل AgentReflection (2026)

تاريخ التجهيز: 2026-11-22  
متوافقة بالكامل مع حزم **P3 + P4 (`council/`) + P5 + فلتر السلة + ترقيات الدخول 2026 v2 + الدفعة الأولى**.

## الملفات المُحدّثة والمُضافة (6 ملفات + هذا السجل)

1. **`backend/core/signal_bus.py`**
   - تفعيل **طابور أولويات حقيقي (`heapq` Priority Queue)** عبر `enqueue()`, `drain_priority_queue()`, `publish_batch()`, و`start_dispatcher()` بحيث تسبق تنبيهات الطوارئ (`priority=2` مثل `dd_alert` و`news_alert` العالي) الإشارات (`priority=1`) والتحليلات (`priority=0`) مع الحفاظ على التوافق العكسي الكامل لدالة `publish()`.
   - دعم **أولوية تنفيذ المشتركين (`subscribe(topic, handler, priority=...)`)** لتنفيذ حراس المخاطر قبل المسجّلات العادية.
   - إضافة **`CouncilStateBridge`** (`bus.attach_council_bridge()`) لجسر التواصل الحي بين `SignalBus` ومجلس الوكلاء الخماسي `council/`.
2. **`backend/core/reflection_memory.py`** *(ملف جديد)*
   - قارئ نشط لجدول `agent_reflections` يحوّله من ذاكرة للكتابة فقط إلى توصية قرار رقمية `ReflectionAdvisory` لكل `(symbol, fsm_regime)` مع كاش قصير الأمد (30 ثانية) يُلغى فوراً عند إغلاق أي صفقة.
   - يحسب `confidence_penalty` و`threshold_penalty` ويفعّل **التبريد المؤقت (`temporary_cooldown`)** عند 4 خسائر متتالية خلال 48 ساعة.
3. **`backend/agents/market_analyst.py`** *(مبني على الدفعة الأولى)*
   - استشارة `ReflectionMemoryReader` قبل إصدار كل إشارة لحجب الزوج/النظام عند التبريد المؤقت (`REFLECTION_COOLDOWN`) أو دمج عقوبة التأمل مع `_regime_confidence_boost`، وإلغاء كاش القارئ فور إغلاق الصفقة.
4. **`council/omega_risk_governor.py`** *(تحت `council/` وفق P4، مبني على 2026 v2)*
   - قبول `bus_context` (من `CouncilStateBridge`) و`reflection_advisory` (من `ReflectionMemoryReader`) لفرض فيتو فوري عند `BUS EMERGENCY DD` أو `BUS NEWS BLACKOUT` أو `REFLECTION COOLDOWN`، ورفع العتبة الديناميكية تلقائياً بعقوبات التأمل والـ Bus.
5. **`backend/config.py`** *(يحتفظ بجميع إعدادات P5 + فلتر السلة + 2026 v2 + الدفعة الأولى)*
   - إضافة كتلة `COMMUNICATION_REFLECTION_2026` المركزية.
6. **`tests/test_bus_priority_and_reflection.py`** *(ملف اختبار جديد)*
   - 6 اختبارات سلوكية شاملة لطابور الأولويات، أولوية المشتركين، جسر `CouncilStateBridge`، القراءة من SQLite `agent_reflections`، والتكامل الكامل مع `MarketAnalystAgent` و`OmegaRiskGovernor`.

## التثبيت والتحقق
فكّ ضغط الحزمة في جذر المشروع مع السماح بالاستبدال، ثم شغّل:
```bash
PYTHONPATH=. python -m unittest tests/test_bus_priority_and_reflection.py tests/test_learning_champion_rollback.py tests/test_entry_signal_upgrades_2026.py tests/test_p5_monitor_agent.py tests/test_basket_magic_filter.py tests/test_no_package_name_collision.py -v
```
