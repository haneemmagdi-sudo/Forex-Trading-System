@echo off
chcp 65001 > nul
title Quantum Forex AI — MT5 Agent Setup
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Quantum Forex AI — MT5 Agent Setup    ║
echo  ║   إعداد وكيل التداول الذكي              ║
echo  ╚══════════════════════════════════════════╝
echo.

set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python
    ) else (
        echo [!] Python غير مثبت. جاري تحميله...
        echo     يرجى تحميل Python 3.11 من: https://python.org
        pause
        exit /b 1
    )
)

echo [1] Python موجود ✓ (%PYTHON%)
echo.
echo [2] تثبيت المكتبات المطلوبة...
"%PYTHON%" -m pip install -r requirements.txt --quiet

echo.
echo [3] التحقق من ملف الإعدادات...
if not exist ".env" (
    echo  ╔══════════════════════════════════════════╗
    echo  ║  تحذير: ملف .env غير موجود!             ║
    echo  ║  يرجى إنشاؤه يدوياً مع القيم التالية:   ║
    echo  ║  AGENT_TOKEN=توكن_من_صفحة_ربط_MT5       ║
    echo  ║  CLOUD_URL=https://your-app.vercel.app   ║
    echo  ║  MT5_LOGIN=رقم_الحساب                    ║
    echo  ║  MT5_PASSWORD=كلمة_المرور                ║
    echo  ║  MT5_SERVER=اسم_السيرفر                  ║
    echo  ╚══════════════════════════════════════════╝
    pause
    exit /b 1
) else (
    echo     ملف .env موجود ✓
    echo     تأكد من تعديل القيم بداخله قبل التشغيل
)

echo.
echo [✓] الإعداد اكتمل!
echo.
echo     لتشغيل الـ Agent: انقر مزدوجاً على start_agent.bat
echo.
pause
