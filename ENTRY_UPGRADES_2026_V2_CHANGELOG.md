# سجل ترقيات إشارة الدخول (2026 Entry Signal Upgrades v2 — متوافق مع P3/P4/P5)

تاريخ التجهيز: 2026-11-22  
متوافقة بالكامل مع حزم **P3 + P4 (`council/`) + P5 + فلتر `MAGIC_NUMBERS` للسلة** (بدون إعادة إنشاء مجلد `agents/` الجذري).

## ملخص الترقيات المُطوَّرة (6 ملفات أساسية + ملف اختبارات)

### الترقية الأولى المُطوَّرة: فك ارتباط التصويت وحارس التعارض + مايكروستركشر تدفق الأوامر
1. **`backend/core/voting_engine.py`**
   - **سقوف محاور متكيفة مع نظام FSM (`regime_pillar_caps`)**: إعادة توزيع سقوف المحاور الأربعة (`trend`, `momentum`, `strength`, `structure`) حسب حالة السوق مع إبقاء المجموع ثابتاً عند `7.5` للمحافظة على معايرة `min_vote_score`.
   - **مقاومة الانحياز الجماعي وحارس التعارض (`Anti-Groupthink & Conflict Guard`)**: حساب إنتروبيا شانون المطبّعة `pillar_entropy` وعدد المحاور المعاكسة `opposing_pillars`، مع خصم الثقة تلقائياً ومنع `signal_strong=True` عند وجود تعارض بين المحاور ما لم تتحقق هيمنة ساحقة (`min_score * 1.55`).
2. **`council/beta_orderflow_agent.py`** *(تحت `council/` وفق P4)*
   - **فلترة إزاحة فجوة القيمة العادلة (`FVG`) مقابل `ATR`**: اشتراط حد أدنى للإزاحة (`0.15 * ATR`) مع تتبع عمر الفجوة (`age_bars`) لاستبعاد فجوات الضوضاء الصغيرة أو المتقادمة.
   - **حارس تدفق الأوامر المستمر (`Continuous OFI Guard`)**: تعديل تدريجي للثقة بناءً على `ofi_z_score` مع عقوبة صريحة ووسم `ofi_counter_flow` عند التدفق المؤسسي المعاكس الشديد (`|ofi_z| > 1.8`).

### الترقية الثانية المُطوَّرة: ذاكرة فخاخ متضائلة زمنياً وتقابلية + قاطع الدائرة المزدوج
3. **`memory_rag/adaptive_trade_journal.py`**
   - **تضائل زمني أسي (`FinMem Time-Decay`, نصف عمر 14 يوماً)** مع ترجيح شدة النتيجة (`pnl_pips`) في `fetch_losing_vectors_with_weights()` و`fetch_winning_vectors_with_weights()`.
   - **نسبة فوز خاصة بكل نظام سوق (`recent_win_rate(regime_state=...)`)** لدعم العتبات التكيفية.
4. **`council/gamma_redteam_critic.py`** *(تحت `council/` وفق P4)*
   - **تشابه `Top-K` المرجح بالتضائل الزمني (`k=3`)** بعد تطبيع Z-Score عمودياً لمنع هيمنة صفقة قديمة شاذة واحدة.
   - **الاسترجاع التقابلي (`Contrastive Win Relief`)**: مقارنة الإعداد بالصفقات الرابحة الحديثة في نفس النظام لتخفيف عقوبة الفخ ضمن حدود مضبوطة (`<= 0.12`) ومنع الرفض الزائف للإعدادات الجيدة.
   - **قاطع الدائرة المزدوج للذاكرة (`Dual Memory Circuit Breaker`)**: تعليق الاسترجاع التاريخي تلقائياً عند صدمة التقلب (`HIGH_VOL_SHOCK` أو `atr_ratio >= 2.0`) **أو** انهيار ثقة تصنيف النظام (`regime_confidence < 0.45`).

### طبقة التنسيق والمعايرة الاحتمالية (2026 Coordination & Calibration)
5. **`council/omega_risk_governor.py`** *(تحت `council/` وفق P4)*
   - **دمج الاحتمال المعايَر (`Calibrated Probability Fusion`)**: عند توفر `calibrated_p_win` من `Meta-Model`، يُدمج مع الدرجة الهيكلية (`0.45 * structural + 0.55 * calibrated`) لمنع القواعد التقديرية المفرطة الثقة من تجاوز المعايرة الإحصائية.
   - **عتبات تكيفية حسب أداء النظام وتعدد ملاحظات النقد**: تشديد عتبة القبول تلقائياً عند انخفاض `regime_win_rate < 0.42` أو وجود ملاحظتَين فأكثر من `GammaRedTeamCritic`.
6. **`backend/config.py`**
   - يحفظ جميع إعدادات P5 + `basket_filter_by_magic: True` ويضيف كتلة `ENTRY_UPGRADES_2026` المركزية لضبط جميع المعاملات.

## التثبيت والتحقق
فكّ ضغط الحزمة في جذر المشروع (بعد P4 وP5) مع السماح بالاستبدال، ثم شغّل:
```bash
PYTHONPATH=. python -m unittest tests/test_entry_signal_upgrades_2026.py tests/test_no_package_name_collision.py tests/test_p5_monitor_agent.py tests/test_basket_magic_filter.py -v
```
