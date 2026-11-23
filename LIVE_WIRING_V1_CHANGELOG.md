# LIVE_WIRING_V1 — توصيل ترقيات 2026 بالمسار الحي

**السبب:** مراجعة التسليم أثبتت أن عدة ترقيات (الدفعتان 2 و3) كانت مُختبَرة كوحدات لكنها غير موصولة بالمسار الحي:
`adjudicate()` يُستدعى بلا `bus_context` ولا `reflection_advisory`، و`AlphaDecayGuard.record_trade` و`record_heartbeat` بلا أي مُستدعٍ إنتاجي.

## ترتيب التثبيت
بعد الحزم الخمس السابقة (الترتيب 5). **قبل الاستخراج:** نفّذ `git status` وتأكد أن الملفات المعدّلة أدناه ليس فيها تعديلات محلية غير محفوظة،
وإلا فاستخدم `git apply live_wiring_v1.patch` بدل استبدال الملفات.

## الملفات (8 معدّلة + 1 جديد)
| الملف | التعديل |
| :--- | :--- |
| `backend/core/signal_bus.py` | `CouncilStateBridge`: صلاحية زمنية للتنبيهات (TTL=1800ث) + تصدير الحالة لملف ذري `backend/models/council_bus_state.json` + `load_council_context()` لعملية المجلس. منطق سياق واحد مشترك. |
| `backend/core/reflection_memory.py` | `ANY_REGIME="*"`: استعلام على مستوى الزوج. |
| `main_orchestrator.py` | `build_omega_live_context()` + `make_reflection_reader()`، وتمرير `bus_context` و`reflection_advisory` إلى `adjudicate()`. |
| `autonomous_master_orchestrator.py` | نفس التمرير + تغذية `AlphaDecayGuard.record_trade` من الصفقات المغلقة في `run_master_cycle`. |
| `backend/main.py` | `bus.attach_council_bridge().enable_state_export()` عند بدء التشغيل. |
| `backend/core/runtime_resilience.py` | حد صمت لكل وكيل = `max(60ث, 3×فاصل الدورة)` + `forget_heartbeat()` + `get_runtime_watchdog()`. |
| `backend/agents/base_agent.py` | تسجيل نبضة كل دورة، ومسحها عند `stop()`/`pause()`. |
| `backend/agents/monitor_agent.py` | تسجيل الوكيل المتوقف مرة واحدة (قراءة فقط). |
| `tests/test_live_wiring_council_context.py` | 13 اختباراً عبر المنسّقين الفعليين. |

## قرارات تصميم مهمة (اكتُشفت أثناء التنفيذ)
1. **عمليتان منفصلتان:** `SignalBus` داخل عملية الـ backend والمجلس عملية أخرى، فجسر داخل عملية المجلس كان سيبقى فارغاً. لذلك يصدّر الـ backend لقطة الحالة لملف، ويقرؤها المجلس.
2. **TTL ضروري:** `dd_alert` يُبثّ عند السوء فقط ولا يُبثّ عند التعافي؛ بدون TTL كان أول `EMERGENCY_STOP` سيحجب المجلس للأبد. التنبيه المستمر يجدد المهلة.
3. **مفردات الأنظمة مختلفة:** المجلس (`TRENDING_LOW_VOL`…) ≠ `agent_reflections.fsm_regime` (`STRONG_TREND`…)، لذا يُستعلم عن التأمّل على مستوى الزوج.
4. **غياب الملف أو تلفه = لا فيتو** (الـ backend غير شغّال)، وليس إغلاقاً للنظام.

## تغيير سلوكي بعد التثبيت
- بعد `EMERGENCY_STOP` يصدر المجلس `STAND_DOWN` طوال 30 دقيقة من آخر تنبيه.
- 4 خسائر متتالية على الزوج خلال 48 ساعة تُوقف إشارات المجلس لذلك الزوج مؤقتاً.
- يبدأ الـ backend بكتابة `backend/models/council_bus_state.json` (يجب أن يكون الـ backend شغّالاً ليتلقى المجلس السياق).

## ما لم يُوصَّل بعد (متعمّد، يحتاج قرارك)
- `calibrated_p_win`: لا مصدر ميزات ثمانية صادق في مسار المجلس (يُبنى من `VotingEngine`).
- `regime_win_rate` في Omega، و`bus_threshold_shift` (يبقى 0 لاختلاف المفردات).
- `record_execution_latency` و`check_and_recover_mt5`: ينفّذان إعادة اتصال حية؛ لم أفعّلهما دون موافقتك.
- `AlphaDecayGuard` في الذاكرة فقط ويعمل لكل تشغيل (المنسّق يشغّل دورة واحدة)، والتحويل للظل **معلوماتي**: يظهر في تقرير الفحص ولا يمنع الإشارات.

## التحقق
`PYTHONPATH=. python -m unittest discover -s tests` → 177/178 ناجحاً؛ الإخفاق الوحيد `test_tradingagents_api` سابق للتعديل (يفشل بنفس الشكل على الأساس).
اختبارات الطفرة: حذف التمرير أو تغذية الحارس يُفشل الاختبارات المقابلة.
