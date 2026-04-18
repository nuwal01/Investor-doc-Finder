@echo off
echo ========================================
echo Financial Report Finder - Run Script
echo ========================================
echo.

REM Check if node is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo Starting Backend Server...
start "Backend Server" cmd /k "cd /d %~dp0backend && npm run dev"

echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo Starting Frontend Server...
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo Both servers are starting!
echo.
echo Backend:  http://localhost:3001
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit this window...
echo (The servers will continue running)
pause >nul
