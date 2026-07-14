# resolve-mcp-studio

Connect **DaVinci Resolve Studio** to **Claude AI** through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), enabling AI-assisted video editing, color grading, Fusion compositing, transcription, and more — all through natural language.

> This repo (`stephanteig/resolve-mcp-studio`) is a fork of [barckley75/resolve-claude-mcp](https://github.com/barckley75/resolve-claude-mcp) extended with **studio workflow tools**: a marker parser/editor, timeline transcription with subtitle track management, project templates, Media Pool ↔ Finder sync, auto clip coloring, and an optional browser panel. See [Studio Extensions](#studio-extensions-this-fork).

> **Note:** This is a third-party integration and is not created by or affiliated with Blackmagic Design or Anthropic.
>
> ⚠️ **Use with caution.** AI-assisted tools can modify or delete project data — always work on backups and keep versioned copies of important projects. This toolset is used on real productions daily, but review every automated change before relying on it.

> **Platform support:** Tested only on **macOS** (Apple Silicon). The Blackmagic scripting API is cross-platform, so the core Resolve-control tools may work on Windows and Linux as well, but this is unverified. Local transcription tools and the `screenshot` tool are **macOS-only** (they rely on `mlx-whisper` and macOS-specific screen-capture APIs).

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [MCP Tools Reference](#mcp-tools-reference)
  - [Project & Navigation](#project--navigation)
  - [Media Pool](#media-pool)
  - [Timeline Operations](#timeline-operations)
  - [Markers](#markers)
  - [Timeline Item Properties](#timeline-item-properties)
  - [Color Grading](#color-grading)
  - [Rendering](#rendering)
  - [AI / Neural Engine](#ai--neural-engine-studio-only)
  - [Audio](#audio)
  - [Fusion (Compositing / VFX)](#fusion-compositing--vfx)
  - [Timeline Export](#timeline-export)
  - [Thumbnail & Screenshot](#thumbnail--screenshot)
  - [Local Transcription](#local-transcription-macos--apple-silicon-only)
  - [Studio Extensions: Markers](#studio-extensions-markers)
  - [Studio Extensions: Subtitle Tracks](#studio-extensions-subtitle-tracks)
  - [Studio Extensions: Project Templates](#studio-extensions-project-templates)
  - [Studio Extensions: Media Pool Sync](#studio-extensions-media-pool-sync)
  - [Studio Extensions: Auto Clip Color](#studio-extensions-auto-clip-color)
  - [Code Execution](#code-execution)
- [Module Reference](#module-reference)
  - [markers.py](#markerspy)
  - [transcription.py](#transcriptionpy)
  - [templates.py](#templatespy)
  - [media_pool.py](#media_poolpy)
  - [connection.py](#connectionpy)
  - [resolve_utils.py](#resolve_utilspy)
  - [clip_colors.py](#clip_colorspy)
  - [panel_server.py](#panel_serverpy)
- [Browser Panel](#browser-panel)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Disclaimer](#disclaimer)
- [Credits](#credits)

---

## Features

### Core
- Direct connection to DaVinci Resolve Studio's scripting API — no addon or plugin needed inside Resolve
- Project inspection and navigation across all pages (Media, Cut, Edit, Fusion, Color, Fairlight, Deliver)
- Media pool management (import, organize, browse)
- Timeline creation and editing
- Arbitrary Python code execution with the full Resolve API

### Color Grading
- Node graph inspection and manipulation
- LUT application
- CDL (Color Decision List) adjustments

### Fusion (Compositing / VFX)
- Create, import, export, and manage Fusion compositions
- Insert Fusion generators, titles, and blank compositions
- Merge timeline items into Fusion clips

### AI / DaVinci Neural Engine (Resolve Studio 19+)
- **Magic Mask** — AI-powered subject isolation
- **Smart Reframe** — automatic reframing for different aspect ratios
- **Stabilization** — AI-powered clip stabilization
- **Scene Cut Detection** — auto-detect and cut at scene boundaries
- **Subtitle Generation** — AI speech-to-text with multi-language support
- **Voice Isolation** — separate speech from background noise

### Local Transcription (macOS / Apple Silicon only)
- **mlx-whisper** transcription running locally on your Mac's Neural Engine / GPU
- Auto-chunks long files with ffmpeg (5-min pieces) — no timeouts on hour-long clips
- Returns compact timestamped transcript inline for immediate use
- Saves SRT file next to source for Resolve subtitle import
- Six model sizes: tiny (fastest) → turbo (default) → large (most accurate)

### Studio Extensions (this fork)
- **Marker parser & editor** — paste a free-text list of timecodes and descriptions; get color-coded markers with a preview/confirm step before writing
- **Timeline transcription** — render the timeline's audio and transcribe locally with mlx-whisper; write as new subtitle track or *correct* an existing track's text without touching timing
- **Project templates** — create projects with predefined structure (resolution, fps, bins, timelines) from JSON configs, or from imported `.drp` files
- **Media Pool ↔ Finder sync** — mirror a Finder folder tree as bins and import each folder's media; idempotent re-runs pick up new files without duplicates
- **Auto clip color** — categorize and color-code clips in the Media Pool or timeline by filename/metadata (drone, talking head, B-roll, music, graphics)
- **Audio Visualizer image generator** — export the current timeline's audio and convert it to a multi-band waveform image ready for the [sh4rk Audio Visualiser](https://sh4rkk.com/shop) Fusion plugin; result is auto-imported into a Media Pool bin
- **Browser panel** — compact dark-themed panel (status, marker editor, transcription) served by a local HTTP bridge

---

## Architecture

Unlike BlenderMCP which requires a socket-based addon, resolve-mcp-studio connects directly to DaVinci Resolve via its native scripting API. This is a single-process architecture:

```
Claude AI (MCP Client)
    │
    ▼
resolve-mcp-studio  (FastMCP over stdio)
    │
    ├── markers.py          Timecode parsing, color assignment
    ├── transcription.py    mlx-whisper, chunking, subtitle track I/O
    ├── templates.py        JSON-based project template system
    ├── media_pool.py       Finder ↔ Media Pool bin/file sync
    ├── clip_colors.py      Filename/metadata → clip color categories
    ├── resolve_utils.py    Resolve API object → JSON serialization
    └── connection.py       ResolveConnection singleton
         │
         ▼
    DaVinciResolveScript  (fusionscript.so / .dll)
         │
         ▼
    DaVinci Resolve Studio (running locally)

Optional: panel_server.py  (localhost HTTP bridge on port 8765)
    │
    ▼
panel/index.html  (browser-based panel UI)
```

No addon to install inside Resolve. No socket server. The MCP server speaks stdio with Claude Desktop; the panel bridge is a separate optional process.

---

## Prerequisites

- **DaVinci Resolve Studio** 18.0+ (free version has limited scripting support)
- **Python** 3.10+
- **uv** package manager
- **ffmpeg** (required for Audio Visualizer and local transcription features)

Install uv:

```bash
# macOS
brew install uv

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install ffmpeg:

```bash
# macOS
brew install ffmpeg

# Windows (via winget)
winget install ffmpeg

# Linux
sudo apt install ffmpeg   # Debian/Ubuntu
sudo dnf install ffmpeg   # Fedora
```

---

## Installation

### Step 1: Clone this repo

```bash
git clone https://github.com/stephanteig/resolve-mcp-studio.git
cd resolve-mcp-studio
uv sync
```

Note the **absolute path** to the cloned folder — you'll need it in Step 2.

### Step 2: Configure Claude Desktop

Claude Desktop reads `claude_desktop_config.json` at startup. Add an entry so it knows about this server.

**File location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "resolve": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/resolve-mcp-studio",
        "run",
        "resolve-claude-mcp"
      ],
      "env": {
        "RESOLVE_SCRIPT_LIB": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
        "RESOLVE_SCRIPT_API": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
        "PYTHONPATH": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
      }
    }
  }
}
```

> If `uv` isn't on Claude Desktop's `PATH`, use the full path — find it with `which uv` (macOS/Linux). On macOS via Homebrew it's typically `/opt/homebrew/bin/uv`.

<details>
<summary>Windows environment variables</summary>

```json
{
  "mcpServers": {
    "resolve": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\resolve-mcp-studio", "run", "resolve-claude-mcp"],
      "env": {
        "RESOLVE_SCRIPT_LIB": "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll",
        "RESOLVE_SCRIPT_API": "C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting",
        "PYTHONPATH": "C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules\\"
      }
    }
  }
}
```

</details>

<details>
<summary>Linux environment variables</summary>

```json
{
  "mcpServers": {
    "resolve": {
      "command": "uv",
      "args": ["--directory", "/path/to/resolve-mcp-studio", "run", "resolve-claude-mcp"],
      "env": {
        "RESOLVE_SCRIPT_LIB": "/opt/resolve/libs/Fusion/fusionscript.so",
        "RESOLVE_SCRIPT_API": "/opt/resolve/Developer/Scripting",
        "PYTHONPATH": "/opt/resolve/Developer/Scripting/Modules/"
      }
    }
  }
}
```

</details>

### Step 3: Enable scripting in Resolve

1. Open DaVinci Resolve Studio
2. Go to **Preferences → General**
3. Under **External scripting using**, select **Local**

### Step 4: Restart Claude Desktop

Quit and reopen the Claude Desktop app. You should see resolve-mcp-studio tools available (hammer icon).

---

## MCP Tools Reference

All tools return JSON strings unless stated otherwise. Parameters shown with their types and defaults.

---

### Project & Navigation

| Tool | Returns | Description |
|------|---------|-------------|
| `get_project_info()` | `string` (JSON) | Returns project name, Resolve version, current page, timeline count, frame rate, resolution, and playback frame rate. |
| `open_page(page)` | `string` | Switches to the specified page. |
| `get_current_page()` | `string` | Returns the name of the currently active page. |

#### `open_page`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | `string` | required | One of: `"media"`, `"cut"`, `"edit"`, `"fusion"`, `"color"`, `"fairlight"`, `"deliver"` |

---

### Media Pool

| Tool | Returns | Description |
|------|---------|-------------|
| `get_media_pool_structure(max_depth, max_clips)` | `string` (JSON) | Returns the bin/clip hierarchy of the Media Pool. |
| `import_media(file_paths)` | `string` (JSON) | Imports files into the current Media Pool folder. Returns count and names of imported clips. |
| `create_timeline(name)` | `string` (JSON) | Creates a new empty timeline in the current project. Returns timeline name, frame rate, and resolution. |

#### `get_media_pool_structure`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_depth` | `int` | `3` | Maximum recursion depth for bin traversal. |
| `max_clips` | `int` | `50` | Maximum clips to return per folder. |

#### `import_media`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_paths` | `list[string]` | required | Absolute paths to files to import. Imports into the currently selected Media Pool folder. |

---

### Timeline Operations

| Tool | Returns | Description |
|------|---------|-------------|
| `get_current_timeline_info()` | `string` (JSON) | Returns name, frame rate, resolution, start/end timecode, track counts, and markers for the current timeline. |
| `get_timeline_items(track_type, track_index)` | `string` (JSON) | Lists all items on a given track with their 0-based index, name, start/end frames, duration, and clip properties. |
| `append_to_timeline(clip_names)` | `string` (JSON) | Appends named clips from the Media Pool to the end of the current timeline. |
| `set_current_timecode(timecode)` | `string` | Moves the playhead to the given timecode. |
| `get_current_timecode()` | `string` | Returns the current playhead position as `HH:MM:SS:FF`. |

#### `get_timeline_items`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_type` | `string` | `"video"` | One of: `"video"`, `"audio"`, `"subtitle"` |
| `track_index` | `int` | `1` | 1-based track number. |

#### `append_to_timeline`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `clip_names` | `list[string]` | required | Names of Media Pool clips to append. Returns which names were not found. |

#### `set_current_timecode`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timecode` | `string` | required | Target position in `HH:MM:SS:FF` format. |

---

### Markers

| Tool | Returns | Description |
|------|---------|-------------|
| `add_marker(frame_id, color, name, note, duration, custom_data)` | `string` | Adds a single marker to the current timeline at the given frame. |
| `get_markers()` | `string` (JSON) | Returns all markers on the current timeline as a list of `{frame, color, name, note, duration}`. |

#### `add_marker`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frame_id` | `int` | required | Absolute frame number for the marker position. |
| `color` | `string` | required | Marker color. Valid values: `Red`, `Orange`, `Yellow`, `Green`, `Cyan`, `Blue`, `Purple`, `Pink`, `Fuchsia`, `Rose`, `Lavender`, `Sky`, `Mint`, `Lemon`, `Sand`, `Cocoa`, `Cream` |
| `name` | `string` | required | Short label displayed on the marker. |
| `note` | `string` | `""` | Extended note text (visible in marker inspector). |
| `duration` | `int` | `1` | Duration in frames (1 = single-frame marker). |
| `custom_data` | `string` | `""` | Arbitrary metadata string stored in the marker. |

---

### Timeline Item Properties

| Tool | Returns | Description |
|------|---------|-------------|
| `get_timeline_item_properties(track_type, track_index, item_index)` | `string` (JSON) | Returns all properties of a specific timeline item. |
| `set_timeline_item_property(property_key, property_value, track_type, track_index, item_index)` | `string` | Sets a single property on a timeline item. Values are auto-converted (float→int where needed, booleans parsed). |

Both tools share the same item-addressing parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_type` | `string` | `"video"` | One of: `"video"`, `"audio"`, `"subtitle"` |
| `track_index` | `int` | `1` | 1-based track number. |
| `item_index` | `int` | `0` | 0-based index within the track (from `get_timeline_items`). |

Common property keys for `set_timeline_item_property`: `Pan`, `Tilt`, `ZoomX`, `ZoomY`, `Opacity`, `CropLeft`, `CropRight`, `CropTop`, `CropBottom`, `RotationAngle`, `FlipX`, `FlipY`, `CompositeMode`, `RetimeProcess`.

---

### Color Grading

| Tool | Returns | Description |
|------|---------|-------------|
| `get_node_graph(track_type, track_index, item_index)` | `string` (JSON) | Returns the node graph structure for a clip. Requires the Color page to be active with the clip selected. |
| `set_lut(node_index, lut_path, track_type, track_index, item_index)` | `string` | Applies a LUT file to a node. |
| `set_cdl(node_index, slope, offset, power, saturation, track_type, track_index, item_index)` | `string` | Applies CDL (Color Decision List) values to a node. |

#### `set_lut`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_index` | `int` | required | 1-based node index in the node graph. |
| `lut_path` | `string` | required | Absolute path to a `.cube`, `.3dl`, or other Resolve-supported LUT file. |

#### `set_cdl`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_index` | `int` | required | 1-based node index. |
| `slope` | `string` | `"1.0 1.0 1.0"` | RGB slope values as space-separated floats (e.g. `"1.2 1.1 0.9"`). |
| `offset` | `string` | `"0.0 0.0 0.0"` | RGB offset values as space-separated floats. |
| `power` | `string` | `"1.0 1.0 1.0"` | RGB power (gamma) values as space-separated floats. |
| `saturation` | `float` | `1.0` | Global saturation multiplier (1.0 = no change). |

---

### Rendering

| Tool | Returns | Description |
|------|---------|-------------|
| `get_render_formats(render_format)` | `string` (JSON) | Lists available render formats and their codecs. Pass `render_format` to get codecs for one format only. |
| `get_render_settings()` | `string` (JSON) | Returns current format, codec, render mode, render preset list, job queue, and whether rendering is active. |
| `set_render_settings(settings, render_format, codec)` | `string` (JSON) | Configures render settings. Returns report of what was applied. |
| `add_render_job()` | `string` (JSON) | Adds a job to the render queue using the current render settings. Returns `job_id`. |
| `start_rendering(job_ids)` | `string` | Starts render jobs. If `job_ids` is omitted, all queued jobs are started. |
| `get_render_status(job_id)` | `string` (JSON) | Returns status of a render job: progress percentage, completion state, errors. |
| `stop_rendering()` | `string` | Stops all currently running render processes. |

#### `set_render_settings`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `settings` | `dict` | `None` | Key/value pairs passed directly to `project.SetRenderSettings()`. Common keys: `TargetDir`, `CustomName`, `SelectAllFrames`, `MarkIn`, `MarkOut`, `ExportVideo`, `ExportAudio`, `FormatWidth`, `FormatHeight`, `FrameRate`. |
| `render_format` | `string` | `None` | Shorthand to set the render format (e.g. `"QuickTime"`, `"MXF"`, `"MP4"`). |
| `codec` | `string` | `None` | Shorthand to set the codec (e.g. `"H.264"`, `"ProRes 422 HQ"`, `"DNxHD"`). |

---

### AI / Neural Engine (Studio only)

All tools in this section require **DaVinci Resolve Studio** with the DaVinci Neural Engine.

| Tool | Returns | Description |
|------|---------|-------------|
| `create_magic_mask(mode, track_type, track_index, item_index)` | `string` | Runs AI subject isolation on a clip, creating a Magic Mask. |
| `regenerate_magic_mask(track_type, track_index, item_index)` | `string` | Re-runs Magic Mask analysis on a clip where a mask already exists. |
| `smart_reframe(track_type, track_index, item_index)` | `string` | Applies Smart Reframe (AI-based automatic reframing for different aspect ratios). |
| `stabilize(track_type, track_index, item_index)` | `string` | Applies DaVinci Neural Engine stabilization to a clip. |
| `detect_scene_cuts()` | `string` (JSON) | Detects scene cuts in the current timeline using AI and returns cut positions. |
| `create_subtitles_from_audio(language, preset, chars_per_line, line_break, gap)` | `string` | Generates subtitles from the timeline's audio using Resolve's built-in AI. Requires Resolve Studio 19+. |

#### `create_magic_mask`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | `string` | `"F"` | Analysis direction: `"F"` (forward), `"B"` (backward), `"BI"` (bidirectional). |

#### `create_subtitles_from_audio`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | `string` | `"auto"` | Recognition language. Values: `auto`, `english`, `french`, `german`, `italian`, `japanese`, `korean`, `mandarin_simplified`, `mandarin_traditional`, `portuguese`, `russian`, `spanish`, `danish`, `dutch`, `norwegian`, `swedish`. |
| `preset` | `string` | `"default"` | Subtitle formatting preset: `"default"`, `"teletext"`, `"netflix"`. |
| `chars_per_line` | `int` | `42` | Maximum characters per subtitle line. |
| `line_break` | `string` | `"single"` | Line break mode: `"single"` or `"double"`. |
| `gap` | `int` | `0` | Minimum gap in frames between subtitle items. |

---

### Audio

| Tool | Returns | Description |
|------|---------|-------------|
| `get_voice_isolation_state(track_index)` | `string` (JSON) | Returns the Voice Isolation state (enabled, amount) for an audio track. Requires Resolve Studio. |
| `set_voice_isolation_state(track_index, enabled, amount)` | `string` | Enables or disables Voice Isolation on an audio track. Requires Resolve Studio. |
| `generate_audio_visualizer_image(preset, target_width, bin_name)` | `string` (JSON) | Exports the current timeline's audio, converts it to a multi-band waveform PNG using the sh4rk Audio Visualiser format, and imports the result into a Media Pool subfolder. Requires `ffmpeg`. |

#### `set_voice_isolation_state`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track_index` | `int` | required | 1-based audio track number. |
| `enabled` | `bool` | required | `True` to enable, `False` to disable. |
| `amount` | `int` | `100` | Isolation strength: 0–100. |

#### `generate_audio_visualizer_image`

Renders the timeline audio via Resolve's built-in "Audio Only" render preset, processes it through a multi-band waveform pipeline (FFmpeg bandpass filters + NumPy + Pillow), and imports the resulting PNG into a named Media Pool bin. The PNG format is compatible with the [sh4rk Audio Visualiser](https://sh4rkk.com/shop) Fusion plugin — each row is one frequency band.

> **Note:** Due to a known issue with the FastMCP tool wrapper in the current server version, this tool must be called via `execute_resolve_code` rather than directly. See [workaround](#audio-visualizer-workaround) below.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `preset` | `string` | `"3band"` | Frequency band preset. One of: `"1band"` (full spectrum), `"3band"` (Low/Mid/High in RGB), `"10band"`, `"25band"`, `"100band"` (maximum resolution, slow). |
| `target_width` | `int` | `0` | Output image width in pixels. `0` = auto (1 pixel per frame, capped at 32 000 px). |
| `bin_name` | `string` | `"Audio Visualizer"` | Name of the Media Pool subfolder to import the result into. Created if it doesn't exist. |

**Example output:** a 854 × 10 px PNG for a 25 fps / 854-frame timeline with the `10band` preset — 10 rows, one per frequency band.

##### Audio Visualizer workaround

Until the FastMCP decorator issue is resolved, call the tool via `execute_resolve_code`:

```python
import sys, importlib
sys.path.insert(0, '/absolute/path/to/resolve-mcp-studio/src')
import resolve_claude_mcp.server as srv
importlib.reload(srv)
result = srv.generate_audio_visualizer_image(
    preset="10band",
    target_width=0,
    bin_name="Audio Visualizer",
)
print(result)
```

Replace `/absolute/path/to/resolve-mcp-studio` with the actual path to your clone.

---

### Fusion (Compositing / VFX)

All Fusion tools address a timeline item using `track_type`, `track_index`, and `item_index` (same convention as timeline item properties).

| Tool | Returns | Description |
|------|---------|-------------|
| `get_fusion_comp_list(track_type, track_index, item_index)` | `string` (JSON) | Lists Fusion compositions on a timeline item: count and names. |
| `add_fusion_comp(track_type, track_index, item_index)` | `string` | Adds a new blank Fusion composition to a timeline item. |
| `import_fusion_comp(comp_path, track_type, track_index, item_index)` | `string` | Imports a `.comp` or `.setting` file as a Fusion composition on a timeline item. |
| `export_fusion_comp(export_path, comp_index, track_type, track_index, item_index)` | `string` | Exports a Fusion composition from a timeline item to a file. |
| `load_fusion_comp(comp_name, track_type, track_index, item_index)` | `string` | Sets the named composition as the active Fusion composition on a timeline item. |
| `delete_fusion_comp(comp_name, track_type, track_index, item_index)` | `string` | Deletes a named Fusion composition from a timeline item. Irreversible. |
| `rename_fusion_comp(old_name, new_name, track_type, track_index, item_index)` | `string` | Renames a Fusion composition on a timeline item. |
| `create_fusion_clip(track_type, track_index, item_indices)` | `string` | Merges one or more timeline items into a Fusion clip. `item_indices` is a list of 0-based indices; omit to use all items on the track. |
| `insert_fusion_generator(generator_name)` | `string` | Inserts a Fusion generator at the current playhead position. |
| `insert_fusion_composition()` | `string` | Inserts a blank Fusion composition at the current playhead position. |
| `insert_fusion_title(title_name)` | `string` | Inserts a Fusion title template at the current playhead position. |

#### `export_fusion_comp`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `export_path` | `string` | required | Absolute file path for the exported `.comp` file. |
| `comp_index` | `int` | `1` | 1-based index of the composition to export. |

---

### Timeline Export

| Tool | Returns | Description |
|------|---------|-------------|
| `export_timeline(file_path, export_type, export_subtype)` | `string` | Exports the current timeline to a file. |
| `export_current_frame(file_path)` | `string` | Exports the current frame as a still image. |

#### `export_timeline`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `string` | required | Absolute path for the output file. |
| `export_type` | `string` | `"fcpxml_1_10"` | Format: `aaf`, `drt`, `edl`, `fcp_7_xml`, `fcpxml_1_8`, `fcpxml_1_9`, `fcpxml_1_10`, `hdr_10_profile_a`, `hdr_10_profile_b`, `csv`, `tab`, `otio`, `ale`, `ale_cdl` |
| `export_subtype` | `string` | `"none"` | For AAF: `"aaf_new"` or `"aaf_existing"`. For EDL: `"cdl"`, `"sdl"`, `"missing_clips"`, or `"none"`. |

#### `export_current_frame`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `string` | required | Absolute path including extension. Supported: `.png`, `.jpg`, `.tif`, `.dpx`, `.exr`. |

---

### Thumbnail & Screenshot

| Tool | Returns | Description |
|------|---------|-------------|
| `get_current_thumbnail()` | `Image` (PNG) | Returns a PNG thumbnail of the current frame from the Color page. Requires the Color page to be active with a clip selected. |
| `screenshot()` | `Image` (PNG) | Captures the DaVinci Resolve window (or full screen as fallback). Returns PNG. **macOS only.** |

> **Privacy note:** Screenshots are sent to Anthropic for AI analysis. Anything visible — client footage, unreleased material, passwords in other apps — may be transmitted. Only use when comfortable with what's on screen.

---

### Local Transcription (macOS / Apple Silicon only)

These tools use **mlx-whisper**, which runs entirely locally on Apple Silicon. They are **not available on Windows or Linux** (MLX is Apple-only).

| Tool | Returns | Description |
|------|---------|-------------|
| `transcribe_audio(file_path, model, language, word_timestamps, initial_prompt)` | `string` (JSON) | Transcribes an audio or video file locally. Auto-splits files longer than 5 minutes into chunks. Returns timestamped transcript and saves an SRT file next to the source. |
| `transcribe_and_add_subtitles(file_path, model, language, initial_prompt)` | `string` (JSON) | Transcribes audio and adds the segments as markers to the current timeline. |
| `export_srt(file_path, output_path, model, language, initial_prompt)` | `string` | Transcribes audio and saves the result as an SRT file ready for import into Resolve. |
| `list_whisper_models()` | `string` (JSON) | Lists available mlx-whisper model sizes with their HuggingFace repo paths. |

#### `transcribe_audio`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `string` | required | Absolute path to an audio or video file. |
| `model` | `string` | `"turbo"` | Model size. Options: `tiny`, `base`, `small`, `medium`, `large`, `turbo`. Or a full HuggingFace repo path (e.g. `"mlx-community/whisper-large-v3"`). |
| `language` | `string` | `None` | ISO 639-1 code (e.g. `"no"`, `"en"`, `"fr"`). `None` = auto-detect. |
| `word_timestamps` | `bool` | `False` | Whether to include word-level timestamp data in the output. |
| `initial_prompt` | `string` | `None` | Prompt to seed the transcription context (useful for proper nouns, spelling). |

**Model size vs. accuracy trade-off:**

| Model | Speed | Accuracy | Approx. download size |
|-------|-------|----------|-----------------------|
| `tiny` | Fastest | Lowest | ~39 MB |
| `base` | Very fast | Low | ~74 MB |
| `small` | Fast | Moderate | ~244 MB |
| `medium` | Moderate | Good | ~769 MB |
| `turbo` | Fast | High | ~809 MB |
| `large` | Slowest | Highest | ~1.5 GB |

Models are downloaded from HuggingFace on first use and cached locally in `~/.cache/huggingface/`.

---

### Studio Extensions: Markers

These tools provide a two-step workflow: **parse → confirm → write**. Nothing is written to the timeline until `set_markers_from_list` is called.

| Tool | Returns | Description |
|------|---------|-------------|
| `parse_and_preview_markers(text, fps)` | `string` (JSON) | Parses free-text timecodes + descriptions into structured markers. Returns a preview list for review. Nothing is written to Resolve. |
| `set_markers_from_list(markers)` | `string` (JSON) | Writes an approved marker list to the current timeline. Returns a report: project, timeline, how many were set, per-row failures. |

#### `parse_and_preview_markers`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `string` | required | Free-text block containing timecodes and descriptions. See supported formats below. |
| `fps` | `float` | `None` | Frame rate to use for conversion. If omitted, reads from the active timeline. |

**Supported line formats:**

```
MM:SS description           02:15 fjern pause
HH:MM:SS description        01:02:15 klipp her
HH:MM:SS:FF description     01:02:15:12 pling inn
- MM:SS description         - 04:00 intro starter
* MM:SS — description       * 07:30 — lyd for lav
```

Three-component timecodes (`HH:MM:SS`) are always interpreted as hours/minutes/seconds. Frame-accurate positions require four components (`HH:MM:SS:FF`). Lines that cannot be parsed are returned in `skipped_lines` for review.

**Automatic color assignment** (first matching keyword wins):

| Color | Keywords |
|-------|----------|
| Red | `feil`, `fjern`, `problem` |
| Orange | `klipp`, `cut`, `edit` |
| Yellow | `lyd`, `musikk`, `audio` |
| Cyan | `pling`, `jingle`, `stikk` |
| Green | `intro`, `outro` |
| Blue | (default — no keyword match) |

**Response format:**

```json
{
  "project": "Kundefilm 2026",
  "timeline": "EDIT-16x9",
  "fps": 25.0,
  "markers": [
    {"frame": 3375, "timecode": "00:02:15:00", "name": "fjern pause", "color": "Red", "note": ""}
  ],
  "skipped_lines": ["dette er ingen timecode"]
}
```

If the panel bridge is running, parsed markers are also pushed there automatically.

#### `set_markers_from_list`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `markers` | `list[dict]` | required | List of marker objects. See schema below. |

**Marker object schema:**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `frame` | `int` | Yes (or `timecode`) | Absolute frame number. Takes precedence over `timecode`. |
| `timecode` | `string` | Yes (if no `frame`) | `HH:MM:SS:FF` — converted to frame using the active timeline's fps. |
| `name` | `string` | No | Marker label. Empty string if omitted. |
| `color` | `string` | No | Marker color. Falls back to `"Blue"` if omitted or invalid. |
| `note` | `string` | No | Extended note text. |
| `duration` | `int` | No | Duration in frames. Defaults to `1`. |

---

### Studio Extensions: Subtitle Tracks

Three-step workflow: **list tracks → transcribe → write**.

| Tool | Returns | Description |
|------|---------|-------------|
| `get_timeline_subtitle_tracks()` | `string` (JSON) | Lists all subtitle tracks on the current timeline: 1-based index, name, subtitle item count, enabled state. |
| `transcribe_timeline_audio(language, output_mode, track_index, model)` | `string` (JSON) | Renders the timeline's audio to a temporary WAV and transcribes it locally. Returns segments for review. Nothing is written to the timeline. |
| `write_subtitles_to_resolve(segments, output_mode, track_name, track_index)` | `string` (JSON) | Writes reviewed segments to the timeline as a subtitle track. |

#### `transcribe_timeline_audio`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | `string` | `"auto"` | Language hint. Accepts: `"auto"`, `"norsk"` / `"no"`, `"engelsk"` / `"en"`, or any ISO 639-1 code. |
| `output_mode` | `string` | `"new"` | `"new"` = prepare segments for a new subtitle track. `"correct"` = map transcription onto the timing of an existing track (requires `track_index`). |
| `track_index` | `int` | `None` | Required when `output_mode="correct"`. 1-based subtitle track number. |
| `model` | `string` | `"turbo"` | mlx-whisper model size. See [model table](#transcribe_audio). |

**How `output_mode="correct"` works:** The transcription is aligned to the existing track's subtitle timing using segment overlap scoring. Each existing segment gets a proposed new text. The `original_text` is returned alongside `text` so differences can be reviewed before writing.

**Audio rendering:** The tool adds a render job to the current queue (audio-only, temporary WAV), runs it, then removes the job. Current render settings are temporarily changed and restored. A 30-minute timeout applies.

#### `write_subtitles_to_resolve`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `segments` | `list[dict]` | required | List of `{"start": float, "end": float, "text": string}` — times in seconds. |
| `output_mode` | `string` | `"new"` | `"new"` = create a new subtitle track. `"correct"` = replace text of an existing track. |
| `track_name` | `string` | `None` | Name for the new subtitle track. Defaults to `"Transcription"`. |
| `track_index` | `int` | `None` | Required when `output_mode="correct"`. 1-based subtitle track number. |

**Correction mode note:** Because the Resolve API cannot edit subtitle text in place, the corrected version is written as a new track named `"<original name> (corrected)"`. The original track is **disabled, never deleted**. Timing is always taken from the original track's items — the transcription text only replaces the label.

---

### Studio Extensions: Project Templates

| Tool | Returns | Description |
|------|---------|-------------|
| `list_project_templates()` | `string` (JSON) | Lists all available templates from `templates/configs/`. Returns id, display name, resolution, fps, timeline names, bin names, and whether a `.drp` file is attached. |
| `create_project_from_template(template_name, project_name)` | `string` (JSON) | Creates and opens a new Resolve project from a template. Returns what was created and any warnings. |

#### `create_project_from_template`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `template_name` | `string` | required | The `id` field from `list_project_templates()` (matches the JSON filename without extension). |
| `project_name` | `string` | required | Name for the new project in Resolve's Project Manager. |

**Template config format** (`templates/configs/<id>.json`):

```json
{
  "name": "Standard (3 timelines)",
  "resolution": "3840x2160",
  "fps": 25,
  "audio_channels": 2,
  "timelines": [
    {"name": "EDIT-16x9", "type": "16:9"},
    {"name": "EDIT-9x16", "type": "9:16"},
    {"name": "Selects",   "type": "16:9"}
  ],
  "bins": ["000_TIMELINE"],
  "drp": "_TEMPLATE_.drp"
}
```

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | `string` | Yes | Human-readable display name shown in `list_project_templates()`. |
| `resolution` | `string` | Yes | Target resolution as `"WxH"` (e.g. `"3840x2160"`, `"1920x1080"`). |
| `fps` | `number` | Yes | Timeline frame rate (e.g. `25`, `23.976`, `29.97`). |
| `audio_channels` | `int` | No | Number of audio channels. Defaults to `2`. |
| `timelines` | `list` | No | Timelines to create. Each entry: `{"name": string, "type": "16:9"\|"9:16"\|...}`. 9:16 timelines get a rotated resolution automatically. |
| `bins` | `list[string]` | No | Bin names to create in the Media Pool root. |
| `drp` | `string` | No | Filename of a `.drp` in `templates/drp/` to import instead of building from scratch. If provided, the project is imported from the DRP and then renamed. |

The templates directory defaults to `<repo root>/templates/` and can be overridden with `RESOLVE_MCP_TEMPLATES_DIR`.

---

### Studio Extensions: Media Pool Sync

| Tool | Returns | Description |
|------|---------|-------------|
| `sync_finder_folder_to_media_pool(folder_path)` | `string` (JSON) | Mirrors a Finder folder tree as bins in the Media Pool and imports each folder's media files. |

#### `sync_finder_folder_to_media_pool`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder_path` | `string` | required | Absolute path to the root folder to sync. |

**Supported media extensions:** `.mp4`, `.mov`, `.mxf`, `.avi`, `.mkv`, `.r3d`, `.braw`, `.arri`, `.wav`, `.aif`, `.aiff`, `.mp3`, `.m4a`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.dpx`, `.exr`, `.dng`.

**Idempotency:** Existing bins with the same name are reused (not recreated). Files already present in a bin are matched by path and skipped. Re-running the tool after adding new files to a folder picks up only the new additions.

**Limitations:** Resolve's API does not support live-linked or auto-updating bins. Each sync run is a discrete import, not a persistent folder watch.

**Response format:**

```json
{
  "project": "Kundefilm 2026",
  "folder_path": "/Volumes/Media/PROSJEKT_X",
  "bins_created": 4,
  "bins_reused": 1,
  "files_imported": 23,
  "files_skipped": 2,
  "files_failed": 0,
  "structure": { "..." : "..." }
}
```

---

### Studio Extensions: Auto Clip Color

| Tool | Returns | Description |
|------|---------|-------------|
| `auto_color_clips(source, dry_run)` | `string` (JSON) | Categorizes clips by filename/metadata and proposes or applies clip colors in the Media Pool. |

#### `auto_color_clips`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `string` | `"timeline"` | `"timeline"` = clips on the current timeline. `"media_pool"` = all clips in all bins. |
| `dry_run` | `bool` | `True` | `True` = return proposals only, nothing applied. `False` = apply colors to clips. |

**Category → color mapping:**

| Category | Trigger keywords / conditions | Clip color |
|----------|------------------------------|------------|
| Drone / aerial | `DJI`, `drone`, `mavic`, `phantom`, `air2`, aerial file patterns | Yellow |
| Talking head / interview | `interview`, `intervju`, `talking`, `sit-down`, talking-head camera metadata | Blue |
| B-roll / handheld | `broll`, `b-roll`, `cutaway`, `handheld` | Green |
| Music / audio-only | `.mp3`, `.wav`, `.aif`, `.m4a`, `music`, `lyd`, `musikk` | Pink |
| Graphics / stills | `.png`, `.jpg`, `.tif`, `.dpx`, `.exr`, `graphic`, `logo`, `title` | Purple |
| Uncategorized | No matching category | Beige |

The tool returns `reason` per clip explaining which rule triggered the categorization.

---

### Code Execution

| Tool | Returns | Description |
|------|---------|-------------|
| `execute_resolve_code(code)` | `string` | Executes arbitrary Python code in the Resolve scripting environment. |

#### `execute_resolve_code`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `code` | `string` | required | Python source code to execute. |

**Pre-loaded namespace variables:**

| Variable | Type | Description |
|----------|------|-------------|
| `resolve` | `Resolve` | Top-level Resolve API object. |
| `project` | `Project` | Currently open project. |
| `mediaPool` | `MediaPool` | Media Pool of the current project. |
| `timeline` | `Timeline` | Currently active timeline (may be `None`). |
| `mediaStorage` | `MediaStorage` | Resolve's media storage manager. |

Use `print()` to return output, or assign to a variable named `result` — both are captured and returned.

> **Security:** This tool executes arbitrary Python with full filesystem and Resolve API access. Review all code before executing. Never run code from untrusted sources.

---

## Module Reference

Detailed reference for the internal Python modules. These are not MCP tools directly — they are the building blocks called by `server.py`.

---

### markers.py

Timecode parsing and color assignment for the marker editor workflow.

**Source:** `src/resolve_claude_mcp/markers.py`

**Constants:**

| Name | Type | Description |
|------|------|-------------|
| `VALID_MARKER_COLORS` | `set[str]` | The 17 color names accepted by `Timeline.AddMarker()`. |
| `DEFAULT_COLOR` | `string` | `"Blue"` — fallback color when no keyword matches. |

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `pick_color` | `(text: str) -> str` | `string` | Returns a marker color based on keyword matching in `text`. Substring matching — `"stikkord"` matches `"stikk"`. |
| `timecode_to_frame` | `(timecode: str, fps: float) -> int` | `int` | Converts a timecode string (`MM:SS`, `HH:MM:SS`, `HH:MM:SS:FF`) to an absolute frame number. Raises `ValueError` on invalid or out-of-range components (minutes/seconds ≥ 60, frames ≥ fps). |
| `frame_to_timecode` | `(frame: int, fps: float) -> str` | `string` | Converts a frame number to `HH:MM:SS:FF`. Uses non-drop-frame math (exact for integer rates like 24/25/30/50/60). |
| `parse_marker_list` | `(text: str, fps: float) -> Tuple[List[Dict], List[str]]` | `(list, list)` | Parses a free-text block into `(markers, skipped_lines)`. Markers are sorted by frame. Non-empty lines that don't match any timecode pattern are collected in `skipped_lines`. |

**`parse_marker_list` — each marker dict:**

| Key | Type | Description |
|-----|------|-------------|
| `frame` | `int` | Absolute frame number (from frame 0). |
| `timecode` | `string` | Human-readable `HH:MM:SS:FF`. |
| `name` | `string` | The description text from the input line. |
| `color` | `string` | Auto-assigned color from keyword matching. |
| `note` | `string` | Always `""` — can be set manually before calling `set_markers_from_list`. |

---

### transcription.py

Local audio transcription using mlx-whisper, optimized for Apple M-series chips. Long files are automatically split into 5-minute chunks to avoid MCP timeout limits. Chunk results are stitched with context continuity.

**Source:** `src/resolve_claude_mcp/transcription.py`

**Constants:**

| Name | Value | Description |
|------|-------|-------------|
| `WHISPER_MODELS` | `dict` | Maps short names (`tiny`, `base`, `small`, `medium`, `large`, `turbo`) to HuggingFace repo paths. |
| `DEFAULT_MODEL` | `"turbo"` | Default model used when `model` is not specified. |
| `CHUNK_SECONDS` | `300` | Audio chunk duration in seconds (5 minutes). |

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `transcribe` | `(file_path, model, language, word_timestamps, initial_prompt)` | `list[dict]` | Main transcription entry point. Detects file duration; if > `CHUNK_SECONDS`, splits with ffmpeg and stitches results. Returns list of `{"start", "end", "text"}` segment dicts. |
| `transcribe_audio` | `(file_path, model, language)` | `(string, list[dict])` | Wrapper used by MCP tools. Returns `(formatted_transcript, segments)`. The formatted transcript is a compact timestamped text block. |
| `segments_to_srt` | `(segments: list) -> str` | `string` | Converts a list of segments to a valid SRT format string with 1-based numbering and `HH:MM:SS,mmm` timestamps. |
| `get_subtitle_tracks` | `(timeline) -> list` | `list[dict]` | Returns all subtitle tracks from a Resolve timeline: `{"index", "name", "item_count", "enabled"}`. |
| `get_subtitle_track_segments` | `(timeline, track_index: int) -> list` | `list[dict]` | Returns subtitle items from a specific 1-based track: `{"start", "end", "text", "index"}`. Times in seconds. |
| `write_subtitle_track` | `(timeline, segments, track_name)` | `dict` | Writes segments as a new subtitle track. Converts to SRT → saves to temp file → imports via Media Pool → adds to timeline. Returns `{"track_name", "segment_count", "status"}`. |
| `correct_subtitle_track` | `(timeline, track_index, corrected_segments)` | `dict` | Replaces text in an existing subtitle track. Creates a new track `"<name> (corrected)"` and disables the original. Returns `{"original_track", "new_track", "segment_count", "status"}`. |
| `map_transcription_to_segments` | `(transcription_segs, existing_segs)` | `list[dict]` | Maps transcription results onto the timing of existing subtitle segments using overlap scoring. Returns `{"start", "end", "text", "original_text"}` for review. |

**ffmpeg dependency:** `ffprobe` is used to read file duration; `ffmpeg` is used to slice audio into 16 kHz mono PCM WAV chunks. Both must be on `PATH`. Install via Homebrew: `brew install ffmpeg`.

---

### templates.py

JSON-based project template system. Reads configs from `templates/configs/` and optional `.drp` files from `templates/drp/`.

**Source:** `src/resolve_claude_mcp/templates.py`

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `list_templates` | `() -> list` | `list[dict]` | Scans `templates/configs/*.json` and returns a summary list with `id`, `name`, `resolution`, `fps`, `timelines`, `bins`, `has_drp`. |
| `create_project_from_template` | `(template_name: str, project_name: str) -> dict` | `dict` | Creates a new Resolve project. If the config has a `"drp"` key, imports the `.drp` and renames it. Otherwise builds the project from scratch: sets resolution + fps, creates bins, creates timelines. Anything that can't be applied is reported in `warnings` rather than failing. Returns `{"project_name", "created", "warnings"}`. |

**Environment override:** Set `RESOLVE_MCP_TEMPLATES_DIR` to an absolute path to use a custom templates directory instead of `<repo root>/templates/`.

---

### media_pool.py

Finder folder → Media Pool bin synchronization.

**Source:** `src/resolve_claude_mcp/media_pool.py`

**Constants:**

`MEDIA_EXTENSIONS` — set of lowercase file extensions recognized as importable media: video (`.mp4`, `.mov`, `.mxf`, `.avi`, `.mkv`, `.r3d`, `.braw`, `.arri`), audio (`.wav`, `.aif`, `.aiff`, `.mp3`, `.m4a`), and image/RAW formats (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.dpx`, `.exr`, `.dng`).

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `read_finder_structure` | `(root_path: str) -> dict` | `dict` | Recursively reads a folder tree from disk. Returns nested `{"name", "path", "subfolders": [...], "files": [...]}`. Hidden files (dot-prefixed names) are excluded. |
| `sync_structure_to_media_pool` | `(structure, media_pool, parent_folder)` | `dict` | Recursively creates bins matching the folder structure and imports media files into the correct bin. Returns counts: `{"bins_created", "bins_reused", "files_imported", "files_skipped", "files_failed"}`. |

**Idempotency detail:** Before importing a file, the function checks existing clips in the target bin for a matching `File Path` property. Files that already match are counted as `skipped`. Bins are matched by name using `GetSubFolderList()` on the parent bin — an existing bin is reused rather than duplicated.

---

### connection.py

Manages the connection to DaVinci Resolve's Python scripting API.

**Source:** `src/resolve_claude_mcp/connection.py`

**Class: `ResolveConnection`**

Singleton-style wrapper around the Resolve API. Instantiated once at server startup and reused for all tool calls. All API access is serialized with an `RLock` — the Resolve scripting API is not thread-safe.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `__init__` | `()` | — | Configures `sys.path` and environment variables. Uses platform-specific defaults if env vars are not set. Loads `DaVinciResolveScript` and calls `scriptapp("Resolve")`. |
| `get_resolve` | `() -> Resolve` | `Resolve` | Returns the top-level Resolve API object. Raises `RuntimeError` if not connected. |
| `get_project_manager` | `() -> ProjectManager` | `ProjectManager` | Returns the Resolve Project Manager. |
| `get_project` | `() -> Project` | `Project` | Returns the currently open project. Raises `RuntimeError` if no project is open. |
| `get_current_timeline` | `() -> Timeline \| None` | `Timeline` or `None` | Returns the active timeline, or `None` if none is open. |
| `get_media_pool` | `() -> MediaPool` | `MediaPool` | Returns the Media Pool of the current project. |
| `get_media_storage` | `() -> MediaStorage` | `MediaStorage` | Returns the Resolve media storage manager. |
| `execute_code` | `(code: str, extra_namespace: dict) -> Any` | `Any` | Executes Python code with Resolve API objects pre-loaded in the namespace. |
| `check_health` | `() -> bool` | `bool` | Attempts a lightweight API call to verify the connection is alive. |

**Platform defaults for `RESOLVE_SCRIPT_LIB`:**

| Platform | Default path |
|----------|-------------|
| macOS | `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so` |
| Windows | `C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll` |
| Linux | `/opt/resolve/libs/Fusion/fusionscript.so` |

**Module function:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `get_resolve_connection` | `() -> ResolveConnection` | `ResolveConnection` | Returns the global singleton `ResolveConnection`. Creates it on first call. |

---

### resolve_utils.py

Serialization helpers that convert Resolve API objects (opaque C++ wrappers) into JSON-serializable Python dicts.

**Source:** `src/resolve_claude_mcp/resolve_utils.py`

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `folder_to_dict` | `(folder, max_depth, max_clips, depth)` | `dict` | Recursively converts a `MediaPoolFolder` to a dict with `name`, `subfolders`, and `clips`. Stops at `max_depth`; limits clips per folder to `max_clips`. |
| `clip_to_dict` | `(clip)` | `dict` | Converts a `MediaPoolItem` to a full dict with all clip properties from `GetClipProperty()`. |
| `clip_to_dict_brief` | `(clip)` | `dict` | Converts a `MediaPoolItem` to a minimal dict: name, duration, fps, file path only. Faster for large media pools. |
| `timeline_to_dict` | `(timeline)` | `dict` | Converts a `Timeline` to a dict: name, frame rate, resolution, start/end timecode, video/audio/subtitle track counts, and markers. |
| `timeline_item_to_dict` | `(item, index: int)` | `dict` | Converts a `TimelineItem` to a dict: 0-based index, name, start/end frame, duration, and media pool item reference. |
| `timeline_item_full_dict` | `(item)` | `dict` | Converts a `TimelineItem` to a full dict including all properties from `GetProperty()`. |
| `node_graph_to_dict` | `(item)` | `dict` | Extracts color grading node graph info from a `TimelineItem` on the Color page. |
| `thumbnail_to_png_bytes` | `(item)` | `bytes` | Requests a thumbnail from the Color page via `GrabStill()` and converts the base64 RGB data to PNG bytes. |
| `safe_serialize` | `(obj) -> Any` | `Any` | Recursively makes an object JSON-serializable. Converts non-serializable values to their `repr()`. |

**Internal helper:** `_safe(fn, *args, default=None)` — wraps a Resolve API call in `try/except` and returns `default` if it raises. Used throughout to handle API calls that fail when a feature is unavailable or the page is wrong.

---

### clip_colors.py

Automatic clip categorization for the `auto_color_clips` MCP tool. Determines a clip's category from its filename, file extension, and available camera metadata.

**Source:** `src/resolve_claude_mcp/clip_colors.py`

**Categories and detection rules:**

| Category | File extension triggers | Filename keyword triggers | Clip color |
|----------|------------------------|--------------------------|------------|
| `drone` | — | `DJI`, `drone`, `mavic`, `phantom`, `air2` | Yellow |
| `talking_head` | — | `interview`, `intervju`, `sit-down`, `talking` | Blue |
| `broll` | — | `broll`, `b-roll`, `cutaway`, `handheld` | Green |
| `music_audio` | `.mp3`, `.wav`, `.aif`, `.aiff`, `.m4a` | `music`, `lyd`, `musikk` | Pink |
| `graphics_stills` | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.dpx`, `.exr` | `graphic`, `logo`, `title` | Purple |
| `uncategorized` | No rule matched | — | Beige |

Categories are evaluated in priority order — the first match wins.

**Functions:**

| Function | Signature | Returns | Description |
|----------|-----------|---------|-------------|
| `propose_color` | `(clip: MediaPoolItem) -> (str, str, str)` | `(category, color, reason)` | Returns a three-tuple for a clip. `reason` is a human-readable sentence explaining which rule triggered (e.g. `"filename contains 'DJI'"`). |

---

### panel_server.py

Local HTTP bridge that exposes the MCP server's core functionality to the browser-based panel.

**Source:** `src/resolve_claude_mcp/panel_server.py`

**Why a separate server?** The MCP server communicates with Claude Desktop over stdio. The HTML panel cannot talk to a stdio process directly. The panel bridge is a lightweight HTTP server bound to `127.0.0.1` that the panel's JavaScript calls via `fetch()`.

**Starting the panel server:**

```bash
uv run python -m resolve_claude_mcp.panel_server
# Default port: 8765
# Open: http://127.0.0.1:8765
```

**Security:** Binds to `127.0.0.1` only. CORS is allowed from `localhost` origins and `file://` (origin `"null"`) — the panel works both when served from the bridge and when opened as a local file.

**HTTP API endpoints:**

| Method | Path | Request body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/status` | — | `{connected, project, timeline}` | Connection state and active project/timeline names. |
| `POST` | `/api/markers/parse` | `{text, fps?}` | `{project, timeline, fps, markers, skipped_lines}` | Parse free-text timecodes into structured markers. |
| `POST` | `/api/markers/set` | `{markers}` | `{set, failures}` | Write an approved marker list to the current timeline. |
| `GET` | `/api/subtitle-tracks` | — | `{tracks}` | List subtitle tracks on the current timeline. |
| `POST` | `/api/transcribe` | `{language, output_mode, track_index?}` | `{job_id}` | Start a transcription job (runs in background thread). |
| `GET` | `/api/transcribe/<job_id>` | — | `{status, result?, error?}` | Poll a running transcription job. `status`: `"running"`, `"done"`, `"error"`. |
| `POST` | `/api/subtitles/write` | `{segments, output_mode, track_name?, track_index?}` | `{status, count}` | Write reviewed segments to the timeline. |

**Static file serving:** The bridge serves the panel's static files from the `panel/` directory. Override with `RESOLVE_MCP_PANEL_DIR`.

**Transcription jobs:** `POST /api/transcribe` returns a `job_id` immediately and runs the transcription in a background thread. Poll `GET /api/transcribe/<job_id>` until `status` is `"done"` or `"error"`.

**Pending markers push:** When `parse_and_preview_markers` is called via Claude, it attempts a best-effort push of the parsed markers to the panel bridge at `http://127.0.0.1:8765`. This makes markers appear in the panel automatically.

**Port:** Defaults to `8765`. Override with `RESOLVE_MCP_PANEL_PORT`.

---

## Browser Panel

The browser panel is a compact dark-themed UI served by `panel_server.py`. It mirrors the MCP tools most useful for hands-on editorial work.

**Starting:**

```bash
uv run python -m resolve_claude_mcp.panel_server
```

Then open `http://127.0.0.1:8765` in any browser.

**Status bar (always visible)**
- Connection indicator (green = connected, red = disconnected)
- Active project name and active timeline name

**Marker Editor**
- Editable table: timecode | name | color | delete
- Color picker with all 17 Resolve marker colors shown as swatches
- Paste-and-parse: paste free text directly into the panel; parsed markers appear in the table
- "Send til Resolve" button — calls `POST /api/markers/set`

**Transcription**
- Language selector: Norsk / Engelsk / Auto
- Mode toggle: New subtitle track / Correct existing track
- Track selector (shown in Correct mode)
- "Start transkripsjon" button — starts async job, shows live progress
- Segment review table appears when transcription finishes
- "Skriv til Resolve" button — writes reviewed segments

**Design tokens:**

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#1a1a1a` | Matches Resolve dark UI |
| Accent | `#00E5FF` | Cyan — primary interactive elements |
| Secondary | `#A855F7` | Violet — secondary highlights |
| Data font | `ui-monospace, 'Cascadia Code', monospace` | Timecodes, frame numbers |
| Label font | `system-ui` | UI labels and buttons |

No external dependencies — fully self-contained vanilla JS and CSS.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOLVE_SCRIPT_LIB` | Platform default | Path to `fusionscript.so` / `fusionscript.dll`. |
| `RESOLVE_SCRIPT_API` | Platform default | Path to the Resolve scripting API directory. |
| `PYTHONPATH` | Platform default | Path to the Resolve scripting Modules directory. |
| `RESOLVE_MCP_TEMPLATES_DIR` | `<repo root>/templates/` | Custom path for the templates directory. |
| `RESOLVE_MCP_PANEL_PORT` | `8765` | HTTP port for the panel bridge server. |
| `RESOLVE_MCP_PANEL_DIR` | `<repo root>/panel/` | Custom path for panel static files. |

---

## Troubleshooting

### "Could not connect to DaVinci Resolve"
- DaVinci Resolve Studio must be running before the MCP server starts
- Check **Preferences → General → External scripting using** is set to **Local**
- Verify `RESOLVE_SCRIPT_LIB` points to the correct `fusionscript.so` / `.dll`

### "Failed to import DaVinciResolveScript"
- Check that `PYTHONPATH` points to the correct Modules directory
- macOS default: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/`

### "No active timeline"
- Open a project and ensure a timeline is active before calling timeline tools

### Tools not appearing in Claude Desktop
- Verify `uv` is installed: `uv --version`
- Restart Claude Desktop after editing `claude_desktop_config.json`
- Check Claude Desktop logs for MCP server startup errors

### Local transcription fails
- Check `ffmpeg` and `ffprobe` are installed: `ffmpeg -version`
- Models are downloaded on first use — ensure internet access for the initial download
- `mlx-whisper` requires Apple Silicon (M1 / M2 / M3 / M4 or later)

### Panel not loading
- Make sure `panel_server.py` is running: `uv run python -m resolve_claude_mcp.panel_server`
- Check the terminal for port conflicts — override with `RESOLVE_MCP_PANEL_PORT`
- The panel is browser-based and is not embedded inside Resolve

### Render settings changed after transcription
- `transcribe_timeline_audio` temporarily modifies render settings to export audio. Settings are restored after the job completes, but if the tool errors out mid-run, settings may be left in the audio-export state. Restore manually in the Deliver page.

### `generate_audio_visualizer_image` returns "NoneType object is not callable"
- This is a known issue with the FastMCP tool wrapper. The tool code itself works correctly — use the `execute_resolve_code` workaround documented in the [Audio section](#audio-visualizer-workaround).

### Audio Visualizer produces no output / ffmpeg not found
- Confirm ffmpeg is installed and on your PATH: `ffmpeg -version`
- On macOS: `brew install ffmpeg`

---

## Disclaimer

**USE AT YOUR OWN RISK.** This software is provided "as is", without warranty of any kind. By using resolve-mcp-studio you acknowledge:

- This is an **unofficial, third-party project** — not created by, affiliated with, endorsed by, or supported by Blackmagic Design or Anthropic
- AI agents can make mistakes: they may **modify, overwrite, or delete** your projects, timelines, clips, render queues, or files on disk
- `execute_resolve_code` runs **arbitrary Python** with full access to the Resolve API and your filesystem — inspect code before execution
- `screenshot` captures the Resolve window and **sends that image to Anthropic** for analysis — anything visible (client footage, unreleased material, passwords) may be transmitted
- **Always work on a backup** — use Resolve's built-in project backups (Project Manager → right-click → Backups)
- The authors accept **no liability** for lost work, corrupted projects, missed deadlines, wasted render time, or any other damages

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## Credits

- Fork of [barckley75/resolve-claude-mcp](https://github.com/barckley75/resolve-claude-mcp)
- Inspired by [coreymaypray/sloth-skill-tree](https://github.com/coreymaypray/sloth-skill-tree) (davinci-resolve-mcp skill)
- Subtitle reference: [Auto-Subs by Tom Moroney](https://tom-moroney.com/auto-subs/)
- Inspired by [BlenderMCP](https://github.com/ahujasid/blender-mcp) by Siddharth Ahuja
- Built with the [Model Context Protocol](https://modelcontextprotocol.io) by Anthropic
- Audio Visualizer image format by [sh4rk](https://sh4rkk.com/shop)
