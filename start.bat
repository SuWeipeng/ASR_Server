@echo off
cd /d "%~dp0"

echo [1/3] Activating conda environment: qwen3-asr
call conda activate qwen3-asr

echo [2/3] Starting backend server...
cd backend
start "ASR Backend" cmd /k "conda activate qwen3-asr && python -m app.main"
cd ..

echo [3/3] Starting frontend dev server...
cd frontend
start "ASR Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ====================================
echo Startup Complete!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo ====================================
