# OmniVoice TTS API

基于 [OmniVoice](https://github.com/k2-fsa/OmniVoice) 的文本转语音服务，支持声音克隆。

## 部署方式

### Docker Compose（推荐）

```bash
docker-compose up -d
```

启动后：
- **API 服务**: http://localhost:1218/docs
- **Web UI**: http://localhost:1219

### 手动运行

需要本地安装依赖并下载模型：

**macOS (Apple Silicon):**

```bash
pip install -r requirements-macos.txt
```

**Linux (Docker/NAS):**

**测试NAS为 绿联DXP4800Plus 16G Ram版本**

```bash
pip install -r requirements-api.txt
```

启动 API（端口 1218）和 Web UI（端口 1219）：

```bash
# 终端 1: 启动 API
python api.py --port 1218 --device auto

# 终端 2: 启动 Web UI（内部自动调用 omnivoice-demo）
python web.py
```

启动后：
- **API**: http://localhost:1218/docs
- **Web UI**: http://localhost:1219

## 使用模式

| 模式 | 端口 | 说明 |
|------|------|------|
| REST API | 1218 | 程序调用，批量生成 |
| Web UI | 1219 | 浏览器交互界面 |
| CLI | - | 命令行交互模式 |

### CLI 模式

```bash
python app.py --device auto
```

流程：扫描 voice_sample → 选择声音 → 输入文字 → 生成音频 → 循环

### REST API

```bash
# 健康检查
curl http://localhost:1218/health

# 查看可用声音列表
curl http://localhost:1218/voice_sample

# 生成语音
curl -X POST "http://localhost:1218/generate?text=你好世界&voice=ami.moment声音样本" -o output.wav

# 批量生成
curl -X POST "http://localhost:1218/generate_batch?voice=ami.moment声音样本" \
  -F "texts=第一段文本" \
  -F "texts=第二段文本" \
  -o batch_output.wav
```

**API 参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 要合成的文本 |
| `voice` | string | 否 | 声音文件夹名，自动匹配音频和文本 |
| `ref_audio` | string | 否 | 参考音频路径（voice 未指定时必填） |
| `ref_text` | string | 否 | 参考文本或文本文件路径 |
| `language` | string | 否 | 语言（如 "Chinese", "English"） |
| `speed` | float | 否 | 语速（1.0 = 默认） |

**输出格式**: 全部返回 **24kHz mono WAV**

## 目录结构

```
.
├── app.py                  # CLI 交互模式
├── api.py                  # FastAPI REST 服务（端口 1218）
├── web.py                  # Web UI 启动器（直接启动 omnivoice-demo，端口 1219）
├── start.sh                # Docker 启动脚本
├── Dockerfile
├── docker-compose.yaml
├── requirements-api.txt   # Linux/Docker 依赖（API 服务）
├── requirements-macos.txt  # macOS 本地依赖
├── voice_sample/           # 声音样本目录
│   └── <voice_name>/
│       ├── *.mp3 / *.wav / *.flac
│       └── *.txt (可选)
└── outputs/                # 生成的音频输出目录
```

## 声音样本格式

每个声音文件夹下需要包含：
- `.mp3`、`.wav` 或 `.flac` 音频文件（自动使用第一个）
- `.txt` 文本文件（可选，自动使用第一个；缺失时使用 Whisper 自动转录）

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUDIO_DIR` | `voice_sample` | 声音样本目录 |
| `HF_ENDPOINT` | - | HuggingFace 镜像（Docker 已配置 `https://hf-mirror.com`） |

## 注意事项

- 模型首次启动需要下载（约 1GB），请耐心等待
- CPU 模式下生成速度较慢
- 参考音频建议 3~10 秒，效果更好