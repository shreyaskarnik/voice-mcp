# voice-mcp

Bidirectional voice MCP server for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Adds `listen()` and `speak()` tools so Claude can hear you and talk back — all running locally on Apple Silicon via [mlx-audio](https://github.com/Blaizzy/mlx-audio).

```
User speaks → listen() → mic + VAD → Voxtral Realtime STT → text to Claude
Claude responds → speak(text) → Kokoro TTS → AudioPlayer → speakers
```

## Requirements

- macOS with Apple Silicon (M1+)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A working microphone and speakers

## Setup

```bash
git clone <this-repo> && cd voice-mcp
uv sync
```

First run downloads the models from HuggingFace (~2.5 GB total):
- **STT**: `mlx-community/Voxtral-Mini-4B-Realtime-2602-int4` (Voxtral Realtime, 4-bit quantized)
- **TTS**: `mlx-community/Kokoro-82M-bf16` (Kokoro, 82M params)

### Configure Claude Code

The repo includes `.mcp.json` so Claude Code auto-discovers the server. Just open Claude Code from the project directory:

```bash
cd voice-mcp
claude
```

On first use, Claude Code will prompt you to approve the MCP server.

To use from a **different project**, add to that project's `.mcp.json`:

```json
{
  "mcpServers": {
    "voice": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/path/to/voice-mcp", "run", "server.py"]
    }
  }
}
```

## Usage

### Voice input
Tell Claude "listen to me" or use the `/listen` slash command. You'll hear a rising chime when the mic is active — speak naturally, and recording stops automatically after 1.5s of silence (falling chime).

### Voice output
Claude will speak conversational responses automatically. Code, data, and technical details stay in the terminal.

### Change voice
Use `/voice` to browse all 54 available voices across 9 languages, or `/voice am_echo` to switch directly.

## Tools

### `listen(duration?)`
Records audio from the microphone and returns a transcription.
- **Default**: VAD-based — waits for speech, stops after silence
- **With `duration`**: fixed-length recording (seconds)
- **STT languages**: ar, de, en, es, fr, hi, it, ja, ko, nl, pt, ru, zh

### `speak(text, voice?, speed?, lang?)`
Speaks text aloud through the computer's speakers.
- **voice**: Kokoro voice ID (default: `af_heart`). See `/voice` for options
- **speed**: playback speed multiplier (default: 1.0)
- **lang**: language code — `a` American English, `b` British English, `e` Spanish, `f` French, `h` Hindi, `i` Italian, `j` Japanese, `p` Portuguese, `z` Mandarin

## How it works

The server runs as a stdio subprocess managed by Claude Code. Audio I/O (mic + speakers) happens in the server process; only text crosses the MCP protocol.

- **STT**: Voxtral Realtime (4B params, int4) — streams audio through a causal encoder-decoder with adaptive RMS normalization
- **TTS**: Kokoro (82M params, bf16) — ALBERT text encoder → prosody predictor → iSTFTNet vocoder
- **VAD**: webrtcvad (mode 3) with energy-based fallback
- **Audio cues**: synthesized tones via sounddevice — rising chime = listening, falling chime = done
- **Notifications**: macOS banners via hooks when listening starts/stops and when speaking

Models are pre-loaded at server startup via FastMCP's lifespan hook, so the first tool call is fast.
