"""
Auto clip color — categorize clips from filename and clip properties and
propose/set Resolve clip colors.

Categories and colors follow BUGFIX.md, with two substitutions because
"Red" and "Cream" are not valid CLIP colors (verified live with
SetClipColor — the clip color palette differs from the marker palette):
music/audio gets Pink instead of Red, uncategorized gets Beige instead
of Cream.

Camera-movement detection ("static camera" vs "handheld") is not possible
through the scripting API — categorization relies on filenames and clip
metadata (Type, alpha, camera fields).
"""

import os
import re
from typing import Any, Dict, Optional, Tuple

# Colors accepted by MediaPoolItem.SetClipColor() (probed live; differs
# from the marker color palette — no Red/Cream/Cyan etc.)
VALID_CLIP_COLORS = {
    "Orange", "Apricot", "Yellow", "Lime", "Olive", "Green", "Teal", "Navy",
    "Blue", "Purple", "Violet", "Pink", "Tan", "Beige", "Brown", "Chocolate",
}

# category → (color, human-readable label)
CATEGORY_COLORS = {
    "drone": ("Yellow", "Drone / luftfoto"),
    "talking_head": ("Blue", "Talking head / intervju"),
    "broll": ("Green", "B-roll / håndholdt"),
    "music_audio": ("Pink", "Musikk / lyd"),          # BUGFIX.md: Red — not a valid clip color
    "graphics_stills": ("Purple", "Grafikk / stillbilder"),
    "uncategorized": ("Beige", "Ukategorisert"),       # BUGFIX.md: Cream — not a valid clip color
}

AUDIO_EXTENSIONS = {"mp3", "wav", "aif", "aiff", "m4a", "flac", "caf", "ogg"}
STILL_EXTENSIONS = {
    "png", "jpg", "jpeg", "psd", "tif", "tiff", "exr", "dpx",
    "heic", "gif", "webp", "bmp", "svg",
}

DRONE_KEYWORDS = ("dji", "drone", "mavic", "avata", "fpv", "aerial", "luftfoto")
INTERVIEW_KEYWORDS = ("intervju", "interview", "talkinghead")
BROLL_KEYWORDS = ("gopro", "broll", "håndholdt", "handheld", "hero")

# Clip property fields that may carry camera/keyword metadata
_METADATA_KEYS = (
    "Camera #", "Camera Type", "Camera Manufacturer", "Camera Notes",
    "Keywords", "Comments", "Description", "Shot", "Scene",
)


def _tokens(name: str) -> set:
    """Lowercase alphanumeric tokens of a filename ('INT-04_DJI' → int, 04, dji)."""
    return set(re.split(r"[^a-z0-9]+", name.lower())) - {""}


def categorize_clip(name: str, properties: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Categorize a clip from its name and clip properties.

    Returns (category, reason). Checks run from most to least certain:
    file type (audio/stills) → drone → interview → b-roll → uncategorized.
    """
    properties = properties or {}
    lowered = name.lower()
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    tokens = _tokens(name)
    clip_type = (properties.get("Type") or "").lower()
    metadata = " ".join(
        str(properties[k]) for k in _METADATA_KEYS if properties.get(k)
    ).lower()

    # Audio — extension or media pool type is definitive
    if ext in AUDIO_EXTENSIONS or clip_type == "audio":
        return "music_audio", f"audio ({'.' + ext if ext in AUDIO_EXTENSIONS else 'Type=Audio'})"

    # Graphics / stills — extension, still type, or alpha channel
    if ext in STILL_EXTENSIONS or clip_type == "still":
        return "graphics_stills", f"still image ({'.' + ext if ext in STILL_EXTENSIONS else 'Type=Still'})"
    alpha = str(properties.get("Alpha mode") or properties.get("Alpha Mode") or "")
    if alpha and alpha.lower() not in ("", "none"):
        return "graphics_stills", f"alpha channel ({alpha})"

    # Drone — name keywords or camera metadata
    for kw in DRONE_KEYWORDS:
        if kw in lowered or kw in metadata:
            where = "name" if kw in lowered else "metadata"
            return "drone", f"'{kw}' in {where}"

    # Talking head / interview — keywords, or the token "int"/"th"
    # (token match so 'paINTing.mp4' doesn't trigger)
    for kw in INTERVIEW_KEYWORDS:
        if kw in lowered or kw in metadata:
            where = "name" if kw in lowered else "metadata"
            return "talking_head", f"'{kw}' in {where}"
    if "int" in tokens or "th" in tokens:
        return "talking_head", "'INT'/'TH' token in name"

    # B-roll / handheld
    for kw in BROLL_KEYWORDS:
        if kw in lowered or kw in metadata:
            where = "name" if kw in lowered else "metadata"
            return "broll", f"'{kw}' in {where}"

    return "uncategorized", "no category matched"


def propose_color(name: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a color proposal for one clip: category, color, label, reason."""
    category, reason = categorize_clip(name, properties)
    color, label = CATEGORY_COLORS[category]
    return {
        "clip": name,
        "category": category,
        "category_label": label,
        "proposed_color": color,
        "reason": reason,
    }
