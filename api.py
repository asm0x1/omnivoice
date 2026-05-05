#!/usr/bin/env python3
import argparse
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import soundfile as sf
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import Response
from pydantic import BaseModel, Field
import torch
from pydub import AudioSegment
import numpy as np

from omnivoice import OmniVoice


# Global model instance
model = None

# Audio directory for reference files
AUDIO_DIR = os.environ.get("AUDIO_DIR", "voice_sample")


def load_model(device: str = "cpu", dtype: torch.dtype = torch.float32):
    """Load OmniVoice model with specified device and precision."""
    global model
    if model is None:
        model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=dtype,
        )
    return model


def auto_device():
    """Auto-detect best available device."""
    if torch.cuda.is_available():
        return "cuda:0"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"


def auto_dtype(device: str) -> torch.dtype:
    """Select dtype based on device capability."""
    return torch.float16 if device.startswith("cuda") or device == "mps" else torch.float32


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    load_model()
    yield
    global model
    model = None


description = """
## OmniVoice TTS API

Text-to-speech API with voice cloning based on [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice).

### Features
- **Voice Cloning**: Generate speech in a voice similar to reference audio
- **Batch Generation**: Generate multiple segments in one request
- **Multi-format Support**: Auto-convert MP3, WAV, and other audio formats

### Voice Selection
Use `voice` parameter to select from available voices in `voice_sample/` directory.
Each voice folder should contain any audio file (.mp3/.wav/.flac) and optionally a .txt file.

### Output Format
- All generated audio is returned as **24kHz mono WAV**
- Chinese text works best with `language="Chinese"`
"""

tags_metadata = [
    {"name": "Info", "description": "System information and health checks"},
    {"name": "Voices", "description": "List and manage available voice clones"},
    {"name": "Generation", "description": "Text-to-speech generation endpoints"},
]

app = FastAPI(
    title="OmniVoice TTS API",
    description=description,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
)


@app.get("/health", tags=["Info"])
async def health_check():
    """
    Check API health status.

    Returns whether the model is loaded and ready to serve requests.
    """
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "device": auto_device() if model else None,
    }


def convert_audio_to_wav(input_path: str) -> str:
    """Convert audio file to 24kHz mono WAV and return path."""
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(24000).set_channels(1)
    output_path = input_path.rsplit(".", 1)[0] + "_converted.wav"
    audio.export(output_path, format="wav")
    return output_path


def resolve_text(ref_text: str | None) -> str | None:
    """Resolve ref_text from file path if it's a file reference."""
    if ref_text is None:
        return None
    # If ref_text is an existing file, read its content
    if Path(ref_text).is_absolute():
        text_path = Path(ref_text)
    else:
        text_path = Path(AUDIO_DIR) / ref_text

    if text_path.exists() and text_path.is_file():
        return text_path.read_text(encoding="utf-8").strip()
    # Otherwise return as-is (direct text input)
    return ref_text


def find_voice_files(voice_name: str) -> tuple[str, str] | None:
    """
    Find voice audio and text files in a voice folder.
    Returns (audio_path, text_path) or None if not found.
    Auto-matching: first audio file + first text file in the folder.
    """
    voice_dir = Path(AUDIO_DIR) / voice_name
    if not voice_dir.is_dir():
        return None

    # Auto-match: first audio file + first text file
    audio_files = list(voice_dir.glob("*.mp3")) + list(voice_dir.glob("*.wav")) + list(voice_dir.glob("*.flac"))
    if not audio_files:
        return None
    audio_path = str(Path(voice_name) / audio_files[0].name)  # relative path with folder prefix

    text_files = list(voice_dir.glob("*.txt"))
    text_path = str(Path(voice_name) / text_files[0].name) if text_files else None  # relative path with folder prefix

    return audio_path, text_path


@app.get("/voice_sample", tags=["Voices"])
async def list_voices():
    """
    List all available voice sample folder names.

    Returns folder names found in the `voice_sample/` directory.
    """
    audio_base = Path(AUDIO_DIR)
    if not audio_base.exists():
        return []

    voices = []
    for item in sorted(audio_base.iterdir()):
        if item.is_dir():
            voice_files = find_voice_files(item.name)
            if voice_files:
                voices.append(item.name)
    return voices


class GenerateParams(BaseModel):
    """Parameters for speech generation."""

    text: Annotated[str, Field(description="Text to synthesize", min_length=1)]
    voice_sample: Annotated[str | None, Field(description="Voice folder name in voice_sample/, auto-selects audio and text")] = None
    ref_audio: Annotated[str | None, Field(description="Reference audio file path (required if voice_sample not specified)")] = None
    ref_text: Annotated[str | None, Field(description="Reference text or path to .txt file")] = None
    language: Annotated[str | None, Field(description="Text language, e.g. 'Chinese' or 'English'")] = None
    speed: Annotated[float | None, Field(description="Speaking speed, 1.0 = default")] = None


@app.post("/generate", tags=["Generation"])
async def generate_speech(params: GenerateParams = Body(...)):
    """
    Generate speech from text using voice cloning.

    Use `voice_sample` to select a pre-configured voice from `voice_sample/`, or provide `ref_audio` directly.

    **Output**: 24kHz mono WAV audio file.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    text = params.text
    voice_sample = params.voice_sample
    ref_audio = params.ref_audio
    ref_text = params.ref_text
    language = params.language
    speed = params.speed

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Auto-detect from voice folder if voice_sample name is provided
    if voice_sample:
        voice_files = find_voice_files(voice_sample)
        if not voice_files:
            raise HTTPException(status_code=400, detail=f"Voice folder not found: {voice_sample}")
        audio_path, text_path = voice_files
        ref_audio = audio_path  # audio_path is already the full resolved path
        if not ref_text and text_path:
            ref_text = text_path

    if not ref_audio:
        raise HTTPException(status_code=400, detail="ref_audio or voice_sample is required")

    # Resolve ref_audio path
    if Path(ref_audio).is_absolute():
        ref_audio_path = ref_audio
    else:
        ref_audio_path = str(Path(AUDIO_DIR) / ref_audio)

    if not Path(ref_audio_path).exists():
        raise HTTPException(status_code=400, detail=f"Reference audio not found: {ref_audio}")

    # Resolve ref_text (file path or direct text)
    resolved_ref_text = resolve_text(ref_text)

    # Convert to required format if needed
    converted_path = None
    try:
        if ref_audio_path.endswith(".wav"):
            audio_path = ref_audio_path
        else:
            audio_path = convert_audio_to_wav(ref_audio_path)
            converted_path = audio_path

        # Generate speech
        audio = model.generate(
            text=text,
            ref_audio=audio_path,
            ref_text=resolved_ref_text,
            language=language,
            speed=speed,
        )

        if not audio or len(audio) == 0:
            raise HTTPException(status_code=500, detail="Generation failed")

        # Return first result as WAV
        output = io.BytesIO()
        sf.write(output, audio[0], 24000, format="WAV")
        output.seek(0)

        return Response(
            content=output.read(),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=output.wav"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
    finally:
        if converted_path and Path(converted_path).exists():
            Path(converted_path).unlink()


class BatchGenerateParams(BaseModel):
    """Parameters for batch speech generation."""

    texts: Annotated[list[str], Field(description="List of texts to synthesize", min_length=1)]
    voice_sample: Annotated[str | None, Field(description="Voice folder name in voice_sample/, auto-selects audio and text")] = None
    ref_audio: Annotated[str | None, Field(description="Reference audio file path (required if voice_sample not specified)")] = None
    ref_text: Annotated[str | None, Field(description="Reference text or path to .txt file")] = None
    language: Annotated[str | None, Field(description="Text language, e.g. 'Chinese' or 'English'")] = None
    speed: Annotated[float | None, Field(description="Speaking speed, 1.0 = default")] = None


@app.post("/generate_batch", tags=["Generation"])
async def generate_batch(params: BatchGenerateParams = Body(...)):
    """
    Generate multiple speech segments in batch.

    All texts share the same voice and reference settings.
    Segments are concatenated into a single WAV file.

    **Output**: 24kHz mono WAV audio file with all segments combined.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    texts = params.texts
    voice_sample = params.voice_sample
    ref_audio = params.ref_audio
    ref_text = params.ref_text
    language = params.language
    speed = params.speed

    if not texts:
        raise HTTPException(status_code=400, detail="Texts list cannot be empty")

    # Auto-detect from voice folder if voice_sample name is provided
    if voice_sample:
        voice_files = find_voice_files(voice_sample)
        if not voice_files:
            raise HTTPException(status_code=400, detail=f"Voice folder not found: {voice_sample}")
        audio_path, text_path = voice_files
        ref_audio = audio_path  # audio_path is already the full resolved path
        if not ref_text and text_path:
            ref_text = text_path

    if not ref_audio:
        raise HTTPException(status_code=400, detail="ref_audio or voice_sample is required")

    # Resolve ref_audio path
    if Path(ref_audio).is_absolute():
        ref_audio_path = ref_audio
    else:
        ref_audio_path = str(Path(AUDIO_DIR) / ref_audio)

    if not Path(ref_audio_path).exists():
        raise HTTPException(status_code=400, detail=f"Reference audio not found: {ref_audio}")

    # Resolve ref_text (file path or direct text)
    resolved_ref_text = resolve_text(ref_text)

    # Convert to required format if needed
    converted_path = None
    try:
        if ref_audio_path.endswith(".wav"):
            audio_path = ref_audio_path
        else:
            audio_path = convert_audio_to_wav(ref_audio_path)
            converted_path = audio_path

        # Generate batch
        audios = model.generate(
            text=texts,
            ref_audio=audio_path,
            ref_text=resolved_ref_text,
            language=language,
            speed=speed,
        )

        # Combine all audio segments
        combined = np.concatenate(audios) if len(audios) > 1 else audios[0]

        output = io.BytesIO()
        sf.write(output, combined, 24000, format="WAV")
        output.seek(0)

        return Response(
            content=output.read(),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=batch_output.wav"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")
    finally:
        if converted_path and Path(converted_path).exists():
            Path(converted_path).unlink()


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="OmniVoice TTS API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=1218, help="Port to bind")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, cuda:0, mps")
    args = parser.parse_args()

    # Auto-detect device
    if args.device == "auto":
        device = auto_device()
    else:
        device = args.device
    dtype = auto_dtype(device)

    load_model(device=device, dtype=dtype)

    uvicorn.run(app, host=args.host, port=args.port)