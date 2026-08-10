#!/bin/bash

echo "===================================="
echo "ASR Practice - 一体化启动脚本"
echo "===================================="
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check Python
echo "[1/6] 检查环境..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

echo "[✓] 环境检查通过"
echo ""

# Install backend dependencies
echo "[2/6] 安装后端依赖..."
cd backend
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "安装 Python 包..."
pip install -r requirements.txt -q
cd ..

echo "[✓] 后端依赖安装完成"
echo ""

# Install frontend dependencies
echo "[3/6] 安装前端依赖..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装 npm 包..."
    npm install --silent
fi
cd ..

echo "[✓] 前端依赖安装完成"
echo ""

# Start backend server
echo "[4/6] 启动后端服务器..."
cd backend
source venv/bin/activate
python -m app.main &
BACKEND_PID=$!
cd ..

echo "[✓] 后端服务器已启动 (PID: $BACKEND_PID)"
echo ""

# Start frontend server
echo "[5/6] 启动前端开发服务器..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "[✓] 前端服务器已启动 (PID: $FRONTEND_PID)"
echo ""

# Wait for services to start
echo "[6/6] 等待服务启动..."
sleep 5

echo "===================================="
echo "启动完成！"
echo "===================================="
echo ""
echo "后端 API:    http://localhost:8000"
echo "API 文档:    http://localhost:8000/docs"
echo "前端界面:    http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "===================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Trap signals
trap cleanup SIGINT SIGTERM

# Wait indefinitely
wait
