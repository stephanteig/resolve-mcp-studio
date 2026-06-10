"""
Media Pool ↔ Finder sync — mirror a folder structure from disk as bins in
the Resolve Media Pool and import each folder's media files into its bin.

The Resolve scripting API has no "live linked bin" concept (Smart Bins are
not scriptable), so "linking" a bin to a folder means importing the media
files that live directly in that folder. The sync is idempotent: existing
bins are reused by name and files already in a bin (matched on file path)
are skipped, so re-running the sync picks up new files without duplicates.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ResolveMCP")

# File extensions treated as importable media (lowercase, no dot)
MEDIA_EXTENSIONS = {
    # video
    "mov", "mp4", "m4v", "mxf", "avi", "mkv", "mts", "m2ts", "webm",
    "braw", "r3d", "ari", "dng",
    # audio
    "wav", "aif", "aiff", "mp3", "m4a", "flac", "caf", "ogg",
    # stills / sequences
    "jpg", "jpeg", "png", "tif", "tiff", "exr", "dpx", "psd", "heic",
    "gif", "cr2", "cr3", "arw", "nef", "raf",
}

# Folder structures deeper than this are almost certainly a mistake
MAX_DEPTH = 10


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def _is_media_file(name: str) -> bool:
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    return ext in MEDIA_EXTENSIONS


def read_finder_structure(root_path: str, max_depth: int = MAX_DEPTH) -> Dict[str, Any]:
    """Read a folder tree from disk into a nested structure.

    Returns {"name", "path", "media_files": [abs paths], "subfolders": [...]}.
    Hidden entries (dotfiles) are skipped; non-media files are counted but
    not listed. Raises on a missing or non-directory root.
    """
    root_path = os.path.abspath(os.path.expanduser(root_path))
    if not os.path.isdir(root_path):
        raise NotADirectoryError(f"Not a directory: {root_path}")
    return _read_folder(root_path, max_depth, depth=0)


def _read_folder(path: str, max_depth: int, depth: int) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "name": os.path.basename(path) or path,
        "path": path,
        "media_files": [],
        "other_file_count": 0,
        "subfolders": [],
    }

    try:
        entries = sorted(os.listdir(path))
    except OSError as e:
        result["error"] = f"Could not read folder: {e}"
        return result

    for entry in entries:
        if _is_hidden(entry):
            continue
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            if depth >= max_depth:
                result.setdefault("skipped_subfolders", []).append(entry)
                continue
            result["subfolders"].append(_read_folder(full, max_depth, depth + 1))
        elif _is_media_file(entry):
            result["media_files"].append(full)
        else:
            result["other_file_count"] += 1

    return result


def _find_subfolder(media_pool, parent, name: str):
    """Find an existing direct subfolder of *parent* by name."""
    for sub in parent.GetSubFolderList() or []:
        if sub.GetName() == name:
            return sub
    return None


def create_bins_from_structure(structure: Dict[str, Any], media_pool, parent=None) -> Dict[str, Any]:
    """Mirror a read_finder_structure() tree as bins in the Media Pool.

    Existing bins are reused by name (idempotent re-runs); only missing
    bins are created. Returns the structure annotated per node with
    "bin" (the MediaPool folder object), "bin_created" (bool) and
    "bin_error" when creation failed.
    """
    if parent is None:
        parent = media_pool.GetRootFolder()

    name = structure["name"]
    existing = _find_subfolder(media_pool, parent, name)
    if existing is not None:
        structure["bin"] = existing
        structure["bin_created"] = False
    else:
        folder = media_pool.AddSubFolder(parent, name)
        if not folder:
            structure["bin"] = None
            structure["bin_created"] = False
            structure["bin_error"] = f"AddSubFolder failed for '{name}'"
            return structure  # no parent bin → can't create children either
        structure["bin"] = folder
        structure["bin_created"] = True

    for sub in structure["subfolders"]:
        create_bins_from_structure(sub, media_pool, parent=structure["bin"])

    return structure


def _existing_clip_paths(bin_folder) -> set:
    """File paths of the clips already in a bin (for duplicate skipping)."""
    paths = set()
    for clip in bin_folder.GetClipList() or []:
        try:
            path = clip.GetClipProperty("File Path")
            if path:
                paths.add(os.path.abspath(path))
        except Exception as e:
            logger.debug("GetClipProperty('File Path') failed: %s", e)
    return paths


def link_bin_to_folder(media_pool, bin_folder, folder_path: str) -> Dict[str, Any]:
    """Import the media files directly inside *folder_path* into *bin_folder*.

    Files whose path already exists as a clip in the bin are skipped, so
    repeated calls only import what's new. Subfolders are NOT descended
    into — they are handled by their own bins. Returns
    {"imported", "skipped_existing", "failed"}.
    """
    folder_path = os.path.abspath(os.path.expanduser(folder_path))
    media_files = [
        os.path.join(folder_path, entry)
        for entry in sorted(os.listdir(folder_path))
        if not _is_hidden(entry)
        and os.path.isfile(os.path.join(folder_path, entry))
        and _is_media_file(entry)
    ]

    existing = _existing_clip_paths(bin_folder)
    to_import = [f for f in media_files if os.path.abspath(f) not in existing]
    skipped = len(media_files) - len(to_import)

    if not to_import:
        return {"imported": 0, "skipped_existing": skipped, "failed": 0}

    if not media_pool.SetCurrentFolder(bin_folder):
        raise RuntimeError(f"Could not set current folder to bin '{bin_folder.GetName()}'")

    imported_items = media_pool.ImportMedia(to_import) or []
    imported = len(imported_items)
    return {
        "imported": imported,
        "skipped_existing": skipped,
        "failed": len(to_import) - imported,
    }


def sync_structure_to_media_pool(media_pool, structure: Dict[str, Any]) -> Dict[str, Any]:
    """Create bins for a structure and import each folder's media.

    Orchestrates create_bins_from_structure + link_bin_to_folder over the
    whole tree. Returns a JSON-serializable report mirroring the folder
    tree, plus totals.
    """
    create_bins_from_structure(structure, media_pool)

    totals = {"bins_created": 0, "bins_reused": 0, "imported": 0,
              "skipped_existing": 0, "failed": 0, "errors": []}

    def _sync_node(node: Dict[str, Any]) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "bin": node["name"],
            "path": node["path"],
        }
        if node.get("bin") is None:
            report["error"] = node.get("bin_error", "bin missing")
            totals["errors"].append(f"{node['path']}: {report['error']}")
            return report

        totals["bins_created" if node["bin_created"] else "bins_reused"] += 1
        report["bin_created"] = node["bin_created"]

        if node["media_files"]:
            try:
                link = link_bin_to_folder(media_pool, node["bin"], node["path"])
                report.update(link)
                for key in ("imported", "skipped_existing", "failed"):
                    totals[key] += link[key]
            except Exception as e:
                report["error"] = str(e)
                totals["errors"].append(f"{node['path']}: {e}")

        if node["subfolders"]:
            report["subfolders"] = [_sync_node(sub) for sub in node["subfolders"]]
        if node.get("skipped_subfolders"):
            report["skipped_subfolders"] = node["skipped_subfolders"]
            totals["errors"].append(
                f"{node['path']}: subfolders beyond max depth skipped: "
                f"{', '.join(node['skipped_subfolders'])}"
            )
        return report

    tree_report = _sync_node(structure)
    return {"totals": totals, "structure": tree_report}
