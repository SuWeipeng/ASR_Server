@echo off
echo ====================================
echo ASR Practice - Startup Script
echo ====================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo [1/6] Checking environment...
conda --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Conda not found. Please install Anaconda or Miniconda
    pause
    exit /b 1
)

REM Activate conda environment
echo Activating conda environment: qwen3-asr
call conda activate qwen3-asr
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate conda environment 'qwen3-asr'
    echo Please create it first: conda create -n qwen3-asr python=3.10
    pause
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

echo [OK] Environment check passed
echo.

echo [2/6] Installing backend dependencies...
cd backend
echo Installing Python packages...
pip install -r requirements.txt
cd ..

echo [OK] Backend dependencies installed
echo.

echo [3/6] Installing frontend dependencies...
cd frontend
if not exist "node_modules" (
    echo Installing npm packages...
    call npm install
)
cd ..

echo [OK] Frontend dependencies installed
echo.

echo [4/6] Starting backend server...
cd backend
start "ASR Backend Server" cmd /k "conda activate qwen3-asr && python -m app.main"
cd ..

echo [OK] Backend server started (http://localhost:8000)
echo.

echo [5/6] Starting frontend dev server...
cd frontend
start "ASR Frontend Server" cmd /k "npm run dev"
cd ..

echo [OK] Frontend server started (http://localhost:5173)
echo.

echo [6/6] Waiting for servers to start...
timeout /t 3 /nobreak >nul

echo ====================================
echo Startup Complete!
echo ====================================
echo.
echo Backend API:    http://localhost:8000
echo API Docs:       http://localhost:8000/docs
echo Frontend:       http://localhost:5173
echo.
echo Press Ctrl+C to stop all services
echo ====================================
echo.

REM Wait for user input before closing
pause
