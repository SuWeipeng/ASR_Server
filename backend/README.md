# ASR Server - Backend

English Speaking Practice Server powered by Qwen3-ASR

## Features

- 🎤 **Audio/Video Upload**: Support for video and audio files
- 📝 **ASR Transcription**: High-quality speech recognition with Qwen3-ASR
- ⏱️ **Timestamp Alignment**: Word-level timestamps with Qwen3-ForcedAligner
- 🎯 **Pronunciation Evaluation**: Compare user speech against target text
- 📊 **Detailed Analysis**: Word-by-word comparison and scoring
- 🔊 **Audio Processing**: FFmpeg integration for audio extraction

## Installation

### Prerequisites

1. **Python 3.8+**
2. **FFmpeg** (must be installed and in PATH)
   - Windows: Download from https://ffmpeg.org/download.html
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`

3. **CUDA** (optional, for GPU acceleration)
   - Install CUDA Toolkit 11.8+ if you have NVIDIA GPU

### Setup

1. Create virtual environment:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. Install PyTorch (choose your platform):

```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CPU only
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install qwen-asr:
```bash
pip install qwen-asr
```

## Configuration

Configuration is handled in `app/config.py`. You can set environment variables:

```bash
# Model selection (0.6B or 1.7B)
export ASR_MODEL_SIZE=1.7B

# Device selection
export USE_CPU=false  # Set to true for CPU

# Model precision
export DTYPE=bfloat16  # Options: bfloat16, float16, float32

# Server configuration
export HOST=127.0.0.1
export PORT=8000
```

Or create a `.env` file in the backend directory.

## Running

### Development Mode
```bash
uvicorn app.main:app --reload --port 8000
```

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### Media
- `POST /api/media/upload` - Upload media file
- `GET /api/media/file/{file_id}` - Download media file
- `GET /api/media/info/{file_id}` - Get file information
- `DELETE /api/media/file/{file_id}` - Delete file
- `GET /api/media/audio/{file_id}` - Get extracted audio

### Transcription
- `POST /api/transcription/generate` - Generate subtitles
- `GET /api/transcription/subtitles/{file_id}` - Get cached subtitles
- `POST /api/transcription/search/{file_id}` - Search subtitles
- `GET /api/transcription/export/{file_id}` - Export subtitles (SRT/VTT)

### Practice
- `POST /api/practice/evaluate` - Evaluate user pronunciation
- `POST /api/practice/quick-score` - Quick text comparison
- `GET /api/practice/health` - Check practice service status

### Dictionary (placeholder)
- `GET /api/dictionary/lookup/{word}` - Look up word definition
- `GET /api/dictionary/available` - Check service availability

### System
- `GET /api/system/status` - Get system status
- `GET /api/system/health` - Health check
- `POST /api/system/initialize` - Initialize system
- `GET /api/system/config` - Get configuration

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration settings
│   ├── api/                 # API routes
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   ├── utils/               # Utility functions
│   └── core/                # Model loaders
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Model Files

Place model files in the project root:

```
../models/
├── Qwen3-ASR-1.7B/
└── Qwen3-ForcedAligner-0.6B/
```

## Testing

Test the API with the documentation page:
1. Open http://localhost:8000/docs
2. Try uploading a file
3. Generate subtitles
4. Evaluate pronunciation

## Troubleshooting

### FFmpeg not found
- Make sure FFmpeg is installed and in PATH
- Test with: `ffmpeg -version`

### CUDA out of memory
- Use smaller model (0.6B)
- Reduce batch size: `MAX_INFERENCE_BATCH_SIZE=16`
- Use CPU: `USE_CPU=true`

### Model not loading
- Check model paths in `config.py`
- Ensure model files exist
- Check available disk space (models are ~10GB)

## Development

### Adding New Endpoints

1. Create schema in `app/models/schemas.py`
2. Add service in `app/services/`
3. Create route in `app/api/`
4. Register in `app/api/__init__.py`

### Logging

Logger is available in all modules:
```python
from app.utils import logger

logger.info("Info message")
logger.error("Error message")
```

## License

MIT License
