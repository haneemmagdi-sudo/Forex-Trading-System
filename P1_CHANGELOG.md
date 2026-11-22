# سجل إصلاحات الدفعة الثانية (P1: إغلاق الحلقة + رياضيات `quant_core`)

تاريخ التجهيز: 2026-11-20  
الفرع المستهدف: `chore/baseline-snapshot`  
*(ملاحظة: هذه الحزمة مبنية فوق الدفعة الأولى P0 — يمكنك فكّ ضغطها مباشرة في جذر المشروع بعد الدفعة الأولى).*

## كيفية التطبيق والتحقق
فكّ ضغط `forex_trading_system_p1_fixes.zip` داخل جذر المشروع (`F:\config\Forex Trading System`) مع السماح بالاستبدال، ثم شغّل:

```bash
PYTHONPATH=. %LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest tests/test_p0_critical_fixes.py tests/test_p1_closed_loop_and_quant.py -v
```

## قائمة الملفات المعدّلة (10 ملفات)

1. **`backend/core/safe_execution_gateway.py`**
   - إضافة `_record_trade_vector()` لتسجيل كل صفقة مفتوحة مع رقم تذكرة MT5 (`ticket`) في `trade_vectors` عند التنفيذ، مما يجعل `update_outcome_by_ticket()` يطابق الصف الفعلي ويغلق حلقة التعلم التكيفية.
2. **`backend/agents/monitor_agent.py`**
   - تتبّع `mae_pips` و`mfe_pips` اللحظي لكل صفقة مفتوحة في `_excursion_tracker`.
   - استخراج `commission` و`swap` الحقيقية من سجل صفقات MT5 وتضمينها في صافي الربح وفي حدث `trade_closed` مع `spread_cost` و`mae_pips` و`mfe_pips`.
   - إضافة وقف خسارة طوارئ (`hedge_sl`) لصفقة التحوط في `_activate_hedge()` بدلاً من `sl=0.0`.
3. **`backend/agents/learning_agent.py`**
   - تمرير `spread_cost` و`commission` و`swap` و`mae_pips` و`mfe_pips` إلى `TradeOutcomeRecorder.update_outcome_by_ticket()`.
   - استدعاء `sweep_stale_open_records(max_age_hours=24.0)` في كل دورة تعلم لمنع بقاء أي سجل `OPEN` عالقاً لأكثر من 24 ساعة.
4. **`autonomous_master_orchestrator.py`**
   - ربط `MT5ClosedDealFeedback.inspect_and_sync_closed_deals()` باستدعاء فعلي لـ `self.recorder._db.update_outcome_by_ticket(...)` وتحديث ذاكرة الفخاخ بدلاً من الطباعة فقط.
   - استدعاء `sweep_stale_open_records(max_age_hours=24.0)` في `run_master_cycle()`.
5. **`memory_rag/adaptive_trade_journal.py`**
   - تصحيح مقارنة طوابع ISO-8601 (`T...Z`) داخل `sweep_stale_open_records()`.
   - إزالة التعريف المكرر لدالة `close()`.
6. **`quant_core/labeling.py`**
   - تصحيح معادلة **Deflated Sharpe Ratio (DSR)** لتعمل على شارب لكل صفقة غير مضخّم (وفق Bailey & Lopez de Prado 2014) مع صيغة التباين الصحيحة `(excess_kurt + 2) / 4`.
   - تصحيح `max_drawdown_pct` لحساب نسبة مئوية حقيقية على منحنى رأس المال بدلاً من مجموع النقاط الخام.
   - تصحيح خط الأساس العشوائي (`Monte Carlo`) ليعمل بـ `1000` تجربة افتراضياً مع خصم التكلفة مرة واحدة فقط.
7. **`quant_core/backtester.py`**
   - إزالة `.bfill()` (التي كانت تُحدث تسريباً مستقبلياً) واستبدالها بـ `.ffill().fillna(0.0)`.
   - تصحيح تقسيم نوافذ Walk-Forward لتغطية 100% من البيانات بعد فترة الإحماء بدلاً من إسقاط آخر 25%.
   - حساب `pnl_usd` بقيمة بيب ملائمة للرمز (أزواج الين مقابل الأزواج الرئيسية).
8. **`quant_core/meta_model.py`**
   - إزالة تسريب البيانات في `MetaLabelingClassifier.fit()`: حساب `brier_score` و`roc_auc` و`log_loss` و`out_of_sample_accuracy` على تنبؤات **خارج العينة (OOS)** الحقيقية عبر `PurgedKFold` بشكل منفصل عن `in_sample_accuracy`.
   - إضافة `save(filepath)` و`load(filepath)` لحفظ النموذج المعاير على القرص وإعادة تحميله.
9. **`tests/test_p1_closed_loop_and_quant.py`** *(ملف اختبار جديد)*
   - 6 اختبارات تحقق شاملة تغطي معادلة DSR وDD وWalk-Forward وPurgedKFold OOS (صفر تسريب) وإغلاق حلقة `trade_vectors`.
10. **`P1_CHANGELOG.md`** — هذا الملف التوثيقي.
