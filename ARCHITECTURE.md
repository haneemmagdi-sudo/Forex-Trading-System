# ARCHITECTURE — خريطة نظام تداول الفوركس

> اقرأ هذا الملف أولاً. كل ما هنا متحقَّق منه مقابل الكود، لا مقابل التوثيق التسويقي.
> آخر تحديث: أكتوبر 2026 — بعد إعادة هيكلة شجرة `agents/` الجذرية إلى `institutional/`.

## 1) ما هو النظام في سطر واحد

محرك تداول فوركس على MetaTrader 5 (Python + FastAPI) يتخذ قراره من **تصويت مرجّح
لتسعة مؤشرات + نظام سوقي (FSM)**، ويُخضع كل إشارة لطبقات مخاطر، **ويعمل إلى جانبه
مجلس وكلاء في وضع الظل** يقيس جودة القرار بلا أي تأثير على التنفيذ.

- الحساب: `ICMarketsSC-Demo` ⇒ أوامر على **ديمو** مع `LIVE_TRADING_ENABLED=false`. فتح صفقة على حساب غير تجريبي يتطلب `true`.
- الواجهة: Vite dashboard على `:5173`، والـ API على `:8000`.
- جهة التنفيذ الوحيدة: `MetaTrader5.order_send` عبر `backend/core/safe_execution_gateway.py`.

## 2) البنية (من أين تبدأ)

| المسار | الدور | حيّ؟ |
|---|---|---|
| `backend/main.py` | نقطة الدخول: FastAPI + دورة حياة الوكلاء الخمسة + كل نقاط النهاية | ✅ المحرك |
| `backend/agents/` | الوكلاء الخمسة الحيّون: `market_analyst` · `execution_agent` · `monitor_agent` · `learning_agent` · `news_agent` + `analyst_cycle_agent` | ✅ |
| `backend/core/` | التنفيذ والمخاطر والمؤشرات: `safe_execution_gateway` · `voting_engine` · `fsm_engine` · `indicators` · `risk_manager` · `mt5_connector` · `signal_bus` · `news_fetcher` · `agent_council` · `execution_bridge` | ✅ |
| `backend/models/` | SQLAlchemy: قاعدة البيانات + `ml_model.pkl` المُدرَّب | ✅ |
| `institutional/` | **الطبقة المؤسسية** (لا تُنفّذ صفقات): اللوحة · الإجماع · المناظرة · النظام السوقي · التدفق · فريق المحللين · راوتر LLM · وكيل ترميم الأكواد | ✅ مستهلَكة |
| `data/` | واجهة بيانات رقيقة للتحليل: أسعار Yahoo + تقويم اقتصادي + عناوين أخبار (تُفوّض `NewsFetcher`) | ✅ |
| `schemas/` | عقود pydantic: `StrategyProposal` · `RiskVerdict` · `CEODecision` · `ExecutionReceipt` · حسابات الفوركس | ✅ |
| `config/` | `settings.py` (بيئة data-layer). **قيم النظام في `backend/config.py`** — راجع الفخ رقم 1 | ✅ |
| `data_layer/` | تكامل OpenBB (أسهم/ماكرو) | جزئي |
| `ml_models/` | خطوط الميزات وTimesFM/DQN/RF (المُدرَّب فعلاً: GBM في `backend/models/ml_model.pkl`) | جزئي |
| `tests/` | 3 ملفات / 16 اختباراً — تعمل بـ `PYTHONPATH=.` | ✅ |
| `platform/` | تطبيق Next.js **منفصل وغير مستخدم** (لا مشغّل يبدأه) | ⚠️ غير مربوط |
| `src/` `public/` `vite.config.ts` | واجهة Vite الحيّة (يبدأها المشغّل على 5173) | ✅ |
| `*.mq5` `*.pine` `MQL5_*.mqh` | إكسبيرتات MT5 واستراتيجية TradingView وجسر ONNX | ⚠️ معزولة عن بايثون |
| `_archive/` | ما أُزيل من الشجرة (غير متتبَّع في git) | 📦 |

## 3) مسار القرار الحيّ (المحرك)

```
MT5 tick
  └─ MarketAnalyst (كل 5 ثوان لكل زوج)
       ├─ TechnicalIndicators.calculate()  → 9 أعضاء تصويت
       ├─ FSMEngine.detect()               → نظام سوقي + اتجاهات مسموحة
       ├─ VotingEngine.vote()              → اتجاه + ثقة (0-100)   [الأوزان معدَّلة تعلّمياً]
       ├─ فلاتر حيّة: تأكيد H4 · سبريد · حظر أخبار (NewsAgent)
       ├─ _save_signal_to_db()             → signals
       └─ _run_shadow_council()            → حكم المجلس (ظل) → shadow_decisions
              └─ SignalBus.emit_signal()
                   └─ ExecutionAgent._process_signal()
                        ├─ حماية Cascade/DD/عدد الصفقات/الشبكة
                        └─ SafeExecutionGateway.execute_signal()
                             ├─ DD  →  مخاطر  →  تخصيص اللوت
                             └─ MT5 order_send()  → trades
```

**المخارج:** هدف سلة (`base_target_usd`) أو إيقاف طارئ عند تراجع 5% — راجع الفخ رقم 4.

## 4) حلقات التعلّم والقياس

| الحلقة | المحرّك | المخرَج |
|---|---|---|
| أوزان التصويت | `LearningAgent` كل 60 دقيقة من الصفقات المغلقة | `VotingEngine.learned_multipliers` (تعديل حيّ) |
| نموذج جودة الإشارة | GradientBoosting على 8 ميزات | `backend/models/ml_model.pkl` + `learning_logs` |
| ذاكرة التأمّل | درس حتمي لكل صفقة مغلقة | `agent_reflections` |
| مجلس الظل | لوحة + إجماع + HMM + تدفق + مناظرة على كل إشارة | `shadow_decisions` |
| فريق المحللين | دورة كل 60 دقيقة في خيط منفصل | `analyst_cycles` |

**الوعود مقابل الواقع:** نموذج GBM دقته ~54-56% وهو **خارج مسار القرار** (مكشوف على
`/api/ml/predict` فقط، ويُستخدم كمُنتِج في مجلس الظل وإلا فلا أثر له).

**نقاط القياس:** `/api/council/report` (هل الفيتو يضيف قيمة؟) · `/api/analyst/report` ·
`/api/institutional/status` (حالة حقيقية بلا ادعاءات).

## 5) الجداول (SQLite: `backend/trading.db`)

`signals` · `trades` · `learning_logs` · `shadow_decisions` · `agent_reflections` ·
`analyst_cycles` · `performance` (فارغ) · `agent_logs` (فارغ)

WAL + `busy_timeout` مُفعَّلان عبر `@event.listens_for(engine, "connect")` في
`backend/models/database.py` لمنع أخطاء `database is locked` تحت التزامن.

## 6) الحزم: مصدر واحد لكل شيء

- **`backend/config.py` = المصدر الوحيد لقيم النظام** (بما فيها ثوابت فريق المحللين).
  حزمة `config/` الجذرية تستورده نجماً وتضيف `settings` فقط.
- **`institutional/` و`backend/` لا تتعارضان**: أُزيلت حزمة `agents` الجذرية وحزمة
  `core` الجذرية، ولم يعد هناك أي التفاف على `sys.path`
  (`backend/agents/__init__.py` أُفرِغ من الحيلة القديمة).
- **`council/`** (الجذر) = مجلس الوكلاء الخماسي (alpha · beta · gamma · delta · omega). كان اسمه `agents/` وتعارض
  مع `backend/agents/` فأُعيدت تسميته (P4). يحرس عدمَ عودة أي تعارض أسماء `tests/test_no_package_name_collision.py`.
- **`institutional/base_agent.py`** هو قاعدة فريق المحللين (تتطلب راوتر LLM)،
  و**`backend/agents/base_agent.py`** هو قاعدة المحرك الحي (دورة تشغيل asyncio).
  لا تخلط بينهما.

## 7) التشغيل والتحقق

```bat
Start_System.bat            :: يشغّل الـ backend + الواجهة (ويثبّت من backend\requirements.txt)
Run_Quantum_Trading.bat     :: نفس الشيء مع فحص أوزان TimesFM
backend\start_backend.bat   :: الـ backend فقط + بوابة تحقق من حزم المفسّر
```

```bash
# الانحدار (16 اختباراً) — يجب أن يكون PYTHONPATH هو جذر المشروع
PYTHONPATH=. python tests/test_system_integrity.py
PYTHONPATH=. python tests/test_institutional_mas.py
PYTHONPATH=. python tests/test_code_healing_agent.py

# أدوات القياس (تعمل من داخل backend/ وتقرأ قاعدة البيانات الحقيقية)
python backend/council_backfill.py --limit 400 --show-reasons 8   # أثر الجسر بأثر رجعي
python backend/order_flow_calibration.py --limit 500              # معايرة طبقة التدفق
python backend/cascade_calibration.py --limit 500                 # معايرة السلسلة كاملة
```

## 8) الفخاخ المعروفة (مهمة لأي وكيل)

1. **`config` اسم لحزمتين**: في سياق التشغيل (`cwd=backend`) تُحلّ `config` إلى
   `backend/config.py`، ومن الجذر إلى حزمة `config/`. القيم كلها في `backend/config.py`
   كمصدر وحيد — لا تُكرّر ثابتاً في الاثنين.
2. **الجلسات الزمنية بـ UTC**: `get_active_forex_session()` في `schemas/forex.py`
   (لندن 7-16، نيويورك 13-22، طوكيو 0-9، سيدني 21-6).
3. **الفيتوات الصلبة معطّلة افتراضياً عن قصد** (`veto_enabled=False`) في:
   `order_flow_agent` · `multi_agent_debate` · `market_regime_hmm`. السبب **مقيس**:
   كانت ترفض 94-96% من الصفقات وتُزيل 94% من الربح، والمجموعة التي كانت تُجيزها
   أداؤها **أسوأ** من التي ترفضها. لا تُفعّلها إلا بدليل جديد من أدوات القياس.
4. **لا SL/TP لكل صفقة**: `use_dynamic_sl=False` في `backend/config.py` يرسل
   `sl=0, tp=0` ويوقف أيضاً Break-even/Partial/Trailing (لأن `monitor_agent`
   يخرج مبكراً عند هذا الإعداد). الحماية الوحيدة: هدف السلة + إيقاف 5% طارئ.
5. **لا مزوّد LLM عامل حالياً** (Ollama متوقف والسحابة تفشل) ⇒ `LLMRouter` يرفع
   `AllProvidersExhaustedError` صراحةً، والمخطط يُرجع `None` (لا مقترح). هذا سلوك
   صحيح لا انعطال. **لا تُعِد المحاولة بقيم مُلفَّقة** — هذا كان عطلاً أُصلح.
6. **الفيتو الحقيقي مقفول ببوابة إثبات**: `COUNCIL["mode"]` + عتبات في
   `backend/config.py`. حتى مع `enforce` لا يبدأ الفلترة قبل تحقّق شروط الدليل.
7. **`.env` غير متتبَّع** ولا يجوز إدخاله في git. المفاتيح الحيّة كانت مكشوفة سابقاً
   في `.env.example` — دوّرها إن لم تكن قد فعلت.
8. **البيئة**: مفسّر التشغيل هو
   `%LOCALAPPDATA%\Programs\Python\Python311\python.exe`. أول `python` في PATH قد
   يكون مفسّراً آخر بلا `MetaTrader5`. لا تشغّل النظام بمفسّر عاري.

## 9) بنود مؤجَّلة (معروفة ومقصودة)

| البند | السبب |
|---|---|
| `backend/core/live_pipeline.py` + `quote_cache.py` | مسار Hyperliquid خامل، لكن `safe_execution_gateway` يستورده ⇒ يحتاج تعديلاً في مسار التنفيذ الحي |
| `platform/` (Next.js) | تطبيق منفصل غير مربوط؛ أُزيلت منه `node_modules`/`.next` فقط (530MB). قراره لك |
| الواجهة في الجذر | نقلها إلى `frontend/` يفرض تعديل المشغّلات و`vite.config` — لم يُنفَّذ حفاظاً على واجهة عاملة |
| `schema` لحزمة `config` | مصدر واحد مُوثَّق، لكن الاسم ما زال مزدوجاً |
| معايرة أوزان المخاطرة | التصنيف السوقي يحمل معلومة حقيقية (فرق 17-21 نقطة فوز) — الأفضل استخدامه **كوزن مخاطرة** لا كفيتو |
