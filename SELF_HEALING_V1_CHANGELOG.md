# سجل الدفعة الثالثة والأخيرة: الترميم الذاتي ومراقب انجراف الألفا وبوابة unittest (2026)

تاريخ التجهيز: 2026-11-22  
متوافقة بالكامل مع حزم **P3 + P4 (`council/`) + P5 + فلتر السلة + ترقيات الدخول 2026 v2 + الدفعتين 1 و 2**.

## الملفات المُحدّثة والمُضافة (5 ملفات + هذا السجل)

1. **`backend/core/runtime_resilience.py`** *(ملف جديد)*
   - **`PageHinkleyDriftDetector` و `AlphaDecayGuard`**: رصد الانحدار التراكمي للأداء (Downward Alpha Decay / Concept Drift) لكل استراتيجية/زوج وتحويله تلقائياً إلى وضع الظل (**Shadow Demotion**) مع إمكانية إعادة التفعيل بعد المراجعة.
   - **`RuntimeResilienceWatchdog`**: كشف توقف نبضات الوكلاء (`Heartbeat Stall`)، وتتبع طفرات زمن التنفيذ (`> 1500ms`)، واسترداد اتصال MT5 تلقائياً بقاطع دائرة (`Circuit-Breaker Reconnect` بحد أقصى للمحاولات وفترة تهدئة).
2. **`institutional/code_healing_agent.py`**
   - إضافة **بوابة اختبار الانحدار الحتمية (`run_unittest_regression` و `verify_candidate_with_tests`)** داخل `DeterministicVerificationGate` بحيث لا يمر أي تصحيح مقترح بمجرد `py_compile` بل يُختبر فعلياً ضد `unittest` مع استعادة ذرية مضمونة للملف الأصلي.
   - الحفاظ الصارم على **`SUGGEST_MODE`** كوضع افتراضي آمن (منع تعديل الكود الحي تلقائياً).
3. **`autonomous_master_orchestrator.py`** *(مبني على P4 — يحفظ استيرادات `council/`)*
   - ترقية `SelfHealingWatchdog` لدمج `RuntimeResilienceWatchdog` و`AlphaDecayGuard` وتوسيع فحص الوحدات ليشمل ملفات 2026 (`champion_challenger`, `reflection_memory`, `runtime_resilience`, `signal_bus`, `voting_engine`) مع دعم تشغيل بوابة `unittest` اختيارياً.
4. **`backend/config.py`** *(يحتفظ بجميع إعدادات P5 + فلتر السلة + 2026 v2 + الدفعتين 1 و 2)*
   - إضافة كتلة `SELF_HEALING_2026` المركزية.
5. **`tests/test_self_healing_and_alpha_drift.py`** *(ملف اختبار جديد)*
   - 6 اختبارات سلوكية تغطي كاشف `Page-Hinkley` والتحويل التلقائي للظل، وكشف توقف النبضات، واسترداد MT5 بقاطع الدائرة، وبوابة `unittest` في `CodeHealingAgent` بوضع `SUGGEST_MODE`.

## التثبيت والتحقق
فكّ ضغط الحزمة في جذر المشروع مع السماح بالاستبدال، ثم شغّل مجموعة الانحدار الكاملة:
```bash
PYTHONPATH=. python -m unittest tests/test_self_healing_and_alpha_drift.py tests/test_bus_priority_and_reflection.py tests/test_learning_champion_rollback.py tests/test_entry_signal_upgrades_2026.py tests/test_p5_monitor_agent.py tests/test_basket_magic_filter.py tests/test_no_package_name_collision.py -v
```
