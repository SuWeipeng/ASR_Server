# ASR Practice Startup Script for PowerShell

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "ASR Practice - Startup Script" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "[1/6] Checking environment..." -ForegroundColor Yellow

# Check if conda environment is active
$envName = $env:CONDA_DEFAULT_ENV
if ($envName -ne "qwen3-asr") {
    Write-Host "[ERROR] Please activate qwen3-asr environment first!" -ForegroundColor Red
    Write-Host "Run: conda activate qwen3-asr" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Using conda environment: $envName" -ForegroundColor Green
Write-Host ""

# Check Node.js
Write-Host "[2/6] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "[OK] Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Install backend dependencies
Write-Host "[3/6] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location backend
Write-Host "Installing Python packages..." -ForegroundColor Cyan
pip install -r requirements.txt
Set-Location ..
Write-Host "[OK] Backend dependencies installed" -ForegroundColor Green
Write-Host ""

# Install frontend dependencies
Write-Host "[4/6] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm packages..." -ForegroundColor Cyan
    npm install
} else {
    Write-Host "Frontend dependencies already installed" -ForegroundColor Cyan
}
Set-Location ..
Write-Host "[OK] Frontend dependencies installed" -ForegroundColor Green
Write-Host ""

# Start backend server
Write-Host "[5/6] Starting backend server..." -ForegroundColor Yellow
Set-Location backend
Start-Process cmd -ArgumentList "/K", "title ASR Backend Server && conda activate qwen3-asr && python -m app.main"
Set-Location ..
Write-Host "[OK] Backend server started (http://localhost:8000)" -ForegroundColor Green
Write-Host ""

# Start frontend server
Write-Host "[6/6] Starting frontend dev server..." -ForegroundColor Yellow
Set-Location frontend
Start-Process cmd -ArgumentList "/K", "title ASR Frontend Server && npm run dev"
Set-Location ..
Write-Host "[OK] Frontend server started (http://localhost:5173)" -ForegroundColor Green
Write-Host ""

# Wait for servers to start
Write-Host "Waiting for servers to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Startup Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API:    http://localhost:8000" -ForegroundColor White
Write-Host "API Docs:       http://localhost:8000/docs" -ForegroundColor White
Write-Host "Frontend:       http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop services (in the server windows)" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to exit this window"
