@echo off
title Quantum AI Forex Trading System - FULL LAUNCH
color 0A
cls

echo ==========================================================
echo    QUANTUM AI AGENTS FOREX TRADING SYSTEM v4.2
echo    FULL SYSTEM LAUNCHER
echo ==========================================================
echo    Backend  API : http://localhost:8000
echo    Frontend UI  : http://localhost:5173
echo ==========================================================
echo.
echo Cleaning up previous instances on ports 8000 and 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5174 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo.

set ROOT=%~dp0

rem -- Check Python 3.11 path
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

rem -- Check Node.js
where node >nul 2>&1
if %errorlevel% equ 0 goto node_ready

echo [ERROR] Node.js not found. Please install it from nodejs.org
pause
exit /b 1

:node_ready

echo [1/5] Checking Python packages...
"%PYTHON%" -m pip install -r "%ROOT%backend\requirements.txt" --quiet 2>nul
echo [OK] Python packages ready.

echo [2/5] Checking TimesFM weights...
"%PYTHON%" -c "import os; w='C:/Users/magdi/timesfm_weights'; ok=os.path.isfile(w+'/model.safetensors'); print('[OK] TimesFM weights found') if ok else print('[WARN] TimesFM weights not found')"
echo.

echo [3/5] Checking Node packages...
if not exist "%ROOT%node_modules" (
    echo Installing npm packages, please wait...
    cd /d "%ROOT%"
    npm install --silent
)
echo [OK] Node packages ready.

echo [4/5] Starting Backend Server...
start /b "" cmd /c "cd /d "%ROOT%backend" && "%PYTHON%" main.py"

echo [5/5] Starting Frontend Server...
start /b "" cmd /c "cd /d "%ROOT%" && npm run dev -- --port 5173"

echo.
echo Waiting for servers to start...
timeout /t 4 /nobreak >nul

echo.
echo Opening Dashboard in browser...
start "" "http://localhost:5173/"

echo ==========================================================
echo    SYSTEM IS RUNNING
echo    Frontend  - http://localhost:5173
echo    Backend   - http://localhost:8000
echo    API Docs  - http://localhost:8000/docs
echo    Close this window to STOP all servers
echo ==========================================================
echo.

:keepalive
timeout /t 30 /nobreak >nul
goto keepalive
