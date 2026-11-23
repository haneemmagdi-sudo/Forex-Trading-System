# LIVE_WIRING_V2 — إكمال بنود الإصلاح والتطوير المتبقية

**شرط التثبيت:** V1 مثبَّتة أولاً (الملفات هنا تحتوي تعديلات V1 + V2 معاً للملفات المشتركة).
قبل الاستبدال نفّذ `git status`؛ وإن كان لديك تعديلات محلية على أي ملف أدناه فاستخدم `live_wiring_v1_v2.patch` (V1+V2 مقابل الأساس).

## الملفات (13 معدّلة + 2 جديدة للكود + 3 اختبارات)
| الملف | التعديل |
| :--- | :--- |
| `backend/agents/learning_agent.py` | الميزة الثامنة صارت ATR٪ من السعر (مقيّدة 0–5) بدل 0 دائماً. **النماذج المدرَّبة سابقاً ببُعد ثامن صفري تحتاج إعادة تدريب.** |
| `backend/main.py` | `/api/ml/predict` يبني نفس متجه التدريب المستقر (كان يمرّر ميزات خام = انحراف تدريب/تقديم)؛ تشغيل/إيقاف موزّع طابور الأولويات. |
| `council/tuning.py` (جديد) | قراءة كتل `backend/config.py` حرفياً عبر `ast` (بلا `import config` ولا آثار جانبية). |
| `council/beta_orderflow_agent.py` | `fvg_min_atr_ratio` و`ofi_counter_flow_z` من الإعداد. |
| `council/gamma_redteam_critic.py` | `episodic_top_k` و`episodic_half_life_days` و`memory_cb_atr_ratio` و`memory_cb_min_regime_conf` من الإعداد. |
| `council/omega_risk_governor.py` | `calibrated_fusion_weight` من الإعداد (كان 0.55 ثابتاً). |
| `backend/core/runtime_resilience.py` | `load_self_healing_config()` + `from_config()` للمراقب والحارس؛ **استمرارية حالة `AlphaDecayGuard`** في `backend/models/alpha_guard_state.json` (ذرّي) مع منع احتساب نفس الصفقة مرتين (`deal_id`). |
| `autonomous_master_orchestrator.py` | مفاتيح `SELF_HEALING_2026` تُبنى منها الأدوات؛ تأكيد `require_suggest_mode_live`؛ **تحويل الظل ينفَّذ فعلاً: `STAND_DOWN` للرمز المنحرف**؛ التقرير يذكر عدد الوكلاء المراقَبين. |
| `main_orchestrator.py` | قارئ التأمّل يأخذ قيم `COMMUNICATION_REFLECTION_2026`. |
| `backend/core/mt5_connector.py` | قياس زمن كل `order_send` وتغذية المراقب؛ `refresh_connection_state()`؛ `reconnect()` لـ MT5 الحي فقط. |
| `backend/agents/monitor_agent.py` | كل دورة: `check_and_recover_mt5` (قاطع دائرة: 3 محاولات + تهدئة 30ث). |
| `backend/core/signal_bus.py` + `backend/agents/news_agent.py` | `dispatch()`: التنبيهات (dd/news) عبر طابور الأولويات حين يعمل الموزّع، وإلا نشر مباشر. |
| `tests/test_live_wiring_v2.py` (جديد) | 20 اختباراً. |
| `tests/test_p0_critical_fixes.py`، `tests/test_live_wiring_council_context.py` | تعديل تركيب فقط (اختبار يتجاوز `__init__`؛ إضافة `deal_ticket`). |

## قرارات تصميم
1. **`reconnect()` منفصلة عن `connect()`:** `connect()` يتحوّل عند الفشل إلى yfinance ويضع `connected=True`؛ استخدامه للاستعادة كان سيحوّل موصلاً حياً إلى ورقي بصمت.
2. **التحويل للظل لا يُرفع تلقائياً:** يبقى حتى مراجعة بشرية. لإعادة التفعيل: `python -c "from core.runtime_resilience import *; g=AlphaDecayGuard.from_config(DEFAULT_ALPHA_GUARD_STATE_PATH); g.promote_back('EURUSD')"` (من مجلد `backend`)، أو احذف الرمز من `alpha_guard_state.json`.
3. **`require_suggest_mode_live`:** تأكيد فقط. ضبطه False لا يفتح التعديل الذاتي للكود.
4. **مراقب عملية المجلس لا يتلقى نبضات الـ backend** (عمليتان). لذا يُعرض `monitored_agents` في التقرير كي لا يُقرأ «لا توقف» كفحص فعلي.
5. **طابور الأولويات:** فائدته محصورة بترتيب التنبيهات فيما بينها؛ بقية الرسائل ما زالت تُنشر مباشرة.

## ما لم يُوصَّل عمداً
- `calibrated_p_win`: لا مصدر ميزات ثمانية صادق في مسار المجلس.
- `regime_win_rate`: مفردات أنظمة المجلس ≠ `fsm_regime` المخزَّن، والمتاح معدّل فوز على مستوى الزوج وهو محسوب أصلاً في عقوبة التأمّل (تمريره = عدّ مزدوج).
- `bus_threshold_shift` يبقى 0 للسبب نفسه.

## تغيير سلوكي بعد التثبيت
- رمز يُكتشف انجراف ألفاه يتوقف المجلس عن إشاراته حتى `promote_back()`.
- ثلاث طفرات تأخير متتالية (>1500ms) أو سقوط اتصال MT5 الحي تُطلق إعادة اتصال محدودة.

## التحقق
`PYTHONPATH=. python -m unittest discover -s tests` → 197/198؛ الإخفاق الوحيد `test_tradingagents_api` بيئي سابق (وحدة `aiohttp` غير مثبّتة).
اختبارات الطفرة: إلغاء بوابة الظل، أو منع التكرار، أو قياس الزمن، أو مسار الطابور، أو وزن الدمج — يُفشل الاختبار المقابل.
