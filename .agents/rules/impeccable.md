# Impeccable — Frontend Design Vocabulary & 62-Rule Deterministic Slop Detector

هذه القاعدة تدمج نظام ومراجع التصميم العالمي (`impeccable` من تطوير Paul Bakaus) داخل مشروع `Forex Trading System` ووكلاء Antigravity.

---

## 1. قاموس أوامر توجيه التصميم (24 Commands)

بدلاً من البرومبتات الغامضة («اجعل التصميم جميلاً»)، يتم توجيه الوكيل بأوامر دقيقة مقسمة إلى 5 فئات:

### أ) التوجيه والتحسين (Steer & Enhance)
- `/impeccable bolder`: تضخيم التصاميم الباهتة أو المحايدة بشكل زائد وإعطاؤها حضوراً بصرياً قوياً.
- `/impeccable quieter`: تهدئة التصاميم المزدحمة أو المشتتة لتقليل الإجهاد البصري.
- `/impeccable distill`: تجريد الواجهة من الزوائد والعناصر غير الضرورية والتركيز على الجوهر.
- `/impeccable colorize`: إدخال لوحة ألوان استراتيجية وواعية للواجهات الرمادية والمونوكروم.
- `/impeccable typeset`: ضبط تسلسل الخطوط (Typography Hierarchy) والأحجام والأوزان.
- `/impeccable layout`: تصحيح المسافات والإيقاع وتوزيع الكتل البصرية.
- `/impeccable animate`: إضافة حركات وتفاعلات مدروسة ومريحة للمستخدم.
- `/impeccable delight`: لمسات شخصية واحترافية تجعل التجربة لا تُنسى.
- `/impeccable overdrive`: مؤثرات بصرية متقدمة (Shaders, Scroll-driven effects).

### ب) المراجعة والتقييم (Review & Evaluate)
- `/impeccable critique`: مراجعة تجربة مستخدم (UX) دقيقة وتقييمها مقابل قواعد الهيورستك المعتمدة وترتيب الأولويات من P0 إلى P3.
- `/impeccable audit`: فحص جودة تقني شامل يغطي سهولة الوصول (Accessibility WCAG)، وسرعة الأداء (Performance)، والتجاوب (Responsive).

### ج) الإنهاء والتحصين (Finish & Harden)
- `/impeccable polish`: اللمسات النهائية الشاملة قبل اعتماد الكود وتسليمه.
- `/impeccable harden`: معالجة الحالات الحدية (Edge Cases)، نصوص الأخطاء، دعم اللغات المتعددة، وتدفق المحتوى الفائض (Overflow).
- `/impeccable clarify`: تحسين وإعادة صياغة نصوص الواجهة وتسميات الأزرار لتكون واضحة لا لبس فيها.
- `/impeccable adapt`: مواءمة الشاشات والأجهزة وأحجام العرض المختلفة.
- `/impeccable optimize`: تحسين أداء التحميل وزمن المعالجة (Rendering Performance).
- `/impeccable onboard`: تصميم تدفقات البداية وحالات الشاشات الفارغة (Empty States).

### د) التخطيط والتوثيق (Plan & Set up)
- `/impeccable shape`: تخطيط تجربة المستخدم قبل كتابة أي سطر كود.
- `/impeccable init`: استخلاص سياق المنتج وأهدافه وتوثيقها في `PRODUCT.md`.
- `/impeccable document`: استخراج نظام التصميم الحالي وتوثيقه في `DESIGN.md`.
- `/impeccable extract`: تحويل الأنماط المتكررة إلى مكونات ورموز تصميمية (Design Tokens).

### هـ) التجربة الحية (Iterate Live)
- `/impeccable live`: فتح خادم التطوير مع طبقة تحكم لاختيار أي عنصر وتجربة بدائل حية فورية.
- `/impeccable generate`: توليد بدائل تصميمية لعنصر محدد تلقائياً.

---

## 2. كاشف العشوائية الحتمي (62-Rule Deterministic Slop Detector)

يعمل كاشف العشوائية الحتمي كـ **Hook حتمي** يفحص تلقائياً أي ملف واجهة يتم تعديله أو إنشاؤه بدون استهلاك API أو توكنز:
1. **رفض كليشيهات الـ AI الشائعة (AI Slop):**
   - التدرجات البنفسجية والزرقاء المستهلكة (`ai-color-palette`: `from-purple-500 to-blue-500`).
   - الإفراط في خطوط مثل Inter و Roboto و Space Grotesk دون تميز (`overused-font`).
   - الحواف الجانبية الملونة السميكة في البطاقات (`side-tab`: `border-r-4`, `border-l-4`).
   - البطاقات المتداخلة داخل بعضها (`nested-cards`).
   - النصوص المتدرجة المشتتة على العناوين والأرقام (`gradient-text`).
   - المسافات الرتيبة المتطابقة في كل مكان (`monotonous-spacing`).
2. **فحص معايير الجودة وسهولة الاستخدام:**
   - النصوص الصغيرة جداً غير المقروءة (`tiny-text` < 12px, `undersized-ui-text` < 11px).
   - تباين الألوان غير الكافي (Low contrast).
   - تجاوز المحتوى لحدود الحاوية (`text-overflow`).
   - العناوين المتزاحمة والخطوط المسطحة غير المتسلسلة.

---

## 3. وكلاء Impeccable المتخصصون

- `impeccable-asset-producer`: إنتاج الأصول والرسومات والرموز المتسقة.
- `impeccable-documenter`: تحديث وحفظ `DESIGN.md` و`PRODUCT.md`.
- `impeccable-finish-reviewer`: المراجعة والتقييم النهائي الشامل قبل الدمج.
- `impeccable-manual-edit-applier`: تطبيق تعديلات المتصفح الحية بأمان في الكود المصدري.

---

## 4. التكامل مع ثوابت التداول ومجلس الوكلاء (`AGENTS.md`)

- يُطبق هذا النظام على واجهات المستخدم (React / Next.js / Tailwind / CSS) فقط.
- تظل نماذج التداول والخوارزميات الخلفية (`backend/`) خاضعة لثوابت `AGENTS.md` الصارمة (عدم تلفيق الأرقام، وضع الظل، واجتياز اختبارات الانحدار الـ 16).
