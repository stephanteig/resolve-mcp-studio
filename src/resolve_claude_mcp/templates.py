"""
Project templates — create Resolve projects with a predefined structure
(resolution, fps, timelines, bins) from JSON configs in templates/configs/.

A config may optionally reference an exported Resolve project file with a
"drp" key (filename in templates/drp/). When the referenced file exists,
create_project_from_template imports it (renamed) instead of building the
project from the config fields.

The templates directory is resolved relative to the repo root (no hardcoded
paths) and can be overridden with the RESOLVE_MCP_TEMPLATES_DIR env var.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ResolveMCP")

TEMPLATES_ENV_VAR = "RESOLVE_MCP_TEMPLATES_DIR"


def _templates_root() -> Path:
    """Locate the templates/ directory (env override → repo root)."""
    override = os.getenv(TEMPLATES_ENV_VAR)
    if override:
        return Path(override)
    # src/resolve_claude_mcp/templates.py → repo root is two levels above src/
    return Path(__file__).resolve().parents[2] / "templates"


def _configs_dir() -> Path:
    return _templates_root() / "configs"


def _drp_dir() -> Path:
    return _templates_root() / "drp"


def list_templates() -> List[Dict[str, Any]]:
    """List available template configs from templates/configs/.

    Returns one entry per JSON config: its id (filename stem, used as
    template_name), display name, key settings and whether a referenced
    .drp file is present. Invalid JSON files are reported, not skipped
    silently.
    """
    configs_dir = _configs_dir()
    if not configs_dir.is_dir():
        raise FileNotFoundError(f"Templates config directory not found: {configs_dir}")

    templates = []
    for path in sorted(configs_dir.glob("*.json")):
        entry: Dict[str, Any] = {"id": path.stem}
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            entry["error"] = f"Invalid template config: {e}"
            templates.append(entry)
            continue

        entry["name"] = config.get("name", path.stem)
        for key in ("resolution", "fps", "audio_channels"):
            if key in config:
                entry[key] = config[key]
        entry["timelines"] = [tl.get("name") for tl in config.get("timelines", [])]
        entry["bins"] = config.get("bins", [])

        drp_name = config.get("drp")
        entry["has_drp"] = bool(drp_name) and (_drp_dir() / drp_name).is_file()
        templates.append(entry)
    return templates


def load_template(template_name: str) -> Dict[str, Any]:
    """Load a template config by id (filename stem) or display name."""
    configs_dir = _configs_dir()
    direct = configs_dir / f"{template_name}.json"
    if direct.is_file():
        return json.loads(direct.read_text(encoding="utf-8"))

    # Fall back to matching the "name" field of each config
    for path in sorted(configs_dir.glob("*.json")):
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if config.get("name") == template_name:
            return config

    available = [p.stem for p in sorted(configs_dir.glob("*.json"))]
    raise ValueError(
        f"Template '{template_name}' not found. Available: {', '.join(available) or '(none)'}"
    )


def _parse_resolution(resolution: str) -> Tuple[int, int]:
    """Parse "3840x2160" into (width, height)."""
    try:
        width_str, height_str = resolution.lower().split("x")
        return int(width_str), int(height_str)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid resolution in template (expected 'WIDTHxHEIGHT'): {resolution!r}")


def _timeline_resolution(timeline_type: str, width: int, height: int) -> Tuple[int, int]:
    """Resolve a timeline's resolution from its aspect type ("16:9", "9:16").

    Portrait types (ratio < 1) get the project resolution rotated; landscape
    types use it as-is.
    """
    try:
        a, b = (int(part) for part in timeline_type.split(":"))
        portrait = a < b
    except (ValueError, AttributeError):
        logger.warning("Unknown timeline type %r — using project resolution", timeline_type)
        portrait = False

    landscape_w, landscape_h = max(width, height), min(width, height)
    if portrait:
        return landscape_h, landscape_w
    return landscape_w, landscape_h


def create_project_from_template(
    project_manager,
    template_name: str,
    project_name: str,
) -> Dict[str, Any]:
    """Create a new Resolve project from a template config.

    If the config references an existing .drp file, the project is imported
    from it (renamed to project_name). Otherwise the project is built from
    the config: resolution + fps settings, bins, and timelines (9:16
    timelines get custom rotated resolution). Timelines are created inside
    the first bin whose name contains "TIMELINE", if any — otherwise in the
    Media Pool root.

    Returns a report dict; "warnings" lists anything that could not be
    applied rather than failing the whole operation.
    """
    config = load_template(template_name)
    report: Dict[str, Any] = {
        "template": config.get("name", template_name),
        "project": project_name,
        "warnings": [],
    }

    # Fail fast on a name collision instead of letting Resolve mangle it
    existing = project_manager.GetProjectListInCurrentFolder() or []
    if project_name in existing:
        raise RuntimeError(f"A project named '{project_name}' already exists")

    # ── Path 1: import a referenced .drp ──
    drp_name = config.get("drp")
    if drp_name:
        drp_path = _drp_dir() / drp_name
        if drp_path.is_file():
            if not project_manager.ImportProject(str(drp_path), project_name):
                raise RuntimeError(f"ImportProject failed for {drp_path}")
            project = project_manager.LoadProject(project_name)
            if project is None:
                raise RuntimeError(f"Imported '{project_name}' but could not open it")
            report["created_from"] = str(drp_path)
            return report
        report["warnings"].append(
            f"Config references drp '{drp_name}' but {drp_path} does not exist — "
            "building project from config instead"
        )

    # ── Path 2: build from config ──
    project = project_manager.CreateProject(project_name)
    if not project:
        raise RuntimeError(f"CreateProject('{project_name}') failed")
    report["created_from"] = "config"

    width, height = _parse_resolution(config.get("resolution", "1920x1080"))
    fps = config.get("fps", 25)
    for key, value in (
        ("timelineResolutionWidth", str(width)),
        ("timelineResolutionHeight", str(height)),
        ("timelineFrameRate", str(fps)),
    ):
        if not project.SetSetting(key, value):
            report["warnings"].append(f"Could not set project setting {key}={value}")

    # The scripting API exposes no project setting for timeline audio
    # channels — record it so the caller knows it wasn't applied.
    if "audio_channels" in config:
        report["warnings"].append(
            f"audio_channels={config['audio_channels']} is not settable via the "
            "scripting API — configure audio channels manually if needed"
        )

    media_pool = project.GetMediaPool()
    root = media_pool.GetRootFolder()

    # Bins
    bins_created = []
    bin_folders: Dict[str, Any] = {}
    for bin_name in config.get("bins", []):
        folder = media_pool.AddSubFolder(root, bin_name)
        if folder:
            bins_created.append(bin_name)
            bin_folders[bin_name] = folder
        else:
            report["warnings"].append(f"Could not create bin '{bin_name}'")
    report["bins_created"] = bins_created

    # Timelines go into the first bin named like a timeline bin, if present
    timeline_bin = next(
        (f for name, f in bin_folders.items() if "TIMELINE" in name.upper()), None
    )
    if timeline_bin is not None:
        if not media_pool.SetCurrentFolder(timeline_bin):
            report["warnings"].append("Could not enter timeline bin — timelines go to root")

    timelines_created = []
    first_timeline = None
    for tl_config in config.get("timelines", []):
        tl_name = tl_config.get("name")
        if not tl_name:
            report["warnings"].append(f"Timeline config without name skipped: {tl_config}")
            continue

        timeline = media_pool.CreateEmptyTimeline(tl_name)
        if not timeline:
            report["warnings"].append(f"Could not create timeline '{tl_name}'")
            continue
        if first_timeline is None:
            first_timeline = timeline

        tl_width, tl_height = _timeline_resolution(tl_config.get("type", "16:9"), width, height)
        if (tl_width, tl_height) != (width, height):
            # Diverging resolution requires per-timeline custom settings
            ok = timeline.SetSetting("useCustomSettings", "1") \
                and timeline.SetSetting("timelineResolutionWidth", str(tl_width)) \
                and timeline.SetSetting("timelineResolutionHeight", str(tl_height))
            if not ok:
                report["warnings"].append(
                    f"Could not apply custom resolution {tl_width}x{tl_height} "
                    f"to timeline '{tl_name}'"
                )
        timelines_created.append({"name": tl_name, "resolution": f"{tl_width}x{tl_height}"})
    report["timelines_created"] = timelines_created

    # CreateEmptyTimeline leaves the LAST timeline active — switch back to
    # the first one for a predictable starting state
    if first_timeline is not None:
        if not project.SetCurrentTimeline(first_timeline):
            report["warnings"].append("Could not set the first timeline as current")

    return report
