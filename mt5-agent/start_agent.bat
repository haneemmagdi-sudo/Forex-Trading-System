@echo off
chcp 65001 > nul
title Quantum Forex AI — MT5 Agent
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Quantum Forex AI — MT5 Agent v1.0    ║
echo  ║   جاري تشغيل وكيل التداول...           ║
echo  ╚══════════════════════════════════════════╝
echo.

:: التحقق من ملف الإعدادات
if not exist ".env" (
    echo [!] ملف .env غير موجود!
    echo     شغّل setup.bat أولاً
    pause
    exit /b 1
)

set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python
    ) else (
        echo [!] Python غير مثبت. يرجى تثبيته من python.org
        pause
        exit /b 1
    )
)

:: تشغيل الـ Agent
"%PYTHON%" agent.py

echo.
echo  [توقف] الـ Agent توقف. اضغط أي مفتاح للخروج
pause
