# Implementation Plan — Nye MCP Tools
> Basert på `resolve-mcp-full-function-list.md` og Resolve 21 Scripting API.
> Oppdateres ved hver PR.

---

## Status

| PR | Branch | Status | Tools | Totalt |
|---|---|---|---|---|
| PR 1 | `feature/tools-high-priority` | ✅ Ferdig — [PR #16](https://github.com/stephanteig/resolve-mcp-studio/pull/16) | 43 nye | 105 |
| PR 2 | `feature/tools-medium-priority` | 🔲 Ikke startet | ~71 nye | ~176 |
| PR 3 | `feature/tools-low-priority` | 🔲 Ikke startet | ~15 nye | ~191 |

**Eksisterende tools ved start:** 62  
**Etter PR 1:** 105  
**Mål:** ~191

---

## ✅ PR 1 — HØY prioritet + Photo Page (ferdig)

**Branch:** `feature/tools-high-priority`  
**PR:** [#16](https://github.com/stephanteig/resolve-mcp-studio/pull/16)  
**Commit:** `ad0f6b1`

### Nye interne helpers
- `_find_clip_in_media_pool(conn, clip_name)` — rekursivt søk etter klipp i Media Pool
- `_find_folder_in_media_pool(conn, folder_name)` — rekursivt søk etter bin
- `_get_gallery_album(conn, album_name)` — søk etter Gallery-album etter navn

### Prosjektstyring (5)
| Tool | API | Status |
|---|---|---|
| `save_project` | `ProjectManager.SaveProject()` | ✅ |
| `list_projects` | `ProjectManager.GetProjectListInCurrentFolder()` | ✅ |
| `load_project` | `ProjectManager.LoadProject(name)` | ✅ |
| `export_project` | `ProjectManager.ExportProject(name, path, withStillsAndLUTs)` | ✅ |
| `archive_project` | `ProjectManager.ArchiveProject(name, path, ...)` | ✅ |

### Timeline-navigasjon (3)
| Tool | API | Status |
|---|---|---|
| `get_all_timelines` | `Project.GetTimelineByIndex(i)` loop | ✅ |
| `switch_timeline` | `Project.SetCurrentTimeline(timeline)` | ✅ |
| `duplicate_timeline` | `Timeline.DuplicateTimeline(name)` | ✅ |

### Timeline-redigering (3)
| Tool | API | Status |
|---|---|---|
| `add_timeline_track` | `Timeline.AddTrack(trackType, subType)` | ✅ |
| `delete_timeline_clips` | `Timeline.DeleteClips([items], ripple)` | ✅ |
| `delete_timeline_markers` | `Timeline.DeleteMarkersByColor()` / `DeleteMarkerAtFrame()` | ✅ |

### Media Pool (9)
| Tool | API | Status |
|---|---|---|
| `set_current_media_pool_folder` | `MediaPool.SetCurrentFolder(folder)` | ✅ |
| `move_clips_to_folder` | `MediaPool.MoveClips([clips], folder)` | ✅ |
| `relink_clips` | `MediaPool.RelinkClips([items], folderPath)` | ✅ |
| `auto_sync_audio` | `MediaPool.AutoSyncAudio([items], {settings})` | ✅ |
| `get_clip_metadata` | `MediaPoolItem.GetMetadata(type)` | ✅ |
| `set_clip_metadata` | `MediaPoolItem.SetMetadata({dict})` | ✅ |
| `add_clip_markers` | `MediaPoolItem.AddMarker(...)` | ✅ |
| `replace_clip` | `MediaPoolItem.ReplaceClip(path)` | ✅ |
| `create_timeline_from_clips` | `MediaPool.CreateTimelineFromClips(name, [clips])` | ✅ |

### Render (3)
| Tool | API | Status |
|---|---|---|
| `render_with_quick_export` | `Project.RenderWithQuickExport(preset, params)` | ✅ |
| `save_render_preset` | `Project.SaveAsNewRenderPreset(name)` | ✅ |
| `delete_render_job` | `Project.DeleteRenderJob(id)` / `DeleteAllRenderJobs()` | ✅ |

### Grading & Gallery (7)
| Tool | API | Status |
|---|---|---|
| `grab_still` | `Timeline.GrabStill()` | ✅ |
| `export_gallery_stills` | `GalleryStillAlbum.ExportStills(stills, folder, prefix, format)` | ✅ |
| `export_lut` | `TimelineItem.ExportLUT(type, path)` | ✅ |
| `copy_grades` | `TimelineItem.CopyGrades([targets])` | ✅ |
| `set_node_enabled` | `Graph.SetNodeEnabled(nodeIndex, bool)` | ✅ |
| `add_color_version` | `TimelineItem.AddVersion(name, type)` | ✅ |
| `load_color_version` | `TimelineItem.LoadVersionByName(name, type)` | ✅ |

### v21 AI-funksjoner (8)
Batch-pattern: optional `folder_name` (bin) eller `clip_name` (enkeltklipp).

| Tool | API | Status |
|---|---|---|
| `generate_speech` | `Project.GenerateSpeech({settings}, timecode)` | ✅ |
| `analyze_for_intellisearch` | `Folder/MediaPoolItem.AnalyzeForIntellisearch(faces, mode)` | ✅ |
| `remove_motion_blur` | `Folder/MediaPoolItem.RemoveMotionBlur({option})` | ✅ |
| `analyze_for_slate` | `Folder/MediaPoolItem.AnalyzeForSlate(color)` | ✅ |
| `perform_audio_classification` | `Folder/MediaPoolItem.PerformAudioClassification()` | ✅ |
| `transcribe_clip_audio` | `Folder/MediaPoolItem.TranscribeAudio(speakerDetection)` | ✅ |
| `apply_fairlight_preset` | `Project.ApplyFairlightPresetToCurrentTimeline(name)` | ✅ |
| `disable_background_tasks` | `Resolve.DisableBackgroundTasksForCurrentResolveSession()` | ✅ |

### Photo Page (5)
| Tool | API | Status |
|---|---|---|
| `open_photo_page` | `Resolve.OpenPage("photo")` | ✅ |
| `create_photo_album` | `Gallery.CreateGalleryStillAlbum()` / `CreateGalleryPowerGradeAlbum()` | ✅ |
| `manage_photo_albums` | `Gallery.GetGalleryStillAlbums()` / `SetAlbumName()` / `SetCurrentStillAlbum()` | ✅ |
| `export_graded_stills` | `GalleryStillAlbum.ExportStills(...)` | ✅ |
| `manage_gallery_stills` | `GalleryStillAlbum.GetStills()` / `SetLabel()` / `DeleteStills()` | ✅ |

---

## 🔲 PR 2 — MEDIUM prioritet (~71 tools)

**Branch:** `feature/tools-medium-priority` (ikke startet)

### Timeline (13)
| Tool | API | Status |
|---|---|---|
| `set_timeline_name` | `Timeline.SetName(name)` | 🔲 |
| `set_start_timecode` | `Timeline.SetStartTimecode(tc)` | 🔲 |
| `get_start_timecode` | `Timeline.GetStartTimecode()` | 🔲 |
| `set_track_enable` | `Timeline.SetTrackEnable(type, idx, bool)` | 🔲 |
| `set_track_lock` | `Timeline.SetTrackLock(type, idx, bool)` | 🔲 |
| `set_track_name` | `Timeline.SetTrackName(type, idx, name)` | 🔲 |
| `delete_track` | `Timeline.DeleteTrack(type, idx)` | 🔲 |
| `get_track_info` | `Timeline.GetTrackName/GetIsTrackEnabled/GetIsTrackLocked/GetTrackSubType` | 🔲 |
| `insert_generator` | `Timeline.InsertGeneratorIntoTimeline(name)` | 🔲 |
| `insert_title` | `Timeline.InsertTitleIntoTimeline(name)` | 🔲 |
| `insert_ofx_generator` | `Timeline.InsertOFXGeneratorIntoTimeline(name)` | 🔲 |
| `create_compound_clip` | `Timeline.CreateCompoundClip([items], {info})` | 🔲 |
| `import_timeline_from_file` | `MediaPool.ImportTimelineFromFile(path, {options})` | 🔲 |

### Timeline (fortsettelse, 8)
| Tool | API | Status |
|---|---|---|
| `set_clips_linked` | `Timeline.SetClipsLinked([items], bool)` | 🔲 |
| `get_current_video_item` | `Timeline.GetCurrentVideoItem()` | 🔲 |
| `grab_all_stills` | `Timeline.GrabAllStills(stillFrameSource)` | 🔲 |
| `set_mark_in_out` | `Timeline.SetMarkInOut(in, out, type)` | 🔲 |
| `clear_mark_in_out` | `Timeline.ClearMarkInOut(type)` | 🔲 |
| `get_timeline_node_graph` | `Timeline.GetNodeGraph()` | 🔲 |
| `analyze_dolby_vision` | `Timeline.AnalyzeDolbyVision([items], type)` | 🔲 |
| `set_start_timecode` | `Timeline.SetStartTimecode(tc)` | 🔲 |

### Timeline Item (10)
| Tool | API | Status |
|---|---|---|
| `set_clip_name` | `TimelineItem.SetName(name)` | 🔲 |
| `set_clip_enabled` | `TimelineItem.SetClipEnabled(bool)` | 🔲 |
| `add_timeline_flags` | `TimelineItem.AddFlag(color)` / `GetFlagList()` | 🔲 |
| `clear_timeline_flags` | `TimelineItem.ClearFlags(color)` | 🔲 |
| `get_clip_positions` | `TimelineItem.GetStart/GetEnd/GetDuration/GetLeftOffset/GetRightOffset` | 🔲 |
| `assign_color_group` | `TimelineItem.AssignToColorGroup(group)` | 🔲 |
| `remove_from_color_group` | `TimelineItem.RemoveFromColorGroup()` | 🔲 |
| `update_sidecar` | `TimelineItem.UpdateSidecar()` | 🔲 |
| `get_linked_items` | `TimelineItem.GetLinkedItems()` | 🔲 |
| `set_cache_mode` | `TimelineItem.SetColorOutputCache()` / `SetFusionOutputCache()` | 🔲 |

### Media Pool (8)
| Tool | API | Status |
|---|---|---|
| `delete_clips` | `MediaPool.DeleteClips([clips])` | 🔲 |
| `delete_folders` | `MediaPool.DeleteFolders([folders])` | 🔲 |
| `move_folders` | `MediaPool.MoveFolders([folders], target)` | 🔲 |
| `export_metadata_csv` | `MediaPool.ExportMetadata(fileName, [clips])` | 🔲 |
| `link_proxy_media` | `MediaPoolItem.LinkProxyMedia(path)` | 🔲 |
| `unlink_proxy_media` | `MediaPoolItem.UnlinkProxyMedia()` | 🔲 |
| `get_selected_clips` | `MediaPool.GetSelectedClips()` | 🔲 |
| `clear_transcription` | `MediaPoolItem/Folder.ClearTranscription()` | 🔲 |
| `clear_audio_classification` | `MediaPoolItem/Folder.ClearAudioClassification()` | 🔲 |

### Gallery & Grading (9)
| Tool | API | Status |
|---|---|---|
| `import_stills` | `GalleryStillAlbum.ImportStills([paths])` | 🔲 |
| `delete_stills` | `GalleryStillAlbum.DeleteStills([stills])` | 🔲 |
| `set_still_label` | `GalleryStillAlbum.SetLabel(still, label)` | 🔲 |
| `get_color_groups` | `Project.GetColorGroupsList()` | 🔲 |
| `add_color_group` | `Project.AddColorGroup(name)` | 🔲 |
| `delete_color_group` | `Project.DeleteColorGroup(group)` | 🔲 |
| `get_group_node_graph` | `ColorGroup.GetPreClipNodeGraph()` / `GetPostClipNodeGraph()` | 🔲 |
| `get_color_versions` | `TimelineItem.GetVersionNameList(type)` | 🔲 |
| `delete_color_version` | `TimelineItem.DeleteVersionByName(name, type)` | 🔲 |

### Graph / Nodegraf (6)
| Tool | API | Status |
|---|---|---|
| `get_node_info` | `Graph.GetNumNodes()` / `GetNodeLabel()` / `GetToolsInNode()` | 🔲 |
| `get_lut_from_node` | `Graph.GetLUT(nodeIndex)` | 🔲 |
| `set_node_cache_mode` | `Graph.SetNodeCacheMode(nodeIndex, value)` | 🔲 |
| `apply_grade_from_drx` | `Graph.ApplyGradeFromDRX(path, gradeMode)` | 🔲 |
| `apply_arri_cdl_lut` | `Graph.ApplyArriCdlLut()` | 🔲 |
| `reset_all_grades` | `Graph.ResetAllGrades()` | 🔲 |

### Resolve-nivå (5)
| Tool | API | Status |
|---|---|---|
| `manage_layout_presets` | `Resolve.LoadLayoutPreset()` / `SaveLayoutPreset()` / `ExportLayoutPreset()` | 🔲 |
| `set_keyframe_mode` | `Resolve.SetKeyframeMode()` / `GetKeyframeMode()` | 🔲 |
| `get_fairlight_presets` | `Resolve.GetFairlightPresets()` | 🔲 |
| `reset_intellisearch` | `Project.ResetIntellisearchAnalysis()` | 🔲 |
| `refresh_lut_list` | `Project.RefreshLUTList()` | 🔲 |

### MediaPoolItem ekstra (6)
| Tool | API | Status |
|---|---|---|
| `get_third_party_metadata` | `MediaPoolItem.GetThirdPartyMetadata(type)` | 🔲 |
| `set_third_party_metadata` | `MediaPoolItem.SetThirdPartyMetadata(type, value)` | 🔲 |
| `get_audio_mapping` | `MediaPoolItem.GetAudioMapping()` | 🔲 |
| `set_clip_mark_in_out` | `MediaPoolItem.SetMarkInOut(in, out, type)` | 🔲 |
| `monitor_growing_file` | `MediaPoolItem.MonitorGrowingFile()` | 🔲 |
| `replace_clip_preserve_subclip` | `MediaPoolItem.ReplaceClipPreserveSubClip(path)` | 🔲 |

### Takes (4)
| Tool | API | Status |
|---|---|---|
| `add_take` | `TimelineItem.AddTake(item, startFrame, endFrame)` | 🔲 |
| `select_take` | `TimelineItem.SelectTakeByIndex(idx)` | 🔲 |
| `delete_take` | `TimelineItem.DeleteTakeByIndex(idx)` | 🔲 |
| `finalize_take` | `TimelineItem.FinalizeTake()` | 🔲 |

### Prosjekt/database (4)
| Tool | API | Status |
|---|---|---|
| `close_project` | `ProjectManager.CloseProject(project)` | 🔲 |
| `get_project_database_info` | `ProjectManager.GetCurrentDatabase()` / `GetDatabaseList()` | 🔲 |
| `switch_database` | `ProjectManager.SetCurrentDatabase({dbInfo})` | 🔲 |
| `import_project` | `ProjectManager.ImportProject(filePath, name)` | 🔲 |

---

## 🔲 PR 3 — LAV prioritet (~15 tools)

**Branch:** `feature/tools-low-priority` (ikke startet)

| Tool | API | Status |
|---|---|---|
| `quit_resolve` | `Resolve.Quit()` | 🔲 |
| `get_mounted_volumes` | `MediaStorage.GetMountedVolumeList()` | 🔲 |
| `browse_media_storage` | `MediaStorage.GetFileList()` / `GetSubFolderList()` | 🔲 |
| `reveal_in_storage` | `MediaStorage.RevealInStorage(path)` | 🔲 |
| `import_burn_in_preset` | `Resolve.ImportBurnInPreset(path)` | 🔲 |
| `export_burn_in_preset` | `Resolve.ExportBurnInPreset(name, path)` | 🔲 |
| `create_stereo_clip` | `MediaPool.CreateStereoClip(left, right)` | 🔲 |
| `convert_timeline_stereo` | `Timeline.ConvertTimelineToStereo()` | 🔲 |
| `analyze_dolby_vision` | `Timeline.AnalyzeDolbyVision([items], type)` | 🔲 |
| `cloud_project_management` | `ProjectManager.CreateCloudProject()` / `LoadCloudProject()` m.fl. | 🔲 |
| `import_folder_from_file` | `MediaPool.ImportFolderFromFile(path, sourceClipsPath)` | 🔲 |
| `get_render_resolutions` | `Project.GetRenderResolutions(format, codec)` | 🔲 |
| `delete_render_preset` | `Project.DeleteRenderPreset(name)` | 🔲 |
| `manage_clip_mattes` | `MediaPool.GetClipMatteList()` / `DeleteClipMattes()` | 🔲 |
| `add_timeline_mattes` | `MediaStorage.AddTimelineMattesToMediaPool([paths])` | 🔲 |

---

## Kodekonvensjoner

Alle tools følger dette mønsteret:
```python
@mcp.tool()
def tool_name(param: type = default) -> str:
    """One-line description.

    Parameters:
    - param: description
    """
    try:
        conn = _conn()
        # ... implementation
        return json.dumps({...}, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"
```

- `_conn()` alltid først
- `_require_timeline(conn)` for timeline-avhengige tools
- `_ok(result, "success", "fail")` for True/False API-kall
- `json.dumps(..., indent=2, ensure_ascii=False)` for strukturert output
- Feil returneres alltid som streng, aldri exception
- Batch-tools: optional `folder_name` (bin-nivå) eller `clip_name` (klipp-nivå)

---

*Sist oppdatert: PR 1 ferdig (105 tools)*
