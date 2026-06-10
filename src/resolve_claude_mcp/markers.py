"""
Marker parsing — converts free-text timecode lists into structured marker
data ready for Timeline.AddMarker().

Supported line formats (description follows the timecode):
    MM:SS text          e.g. "02:15 fjern pause"
    HH:MM:SS text       e.g. "01:02:15 klipp her"
    HH:MM:SS:FF text    e.g. "01:02:15:12 pling inn"

Three-component timecodes are ALWAYS interpreted as HH:MM:SS — frame-accurate
positions must be given explicitly with four components (HH:MM:SS:FF).

Lines may optionally start with a list bullet ("-", "*", "•") and the
timecode may be separated from the description by "-", "–", "—" or just
whitespace.
"""

import re
from typing import Dict, List, Tuple

# Marker colors accepted by Timeline.AddMarker()
VALID_MARKER_COLORS = {
    "Red", "Orange", "Yellow", "Green", "Cyan", "Blue",
    "Purple", "Pink", "Fuchsia", "Rose", "Lavender", "Sky",
    "Mint", "Lemon", "Sand", "Cocoa", "Cream",
}

DEFAULT_COLOR = "Blue"

# Keyword → color mapping. Order matters: the first matching category wins,
# so "jingle" maps to Cyan (spec lists it under both Cyan and Green —
# Cyan is checked first; Green still covers "intro"/"outro").
_COLOR_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("Red", ("feil", "fjern", "problem")),
    ("Orange", ("klipp", "cut", "edit")),
    ("Yellow", ("lyd", "musikk", "audio")),
    ("Cyan", ("pling", "jingle", "stikk")),
    ("Green", ("intro", "outro")),
]

# Optional bullet, 2–4 colon-separated timecode components, optional
# dash/colon separator, then the description (must contain non-whitespace).
_LINE_RE = re.compile(
    r"^\s*(?:[-*•]\s*)?"            # optional list bullet
    r"(\d{1,2}(?::\d{1,2}){1,3})"   # timecode: 2–4 components
    r"\s*(?:[-–—:]\s*)?\s*"         # optional separator
    r"(\S.*?)\s*$"                  # description
)


def pick_color(text: str) -> str:
    """Pick a marker color based on keywords in the description.

    Substring matching is intentional so e.g. "stikkord" matches "stikk".
    """
    lowered = text.lower()
    for color, keywords in _COLOR_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return color
    return DEFAULT_COLOR


def timecode_to_frame(timecode: str, fps: float) -> int:
    """Convert a timecode string to an absolute frame number (from frame 0).

    Accepts MM:SS, HH:MM:SS and HH:MM:SS:FF. Raises ValueError on
    out-of-range components (seconds/minutes >= 60, frames >= fps).
    """
    parts = [int(p) for p in timecode.split(":")]
    frames_extra = 0

    if len(parts) == 2:
        hours, (minutes, seconds) = 0, parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 4:
        hours, minutes, seconds, frames_extra = parts
    else:
        raise ValueError(f"Invalid timecode: {timecode!r}")

    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid timecode (minutes/seconds must be < 60): {timecode!r}")
    if frames_extra >= round(fps):
        raise ValueError(f"Invalid timecode (frame component must be < fps={fps}): {timecode!r}")

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return round(total_seconds * fps) + frames_extra


def frame_to_timecode(frame: int, fps: float) -> str:
    """Convert a frame number to an HH:MM:SS:FF timecode string.

    Uses non-drop-frame math (exact for integer rates like 24/25/30/50/60).
    """
    fps_int = round(fps)
    ff = frame % fps_int
    total_seconds = frame // fps_int
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = total_seconds // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def parse_marker_list(text: str, fps: float) -> Tuple[List[Dict], List[str]]:
    """Parse free text with timecodes + descriptions into structured markers.

    Returns (markers, skipped_lines):
      markers: list of {"frame", "timecode", "name", "color", "note"} sorted
               by frame, ready for Timeline.AddMarker()
      skipped_lines: non-empty lines that could not be parsed, so the caller
               can surface them for review instead of silently dropping them
    """
    markers: List[Dict] = []
    skipped: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _LINE_RE.match(line)
        if not match:
            skipped.append(line)
            continue

        timecode_str, description = match.groups()
        try:
            frame = timecode_to_frame(timecode_str, fps)
        except ValueError:
            skipped.append(line)
            continue

        markers.append({
            "frame": frame,
            "timecode": frame_to_timecode(frame, fps),
            "name": description,
            "color": pick_color(description),
            "note": "",
        })

    markers.sort(key=lambda m: m["frame"])
    return markers, skipped
