# ASR Server - English Speaking Practice Web Application

基于 Qwen3-ASR 的英语口语练习 Web 应用

## 功能特性

- 🎤 **音视频上传** - 支持视频和音频文件
- 📝 **AI字幕生成** - 使用 Qwen3-ASR 生成高质量字幕
- ⏱️ **时间轴对齐** - 单词级时间戳，支持精确同步
- 🎯 **跟读练习** - 录音并评估发音准确度
- 📊 **详细分析** - 单词级对比和评分反馈
- ⌨️ **快捷键支持** - 高效的键盘操作
- 🌙 **深色模式** - 护眼的深色主题

## 技术栈

### 后端
- **框架**: FastAPI + Python
- **AI模型**: Qwen3-ASR-1.7B + Qwen3ForcedAligner-0.6B
- **音频处理**: FFmpeg, soundfile
- **架构**: 分层架构 (API → Service → Core)

### 前端
- **框架**: React 18 + Vite
- **状态管理**: Redux Toolkit
- **样式**: TailwindCSS
- **图标**: Lucide React

## 快速开始

### 前置要求

1. **Python 3.8+**
2. **Node.js 18+**
3. **FFmpeg** (必须安装并在 PATH 中)
   - Windows: [下载](https://ffmpeg.org/download.html)
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`
4. **CUDA** (可选，GPU 加速)
5. **模型文件** - 下载以下模型到 `models/` 目录:
   - Qwen3-ASR-1.7B (或 0.6B)
   - Qwen3-ForcedAligner-0.6B

### 一键启动

#### Windows
```batch
start.bat
```

#### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

脚本会自动:
1. 检查环境
2. 安装依赖
3. 启动后端服务器 (http://localhost:8000)
4. 启动前端服务器 (http://localhost:5173)

### 手动启动

#### 后端
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m app.main
```

#### 前端
```bash
cd frontend
npm install
npm run dev
```

## 使用指南

### 1. 上传文件
- 点击顶部导航栏的 "打开文件" 按钮
- 选择视频或音频文件

### 2. 生成字幕
- 上传后自动生成字幕
- 右侧面板显示字幕列表

### 3. 播放与练习
- 使用播放器控制条播放视频
- 点击字幕跳转到对应时间
- 选择字幕后可在下方练习区进行跟读

### 4. 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Space` | 播放/暂停 |
| `A` | 上一句 |
| `D` | 下一句 |
| `R` | 重播当前句 |
| `S` | 切换单句循环 |
| `L` | 按住录音 |
| `1-4` | 切换倍速 (0.5x - 1.25x) |
| `Ctrl+F` | 搜索字幕 |
| `Esc` | 关闭弹窗 |
| `?` | 显示快捷键帮助 |

## API 文档

启动后端后访问: http://localhost:8000/docs

### 主要端点

#### 媒体管理
- `POST /api/media/upload` - 上传文件
- `GET /api/media/file/{file_id}` - 获取文件
- `DELETE /api/media/file/{file_id}` - 删除文件

#### 字幕生成
- `POST /api/transcription/generate` - 生成字幕
- `GET /api/transcription/subtitles/{file_id}` - 获取字幕
- `GET /api/transcription/export/{file_id}` - 导出字幕 (SRT/VTT)

#### 练习评估
- `POST /api/practice/evaluate` - 评估发音
- `GET /api/practice/health` - 健康检查

#### 系统状态
- `GET /api/system/status` - 系统状态
- `GET /api/system/health` - 健康检查

## 配置

### 环境变量

创建 `.env` 文件在 `backend/` 目录:

```bash
# 模型配置
ASR_MODEL_SIZE=1.7B          # 可选: 0.6B 或 1.7B

# 设备配置
USE_CPU=false                 # true 使用 CPU

# 模型精度
DTYPE=bfloat16               # bfloat16, float16, float32

# 服务配置
HOST=127.0.0.1
PORT=8000

# 文件上传
MAX_UPLOAD_SIZE=524288000    # 500MB
```

### 前端配置

编辑 `frontend/vite.config.js` 修改端口和代理设置。

## 项目结构

```
D:\ASR_Server/
├── backend/                 # 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── services/       # 业务逻辑
│   │   ├── models/         # 数据模型
│   │   ├── utils/          # 工具函数
│   │   └── core/           # 模型加载
│   ├── requirements.txt
│   └── README.md
├── frontend/               # 前端
│   ├── src/
│   │   ├── components/     # React 组件
│   │   ├── store/          # Redux 状态
│   │   ├── services/       # API 服务
│   │   ├── hooks/          # 自定义 Hooks
│   │   └── utils/          # 工具函数
│   ├── package.json
│   └── vite.config.js
├── models/                 # 模型文件
├── uploads/                # 上传文件
├── temp/                   # 临时文件
├── start.bat              # Windows 启动脚本
├── start.sh               # Linux/Mac 启动脚本
└── README.md              # 本文件
```

## 故障排除

### FFmpeg 未找到
- 确保 FFmpeg 在 PATH 中
- 测试: `ffmpeg -version`

### CUDA 内存不足
- 使用小模型 (0.6B)
- 设置 `USE_CPU=true`
- 减小批次大小

### 模型加载失败
- 检查模型路径是否正确
- 确保模型文件完整
- 检查磁盘空间 (约 10GB)

### 前端无法连接后端
- 检查后端是否启动 (http://localhost:8000/health)
- 检查 CORS 配置
- 查看浏览器控制台错误

## 开发

### 后端开发
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端开发
```bash
cd frontend
npm install
npm run dev
```

### 添加新功能
1. 后端: 在 `app/api/` 添加路由
2. 前端: 在 `src/services/` 添加 API 调用
3. 状态: 在 `src/store/` 添加 slice

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request!

## 致谢

- [Qwen Team](https://github.com/QwenLM/Qwen2-Audio) - Qwen3-ASR 模型
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [React](https://react.dev/) - UI 框架
- [TailwindCSS](https://tailwindcss.com/) - CSS 框架

---

**Made with ❤️ for English learners**
