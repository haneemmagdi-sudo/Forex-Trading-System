# Replay backtest — إعادة تشغيل منطق النظام الحقيقي على بيانات MT5

يعيد تشغيل **نفس الكود الحي** على تاريخ MT5 (H1) ليقيس نسبة الربح والـ payoff والتوقّع الحقيقي للدخول مع سلة ATR 1:1 لكل رمز، قبل أي استخدام حي.
لا يرسل أي أمر تداول: `export` يقرأ التاريخ فقط، و`run` يعمل على ملفات CSV بلا MT5.

## ما يُعاد تشغيله فعلاً (كود النظام نفسه)
`TechnicalIndicators` → `FSMEngine` → `VotingEngine` → بوابة `signal_strong & trade_allowed` → تأكيد H4 → حد السبريد لكل رمز
→ قواعد `ExecutionAgent` (cascade، DD، `max_open_trades`، مسافة الشبكة، flash spread) → `RiskManager.calc_trade_params`
→ **`MonitorAgent.run_cycle` الحقيقي** (سلة لكل رمز بوقف ATR وهدف 1:1، break-even، trailing، حماية DD) فوق وسيط محاكى `SimBroker`.
لحظة بلوغ هدف/وقف السلة تُحدَّد بالتنصيف على حكم `_evaluate_symbol_basket` نفسه، فالتعبئة عند العتبة بالضبط.

## الاستخدام
```powershell
cd "F:\config\Forex Trading System"
pip install MetaTrader5 pandas numpy        # للتصدير فقط MetaTrader5
python backtest\replay_backtest.py export --days 365          # يتطلب محطة MT5 مفتوحة (حساب Demo)
python backtest\replay_backtest.py run --oos-fraction 0.3     # التقرير + backtest\out\report.json + trades.csv
python backtest\replay_backtest.py run --legacy-basket --out backtest\out_legacy   # السلة القديمة ($2/$20) للمقارنة
python backtest\replay_backtest.py run --set basket_rr=1.5 --set basket_sl_atr_mult=2.0 --out backtest\out_rr15
```
خيارات التجارب (للتحكم والفحص، لا للضبط): `--signal-mode random|invert` (نفس توقيت وATR ونظام الإشارات الحقيقية مع اتجاه عشوائي/معكوس) ·
`--seed N` · `--regimes STRONG_TREND` (السماح بالدخول في هذه الأنظمة فقط) · `--path-order adverse|favorable` (الأسوأ/الأفضل أولاً داخل الشمعة بالنسبة لاتجاه الصفقات المفتوحة) ·
`--set grid_distance_pips=100000` (إلغاء الشبكة).
إشارات الدخول تُحسب مرة واحدة لكل رمز وتُخزَّن في `backtest\out_cache` (دالة نقية للبيانات والإعدادات؛ تُبطَل تلقائياً إن تغيّرت البيانات أو معاملات المؤشرات/التصويت/السبريد أو شيفرة المؤشرات)، فالتشغيلات اللاحقة أسرع كثيراً.
خيارات مفيدة: `--symbols EURUSD,GBPUSD` · `--from 2026-01-01 --to 2026-06-30` · `--commission-per-lot 7` (دولار ذهاب وإياب) · `--balance 1000`.

## كيف تقرأ النتيجة
- **BASKETS** هي الوحدة الصحيحة (طبقات الشبكة لسلة واحدة تُحسب مرة).
- حقّق الربحية فقط إذا: `win_rate` أعلى من `breakeven_win` بهامش واضح **و**`expectancy > 0` **و**الحد الأدنى من فاصل الثقة 95% لنسبة الربح فوق نسبة التعادل، **و**عدد السلال ≥ 100 (يفضَّل مئات).
- قارن دائماً `--legacy-basket` مقابل الافتراضي، وقارن `in_sample` مقابل `out_of_sample`.
- لا يوجد أي ضبط/تحسين للمعاملات داخل الأداة، فالتقسيم الزمني يكشف عدم الثبات لا فرط الملاءمة؛ أي تجربة `--set` متعددة تعيد خطر الإفراط في الملاءمة، فاحتفظ بفترة OOS لم تُستعمل في الاختيار.

## حدود وتقريبات (موثّقة أيضاً داخل report.json)
1. التحليل على شموع **مغلقة** والدخول عند افتتاح التالية (الحي يحلّل الشمعة الحالية باستمرار).
2. مسار الشمعة O→L→H→C للصاعدة وO→H→L→C للهابطة (الترتيب الحقيقي مجهول) — يؤثر على أي شمعة تلمس الهدف والوقف معاً.
3. بلا slippage ولا requotes ولا swap؛ السبريد من عمود `spread_pips` لكل شمعة (آخر سبريد في الشمعة)، والعمولة ثابتة للوت.
4. غير مُعاد: حظر الأخبار، التأمّل، التشديد التكيفي، TimesFM، المجلس (ظل)، أوزان التعلم، بوابة SafeExecutionGateway الإضافية، الهامش/Stop-out.
5. التحوّط (DD ≥ 2.5%) يُحاكى لكنه يُطلق مرة لكل دورة مراقبة (~4 دورات/شمعة هنا مقابل آلاف الدورات حياً).
6. cascade يعدّ كل صفقة خاسرة على حدة.
7. أزواج التقاطع (EURJPY/GBPJPY/EURGBP) تُحوَّل قيمة بيبها بآخر سعر لزوج دولار محمَّل؛ صدّر USDJPY وGBPUSD معها.
8. نتيجة الأداة **تقدير** وليست ضماناً. الأرقام على بيانات Demo وبمعطيات وسيطك.

## الاختبارات
`PYTHONPATH=. python -m unittest tests.test_replay_backtest -v` (24 اختباراً ببيانات اصطناعية: رياضيات الوسيط، ترتيب مسار الشمعة، التعبئة عند ±25 بيب بالضبط، استقلال الرموز، القاعدة القديمة، قاعدة الشبكة، السبريد، المقاييس، وتشغيل كامل بالمؤشرات الحقيقية).
