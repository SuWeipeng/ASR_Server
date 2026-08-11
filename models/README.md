# 模型文件

本目录用于存放 ASR 服务器所需的 AI 模型文件。

## 所需模型

根据配置，需要下载以下模型之一：

### ASR 模型（二选一）

1. **Qwen3-ASR-1.7B**（推荐，精度更高）
2. **Qwen3-ASR-0.6B**（轻量级，速度更快）

### 强制对齐模型（必需）

- **Qwen3-ForcedAligner-0.6B**

## 下载方法

### 方法一：使用 Hugging Face CLI

```bash
# 安装 huggingface-cli
pip install -U huggingface_hub

# 下载 ASR 模型（1.7B 版本）
huggingface-cli download Qwen/Qwen3-ASR-1.7B --local-dir Qwen3-ASR-1.7B

# 或下载 0.6B 版本
huggingface-cli download Qwen/Qwen3-ASR-0.6B --local-dir Qwen3-ASR-0.6B

# 下载强制对齐模型
huggingface-cli download Qwen/Qwen3-ForcedAligner-0.6B --local-dir Qwen3-ForcedAligner-0.6B
```

### 方法二：使用 Git LFS

```bash
# 安装 Git LFS（如未安装）
git lfs install

# 下载 ASR 模型（1.7B 版本）
git clone https://huggingface.co/Qwen/Qwen3-ASR-1.7B

# 或下载 0.6B 版本
git clone https://huggingface.co/Qwen/Qwen3-ASR-0.6B

# 下载强制对齐模型
git clone https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B
```

### 方法三：中国用户使用 ModelScope

```bash
# 安装 modelscope
pip install modelscope

# 下载 ASR 模型（1.7B 版本）
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-ASR-1.7B', cache_dir='.')"

# 或下载 0.6B 版本
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-ASR-0.6B', cache_dir='.')"

# 下载强制对齐模型
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-ForcedAligner-0.6B', cache_dir='.')"
```

或使用 Git：

```bash
git clone https://www.modelscope.cn/Qwen/Qwen3-ASR-1.7B.git
git clone https://www.modelscope.cn/Qwen/Qwen3-ASR-0.6B.git
git clone https://www.modelscope.cn/Qwen/Qwen3-ForcedAligner-0.6B.git
```

## 目录结构

下载完成后，确保目录结构如下：

```
models/
├── Qwen3-ASR-1.7B/          # 或 Qwen3-ASR-0.6B/
│   ├── config.json
│   ├── model.pth
│   └── ...
└── Qwen3-ForcedAligner-0.6B/
    ├── config.json
    ├── model.pth
    └── ...
```

## 配置模型大小

在 `backend/.env` 文件中设置模型大小：

```bash
# 使用 1.7B 模型（默认）
ASR_MODEL_SIZE=1.7B

# 或使用 0.6B 模型（轻量级）
ASR_MODEL_SIZE=0.6B
```

## 模型信息

| 模型 | 参数量 | 用途 | 下载大小 |
|------|--------|------|----------|
| Qwen3-ASR-1.7B | 1.7B | ASR 转录 | ~7GB |
| Qwen3-ASR-0.6B | 0.6B | ASR 转录（轻量） | ~2.5GB |
| Qwen3-ForcedAligner-0.6B | 0.6B | 单词级时间戳 | ~2.5GB |

## 官方链接

- [Hugging Face - Qwen3-ASR Collection](https://huggingface.co/collections/Qwen/qwen3-asr)
- [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
- [Qwen3-ASR-0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B)
- [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)
- [ModelScope Mirror](https://modelscope.cn/models/Qwen/Qwen3-ASR-1.7B) (中国用户推荐)
