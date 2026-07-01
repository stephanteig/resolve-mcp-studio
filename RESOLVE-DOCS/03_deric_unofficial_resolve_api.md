# Unofficial DaVinci Resolve Scripting Documentation
## Source: deric.github.io
## URL: https://deric.github.io/DaVinciResolve-API-Docs/
## WARNING: This is an older version (last updated ~2022). Missing v20+ and v21 additions.
## Fetched: 2026-06-30

---

## About This Document

This document is a formatted copy of the official BlackmagicDesign DaVinci Resolve scripting documentation.
WARNING: This document might contain errors and might not be up to date with the current Resolve version.

## Resolve

| Method | Return | Comment |
|---|---|---|
| Fusion() | Fusion | Returns the Fusion object |
| GetMediaStorage() | MediaStorage | Returns media storage object |
| GetProjectManager() | ProjectManager | Returns project manager object |
| OpenPage(pageName) | None | Switch page: "media", "cut", "edit", "fusion", "color", "fairlight", "deliver" |

## ProjectManager

| Method | Return | Comment |
|---|---|---|
| CreateProject(projectName) | Project | Creates project if name is unique |
| DeleteProject(projectName) | Bool | Delete project in current folder |
| LoadProject(projectName) | Project | Load project by name |
| GetCurrentProject() | Project | Returns current project |
| SaveProject() | Bool | Saves current project |
| CloseProject(project) | Bool | Closes project without saving |
| CreateFolder(folderName) | Bool | Creates folder if name unique |
| GetProjectListInCurrentFolder() | [names...] | List projects in current folder |
| GetFolderListInCurrentFolder() | [names...] | List folders in current folder |
| GotoRootFolder() | Bool | Open root folder |
| GotoParentFolder() | Bool | Open parent folder |
| OpenFolder(folderName) | Bool | Open folder by name |
| ImportProject(filePath) | Bool | Import project file |
| ExportProject(projectName, filePath) | Bool | Export project to file |
| RestoreProject(filePath) | Bool | Restore project from backup |

## Project

| Method | Return | Comment |
|---|---|---|
| GetMediaPool() | MediaPool | Returns Media Pool object |
| GetTimelineCount() | int | Number of timelines |
| GetTimelineByIndex(idx) | Timeline | Timeline at index |
| GetCurrentTimeline() | Timeline | Current timeline |
| SetCurrentTimeline(timeline) | Bool | Set current timeline |
| GetName() | string | Project name |
| SetName(projectName) | Bool | Set project name |
| GetPresetList() | [presets...] | List presets |
| SetPreset(presetName) | Bool | Set preset |
| GetRenderJobList() | [jobs...] | List render jobs |
| GetRenderPresetList() | [presets...] | List render presets |
| StartRendering(...) | Bool | Start rendering |
| StopRendering() | None | Stop rendering |
| IsRenderingInProgress() | Bool | Check if rendering |
| AddRenderJob() | Bool | Add render job |
| DeleteAllRenderJobs() | Bool | Delete all render jobs |
| LoadRenderPreset(presetName) | Bool | Load render preset |
| SaveAsNewRenderPreset(presetName) | Bool | Save new render preset |
| SetRenderSettings({settings}) | Bool | Set render settings |
| GetRenderJobStatus(idx) | {status} | Get job status |
| GetSetting(settingName) | string | Get project setting |
| SetSetting(settingName, settingValue) | Bool | Set project setting |
| GetRenderFormats() | {formats} | Available render formats |
| GetRenderCodecs(renderFormat) | {codecs} | Available codecs |
| GetCurrentRenderFormatAndCodec() | {format, codec} | Current format/codec |
| SetCurrentRenderFormatAndCodec(format, codec) | Bool | Set format/codec |

## MediaStorage

| Method | Return | Comment |
|---|---|---|
| GetMountedVolumeList() | [paths...] | Mounted volumes |
| GetSubFolderList(folderPath) | [paths...] | Subfolders |
| GetFileList(folderPath) | [paths...] | Files in folder |
| RevealInStorage(path) | None | Reveal in media storage |
| AddItemListToMediaPool(items) | [clips...] | Add to media pool |

## MediaPool

| Method | Return | Comment |
|---|---|---|
| GetRootFolder() | Folder | Root folder |
| AddSubFolder(folder, name) | Folder | Add subfolder |
| CreateEmptyTimeline(name) | Timeline | New timeline |
| AppendToTimeline(clips) | Bool | Append clips |
| CreateTimelineFromClips(name, clips) | Timeline | Create timeline from clips |
| ImportTimelineFromFile(filePath) | Timeline | Import timeline |
| GetCurrentFolder() | Folder | Current folder |
| SetCurrentFolder(Folder) | Bool | Set current folder |
| DeleteClips([clips]) | Bool | Delete clips |
| DeleteFolders([subfolders]) | Bool | Delete folders |
| MoveClips([clips], targetFolder) | Bool | Move clips |
| MoveFolders([folders], targetFolder) | Bool | Move folders |

## Folder

| Method | Return | Comment |
|---|---|---|
| GetClipList() | [clips...] | Clips in folder |
| GetName() | string | Folder name |
| GetSubFolderList() | [folders...] | Subfolders |

## MediaPoolItem

| Method | Return | Comment |
|---|---|---|
| GetMetadata(metadataType) | {metadata} | Get metadata |
| SetMetadata(type, value) | Bool | Set metadata |
| GetMediaId() | string | Unique media ID |
| AddMarker(frameId, color, name, note, duration) | Bool | Add marker |
| GetMarkers() | {markers...} | Get all markers |
| DeleteMarkersByColor(color) | Bool | Delete markers by color |
| DeleteMarkerAtFrame(frameNum) | Bool | Delete marker at frame |
| AddFlag(color) | Bool | Add flag |
| GetFlagList() | [colors...] | Get flags |
| ClearFlags(color) | Bool | Clear flags |
| GetClipColor() | string | Get clip color |
| SetClipColor(colorName) | Bool | Set clip color |
| ClearClipColor() | Bool | Clear clip color |
| GetClipProperty(propertyName) | {properties} | Get clip property |
| SetClipProperty(name, value) | Bool | Set clip property |

## Timeline

| Method | Return | Comment |
|---|---|---|
| GetName() | string | Timeline name |
| SetName(name) | Bool | Set name |
| GetStartFrame() | int | Start frame |
| GetEndFrame() | int | End frame |
| GetTrackCount(trackType) | int | Track count |
| GetItemListInTrack(trackType, index) | [items...] | Items on track |
| AddMarker(frameId, color, name, note, duration) | Bool | Add marker |
| GetMarkers() | {markers...} | Get markers |
| DeleteMarkersByColor(color) | Bool | Delete by color |
| DeleteMarkerAtFrame(frameNum) | Bool | Delete at frame |
| ApplyGradeFromDRX(path, gradeMode, items) | Bool | Apply grade |
| GetCurrentTimecode() | string | Current timecode |
| GetCurrentVideoItem() | item | Current video item |
| GetCurrentClipThumbnailImage() | {thumbnailData} | Current thumbnail |
| GetTrackName(trackType, trackIndex) | string | Track name |
| SetTrackName(trackType, trackIndex, name) | Bool | Set track name |

## TimelineItem

| Method | Return | Comment |
|---|---|---|
| GetName() | string | Item name |
| GetDuration() | int | Duration |
| GetEnd() | int | End frame |
| GetStart() | int | Start frame |
| GetFusionCompCount() | int | Fusion comp count |
| GetFusionCompByIndex(compIndex) | fusionComp | Get comp by index |
| GetFusionCompNameList() | [names...] | Comp names |
| GetFusionCompByName(compName) | fusionComp | Get comp by name |
| GetLeftOffset() | int | Left extension |
| GetRightOffset() | int | Right extension |
| AddMarker(frameId, color, name, note, duration) | Bool | Add marker |
| GetMarkers() | {markers...} | Get markers |
| DeleteMarkersByColor(color) | Bool | Delete by color |
| DeleteMarkerAtFrame(frameNum) | Bool | Delete at frame |
| AddFlag(color) | Bool | Add flag |
| GetFlagList() | [colors...] | Get flags |
| ClearFlags(color) | Bool | Clear flags |
| GetClipColor() | string | Clip color |
| SetClipColor(colorName) | Bool | Set color |
| ClearClipColor() | Bool | Clear color |
| AddFusionComp() | fusionComp | Add Fusion comp |
| ImportFusionComp(path) | fusionComp | Import comp |
| ExportFusionComp(path, compIndex) | Bool | Export comp |
| DeleteFusionCompByName(compName) | Bool | Delete comp |
| LoadFusionCompByName(compName) | fusionComp | Load comp |
| RenameFusionCompByName(old, new) | Bool | Rename comp |
| AddVersion(name, type) | Bool | Add version |
| DeleteVersionByName(name, type) | Bool | Delete version |
| LoadVersionByName(name, type) | Bool | Load version |
| RenameVersionByName(old, new, type) | Bool | Rename version |
| GetVersionNameList(type) | [names...] | Version names |
| GetMediaPoolItem() | MediaPoolItem | Source media pool item |
| SetLUT(nodeIndex, lutPath) | Bool | Set LUT |
| SetCDL([CDL map]) | Bool | Set CDL values |
| AddTake(mediaPoolItem, start, end) | Bool | Add take |
| GetSelectedTakeIndex() | int | Selected take |
| GetTakesCount() | int | Take count |
| GetTakeByIndex(idx) | {takeInfo} | Take info |
| DeleteTakeByIndex(idx) | Bool | Delete take |
| SelectTakeByIndex(idx) | Bool | Select take |
| FinalizeTake() | Bool | Finalize take |
| CopyGrades([targets]) | Bool | Copy grades |
| SetClipEnabled(Bool) | Bool | Enable/disable clip |
| GetClipEnabled() | Bool | Check if enabled |
| CreateMagicMask(mode) | Bool | Create magic mask |
| RegenerateMagicMask() | Bool | Regenerate mask |
| Stabilize() | Bool | Stabilize clip |
| SmartReframe() | Bool | Smart reframe |
