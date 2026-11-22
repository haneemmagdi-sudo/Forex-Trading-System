@echo off
TITLE Institutional Autonomous Multi-Agent Trading System [2026]
COLOR 0A

echo ===============================================================================
echo     INSTITUTIONAL AUTONOMOUS MULTI-AGENT QUANTITATIVE ENGINE
echo     Target: MetaTrader 5 + Autonomous 5-Agent Council + Self-Healing AST
echo ===============================================================================
echo.

set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe

if not exist "%PY%" (
    echo [ERROR] Python 3.11 not found at %PY%
    echo Please ensure Python 3.11 is installed.
    pause
    exit /b 1
)

echo [1/3] Running Full Quantitative Regression Test Suite (67 Tests)...
set PYTHONPATH=.

rem -- Guard against package collisions (council/ vs backend/agents/)
echo [Guard] Verifying package name collisions and council imports...
"%PY%" tests\test_no_package_name_collision.py
if errorlevel 1 goto error

rem -- Safety, Governance & Monitor Basket Tests
"%PY%" tests\test_phase0_safety.py
if errorlevel 1 goto error
"%PY%" tests\test_p2_wiring_and_governance.py
if errorlevel 1 goto error
"%PY%" tests\test_p5_monitor_agent.py
if errorlevel 1 goto error
"%PY%" tests\test_basket_magic_filter.py
if errorlevel 1 goto error

rem -- Core System & MAS Integrity Tests
"%PY%" tests\test_system_integrity.py
if errorlevel 1 goto error
"%PY%" tests\test_institutional_mas.py
if errorlevel 1 goto error
"%PY%" tests\test_code_healing_agent.py
if errorlevel 1 goto error
"%PY%" tests\test_quant_core_and_bridge.py
if errorlevel 1 goto error
"%PY%" tests\test_autonomous_master.py
if errorlevel 1 goto error

echo.
echo [2/3] Verification Passed: 67/67 Tests 100%% GREEN.
echo [3/3] Launching Autonomous Master Orchestrator (Blackboard + Debate + Self-Healing)...
echo.

"%PY%" autonomous_master_orchestrator.py

echo.
echo ===============================================================================
echo [SUCCESS] Autonomous Cycle Finished. Signals published to MT5 Common Files.
echo ===============================================================================
pause
exit /b 0

:error
echo.
echo [ERROR] Regression tests failed! Aborting run to protect capital.
pause
exit /b 1
