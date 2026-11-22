# سجل التعديل: فلتر MAGIC_NUMBERS لهدف ووقف السلة (مبني على P5)

## المشكلة التي تم إصلاحها
في `MonitorAgent.run_cycle()` كان حساب ربح/خسارة السلة (`base_target_usd` و `basket_max_loss_usd`) واستدعاء `close_all_positions()` يشملان جميع الصفقات المفتوحة على الحساب دون تمييز، ما قد يؤدي إلى إغلاق الصفقات اليدوية (`magic=0`) أو صفقات أنظمة أخرى على نفس الحساب، أو إطلاق هدف السلة بسبب ربح صفقة يدوية.

## التعديلات الجراحية (3 ملفات + ملف اختبارات)
1. **`backend/config.py`**
   - إضافة مفتاح `"basket_filter_by_magic": True` في `STRATEGY` بجانب `basket_max_loss_usd`.
2. **`backend/core/mt5_connector.py`**
   - تحديث `MT5Connector.close_all_positions(symbol=None, reason="AI_Emergency", magic_numbers=None)` لتصفية الصفقات المغلقة حسب `magic_numbers` عند تمريرها، مع إبقاء السلوك السابق كاملاً عند `magic_numbers=None`.
3. **`backend/agents/monitor_agent.py`**
   - تصفية `basket_positions` في `run_cycle()` وفق `MAGIC_NUMBERS.values()` عند تفعيل `basket_filter_by_magic`.
   - حساب `total_profit` وفحص `base_target_usd` / `basket_max_loss_usd` على `basket_positions` فقط.
   - إغلاق صفقات النظام فقط عبر `_close_basket_positions()` (مع توافق عكسي للموكات القديمة)، وتمرير `other_positions` إلى `_sync_closed_trades()`.
4. **`tests/test_basket_magic_filter.py`**
   - 6 اختبارات سلوكية تغطي عدم تأثر الصفقات اليدوية/الخارجية بربح أو خسارة السلة، وإغلاق صفقات النظام فقط، والتوافق العكسي لـ `MT5Connector.close_all_positions`.

## التثبيت والتحقق
انسخ الملفات فوق مسار المشروع (بعد P5) ثم شغّل:
```bash
PYTHONPATH=. python -m unittest tests/test_p5_monitor_agent.py tests/test_basket_magic_filter.py -v
```
