# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

voice-mcp is a bidirectional voice MCP server for Claude Code (and other MCP-compatible agents). It exposes two tools — `listen()` (STT) and `speak()` (TTS) — that run locally on Apple Silicon via mlx-audio. The entire server is a single file: `server.py`.

## Commands

```bash
uv sync              # Install dependencies
uv run server.py     # Start the MCP server (stdio transport)
```

There is no test suite, linter, or build step.

## Architecture

**Single-file server** (`server.py`, ~273 lines) built on FastMCP (from the `mcp` SDK). Communicates over stdio — stdout is the MCP JSON-RPC channel, so all logging goes to stderr.

Key components:
- **Lifespan hook** — pre-loads STT and TTS models at startup so first tool call is fast
- **Lazy singletons** — `get_stt_model()` / `get_tts_model()` load models once from HuggingFace MLX Community repos
- **VAD recording** — `record_until_silence()` uses webrtcvad (mode 3) with energy-based fallback; stops after 1.5s of silence
- **Audio cues** — `chime_listening()` / `chime_done()` synthesize short tones via numpy+sounddevice to signal mic state
- **TTS playback** — `speak()` redirects stdout to /dev/null during playback because mlx-audio's AudioPlayer prints to stdout, which would corrupt the MCP stdio channel

**Models:**
- STT: `mlx-community/Voxtral-Mini-4B-Realtime-2602-int4` (16 kHz input)
- TTS: `mlx-community/Kokoro-82M-bf16` (24 kHz output, 54 voices across 9 languages)

**Hooks** (`.claude/settings.json` + `.claude/hooks/notify.sh`):
- PreToolUse on `mcp__voice__listen` — shows macOS notification and forces permission prompt for mic access
- PreToolUse on `mcp__voice__speak` — shows notification with text preview
- PostToolUse on `mcp__voice__listen` — shows notification with transcription result

## Important Constraints

- **stdout is sacred**: Never print to stdout in server code. All logging must use `log.*()` (configured to stderr). The `speak()` function's stdout redirect pattern exists for this reason.
- **macOS + Apple Silicon only**: mlx-audio requires Metal (Apple GPU). No CPU/CUDA fallback.
- **mlx-audio installed from git main**: The `mlx-audio` dependency is pinned to the GitHub main branch, not PyPI.
