"""
DaVinci Resolve MCP Server

A FastMCP server that exposes DaVinci Resolve Studio's scripting API
as MCP tools, allowing Claude to control Resolve via natural language.
"""

from mcp.server.fastmcp import FastMCP, Image
import json
import logging
import os
import subprocess
import tempfile
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional

from .connection import get_resolve_connection, ResolveConnection
from .transcription import (
    transcribe as _transcribe,
    transcribe_audio as _transcribe_audio,
    segments_to_srt,
    get_subtitle_tracks as _get_subtitle_tracks,
    get_subtitle_track_segments as _get_subtitle_track_segments,
    write_subtitle_track as _write_subtitle_track,
    correct_subtitle_track as _correct_subtitle_track,
    map_transcription_to_segments as _map_transcription_to_segments,
    WHISPER_MODELS,
    DEFAULT_MODEL,
)
from .markers import (
    parse_marker_list,
    VALID_MARKER_COLORS,
    DEFAULT_COLOR as DEFAULT_MARKER_COLOR,
)
from .templates import (
    list_templates as _list_templates,
    create_project_from_template as _create_project_from_template,
)
from .media_pool import (
    read_finder_structure as _read_finder_structure,
    sync_structure_to_media_pool as _sync_structure_to_media_pool,
)
from .clip_colors import propose_color as _propose_clip_color
from .resolve_utils import (
    folder_to_dict,
    clip_to_dict,
    clip_to_dict_brief,
    timeline_to_dict,
    timeline_item_to_dict,
    timeline_item_full_dict,
    node_graph_to_dict,
    thumbnail_to_png_bytes,
    safe_serialize,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ResolveMCP")


# ── Helpers ──

def _conn() -> ResolveConnection:
    """Shorthand that gives a clear error when Resolve isn't reachable."""
    return get_resolve_connection()


def _require_timeline(conn: ResolveConnection):
    """Return the current timeline or raise with a helpful message."""
    tl = conn.get_current_timeline()
    if tl is None:
        raise RuntimeError(
            "No active timeline. Create or open a timeline first."
        )
    return tl


def _get_timeline_item(track_type: str, track_index: int, item_index: int):
    """Get a specific TimelineItem from the current timeline."""
    conn = _conn()
    timeline = _require_timeline(conn)

    items = timeline.GetItemListInTrack(track_type, track_index)
    if not items:
        raise RuntimeError(
            f"No items found on {track_type} track {track_index}. "
            f"Check track_type ('video'/'audio'/'subtitle') and track_index (1-based)."
        )
    if item_index < 0 or item_index >= len(items):
        raise RuntimeError(
            f"item_index {item_index} out of range — track has {len(items)} item(s) (0-{len(items) - 1})"
        )
    return items[item_index]


def _ok(result: Any, success_msg: str, fail_msg: str) -> str:
    """Return success_msg if result is truthy, else fail_msg."""
    return success_msg if result else fail_msg


def _find_clip_in_media_pool(conn: ResolveConnection, clip_name: str):
    """Recursively search Media Pool for a clip by name. Returns MediaPoolItem or None."""
    def _search(folder):
        for clip in (folder.GetClipList() or []):
            try:
                if clip.GetName() == clip_name:
                    return clip
            except Exception:
                pass
        for sub in (folder.GetSubFolderList() or []):
            result = _search(sub)
            if result:
                return result
        return None
    root = conn.get_media_pool().GetRootFolder()
    return _search(root)


def _find_folder_in_media_pool(conn: ResolveConnection, folder_name: str):
    """Recursively search Media Pool for a folder by name. Returns Folder or None."""
    def _search(folder):
        try:
            if folder.GetName() == folder_name:
                return folder
        except Exception:
            pass
        for sub in (folder.GetSubFolderList() or []):
            result = _search(sub)
            if result:
                return result
        return None
    root = conn.get_media_pool().GetRootFolder()
    # Check root's subfolders (root itself usually has no user-facing name)
    for sub in (root.GetSubFolderList() or []):
        result = _search(sub)
        if result:
            return result
    return None


def _get_gallery_album(conn: ResolveConnection, album_name: str):
    """Find a GalleryStillAlbum by name. Returns album or None."""
    gallery = conn.get_resolve().GetProjectManager().GetCurrentProject().GetGallery()
    if not gallery:
        return None
    albums = gallery.GetGalleryStillAlbums() or []
    for album in albums:
        try:
            if gallery.GetAlbumName(album) == album_name:
                return album
        except Exception:
            pass
    return None


# ── Lifespan ──

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    try:
        logger.info("ResolveMCP server starting up")
        try:
            conn = get_resolve_connection()
            project = conn.get_project()
            logger.info("Connected to Resolve — project: %s", project.GetName())
        except Exception as e:
            logger.warning("Could not connect to Resolve on startup: %s", e)
            logger.warning("Tools will attempt to connect when called.")
        yield {}
    finally:
        logger.info("ResolveMCP server shut down")


mcp = FastMCP("ResolveMCP", lifespan=server_lifespan)


# ═══════════════════════════════════════════════════════════════════
#  PROJECT & NAVIGATION
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_project_info() -> str:
    """
    Get information about the current DaVinci Resolve project.

    Returns project name, settings (frame rate, resolution),
    timeline count, current page, and version info.
    """
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        project = conn.get_project()

        info = {
            "project_name": project.GetName(),
            "resolve_version": resolve.GetVersionString(),
            "current_page": resolve.GetCurrentPage(),
            "timeline_count": project.GetTimelineCount(),
        }

        for key in (
            "timelineFrameRate",
            "timelineResolutionWidth",
            "timelineResolutionHeight",
            "timelinePlaybackFrameRate",
        ):
            val = project.GetSetting(key)
            if val:
                info[key] = val

        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def open_page(page: str) -> str:
    """
    Switch to a specific page in DaVinci Resolve.

    Parameters:
    - page: One of "media", "cut", "edit", "fusion", "color", "fairlight", "deliver"
    """
    valid_pages = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")
    if page not in valid_pages:
        return f"Invalid page '{page}'. Must be one of: {', '.join(valid_pages)}"
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        success = resolve.OpenPage(page)
        return _ok(success, f"Switched to {page} page", f"Failed to switch to {page} page")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_current_page() -> str:
    """Get the currently active page in DaVinci Resolve."""
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        page = resolve.GetCurrentPage()
        return page or "unknown"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  MEDIA POOL
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_media_pool_structure(max_depth: int = 3, max_clips: int = 50) -> str:
    """
    Get the folder/clip structure of the media pool.

    Parameters:
    - max_depth: Maximum folder recursion depth (default: 3)
    - max_clips: Maximum clips to list per folder (default: 50)
    """
    try:
        conn = _conn()
        mp = conn.get_media_pool()
        root = mp.GetRootFolder()
        if root is None:
            return "Error: Could not get root folder from media pool"
        structure = folder_to_dict(root, max_depth, max_clips)
        return json.dumps(structure, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def import_media(file_paths: List[str]) -> str:
    """
    Import media files into the current media pool folder.

    Parameters:
    - file_paths: List of absolute file paths to import
    """
    try:
        conn = _conn()
        mp = conn.get_media_pool()
        items = mp.ImportMedia(file_paths)
        if items:
            names = [item.GetName() for item in items if item]
            return json.dumps({"imported": len(names), "clips": names}, indent=2)
        return "No media was imported. Check that file paths exist and are supported formats."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_timeline(name: str) -> str:
    """
    Create a new empty timeline in the current project.

    Parameters:
    - name: Name for the new timeline
    """
    try:
        conn = _conn()
        mp = conn.get_media_pool()
        timeline = mp.CreateEmptyTimeline(name)
        if timeline:
            return json.dumps(timeline_to_dict(timeline), indent=2)
        return f"Failed to create timeline '{name}'. Name may already exist."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_current_timeline_info() -> str:
    """Get detailed information about the current timeline."""
    try:
        conn = _conn()
        timeline = conn.get_current_timeline()
        if timeline is None:
            return "No active timeline. Create or open a timeline first."
        return json.dumps(timeline_to_dict(timeline), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_timeline_items(track_type: str = "video", track_index: int = 1) -> str:
    """
    List all clips/items on a specific track of the current timeline.

    Parameters:
    - track_type: "video", "audio", or "subtitle" (default: "video")
    - track_index: 1-based track index (default: 1)
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)

        items = timeline.GetItemListInTrack(track_type, track_index)
        if not items:
            return f"No items on {track_type} track {track_index}"

        result = []
        for i, item in enumerate(items):
            d = timeline_item_to_dict(item)
            d["index"] = i
            result.append(d)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def append_to_timeline(clip_names: List[str]) -> str:
    """
    Append media pool clips to the current timeline by name.

    Parameters:
    - clip_names: List of clip names to append (must exist in the current media pool folder)
    """
    try:
        conn = _conn()
        mp = conn.get_media_pool()
        folder = mp.GetCurrentFolder()
        if folder is None:
            return "Error: Could not get current media pool folder"

        all_clips = folder.GetClipList() or []
        name_to_clip = {}
        for clip in all_clips:
            n = clip.GetName()
            if n:
                name_to_clip[n] = clip

        clips_to_add = []
        not_found = []
        for name in clip_names:
            if name in name_to_clip:
                clips_to_add.append(name_to_clip[name])
            else:
                not_found.append(name)

        if not clips_to_add:
            available = list(name_to_clip.keys())[:20]
            return (
                f"No matching clips found. Not found: {not_found}\n"
                f"Available clips in current folder: {available}"
            )

        result = mp.AppendToTimeline(clips_to_add)
        output: dict = {"appended": len(clips_to_add)}
        if not_found:
            output["not_found"] = not_found
        if result:
            output["timeline_items"] = [item.GetName() for item in result if item]
        return json.dumps(output, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_marker(
    frame_id: int,
    color: str,
    name: str,
    note: str = "",
    duration: int = 1,
    custom_data: str = "",
) -> str:
    """
    Add a marker to the current timeline.

    Parameters:
    - frame_id: Frame position for the marker
    - color: Marker color ("Red", "Orange", "Yellow", "Green", "Cyan", "Blue",
             "Purple", "Pink", "Fuchsia", "Rose", "Lavender", "Sky", "Mint",
             "Lemon", "Sand", "Cocoa", "Cream")
    - name: Marker name
    - note: Optional note text
    - duration: Marker duration in frames (default: 1)
    - custom_data: Optional custom data string
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        success = timeline.AddMarker(frame_id, color, name, note, duration, custom_data)
        return _ok(success, f"Marker '{name}' added at frame {frame_id}", "Failed to add marker")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_markers() -> str:
    """Get all markers on the current timeline."""
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        markers = timeline.GetMarkers()
        if not markers:
            return "No markers on timeline"
        return json.dumps({str(k): v for k, v in markers.items()}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


def _push_markers_to_panel(markers: List[Dict[str, Any]]) -> bool:
    """Best-effort push of parsed markers to the panel bridge, if running.

    The panel bridge (panel_server.py) is a separate localhost process —
    when it's up, pushed markers appear in the panel's marker editor
    within its 2s poll interval. Failure is never an error: the panel
    is optional.
    """
    import urllib.request
    port = int(os.getenv("RESOLVE_MCP_PANEL_PORT", "8765"))
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/markers/load",
        data=json.dumps({"markers": markers}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            return response.status == 200
    except Exception as e:
        logger.debug("Panel marker push skipped: %s", e)
        return False


@mcp.tool()
def parse_and_preview_markers(text: str, fps: Optional[float] = None) -> str:
    """
    Parse a free-text list of timecodes + descriptions into structured
    markers, ready for review BEFORE they are written to the timeline.

    If the panel bridge is running, the parsed markers are also pushed to
    the panel's marker editor for visual review/editing (the response
    field "pushed_to_panel" tells whether that happened).

    Supported line formats (description follows the timecode):
    - "MM:SS text"        e.g. "02:15 fjern pause"
    - "HH:MM:SS text"     e.g. "01:02:15 klipp her"
    - "HH:MM:SS:FF text"  e.g. "01:02:15:12 pling inn"

    Three components are always interpreted as HH:MM:SS; frame-accurate
    positions require the explicit four-component form. Colors are
    auto-assigned from keywords in the description (e.g. "fjern" → Red,
    "klipp" → Orange, "lyd" → Yellow, "pling"/"jingle" → Cyan,
    "intro"/"outro" → Green, otherwise Blue).

    Parameters:
    - text: Raw text, one marker per line
    - fps: Frame rate for timecode conversion. If omitted, read from the
      current timeline.

    Returns JSON with the parsed markers, any skipped (unparseable) lines,
    and the active project + timeline name so the user can confirm the
    target before calling set_markers_from_list.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = _require_timeline(conn)

        if fps is None:
            fps_setting = timeline.GetSetting("timelineFrameRate")
            if not fps_setting:
                return "Error: could not read frame rate from timeline — pass fps explicitly"
            fps = float(fps_setting)

        markers, skipped = parse_marker_list(text, fps)
        pushed = _push_markers_to_panel(markers) if markers else False
        return json.dumps({
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "fps": fps,
            "marker_count": len(markers),
            "markers": markers,
            "skipped_lines": skipped,
            "pushed_to_panel": pushed,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_markers_from_list(markers: List[Dict[str, Any]]) -> str:
    """
    Write an approved list of markers to the current timeline.

    Intended to be called with the (possibly user-edited) marker list from
    parse_and_preview_markers. Each marker dict:
    - frame (int, required): frame position relative to timeline start
    - name (str, required): marker name
    - color (str, optional): a valid Resolve marker color, default "Blue"
    - note (str, optional): marker note
    - duration (int, optional): duration in frames, default 1

    Returns a JSON report with the project and timeline name (so the user
    can confirm where the markers landed), how many were set, and any
    failures with the reason.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = _require_timeline(conn)

        set_count = 0
        failures = []
        for i, marker in enumerate(markers):
            frame = marker.get("frame")
            name = marker.get("name", "")
            if not isinstance(frame, int) or frame < 0:
                failures.append({"index": i, "marker": name, "reason": f"invalid frame: {frame!r}"})
                continue

            color = marker.get("color") or DEFAULT_MARKER_COLOR
            if color not in VALID_MARKER_COLORS:
                failures.append({"index": i, "marker": name, "reason": f"invalid color: {color!r}"})
                continue

            note = marker.get("note", "")
            duration = marker.get("duration", 1)
            success = timeline.AddMarker(frame, color, name, note, duration, "")
            if success:
                set_count += 1
            else:
                failures.append({
                    "index": i, "marker": name,
                    "reason": f"AddMarker failed at frame {frame} "
                              "(marker may already exist at this frame)",
                })

        return json.dumps({
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "requested": len(markers),
            "set": set_count,
            "failures": failures,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_current_timecode(timecode: str) -> str:
    """
    Move the playhead to a specific timecode.

    Parameters:
    - timecode: Timecode string in "HH:MM:SS:FF" format
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        success = timeline.SetCurrentTimecode(timecode)
        return _ok(success, f"Playhead moved to {timecode}", f"Failed to set timecode to {timecode}")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_current_timecode() -> str:
    """Get the current playhead timecode."""
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        tc = timeline.GetCurrentTimecode()
        return tc or "Could not read timecode"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE ITEM PROPERTIES
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_timeline_item_properties(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Get all properties of a specific timeline item.

    Parameters:
    - track_type: "video", "audio", or "subtitle" (default: "video")
    - track_index: 1-based track index (default: 1)
    - item_index: 0-based index of the item in the track (default: 0)
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        return json.dumps(timeline_item_full_dict(item), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_timeline_item_property(
    property_key: str,
    property_value: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Set a property on a specific timeline item.

    Parameters:
    - property_key: Property name (e.g. "Pan", "Tilt", "ZoomX", "ZoomY", "Opacity",
                    "CropLeft", "CropRight", "CropTop", "CropBottom", "RotationAngle",
                    "FlipX", "FlipY", "CompositeMode", "RetimeProcess", "Scaling", etc.)
    - property_value: Value to set (will be auto-converted to appropriate type)
    - track_type: "video", "audio", or "subtitle" (default: "video")
    - track_index: 1-based track index (default: 1)
    - item_index: 0-based index of the item in the track (default: 0)
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)

        # Auto-convert value types
        value: Any = property_value
        try:
            value = float(property_value)
            if value == int(value):
                value = int(value)
        except (ValueError, TypeError):
            if isinstance(property_value, str) and property_value.lower() in ("true", "false"):
                value = property_value.lower() == "true"

        success = item.SetProperty(property_key, value)
        if success:
            return f"Set {property_key} = {value} on item {item_index}"
        return (
            f"Failed to set {property_key}={value}. "
            f"Check the property name is valid and the value is in the accepted range."
        )
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  COLOR GRADING
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_node_graph(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Get the color grading node graph info for a timeline item.
    Must be on the Color page with a clip selected.

    Parameters:
    - track_type: "video", "audio", or "subtitle" (default: "video")
    - track_index: 1-based track index (default: 1)
    - item_index: 0-based item index (default: 0)
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if graph is None:
            return (
                "No node graph available. "
                "Make sure you are on the Color page and have a video clip selected."
            )
        return json.dumps(node_graph_to_dict(graph), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_lut(
    node_index: int,
    lut_path: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Apply a LUT to a node in a clip's color node graph.

    Parameters:
    - node_index: 1-based node index
    - lut_path: Absolute path to the LUT file (.cube, .3dl, etc.)
    - track_type: "video" (default)
    - track_index: 1-based track index (default: 1)
    - item_index: 0-based item index (default: 0)
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if graph is None:
            return "No node graph available. Switch to the Color page first."
        success = graph.SetLUT(node_index, lut_path)
        return _ok(
            success,
            f"LUT applied to node {node_index}: {lut_path}",
            "Failed to apply LUT. Check that node_index is valid and LUT file exists.",
        )
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_cdl(
    node_index: int,
    slope: str = "1.0 1.0 1.0",
    offset: str = "0.0 0.0 0.0",
    power: str = "1.0 1.0 1.0",
    saturation: float = 1.0,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Apply CDL (Color Decision List) values to a node.

    Parameters:
    - node_index: 1-based node index
    - slope: RGB slope as space-separated string (default: "1.0 1.0 1.0")
    - offset: RGB offset as space-separated string (default: "0.0 0.0 0.0")
    - power: RGB power as space-separated string (default: "1.0 1.0 1.0")
    - saturation: Saturation value (default: 1.0)
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        cdl_map = {
            "NodeIndex": node_index,
            "Slope": slope,
            "Offset": offset,
            "Power": power,
            "Saturation": str(saturation),
        }
        success = item.SetCDL(cdl_map)
        if success:
            return f"CDL applied to node {node_index}"
        return (
            "Failed to apply CDL. Make sure you are on the Color page "
            "and the node_index is valid."
        )
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  RENDERING
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_render_formats(render_format: Optional[str] = None) -> str:
    """
    Get available render formats and codecs.

    Parameters:
    - render_format: If provided, returns codecs for that format. Otherwise returns all formats.
    """
    try:
        conn = _conn()
        project = conn.get_project()

        if render_format:
            codecs = project.GetRenderCodecs(render_format)
            return json.dumps({"format": render_format, "codecs": codecs}, indent=2, default=str)

        formats = project.GetRenderFormats()
        return json.dumps({"formats": formats}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_render_settings() -> str:
    """Get current render format, codec, render job list, and render presets."""
    try:
        conn = _conn()
        project = conn.get_project()

        result: dict = {}

        try:
            result["current_format_codec"] = project.GetCurrentRenderFormatAndCodec()
        except Exception:
            pass
        try:
            result["render_mode"] = project.GetCurrentRenderMode()
        except Exception:
            pass
        try:
            jobs = project.GetRenderJobList()
            result["render_jobs"] = safe_serialize(jobs) if jobs else []
        except Exception:
            pass
        try:
            presets = project.GetRenderPresetList()
            result["render_presets"] = safe_serialize(presets) if presets else []
        except Exception:
            pass
        try:
            result["is_rendering"] = project.IsRenderingInProgress()
        except Exception:
            pass

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_render_settings(
    settings: Optional[Dict[str, Any]] = None,
    render_format: Optional[str] = None,
    codec: Optional[str] = None,
) -> str:
    """
    Configure render settings for the current project.

    Parameters:
    - settings: Dict of render settings. Common keys:
        "TargetDir" (str), "CustomName" (str), "SelectAllFrames" (bool),
        "MarkIn" (int), "MarkOut" (int), "ExportVideo" (bool), "ExportAudio" (bool),
        "FormatWidth" (int), "FormatHeight" (int), "FrameRate" (float)
    - render_format: Format string (e.g. "mp4", "mov"). Set together with codec.
    - codec: Codec string (e.g. "H.264", "H.265", "ProRes 422 HQ")
    """
    try:
        conn = _conn()
        project = conn.get_project()
        results: dict = {}

        if render_format and codec:
            success = project.SetCurrentRenderFormatAndCodec(render_format, codec)
            results["format_codec"] = "set" if success else "failed"

        if settings:
            success = project.SetRenderSettings(settings)
            results["settings"] = "set" if success else "failed"

        if not results:
            return "No settings provided. Pass 'settings' dict and/or 'render_format'+'codec'."

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_render_job() -> str:
    """Add a render job to the queue based on current render settings."""
    try:
        conn = _conn()
        project = conn.get_project()
        job_id = project.AddRenderJob()
        if job_id:
            return json.dumps({"job_id": job_id})
        return "Failed to add render job. Configure render settings first (set_render_settings)."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def start_rendering(job_ids: Optional[List[str]] = None) -> str:
    """
    Start rendering queued jobs.

    Parameters:
    - job_ids: Optional list of job IDs to render. If None, renders all queued jobs.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        if job_ids:
            success = project.StartRendering(job_ids)
        else:
            success = project.StartRendering()
        return _ok(success, "Rendering started", "Failed to start rendering. Check render job queue.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_render_status(job_id: str) -> str:
    """
    Get the status of a render job.

    Parameters:
    - job_id: The render job ID (returned by add_render_job)
    """
    try:
        conn = _conn()
        project = conn.get_project()
        status = project.GetRenderJobStatus(job_id)
        if status is None:
            return f"No render job found with ID '{job_id}'"
        return json.dumps(safe_serialize(status), indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def stop_rendering() -> str:
    """Stop any currently running render processes."""
    try:
        conn = _conn()
        project = conn.get_project()
        project.StopRendering()
        return "Rendering stopped"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  AI / NEURAL ENGINE FEATURES (Resolve 19+ / Studio only)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def create_magic_mask(
    mode: str = "F",
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Create an AI-powered Magic Mask on a timeline item for subject isolation.
    Requires DaVinci Resolve Studio with Neural Engine.

    Parameters:
    - mode: "F" (forward), "B" (backward), or "BI" (bidirectional)
    - track_type/track_index/item_index: Clip locator
    """
    valid_modes = ("F", "B", "BI")
    if mode not in valid_modes:
        return f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}"
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        if not hasattr(item, 'CreateMagicMask'):
            return "CreateMagicMask is not available. Requires Resolve Studio 19+."
        success = item.CreateMagicMask(mode)
        return _ok(success, f"Magic Mask created (mode: {mode})", "Failed to create Magic Mask")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def regenerate_magic_mask(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Regenerate an existing Magic Mask on a timeline item.

    Parameters:
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        if not hasattr(item, 'RegenerateMagicMask'):
            return "RegenerateMagicMask is not available. Requires Resolve Studio 19+."
        success = item.RegenerateMagicMask()
        return _ok(success, "Magic Mask regenerated", "Failed to regenerate Magic Mask")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def smart_reframe(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Apply Smart Reframe to a timeline item (AI-based reframing).
    Requires DaVinci Resolve Studio with Neural Engine.

    Parameters:
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        if not hasattr(item, 'SmartReframe'):
            return "SmartReframe is not available. Requires Resolve Studio 19+."
        success = item.SmartReframe()
        return _ok(success, "Smart Reframe applied", "Failed to apply Smart Reframe")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def stabilize(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Apply stabilization to a timeline item using DaVinci Neural Engine.
    Requires DaVinci Resolve Studio.

    Parameters:
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        if not hasattr(item, 'Stabilize'):
            return "Stabilize is not available. Requires Resolve Studio 19+."
        success = item.Stabilize()
        return _ok(success, "Stabilization applied", "Failed to stabilize")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def detect_scene_cuts() -> str:
    """
    Detect scene cuts in the current timeline using AI.
    Requires DaVinci Resolve Studio.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if not hasattr(timeline, 'DetectSceneCuts'):
            return "DetectSceneCuts is not available. Requires Resolve Studio 19+."
        success = timeline.DetectSceneCuts()
        return _ok(success, "Scene cuts detected and applied", "Failed to detect scene cuts")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_subtitles_from_audio(
    language: str = "auto",
    preset: str = "default",
    chars_per_line: int = 42,
    line_break: str = "single",
    gap: int = 0,
) -> str:
    """
    Generate subtitles from audio using AI speech recognition.
    Requires DaVinci Resolve Studio 19+.

    Parameters:
    - language: "auto", "english", "french", "german", "italian", "japanese",
                "korean", "mandarin_simplified", "mandarin_traditional",
                "portuguese", "russian", "spanish", "danish", "dutch",
                "norwegian", "swedish"
    - preset: "default", "teletext", or "netflix"
    - chars_per_line: Characters per line (1-60, default: 42)
    - line_break: "single" or "double"
    - gap: Gap between subtitles in frames (0-10, default: 0)
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        resolve = conn.get_resolve()

        if not hasattr(timeline, 'CreateSubtitlesFromAudio'):
            return "CreateSubtitlesFromAudio is not available. Requires Resolve Studio 19+."

        # Build settings using Resolve constants from the existing connection
        language_map = {
            "auto": "AUTO_CAPTION_AUTO",
            "english": "AUTO_CAPTION_ENGLISH",
            "french": "AUTO_CAPTION_FRENCH",
            "german": "AUTO_CAPTION_GERMAN",
            "italian": "AUTO_CAPTION_ITALIAN",
            "japanese": "AUTO_CAPTION_JAPANESE",
            "korean": "AUTO_CAPTION_KOREAN",
            "mandarin_simplified": "AUTO_CAPTION_MANDARIN_SIMPLIFIED",
            "mandarin_traditional": "AUTO_CAPTION_MANDARIN_TRADITIONAL",
            "portuguese": "AUTO_CAPTION_PORTUGUESE",
            "russian": "AUTO_CAPTION_RUSSIAN",
            "spanish": "AUTO_CAPTION_SPANISH",
            "danish": "AUTO_CAPTION_DANISH",
            "dutch": "AUTO_CAPTION_DUTCH",
            "norwegian": "AUTO_CAPTION_NORWEGIAN",
            "swedish": "AUTO_CAPTION_SWEDISH",
        }
        preset_map = {
            "default": "AUTO_CAPTION_SUBTITLE_DEFAULT",
            "teletext": "AUTO_CAPTION_TELETEXT",
            "netflix": "AUTO_CAPTION_NETFLIX",
        }
        line_break_map = {
            "single": "AUTO_CAPTION_LINE_SINGLE",
            "double": "AUTO_CAPTION_LINE_DOUBLE",
        }

        def _resolve_const(name):
            return getattr(resolve, name, None)

        lang_const = _resolve_const(language_map.get(language, "AUTO_CAPTION_AUTO"))
        preset_const = _resolve_const(preset_map.get(preset, "AUTO_CAPTION_SUBTITLE_DEFAULT"))
        lb_const = _resolve_const(line_break_map.get(line_break, "AUTO_CAPTION_LINE_SINGLE"))

        subtitle_lang_key = _resolve_const("SUBTITLE_LANGUAGE")
        subtitle_preset_key = _resolve_const("SUBTITLE_CAPTION_PRESET")
        subtitle_cpl_key = _resolve_const("SUBTITLE_CHARS_PER_LINE")
        subtitle_lb_key = _resolve_const("SUBTITLE_LINE_BREAK")
        subtitle_gap_key = _resolve_const("SUBTITLE_GAP")

        if subtitle_lang_key is None:
            return (
                "Subtitle constants not available on this Resolve version. "
                "Requires Resolve Studio 19+."
            )

        settings = {
            subtitle_lang_key: lang_const,
            subtitle_preset_key: preset_const,
            subtitle_cpl_key: chars_per_line,
            subtitle_lb_key: lb_const,
            subtitle_gap_key: gap,
        }

        result = timeline.CreateSubtitlesFromAudio(settings)
        return _ok(result, "Subtitles generated from audio successfully", "Failed to generate subtitles")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TRANSCRIPTION & SUBTITLE TRACKS (mlx-whisper)
# ═══════════════════════════════════════════════════════════════════

# Whisper expects ISO 639-1 codes; accept human-friendly names too
_LANGUAGE_ALIASES = {
    "auto": None,
    "norsk": "no", "norwegian": "no", "no": "no", "nb": "no",
    "engelsk": "en", "english": "en", "en": "en",
}


def _normalize_language(language: Optional[str]) -> Optional[str]:
    """Map a language name/code to an ISO code for whisper (None = auto)."""
    if language is None:
        return None
    key = language.strip().lower()
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]
    return key  # assume the caller passed a valid ISO code


def _render_timeline_audio(project) -> str:
    """Render the current timeline's audio to a temp WAV file.

    Uses the render queue (audio-only job) — the job is removed again
    after rendering, but the current render settings are altered.
    Returns the path to the rendered file.
    """
    import time

    tmp_dir = tempfile.mkdtemp(prefix="resolve_transcribe_")

    # The API's format key is "Wave" (GetRenderFormats → {'Wave': 'wav'}) and
    # Wave has no codec list (GetRenderCodecs('Wave') → {}). Try the explicit
    # codec name, then an empty codec. On versions where neither is accepted
    # (e.g. Resolve 21 beta), fall back to the built-in "Audio Only" preset.
    if not project.SetCurrentRenderFormatAndCodec("Wave", "Linear PCM"):
        if not project.SetCurrentRenderFormatAndCodec("Wave", ""):
            if not project.LoadRenderPreset("Audio Only"):
                raise RuntimeError(
                    "Could not set render format to Wave and the 'Audio Only' "
                    "render preset is unavailable — check get_render_formats"
                )
    if not project.SetRenderSettings({
        "SelectAllFrames": True,
        "ExportVideo": False,
        "ExportAudio": True,
        "TargetDir": tmp_dir,
        "CustomName": "timeline_audio",
    }):
        raise RuntimeError("SetRenderSettings failed for audio-only render")

    job_id = project.AddRenderJob()
    if not job_id:
        raise RuntimeError("AddRenderJob failed")

    try:
        if not project.StartRendering([job_id]):
            raise RuntimeError("StartRendering failed")

        deadline = time.time() + 1800  # 30 min ceiling
        while project.IsRenderingInProgress():
            if time.time() > deadline:
                project.StopRendering()
                raise TimeoutError("Audio render did not finish within 30 minutes")
            time.sleep(1)

        status = project.GetRenderJobStatus(job_id) or {}
        if status.get("JobStatus") != "Complete":
            raise RuntimeError(f"Audio render failed: {status}")
    finally:
        try:
            project.DeleteRenderJob(job_id)
        except Exception:
            logger.debug("Could not delete render job %s", job_id)

    # The "Audio Only" preset fallback may produce another container than
    # .wav — accept anything ffmpeg/whisper can read.
    files = [
        f for f in os.listdir(tmp_dir)
        if f.lower().endswith((".wav", ".mov", ".mp4", ".aif", ".aiff", ".mp3", ".m4a", ".mxf"))
    ]
    if not files:
        raise RuntimeError(f"Render reported success but no audio file found in {tmp_dir}")
    return os.path.join(tmp_dir, files[0])


@mcp.tool()
def get_timeline_subtitle_tracks() -> str:
    """
    List the subtitle tracks on the current timeline.

    Returns JSON with project/timeline name and per track: index (1-based),
    name, item_count and enabled state. Use the index as track_index for
    transcribe_timeline_audio / write_subtitles_to_resolve in correct mode.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = _require_timeline(conn)
        return json.dumps({
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "subtitle_tracks": _get_subtitle_tracks(timeline),
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def transcribe_timeline_audio(
    language: str = "auto",
    output_mode: str = "new",
    track_index: Optional[int] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Transcribe the current timeline's audio locally with mlx-whisper.

    Renders the timeline audio to a temporary WAV via the render queue
    (the temporary job is cleaned up, but current render settings are
    changed), then transcribes. Nothing is written to the timeline —
    review the returned segments, then call write_subtitles_to_resolve.

    Parameters:
    - language: "auto", "norsk"/"no", "engelsk"/"en" or any ISO 639-1 code
    - output_mode: "new" → segments for a new subtitle track.
      "correct" → map the transcription onto the timing of an EXISTING
      subtitle track; each returned segment keeps the original timing and
      includes both the proposed text and original_text for comparison.
    - track_index: required when output_mode="correct" (1-based, see
      get_timeline_subtitle_tracks)
    - model: whisper model ("tiny", "base", "small", "medium", "large",
      "turbo" or a HuggingFace repo path)

    May take a while for long timelines (render + transcription).
    """
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = _require_timeline(conn)

        if output_mode not in ("new", "correct"):
            return "Error: output_mode must be 'new' or 'correct'"
        if output_mode == "correct" and track_index is None:
            return "Error: track_index is required when output_mode='correct'"

        existing = None
        if output_mode == "correct":
            # Read the existing track BEFORE the slow render+transcribe,
            # so an invalid track_index fails fast
            existing = _get_subtitle_track_segments(timeline, track_index)

        audio_path = _render_timeline_audio(project)
        transcription = _transcribe_audio(
            audio_path,
            language=_normalize_language(language),
            model=model,
            word_timestamps=(output_mode == "correct"),
        )

        if output_mode == "correct":
            segments = _map_transcription_to_segments(existing, transcription)
        else:
            segments = transcription["segments"]

        return json.dumps({
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "language": transcription["language"],
            "output_mode": output_mode,
            "track_index": track_index,
            "segment_count": len(segments),
            "segments": segments,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def write_subtitles_to_resolve(
    segments: List[Dict[str, Any]],
    output_mode: str = "new",
    track_name: Optional[str] = None,
    track_index: Optional[int] = None,
) -> str:
    """
    Write an approved transcription to the current timeline.

    Parameters:
    - segments: list of {"start": float, "end": float, "text": str}
      (seconds relative to timeline start) — typically the reviewed output
      of transcribe_timeline_audio
    - output_mode: "new" → write segments as a new subtitle track.
      "correct" → replace ONLY the text of the subtitle track at
      track_index; timing always comes from the existing items (any
      timing in the segments is ignored). Because the Resolve API cannot
      edit subtitle text in place, the corrected version is written as a
      new track and the original track is disabled — never deleted.
    - track_name: optional name for the new track
    - track_index: required when output_mode="correct" (1-based)

    Returns a JSON report with project/timeline name and the result.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = _require_timeline(conn)
        media_pool = conn.get_media_pool()

        if output_mode == "new":
            result = _write_subtitle_track(timeline, media_pool, segments, track_name)
        elif output_mode == "correct":
            if track_index is None:
                return "Error: track_index is required when output_mode='correct'"
            result = _correct_subtitle_track(timeline, media_pool, track_index, segments)
        else:
            return "Error: output_mode must be 'new' or 'correct'"

        return json.dumps({
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "output_mode": output_mode,
            **result,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  PROJECT TEMPLATES
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def list_project_templates() -> str:
    """
    List the available project templates from templates/configs/.

    Each entry has an id (use as template_name for
    create_project_from_template), display name, resolution/fps,
    timeline and bin names, and whether a .drp file is attached.
    """
    try:
        return json.dumps({
            "templates": _list_templates(),
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_project_from_template(template_name: str, project_name: str) -> str:
    """
    Create a new Resolve project from a template.

    If the template references a .drp file (templates/drp/), the project
    is imported from it and renamed. Otherwise it is built from the
    config: resolution + frame rate, bins, and timelines — 9:16 timelines
    get a custom rotated resolution. The new project is opened and its
    first timeline made current.

    Parameters:
    - template_name: template id or display name (see list_project_templates)
    - project_name: name for the new project (must not already exist)

    Returns a JSON report: what was created, plus warnings for anything
    that could not be applied.
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        report = _create_project_from_template(pm, template_name, project_name)
        return json.dumps(report, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  MEDIA POOL ↔ FINDER SYNC
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def sync_finder_folder_to_media_pool(folder_path: str) -> str:
    """
    Mirror a Finder folder structure as bins in the Media Pool and import
    each folder's media files into its bin.

    A bin named after the folder is created in the Media Pool root, with
    sub-bins matching the subfolder tree. Media files directly inside each
    folder are imported into the matching bin. The sync is idempotent:
    existing bins are reused by name and files already present in a bin
    (matched on file path) are skipped — re-run it to pick up new files.

    Note: Resolve's scripting API has no live-linked bins, so this is a
    one-time import per run, not a persistent link.

    Parameters:
    - folder_path: absolute path to the folder to sync

    Returns a JSON report: project name, totals (bins created/reused,
    files imported/skipped/failed) and the created bin structure.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        media_pool = conn.get_media_pool()

        structure = _read_finder_structure(folder_path)
        report = _sync_structure_to_media_pool(media_pool, structure)
        return json.dumps({
            "project": project.GetName(),
            "synced_path": structure["path"],
            **report,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  AUTO CLIP COLOR
# ═══════════════════════════════════════════════════════════════════

def _collect_clips_for_coloring(conn, source: str):
    """Collect unique MediaPoolItems from the timeline or the media pool.

    Returns (clips, skipped) where clips is a list of MediaPoolItem and
    skipped counts timeline items without a media pool clip (titles,
    generators).
    """
    seen = set()
    clips = []
    skipped = 0

    def _add(clip):
        try:
            key = clip.GetUniqueId()
        except Exception:
            key = clip.GetName()
        if key not in seen:
            seen.add(key)
            clips.append(clip)

    if source == "timeline":
        timeline = _require_timeline(conn)
        for track_type in ("video", "audio"):
            for index in range(1, (timeline.GetTrackCount(track_type) or 0) + 1):
                for item in timeline.GetItemListInTrack(track_type, index) or []:
                    clip = None
                    try:
                        clip = item.GetMediaPoolItem()
                    except Exception:
                        pass
                    if clip is None:  # Text+, generators, etc.
                        skipped += 1
                        continue
                    _add(clip)
    elif source == "media_pool":
        media_pool = conn.get_media_pool()

        def _walk(folder):
            for clip in folder.GetClipList() or []:
                # Skip non-media entries in the pool (timelines, imported
                # subtitles, Fusion titles/generators)
                clip_type = None
                try:
                    clip_type = clip.GetClipProperty("Type")
                except Exception:
                    pass
                if clip_type in ("Timeline", "Subtitle") or (
                    clip_type and "fusion" in clip_type.lower()
                ):
                    continue
                _add(clip)
            for sub in folder.GetSubFolderList() or []:
                _walk(sub)

        _walk(media_pool.GetRootFolder())
    else:
        raise ValueError("source must be 'timeline' or 'media_pool'")

    return clips, skipped


@mcp.tool()
def auto_color_clips(
    source: str = "timeline",
    dry_run: bool = True,
) -> str:
    """
    Categorize clips from filename + metadata and set clip colors.

    Categories: Drone/luftfoto → Yellow, Talking head/intervju → Blue,
    B-roll/håndholdt → Green, Musikk/lyd → Pink, Grafikk/stillbilder →
    Purple, Ukategorisert → Beige. (BUGFIX.md suggested Red and Cream for
    the last two audio/uncategorized buckets, but those are not valid CLIP
    colors in Resolve — Pink and Beige are the closest valid substitutes.)

    ALWAYS run with dry_run=True first: it returns the proposed color per
    clip (with the reason) without changing anything, so the user can
    confirm. Call again with dry_run=False to apply the colors via
    MediaPoolItem.SetClipColor.

    Parameters:
    - source: "timeline" (clips used on the current timeline; titles and
      generators are skipped) or "media_pool" (every clip in every bin)
    - dry_run: True = preview only (default), False = set the colors

    Returns a JSON report with proposals and, when applying, how many
    colors were set or failed.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        clips, skipped = _collect_clips_for_coloring(conn, source)

        proposals = []
        for clip in clips:
            properties = {}
            try:
                props = clip.GetClipProperty()
                if isinstance(props, dict):
                    properties = props
            except Exception as e:
                logger.debug("GetClipProperty() failed for %s: %s", clip.GetName(), e)

            proposal = _propose_clip_color(clip.GetName(), properties)
            proposal["current_color"] = clip.GetClipColor() or None
            proposals.append((clip, proposal))

        report: Dict[str, Any] = {
            "project": project.GetName(),
            "source": source,
            "dry_run": dry_run,
            "clip_count": len(proposals),
            "skipped_non_media_items": skipped,
        }

        if dry_run:
            report["proposals"] = [p for _, p in proposals]
            report["note"] = (
                "Ingen farger er satt. Bekreft forslagene og kall "
                "auto_color_clips med dry_run=False for å sette dem."
            )
            return json.dumps(report, indent=2, ensure_ascii=False)

        set_count = 0
        failures = []
        for clip, proposal in proposals:
            if clip.SetClipColor(proposal["proposed_color"]):
                set_count += 1
            else:
                failures.append({
                    "clip": proposal["clip"],
                    "color": proposal["proposed_color"],
                    "reason": "SetClipColor returned False",
                })
        report["colors_set"] = set_count
        report["failures"] = failures
        report["proposals"] = [p for _, p in proposals]
        return json.dumps(report, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  FUSION (Compositing / VFX)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_fusion_comp_list(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Get all Fusion compositions associated with a timeline item.

    Parameters:
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        count = item.GetFusionCompCount() or 0
        names = item.GetFusionCompNameList() or []
        return json.dumps({
            "item_name": item.GetName(),
            "fusion_comp_count": count,
            "fusion_comp_names": list(names),
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_fusion_comp(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Add a new Fusion composition to a timeline item.

    Parameters:
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        comp = item.AddFusionComp()
        return _ok(comp, f"Fusion composition added to '{item.GetName()}'", "Failed to add Fusion composition")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def import_fusion_comp(
    comp_path: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Import a Fusion composition from file into a timeline item.

    Parameters:
    - comp_path: Absolute path to the .comp or .setting file
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        comp = item.ImportFusionComp(comp_path)
        return _ok(comp, f"Fusion comp imported from '{comp_path}'", "Failed to import Fusion composition. Check file path.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_fusion_comp(
    export_path: str,
    comp_index: int = 1,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Export a Fusion composition from a timeline item to a file.

    Parameters:
    - export_path: Destination file path
    - comp_index: 1-based Fusion composition index (default: 1)
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        success = item.ExportFusionComp(export_path, comp_index)
        return _ok(success, f"Fusion comp {comp_index} exported to '{export_path}'", "Failed to export Fusion composition")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def load_fusion_comp(
    comp_name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Load a named Fusion composition as the active composition.

    Parameters:
    - comp_name: Name of the Fusion composition to load
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        comp = item.LoadFusionCompByName(comp_name)
        return _ok(comp, f"Loaded Fusion composition '{comp_name}'", f"Failed to load '{comp_name}'")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_fusion_comp(
    comp_name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Delete a named Fusion composition from a timeline item.

    Parameters:
    - comp_name: Name of the Fusion composition to delete
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        success = item.DeleteFusionCompByName(comp_name)
        return _ok(success, f"Deleted Fusion composition '{comp_name}'", f"Failed to delete '{comp_name}'")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def rename_fusion_comp(
    old_name: str,
    new_name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """
    Rename a Fusion composition on a timeline item.

    Parameters:
    - old_name: Current name of the Fusion composition
    - new_name: New name for the composition
    - track_type/track_index/item_index: Clip locator
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        success = item.RenameFusionCompByName(old_name, new_name)
        return _ok(success, f"Renamed '{old_name}' to '{new_name}'", "Failed to rename Fusion composition")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_fusion_clip(
    track_type: str = "video",
    track_index: int = 1,
    item_indices: Optional[List[int]] = None,
) -> str:
    """
    Create a Fusion clip from one or more timeline items.

    Parameters:
    - track_type: "video" (default)
    - track_index: 1-based track index (default: 1)
    - item_indices: List of 0-based item indices to merge. If None, uses all items.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)

        all_items = timeline.GetItemListInTrack(track_type, track_index)
        if not all_items:
            return f"No items on {track_type} track {track_index}"

        if item_indices is not None:
            items = [all_items[i] for i in item_indices if 0 <= i < len(all_items)]
        else:
            items = list(all_items)

        if not items:
            return "No valid items selected"

        result = timeline.CreateFusionClip(items)
        return _ok(result, f"Fusion clip created from {len(items)} item(s)", "Failed to create Fusion clip")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_fusion_generator(generator_name: str) -> str:
    """
    Insert a Fusion generator into the current timeline at the playhead.

    Parameters:
    - generator_name: Name of the Fusion generator to insert
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.InsertFusionGeneratorIntoTimeline(generator_name)
        return _ok(item, f"Fusion generator '{generator_name}' inserted", f"Failed to insert generator '{generator_name}'")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_fusion_composition() -> str:
    """Insert a blank Fusion composition into the current timeline at the playhead."""
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if not hasattr(timeline, 'InsertFusionCompositionIntoTimeline'):
            return "InsertFusionCompositionIntoTimeline is not available in this Resolve version."
        item = timeline.InsertFusionCompositionIntoTimeline()
        return _ok(item, "Fusion composition inserted into timeline", "Failed to insert Fusion composition")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_fusion_title(title_name: str) -> str:
    """
    Insert a Fusion title into the current timeline at the playhead.

    Parameters:
    - title_name: Name of the Fusion title template to insert
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.InsertFusionTitleIntoTimeline(title_name)
        return _ok(item, f"Fusion title '{title_name}' inserted", f"Failed to insert title '{title_name}'")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE EXPORT
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def export_timeline(
    file_path: str,
    export_type: str = "fcpxml_1_10",
    export_subtype: str = "none",
) -> str:
    """
    Export the current timeline to a file.

    Parameters:
    - file_path: Destination file path
    - export_type: One of "aaf", "drt", "edl", "fcp_7_xml", "fcpxml_1_8",
                   "fcpxml_1_9", "fcpxml_1_10", "hdr_10_profile_a",
                   "hdr_10_profile_b", "csv", "tab", "otio", "ale", "ale_cdl"
    - export_subtype: For AAF: "aaf_new" or "aaf_existing".
                      For EDL: "cdl", "sdl", "missing_clips", or "none".
    """
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        timeline = _require_timeline(conn)

        type_map = {
            "aaf": "EXPORT_AAF",
            "drt": "EXPORT_DRT",
            "edl": "EXPORT_EDL",
            "fcp_7_xml": "EXPORT_FCP_7_XML",
            "fcpxml_1_8": "EXPORT_FCPXML_1_8",
            "fcpxml_1_9": "EXPORT_FCPXML_1_9",
            "fcpxml_1_10": "EXPORT_FCPXML_1_10",
            "hdr_10_profile_a": "EXPORT_HDR_10_PROFILE_A",
            "hdr_10_profile_b": "EXPORT_HDR_10_PROFILE_B",
            "csv": "EXPORT_TEXT_CSV",
            "tab": "EXPORT_TEXT_TAB",
            "otio": "EXPORT_OTIO",
            "ale": "EXPORT_ALE",
            "ale_cdl": "EXPORT_ALE_CDL",
        }
        subtype_map = {
            "none": "EXPORT_NONE",
            "aaf_new": "EXPORT_AAF_NEW",
            "aaf_existing": "EXPORT_AAF_EXISTING",
            "cdl": "EXPORT_CDL",
            "sdl": "EXPORT_SDL",
            "missing_clips": "EXPORT_MISSING_CLIPS",
        }

        type_const_name = type_map.get(export_type)
        sub_const_name = subtype_map.get(export_subtype, "EXPORT_NONE")

        if type_const_name is None:
            return f"Unknown export_type '{export_type}'. Valid: {list(type_map.keys())}"

        exp_type = getattr(resolve, type_const_name, None)
        exp_sub = getattr(resolve, sub_const_name, None)

        if exp_type is None:
            return f"Export constant '{type_const_name}' not available in this Resolve version."

        result = timeline.Export(file_path, exp_type, exp_sub)
        return _ok(result, f"Timeline exported to {file_path}", f"Failed to export timeline to {file_path}")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  THUMBNAIL / SCREENSHOT
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_current_thumbnail() -> Image:
    """
    Get a thumbnail of the current frame from the Color page.
    Must be on the Color page with a clip selected.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)

        thumbnail_data = timeline.GetCurrentClipThumbnailImage()
        if not thumbnail_data or not isinstance(thumbnail_data, dict):
            raise RuntimeError(
                "No thumbnail available. Make sure you are on the Color page with a clip selected."
            )

        png_bytes = thumbnail_to_png_bytes(thumbnail_data)
        return Image(data=png_bytes, format="png")
    except Exception as e:
        raise RuntimeError(f"Error getting thumbnail: {e}")


@mcp.tool()
def export_current_frame(file_path: str) -> str:
    """
    Export the current frame as a still image.

    Parameters:
    - file_path: Destination file path (.png, .jpg, .tif, .dpx, .exr)
    """
    try:
        conn = _conn()
        project = conn.get_project()
        if not hasattr(project, 'ExportCurrentFrameAsStill'):
            return "ExportCurrentFrameAsStill is not available in this Resolve version."
        success = project.ExportCurrentFrameAsStill(file_path)
        return _ok(success, f"Current frame exported to {file_path}", "Failed to export frame. Check file path and extension.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  SCREENSHOT (give Claude eyes)
# ═══════════════════════════════════════════════════════════════════

def _find_resolve_window_id() -> int | None:
    """Find the CGWindowID of the main DaVinci Resolve window via Quartz."""
    try:
        import Quartz  # type: ignore[import-not-found]  # macOS-only
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        )
        for w in windows:
            owner = w.get("kCGWindowOwnerName", "")
            if "DaVinci Resolve" in str(owner):
                layer = w.get("kCGWindowLayer", 999)
                # Main window is layer 0, skip menus/tooltips
                if layer == 0:
                    return w.get("kCGWindowNumber")
    except ImportError:
        pass
    return None


def _capture_screenshot() -> bytes:
    """Capture Resolve window (or full screen as fallback). Returns PNG bytes."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        wid = _find_resolve_window_id()
        if wid is not None:
            r = subprocess.run(
                ["screencapture", "-x", "-l", str(wid), tmp.name],
                capture_output=True,
            )
        else:
            r = subprocess.run(
                ["screencapture", "-x", tmp.name],
                capture_output=True,
            )
        if r.returncode != 0:
            raise RuntimeError(
                "screencapture failed. Grant Screen Recording permission to "
                "the host app in System Settings > Privacy & Security > Screen Recording."
            )
        with open(tmp.name, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp.name)


@mcp.tool()
def screenshot() -> Image:
    """
    Take a screenshot of DaVinci Resolve so you can SEE the current state.
    Call this frequently — before and after changes, when the user describes
    something visual, or whenever you need to verify what's on screen.
    Captures the Resolve window directly. Works on any page.
    """
    try:
        png_data = _capture_screenshot()
        if not png_data:
            raise RuntimeError("Screenshot captured but file was empty")
        return Image(data=png_data, format="png")
    except Exception as e:
        raise RuntimeError(f"Error taking screenshot: {e}")


# ═══════════════════════════════════════════════════════════════════
#  AUDIO
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_voice_isolation_state(track_index: int) -> str:
    """
    Get the Voice Isolation state for an audio track.
    Requires DaVinci Resolve Studio.

    Parameters:
    - track_index: 1-based audio track index
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if not hasattr(timeline, 'GetVoiceIsolationState'):
            return "Voice Isolation is not available in this Resolve version."
        state = timeline.GetVoiceIsolationState(track_index)
        return json.dumps(safe_serialize(state), indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_voice_isolation_state(
    track_index: int,
    enabled: bool,
    amount: int = 100,
) -> str:
    """
    Set Voice Isolation on an audio track to isolate speech from background noise.
    Requires DaVinci Resolve Studio.

    Parameters:
    - track_index: 1-based audio track index
    - enabled: True to enable, False to disable
    - amount: Isolation amount (0-100, default: 100)
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if not hasattr(timeline, 'SetVoiceIsolationState'):
            return "Voice Isolation is not available in this Resolve version."
        success = timeline.SetVoiceIsolationState(
            track_index, {"isEnabled": enabled, "amount": amount}
        )
        state = "enabled" if enabled else "disabled"
        return _ok(success, f"Voice Isolation {state} (amount: {amount}) on audio track {track_index}", "Failed to set voice isolation state")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  CODE EXECUTION (POWER TOOL)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def execute_resolve_code(code: str) -> str:
    """
    Execute arbitrary Python code in the DaVinci Resolve scripting environment.
    Use this for operations not covered by specific tools.

    Pre-loaded namespace variables:
    - resolve: The DaVinci Resolve object
    - project: The current project
    - mediaPool: The current media pool
    - timeline: The current timeline (may be None)
    - mediaStorage: The media storage object

    Use print() to output results, or set a variable named 'result'.

    Parameters:
    - code: Python code to execute
    """
    try:
        conn = _conn()
        return conn.execute_code(code)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  PROMPT: Editing Strategy
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
#  LOCAL TRANSCRIPTION (mlx-whisper on Apple Silicon)
#
#  Long files are auto-chunked with ffmpeg (5-min pieces) so each
#  whisper call finishes well within any MCP timeout.
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def transcribe_audio(
    file_path: str,
    model: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    word_timestamps: bool = False,
    initial_prompt: Optional[str] = None,
) -> str:
    """
    Transcribe an audio/video file locally using mlx-whisper (Apple Silicon).
    Long files are automatically split into 5-minute chunks so it never times out.

    Returns ALL segments with timestamps inline (compact format) plus saves
    an SRT file next to the source for Resolve import.

    Parameters:
    - file_path: Absolute path to audio/video file (mp3, wav, m4a, mp4, mov, etc.)
    - model: "tiny" (fastest), "base", "small", "medium", "large" (most accurate),
             "turbo" (best speed/quality, default). Or a full HuggingFace repo path.
    - language: Language code (e.g. "en", "fr", "de", "ja"). None = auto-detect.
    - word_timestamps: Include word-level timestamps in output.
    - initial_prompt: Optional text to guide the model's vocabulary/style.
    """
    try:
        result = _transcribe(
            audio_path=file_path,
            model=model,
            language=language,
            word_timestamps=word_timestamps,
            initial_prompt=initial_prompt,
        )

        segments = result.get("segments", [])

        # Write SRT file next to the source for Resolve import
        base = os.path.splitext(file_path)[0]
        srt_path = base + ".srt"
        srt_content = segments_to_srt(segments)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # Build compact timestamped transcript inline —
        # one line per segment: [MM:SS-MM:SS] text
        lines = []
        for s in segments:
            t0 = s["start"]
            t1 = s["end"]
            m0, s0 = int(t0 // 60), int(t0 % 60)
            m1, s1 = int(t1 // 60), int(t1 % 60)
            lines.append(f"[{m0:02d}:{s0:02d}-{m1:02d}:{s1:02d}] {s['text'].strip()}")

        transcript_block = "\n".join(lines)

        return (
            f"Language: {result.get('language', 'unknown')}\n"
            f"Segments: {len(segments)}\n"
            f"SRT saved: {srt_path}\n"
            f"\n{transcript_block}"
        )
    except ImportError:
        return (
            "mlx-whisper is not installed. Install with:\n"
            "  uv pip install 'mlx-whisper>=0.4.3'\n"
            "Or: pip install 'resolve-claude-mcp[transcription]'"
        )
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def transcribe_and_add_subtitles(
    file_path: str,
    model: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None,
) -> str:
    """
    Transcribe audio locally with mlx-whisper and add subtitle markers to the timeline.
    Long files are auto-chunked so this works on any length.

    Parameters:
    - file_path: Absolute path to the audio/video file to transcribe
    - model: Whisper model size ("tiny", "base", "small", "medium", "large", "turbo")
    - language: Language code (e.g. "en", "fr"). None = auto-detect.
    - initial_prompt: Optional text to guide recognition vocabulary
    """
    try:
        result = _transcribe(
            audio_path=file_path,
            model=model,
            language=language,
            initial_prompt=initial_prompt,
        )

        segments = result.get("segments", [])
        if not segments:
            return "Transcription produced no segments. Check that the file contains speech."

        conn = _conn()
        timeline = _require_timeline(conn)

        fps_str = timeline.GetSetting("timelineFrameRate")
        fps = float(fps_str) if fps_str else 24.0
        timeline_start = timeline.GetStartFrame() or 0

        added = 0
        for seg in segments:
            frame_pos = timeline_start + int(seg["start"] * fps)
            duration_frames = max(1, int((seg["end"] - seg["start"]) * fps))
            text = seg["text"].strip()

            if timeline.AddMarker(frame_pos, "Cream", text, text, duration_frames, ""):
                added += 1

        srt_content = segments_to_srt(segments)

        return json.dumps({
            "language": result.get("language", "unknown"),
            "total_segments": len(segments),
            "markers_added": added,
            "srt_preview": srt_content[:2000],
            "note": (
                f"Added {added} timeline markers. "
                "Use export_srt() to save an SRT file for import as a subtitle track."
            ),
        }, indent=2, ensure_ascii=False)
    except ImportError:
        return "mlx-whisper is not installed. Install with: uv pip install 'mlx-whisper>=0.4.3'"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_srt(
    file_path: str,
    output_path: str,
    model: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None,
) -> str:
    """
    Transcribe audio and save as an SRT subtitle file.
    The SRT can then be imported into Resolve's subtitle track.

    Parameters:
    - file_path: Absolute path to the audio/video file to transcribe
    - output_path: Where to save the .srt file
    - model: Whisper model size ("tiny", "base", "small", "medium", "large", "turbo")
    - language: Language code or None for auto-detect
    - initial_prompt: Optional vocabulary/style hint
    """
    try:
        result = _transcribe(
            audio_path=file_path,
            model=model,
            language=language,
            initial_prompt=initial_prompt,
        )

        segments = result.get("segments", [])
        if not segments:
            return "Transcription produced no segments."

        srt = segments_to_srt(segments)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt)

        return json.dumps({
            "language": result.get("language", "unknown"),
            "segments": len(segments),
            "output_path": output_path,
            "note": "SRT saved. Import into Resolve: File > Import > Subtitle.",
        }, indent=2)
    except ImportError:
        return "mlx-whisper is not installed. Install with: uv pip install 'mlx-whisper>=0.4.3'"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def list_whisper_models() -> str:
    """List available mlx-whisper models with their HuggingFace repo paths."""
    return json.dumps({
        "models": {k: v for k, v in WHISPER_MODELS.items()},
        "default": DEFAULT_MODEL,
        "note": "First use of each model triggers a one-time download.",
    }, indent=2)


# ═══════════════════════════════════════════════════════════════════
#  PROMPT: Editing Strategy
# ═══════════════════════════════════════════════════════════════════

@mcp.prompt()
def editing_strategy() -> str:
    """Defines the recommended workflow for editing in DaVinci Resolve"""
    return """When working with DaVinci Resolve through MCP, follow this workflow:

    0. USE screenshot() TO SEE WHAT YOU'RE DOING:
       - BEFORE making changes: take a screenshot to understand the current state
       - AFTER making changes: take a screenshot to verify the result
       - When the user describes something visual ("this clip looks too dark",
         "the timeline is messy"), take a screenshot to see what they see
       - When debugging why something failed, take a screenshot
       - When the user asks "what does it look like?" or "how does it look?", screenshot
       - Think of it like looking at your monitor — do it frequently

    1. ALWAYS start by checking the current state:
       - Use screenshot() to see the Resolve UI
       - Use get_project_info() to understand the project
       - Use get_current_timeline_info() to see the active timeline
       - Use get_current_page() to know which page you're on

    2. For media management:
       - Use get_media_pool_structure() to see available clips
       - Use import_media() to bring in new footage
       - Use create_timeline() to start a new edit
       - Use append_to_timeline() to add clips

    3. For editing operations:
       - Use get_timeline_items() to see what's on each track
       - Use set_timeline_item_property() for transforms (Pan, Tilt, Zoom, Opacity, Crop)
       - Use add_marker() to mark important points
       - Use set_current_timecode() to navigate

    4. For color grading (switch to Color page first):
       - Use get_node_graph() to see the current grade
       - Use set_lut() to apply LUTs
       - Use set_cdl() for CDL adjustments

    5. For transcription and subtitles (local, no Studio needed):
       - Use transcribe_audio() to transcribe any audio/video file locally via mlx-whisper
       - Use transcribe_and_add_subtitles() to transcribe and add markers to the timeline
       - Use export_srt() to save transcription as an SRT file for import
       - Use list_whisper_models() to see available model sizes

    6. For AI-powered features (Resolve Studio 19+ only):
       - Use detect_scene_cuts() to auto-detect cuts
       - Use create_magic_mask() for AI subject isolation
       - Use smart_reframe() for automatic reframing
       - Use stabilize() for clip stabilization
       - Use create_subtitles_from_audio() for Resolve's built-in AI subtitles
       - Use set_voice_isolation_state() to isolate speech

    7. For rendering:
       - Use get_render_formats() to see available options
       - Use set_render_settings() to configure output
       - Use add_render_job() then start_rendering()
       - Use get_render_status() to monitor progress

    8. For Fusion (compositing/VFX):
       - Use get_fusion_comp_list() to see existing compositions
       - Use add_fusion_comp() to create a new composition
       - Use import_fusion_comp() / export_fusion_comp() for .comp files
       - Use create_fusion_clip() to merge clips into a Fusion composition
       - Use insert_fusion_generator() / insert_fusion_title() for generators and titles
       - For advanced Fusion node manipulation, use execute_resolve_code()

    9. For anything not covered by specific tools:
       - Use execute_resolve_code() to run arbitrary Python
       - The Resolve Python API is comprehensive — most operations are possible

    IMPORTANT:
    - DaVinci Resolve must be running for all tools to work.
    - Some features require the Color page. AI features require Resolve Studio 19+.
    - USE screenshot() LIBERALLY. It is your eyes. Look before you act, look after you act.
    """


# ═══════════════════════════════════════════════════════════════════
#  PROJECT MANAGEMENT (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def save_project() -> str:
    """Save the current DaVinci Resolve project.

    Should be called after significant changes. Equivalent to Ctrl+S in the UI.
    """
    try:
        conn = _conn()
        result = conn.get_project_manager().SaveProject()
        return _ok(result, "Project saved successfully.", "Failed to save project.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def list_projects(folder_name: Optional[str] = None) -> str:
    """List all projects in the current (or specified) Project Manager folder.

    Parameters:
    - folder_name: Optional folder name to navigate into before listing.
      If omitted, lists projects in the current folder.
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        if folder_name:
            ok = pm.OpenFolder(folder_name)
            if not ok:
                return f"Failed to open folder '{folder_name}'."
        projects = pm.GetProjectListInCurrentFolder() or []
        folders = pm.GetFolderListInCurrentFolder() or []
        current = pm.GetCurrentFolder()
        return json.dumps({
            "current_folder": current,
            "project_count": len(projects),
            "projects": projects,
            "subfolders": folders,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def load_project(project_name: str) -> str:
    """Load a DaVinci Resolve project by name.

    The project must exist in the current Project Manager folder.
    Use list_projects() first to find available project names.

    Parameters:
    - project_name: Exact name of the project to load.
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        project = pm.LoadProject(project_name)
        if not project:
            return f"Failed to load project '{project_name}'. Check the name with list_projects()."
        return json.dumps({
            "status": "loaded",
            "project": project.GetName(),
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_project(
    project_name: str,
    export_path: str,
    with_stills_and_luts: bool = True,
) -> str:
    """Export a DaVinci Resolve project to a .drp file.

    Parameters:
    - project_name: Name of the project to export (must exist in current folder).
    - export_path: Full file path for the exported .drp file.
    - with_stills_and_luts: Include gallery stills and LUTs in the export (default True).
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        result = pm.ExportProject(project_name, export_path, with_stills_and_luts)
        return _ok(result, f"Exported '{project_name}' to {export_path}", f"Failed to export '{project_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def archive_project(
    project_name: str,
    archive_path: str,
    with_stills_and_luts: bool = True,
    with_media: bool = False,
    with_render_cache: bool = False,
    with_proxy_media: bool = False,
) -> str:
    """Archive a DaVinci Resolve project to a .dra file with configurable media options.

    Use this for long-term storage or client delivery. Larger than export_project()
    when media is included.

    Parameters:
    - project_name: Name of the project to archive.
    - archive_path: Full file path for the .dra archive.
    - with_stills_and_luts: Include gallery stills and LUTs (default True).
    - with_media: Include all source media files (default False — very large).
    - with_render_cache: Include render cache (default False).
    - with_proxy_media: Include proxy media files (default False).
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        result = pm.ArchiveProject(
            project_name,
            archive_path,
            with_stills_and_luts,
            with_media,
            with_render_cache,
            with_proxy_media,
        )
        return _ok(result, f"Archived '{project_name}' to {archive_path}", f"Failed to archive '{project_name}'.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE NAVIGATION (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_all_timelines() -> str:
    """List all timelines in the current project with their index, name, and frame rate.

    Use this to discover available timelines before calling switch_timeline().
    """
    try:
        conn = _conn()
        project = conn.get_project()
        count = project.GetTimelineCount()
        current = conn.get_current_timeline()
        current_name = current.GetName() if current else None
        timelines = []
        for i in range(1, count + 1):
            tl = project.GetTimelineByIndex(i)
            if tl:
                try:
                    fps = tl.GetSetting("timelineFrameRate") or ""
                    timelines.append({
                        "index": i,
                        "name": tl.GetName(),
                        "fps": fps,
                        "is_active": tl.GetName() == current_name,
                    })
                except Exception:
                    timelines.append({"index": i, "name": str(tl), "is_active": False})
        return json.dumps({
            "project": project.GetName(),
            "timeline_count": count,
            "active_timeline": current_name,
            "timelines": timelines,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def switch_timeline(name: Optional[str] = None, index: Optional[int] = None) -> str:
    """Switch the active timeline by name or 1-based index.

    Provide either name or index (name takes priority if both are given).
    Use get_all_timelines() to see available timelines and their indices.

    Parameters:
    - name: Timeline name (exact match).
    - index: 1-based timeline index.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        if name is None and index is None:
            return "Error: provide 'name' or 'index'."
        timeline = None
        if name:
            count = project.GetTimelineCount()
            for i in range(1, count + 1):
                tl = project.GetTimelineByIndex(i)
                if tl and tl.GetName() == name:
                    timeline = tl
                    break
            if not timeline:
                return f"No timeline named '{name}'. Use get_all_timelines() to see available timelines."
        else:
            timeline = project.GetTimelineByIndex(index)
            if not timeline:
                return f"No timeline at index {index}."
        result = project.SetCurrentTimeline(timeline)
        return _ok(result, f"Switched to timeline '{timeline.GetName()}'.", f"Failed to switch timeline.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def duplicate_timeline(new_name: str) -> str:
    """Duplicate the current timeline with a new name.

    Useful for creating versioned copies before making destructive edits.

    Parameters:
    - new_name: Name for the duplicated timeline.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        new_tl = timeline.DuplicateTimeline(new_name)
        if not new_tl:
            return f"Failed to duplicate timeline as '{new_name}'."
        return json.dumps({
            "status": "duplicated",
            "source": timeline.GetName(),
            "new_timeline": new_tl.GetName(),
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE EDITING (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def add_timeline_track(
    track_type: str,
    sub_type: Optional[str] = None,
) -> str:
    """Add a new track to the current timeline.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - sub_type: Audio subtype — 'mono', 'stereo', '5.1', '5.1film', '7.1', '7.1film',
      'adaptive1' through 'adaptive24'. Ignored for video/subtitle tracks.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if sub_type:
            result = timeline.AddTrack(track_type, sub_type)
        else:
            result = timeline.AddTrack(track_type)
        return _ok(result, f"Added {track_type} track{' (' + sub_type + ')' if sub_type else ''}.",
                   f"Failed to add {track_type} track.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_timeline_clips(
    track_type: str,
    track_index: int,
    item_indices: List[int],
    ripple: bool = False,
) -> str:
    """Delete clips from the current timeline by track and item index.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - item_indices: List of 0-based item indices to delete.
    - ripple: If True, close the gap left by deleted clips (ripple delete).
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        items = timeline.GetItemListInTrack(track_type, track_index)
        if not items:
            return f"No items on {track_type} track {track_index}."
        to_delete = []
        for idx in item_indices:
            if 0 <= idx < len(items):
                to_delete.append(items[idx])
            else:
                return f"item_index {idx} out of range — track has {len(items)} items (0-{len(items)-1})."
        result = timeline.DeleteClips(to_delete, ripple)
        return _ok(result, f"Deleted {len(to_delete)} clip(s) from {track_type} track {track_index}.",
                   "Failed to delete clips.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_timeline_markers(
    color: Optional[str] = None,
    frame: Optional[int] = None,
) -> str:
    """Delete markers from the current timeline by color or frame number.

    Provide 'color' to delete all markers of that color, or 'frame' to delete
    the marker at a specific frame. Provide neither to delete ALL markers (color='All').

    Parameters:
    - color: Marker color name (e.g. 'Blue', 'Red', 'All'). Case-sensitive.
    - frame: Exact frame number of the marker to delete.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if frame is not None:
            result = timeline.DeleteMarkerAtFrame(frame)
            return _ok(result, f"Deleted marker at frame {frame}.", f"No marker at frame {frame}.")
        target_color = color or "All"
        result = timeline.DeleteMarkersByColor(target_color)
        return _ok(result, f"Deleted all '{target_color}' markers.", f"Failed to delete markers.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  MEDIA POOL (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def set_current_media_pool_folder(folder_name: str) -> str:
    """Navigate to a bin in the Media Pool by name.

    Sets the active bin for subsequent import operations. Searches all bins
    recursively by name — use the exact bin name.

    Parameters:
    - folder_name: Exact bin name to navigate to.
    """
    try:
        conn = _conn()
        folder = _find_folder_in_media_pool(conn, folder_name)
        if not folder:
            return f"Bin '{folder_name}' not found. Use get_media_pool_structure() to see available bins."
        result = conn.get_media_pool().SetCurrentFolder(folder)
        return _ok(result, f"Navigated to bin '{folder_name}'.", f"Failed to set bin '{folder_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def move_clips_to_folder(clip_names: List[str], target_folder_name: str) -> str:
    """Move clips to a different bin in the Media Pool.

    Parameters:
    - clip_names: List of exact clip names to move.
    - target_folder_name: Exact name of the destination bin.
    """
    try:
        conn = _conn()
        target = _find_folder_in_media_pool(conn, target_folder_name)
        if not target:
            return f"Target bin '{target_folder_name}' not found."
        clips = []
        not_found = []
        for name in clip_names:
            clip = _find_clip_in_media_pool(conn, name)
            if clip:
                clips.append(clip)
            else:
                not_found.append(name)
        if not clips:
            return f"None of the specified clips were found: {clip_names}"
        result = conn.get_media_pool().MoveClips(clips, target)
        return json.dumps({
            "status": "ok" if result else "failed",
            "moved": len(clips),
            "not_found": not_found,
            "target_folder": target_folder_name,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def relink_clips(clip_names: List[str], folder_path: str) -> str:
    """Relink offline clips to media files in a new folder.

    Resolves 'media offline' for clips whose files have moved. Resolve matches
    files by name within the given folder.

    Parameters:
    - clip_names: List of exact clip names to relink.
    - folder_path: Absolute path to the folder containing the new media files.
    """
    try:
        conn = _conn()
        clips = []
        not_found = []
        for name in clip_names:
            clip = _find_clip_in_media_pool(conn, name)
            if clip:
                clips.append(clip)
            else:
                not_found.append(name)
        if not clips:
            return f"None of the specified clips were found: {clip_names}"
        result = conn.get_media_pool().RelinkClips(clips, folder_path)
        return json.dumps({
            "status": "ok" if result else "failed",
            "relinked": len(clips),
            "not_found": not_found,
            "folder": folder_path,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def auto_sync_audio(
    clip_names: List[str],
    method: str = "waveform",
    timecode_mismatch_threshold: int = 0,
) -> str:
    """Auto-sync audio for multi-cam or double-system sound recordings.

    Parameters:
    - clip_names: List of clip names to sync (must be in Media Pool).
    - method: Sync method — 'waveform' (default) or 'timecode'.
    - timecode_mismatch_threshold: Threshold in frames for timecode method (default 0).
    """
    try:
        conn = _conn()
        clips = []
        not_found = []
        for name in clip_names:
            clip = _find_clip_in_media_pool(conn, name)
            if clip:
                clips.append(clip)
            else:
                not_found.append(name)
        if not clips:
            return f"None of the specified clips were found: {clip_names}"
        settings = {
            "audioSyncMethod": method,
            "timecodeOffsetInFrames": timecode_mismatch_threshold,
        }
        result = conn.get_media_pool().AutoSyncAudio(clips, settings)
        return json.dumps({
            "status": "ok" if result else "failed",
            "clip_count": len(clips),
            "not_found": not_found,
            "method": method,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_clip_metadata(clip_name: str, metadata_type: Optional[str] = None) -> str:
    """Read metadata from a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - metadata_type: Specific metadata key to read (e.g. 'Camera #', 'Scene', 'Shot').
      If omitted, returns all metadata as a dict.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found in Media Pool."
        if metadata_type:
            value = clip.GetMetadata(metadata_type)
            return json.dumps({"clip": clip_name, metadata_type: value}, indent=2)
        metadata = clip.GetMetadata()
        return json.dumps({"clip": clip_name, "metadata": metadata}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_clip_metadata(clip_name: str, metadata: Dict[str, str]) -> str:
    """Write metadata to a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - metadata: Dict of metadata key-value pairs (e.g. {'Scene': '01A', 'Shot': '02'}).
      Common keys: 'Camera #', 'Scene', 'Shot', 'Take', 'Angle', 'Description',
      'Comments', 'Keywords', 'Good Take', 'Frame Rate'.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found in Media Pool."
        result = clip.SetMetadata(metadata)
        return _ok(result, f"Metadata set on '{clip_name}'.", f"Failed to set metadata on '{clip_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_clip_markers(
    clip_name: str,
    markers: List[Dict[str, Any]],
) -> str:
    """Add markers directly to a Media Pool clip (not timeline markers).

    Each marker dict must have 'frame' and optionally 'color', 'name', 'note',
    'duration', 'custom_data'.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - markers: List of marker dicts. Example:
      [{'frame': 0, 'color': 'Blue', 'name': 'Start', 'note': '', 'duration': 1}]
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found in Media Pool."
        added = 0
        failures = []
        for m in markers:
            frame = m.get("frame", 0)
            color = m.get("color", "Blue")
            name = m.get("name", "")
            note = m.get("note", "")
            duration = m.get("duration", 1)
            custom_data = m.get("custom_data", "")
            result = clip.AddMarker(frame, color, name, note, duration, custom_data)
            if result:
                added += 1
            else:
                failures.append(frame)
        return json.dumps({
            "clip": clip_name,
            "added": added,
            "failed_frames": failures,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def replace_clip(clip_name: str, new_file_path: str) -> str:
    """Replace the media file for an existing Media Pool clip (offline→online workflow).

    The clip retains its position in the Media Pool and on timelines.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - new_file_path: Absolute path to the replacement media file.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found in Media Pool."
        result = clip.ReplaceClip(new_file_path)
        return _ok(result, f"Replaced '{clip_name}' with {new_file_path}",
                   f"Failed to replace '{clip_name}'. Check the file path.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_timeline_from_clips(timeline_name: str, clip_names: List[str]) -> str:
    """Create a new timeline directly from a list of Media Pool clips.

    Faster than create_timeline() + append_to_timeline() separately.

    Parameters:
    - timeline_name: Name for the new timeline.
    - clip_names: Ordered list of clip names from the Media Pool to include.
    """
    try:
        conn = _conn()
        clips = []
        not_found = []
        for name in clip_names:
            clip = _find_clip_in_media_pool(conn, name)
            if clip:
                clips.append(clip)
            else:
                not_found.append(name)
        if not clips:
            return f"None of the specified clips were found: {clip_names}"
        new_tl = conn.get_media_pool().CreateTimelineFromClips(timeline_name, clips)
        if not new_tl:
            return f"Failed to create timeline '{timeline_name}'."
        return json.dumps({
            "status": "created",
            "timeline": new_tl.GetName(),
            "clips_added": len(clips),
            "not_found": not_found,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  RENDER (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def render_with_quick_export(
    preset_name: str,
    output_path: Optional[str] = None,
) -> str:
    """Render the current timeline using a Quick Export preset.

    Simpler than the full render queue — no need to configure format/codec separately.
    Use get_render_formats() to browse standard presets, or check Resolve's
    Deliver > Quick Export panel for preset names.

    Parameters:
    - preset_name: Name of the Quick Export preset (e.g. 'H.264', 'YouTube').
    - output_path: Optional output file path. If omitted, uses the preset's default.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        params: Dict[str, Any] = {}
        if output_path:
            params["TargetDir"] = os.path.dirname(output_path)
            params["CustomName"] = os.path.basename(output_path)
        result = project.RenderWithQuickExport(preset_name, params)
        if result:
            return json.dumps({"status": "rendering_started", "preset": preset_name}, indent=2)
        return f"Failed to start Quick Export with preset '{preset_name}'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def save_render_preset(preset_name: str) -> str:
    """Save the current render settings as a new named preset.

    Call this after configuring render settings with set_render_settings().

    Parameters:
    - preset_name: Name for the new render preset.
    """
    try:
        conn = _conn()
        result = conn.get_project().SaveAsNewRenderPreset(preset_name)
        return _ok(result, f"Render preset '{preset_name}' saved.", f"Failed to save render preset '{preset_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_render_job(job_id: Optional[str] = None, delete_all: bool = False) -> str:
    """Delete one or all render jobs from the queue.

    Parameters:
    - job_id: ID of a specific job to delete. Use get_render_settings() to see job IDs.
    - delete_all: If True, deletes all jobs in the queue (ignores job_id).
    """
    try:
        conn = _conn()
        project = conn.get_project()
        if delete_all:
            result = project.DeleteAllRenderJobs()
            return _ok(result, "Deleted all render jobs.", "Failed to delete render jobs.")
        if not job_id:
            return "Error: provide 'job_id' or set 'delete_all=True'."
        result = project.DeleteRenderJob(job_id)
        return _ok(result, f"Deleted render job '{job_id}'.", f"Failed to delete job '{job_id}'.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  GRADING & GALLERY (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def grab_still() -> str:
    """Grab a still from the current clip in the Color page and add it to the Gallery.

    Must be on the Color page with a clip selected. Returns the still reference.
    Use export_gallery_stills() to save stills to disk.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        still = timeline.GrabStill()
        if not still:
            return "Failed to grab still. Make sure you are on the Color page with a clip selected."
        return json.dumps({"status": "grabbed", "timeline": timeline.GetName()}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_gallery_stills(
    folder_path: str,
    album_name: Optional[str] = None,
    file_format: str = "png",
    prefix: str = "",
) -> str:
    """Export gallery stills to a folder on disk.

    Parameters:
    - folder_path: Absolute path to the output folder.
    - album_name: Name of the still album to export from. If omitted, uses the current album.
    - file_format: Output format — 'dpx', 'cin', 'tif', 'jpg', 'png' (default), 'ppm', 'bmp', 'xpm', 'drx'.
    - prefix: Optional filename prefix for exported files.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        gallery = project.GetGallery()
        if not gallery:
            return "Gallery not available."
        if album_name:
            album = _get_gallery_album(conn, album_name)
            if not album:
                return f"Album '{album_name}' not found."
        else:
            album = gallery.GetCurrentStillAlbum()
        if not album:
            return "No album available. Grab a still first with grab_still()."
        stills = album.GetStills() or []
        if not stills:
            return "No stills in the album."
        result = album.ExportStills(stills, folder_path, prefix, file_format)
        return _ok(result, f"Exported {len(stills)} still(s) to {folder_path}",
                   f"Failed to export stills.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_lut(
    export_type: str,
    output_path: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Export the color grade as a LUT file from a timeline clip.

    Must be on the Color page.

    Parameters:
    - export_type: LUT size/type — '17PointCube', '33PointCube', '65PointCube', 'PanasonicVlut'.
    - output_path: Absolute file path for the exported LUT (e.g. '/path/to/grade.cube').
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.ExportLUT(export_type, output_path)
        return _ok(result, f"LUT exported to {output_path}", f"Failed to export LUT.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def copy_grades(
    source_track_index: int,
    source_item_index: int,
    target_item_indices: List[Dict[str, int]],
    track_type: str = "video",
) -> str:
    """Copy the color grade from one clip to other clips on the timeline.

    Must be on the Color page.

    Parameters:
    - source_track_index: 1-based track index of the source clip.
    - source_item_index: 0-based item index of the source clip.
    - target_item_indices: List of dicts with 'track_index' and 'item_index' for targets.
      Example: [{'track_index': 1, 'item_index': 2}, {'track_index': 1, 'item_index': 3}]
    - track_type: Track type for source and targets (default 'video').
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        source = _get_timeline_item(track_type, source_track_index, source_item_index)
        targets = []
        for t in target_item_indices:
            item = _get_timeline_item(track_type, t.get("track_index", 1), t.get("item_index", 0))
            targets.append(item)
        if not targets:
            return "No valid target clips found."
        result = source.CopyGrades(targets)
        return _ok(result, f"Copied grade to {len(targets)} clip(s).", "Failed to copy grades.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_node_enabled(
    node_index: int,
    enabled: bool,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Enable or disable (bypass) a color correction node on a timeline clip.

    Must be on the Color page.

    Parameters:
    - node_index: 1-based node index.
    - enabled: True to enable the node, False to bypass/disable it.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph available. Make sure you are on the Color page."
        result = graph.SetNodeEnabled(node_index, enabled)
        state = "enabled" if enabled else "disabled"
        return _ok(result, f"Node {node_index} {state}.", f"Failed to {state} node {node_index}.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_color_version(
    version_name: str,
    version_type: int = 0,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Add a new color version to a timeline clip.

    Color versions let you maintain multiple independent grades for one clip.

    Parameters:
    - version_name: Name for the new version.
    - version_type: 0 = Local version (default), 1 = Remote version.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.AddVersion(version_name, version_type)
        return _ok(result, f"Added color version '{version_name}'.", f"Failed to add version '{version_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def load_color_version(
    version_name: str,
    version_type: int = 0,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Load (activate) a named color version on a timeline clip.

    Use get_color_versions() to list available versions.

    Parameters:
    - version_name: Exact name of the version to activate.
    - version_type: 0 = Local (default), 1 = Remote.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.LoadVersionByName(version_name, version_type)
        return _ok(result, f"Loaded color version '{version_name}'.", f"Version '{version_name}' not found.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  v21 AI TOOLS (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def generate_speech(
    text: str,
    timecode: str,
    voice: str = "Female 1",
    language: str = "English (United States)",
) -> str:
    """Generate AI speech (text-to-voice) and insert it into the current timeline.

    Requires the AI Speech Generator Extra in DaVinci Resolve Studio v21+.
    Maximum 350 characters per call.

    Parameters:
    - text: The text to speak (max 350 characters).
    - timecode: Timeline position to insert the audio (HH:MM:SS:FF format).
    - voice: Voice to use — 'Female 1' (default), 'Male 1', or 'Custom Voice'.
    - language: Language/accent string (default 'English (United States)').
    """
    try:
        if len(text) > 350:
            return f"Error: text exceeds 350 character limit ({len(text)} characters)."
        conn = _conn()
        project = conn.get_project()
        settings = {
            "text": text,
            "voice": voice,
            "language": language,
        }
        result = project.GenerateSpeech(settings, timecode)
        return _ok(result, f"Speech generated and inserted at {timecode}.",
                   "Failed to generate speech. Check that AI Speech Generator Extra is installed.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def analyze_for_intellisearch(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
    identify_faces: bool = False,
    better_mode: bool = False,
) -> str:
    """Run IntelliSearch AI analysis on a clip or an entire Media Pool bin.

    Requires AI IntelliSearch Extra in DaVinci Resolve Studio v21+.
    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin to analyze (batch mode).
    - clip_name: Name of a single clip to analyze.
    - identify_faces: Enable face detection/recognition (default False).
    - better_mode: Use higher-quality (slower) analysis mode (default False).
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.AnalyzeForIntellisearch(identify_faces, better_mode)
            return _ok(result, f"IntelliSearch analysis started for bin '{folder_name}'.",
                       f"Failed to analyze bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.AnalyzeForIntellisearch(identify_faces, better_mode)
            return _ok(result, f"IntelliSearch analysis started for '{clip_name}'.",
                       f"Failed to analyze '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def remove_motion_blur(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
) -> str:
    """Remove motion blur from a clip or all clips in a Media Pool bin using AI.

    Requires DaVinci Resolve Studio v21+. Creates new de-blurred clips in the Media Pool.
    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin to process (batch mode).
    - clip_name: Name of a single clip to process.
    """
    try:
        conn = _conn()
        deblur_option = {"outputSuffix": "_deblurred"}
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.RemoveMotionBlur(deblur_option)
            if result:
                return json.dumps({"status": "started", "folder": folder_name,
                                   "note": "New de-blurred clips will appear in the Media Pool."}, indent=2)
            return f"Failed to start motion blur removal for bin '{folder_name}'."
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.RemoveMotionBlur(deblur_option)
            if result:
                return json.dumps({"status": "started", "clip": clip_name,
                                   "note": "A new de-blurred clip will appear in the Media Pool."}, indent=2)
            return f"Failed to start motion blur removal for '{clip_name}'."
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def analyze_for_slate(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
    marker_color: str = "Blue",
) -> str:
    """Run AI Slate ID analysis to automatically identify slate/clapperboard info.

    Requires AI Slate ID Extra in DaVinci Resolve Studio v21+.
    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin to analyze (batch mode).
    - clip_name: Name of a single clip to analyze.
    - marker_color: Color for the slate marker (default 'Blue').
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.AnalyzeForSlate(marker_color)
            return _ok(result, f"Slate analysis started for bin '{folder_name}'.",
                       f"Failed to analyze bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.AnalyzeForSlate(marker_color)
            return _ok(result, f"Slate analysis started for '{clip_name}'.",
                       f"Failed to analyze '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def perform_audio_classification(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
) -> str:
    """Classify audio content (speech, music, ambience, etc.) using AI.

    Requires AI Extra in DaVinci Resolve Studio v21+.
    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin to classify (batch mode).
    - clip_name: Name of a single clip to classify.
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.PerformAudioClassification()
            return _ok(result, f"Audio classification started for bin '{folder_name}'.",
                       f"Failed to classify audio in bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.PerformAudioClassification()
            return _ok(result, f"Audio classification started for '{clip_name}'.",
                       f"Failed to classify audio in '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def transcribe_clip_audio(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
    use_speaker_detection: bool = False,
) -> str:
    """Transcribe audio using Resolve's built-in AI (not mlx-whisper).

    Requires DaVinci Resolve Studio v21+. Results appear in the clip's
    transcript metadata, accessible via the Transcription panel.
    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin to transcribe (batch mode).
    - clip_name: Name of a single clip to transcribe.
    - use_speaker_detection: Detect and label different speakers (default False).
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.TranscribeAudio(use_speaker_detection)
            return _ok(result, f"Transcription started for bin '{folder_name}'.",
                       f"Failed to transcribe bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.TranscribeAudio(use_speaker_detection)
            return _ok(result, f"Transcription started for '{clip_name}'.",
                       f"Failed to transcribe '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def apply_fairlight_preset(preset_name: str) -> str:
    """Apply a saved Fairlight audio preset to the current timeline.

    Requires DaVinci Resolve Studio v21+. Use get_fairlight_presets() (coming soon)
    to list available presets.

    Parameters:
    - preset_name: Exact name of the Fairlight preset to apply.
    """
    try:
        conn = _conn()
        result = conn.get_project().ApplyFairlightPresetToCurrentTimeline(preset_name)
        return _ok(result, f"Applied Fairlight preset '{preset_name}'.",
                   f"Failed to apply Fairlight preset '{preset_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def disable_background_tasks() -> str:
    """Disable all background AI tasks for the current Resolve session.

    Useful before running scripts that modify clips or the timeline, to prevent
    AI analysis tasks (IntelliSearch, Audio Classification, etc.) from interfering.
    Requires DaVinci Resolve Studio v21+.

    Note: Background tasks resume when Resolve is restarted.
    """
    try:
        conn = _conn()
        result = conn.get_resolve().DisableBackgroundTasksForCurrentResolveSession()
        return _ok(result, "Background tasks disabled for this session.",
                   "Failed to disable background tasks.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  PHOTO PAGE (HIGH PRIORITY)
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def open_photo_page() -> str:
    """Navigate to the Photo page in DaVinci Resolve (v21+).

    The Photo page is designed for still photo editing and grading.
    Note: open_page('photo') also works if you prefer the generic tool.
    """
    try:
        conn = _conn()
        result = conn.get_resolve().OpenPage("photo")
        return _ok(result, "Opened Photo page.", "Failed to open Photo page (requires Resolve v21+).")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_photo_album(album_name: str, album_type: str = "still") -> str:
    """Create a new Gallery album for stills or PowerGrades.

    Parameters:
    - album_name: Name for the new album.
    - album_type: 'still' (default) for a still album, 'powergrade' for a PowerGrade album.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        gallery = project.GetGallery()
        if not gallery:
            return "Gallery not available."
        if album_type == "powergrade":
            album = gallery.CreateGalleryPowerGradeAlbum()
        else:
            album = gallery.CreateGalleryStillAlbum()
        if not album:
            return f"Failed to create {album_type} album."
        if album_name:
            gallery.SetAlbumName(album, album_name)
        return json.dumps({"status": "created", "album": album_name, "type": album_type}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def manage_photo_albums(
    action: str = "list",
    album_name: Optional[str] = None,
    new_name: Optional[str] = None,
) -> str:
    """List, rename, or navigate Gallery still albums.

    Parameters:
    - action: 'list' (default) — list all albums; 'rename' — rename an album;
      'set_current' — make an album active.
    - album_name: Album name (required for 'rename' and 'set_current').
    - new_name: New name for the album (required for 'rename').
    """
    try:
        conn = _conn()
        project = conn.get_project()
        gallery = project.GetGallery()
        if not gallery:
            return "Gallery not available."
        if action == "list":
            albums = gallery.GetGalleryStillAlbums() or []
            current = gallery.GetCurrentStillAlbum()
            current_name = gallery.GetAlbumName(current) if current else None
            result = []
            for a in albums:
                try:
                    name = gallery.GetAlbumName(a)
                    stills = a.GetStills() or []
                    result.append({"name": name, "still_count": len(stills),
                                   "is_current": name == current_name})
                except Exception:
                    pass
            return json.dumps({"albums": result, "current": current_name}, indent=2)
        if action == "rename":
            if not album_name or not new_name:
                return "Error: 'album_name' and 'new_name' required for rename."
            album = _get_gallery_album(conn, album_name)
            if not album:
                return f"Album '{album_name}' not found."
            result = gallery.SetAlbumName(album, new_name)
            return _ok(result, f"Renamed album '{album_name}' to '{new_name}'.",
                       f"Failed to rename album.")
        if action == "set_current":
            if not album_name:
                return "Error: 'album_name' required for set_current."
            album = _get_gallery_album(conn, album_name)
            if not album:
                return f"Album '{album_name}' not found."
            result = gallery.SetCurrentStillAlbum(album)
            return _ok(result, f"Set '{album_name}' as current album.", "Failed to set current album.")
        return f"Unknown action '{action}'. Use 'list', 'rename', or 'set_current'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_graded_stills(
    folder_path: str,
    album_name: Optional[str] = None,
    file_format: str = "png",
    prefix: str = "",
) -> str:
    """Export graded stills from a Gallery album to a folder on disk.

    Alias for export_gallery_stills() with Photo Page context in mind.

    Parameters:
    - folder_path: Absolute path to the output folder.
    - album_name: Gallery album name. If omitted, uses the current album.
    - file_format: Output format — 'png' (default), 'jpg', 'tif', 'dpx', 'drx'.
    - prefix: Optional filename prefix.
    """
    return export_gallery_stills(
        folder_path=folder_path,
        album_name=album_name,
        file_format=file_format,
        prefix=prefix,
    )


@mcp.tool()
def manage_gallery_stills(
    action: str = "list",
    album_name: Optional[str] = None,
    still_label: Optional[str] = None,
    still_index: Optional[int] = None,
) -> str:
    """List, label, or delete stills in a Gallery album.

    Parameters:
    - action: 'list' — list stills with labels; 'set_label' — set label on a still;
      'delete' — delete a still by index.
    - album_name: Album name. If omitted, uses the current album.
    - still_label: New label text (required for 'set_label').
    - still_index: 0-based still index (required for 'set_label' and 'delete').
    """
    try:
        conn = _conn()
        project = conn.get_project()
        gallery = project.GetGallery()
        if not gallery:
            return "Gallery not available."
        if album_name:
            album = _get_gallery_album(conn, album_name)
            if not album:
                return f"Album '{album_name}' not found."
        else:
            album = gallery.GetCurrentStillAlbum()
        if not album:
            return "No album available."
        stills = album.GetStills() or []
        if action == "list":
            result = []
            for i, s in enumerate(stills):
                try:
                    label = album.GetLabel(s)
                    result.append({"index": i, "label": label})
                except Exception:
                    result.append({"index": i, "label": None})
            return json.dumps({"still_count": len(stills), "stills": result}, indent=2)
        if still_index is None or still_index < 0 or still_index >= len(stills):
            return f"still_index {still_index} out of range — album has {len(stills)} stills."
        still = stills[still_index]
        if action == "set_label":
            if not still_label:
                return "Error: 'still_label' required for set_label."
            result = album.SetLabel(still, still_label)
            return _ok(result, f"Label set to '{still_label}' on still {still_index}.",
                       "Failed to set label.")
        if action == "delete":
            result = album.DeleteStills([still])
            return _ok(result, f"Deleted still {still_index}.", "Failed to delete still.")
        return f"Unknown action '{action}'. Use 'list', 'set_label', or 'delete'."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def set_timeline_name(name: str) -> str:
    """Rename the current timeline.

    Parameters:
    - name: New timeline name.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.SetName(name)
        return _ok(result, f"Timeline renamed to '{name}'.", "Failed to rename timeline.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_start_timecode(timecode: str) -> str:
    """Set the start timecode for the current timeline.

    Parameters:
    - timecode: Start timecode in HH:MM:SS:FF format (e.g. '01:00:00:00').
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.SetStartTimecode(timecode)
        return _ok(result, f"Start timecode set to {timecode}.", "Failed to set start timecode.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_start_timecode() -> str:
    """Get the start timecode of the current timeline."""
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        tc = timeline.GetStartTimecode()
        return json.dumps({"timeline": timeline.GetName(), "start_timecode": tc}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_track_info(track_type: str, track_index: int) -> str:
    """Get name, enabled, locked, and subtype info for a timeline track.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        name = timeline.GetTrackName(track_type, track_index)
        enabled = timeline.GetIsTrackEnabled(track_type, track_index)
        locked = timeline.GetIsTrackLocked(track_type, track_index)
        sub_type = None
        if track_type == "audio":
            try:
                sub_type = timeline.GetTrackSubType(track_type, track_index)
            except Exception:
                pass
        return json.dumps({
            "track_type": track_type,
            "track_index": track_index,
            "name": name,
            "enabled": enabled,
            "locked": locked,
            "sub_type": sub_type,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_track_enable(track_type: str, track_index: int, enabled: bool) -> str:
    """Enable or disable a timeline track.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - enabled: True to enable, False to disable.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.SetTrackEnable(track_type, track_index, enabled)
        state = "enabled" if enabled else "disabled"
        return _ok(result, f"{track_type.capitalize()} track {track_index} {state}.",
                   f"Failed to {state} track.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_track_lock(track_type: str, track_index: int, locked: bool) -> str:
    """Lock or unlock a timeline track.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - locked: True to lock, False to unlock.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.SetTrackLock(track_type, track_index, locked)
        state = "locked" if locked else "unlocked"
        return _ok(result, f"{track_type.capitalize()} track {track_index} {state}.",
                   f"Failed to {state} track.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_track_name(track_type: str, track_index: int, name: str) -> str:
    """Rename a timeline track.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - name: New track name.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.SetTrackName(track_type, track_index, name)
        return _ok(result, f"{track_type.capitalize()} track {track_index} renamed to '{name}'.",
                   "Failed to rename track.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_track(track_type: str, track_index: int) -> str:
    """Delete a track from the current timeline.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index to delete.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.DeleteTrack(track_type, track_index)
        return _ok(result, f"Deleted {track_type} track {track_index}.",
                   f"Failed to delete track.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_generator(generator_name: str) -> str:
    """Insert a standard Resolve generator at the playhead position.

    Common generator names: 'Solid Color', 'Bars and Tone', 'Checkerboard',
    '4 Color Gradient', 'Window'. Use execute_resolve_code() to list all.

    Parameters:
    - generator_name: Name of the generator to insert.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.InsertGeneratorIntoTimeline(generator_name)
        if not item:
            return f"Failed to insert generator '{generator_name}'. Check the name."
        return json.dumps({"status": "inserted", "generator": generator_name}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_title(title_name: str) -> str:
    """Insert a standard Resolve title at the playhead position.

    Common title names: 'Text', 'Text+', 'Scroll', 'Lower Third'.
    Use execute_resolve_code() to list all available titles.

    Parameters:
    - title_name: Name of the title to insert.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.InsertTitleIntoTimeline(title_name)
        if not item:
            return f"Failed to insert title '{title_name}'. Check the name."
        return json.dumps({"status": "inserted", "title": title_name}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def insert_ofx_generator(generator_name: str) -> str:
    """Insert an OFX generator at the playhead position.

    Parameters:
    - generator_name: Name of the OFX generator to insert.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.InsertOFXGeneratorIntoTimeline(generator_name)
        if not item:
            return f"Failed to insert OFX generator '{generator_name}'."
        return json.dumps({"status": "inserted", "ofx_generator": generator_name}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def create_compound_clip(
    track_type: str,
    track_index: int,
    item_indices: List[int],
    clip_name: Optional[str] = None,
) -> str:
    """Create a compound clip from selected timeline items.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - item_indices: List of 0-based item indices to include.
    - clip_name: Optional name for the compound clip.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        items = timeline.GetItemListInTrack(track_type, track_index)
        if not items:
            return f"No items on {track_type} track {track_index}."
        selected = []
        for idx in item_indices:
            if 0 <= idx < len(items):
                selected.append(items[idx])
            else:
                return f"item_index {idx} out of range."
        clip_info = {"name": clip_name} if clip_name else {}
        result = timeline.CreateCompoundClip(selected, clip_info)
        if not result:
            return "Failed to create compound clip."
        return json.dumps({"status": "created", "name": clip_name, "items_merged": len(selected)}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def import_timeline_from_file(
    file_path: str,
    timeline_name: Optional[str] = None,
    source_clips_path: Optional[str] = None,
) -> str:
    """Import a timeline from an AAF, EDL, XML, FCPXML, DRT, or OTIO file.

    Parameters:
    - file_path: Absolute path to the timeline file.
    - timeline_name: Optional name override for the imported timeline.
    - source_clips_path: Optional folder path to locate source clips for relink.
    """
    try:
        conn = _conn()
        options: Dict[str, Any] = {}
        if timeline_name:
            options["timelineName"] = timeline_name
        if source_clips_path:
            options["sourceClipsPath"] = source_clips_path
        timeline = conn.get_media_pool().ImportTimelineFromFile(file_path, options)
        if not timeline:
            return f"Failed to import timeline from '{file_path}'."
        return json.dumps({
            "status": "imported",
            "timeline": timeline.GetName(),
            "file": file_path,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_clips_linked(
    track_type: str,
    track_index: int,
    item_indices: List[int],
    linked: bool = True,
) -> str:
    """Link or unlink clips on the current timeline.

    Linked clips move together when trimmed or repositioned.

    Parameters:
    - track_type: 'video', 'audio', or 'subtitle'.
    - track_index: 1-based track index.
    - item_indices: List of 0-based item indices.
    - linked: True to link (default), False to unlink.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        items_list = timeline.GetItemListInTrack(track_type, track_index)
        if not items_list:
            return f"No items on {track_type} track {track_index}."
        selected = [items_list[i] for i in item_indices if 0 <= i < len(items_list)]
        if not selected:
            return "No valid items found for given indices."
        result = timeline.SetClipsLinked(selected, linked)
        state = "linked" if linked else "unlinked"
        return _ok(result, f"{len(selected)} clip(s) {state}.", f"Failed to {state} clips.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_current_video_item() -> str:
    """Get info about the clip currently under the playhead on the timeline."""
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        item = timeline.GetCurrentVideoItem()
        if not item:
            return "No video item at current playhead position."
        return json.dumps(timeline_item_to_dict(item, 0), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def grab_all_stills(still_frame_source: int = 1) -> str:
    """Grab stills from all clips on the current timeline into the Gallery.

    Must be on the Color page.

    Parameters:
    - still_frame_source: 1 = first frame of each clip (default), 2 = middle frame.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.GrabAllStills(still_frame_source)
        if result is None or result is False:
            return "Failed to grab stills. Make sure you are on the Color page."
        count = len(result) if isinstance(result, list) else "unknown"
        return json.dumps({"status": "grabbed", "still_count": count,
                           "source": "first_frame" if still_frame_source == 1 else "middle_frame"}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_timeline_mark_in_out(
    mark_in: Optional[int] = None,
    mark_out: Optional[int] = None,
    mark_type: str = "all",
) -> str:
    """Set In/Out points on the current timeline.

    Parameters:
    - mark_in: In point as frame number. Omit to leave unchanged.
    - mark_out: Out point as frame number. Omit to leave unchanged.
    - mark_type: 'video', 'audio', or 'all' (default).
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        if mark_in is None and mark_out is None:
            return "Error: provide at least 'mark_in' or 'mark_out'."
        in_val = mark_in if mark_in is not None else timeline.GetStartFrame()
        out_val = mark_out if mark_out is not None else timeline.GetEndFrame()
        result = timeline.SetMarkInOut(in_val, out_val, mark_type)
        return _ok(result, f"In/Out set: {in_val} → {out_val} ({mark_type}).",
                   "Failed to set In/Out points.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def clear_timeline_mark_in_out(mark_type: str = "all") -> str:
    """Clear In/Out points on the current timeline.

    Parameters:
    - mark_type: 'video', 'audio', or 'all' (default).
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        result = timeline.ClearMarkInOut(mark_type)
        return _ok(result, f"In/Out points cleared ({mark_type}).", "Failed to clear In/Out points.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_timeline_node_graph() -> str:
    """Get the timeline-level node graph for color grading.

    The timeline node graph applies grades to all clips on the timeline.
    Must be on the Color page.
    """
    try:
        conn = _conn()
        timeline = _require_timeline(conn)
        graph = timeline.GetNodeGraph()
        if not graph:
            return "Timeline node graph not available. Make sure you are on the Color page."
        return json.dumps(node_graph_to_dict(graph), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TIMELINE ITEM — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def set_clip_name(
    name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Rename a clip on the current timeline.

    Parameters:
    - name: New clip name.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.SetName(name)
        return _ok(result, f"Clip renamed to '{name}'.", f"Failed to rename clip.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_clip_enabled(
    enabled: bool,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Enable or disable a clip on the current timeline.

    Disabled clips are skipped during playback and rendering.

    Parameters:
    - enabled: True to enable, False to disable.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.SetClipEnabled(enabled)
        state = "enabled" if enabled else "disabled"
        return _ok(result, f"Clip {state}.", f"Failed to {state} clip.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_timeline_flags(
    colors: List[str],
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Add flag(s) to a timeline clip.

    Flags are colored markers on the clip used for filtering and organization.

    Parameters:
    - colors: List of flag colors to add (e.g. ['Red', 'Blue']).
      Valid colors: Red, Orange, Yellow, Green, Cyan, Blue, Purple, Pink, Fawn, Lavender,
      Rose, Cocoa, Cream, Lime, Mint, Sky.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        added = []
        failed = []
        for color in colors:
            if item.AddFlag(color):
                added.append(color)
            else:
                failed.append(color)
        return json.dumps({"added": added, "failed": failed,
                           "current_flags": item.GetFlagList()}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def clear_timeline_flags(
    color: str = "All",
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Remove flags from a timeline clip.

    Parameters:
    - color: Flag color to remove, or 'All' to remove all flags (default).
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.ClearFlags(color)
        return _ok(result, f"Flags cleared ({color}).", "Failed to clear flags.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_clip_positions(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Get position and duration info for a timeline clip.

    Returns start, end, duration, source start/end frames, and available trim margins.

    Parameters:
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        return json.dumps({
            "start": item.GetStart(),
            "end": item.GetEnd(),
            "duration": item.GetDuration(),
            "source_start_frame": item.GetSourceStartFrame(),
            "source_end_frame": item.GetSourceEndFrame(),
            "left_offset": item.GetLeftOffset(),
            "right_offset": item.GetRightOffset(),
            "track_type": track_type,
            "track_index": track_index,
            "item_index": item_index,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def assign_color_group(
    group_name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Assign a timeline clip to a Color Group.

    Color Groups apply shared pre/post-clip grades to all assigned clips.
    Use get_color_groups() to see available groups.

    Parameters:
    - group_name: Name of the Color Group to assign to.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        conn = _conn()
        item = _get_timeline_item(track_type, track_index, item_index)
        groups = conn.get_project().GetColorGroupsList() or []
        target_group = None
        for g in groups:
            try:
                if g.GetName() == group_name:
                    target_group = g
                    break
            except Exception:
                pass
        if not target_group:
            return f"Color Group '{group_name}' not found. Use get_color_groups() to list available groups."
        result = item.AssignToColorGroup(target_group)
        return _ok(result, f"Clip assigned to Color Group '{group_name}'.",
                   f"Failed to assign clip to group '{group_name}'.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def remove_from_color_group(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Remove a timeline clip from its Color Group.

    Parameters:
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.RemoveFromColorGroup()
        return _ok(result, "Clip removed from Color Group.", "Failed to remove clip from Color Group.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def update_sidecar(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Update the sidecar file for a BRAW or R3D clip on the timeline.

    Call this after changing RAW parameters to write the changes to the sidecar.

    Parameters:
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.UpdateSidecar()
        return _ok(result, "Sidecar updated.", "Failed to update sidecar (clip may not be BRAW/R3D).")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_linked_items(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Get all clips linked to a specific timeline clip.

    Parameters:
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        linked = item.GetLinkedItems() or []
        result = []
        for i, linked_item in enumerate(linked):
            try:
                info = item.GetTrackTypeAndIndex()
                result.append({"index": i, "name": linked_item.GetName(),
                               "track_info": info})
            except Exception:
                result.append({"index": i, "name": str(linked_item)})
        return json.dumps({"linked_count": len(result), "linked_items": result}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_cache_mode(
    color_cache: Optional[str] = None,
    fusion_cache: Optional[str] = None,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Set Color and/or Fusion output cache mode for a timeline clip.

    Parameters:
    - color_cache: Color output cache — 'auto', 'on', or 'off'. Omit to leave unchanged.
    - fusion_cache: Fusion output cache — 'auto', 'on', or 'off'. Omit to leave unchanged.
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        results = {}
        if color_cache is not None:
            r = item.SetColorOutputCache(color_cache)
            results["color_cache"] = color_cache if r else "failed"
        if fusion_cache is not None:
            r = item.SetFusionOutputCache(fusion_cache)
            results["fusion_cache"] = fusion_cache if r else "failed"
        if not results:
            return "Error: provide 'color_cache' and/or 'fusion_cache'."
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  MEDIA POOL — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def delete_clips(clip_names: List[str]) -> str:
    """Delete clips from the Media Pool permanently.

    Parameters:
    - clip_names: List of exact clip names to delete from the Media Pool.
    """
    try:
        conn = _conn()
        clips = []
        not_found = []
        for name in clip_names:
            clip = _find_clip_in_media_pool(conn, name)
            if clip:
                clips.append(clip)
            else:
                not_found.append(name)
        if not clips:
            return f"None of the specified clips were found: {clip_names}"
        result = conn.get_media_pool().DeleteClips(clips)
        return json.dumps({
            "status": "ok" if result else "failed",
            "deleted": len(clips),
            "not_found": not_found,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_folders(folder_names: List[str]) -> str:
    """Delete bins from the Media Pool.

    Parameters:
    - folder_names: List of exact bin names to delete.
    """
    try:
        conn = _conn()
        folders = []
        not_found = []
        for name in folder_names:
            folder = _find_folder_in_media_pool(conn, name)
            if folder:
                folders.append(folder)
            else:
                not_found.append(name)
        if not folders:
            return f"None of the specified bins were found: {folder_names}"
        result = conn.get_media_pool().DeleteFolders(folders)
        return json.dumps({
            "status": "ok" if result else "failed",
            "deleted": len(folders),
            "not_found": not_found,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def move_folders(folder_names: List[str], target_folder_name: str) -> str:
    """Move bins into another bin in the Media Pool.

    Parameters:
    - folder_names: List of exact bin names to move.
    - target_folder_name: Exact name of the destination bin.
    """
    try:
        conn = _conn()
        target = _find_folder_in_media_pool(conn, target_folder_name)
        if not target:
            return f"Target bin '{target_folder_name}' not found."
        folders = []
        not_found = []
        for name in folder_names:
            folder = _find_folder_in_media_pool(conn, name)
            if folder:
                folders.append(folder)
            else:
                not_found.append(name)
        if not folders:
            return f"None of the specified bins were found."
        result = conn.get_media_pool().MoveFolders(folders, target)
        return json.dumps({
            "status": "ok" if result else "failed",
            "moved": len(folders),
            "not_found": not_found,
            "target": target_folder_name,
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def export_metadata_csv(
    output_path: str,
    clip_names: Optional[List[str]] = None,
) -> str:
    """Export clip metadata to a CSV file.

    Parameters:
    - output_path: Absolute file path for the CSV export.
    - clip_names: Optional list of clip names to export. If omitted, exports all clips
      in the current Media Pool folder.
    """
    try:
        conn = _conn()
        clips = None
        if clip_names:
            clips = []
            not_found = []
            for name in clip_names:
                clip = _find_clip_in_media_pool(conn, name)
                if clip:
                    clips.append(clip)
                else:
                    not_found.append(name)
            if not clips:
                return f"None of the specified clips were found."
        result = conn.get_media_pool().ExportMetadata(output_path, clips or [])
        return _ok(result, f"Metadata exported to {output_path}.", "Failed to export metadata.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def link_proxy_media(clip_name: str, proxy_file_path: str) -> str:
    """Link a proxy media file to a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - proxy_file_path: Absolute path to the proxy media file.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        result = clip.LinkProxyMedia(proxy_file_path)
        return _ok(result, f"Proxy linked to '{clip_name}'.", f"Failed to link proxy.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def unlink_proxy_media(clip_name: str) -> str:
    """Remove the proxy media link from a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        result = clip.UnlinkProxyMedia()
        return _ok(result, f"Proxy unlinked from '{clip_name}'.", "Failed to unlink proxy.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_selected_clips() -> str:
    """Get the currently selected clips in the Media Pool UI."""
    try:
        conn = _conn()
        clips = conn.get_media_pool().GetSelectedClips() or []
        result = []
        for clip in clips:
            try:
                result.append(clip_to_dict_brief(clip))
            except Exception:
                result.append({"name": str(clip)})
        return json.dumps({"selected_count": len(result), "clips": result}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def clear_transcription(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
) -> str:
    """Delete Resolve AI transcription data from a clip or bin.

    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin.
    - clip_name: Name of a single clip.
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.ClearTranscription()
            return _ok(result, f"Transcription cleared for bin '{folder_name}'.",
                       f"Failed to clear transcription for bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.ClearTranscription()
            return _ok(result, f"Transcription cleared for '{clip_name}'.",
                       f"Failed to clear transcription for '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def clear_audio_classification(
    folder_name: Optional[str] = None,
    clip_name: Optional[str] = None,
) -> str:
    """Delete AI audio classification data from a clip or bin.

    Provide either folder_name (batch) or clip_name (single clip).

    Parameters:
    - folder_name: Name of a Media Pool bin.
    - clip_name: Name of a single clip.
    """
    try:
        conn = _conn()
        if folder_name:
            folder = _find_folder_in_media_pool(conn, folder_name)
            if not folder:
                return f"Bin '{folder_name}' not found."
            result = folder.ClearAudioClassification()
            return _ok(result, f"Audio classification cleared for bin '{folder_name}'.",
                       f"Failed to clear audio classification for bin '{folder_name}'.")
        if clip_name:
            clip = _find_clip_in_media_pool(conn, clip_name)
            if not clip:
                return f"Clip '{clip_name}' not found."
            result = clip.ClearAudioClassification()
            return _ok(result, f"Audio classification cleared for '{clip_name}'.",
                       f"Failed to clear audio classification for '{clip_name}'.")
        return "Error: provide 'folder_name' or 'clip_name'."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  GALLERY & GRADING — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def import_stills(file_paths: List[str], album_name: Optional[str] = None) -> str:
    """Import still images into a Gallery album.

    Parameters:
    - file_paths: List of absolute file paths to still images (.dpx, .tif, .jpg, .png, .drx).
    - album_name: Gallery album to import into. If omitted, uses the current album.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        gallery = project.GetGallery()
        if not gallery:
            return "Gallery not available."
        if album_name:
            album = _get_gallery_album(conn, album_name)
            if not album:
                return f"Album '{album_name}' not found."
        else:
            album = gallery.GetCurrentStillAlbum()
        if not album:
            return "No album available. Create one with create_photo_album() first."
        result = album.ImportStills(file_paths)
        return _ok(result, f"Imported {len(file_paths)} still(s) into album.",
                   "Failed to import stills.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_color_groups() -> str:
    """List all Color Groups in the current project."""
    try:
        conn = _conn()
        groups = conn.get_project().GetColorGroupsList() or []
        result = []
        for g in groups:
            try:
                result.append({"name": g.GetName()})
            except Exception:
                result.append({"name": str(g)})
        return json.dumps({"color_group_count": len(result), "color_groups": result}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def add_color_group(group_name: str) -> str:
    """Create a new Color Group in the current project.

    Color Groups let you apply shared pre/post-clip grades to multiple clips.

    Parameters:
    - group_name: Name for the new Color Group.
    """
    try:
        conn = _conn()
        group = conn.get_project().AddColorGroup(group_name)
        if not group:
            return f"Failed to create Color Group '{group_name}'."
        return json.dumps({"status": "created", "color_group": group_name}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_color_group(group_name: str) -> str:
    """Delete a Color Group from the current project.

    Parameters:
    - group_name: Exact name of the Color Group to delete.
    """
    try:
        conn = _conn()
        project = conn.get_project()
        groups = project.GetColorGroupsList() or []
        target = None
        for g in groups:
            try:
                if g.GetName() == group_name:
                    target = g
                    break
            except Exception:
                pass
        if not target:
            return f"Color Group '{group_name}' not found."
        result = project.DeleteColorGroup(target)
        return _ok(result, f"Color Group '{group_name}' deleted.", f"Failed to delete Color Group.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_group_node_graph(group_name: str, graph_type: str = "pre") -> str:
    """Get the pre-clip or post-clip node graph for a Color Group.

    Parameters:
    - group_name: Exact Color Group name.
    - graph_type: 'pre' (default) for pre-clip graph, 'post' for post-clip graph.
    """
    try:
        conn = _conn()
        groups = conn.get_project().GetColorGroupsList() or []
        target = None
        for g in groups:
            try:
                if g.GetName() == group_name:
                    target = g
                    break
            except Exception:
                pass
        if not target:
            return f"Color Group '{group_name}' not found."
        if graph_type == "post":
            graph = target.GetPostClipNodeGraph()
        else:
            graph = target.GetPreClipNodeGraph()
        if not graph:
            return f"No {graph_type}-clip node graph found for group '{group_name}'."
        return json.dumps(node_graph_to_dict(graph), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_color_versions(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
    version_type: int = 0,
) -> str:
    """List all color versions for a timeline clip.

    Parameters:
    - track_type: 'video' (default), 'audio', or 'subtitle'.
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    - version_type: 0 = Local (default), 1 = Remote.
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        versions = item.GetVersionNameList(version_type) or []
        current = item.GetCurrentVersion()
        current_name = None
        if current:
            try:
                current_name = current.get("versionName") if isinstance(current, dict) else str(current)
            except Exception:
                pass
        return json.dumps({
            "version_count": len(versions),
            "current_version": current_name,
            "versions": versions,
            "version_type": "local" if version_type == 0 else "remote",
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_color_version(
    version_name: str,
    version_type: int = 0,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Delete a color version from a timeline clip.

    Parameters:
    - version_name: Exact name of the version to delete.
    - version_type: 0 = Local (default), 1 = Remote.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.DeleteVersionByName(version_name, version_type)
        return _ok(result, f"Deleted color version '{version_name}'.",
                   f"Failed to delete version '{version_name}'.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  GRAPH / NODEGRAF — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_node_info(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Get detailed info about all nodes in a clip's color node graph.

    Returns node count, labels, tools per node, and LUT paths.
    Must be on the Color page.

    Parameters:
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph. Make sure you are on the Color page."
        num = graph.GetNumNodes()
        nodes = []
        for i in range(1, num + 1):
            node_info: Dict[str, Any] = {"node_index": i}
            try:
                node_info["label"] = graph.GetNodeLabel(i)
            except Exception:
                pass
            try:
                node_info["lut"] = graph.GetLUT(i)
            except Exception:
                pass
            try:
                node_info["tools"] = graph.GetToolsInNode(i)
            except Exception:
                pass
            nodes.append(node_info)
        return json.dumps({"node_count": num, "nodes": nodes}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_node_cache_mode(
    node_index: int,
    cache_mode: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Set the cache mode for a specific node in the color node graph.

    Parameters:
    - node_index: 1-based node index.
    - cache_mode: 'auto', 'on', or 'off'.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph. Make sure you are on the Color page."
        result = graph.SetNodeCacheMode(node_index, cache_mode)
        return _ok(result, f"Node {node_index} cache mode set to '{cache_mode}'.",
                   f"Failed to set cache mode.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def apply_grade_from_drx(
    drx_path: str,
    grade_mode: int = 0,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Apply a grade from a .drx still file to a timeline clip.

    Parameters:
    - drx_path: Absolute path to the .drx file.
    - grade_mode: 0 = No keyframes (default), 1 = Source timecode, 2 = Timeline timecode.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph. Make sure you are on the Color page."
        result = graph.ApplyGradeFromDRX(drx_path, grade_mode)
        return _ok(result, f"Grade applied from '{drx_path}'.", "Failed to apply grade from DRX.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def apply_arri_cdl_lut(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Apply the ARRI CDL and LUT to a timeline clip's node graph.

    Used for ARRI camera footage that includes embedded CDL and LUT metadata.
    Must be on the Color page.

    Parameters:
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph. Make sure you are on the Color page."
        result = graph.ApplyArriCdlLut()
        return _ok(result, "ARRI CDL+LUT applied.", "Failed to apply ARRI CDL+LUT.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def reset_all_grades(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Reset all grades in the node graph for a timeline clip.

    Clears all color corrections from all nodes. Cannot be undone via this tool.
    Must be on the Color page.

    Parameters:
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        graph = item.GetNodeGraph()
        if not graph:
            return "No node graph. Make sure you are on the Color page."
        result = graph.ResetAllGrades()
        return _ok(result, "All grades reset.", "Failed to reset grades.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  RESOLVE-LEVEL — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def manage_layout_presets(
    action: str = "list",
    preset_name: Optional[str] = None,
    export_path: Optional[str] = None,
    import_path: Optional[str] = None,
) -> str:
    """List, load, save, export, or delete UI layout presets.

    Parameters:
    - action: 'list' — not supported via API (use Resolve UI);
      'load' — load a preset; 'save' — save current layout as preset;
      'export' — export preset to file; 'delete' — delete a preset.
    - preset_name: Preset name (required for load, save, export, delete).
    - export_path: File path for export action.
    - import_path: File path to import a preset from (action='import').
    """
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        if action == "load":
            if not preset_name:
                return "Error: 'preset_name' required."
            result = resolve.LoadLayoutPreset(preset_name)
            return _ok(result, f"Layout preset '{preset_name}' loaded.",
                       f"Failed to load preset '{preset_name}'.")
        if action == "save":
            if not preset_name:
                return "Error: 'preset_name' required."
            result = resolve.SaveLayoutPreset(preset_name)
            return _ok(result, f"Layout saved as preset '{preset_name}'.",
                       f"Failed to save preset '{preset_name}'.")
        if action == "export":
            if not preset_name or not export_path:
                return "Error: 'preset_name' and 'export_path' required."
            result = resolve.ExportLayoutPreset(preset_name, export_path)
            return _ok(result, f"Preset '{preset_name}' exported to {export_path}.",
                       "Failed to export preset.")
        if action == "import":
            if not import_path:
                return "Error: 'import_path' required."
            name = preset_name or os.path.splitext(os.path.basename(import_path))[0]
            result = resolve.ImportLayoutPreset(import_path, name)
            return _ok(result, f"Preset imported as '{name}'.", "Failed to import preset.")
        if action == "delete":
            if not preset_name:
                return "Error: 'preset_name' required."
            result = resolve.DeleteLayoutPreset(preset_name)
            return _ok(result, f"Preset '{preset_name}' deleted.", "Failed to delete preset.")
        return f"Unknown action '{action}'. Use 'load', 'save', 'export', 'import', or 'delete'."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_keyframe_mode(mode: Optional[str] = None) -> str:
    """Get or set the keyframe mode for color grading.

    Parameters:
    - mode: 'all' — all parameters; 'color' — color parameters only;
      'sizing' — sizing parameters only. Omit to get the current mode.
    """
    try:
        conn = _conn()
        resolve = conn.get_resolve()
        mode_map = {"all": 0, "color": 1, "sizing": 2}
        reverse_map = {0: "all", 1: "color", 2: "sizing"}
        if mode is None:
            current = resolve.GetKeyframeMode()
            return json.dumps({"keyframe_mode": reverse_map.get(current, current)}, indent=2)
        if mode not in mode_map:
            return f"Invalid mode '{mode}'. Use 'all', 'color', or 'sizing'."
        result = resolve.SetKeyframeMode(mode_map[mode])
        return _ok(result, f"Keyframe mode set to '{mode}'.", f"Failed to set keyframe mode.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_fairlight_presets() -> str:
    """List available Fairlight audio presets."""
    try:
        conn = _conn()
        presets = conn.get_resolve().GetFairlightPresets() or []
        return json.dumps({"preset_count": len(presets), "presets": presets}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def reset_intellisearch() -> str:
    """Delete all IntelliSearch analysis data for the current project.

    Use this to re-run IntelliSearch analysis from scratch.
    Requires DaVinci Resolve Studio v21+.
    """
    try:
        conn = _conn()
        result = conn.get_project().ResetIntellisearchAnalysis()
        return _ok(result, "IntelliSearch analysis data reset.",
                   "Failed to reset IntelliSearch data.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def refresh_lut_list() -> str:
    """Refresh Resolve's LUT list from disk.

    Call this after installing new LUT files to make them available in the UI and API.
    """
    try:
        conn = _conn()
        result = conn.get_project().RefreshLUTList()
        return _ok(result, "LUT list refreshed.", "Failed to refresh LUT list.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  MEDIAPOOLITEM EXTRA — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_third_party_metadata(
    clip_name: str,
    metadata_type: Optional[str] = None,
) -> str:
    """Read third-party metadata from a Media Pool clip.

    Third-party metadata is written by cameras, NLEs, or production tools
    and stored separately from Resolve's native metadata.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - metadata_type: Specific metadata key. If omitted, returns all.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        if metadata_type:
            value = clip.GetThirdPartyMetadata(metadata_type)
            return json.dumps({"clip": clip_name, metadata_type: value}, indent=2)
        value = clip.GetThirdPartyMetadata()
        return json.dumps({"clip": clip_name, "third_party_metadata": value}, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_third_party_metadata(clip_name: str, metadata_type: str, value: str) -> str:
    """Write a third-party metadata value to a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - metadata_type: Metadata key to set.
    - value: Value to write.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        result = clip.SetThirdPartyMetadata(metadata_type, value)
        return _ok(result, f"Third-party metadata '{metadata_type}' set on '{clip_name}'.",
                   "Failed to set third-party metadata.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_audio_mapping(clip_name: str) -> str:
    """Get the audio channel mapping for a Media Pool clip.

    Returns a JSON string describing how source audio channels are mapped.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        mapping = clip.GetAudioMapping()
        return json.dumps({"clip": clip_name, "audio_mapping": mapping}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_clip_mark_in_out(
    clip_name: str,
    mark_in: Optional[int] = None,
    mark_out: Optional[int] = None,
    mark_type: str = "all",
) -> str:
    """Set In/Out points on a Media Pool clip.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - mark_in: In point as frame number.
    - mark_out: Out point as frame number.
    - mark_type: 'video', 'audio', or 'all' (default).
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        if mark_in is None and mark_out is None:
            return "Error: provide at least 'mark_in' or 'mark_out'."
        current = clip.GetMarkInOut() or {}
        in_val = mark_in if mark_in is not None else current.get("in", 0)
        out_val = mark_out if mark_out is not None else current.get("out", 0)
        result = clip.SetMarkInOut(in_val, out_val, mark_type)
        return _ok(result, f"In/Out set on '{clip_name}': {in_val} → {out_val} ({mark_type}).",
                   "Failed to set In/Out points.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def replace_clip_preserve_subclip(clip_name: str, new_file_path: str) -> str:
    """Replace a Media Pool clip's media file while preserving sub-clip boundaries.

    Use this instead of replace_clip() when the clip has sub-clips that must be kept.

    Parameters:
    - clip_name: Exact clip name in the Media Pool.
    - new_file_path: Absolute path to the replacement media file.
    """
    try:
        conn = _conn()
        clip = _find_clip_in_media_pool(conn, clip_name)
        if not clip:
            return f"Clip '{clip_name}' not found."
        result = clip.ReplaceClipPreserveSubClip(new_file_path)
        return _ok(result, f"Clip '{clip_name}' replaced (sub-clips preserved).",
                   "Failed to replace clip.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  TAKES — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def add_take(
    media_clip_name: str,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
    start_frame: Optional[int] = None,
    end_frame: Optional[int] = None,
) -> str:
    """Add a Media Pool clip as a take to a timeline clip's take selector.

    Parameters:
    - media_clip_name: Name of the Media Pool clip to add as a take.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    - start_frame: Optional start frame within the media clip.
    - end_frame: Optional end frame within the media clip.
    """
    try:
        conn = _conn()
        item = _get_timeline_item(track_type, track_index, item_index)
        media_clip = _find_clip_in_media_pool(conn, media_clip_name)
        if not media_clip:
            return f"Media Pool clip '{media_clip_name}' not found."
        args = [media_clip]
        if start_frame is not None:
            args.append(start_frame)
        if end_frame is not None:
            args.append(end_frame)
        result = item.AddTake(*args)
        return _ok(result, f"Take '{media_clip_name}' added.", "Failed to add take.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def select_take(
    take_index: int,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Select a take by index in a timeline clip's take selector.

    Parameters:
    - take_index: 1-based take index to select.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        count = item.GetTakesCount()
        result = json.dumps({
            "takes_count": count,
            "selected_take": item.GetSelectedTakeIndex(),
        }, indent=2)
        ok = item.SelectTakeByIndex(take_index)
        if not ok:
            return f"Failed to select take {take_index}. Clip has {count} take(s)."
        return f"Take {take_index} selected. (Previously: {result})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_take(
    take_index: int,
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Delete a take from a timeline clip's take selector.

    Parameters:
    - take_index: 1-based take index to delete.
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.DeleteTakeByIndex(take_index)
        return _ok(result, f"Take {take_index} deleted.", f"Failed to delete take {take_index}.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def finalize_take(
    track_type: str = "video",
    track_index: int = 1,
    item_index: int = 0,
) -> str:
    """Finalize the selected take for a timeline clip.

    Converts the take selector back to a regular clip using the selected take.

    Parameters:
    - track_type: 'video' (default).
    - track_index: 1-based track index (default 1).
    - item_index: 0-based item index (default 0).
    """
    try:
        item = _get_timeline_item(track_type, track_index, item_index)
        result = item.FinalizeTake()
        return _ok(result, "Take finalized.", "Failed to finalize take.")
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════
#  PROJECT / DATABASE — MEDIUM PRIORITY
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
def close_project(save_first: bool = False) -> str:
    """Close the current project.

    Parameters:
    - save_first: If True, saves the project before closing (default False).
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        if save_first:
            pm.SaveProject()
        project = conn.get_project()
        result = pm.CloseProject(project)
        return _ok(result, "Project closed.", "Failed to close project.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_project_database_info() -> str:
    """Get info about the current Resolve database and list all available databases."""
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        current = pm.GetCurrentDatabase()
        all_dbs = pm.GetDatabaseList() or []
        return json.dumps({
            "current_database": current,
            "database_count": len(all_dbs),
            "databases": all_dbs,
        }, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def switch_database(db_type: str, db_name: str, ip_address: Optional[str] = None) -> str:
    """Switch to a different Resolve database.

    Closing the current project is required. Resolve will reconnect.

    Parameters:
    - db_type: 'local' for local disk database, 'network' for PostgreSQL/remote.
    - db_name: Database name.
    - ip_address: IP address (required for network databases).
    """
    try:
        conn = _conn()
        db_info: Dict[str, Any] = {"DbType": db_type, "DbName": db_name}
        if ip_address:
            db_info["IpAddress"] = ip_address
        result = conn.get_project_manager().SetCurrentDatabase(db_info)
        return _ok(result, f"Switched to database '{db_name}' ({db_type}).",
                   "Failed to switch database. Close the current project first.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def import_project(file_path: str, project_name: Optional[str] = None) -> str:
    """Import a DaVinci Resolve project from a .drp file.

    Parameters:
    - file_path: Absolute path to the .drp file.
    - project_name: Optional name override. If omitted, uses the name stored in the file.
    """
    try:
        conn = _conn()
        pm = conn.get_project_manager()
        result = pm.ImportProject(file_path, project_name or "")
        return _ok(result, f"Project imported from '{file_path}'.",
                   f"Failed to import project from '{file_path}'.")
    except Exception as e:
        return f"Error: {e}"


# ── Entry point ──

def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
