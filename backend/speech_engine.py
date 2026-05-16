import os
import tempfile
from threading import Event, Lock
from typing import Optional

try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from scipy.io import wavfile
except Exception as import_error:  # pragma: no cover - runtime dependency guard
    np = None
    sd = None
    WhisperModel = None
    wavfile = None
    _IMPORT_ERROR: Optional[Exception] = import_error
else:
    _IMPORT_ERROR = None


SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 0.1
SILENCE_SECONDS = 2.0
INITIAL_SILENCE_SECONDS = 10.0
MAX_RECORD_SECONDS = 120.0
ENERGY_THRESHOLD = 0.012
START_SPEECH_CHUNKS = 2
MAX_NO_SPEECH_PROBABILITY = 0.65

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
            _log("Loading Faster-Whisper model 'base' on CPU (int8)")
            model = WhisperModel(
                "base",
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


def _segments_are_confident(segments: list) -> bool:
    speech_segments = [
        segment for segment in segments
        if segment.text and segment.text.strip()
    ]
    if not speech_segments:
        return False

    high_no_speech_segments = [
        segment for segment in speech_segments
        if getattr(segment, "no_speech_prob", 0.0) > MAX_NO_SPEECH_PROBABILITY
    ]
    return len(high_no_speech_segments) < len(speech_segments)


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
    Record microphone audio until speech ends, then return transcribed text.

    The normal stop condition is silence after speech, not a fixed duration.
    All failures return an empty string so FastAPI never crashes.
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
        segments, _info = model.transcribe(
            temp_path,
            language="en",
            beam_size=5,
            vad_filter=True,
        )
        segments = list(segments)
        if not _segments_are_confident(segments):
            _log("Rejected low-confidence speech")
            return ""

        text = " ".join(segment.text.strip() for segment in segments).strip()
        clean_text = " ".join(text.split())

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
    """Backward-compatible wrapper for older local voice scripts."""
    return listen_once()


def listen_short() -> str:
    """Backward-compatible wrapper for older local selection listening."""
    return listen_once()
