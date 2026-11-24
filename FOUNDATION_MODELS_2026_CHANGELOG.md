# سجل حزمة دمج نماذج الأساس 2026 (TimesFM 2.5 + FinBERT + Gemma)

تاريخ التجهيز: 2026-11-23  
متوافقة بالكامل مع جميع الحزم السابقة (**P3 + P4 `council/` + P5 + فلتر السلة + ترقيات الدخول 2026 v2 + الدفعات 1–3**).

## الملفات المُحدّثة والمُضافة (7 ملفات + هذا السجل)
1. **`ml_models/timesfm_extractor.py`**: إضافة حارس الترخيص الإنتاجي `validate_timesfm_repo_license()` (يفرض أوزان **TimesFM 2.5 Apache-2.0** ويمنع الاستضافة الذاتية الإنتاجية لـ TimesFM 3.0 غير التجاري)، وإضافة **`CachedTimesFMService`** بكاش TTL (300 ثانية) وتحميل كسول وتدهور آمن.
2. **`backend/core/news_sentiment_engine.py`** *(جديد)*: محرك مشاعر الأخبار الهجين **`HybridNewsSentimentEngine`** (المسار السريع: `ProsusAI/finbert`، المسار العميق لأخبار `HIGH`: `Gemma 3/4` عبر Ollama، ومسار احتياطي حتمي عند العمل دون إنترنت، مع عكس الإشارة تلقائياً لعملة التسعير Quote Currency).
3. **`backend/agents/news_agent.py`**: دمج `HybridNewsSentimentEngine` ونشر `sentiment_scores` المستمرة `[-1..+1]` و`central_bank_tones` عبر `SignalBus` مع الحفاظ التام على `sentiment`.
4. **`backend/agents/market_analyst.py`** *(تراكمي فوق الدفعتين 1 و2)*: دمج `CachedTimesFMService` ودرجات المشاعر المستمرة من `NewsAgent`، وتشديد عتبة الثقة (`+5%`) تلقائياً عند ارتفاع تباين عدم يقين TimesFM.
5. **`backend/agents/learning_agent.py`** *(تراكمي فوق الدفعة 1)*: إضافة متجه v2 ذي الـ 12 ميزة (`build_v2_feature_vector`) وبوابة الترقية خارج العينة (`should_promote_v2_model`) مع الحفاظ الكامل على عقد الـ 8 ميزات لـ `META_GATE`.
6. **`backend/config.py`** *(تراكمي فوق جميع الحزم)*: إضافة كتلة `FOUNDATION_MODELS_2026`.
7. **`tests/test_foundation_models_integration.py`** *(جديد)*: 6 اختبارات سلوكية تغطي حارس الترخيص، كاش TimesFM، محرك FinBERT+Gemma، عكس عملة التسعير، متجه v2 وبوابة الترقية، وتشديد الثقة في `MarketAnalystAgent`.

## غير موصول بعد (NOT WIRED — ملاحظات مراجعة 2026)
البنود التالية مُعرّفة ومختبرة كوحدات فقط وليست موصولة في مسار التدريب أو التقديم الحي حتى الآن:
- **متجه الـ 12 ميزة (`LearningAgent.build_v2_feature_vector`) ومفتاح `FOUNDATION_MODELS_2026["v2_feature_count"]`**: محجوزان لموديل v2 مستقبلي؛ لا يوجد مسار تدريب أو تقديم لنموذج الـ 12 ميزة بعد (النظام لا يزال يعمل بنموذج الـ 8 ميزات فقط).
- **بوابة ترقية v2 (`LearningAgent.should_promote_v2_model`)**: غير مُستدعاة خارج الاختبارات ولا تدير أي ترقية حية حالياً.
- **مدخلات `news_sentiment_score` وميزات `TimesFM` داخل نموذج التعلم**: غير موصولة كمدخلات لنموذج ML/Meta-Labeling بعد.
- **السلوك الفعلي الحالي**:
  - **TimesFM**: يقتصر أثره الحي حالياً على رفع الحد الأدنى لعتبة الثقة بمقدار `+5%` عند ارتفاع تباين التوقعات (`forecast_variance_risk`).
  - **FinBERT**: يحتاج تثبيت حزمة `transformers` (`transformers>=4.40.0` في `backend/requirements.txt`)؛ وعند غيابها يتراجع تلقائياً مع تحذير `WARNING` إلى المعجم الحتمي الاحتياطي (Lexicon Fallback).
