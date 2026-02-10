"""
voice-mcp: Bidirectional voice MCP server for Claude Code.

Exposes two tools over stdio:
  - listen()  — record mic audio, transcribe with Voxtral Realtime
  - speak()   — synthesize text with Kokoro TTS, play through speakers
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import sounddevice as sd
import webrtcvad
from mcp.server.fastmcp import FastMCP

# ── Logging (stderr only — stdout is the MCP protocol channel) ───────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("voice-mcp")

# ── Lifespan: pre-load models at startup ─────────────────────────────────

@asynccontextmanager
async def lifespan(server: FastMCP):
    log.info("Pre-loading models…")
    get_stt_model()
    get_tts_model()
    log.info("Models ready — voice server is live.")
    yield


# ── FastMCP server ───────────────────────────────────────────────────────
mcp = FastMCP(
    "voice",
    lifespan=lifespan,
    instructions="""\
You have access to voice tools for talking with the user via microphone and speakers.

WHEN TO USE speak():
- Conversational responses, greetings, confirmations, and status updates
- Summarising what you did or what you found
- Asking the user clarifying questions
- Anything you'd naturally say out loud

WHEN NOT TO USE speak():
- Code, code snippets, diffs, or file contents — write these to the terminal as normal
- Structured data, tables, JSON, logs, or stack traces
- Long technical explanations — speak a brief summary, write the details
- File paths, URLs, or command invocations the user needs to copy

Keep spoken text short and natural. If a response has both conversational and
technical parts, speak the conversational part and write the technical part.

LANGUAGE SUPPORT:
- listen() understands: ar, de, en, es, fr, hi, it, nl, pt, zh, ja, ko, ru
- speak() supports: "a" American English, "b" British English, "e" Spanish,
  "f" French, "h" Hindi, "i" Italian, "j" Japanese, "p" Portuguese, "z" Mandarin
- When the user speaks a non-English language, respond in that language and set
  the speak() `lang` parameter to match. For languages listen() understands but
  speak() cannot produce (ar, de, nl, ko, ru), respond in the user's language
  via text and use speak() only for an English summary if helpful.
- IMPORTANT: When passing non-English text to speak(), always use the native
  script — e.g. Hindi in Devanagari (मैं अच्छा हूँ), Japanese in kana/kanji,
  Chinese in hanzi. Never pass romanized/transliterated text; the TTS engine
  needs native script for correct pronunciation.

VOICE SELECTION:
- The default voice is "af_heart" (American female).
- Users can change the voice with /voice. Remember their preference for the session.
""",
)

# ── Lazy-loaded model singletons ─────────────────────────────────────────
_stt_model = None
_tts_model = None

STT_MODEL_REPO = "mlx-community/Voxtral-Mini-4B-Realtime-2602-int4"
TTS_MODEL_REPO = "mlx-community/Kokoro-82M-bf16"

MIC_SAMPLE_RATE = 16_000  # Voxtral expects 16 kHz
SPEAKER_SAMPLE_RATE = 24_000  # Kokoro outputs 24 kHz
CHIME_SAMPLE_RATE = 44_100  # higher rate for cleaner tones


# ── Audio chimes ─────────────────────────────────────────────────────────

def _play_tone(freqs: list[float], duration: float = 0.12, volume: float = 0.3):
    """Play a short multi-frequency tone as an audio cue."""
    t = np.linspace(0, duration, int(CHIME_SAMPLE_RATE * duration), endpoint=False)
    # Blend frequencies and apply a smooth fade-in/out envelope
    tone = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    fade = np.minimum(t / 0.01, 1.0) * np.minimum((duration - t) / 0.01, 1.0)
    samples = (tone * fade * volume).astype(np.float32)
    sd.play(samples, samplerate=CHIME_SAMPLE_RATE)
    sd.wait()


def chime_listening():
    """Rising two-tone: 'start speaking'."""
    _play_tone([880, 1320], duration=0.1)


def chime_done():
    """Falling tone: 'got it, processing'."""
    _play_tone([660, 440], duration=0.1)


def get_stt_model():
    global _stt_model
    if _stt_model is None:
        log.info("Loading STT model: %s", STT_MODEL_REPO)
        from mlx_audio.stt import load
        _stt_model = load(STT_MODEL_REPO)
        log.info("STT model ready.")
    return _stt_model


def get_tts_model():
    global _tts_model
    if _tts_model is None:
        log.info("Loading TTS model: %s", TTS_MODEL_REPO)
        from mlx_audio.tts import load
        _tts_model = load(TTS_MODEL_REPO)
        log.info("TTS model ready.")
    return _tts_model


# ── Mic recording with VAD ───────────────────────────────────────────────

def record_until_silence(
    sample_rate: int = MIC_SAMPLE_RATE,
    frame_duration_ms: int = 30,
    vad_mode: int = 3,
    silence_duration: float = 1.5,
) -> np.ndarray:
    """Record from the microphone until speech ends (VAD-based).

    Returns float32 audio array normalised to [-1, 1].
    """
    vad = webrtcvad.Vad(vad_mode)
    frame_size = int(sample_rate * frame_duration_ms / 1000)  # samples per frame
    frames_until_silence = int(silence_duration * 1000 / frame_duration_ms)

    frames: list[bytes] = []
    silent_frames = 0
    speaking_detected = False

    log.info("Listening… (speak now)")
    chime_listening()

    with sd.InputStream(
        samplerate=sample_rate,
        blocksize=frame_size,
        channels=1,
        dtype="int16",
    ) as stream:
        while True:
            data, _overflowed = stream.read(frame_size)
            frame_bytes = data.tobytes()

            try:
                is_speech = vad.is_speech(frame_bytes, sample_rate)
            except ValueError:
                # Fallback: energy-based detection
                audio_f32 = data.flatten().astype(np.float32) / 32768.0
                energy = np.linalg.norm(audio_f32) / np.sqrt(audio_f32.size)
                is_speech = energy > 0.03

            if is_speech:
                speaking_detected = True
                silent_frames = 0
                frames.append(frame_bytes)
            elif speaking_detected:
                silent_frames += 1
                frames.append(frame_bytes)
                if silent_frames >= frames_until_silence:
                    break

    chime_done()
    log.info("Recording complete — %d frames captured.", len(frames))
    pcm = np.frombuffer(b"".join(frames), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def record_fixed_duration(duration: float) -> np.ndarray:
    """Record from the microphone for a fixed number of seconds."""
    log.info("Recording for %.1fs…", duration)
    chime_listening()
    samples = int(MIC_SAMPLE_RATE * duration)
    audio = sd.rec(samples, samplerate=MIC_SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    chime_done()
    return audio.flatten().astype(np.float32) / 32768.0


# ── MCP Tools ────────────────────────────────────────────────────────────

@mcp.tool()
def listen(duration: Optional[float] = None) -> str:
    """Listen to the user via the microphone and return a transcription.

    By default, uses voice-activity detection to automatically stop recording
    when the user stops speaking. Pass `duration` (seconds) to record for a
    fixed length instead.
    """
    import mlx.core as mx

    if duration is not None and duration > 0:
        audio = record_fixed_duration(duration)
    else:
        audio = record_until_silence()

    if len(audio) == 0:
        return "(no speech detected)"

    model = get_stt_model()
    result = model.generate(mx.array(audio))
    text = result.text.strip()
    log.info("Transcribed: %s", text)
    return text if text else "(no speech detected)"


@mcp.tool()
def speak(text: str, voice: str = "af_heart", speed: float = 1.0, lang: str = "a") -> str:
    """Speak the given text aloud through the computer's speakers.

    Only use this for natural conversational speech — short confirmations,
    summaries, or questions. Never pass code, file contents, structured data,
    or long technical explanations through this tool; write those to the
    terminal instead.

    Args:
        text:  The text to speak (conversational, not code).
        voice: Kokoro voice ID (default: af_heart).
        speed: Playback speed multiplier (default: 1.0).
        lang:  Language code — "a" American English, "b" British English,
               "e" Spanish, "f" French, "h" Hindi, "i" Italian,
               "j" Japanese, "p" Portuguese, "z" Mandarin Chinese.
               Match this to the language of the text being spoken.
    """
    import os
    from mlx_audio.tts.audio_player import AudioPlayer

    model = get_tts_model()
    player = AudioPlayer(sample_rate=SPEAKER_SAMPLE_RATE)

    # AudioPlayer.start_stream() calls print() which would corrupt the MCP
    # stdio channel. Redirect stdout to devnull during playback.
    real_stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        for segment in model.generate(text=text, voice=voice, speed=speed, lang_code=lang):
            audio = np.array(segment.audio)
            player.queue_audio(audio)

        player.stop()
    finally:
        sys.stdout.close()
        sys.stdout = real_stdout
    log.info("Spoke: %s", text)
    return f"Spoke: {text}"


# ── Entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
