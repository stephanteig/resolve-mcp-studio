"""
Local audio transcription using mlx-whisper (optimized for Apple M-series chips).

Long files are split into chunks with ffmpeg so each transcription call
completes well within any MCP timeout.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional, List, Dict, Any

logger = logging.getLogger("ResolveMCP")

# ── Models ──────────────────────────────────────────────────────────

WHISPER_MODELS = {
    "tiny": "mlx-community/whisper-tiny",
    "base": "mlx-community/whisper-base",
    "small": "mlx-community/whisper-small",
    "medium": "mlx-community/whisper-medium",
    "large": "mlx-community/whisper-large-v3",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}

DEFAULT_MODEL = "turbo"

# Each chunk is this many seconds — short enough to never time out
CHUNK_SECONDS = 300  # 5 minutes


def _get_model_repo(model: str) -> str:
    if "/" in model:
        return model
    repo = WHISPER_MODELS.get(model)
    if repo is None:
        raise ValueError(
            f"Unknown model '{model}'. Choose from: {', '.join(WHISPER_MODELS.keys())} "
            f"or pass a full HuggingFace repo path."
        )
    return repo


# ── ffmpeg helpers ──────────────────────────────────────────────────

def _get_duration(path: str) -> float:
    """Get duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path,
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def _extract_chunk(src: str, start: float, duration: float, dst: str):
    """Extract a chunk of audio with ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", src,
        "-vn",                # drop video
        "-acodec", "pcm_s16le",
        "-ar", "16000",       # whisper expects 16 kHz
        "-ac", "1",           # mono
        dst,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _split_audio(path: str, chunk_sec: int, tmp_dir: str) -> List[Dict[str, Any]]:
    """Split into ≤chunk_sec WAV files.  Returns list of {path, offset}."""
    total = _get_duration(path)
    chunks = []
    offset = 0.0
    idx = 0
    while offset < total:
        chunk_path = os.path.join(tmp_dir, f"chunk_{idx:04d}.wav")
        _extract_chunk(path, offset, chunk_sec, chunk_path)
        chunks.append({"path": chunk_path, "offset": offset})
        offset += chunk_sec
        idx += 1
    return chunks


# ── Core transcription ─────────────────────────────────────────────

def transcribe(
    audio_path: str,
    model: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    word_timestamps: bool = False,
    initial_prompt: Optional[str] = None,
    chunk_seconds: int = CHUNK_SECONDS,
) -> Dict[str, Any]:
    """
    Transcribe an audio/video file using mlx-whisper.

    Files longer than *chunk_seconds* are automatically split with ffmpeg
    so each chunk completes quickly.
    """
    try:
        import mlx_whisper
    except ImportError:
        raise ImportError(
            "mlx-whisper is not installed. Install with: "
            "uv pip install 'mlx-whisper>=0.4.3'"
        )

    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    repo = _get_model_repo(model)
    duration = _get_duration(audio_path)

    decode_options: Dict[str, Any] = {}
    if language:
        decode_options["language"] = language

    # Short file → transcribe directly
    if duration <= chunk_seconds:
        logger.info("Transcribing '%s' (%.0fs) with %s", audio_path, duration, repo)
        return mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=repo,
            word_timestamps=word_timestamps,
            initial_prompt=initial_prompt,
            verbose=False,
            **decode_options,
        )

    # Long file → chunk, transcribe each, stitch
    logger.info(
        "Splitting '%s' (%.0fs) into %d-second chunks",
        audio_path, duration, chunk_seconds,
    )
    tmp_dir = tempfile.mkdtemp(prefix="resolve_whisper_")
    try:
        chunks = _split_audio(audio_path, chunk_seconds, tmp_dir)
        logger.info("Created %d chunks", len(chunks))

        all_segments: List[Dict[str, Any]] = []
        all_text_parts: List[str] = []
        detected_language = None

        for i, chunk in enumerate(chunks):
            logger.info("Transcribing chunk %d/%d (offset %.0fs)...", i + 1, len(chunks), chunk["offset"])

            result = mlx_whisper.transcribe(
                chunk["path"],
                path_or_hf_repo=repo,
                word_timestamps=word_timestamps,
                initial_prompt=initial_prompt,
                verbose=False,
                **decode_options,
            )

            if detected_language is None:
                detected_language = result.get("language")

            offset = chunk["offset"]
            for seg in result.get("segments", []):
                all_segments.append({
                    "start": seg["start"] + offset,
                    "end": seg["end"] + offset,
                    "text": seg["text"],
                })

            text = result.get("text", "")
            if text:
                all_text_parts.append(text.strip())

            # Use the tail of the last chunk's text as prompt for the next
            # to maintain context continuity across chunk boundaries
            if text:
                initial_prompt = text.strip()[-200:]

        return {
            "language": detected_language or "unknown",
            "text": " ".join(all_text_parts),
            "segments": all_segments,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── SRT helpers ────────────────────────────────────────────────────

def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _seconds_to_srt_time(seg["start"])
        end = _seconds_to_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Spec-level wrapper ──────────────────────────────────────────────

def transcribe_audio(
    audio_path: str,
    language: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    word_timestamps: bool = False,
) -> Dict[str, Any]:
    """Transcribe an audio file and return normalized segments.

    Thin wrapper around transcribe() that guarantees a uniform shape:
    {"language": str, "text": str, "segments": [{"start", "end", "text", "words"?}]}
    """
    result = transcribe(
        audio_path,
        model=model,
        language=language,
        word_timestamps=word_timestamps,
    )
    segments = []
    for seg in result.get("segments", []):
        norm = {
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg["text"].strip(),
        }
        if word_timestamps and seg.get("words"):
            norm["words"] = [
                {"start": float(w["start"]), "end": float(w["end"]), "text": w["word"]}
                for w in seg["words"]
            ]
        segments.append(norm)
    return {
        "language": result.get("language", "unknown"),
        "text": result.get("text", "").strip(),
        "segments": segments,
    }


# ── Resolve subtitle track helpers ──────────────────────────────────
#
# The Resolve scripting API has no call that creates subtitle items
# directly, and no setter for the text of an existing subtitle item.
# The established workaround (same approach as Auto-Subs) is:
#   write an SRT file → MediaPool.ImportMedia() → MediaPool.AppendToTimeline()
# which places the subtitles on a subtitle track in the current timeline.
# Correction therefore writes a NEW track with the original timing and
# corrected text, and disables (never deletes) the original track.

def _timeline_fps(timeline) -> float:
    """Read the frame rate from a timeline, raising if unavailable."""
    fps_setting = timeline.GetSetting("timelineFrameRate")
    if not fps_setting:
        raise RuntimeError("Could not read frame rate from timeline")
    return float(fps_setting)


def get_subtitle_tracks(timeline) -> List[Dict[str, Any]]:
    """List the subtitle tracks on a timeline (1-based indices)."""
    count = timeline.GetTrackCount("subtitle") or 0
    tracks = []
    for index in range(1, count + 1):
        items = timeline.GetItemListInTrack("subtitle", index) or []
        track: Dict[str, Any] = {
            "index": index,
            "name": timeline.GetTrackName("subtitle", index) or f"Subtitle {index}",
            "item_count": len(items),
        }
        try:
            track["enabled"] = timeline.GetIsTrackEnabled("subtitle", index)
        except Exception:
            pass  # not available on older Resolve versions
        tracks.append(track)
    return tracks


def get_subtitle_track_segments(timeline, track_index: int) -> List[Dict[str, Any]]:
    """Read the subtitle items on a track as {start, end, text} in seconds.

    start/end are relative to the timeline start (matching SRT and
    transcription timestamps). The text comes from TimelineItem.GetName(),
    which holds the subtitle text for subtitle items.
    """
    items = timeline.GetItemListInTrack("subtitle", track_index)
    if not items:
        raise RuntimeError(f"No subtitle items found on subtitle track {track_index}")

    fps = _timeline_fps(timeline)
    start_frame = timeline.GetStartFrame() or 0

    segments = []
    for item in items:
        segments.append({
            "start": (item.GetStart() - start_frame) / fps,
            "end": (item.GetEnd() - start_frame) / fps,
            "text": (item.GetName() or "").strip(),
        })
    return segments


def _subtitle_track_item_counts(timeline) -> Dict[int, int]:
    """Snapshot {track_index: item_count} for all subtitle tracks."""
    counts = {}
    for index in range(1, (timeline.GetTrackCount("subtitle") or 0) + 1):
        counts[index] = len(timeline.GetItemListInTrack("subtitle", index) or [])
    return counts


def write_subtitle_track(
    timeline,
    media_pool,
    segments: List[Dict[str, Any]],
    track_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Write segments as a new subtitle track on the timeline.

    Generates an SRT file, imports it into the media pool and appends it to
    the timeline. Placement is VERIFIED: on Resolve versions where
    AppendToTimeline silently fails for subtitle clips (returns [None],
    e.g. Resolve 21 beta — InsertSubtitleIntoTimeline/ImportIntoTimeline/
    SetName were all probed and don't work either), the result has
    "placed": False with the SRT path and instructions for manual import.

    Returns {"placed", "track_index", "track_name", "segments_written",
    "srt_path"} (+ "instructions" when placed is False). The SRT file must
    stay on disk — the media pool clip references it.
    """
    if not segments:
        raise ValueError("No segments to write")

    srt_content = segments_to_srt(segments)
    tmp_dir = tempfile.mkdtemp(prefix="resolve_srt_")
    safe_name = "".join(
        c if c.isalnum() or c in "-_ " else "_" for c in (track_name or "subtitles")
    ).strip() or "subtitles"
    srt_path = os.path.join(tmp_dir, f"{safe_name}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    before = _subtitle_track_item_counts(timeline)

    # Add a fresh track so the import doesn't merge into an existing one.
    # AddTrack may not exist on older Resolve versions — then the import
    # decides the target track itself.
    try:
        timeline.AddTrack("subtitle")
    except Exception as e:
        logger.debug("AddTrack('subtitle') failed: %s", e)

    imported = media_pool.ImportMedia([srt_path])
    if not imported:
        raise RuntimeError(f"Failed to import SRT into media pool: {srt_path}")

    media_pool.AppendToTimeline(imported)  # return value is unreliable — verify below

    # Verify by item counts which subtitle track actually received the items
    after = _subtitle_track_item_counts(timeline)
    target_index = None
    for index, count in after.items():
        if count > before.get(index, 0):
            target_index = index
            break

    if target_index is not None:
        if track_name:
            timeline.SetTrackName("subtitle", target_index, track_name)
        return {
            "placed": True,
            "track_index": target_index,
            "track_name": track_name,
            "segments_written": len(segments),
            "srt_path": srt_path,
        }

    # Nothing landed — remove the empty track we just added (if we did and
    # it's still empty) and fall back to manual import.
    added_index = max(after) if len(after) > len(before) else None
    if added_index is not None and after.get(added_index, 0) == 0:
        try:
            timeline.DeleteTrack("subtitle", added_index)
        except Exception as e:
            logger.debug("DeleteTrack('subtitle', %s) failed: %s", added_index, e)

    return {
        "placed": False,
        "track_index": None,
        "track_name": track_name,
        "segments_written": len(segments),
        "srt_path": srt_path,
        "instructions": (
            "Resolve's scripting API could not place the subtitles on the "
            f"timeline (AppendToTimeline is unreliable for SRT on this "
            f"Resolve version). The SRT file is ready at: {srt_path} — "
            "import it manually: open the Edit page, then either "
            "File → Import → Subtitle… and pick the file, or right-click "
            f"the imported clip '{safe_name}' in the Media Pool and choose "
            "'Insert Selected Subtitles to Timeline Using Timecode'."
        ),
    }


def correct_subtitle_track(
    timeline,
    media_pool,
    track_index: int,
    corrected_segments: List[Any],
) -> Dict[str, Any]:
    """Replace the TEXT of a subtitle track without touching its timing.

    corrected_segments must have exactly one entry per subtitle item on the
    track, in order — either plain strings or dicts with a "text" key. Any
    timing fields in the input are deliberately ignored; start/end always
    come from the existing items.

    Because the Resolve API cannot edit subtitle text in place, this writes
    a new track ("<name> (corrected)") with the original timing and disables
    the original track. Nothing is deleted.
    """
    existing = get_subtitle_track_segments(timeline, track_index)
    if len(corrected_segments) != len(existing):
        raise ValueError(
            f"Segment count mismatch: track {track_index} has {len(existing)} "
            f"subtitle items but {len(corrected_segments)} corrections were given"
        )

    segments = []
    for original, correction in zip(existing, corrected_segments):
        text = correction.get("text") if isinstance(correction, dict) else str(correction)
        if not text or not text.strip():
            text = original["text"]  # empty correction → keep original text
        segments.append({
            "start": original["start"],  # timing always from the existing item
            "end": original["end"],
            "text": text.strip(),
        })

    original_name = timeline.GetTrackName("subtitle", track_index) or f"Subtitle {track_index}"
    result = write_subtitle_track(
        timeline, media_pool, segments, f"{original_name} (corrected)"
    )

    # Only disable the original once the corrected track is actually on the
    # timeline — on the manual-import fallback the user does this themselves.
    if result.get("placed"):
        try:
            timeline.SetTrackEnable("subtitle", track_index, False)
            result["original_track_disabled"] = track_index
        except Exception as e:
            logger.debug("SetTrackEnable failed: %s", e)
            result["original_track_disabled"] = None
    else:
        result["original_track_disabled"] = None
        result["instructions"] += (
            f" After importing, disable the original subtitle track "
            f"{track_index} ('{original_name}') manually — it was left "
            "enabled since the corrected track isn't on the timeline yet."
        )

    return result


# ── Correction mapping ──────────────────────────────────────────────

def map_transcription_to_segments(
    existing_segments: List[Dict[str, Any]],
    transcription: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Map a fresh transcription onto existing subtitle timing windows.

    For each existing segment window, collect the transcribed words (or
    whole segments, when word timestamps are unavailable) whose midpoint
    falls inside the window; out-of-window units are assigned to the
    nearest window so no text is lost. Returns segments with the ORIGINAL
    timing, the proposed corrected text and the original text for review.
    """
    if not existing_segments:
        raise ValueError("No existing segments to map onto")

    # Prefer word-level units; fall back to whole whisper segments
    units: List[Dict[str, Any]] = []
    for seg in transcription.get("segments", []):
        if seg.get("words"):
            units.extend(seg["words"])
        else:
            units.append(seg)

    def nearest_window(midpoint: float) -> int:
        for i, win in enumerate(existing_segments):
            if win["start"] <= midpoint < win["end"]:
                return i
        # Outside all windows → closest by boundary distance
        return min(
            range(len(existing_segments)),
            key=lambda i: min(
                abs(midpoint - existing_segments[i]["start"]),
                abs(midpoint - existing_segments[i]["end"]),
            ),
        )

    buckets: List[List[str]] = [[] for _ in existing_segments]
    for unit in units:
        midpoint = (unit["start"] + unit["end"]) / 2
        buckets[nearest_window(midpoint)].append(unit["text"].strip())

    result = []
    for window, words in zip(existing_segments, buckets):
        corrected = " ".join(w for w in words if w).strip()
        result.append({
            "start": window["start"],
            "end": window["end"],
            "text": corrected or window["text"],  # no speech mapped → keep original
            "original_text": window["text"],
        })
    return result
