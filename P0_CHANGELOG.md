# سجل إصلاحات الدفعة الأولى (P0 الحرجة) — Forex Trading System

تاريخ التجهيز: 2026-11-20  
الفرع المستهدف: `chore/baseline-snapshot`

## كيفية التطبيق على مشروعك
فكّ ضغط ملف `forex_trading_system_p0_fixes.zip` مباشرة داخل مجلد المشروع الجذري (`F:\config\Forex Trading System`) مع السماح باستبدال الملفات المعدّلة فقط، ثم شغّل:

```bash
PYTHONPATH=. %LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest tests/test_p0_critical_fixes.py tests/test_phase0_safety.py -v
```

## قائمة الملفات المعدّلة (14 ملفاً)

1. **`backend/core/mt5_connector.py`**
   - إضافة دالة موحّدة `MT5Connector.get_pip_size(symbol, digits=None)` تدعم `XAUUSD (0.1)` و`XAGUSD/JPY (0.01)` وباقي الأزواج (`0.0001`).
   - تصحيح `get_digits()` ليرجع `2` للذهب والفضة بدلاً من `5`.
   - إزالة عامل الضرب الخاطئ `* 10` من حساب أرباح وضع Paper/Fallback في `get_open_positions()`.
   - توحيد قيمة `XAUUSD` في `get_pip_value()` إلى `10.0` (عقد 100 أونصة × 0.10$ بيب = 10$ لكل لوت قياسي).
2. **`backend/core/risk_manager.py`**
   - استخدام `MT5Connector.get_pip_size(symbol, digits)` في `calc_trade_params()` لحل خطأ `digits == 2` للذهب.
   - إضافة وقف خسارة طوارئ على خادم MT5 (`emergency_hard_sl_enabled`, `emergency_hard_sl_atr_mult`) عند تعطيل `use_dynamic_sl`.
   - تصحيح تقريب `calc_trailing_sl()` حسب خانات الرمز، وربط `check_spread(spread, symbol)` بـ `symbol_spread_limits`.
3. **`backend/config.py`**
   - إضافة `emergency_hard_sl_enabled: True` و`emergency_hard_sl_atr_mult: 5.0`.
4. **`backend/core/safe_execution_gateway.py`**
   - تطبيق `CalibratedKellySizer` **قبل** سقف مخاطرة `1.5% Equity` حتى لا يتجاوز الحجم السقف المسموح.
   - ربط `_check_slippage()` بـ `STRATEGY["symbol_spread_limits"]` الموحّد.
   - استخدام `MT5Connector.get_pip_size(symbol)` وإزالة عامل `* 10` الخاطئ في `_trace_position_loop()`.
5. **`backend/agents/execution_agent.py`**
   - استخدام `MT5Connector.get_pip_size(symbol)` في حساب مسافة الشبكة الذكية.
   - استخدام `symbol_spread_limits` في فحص تمدد السبريد اللحظي (`Flash Spread Protection`).
6. **`backend/agents/monitor_agent.py`**
   - استخدام `MT5Connector.get_pip_size(symbol)` في `_manage_position()`.
7. **`backend/agents/learning_agent.py`**
   - استخدام `MT5Connector.get_pip_size(symbol)` في `_on_trade_closed_event()`.
8. **`backend/agents/market_analyst.py`**
   - إصلاح تسرب حظر الأخبار في `_on_news_alert()` عبر تخزين مجموعة `affected` الكاملة وإزالتها جميعاً بعد 30 دقيقة.
9. **`backend/core/execution_bridge.py`**
   - حساب `atr_baseline` ديناميكياً من متوسط المدى الحقيقي للرمز بدلاً من القيمة الثابتة `0.0015`.
10. **`agents/beta_orderflow_agent.py`**
    - تصحيح إشارة `tp2` في صفقة البيع `BSL_SWEEP_REVERSAL` إلى الطرح `entry_price - (3.2 * risk_dist)`.
11. **`backend/models/database.py`**
    - إضافة `from loguru import logger` لمنع `NameError` داخل `create_tables()`.
12. **`backend/backtest_walkforward.py`**
    - نقل `import math` إلى أعلى الملف، وتصحيح `connector.get_rates()` إلى `connector.get_ohlcv()`، وإزالة ضرب السبريد في `0.1`.
13. **`tests/test_phase0_safety.py`**
    - تحديث توقّع `get_pip_value("XAUUSD")` إلى `10.0` (متطابق مع عقد 100 أونصة وحجم بيب `0.1`).
14. **`tests/test_p0_critical_fixes.py`** *(ملف اختبار جديد)*
    - 10 اختبارات تحقق مباشرة تغطي جميع إصلاحات P0 أعلاه.
