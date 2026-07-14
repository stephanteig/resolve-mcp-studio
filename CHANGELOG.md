# Changelog

All notable changes to resolve-mcp-studio are documented here.

---

## [Unreleased]

### Added

#### Audio Visualizer image generator — `server.py`

New tool `generate_audio_visualizer_image` that converts the current timeline's audio into a multi-band waveform PNG and imports it into a Media Pool subfolder, ready for use with the [sh4rk Audio Visualiser](https://sh4rkk.com/shop) Fusion plugin.

**How it works:**
1. Exports the timeline's audio to WAV using Resolve's built-in "Audio Only" render preset
2. Splits the audio into frequency bands using FFmpeg bandpass filters
3. Converts each band to a 1-pixel-tall waveform strip via NumPy normalization
4. Stacks bands into a single PNG (one row per band) using Pillow
5. Creates an "Audio Visualizer" subfolder in the Media Pool root (if it doesn't exist) and imports the PNG

**Parameters:**
- `preset` — frequency band mode: `1band`, `3band` (Low/Mid/High RGB), `10band`, `25band`, `100band`
- `target_width` — image width in pixels; `0` = auto (1 px per frame, capped at 32 000 px)
- `bin_name` — Media Pool subfolder name (default: `"Audio Visualizer"`)

**Dependencies added:** `Pillow>=10.0.0` (added to `pyproject.toml`); `ffmpeg` on PATH (install separately).

**Known issue:** The tool returns `'NoneType' object is not callable` when called directly via the MCP tool interface due to a FastMCP decorator compatibility issue. The underlying code works correctly — call it via `execute_resolve_code` as a workaround (see README).

---

### Fixed

#### Memory management — `transcription.py`

Free MLX GPU cache after transcription completes.

Previously, Whisper model weights (~2 GB) were loaded into Apple Silicon unified memory and held for the lifetime of the server process. Memory is now released as soon as each transcription job finishes.

- Added `gc` import
- Added `_free_mlx_cache()` helper that calls `mx.metal.clear_cache()` followed by `gc.collect()`
- Both the short-file and chunked code paths call `_free_mlx_cache()` in a `finally` block — cleanup runs regardless of whether transcription succeeds or fails
- Server process idle memory footprint drops from ~2.7 GB to ~83 MB between jobs
- **Trade-off:** the model reloads on the next transcription call (~5–10 seconds) instead of being instantly available from cache

---

## Earlier changes

This project is a fork of [barckley75/resolve-claude-mcp](https://github.com/barckley75/resolve-claude-mcp). For history prior to this fork, see the upstream repository.
