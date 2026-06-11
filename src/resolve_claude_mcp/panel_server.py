"""
Local HTTP bridge for the Resolve workspace panel.

The MCP server speaks stdio with Claude Desktop, so the HTML panel cannot
call it directly. This module exposes the same underlying functionality
over a small localhost-only HTTP API and serves the panel's static files.

Run alongside the MCP server:
    uv run python -m resolve_claude_mcp.panel_server
then open http://127.0.0.1:8765 (port: RESOLVE_MCP_PANEL_PORT).

Endpoints:
    GET  /api/status                  connection + project/timeline names
    POST /api/markers/parse           {text, fps?} → parsed markers
    POST /api/markers/set             {markers} → write markers to timeline
    GET  /api/subtitle-tracks         subtitle tracks on current timeline
    POST /api/transcribe              {language, output_mode, track_index?} → {job_id}
    GET  /api/transcribe/<job_id>     poll a transcription job
    POST /api/subtitles/write         {segments, output_mode, ...} → write subtitles

Security: binds to 127.0.0.1 only. Cross-origin requests are allowed only
from localhost origins or file:// (origin "null") so the panel works both
served from this bridge and opened as a local file.
"""

import json
import logging
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .markers import (
    parse_marker_list,
    timecode_to_frame,
    frame_to_timecode,
    VALID_MARKER_COLORS,
    DEFAULT_COLOR,
)
from .transcription import (
    transcribe_audio,
    get_subtitle_tracks,
    get_subtitle_track_segments,
    write_subtitle_track,
    correct_subtitle_track,
    map_transcription_to_segments,
)
from .media_pool import read_finder_structure, sync_structure_to_media_pool
from .server import _conn, _require_timeline, _render_timeline_audio, _normalize_language

logger = logging.getLogger("ResolveMCP")

DEFAULT_PORT = 8765
PANEL_DIR_ENV_VAR = "RESOLVE_MCP_PANEL_DIR"

_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}

# ── Transcription job store ─────────────────────────────────────────

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()

# ── Pending markers (pushed by the MCP server, polled by the panel) ──

_pending_markers: list = []
_pending_markers_lock = threading.Lock()


def _panel_dir() -> Path:
    override = os.getenv(PANEL_DIR_ENV_VAR)
    if override:
        return Path(override)
    # src/resolve_claude_mcp/panel_server.py → repo root is two levels above src/
    return Path(__file__).resolve().parents[2] / "panel"


def _timeline_fps(timeline) -> float:
    fps_setting = timeline.GetSetting("timelineFrameRate")
    if not fps_setting:
        raise RuntimeError("Could not read frame rate from timeline")
    return float(fps_setting)


# ── API handlers (each returns a JSON-serializable dict) ───────────

def _api_status() -> Dict[str, Any]:
    try:
        conn = _conn()
        project = conn.get_project()
        timeline = conn.get_current_timeline()
        return {
            "connected": True,
            "project": project.GetName(),
            "timeline": timeline.GetName() if timeline else None,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def _api_markers_parse(body: Dict[str, Any]) -> Dict[str, Any]:
    text = body.get("text", "")
    conn = _conn()
    project = conn.get_project()
    timeline = _require_timeline(conn)
    fps = float(body["fps"]) if body.get("fps") else _timeline_fps(timeline)
    markers, skipped = parse_marker_list(text, fps)
    return {
        "project": project.GetName(),
        "timeline": timeline.GetName(),
        "fps": fps,
        "markers": markers,
        "skipped_lines": skipped,
    }


def _api_markers_set(body: Dict[str, Any]) -> Dict[str, Any]:
    markers = body.get("markers", [])
    conn = _conn()
    project = conn.get_project()
    timeline = _require_timeline(conn)
    fps = _timeline_fps(timeline)

    set_count = 0
    failures = []
    for i, marker in enumerate(markers):
        name = marker.get("name", "")
        # Rows edited in the panel carry a timecode, not a frame — convert
        frame = marker.get("frame")
        if frame is None and marker.get("timecode"):
            try:
                frame = timecode_to_frame(marker["timecode"], fps)
            except ValueError as e:
                failures.append({"index": i, "marker": name, "reason": str(e)})
                continue
        if not isinstance(frame, int) or frame < 0:
            failures.append({"index": i, "marker": name, "reason": f"invalid frame: {frame!r}"})
            continue

        color = marker.get("color") or DEFAULT_COLOR
        if color not in VALID_MARKER_COLORS:
            failures.append({"index": i, "marker": name, "reason": f"invalid color: {color!r}"})
            continue

        success = timeline.AddMarker(
            frame, color, name, marker.get("note", ""), marker.get("duration", 1), ""
        )
        if success:
            set_count += 1
        else:
            failures.append({
                "index": i, "marker": name,
                "reason": f"AddMarker failed at frame {frame}",
            })

    return {
        "project": project.GetName(),
        "timeline": timeline.GetName(),
        "requested": len(markers),
        "set": set_count,
        "failures": failures,
    }


def _api_markers_load(body: Dict[str, Any]) -> Dict[str, Any]:
    """Receive a marker list pushed by Claude (via the MCP server)."""
    global _pending_markers
    markers = body.get("markers")
    if not isinstance(markers, list):
        raise ValueError("markers must be a list")
    with _pending_markers_lock:
        _pending_markers = list(markers)
    return {"ok": True, "count": len(markers)}


def _api_markers_pending() -> Dict[str, Any]:
    """Return and clear the pushed marker list (polled by the panel)."""
    global _pending_markers
    with _pending_markers_lock:
        markers, _pending_markers = _pending_markers, []
    return {"markers": markers}


def _api_markers_timeline() -> Dict[str, Any]:
    """Read the existing markers on the current timeline for the editor."""
    conn = _conn()
    timeline = _require_timeline(conn)
    fps = _timeline_fps(timeline)

    raw = timeline.GetMarkers() or {}
    markers = []
    for frame_key, info in sorted(raw.items(), key=lambda kv: int(kv[0])):
        frame = int(frame_key)
        markers.append({
            "frame": frame,
            "timecode": frame_to_timecode(frame, fps),
            "name": info.get("name", ""),
            "color": info.get("color", DEFAULT_COLOR),
            "note": info.get("note", ""),
            "duration": info.get("duration", 1),
        })
    return {"markers": markers}


def _api_subtitle_tracks() -> Dict[str, Any]:
    conn = _conn()
    timeline = _require_timeline(conn)
    return {"tracks": get_subtitle_tracks(timeline)}


def _api_transcribe_start(body: Dict[str, Any]) -> Dict[str, Any]:
    language = _normalize_language(body.get("language", "auto"))
    output_mode = body.get("output_mode", "new")
    track_index = body.get("track_index")
    model = body.get("model", "turbo")

    if output_mode not in ("new", "correct"):
        raise ValueError("output_mode must be 'new' or 'correct'")
    if output_mode == "correct" and track_index is None:
        raise ValueError("track_index is required when output_mode='correct'")

    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"state": "running", "step": "starting"}

    def _set(updates: Dict[str, Any]):
        with _jobs_lock:
            _jobs[job_id].update(updates)

    def _run():
        try:
            conn = _conn()
            project = conn.get_project()
            timeline = _require_timeline(conn)

            existing = None
            if output_mode == "correct":
                existing = get_subtitle_track_segments(timeline, int(track_index))

            _set({"step": "rendering audio"})
            audio_path = _render_timeline_audio(project)

            _set({"step": "transcribing"})
            transcription = transcribe_audio(
                audio_path,
                language=language,
                model=model,
                word_timestamps=(output_mode == "correct"),
            )

            segments = (
                map_transcription_to_segments(existing, transcription)
                if output_mode == "correct"
                else transcription["segments"]
            )
            _set({
                "state": "done", "step": "done",
                "language": transcription["language"],
                "output_mode": output_mode,
                "track_index": track_index,
                "segments": segments,
            })
        except Exception as e:
            logger.exception("Transcription job %s failed", job_id)
            _set({"state": "error", "error": str(e)})

    threading.Thread(target=_run, name=f"transcribe-{job_id}", daemon=True).start()
    return {"job_id": job_id}


def _api_transcribe_status(job_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        return dict(job)


def _api_media_pool_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    """Run a Finder → Media Pool sync for a root folder."""
    folder_path = (body.get("folder_path") or "").strip()
    if not folder_path:
        raise ValueError("folder_path is required")

    conn = _conn()
    project = conn.get_project()
    media_pool = conn.get_media_pool()

    structure = read_finder_structure(folder_path)
    report = sync_structure_to_media_pool(media_pool, structure)
    return {
        "project": project.GetName(),
        "synced_path": structure["path"],
        **report,
    }


def _api_subtitles_write(body: Dict[str, Any]) -> Dict[str, Any]:
    segments = body.get("segments", [])
    output_mode = body.get("output_mode", "new")
    conn = _conn()
    project = conn.get_project()
    timeline = _require_timeline(conn)
    media_pool = conn.get_media_pool()

    if output_mode == "new":
        result = write_subtitle_track(timeline, media_pool, segments, body.get("track_name"))
    elif output_mode == "correct":
        track_index = body.get("track_index")
        if track_index is None:
            raise ValueError("track_index is required when output_mode='correct'")
        result = correct_subtitle_track(timeline, media_pool, int(track_index), segments)
    else:
        raise ValueError("output_mode must be 'new' or 'correct'")

    return {
        "project": project.GetName(),
        "timeline": timeline.GetName(),
        "output_mode": output_mode,
        **result,
    }


# ── HTTP plumbing ───────────────────────────────────────────────────

class PanelHandler(BaseHTTPRequestHandler):
    server_version = "ResolveMCPPanel/1.0"

    # -- helpers --

    def _allowed_origin(self) -> Optional[str]:
        """Echo only localhost / file:// origins — never arbitrary sites."""
        origin = self.headers.get("Origin")
        if origin is None:
            return None
        if origin == "null":  # file:// pages send Origin: null
            return "null"
        if origin.startswith(("http://127.0.0.1", "http://localhost")):
            return origin
        return None

    def _send_headers(self, status: int, content_type: str, length: int):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        allowed = self._allowed_origin()
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
        self.end_headers()

    def _send_json(self, data: Any, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_headers(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _send_error_json(self, e: Exception):
        status = 400 if isinstance(e, (ValueError, KeyError, NotADirectoryError)) else 500
        self._send_json({"error": str(e)}, status)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_static(self, path: str):
        panel_dir = _panel_dir().resolve()
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (panel_dir / rel).resolve()
        # Path traversal guard: stay inside the panel directory
        if not str(target).startswith(str(panel_dir) + os.sep) and target != panel_dir:
            self._send_json({"error": "Not found"}, 404)
            return
        if not target.is_file():
            self._send_json({"error": "Not found"}, 404)
            return
        content = target.read_bytes()
        mime = _MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send_headers(200, mime, len(content))
        self.wfile.write(content)

    # -- HTTP methods --

    def do_OPTIONS(self):
        self.send_response(204)
        allowed = self._allowed_origin()
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                self._send_json(_api_status())
            elif path == "/api/markers/pending":
                self._send_json(_api_markers_pending())
            elif path == "/api/markers/timeline":
                self._send_json(_api_markers_timeline())
            elif path == "/api/subtitle-tracks":
                self._send_json(_api_subtitle_tracks())
            elif path.startswith("/api/transcribe/"):
                self._send_json(_api_transcribe_status(path.rsplit("/", 1)[1]))
            elif path.startswith("/api/"):
                self._send_json({"error": "Not found"}, 404)
            else:
                self._serve_static(path)
        except Exception as e:
            logger.exception("GET %s failed", path)
            self._send_error_json(e)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_body()
            if path == "/api/markers/parse":
                self._send_json(_api_markers_parse(body))
            elif path == "/api/markers/load":
                self._send_json(_api_markers_load(body))
            elif path == "/api/markers/set":
                self._send_json(_api_markers_set(body))
            elif path == "/api/transcribe":
                self._send_json(_api_transcribe_start(body))
            elif path == "/api/media-pool/sync":
                self._send_json(_api_media_pool_sync(body))
            elif path == "/api/subtitles/write":
                self._send_json(_api_subtitles_write(body))
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            logger.exception("POST %s failed", path)
            self._send_error_json(e)

    def log_message(self, format, *args):  # route access log to our logger
        logger.debug("panel http: " + format, *args)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    port = int(os.getenv("RESOLVE_MCP_PANEL_PORT", str(DEFAULT_PORT)))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), PanelHandler)
    logger.info("Panel bridge running at http://127.0.0.1:%d (panel dir: %s)", port, _panel_dir())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Panel bridge stopped")


if __name__ == "__main__":
    main()
