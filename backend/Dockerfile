# ============================================================
# Dockerfile — تهيئة الباكيند للعمل على السيرفر
# ============================================================
FROM python:3.10-slim

# ضبط متغيرات البيئة لمنع بايثون من كتابة ملفات pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# تثبيت الحزم الأساسية للنظام ومترجم C للـ scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لتسريع عملية البناء (Caching)
COPY requirements.txt .

# حذف مكتبة MetaTrader5 من ملف المتطلبات لأنها تدعم ويندوز فقط
# وسيتم الانتقال تلقائياً لوضع المحاكاة (Simulation Mode) على سيرفرات Linux
RUN sed -i '/MetaTrader5/d' requirements.txt

# تثبيت المكتبات
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# فتح المنفذ الخاص بالـ API والواجهة
EXPOSE 8000

# تشغيل الخادم الرئيسي
CMD ["python", "main.py"]
