# سجل الدفعة الأولى: ترقية التعلم الآلي وحوكمة Champion/Challenger مع التراجع التلقائي (2026)

تاريخ التجهيز: 2026-11-22  
متوافقة بالكامل مع حزم **P3 + P4 (`council/`) + P5 + فلتر السلة + ترقيات الدخول 2026 v2**.

## الملفات المُحدّثة والمُضافة (5 ملفات + هذا السجل)

1. **`backend/core/champion_challenger.py`** *(ملف جديد)*
   - **`ExponentialAttributionBandit`**: يحسب تعديلات مضاعِفات أوزان التصويت بتقليص بايزي (`Empirical Bayes Shrinkage`) نحو `1.0` لمنع الإفراط في التخصيص عند قلة الصفقات.
   - **`ChampionChallengerManager`**: يقيّد كل تعديل بحد أقصى للخطوة (`±0.25`)، ويختبر أوزان `Challenger` خلال نافذة اختبار حية (`10` صفقات مغلقة)، ثم إما يُرقّيها إلى `Champion` جديد أو يُنفّذ **تراجعاً تلقائياً (`Auto-Rollback`)** فورياً عند `4` خسائر متتالية أو تدهور نسبة الفوز/التوقع مع فترة تهدئة (`5` صفقات) وحفظ ذري للحالة في `backend/models/champion_weights_state.json`.
2. **`backend/agents/learning_agent.py`** *(مبني على P3)*
   - استبدال `cross_val_score` العشوائي بـ **`Purged Walk-Forward Time-Series CV`** مع فجوة حظر زمني (`Embargo`) وترتيب زمني تصاعدي للإشارات لمنع أي تسرّب مستقبلي.
   - استبدال السعر الخام `ema_value` بـ **المسافة المطبّعة عن EMA بوحدات ATR** `(price - ema) / atr` وتطبيع `MACD/ATR` للحفاظ على ثبات المقياس عبر كل الأزواج (EURUSD / USDJPY / XAUUSD) مع إبقاء عقد الـ 8 ميزات متوافقاً مع `MetaLabelingClassifier` و`META_GATE`.
   - ربط `ChampionChallengerManager` في `run_cycle()` و`_on_trade_closed_event()` لاستعادة أوزان الـ Champion في `VotingEngine` تلقائياً وبث حدث `champion_rollback` على `SignalBus`.
3. **`backend/agents/market_analyst.py`** *(مبني على P3)*
   - إغلاق حلقة تعديل السلوك المقطوعة: تطبيق `self._regime_confidence_boost` الوارد من `LearningAgent` فعلياً على عتبة الثقة (`min_signal_confidence + boost`) قبل إرسال الإشارة، مع تسجيل السبب `ADAPTIVE_CONFIDENCE_FILTER` في قاعدة البيانات، والاشتراك في حدث `champion_rollback`.
4. **`backend/config.py`** *(يحتفظ بجميع إعدادات P5 + `basket_filter_by_magic` + `ENTRY_UPGRADES_2026`)*
   - إضافة كتلة `LEARNING_UPGRADES_2026` المركزية لضبط نافذة الاختبار والتراجع التلقائي وعتبة الثقة.
5. **`tests/test_learning_champion_rollback.py`** *(ملف اختبار جديد)*
   - 7 اختبارات سلوكية تغطي التقليص البايزي، تقييد الخطوة، الترقية، التراجع التلقائي المبكر والمتأخر، فترة التهدئة، الحفظ الذري، ثبات مقياس الميزات عبر الأزواج، وتطبيق تشديد الثقة في `MarketAnalystAgent`.

## التثبيت والتحقق
فكّ ضغط الحزمة في جذر المشروع مع السماح بالاستبدال، ثم شغّل:
```bash
PYTHONPATH=. python -m unittest tests/test_learning_champion_rollback.py tests/test_entry_signal_upgrades_2026.py tests/test_p5_monitor_agent.py tests/test_basket_magic_filter.py tests/test_no_package_name_collision.py -v
```
