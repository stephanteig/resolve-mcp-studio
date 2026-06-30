# CLAUDE.md — resolve-mcp-studio
> Handlingsklar referanse for Claude Code.
> Les hele filen — spesielt [Workflow-regler](#workflow-regler) og [Kodemønstre](#kodemønstre) — før du skriver én linje kode.

---

## Prosjekt

**Navn:** resolve-mcp-studio  
**Beskrivelse:** Lokal MCP-server som kobler Claude Desktop direkte til DaVinci Resolve Studio. Valgfritt browser-panel som frontend via localhost HTTP-bro.  
**Problem det løser:** Markers, transkripsjon, prosjektmaler og Media Pool-struktur er tidkrevende å gjøre manuelt i Resolve — dette automatiserer det via naturlig språk i Claude Desktop.  
**Versjon:** 1.0.0 (MVP levert)  
**Repo:** `stephanteig/resolve-mcp-studio` (fork av `barckley75/resolve-claude-mcp`)

---

## Platform

| Plattform | Prioritet | Krav |
|-----------|-----------|------|
| macOS (Apple Silicon) | Primær | macOS 13+, M1 eller nyere |
| Windows / Linux | Ikke testet | Kjerne-API-verktøy kan fungere, mlx-whisper gjør det ikke |

- DaVinci Resolve **Studio** kreves (ikke gratis-versjonen)
- Claude Desktop med MCP-støtte kreves
- Python 3.11+ — prosjektet bruker **uv** som pakkebehandler
- ffmpeg + ffprobe må være på PATH for transkripsjonsverktøy

---

## Tech Stack

| Komponent | Teknologi | Begrunnelse |
|-----------|-----------|-------------|
| MCP-server | Python + FastMCP (stdio) | Resolve scripting API er Python-basert; FastMCP var allerede i fork |
| Transkripsjon | mlx-whisper | Kjører lokalt på Apple Neural Engine, ingen sky, gratis |
| Panel | HTML + vanilla JS + CSS | Resolve workspace panel API støtter kun HTML — ingen React/Electron |
| Malsystem | JSON-filer i `templates/configs/` | Enkelt å redigere uten kode |
| Panel-bro | Python `http.server.ThreadingHTTPServer` | Binder kun til 127.0.0.1, ingen avhengigheter |
| Package manager | uv | Raskere enn pip, reproducerbare låste avhengigheter |

---

## Filstruktur

```
resolve-mcp-studio/
├── src/
│   └── resolve_claude_mcp/
│       ├── __init__.py
│       ├── server.py          ← MCP-server entry point (FastMCP, alle @mcp.tool())
│       ├── connection.py      ← ResolveConnection singleton + platform-defaults
│       ├── resolve_utils.py   ← Resolve API-objekt → JSON-serialisering
│       ├── markers.py         ← Timecode-parsing, fargekoding
│       ├── transcription.py   ← mlx-whisper, chunking, subtitle track I/O
│       ├── templates.py       ← JSON-basert prosjektmalsystem
│       ├── media_pool.py      ← Finder ↔ Media Pool bin/fil-sync
│       ├── clip_colors.py     ← Filnavn/metadata → klippkategori og farge
│       └── panel_server.py    ← Localhost HTTP-bro for panel
├── panel/
│   ├── index.html             ← Panel entry point
│   ├── panel.css
│   ├── panel.js
│   └── components/
│       ├── marker-editor.js
│       ├── transcription.js
│       └── status.js
├── templates/
│   ├── configs/
│   │   └── default.json       ← Standard prosjektmal-konfig
│   └── drp/
│       └── _TEMPLATE_.drp     ← Valgfri DRP-fil for import-baserte maler
├── assets/
├── pyproject.toml
├── uv.lock
├── CLAUDE.md                  ← denne filen
├── BRIEF.md
├── QUICKSTART.md
└── README.md
```

---

## Arkitektur

```
Claude AI (MCP Client)
    │  stdio
    ▼
server.py  (FastMCP — alle @mcp.tool())
    │
    ├── markers.py         parse_marker_list(), timecode_to_frame(), pick_color()
    ├── transcription.py   transcribe(), write_subtitle_track(), correct_subtitle_track()
    ├── templates.py       list_templates(), create_project_from_template()
    ├── media_pool.py      read_finder_structure(), sync_structure_to_media_pool()
    ├── clip_colors.py     propose_color()
    ├── resolve_utils.py   folder_to_dict(), timeline_item_to_dict(), safe_serialize()
    └── connection.py      ResolveConnection (singleton, RLock)
         │
         ▼
    fusionscript.so / .dll  (DaVinciResolveScript)
         │
         ▼
    DaVinci Resolve Studio (kjører lokalt)

Valgfritt:
panel_server.py  (127.0.0.1:8765, HTTP-bro)
    │  fetch()
    ▼
panel/index.html  (browser)
```

**Viktige designbeslutninger:**
- MCP-serveren bruker **stdio** — den kan ikke snakke HTTP med panelet
- Panelet bruker **HTTP** til panel_server.py, ikke direkte til MCP-serveren
- All Resolve API-tilgang serialiseres via `RLock` i `ResolveConnection` — Resolve scripting API er ikke thread-safe
- `transcribe_timeline_audio` endrer midlertidig render-innstillinger, rydder opp etter seg — men hvis verktøyet krasjer halvveis kan innstillingene bli stående

---

## Modul-referanse

### server.py

Entry point for FastMCP-serveren. Inneholder alle `@mcp.tool()`-dekoratorer. Importerer fra alle andre moduler.

**Interne hjelpefunksjoner (ikke MCP-verktøy):**

| Funksjon | Signatur | Beskrivelse |
|----------|----------|-------------|
| `_conn()` | `() -> ResolveConnection` | Henter tilkobling, kaster tydelig feil hvis Resolve ikke er tilgjengelig |
| `_require_timeline(conn)` | `(ResolveConnection) -> Timeline` | Returnerer aktiv timeline eller kaster RuntimeError med hjelpsom melding |
| `_get_timeline_item(track_type, track_index, item_index)` | `(str, int, int) -> TimelineItem` | Henter et spesifikt TimelineItem med indeksvalidering |
| `_ok(result, success_msg, fail_msg)` | `(Any, str, str) -> str` | Returnerer success_msg hvis result er truthy, ellers fail_msg |
| `_push_markers_to_panel(markers)` | `(list) -> bool` | Best-effort push av parsede markers til panel-broen. Feil er aldri fatal. |
| `_normalize_language(language)` | `(str\|None) -> str\|None` | Mapper "norsk"/"no" og "engelsk"/"en" til ISO 639-1-koder |
| `_render_timeline_audio(project)` | `(Project) -> str` | Renderer tidslinjens lyd til midlertidig WAV via render-køen. Returnerer filsti. 30 min timeout. |

**MCP-verktøy — oversikt:**

| Kategori | Verktøy |
|----------|---------|
| Prosjekt & navigasjon | `get_project_info`, `open_page`, `get_current_page` |
| Media Pool | `get_media_pool_structure`, `import_media`, `create_timeline` |
| Tidslinje | `get_current_timeline_info`, `get_timeline_items`, `append_to_timeline`, `set_current_timecode`, `get_current_timecode` |
| Markers (kjerneAPI) | `add_marker`, `get_markers` |
| Markers (studio) | `parse_and_preview_markers`, `set_markers_from_list` |
| Klipp-egenskaper | `get_timeline_item_properties`, `set_timeline_item_property` |
| Fargegradering | `get_node_graph`, `set_lut`, `set_cdl` |
| Rendering | `get_render_formats`, `get_render_settings`, `set_render_settings`, `add_render_job`, `start_rendering`, `get_render_status`, `stop_rendering` |
| AI / Neural Engine | `create_magic_mask`, `regenerate_magic_mask`, `smart_reframe`, `stabilize`, `detect_scene_cuts`, `create_subtitles_from_audio` |
| Lyd | `get_voice_isolation_state`, `set_voice_isolation_state` |
| Fusion | `get_fusion_comp_list`, `add_fusion_comp`, `import_fusion_comp`, `export_fusion_comp`, `load_fusion_comp`, `delete_fusion_comp`, `rename_fusion_comp`, `create_fusion_clip`, `insert_fusion_generator`, `insert_fusion_composition`, `insert_fusion_title` |
| Export | `export_timeline`, `export_current_frame` |
| Thumbnail / skjermbilde | `get_current_thumbnail`, `screenshot` |
| Lokal transkripsjon | `transcribe_audio`, `transcribe_and_add_subtitles`, `export_srt`, `list_whisper_models` |
| Subtitle tracks (studio) | `get_timeline_subtitle_tracks`, `transcribe_timeline_audio`, `write_subtitles_to_resolve` |
| Prosjektmaler (studio) | `list_project_templates`, `create_project_from_template` |
| Media Pool sync (studio) | `sync_finder_folder_to_media_pool` |
| Auto klippfarge (studio) | `auto_color_clips` |
| Kodekjøring | `execute_resolve_code` |

---

### markers.py

Parser fritekst med tidskoder til strukturerte marker-dicts. Brukes av `parse_and_preview_markers` og panel-broen.

**Konstanter:**

| Navn | Verdi | Beskrivelse |
|------|-------|-------------|
| `VALID_MARKER_COLORS` | `set[str]` | De 17 fargenavnene `Timeline.AddMarker()` aksepterer |
| `DEFAULT_COLOR` | `"Blue"` | Fallback-farge når ingen nøkkelord matcher |

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `pick_color` | `(text: str) -> str` | `str` | Velger markerfarge basert på nøkkelord i teksten. Substring-matching — "stikkord" matcher "stikk". |
| `timecode_to_frame` | `(timecode: str, fps: float) -> int` | `int` | Konverterer `MM:SS`, `HH:MM:SS` eller `HH:MM:SS:FF` til absolutt frame-nummer. Kaster `ValueError` på ugyldige komponenter. |
| `frame_to_timecode` | `(frame: int, fps: float) -> str` | `str` | Konverterer frame-nummer til `HH:MM:SS:FF`. Bruker non-drop-frame matematikk. |
| `parse_marker_list` | `(text: str, fps: float) -> Tuple[List[Dict], List[str]]` | `(markers, skipped)` | Parser fritekst-blokk til `(markers, skipped_lines)`. Markers sorteres etter frame. |

**Støttede linjeformater:**
```
MM:SS beskrivelse           02:15 fjern pause
HH:MM:SS beskrivelse        01:02:15 klipp her
HH:MM:SS:FF beskrivelse     01:02:15:12 pling inn
- MM:SS beskrivelse         valgfri listebullet
* MM:SS — beskrivelse       valgfri separator etter tidskode
```

**Automatisk fargekoding** (første match vinner):

| Farge | Nøkkelord |
|-------|-----------|
| Red | `feil`, `fjern`, `problem` |
| Orange | `klipp`, `cut`, `edit` |
| Yellow | `lyd`, `musikk`, `audio` |
| Cyan | `pling`, `jingle`, `stikk` |
| Green | `intro`, `outro` |
| Blue | (default) |

---

### transcription.py

Lokal lydtranskripsjon med mlx-whisper. Lange filer deles automatisk i 5-minutters chunks via ffmpeg.

**Konstanter:**

| Navn | Verdi | Beskrivelse |
|------|-------|-------------|
| `WHISPER_MODELS` | `dict` | Kortnavn → HuggingFace repo-sti for `tiny`, `base`, `small`, `medium`, `large`, `turbo` |
| `DEFAULT_MODEL` | `"turbo"` | Standardmodell |
| `CHUNK_SECONDS` | `300` | Chunk-varighet i sekunder (5 min) |

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `transcribe` | `(file_path, model, language, word_timestamps, initial_prompt)` | `list[dict]` | Hoved-transcribe-funksjon. Splitter lange filer med ffmpeg, stitcher resultater. Returnerer `[{start, end, text}]`. |
| `transcribe_audio` | `(file_path, model, language)` | `(str, list[dict])` | Wrapper brukt av MCP-verktøy. Returnerer `(formatert_tekst, segmenter)`. |
| `segments_to_srt` | `(segments: list) -> str` | `str` | Konverterer segmenter til gyldig SRT-format med 1-basert nummerering og `HH:MM:SS,mmm`-tidsstempler. |
| `get_subtitle_tracks` | `(timeline) -> list` | `list[dict]` | Returnerer alle subtitle-tracks: `{index, name, item_count, enabled}`. |
| `get_subtitle_track_segments` | `(timeline, track_index: int) -> list` | `list[dict]` | Returnerer subtitle-elementer fra én track: `{start, end, text, index}`. Tider i sekunder. |
| `write_subtitle_track` | `(timeline, segments, track_name)` | `dict` | Skriver segmenter som ny subtitle-track. SRT → temp-fil → Media Pool import → legg til timeline. |
| `correct_subtitle_track` | `(timeline, track_index, corrected_segments)` | `dict` | Erstatter tekst i eksisterende subtitle-track uten å endre timing. Skriver ny track `"<navn> (corrected)"`, deaktiverer originalen. |
| `map_transcription_to_segments` | `(transcription_segs, existing_segs)` | `list[dict]` | Mapper transkripsjonsresultater til eksisterende subtitle-timing via overlap-scoring. Returnerer `{start, end, text, original_text}`. |

**ffmpeg-avhengighet:** `ffprobe` brukes til å lese filvarighet; `ffmpeg` brukes til å skjære ut chunks som 16 kHz mono PCM WAV. Begge må være på PATH.

---

### templates.py

JSON-basert prosjektmalsystem. Leser konfigs fra `templates/configs/` og valgfrie `.drp`-filer fra `templates/drp/`.

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `list_templates` | `() -> list` | `list[dict]` | Scanner `templates/configs/*.json`. Returnerer `{id, name, resolution, fps, timelines, bins, has_drp}`. |
| `create_project_from_template` | `(template_name: str, project_name: str) -> dict` | `dict` | Oppretter nytt Resolve-prosjekt. Hvis config har `"drp"`-nøkkel: importer DRP og gi nytt navn. Ellers: bygg fra scratch (resolution, fps, bins, timelines). Alt som ikke kan settes rapporteres i `warnings` istedenfor å feile. |

**Mal-konfig format** (`templates/configs/<id>.json`):

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

9:16-timelines får automatisk rotert oppløsning (f.eks. 2160×3840 fra 3840×2160).

**Env-override:** Sett `RESOLVE_MCP_TEMPLATES_DIR` til absolutt sti for å bruke alternativ templates-mappe.

---

### media_pool.py

Synkroniserer Finder-mappestruktur til Media Pool-bins.

**Konstanter:**

`MEDIA_EXTENSIONS` — sett av filendelser som regnes som importerbar media: video (`.mp4`, `.mov`, `.mxf`, `.avi`, `.mkv`, `.r3d`, `.braw`, `.arri`), lyd (`.wav`, `.aif`, `.aiff`, `.mp3`, `.m4a`), bilde/RAW (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.dpx`, `.exr`, `.dng`).

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `read_finder_structure` | `(root_path: str) -> dict` | `dict` | Leser mappestruktur rekursivt fra disk. Returnerer nestet `{name, path, subfolders, files}`. Skjulte filer (punktprefiks) ekskluderes. |
| `sync_structure_to_media_pool` | `(structure, media_pool, parent_folder)` | `dict` | Oppretter bins rekursivt og importerer mediefiler. Returnerer `{bins_created, bins_reused, files_imported, files_skipped, files_failed}`. |

**Idempotens:** Sjekker eksisterende bins via `GetSubFolderList()` — gjenbruker bin med samme navn istedenfor å duplisere. Sjekker eksisterende klipp via `File Path`-egenskapen — hopper over filer som allerede er importert.

---

### connection.py

Administrerer tilkoblingen til DaVinci Resolve scripting API.

**Klasse: `ResolveConnection`**

| Metode | Signatur | Returnerer | Beskrivelse |
|--------|----------|------------|-------------|
| `__init__` | `()` | — | Konfigurerer `sys.path` og miljøvariabler. Bruker platform-spesifikke defaults hvis env-vars ikke er satt. Laster `DaVinciResolveScript` og kaller `scriptapp("Resolve")`. |
| `get_resolve` | `() -> Resolve` | `Resolve` | Returnerer Resolve-API-objekt. Kaster `RuntimeError` hvis ikke tilkoblet. |
| `get_project_manager` | `() -> ProjectManager` | `ProjectManager` | Returnerer Resolve Project Manager. |
| `get_project` | `() -> Project` | `Project` | Returnerer åpent prosjekt. Kaster `RuntimeError` hvis intet prosjekt er åpent. |
| `get_current_timeline` | `() -> Timeline\|None` | `Timeline` eller `None` | Returnerer aktiv timeline, eller `None`. |
| `get_media_pool` | `() -> MediaPool` | `MediaPool` | Returnerer Media Pool for aktivt prosjekt. |
| `get_media_storage` | `() -> MediaStorage` | `MediaStorage` | Returnerer Resolve media storage manager. |
| `execute_code` | `(code: str, extra_namespace: dict) -> Any` | `Any` | Kjører Python-kode med Resolve API-objekter forhåndslastet i namespace. |
| `check_health` | `() -> bool` | `bool` | Forsøker et lett API-kall for å verifisere at tilkoblingen er live. |

**Modul-funksjon:**

| Funksjon | Beskrivelse |
|----------|-------------|
| `get_resolve_connection()` | Returnerer global singleton `ResolveConnection`. Oppretter ved første kall. |

**Platform-defaults for `RESOLVE_SCRIPT_LIB`:**

| Platform | Standard sti |
|----------|-------------|
| macOS | `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so` |
| Windows | `C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll` |
| Linux | `/opt/resolve/libs/Fusion/fusionscript.so` |

---

### resolve_utils.py

Serialiseringshjelpere som konverterer Resolve API-objekter (ugjennomsiktige C++-wrappers) til JSON-serialiserbare Python-dicts.

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `folder_to_dict` | `(folder, max_depth, max_clips, depth)` | `dict` | Konverterer `MediaPoolFolder` rekursivt til dict med `name`, `subfolders`, `clips`. |
| `clip_to_dict` | `(clip)` | `dict` | Konverterer `MediaPoolItem` til fullt dict med alle klippegenskaper fra `GetClipProperty()`. |
| `clip_to_dict_brief` | `(clip)` | `dict` | Som `clip_to_dict` men returnerer kun navn, varighet, fps og filsti. Raskere for store media pools. |
| `timeline_to_dict` | `(timeline)` | `dict` | Konverterer `Timeline` til dict: navn, fps, oppløsning, start/slutt-timecode, spor-telleere, markers. |
| `timeline_item_to_dict` | `(item, index: int)` | `dict` | Konverterer `TimelineItem` til dict: 0-basert index, navn, start/slutt-frame, varighet, media pool-referanse. |
| `timeline_item_full_dict` | `(item)` | `dict` | Som over men inkluderer alle egenskaper fra `GetProperty()`. |
| `node_graph_to_dict` | `(item)` | `dict` | Henter fargegradering-nodegraf-info fra `TimelineItem` på Color-siden. |
| `thumbnail_to_png_bytes` | `(item)` | `bytes` | Ber om thumbnail fra Color-siden via `GrabStill()` og konverterer base64 RGB-data til PNG-bytes. |
| `safe_serialize` | `(obj) -> Any` | `Any` | Gjør et objekt rekursivt JSON-serialiserbart. Ikke-serialiserbare verdier konverteres til `repr()`. |

**Intern hjelper:** `_safe(fn, *args, default=None)` — wrapper rundt Resolve API-kall med try/except. Returnerer `default` ved feil.

---

### clip_colors.py

Automatisk klipp-kategorisering for `auto_color_clips`-verktøyet.

**Kategorier og deteksjonsregler:**

| Kategori | Filendelse-triggere | Nøkkelord i filnavn | Klippfarge |
|----------|--------------------|--------------------|------------|
| `drone` | — | `DJI`, `drone`, `mavic`, `phantom`, `air2` | Yellow |
| `talking_head` | — | `interview`, `intervju`, `sit-down`, `talking` | Blue |
| `broll` | — | `broll`, `b-roll`, `cutaway`, `handheld` | Green |
| `music_audio` | `.mp3`, `.wav`, `.aif`, `.aiff`, `.m4a` | `music`, `lyd`, `musikk` | Pink |
| `graphics_stills` | `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.dpx`, `.exr` | `graphic`, `logo`, `title` | Purple |
| `uncategorized` | Ingen regel matchet | — | Beige |

**Funksjoner:**

| Funksjon | Signatur | Returnerer | Beskrivelse |
|----------|----------|------------|-------------|
| `propose_color` | `(clip: MediaPoolItem) -> (str, str, str)` | `(kategori, farge, grunn)` | Returnerer tre-tuppel for ett klipp. `grunn` forklarer hvilken regel som trigget. |

---

### panel_server.py

Localhost HTTP-bro mellom browser-panelet og Resolve scripting API.

**Start:**
```bash
uv run python -m resolve_claude_mcp.panel_server
# Åpne http://127.0.0.1:8765
```

**HTTP API-endepunkter:**

| Metode | Sti | Request body | Respons | Beskrivelse |
|--------|-----|-------------|---------|-------------|
| `GET` | `/api/status` | — | `{connected, project, timeline}` | Tilkoblingsstatus og aktivt prosjekt/timeline |
| `POST` | `/api/markers/parse` | `{text, fps?}` | `{project, timeline, fps, markers, skipped_lines}` | Parser fritekst-tidskoder til strukturerte markers |
| `POST` | `/api/markers/set` | `{markers}` | `{set, failures}` | Setter godkjent marker-liste i aktiv timeline |
| `GET` | `/api/subtitle-tracks` | — | `{tracks}` | Lister subtitle-tracks på aktiv timeline |
| `POST` | `/api/transcribe` | `{language, output_mode, track_index?}` | `{job_id}` | Starter transkripsjonsjobb (asynkron, bakgrunnstråd) |
| `GET` | `/api/transcribe/<job_id>` | — | `{status, result?, error?}` | Poller transkripsjonsjobb. Status: `"running"`, `"done"`, `"error"` |
| `POST` | `/api/subtitles/write` | `{segments, output_mode, track_name?, track_index?}` | `{status, count}` | Skriver gjennomgåtte segmenter til timeline |

**Sikkerhet:** Binder kun til 127.0.0.1. CORS tillates fra localhost-opprinnelser og `file://` (origin `"null"`).

**Env-variabler:**

| Variabel | Default | Beskrivelse |
|----------|---------|-------------|
| `RESOLVE_MCP_PANEL_PORT` | `8765` | HTTP-port for panel-broen |
| `RESOLVE_MCP_PANEL_DIR` | `<repo root>/panel/` | Alternativ sti til panel-filer |

---

## Workflow-regler

Disse reglene er absolutte og ikke forhandlingsbare:

- **Alle kodeendringer via Pull Request** — ingen direkte commits til `main`
- **Branch-navn:** `feature/beskrivelse` eller `fix/beskrivelse`
- **Commit-meldinger:** kortfattede og beskrivende på engelsk
- **Før du oppretter en fil:** sjekk om den allerede eksisterer med `ls` eller `Read`
- **Ikke endre eksisterende MCP-verktøy** uten eksplisitt instruksjon fra bruker
- **Ved feil:** forsøk å fikse selv (maks 2 forsøk), rapporter deretter tydelig

---

## Kodemønstre

### Slik ser et typisk MCP-verktøy ut

```python
@mcp.tool()
def get_timeline_subtitle_tracks() -> str:
    """Lists all subtitle tracks on the current timeline."""
    conn = _conn()
    timeline = _require_timeline(conn)
    project = conn.get_project()
    tracks = _get_subtitle_tracks(timeline)
    return json.dumps({
        "project": project.GetName(),
        "timeline": timeline.GetName(),
        "tracks": tracks,
    })
```

Mønster:
1. `_conn()` — hent tilkobling
2. `_require_timeline(conn)` — krev aktiv timeline (eller hopp over dette trinnet)
3. Kall modulhjelper (markers, transcription, osv.)
4. Returner `json.dumps({...})` — alltid JSON-streng

### Feilhåndtering

```python
try:
    result = timeline.SomeApiCall()
    if not result:
        return "Failed: SomeApiCall returned falsy"
    return json.dumps({"status": "ok", "result": result})
except Exception as e:
    return f"Error: {e}"
```

Ikke la exceptions propagere — MCP-klienten håndterer dem dårlig. Returner alltid en streng.

### Indeksering

- **Timeline tracks:** 1-basert (`track_index=1` er første video-spor)
- **Timeline items innen spor:** 0-basert (`item_index=0` er første klipp)
- **Fusion compositions:** 1-basert (`comp_index=1`)
- **Subtitle tracks:** 1-basert (`track_index=1`)
- **Node graph:** 1-basert (`node_index=1`)

### Verktøy som krever spesifikk side

- `get_current_thumbnail()` — krever Color-siden med valgt klipp
- `get_node_graph()` — krever Color-siden
- `set_lut()` / `set_cdl()` — krever Color-siden
- `screenshot()` — macOS-only, krever skjermopptakstillatelse til Claude Desktop

---

## Avhengigheter

```toml
# pyproject.toml — nøkkelavhengigheter
[project]
dependencies = [
    "mcp[cli]",          # FastMCP / MCP protokoll
    "mlx-whisper",       # Lokal transkripsjon (Apple Silicon)
    "numpy",             # mlx-whisper avhengighet
    "pillow",            # PNG-konvertering for thumbnails
]
```

Ekstern avhengighet som **ikke** er i pyproject.toml:
- `ffmpeg` og `ffprobe` — må installeres via Homebrew: `brew install ffmpeg`
- `DaVinciResolveScript` — leveres av Resolve-installasjonen, injiseres via PYTHONPATH

---

## Miljøvariabler

| Variabel | Default | Beskrivelse |
|----------|---------|-------------|
| `RESOLVE_SCRIPT_LIB` | Platform-default | Sti til `fusionscript.so` / `.dll` |
| `RESOLVE_SCRIPT_API` | Platform-default | Sti til Resolve scripting API-mappe |
| `PYTHONPATH` | Platform-default | Sti til Resolve scripting Modules-mappe |
| `RESOLVE_MCP_TEMPLATES_DIR` | `<repo root>/templates/` | Alternativ templates-mappe |
| `RESOLVE_MCP_PANEL_PORT` | `8765` | HTTP-port for panel-broen |
| `RESOLVE_MCP_PANEL_DIR` | `<repo root>/panel/` | Alternativ sti til panel-filer |

---

## Definition of Done (MVP levert ✓)

- [x] `parse_and_preview_markers` parser fritekst-liste korrekt til strukturert JSON
- [x] `set_markers_from_list` setter markers i Resolve med riktig timecode
- [x] Marker-editor i panel viser, redigerer og sender markers til Resolve
- [x] Transkripsjon med mlx-whisper fungerer for norsk og engelsk
- [x] Ny subtitle-track kan skrives til aktiv timeline i Resolve
- [x] Korreksjonsmodus retter tekst uten å endre timing
- [x] `create_project_from_template` oppretter prosjekt med korrekt struktur
- [x] `sync_finder_folder_to_media_pool` oppretter bins og importerer filer
- [x] Browser-panel fungerer for marker-editor og transkripsjon
- [x] Alle MCP-verktøy er dokumentert i README med parameter-tabeller
- [x] Ingen hardkodede stier — konfig eller Resolve API

---

## Credits

- Fork av [barckley75/resolve-claude-mcp](https://github.com/barckley75/resolve-claude-mcp)
- Inspirert av [coreymaypray/sloth-skill-tree](https://github.com/coreymaypray/sloth-skill-tree) (davinci-resolve-mcp skill)
- Subtitle-referanse: [Auto-Subs av Tom Moroney](https://tom-moroney.com/auto-subs/)
- Inspirert av [BlenderMCP](https://github.com/ahujasid/blender-mcp) av Siddharth Ahuja

---

*Stephan Teig — sist oppdatert 2026-06-30*
