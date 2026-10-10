@echo off
chcp 65001 > nul
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   🚀 Quantum AI Trading System — Backend Launcher   ║
echo ║   بيانات حقيقية + أخبار + تعلم آلي                 ║
echo ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" (
    echo.
    echo [ERROR] Python 3.11 not found at:
    echo         %LOCALAPPDATA%\Programs\Python\Python311\python.exe
    echo.
    echo         Install it from https://python.org then re-run this file.
    echo         Do NOT fall back to a bare "python": on this machine it can
    echo         resolve to a different interpreter that lacks MetaTrader5,
    echo         scikit-learn and torch.
    echo.
    pause
    exit /b 1
)

echo [1/4] التحقق من Python...
"%PYTHON%" --version
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python غير مثبت. ثبّت Python 3.10+ من https://python.org
    pause
    exit /b 1
)

echo.
echo [2/4] تثبيت المتعلّقات...
"%PYTHON%" -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ بعض المكتبات لم تُثبَّت — سيحاول النظام الاستمرار
)

echo.
echo [2b/4] التحقق من مفسّر التشغيل...
"%PYTHON%" -c "import MetaTrader5, sklearn, pandas, mcp" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ مفسّر Python هذا لا يملك حزم التشغيل الأساسية ^(MetaTrader5 / scikit-learn / mcp^).
    echo    شغّل:  "%PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo ✅ حزم التشغيل الأساسية موجودة

echo.
echo [3/4] التحقق من ملف الإعدادات...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo ✅ تم إنشاء .env من المثال — عدّل الإعدادات حسب حاجتك
    ) else (
        echo ⚠️ لم يُعثر على .env — تأكد من الإعدادات
    )
) else (
    echo ✅ .env موجود
)

echo.
echo [4/4] تشغيل الخادم...
echo.
echo ╔══════════════════════════════════════════╗
echo ║  📡 الخادم يعمل على: http://localhost:8000  ║
echo ║  📖 API Docs:  http://localhost:8000/docs   ║
echo ║  🔌 WebSocket: ws://localhost:8000/ws       ║
echo ╚══════════════════════════════════════════╝
echo.

"%PYTHON%" main.py

pause
