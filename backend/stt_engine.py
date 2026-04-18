"""
stt_engine.py — Speech-to-Text Engine
Uses faster-whisper (CTranslate2 backend) for transcription.
Works with Python 3.14. Supports multilingual audio.
Falls back to simulation mode if model isn't available.
"""

import io
import os
import wave
import tempfile
import numpy as np
import logging
from typing import Optional
from models import STTResult

logger = logging.getLogger(__name__)

# ─── Faster-Whisper Model (lazy load) ────────────────────────

_whisper_model = None


def _load_whisper():
    """Load faster-whisper model on first use. Uses 'base' for speed."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    try:
        from faster_whisper import WhisperModel

        # Use 'base' model — good balance of speed and accuracy
        # compute_type: 'int8' for CPU (fastest), 'float16' for GPU
        logger.info("Loading faster-whisper 'base' model...")
        _whisper_model = WhisperModel(
            "base",
            device="cpu",           # Use 'cuda' if you have a GPU
            compute_type="int8",    # Fastest for CPU
        )
        logger.info("faster-whisper model loaded successfully.")
        return _whisper_model
    except Exception as e:
        logger.warning(f"Could not load faster-whisper model: {e}")
        logger.info("Will use simulation mode for STT.")
        return None


# ─── Core Transcription ─────────────────────────────────────

async def transcribe_audio(audio_bytes: bytes, sample_rate: int = 16000) -> STTResult:
    """
    Transcribe raw audio bytes to text using faster-whisper.
    
    Args:
        audio_bytes: Raw PCM audio bytes (16-bit mono)
        sample_rate: Audio sample rate (default 16kHz for Whisper)
    
    Returns:
        STTResult with transcription text, language, and confidence
    """
    model = _load_whisper()

    if model is None:
        # Simulation mode — useful for frontend testing without model
        return STTResult(
            text="[Simulated transcription — Whisper model not loaded]",
            language="en",
            confidence=0.0
        )

    try:
        # Convert raw PCM bytes to WAV file (faster-whisper needs file input)
        wav_bytes = pcm_to_wav_bytes(audio_bytes, sample_rate)

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            # Run faster-whisper transcription
            segments, info = model.transcribe(
                tmp_path,
                beam_size=5,
                language=None,        # Auto-detect language
                task="transcribe",
                vad_filter=True,      # Filter out non-speech
            )

            # Collect all segments
            all_text = []
            total_logprob = 0.0
            segment_count = 0

            for segment in segments:
                all_text.append(segment.text)
                total_logprob += segment.avg_logprob
                segment_count += 1

            text = " ".join(all_text).strip()
            detected_language = info.language or "en"

            # Calculate confidence from average log probability
            if segment_count > 0:
                avg_logprob = total_logprob / segment_count
                confidence = max(0, min(1, 1 + avg_logprob))
            else:
                confidence = 0.0

            logger.info(f"STT: [{detected_language}] {text[:80]}... (conf: {confidence:.2f})")

            return STTResult(
                text=text,
                language=detected_language,
                confidence=confidence
            )
        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return STTResult(
            text="",
            language="en",
            confidence=0.0
        )


async def transcribe_wav_file(file_path: str) -> STTResult:
    """Transcribe a WAV file (for testing/demo purposes)."""
    model = _load_whisper()

    if model is None:
        return STTResult(
            text="[Simulated — Whisper not loaded]",
            language="en",
            confidence=0.0
        )

    try:
        segments, info = model.transcribe(file_path, beam_size=5)
        text = " ".join(s.text for s in segments).strip()
        language = info.language or "en"

        return STTResult(text=text, language=language, confidence=0.8)
    except Exception as e:
        logger.error(f"WAV transcription error: {e}")
        return STTResult(text="", language="en", confidence=0.0)


# ─── Audio Utilities ─────────────────────────────────────────

def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw PCM bytes to WAV format (for saving/playback)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def is_speech_present(audio_bytes: bytes, threshold: float = 500.0) -> bool:
    """
    Simple voice activity detection — checks if audio has enough energy
    to likely contain speech. Prevents processing silence.
    """
    if len(audio_bytes) < 100:
        return False
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(audio_np ** 2))
    return rms > threshold
