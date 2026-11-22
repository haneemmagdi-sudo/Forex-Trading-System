@echo off
title Quantum AI Agents Forex Trading System - STOP ALL
color 0C
cls

echo ==========================================================
echo    STOPPING QUANTUM AI FOREX TRADING SYSTEM
echo ==========================================================
echo.
echo Stopping processes listening on ports 8000, 5173, 5174...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing Backend PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    echo Killing Frontend PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5174 ^| findstr LISTENING') do (
    echo Killing Extra PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo [OK] All system servers have been stopped.
echo ==========================================================
ping 127.0.0.1 -n 3 >nul
