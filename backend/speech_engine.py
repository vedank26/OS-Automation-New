import os
import tempfile
from threading import Event, Lock
from typing import Optional

try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from scipy.io import wavfile
    from scipy.signal import butter, filtfilt
except Exception as import_error:
    np = None
    sd = None
    WhisperModel = None
    wavfile = None
    butter = None
    filtfilt = None
    _IMPORT_ERROR: Optional[Exception] = import_error
else:
    _IMPORT_ERROR = None

try:
    import noisereduce as nr
    _HAS_NR = True
except ImportError:
    _HAS_NR = False
    nr = None

# Hinglish support libraries
try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    _HAS_INDIC = True
except ImportError:
    _HAS_INDIC = False
    transliterate = None


SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 0.1
SILENCE_SECONDS = 2.5
INITIAL_SILENCE_SECONDS = 10.0
MAX_RECORD_SECONDS = 120.0
ENERGY_THRESHOLD = 0.006
START_SPEECH_CHUNKS = 1
MAX_NO_SPEECH_PROBABILITY = 0.75

# ── HINGLISH CONFIG ────────────────────────────────────────
ENABLE_HINGLISH = True
HINGLISH_CONFIDENCE_THRESHOLD = 0.35  # Accept lower confidence for Hinglish
WHISPER_MODEL_SIZE = "base"  # "base" / "small" / "medium"
# ─────────────────────────────────────────────────────────────

_model = None
_model_lock = Lock()
_model_load_attempted = False
_listen_lock = Lock()
_stop_listening = Event()


def _log(message: str) -> None:
    print(f"[speech] {message}")


def _get_model():
    global _model, _model_load_attempted

    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        if _model_load_attempted:
            _log("Faster-Whisper model is unavailable from the first load attempt")
            return None

        _model_load_attempted = True

        if WhisperModel is None:
            _log(f"Voice dependencies unavailable: {_IMPORT_ERROR}")
            return None

        try:
            _log(f"Loading Faster-Whisper model '{WHISPER_MODEL_SIZE}' on CPU (int8)")
            model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",
            )
            _model = model
            _log("Faster-Whisper model ready")
            return _model
        except Exception as exc:
            _log(f"Could not load Faster-Whisper model: {exc}")
            return None


def _is_voice_chunk(audio_chunk) -> bool:
    rms = float(np.sqrt(np.mean(np.square(audio_chunk), dtype=np.float64)))
    return rms >= ENERGY_THRESHOLD


def _is_english_command_text(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    return ascii_chars / max(len(text), 1) >= 0.95


def _has_devanagari(text: str) -> bool:
    """Check if text contains Devanagari (Hindi) script."""
    devanagari_range = range(0x0900, 0x097F)
    return any(ord(char) in devanagari_range for char in text)


def _is_hinglish(text: str) -> bool:
    """Detect if text is Hinglish (mix of English + Devanagari)."""
    if not text:
        return False
    has_devanagari = _has_devanagari(text)
    has_english = any(char.isascii() and char.isalpha() for char in text)
    return has_devanagari or has_english


def _transliterate_hinglish(text: str) -> str:
    """
    Try to transliterate Devanagari to Roman (IAST/HK for phonetic recognition).
    Falls back to original if indic_transliteration not installed.
    """
    if not _HAS_INDIC or transliterate is None:
        return text
    
    if not _has_devanagari(text):
        return text

    try:
        # Transliterate Devanagari → IAST (Roman) for better Whisper matching
        transliterated = transliterate(
            text,
            sanscript.DEVANAGARI,
            sanscript.IAST,
        )
        _log(f"Transliterated: {text} → {transliterated}")
        return transliterated
    except Exception as exc:
        _log(f"Transliteration failed: {exc} — using original")
        return text


def _segments_are_confident(segments: list, is_hinglish: bool = False) -> bool:
    """
    Check confidence. Hinglish gets lower threshold since Whisper is less trained on it.
    """
    speech_segments = [
        segment for segment in segments
        if segment.text and segment.text.strip()
    ]
    if not speech_segments:
        return False

    # Relax confidence threshold for Hinglish
    threshold = HINGLISH_CONFIDENCE_THRESHOLD if is_hinglish else MAX_NO_SPEECH_PROBABILITY

    high_no_speech_segments = [
        segment for segment in speech_segments
        if getattr(segment, "no_speech_prob", 0.0) > threshold
    ]
    return len(high_no_speech_segments) < len(speech_segments)


# ── Noise cancellation ────────────────────────────────────────

def _highpass_filter(audio: np.ndarray, cutoff_hz: int = 80) -> np.ndarray:
    """Remove low-frequency rumble."""
    if butter is None or filtfilt is None:
        return audio
    try:
        nyquist = SAMPLE_RATE / 2.0
        normal_cutoff = cutoff_hz / nyquist
        if normal_cutoff >= 1.0:
            return audio
        b, a = butter(4, normal_cutoff, btype="high", analog=False)
        return filtfilt(b, a, audio).astype(np.float32)
    except Exception as exc:
        _log(f"High-pass filter skipped: {exc}")
        return audio


def _spectral_denoise(audio: np.ndarray) -> np.ndarray:
    """Spectral subtraction via noisereduce."""
    if not _HAS_NR or nr is None:
        return audio
    try:
        noise_sample_len = min(int(0.5 * SAMPLE_RATE), len(audio))
        reduced = nr.reduce_noise(
            y=audio,
            sr=SAMPLE_RATE,
            y_noise=audio[:noise_sample_len],
            stationary=True,
            prop_decrease=0.75,
        )
        _log("Noise reduction applied")
        return reduced.astype(np.float32)
    except Exception as exc:
        _log(f"Noise reduction skipped: {exc}")
        return audio


def _normalize(audio: np.ndarray) -> np.ndarray:
    """Peak-normalize."""
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    return (audio / peak).astype(np.float32)


def _clean_audio(audio: np.ndarray) -> np.ndarray:
    """Full pipeline: high-pass → spectral denoise → normalize."""
    audio = _highpass_filter(audio)
    audio = _spectral_denoise(audio)
    audio = _normalize(audio)
    return audio

# ─────────────────────────────────────────────────────────────


def _record_until_silence() -> str:
    if np is None or sd is None or wavfile is None:
        raise RuntimeError(f"Voice dependencies unavailable: {_IMPORT_ERROR}")

    blocksize = int(SAMPLE_RATE * CHUNK_SECONDS)
    max_chunks = int(MAX_RECORD_SECONDS / CHUNK_SECONDS)
    initial_silence_chunks = int(INITIAL_SILENCE_SECONDS / CHUNK_SECONDS)
    silence_limit_chunks = int(SILENCE_SECONDS / CHUNK_SECONDS)

    chunks = []
    speech_started = False
    voice_streak = 0
    silent_chunks = 0

    _stop_listening.clear()
    _log("Listening with silence detection")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=blocksize,
    ) as stream:
        for chunk_index in range(max_chunks):
            if _stop_listening.is_set():
                _log("Listening stopped by user")
                break

            audio_chunk, _overflowed = stream.read(blocksize)
            mono_chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
            has_voice = _is_voice_chunk(mono_chunk)

            if has_voice:
                voice_streak += 1
                silent_chunks = 0
            else:
                silent_chunks += 1
                voice_streak = 0

            if not speech_started:
                if has_voice:
                    chunks.append(mono_chunk.copy())
                if voice_streak >= START_SPEECH_CHUNKS:
                    speech_started = True
                    _log("Speech detected")
                elif chunk_index >= initial_silence_chunks:
                    _log("Initial silence timeout")
                    break
                continue

            chunks.append(mono_chunk.copy())

            if silent_chunks >= silence_limit_chunks:
                _log(f"Silence detected for {SILENCE_SECONDS:.1f}s")
                break
        else:
            _log("Emergency recording limit reached")

    if not chunks or not speech_started:
        return ""

    audio = np.concatenate(chunks)
    audio = np.clip(audio, -1.0, 1.0)

    # Apply noise cancellation
    audio = _clean_audio(audio)

    audio_pcm = (audio * 32767).astype(np.int16)

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        prefix="flowforge_voice_",
        delete=False,
    )
    temp_path = temp_file.name
    temp_file.close()

    wavfile.write(temp_path, SAMPLE_RATE, audio_pcm)
    return temp_path


def listen_once() -> str:
    """
    Record audio, transcribe with Whisper.
    Detects Hinglish and applies language-specific handling.
    """
    temp_path = ""

    try:
        model = _get_model()
        if model is None:
            return ""

        temp_path = _record_until_silence()
        if not temp_path:
            return ""

        _log("Processing speech")
        
        # Transcribe with language detection
        segments, info = model.transcribe(
            temp_path,
            language=None,  # Let Whisper auto-detect (supports ~99 langs)
            beam_size=8,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        segments = list(segments)
        detected_lang = getattr(info, "language", "unknown")
        _log(f"Detected language: {detected_lang}")

        # Check if Hinglish or mixed language
        raw_text = " ".join(segment.text.strip() for segment in segments).strip()
        is_hinglish_detected = _is_hinglish(raw_text)

        if is_hinglish_detected and ENABLE_HINGLISH:
            _log("Hinglish detected → using relaxed confidence threshold")
        
        # Use relaxed confidence for Hinglish
        if not _segments_are_confident(segments, is_hinglish=is_hinglish_detected):
            _log("Rejected low-confidence speech")
            return ""

        clean_text = " ".join(raw_text.split())

        # For Hinglish: keep Devanagari but optionally transliterate
        if is_hinglish_detected and ENABLE_HINGLISH:
            # Transliterate Devanagari to help with command matching
            transliterated = _transliterate_hinglish(clean_text)
            
            # Log both versions
            _log(f"Original Hinglish: {clean_text}")
            _log(f"Transliterated: {transliterated}")
            
            # Return transliterated version (phonetically matches English better)
            if clean_text:
                return transliterated
        
        # English path: strict validation
        if not is_hinglish_detected:
            if not _is_english_command_text(clean_text):
                _log(f"Rejected non-English transcription: {clean_text}")
                return ""

        if clean_text:
            _log(f"Recognized: {clean_text}")
        else:
            _log("No speech recognized")

        return clean_text
        
    except Exception as exc:
        _log(f"Voice recognition failed: {exc}")
        return ""
    finally:
        _stop_listening.clear()
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError as exc:
                _log(f"Could not remove temp audio file: {exc}")


def listen_once_result() -> dict[str, str]:
    if not _listen_lock.acquire(blocking=False):
        _log("Listen request rejected: already listening")
        return {"text": "", "status": "already_listening"}

    try:
        text = listen_once()
        return {
            "text": text or "",
            "status": "ok" if text else "no_speech",
        }
    finally:
        _listen_lock.release()


def stop_listening() -> None:
    _stop_listening.set()


def listen() -> str:
    """Backward-compatible wrapper."""
    return listen_once()


def listen_short() -> str:
    """Backward-compatible wrapper."""
    return listen_once()