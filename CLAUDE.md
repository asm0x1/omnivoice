# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Text-to-speech (TTS) project using [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) model with voice cloning support.

## Commands

```bash
# Local CLI (macOS: use requirements-macos.txt)
pip install -r requirements-macos.txt
python app.py --device auto

# Docker Compose (API: 1218, Web UI: 1219)
docker-compose up -d

# Direct API run (requires dependencies)
python api.py --device auto

# Build Docker image
docker build -t omnivoice-api .
```

## Dependencies

- `requirements-api.txt` — API/Docker (Linux x86_64 CPU torch)
- `requirements-macos.txt` — macOS local CLI (arm64/mps torch)

## Architecture

- **app.py**: Interactive CLI for local TTS generation
- **api.py**: FastAPI REST server on port 1218
- **web.py**: Starts omnivoice-demo directly on port 1219 (no proxy)
- **start.sh**: Docker entrypoint — starts web.py and api.py both in background, managed by PID 1
- **docker-compose.yaml**: Container with ports 1218 (API) + 1219 (Web UI)

### Device Configuration

Auto-detection priority: CUDA → MPS → CPU. Use `--device auto` (default on API, not CLI) for automatic detection.

| Platform | Device | dtype |
|----------|--------|-------|
| Apple Silicon | mps | float16 |
| NVIDIA GPU | cuda:0 | float16 |
| CPU | cpu | float32 |

### Voice Sample Structure

Each voice lives in a subdirectory under `voice_sample/`:
- Audio file: `.mp3`, `.wav`, or `.flac` (first one found)
- Text file: `.txt` (first one found, optional - if missing, uses Whisper auto-transcription)

### API Endpoints

API docs at `http://localhost:1218/docs`. All output is **24kHz mono WAV**.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + device info |
| `/voice_sample` | GET | List voice sample folders |
| `/generate` | POST | Generate single speech |
| `/generate_batch` | POST | Generate multiple segments (concatenated) |

### Web UI

Start with `python web.py` (launches omnivoice-demo directly on port 1219). Access at `http://localhost:1219`.

### Environment Variables

- `AUDIO_DIR`: Override voice sample directory (default: `voice_sample`)
- `HF_ENDPOINT`: HuggingFace mirror for Chinese networks (docker-compose sets `https://hf-mirror.com`)