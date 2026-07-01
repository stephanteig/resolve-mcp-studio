# DaVinci Resolve Scripting API Doc v20.3 — X-Raym Gist
## Source: X-Raym GitHub Gist (most actively maintained community copy)
## URL: https://gist.github.com/X-Raym/2f2bf453fc481b9cca624d7ca0e19de8
## Formatted HTML version: https://extremraym.com/cloud/resolve-scripting-doc/
## Last updated: 7 Oct 2025 (v20.3)
## Fetched: 2026-06-30
## NOTE: The full raw text is ~1000 lines. This file contains the API reference portion fetched.
## For the complete untruncated file, see your local README.txt after updating Resolve 21.

---

## Key info about this source

- This is the most actively maintained community copy of the Resolve Scripting API docs
- Uses GitHub Gist revision history to track diffs between Resolve versions
- 133 stars, 21 forks — de facto community reference
- The content is a direct copy-paste of the official README.txt bundled with Resolve Studio

## v20.3 API Classes (14 total)

1. **Resolve** — Root object. Page switching, version info, layout presets, render preset import/export, keyframe mode, Fairlight presets
2. **ProjectManager** — Database management, project CRUD, cloud projects, archive/restore
3. **Project** — Media pool access, timelines, gallery, render queue, settings, color groups, Fairlight presets
4. **MediaStorage** — Volume listing, file browsing, importing to media pool, mattes
5. **MediaPool** — Folder management, timeline creation, clip import/export, metadata, stereo clips, audio sync, selection
6. **Folder** — Clip listing, subfolder listing, export, transcription
7. **MediaPoolItem** — Metadata, markers, flags, colors, properties, proxy media, replace, transcription, audio mapping, mark in/out, growing file monitoring
8. **Timeline** — Tracks, markers, timecode, thumbnails, grades, export, generators, titles, stills, subtitles, scene detection, node graph, Dolby Vision, voice isolation, mark in/out
9. **TimelineItem** — Properties (pan/tilt/zoom/crop/opacity/composite), markers, flags, Fusion comps, versions, takes, grades, LUT/CDL, magic mask, stabilize, smart reframe, cache, voice isolation, linked items, track info, sidecar
10. **Gallery** — Album management (still albums and PowerGrade albums)
11. **GalleryStillAlbum** — Stills listing, labeling, import/export/delete
12. **GalleryStill** — No API functions (object type only)
13. **Graph** — Node count, LUT get/set, cache mode, node labels, tools in node, node enable, grade application, ARRI CDL
14. **ColorGroup** — Name, clips in timeline, pre/post clip node graphs

## Additional documented sections

- Keyframe Mode information (KEYFRAME_MODE_ALL=0, _COLOR=1, _SIZING=2)
- Cache Mode information (CACHE_AUTO_ENABLED=-1, _DISABLED=0, _ENABLED=1)
- Cloud Projects Settings (CLOUD_SETTING_* keys, CLOUD_SYNC_* modes)
- Audio Sync Settings (AUDIO_SYNC_WAVEFORM, _TIMECODE, channel settings)
- Auto Caption Settings (SUBTITLE_LANGUAGE, _CAPTION_PRESET, _CHARS_PER_LINE, _LINE_BREAK, _GAP)
- Render Settings (full dict of supported keys)
- Timeline Export Types (AAF, DRT, EDL, FCP XML, FCPXML 1.8-1.10, HDR10, CSV, TAB, Dolby Vision, OTIO, ALE)
- Timeline Item Properties (full list with value ranges and constants)
- Audio Mapping format (JSON structure)
- ExportLUT notes
- Deprecated functions
- Unsupported functions

## What v21 adds (not in this gist yet)

Per Blackmagic's release notes and upstream MCP server:
- IntelliSearch API
- Slate Analysis API  
- Speech Generator API
- Motion Blur Removal API
- Audio Classification API
- Speaker Detection API
- Background Task Control API
- OpenPage now likely accepts "photo" as pageName (needs verification)
- Possible new Photo Album-related methods (needs verification with local README.txt)
