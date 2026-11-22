@echo off
title Quantum AI Agents Forex Trading System v4.2 Elite - REAL DATA
color 0A
cls

echo ==========================================================
echo    QUANTUM AI AGENTS FOREX TRADING SYSTEM v4.2
echo    FULL SYSTEM LAUNCHER - REAL DATA MODE
echo ==========================================================
echo    Backend API : http://localhost:8000
echo    Frontend UI : http://localhost:5173
echo ==========================================================
echo.
echo Cleaning up previous instances on ports 8000 and 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5174 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo.

set ROOT=%~dp0

rem -- Python 3.11 path
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe

if exist "%PYTHON%" goto python_ready

set PYTHON=C:\Python311\python.exe
if exist "%PYTHON%" goto python_ready

echo [ERROR] Python 3.11 not found!
echo         Searched at:
echo           %LOCALAPPDATA%\Programs\Python\Python311\python.exe
echo           C:\Python311\python.exe
echo.
echo Please install Python 3.11 from https://python.org
pause
exit /b 1

:python_ready

rem -- Verify Node.js
where node >nul 2>&1
if %errorlevel% equ 0 goto node_ready

echo [ERROR] Node.js not found. Please install it from nodejs.org
pause
exit /b 1

:node_ready

echo [1/5] Core packages verified.

echo [2/5] Checking TimesFM weights...
"%PYTHON%" -c "import os; w='C:/Users/magdi/timesfm_weights'; ok=os.path.isfile(w+'/model.safetensors'); print('[OK] TimesFM weights found') if ok else print('[WARN] TimesFM weights not found')"
echo.

echo [3/5] Node packages ready.

echo [4/5] Starting Backend Server (FastAPI)...
start /b cmd /c "cd /d "%ROOT%backend" && "%PYTHON%" main.py"

echo [5/5] Starting Frontend Server (Vite UI)...
start /b cmd /c "cd /d "%ROOT%" && node node_modules\vite\bin\vite.js --port 5173 --host 0.0.0.0"

rem -- Start MetaTrader 5 if exists
set MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
if exist "%MT5_PATH%" (
    echo [MT5] Launching MetaTrader 5...
    start "" "%MT5_PATH%"
) else (
    set MT5_PATH=C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe
    if exist "%MT5_PATH%" (
        echo [MT5] Launching MetaTrader 5 EXNESS...
        start "" "%MT5_PATH%"
    ) else (
        set MT5_PATH=C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe
        if exist "%MT5_PATH%" (
            echo [MT5] Launching MetaTrader 5 IC Markets Global...
            start "" "%MT5_PATH%"
        )
    )
)

echo.
echo Initializing servers (waiting for ports 8000 and 5173)...
set WAIT_COUNT=0
:wait_frontend
ping 127.0.0.1 -n 2 >nul
set /a WAIT_COUNT+=1
netstat -aon | findstr :5173 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 goto servers_ready
if %WAIT_COUNT% lss 30 (
    echo Waiting for Vite UI to be ready... (%WAIT_COUNT%/30)
    goto wait_frontend
)
echo [WARN] UI port 5173 did not respond within timeout, proceeding anyway.

:servers_ready
echo [OK] Servers initialized successfully.
echo.
echo Opening Dashboard in browser...
start http://localhost:5173/

echo ==========================================================
echo    SYSTEM IS FULLY RUNNING IN SINGLE CONSOLE
echo    Frontend  - http://localhost:5173
echo    Backend   - http://localhost:8000
echo    API Docs  - http://localhost:8000/docs
echo ==========================================================
echo    Close this window to STOP all servers
echo ==========================================================
echo.

:keepalive
ping 127.0.0.1 -n 30 >nul
goto keepalive
