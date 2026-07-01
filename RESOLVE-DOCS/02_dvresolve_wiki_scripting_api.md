# DaVinci Resolve Scripting API — dvresolve.com Wiki
## Source: DaVinci Resolve Wiki (community)
## URL: https://wiki.dvresolve.com/developer-docs/scripting-api
## Last updated in source: 18 July 2023 (older version — missing v20+ and v21 additions)
## Fetched: 2026-06-30

---

## Overview

As with Blackmagic Design Fusion scripts, user scripts written in Lua and Python programming languages are supported. By default, scripts can be invoked from the Console window in the Fusion page, or via command line. This permission can be changed in Resolve Preferences, to be only from Console, or to be invoked from the local network.

## Prerequisites

- Lua 5.1
- Python 2.7 64-bit
- Python >= 3.6 64-bit

## Environment Variables

Mac OS X:
  RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
  RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
  PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

Windows:
  RESOLVE_SCRIPT_API="%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
  RESOLVE_SCRIPT_LIB="C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
  PYTHONPATH="%PYTHONPATH%;%RESOLVE_SCRIPT_API%\Modules\"

Linux:
  RESOLVE_SCRIPT_API="/opt/resolve/Developer/Scripting"
  RESOLVE_SCRIPT_LIB="/opt/resolve/libs/Fusion/fusionscript.so"
  PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

## Script Locations

Mac OS X:
  - All users: /Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts
  - Specific user: /Users/<UserName>/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts

Windows:
  - All users: %PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Fusion\Scripts
  - Specific user: %APPDATA%\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts

Linux:
  - All users: /opt/resolve/Fusion/Scripts
  - Specific user: $HOME/.local/share/DaVinciResolve/Fusion/Scripts

## Basic Resolve API

### Resolve

- Fusion() --> Fusion
- GetMediaStorage() --> MediaStorage
- GetProjectManager() --> ProjectManager
- OpenPage(pageName) --> Bool — Input: "media", "cut", "edit", "fusion", "color", "fairlight", "deliver"
- GetCurrentPage() --> String — Returns: "media", "cut", "edit", "fusion", "color", "fairlight", "deliver", None
- GetProductName() --> string
- GetVersion() --> [version fields] — [major, minor, patch, build, suffix]
- GetVersionString() --> string — "major.minor.patch[suffix].build"
- LoadLayoutPreset(presetName) --> Bool
- UpdateLayoutPreset(presetName) --> Bool
- ExportLayoutPreset(presetName, presetFilePath) --> Bool
- DeleteLayoutPreset(presetName) --> Bool
- SaveLayoutPreset(presetName) --> Bool
- ImportLayoutPreset(presetFilePath, presetName) --> Bool
- Quit() --> None
- ImportRenderPreset(presetPath) --> Bool
- ExportRenderPreset(presetName, exportPath) --> Bool
- ImportBurnInPreset(presetPath) --> Bool
- ExportBurnInPreset(presetName, exportPath) --> Bool

### ProjectManager

- ArchiveProject(projectName, filePath, isArchiveSrcMedia=True, isArchiveRenderCache=True, isArchiveProxyMedia=False) --> Bool
- CreateProject(projectName) --> Project
- DeleteProject(projectName) --> Bool
- LoadProject(projectName) --> Project
- GetCurrentProject() --> Project
- SaveProject() --> Bool
- CloseProject(project) --> Bool
- CreateFolder(folderName) --> Bool
- DeleteFolder(folderName) --> Bool
- GetProjectListInCurrentFolder() --> [project names...]
- GetFolderListInCurrentFolder() --> [folder names...]
- GotoRootFolder() --> Bool
- GotoParentFolder() --> Bool
- GetCurrentFolder() --> string
- OpenFolder(folderName) --> Bool
- ImportProject(filePath, projectName=None) --> Bool
- ExportProject(projectName, filePath, withStillsAndLUTs=True) --> Bool
- RestoreProject(filePath, projectName=None) --> Bool
- GetCurrentDatabase() --> {dbInfo} — keys: 'DbType', 'DbName', optional 'IpAddress'
- GetDatabaseList() --> [{dbInfo}]
- SetCurrentDatabase({dbInfo}) --> Bool

### Project

- GetMediaPool() --> MediaPool
- GetTimelineCount() --> int
- GetTimelineByIndex(idx) --> Timeline
- GetCurrentTimeline() --> Timeline
- SetCurrentTimeline(timeline) --> Bool
- GetGallery() --> Gallery
- GetName() --> string
- SetName(projectName) --> Bool
- GetPresetList() --> [presets...]
- SetPreset(presetName) --> Bool
- AddRenderJob() --> string
- DeleteRenderJob(jobId) --> Bool
- DeleteAllRenderJobs() --> Bool
- GetRenderJobList() --> [render jobs...]
- GetRenderPresetList() --> [presets...]
- StartRendering(jobId1, jobId2, ...) --> Bool
- StartRendering([jobIds...], isInteractiveMode=False) --> Bool
- StartRendering(isInteractiveMode=False) --> Bool
- StopRendering() --> None
- IsRenderingInProgress() --> Bool
- LoadRenderPreset(presetName) --> Bool
- SaveAsNewRenderPreset(presetName) --> Bool
- SetRenderSettings({settings}) --> Bool
- GetRenderJobStatus(jobId) --> {status info}
- GetSetting(settingName) --> string
- SetSetting(settingName, settingValue) --> Bool
- GetRenderFormats() --> {render formats..}
- GetRenderCodecs(renderFormat) --> {render codecs...}
- GetCurrentRenderFormatAndCodec() --> {format, codec}
- SetCurrentRenderFormatAndCodec(format, codec) --> Bool
- GetCurrentRenderMode() --> int — 0=Individual clips, 1=Single clip
- SetCurrentRenderMode(renderMode) --> Bool
- GetRenderResolutions(format, codec) --> [{Resolution}]
- RefreshLUTList() --> Bool
- GetUniqueId() --> string
- InsertAudioToCurrentTrackAtPlayhead(mediaPath, startOffsetInSamples, durationInSamples) --> Bool
- LoadBurnInPreset(presetName) --> Bool
- ExportCurrentFrameAsStill(filePath) --> Bool

### MediaStorage

- GetMountedVolumeList() --> [paths...]
- GetSubFolderList(folderPath) --> [paths...]
- GetFileList(folderPath) --> [paths...]
- RevealInStorage(path) --> Bool
- AddItemListToMediaPool(item1, item2, ...) --> [clips...]
- AddItemListToMediaPool([items...]) --> [clips...]
- AddItemListToMediaPool([{itemInfo}, ...]) --> [clips...]
- AddClipMattesToMediaPool(MediaPoolItem, [paths], stereoEye) --> Bool
- AddTimelineMattesToMediaPool([paths]) --> [MediaPoolItems]

### MediaPool

- GetRootFolder() --> Folder
- AddSubFolder(folder, name) --> Folder
- RefreshFolders() --> Bool
- CreateEmptyTimeline(name) --> Timeline
- AppendToTimeline(clip1, clip2, ...) --> [TimelineItem]
- AppendToTimeline([clips]) --> [TimelineItem]
- AppendToTimeline([{clipInfo}, ...]) --> [TimelineItem]
- CreateTimelineFromClips(name, clip1, clip2,...) --> Timeline
- CreateTimelineFromClips(name, [clips]) --> Timeline
- CreateTimelineFromClips(name, [{clipInfo}]) --> Timeline
- ImportTimelineFromFile(filePath, {importOptions}) --> Timeline
- DeleteTimelines([timeline]) --> Bool
- GetCurrentFolder() --> Folder
- SetCurrentFolder(Folder) --> Bool
- DeleteClips([clips]) --> Bool
- ImportFolderFromFile(filePath, sourceClipsPath="") --> Bool
- DeleteFolders([subfolders]) --> Bool
- MoveClips([clips], targetFolder) --> Bool
- MoveFolders([folders], targetFolder) --> Bool
- GetClipMatteList(MediaPoolItem) --> [paths]
- GetTimelineMatteList(Folder) --> [MediaPoolItems]
- DeleteClipMattes(MediaPoolItem, [paths]) --> Bool
- RelinkClips([MediaPoolItem], folderPath) --> Bool
- UnlinkClips([MediaPoolItem]) --> Bool
- ImportMedia([items...]) --> [MediaPoolItems]
- ImportMedia([{clipInfo}]) --> [MediaPoolItems]
- ExportMetadata(fileName, [clips]) --> Bool
- GetUniqueId() --> string

### Folder

- GetClipList() --> [clips...]
- GetName() --> string
- GetSubFolderList() --> [folders...]
- GetIsFolderStale() --> bool
- GetUniqueId() --> string
- Export(filePath) --> bool

### MediaPoolItem

- GetName() --> string
- GetMetadata(metadataType=None) --> string|dict
- SetMetadata(metadataType, metadataValue) --> Bool
- SetMetadata({metadata}) --> Bool
- GetMediaId() --> string
- AddMarker(frameId, color, name, note, duration, customData) --> Bool
- GetMarkers() --> {markers...}
- GetMarkerByCustomData(customData) --> {markers...}
- UpdateMarkerCustomData(frameId, customData) --> Bool
- GetMarkerCustomData(frameId) --> string
- DeleteMarkersByColor(color) --> Bool
- DeleteMarkerAtFrame(frameNum) --> Bool
- DeleteMarkerByCustomData(customData) --> Bool
- AddFlag(color) --> Bool
- GetFlagList() --> [colors...]
- ClearFlags(color) --> Bool
- GetClipColor() --> string
- SetClipColor(colorName) --> Bool
- ClearClipColor() --> Bool
- GetClipProperty(propertyName=None) --> string|dict
- SetClipProperty(propertyName, propertyValue) --> Bool
- LinkProxyMedia(proxyMediaFilePath) --> Bool
- UnlinkProxyMedia() --> Bool
- ReplaceClip(filePath) --> Bool
- GetUniqueId() --> string
- TranscribeAudio() --> Bool
- ClearTranscription() --> Bool

### Timeline

- GetName() --> string
- SetName(timelineName) --> Bool
- GetStartFrame() --> int
- GetEndFrame() --> int
- SetStartTimecode(timecode) --> Bool
- GetStartTimecode() --> string
- GetTrackCount(trackType) --> int — "audio", "video", "subtitle"
- AddTrack(trackType, optionalSubTrackType) --> Bool
- DeleteTrack(trackType, trackIndex) --> Bool
- SetTrackEnable(trackType, trackIndex, Bool) --> Bool
- GetIsTrackEnabled(trackType, trackIndex) --> Bool
- SetTrackLock(trackType, trackIndex, Bool) --> Bool
- GetIsTrackLocked(trackType, trackIndex) --> Bool
- DeleteClips([timelineItems], Bool) --> Bool
- SetClipsLinked([timelineItems], Bool) --> Bool
- GetItemListInTrack(trackType, index) --> [items...]
- AddMarker(frameId, color, name, note, duration, customData) --> Bool
- GetMarkers() --> {markers...}
- GetMarkerByCustomData(customData) --> {markers...}
- UpdateMarkerCustomData(frameId, customData) --> Bool
- GetMarkerCustomData(frameId) --> string
- DeleteMarkersByColor(color) --> Bool
- DeleteMarkerAtFrame(frameNum) --> Bool
- DeleteMarkerByCustomData(customData) --> Bool
- ApplyGradeFromDRX(path, gradeMode, item1, item2, ...) --> Bool
- ApplyGradeFromDRX(path, gradeMode, [items]) --> Bool
- GetCurrentTimecode() --> string
- SetCurrentTimecode(timecode) --> Bool
- GetCurrentVideoItem() --> item
- GetCurrentClipThumbnailImage() --> {thumbnailData}
- GetTrackName(trackType, trackIndex) --> string
- SetTrackName(trackType, trackIndex, name) --> Bool
- DuplicateTimeline(timelineName) --> timeline
- CreateCompoundClip([timelineItems], {clipInfo}) --> timelineItem
- CreateFusionClip([timelineItems]) --> timelineItem
- ImportIntoTimeline(filePath, {importOptions}) --> Bool
- Export(fileName, exportType, exportSubtype) --> Bool
- GetSetting(settingName) --> string
- SetSetting(settingName, settingValue) --> Bool
- InsertGeneratorIntoTimeline(generatorName) --> TimelineItem
- InsertFusionGeneratorIntoTimeline(generatorName) --> TimelineItem
- InsertFusionCompositionIntoTimeline() --> TimelineItem
- InsertOFXGeneratorIntoTimeline(generatorName) --> TimelineItem
- InsertTitleIntoTimeline(titleName) --> TimelineItem
- InsertFusionTitleIntoTimeline(titleName) --> TimelineItem
- GrabStill() --> galleryStill
- GrabAllStills(stillFrameSource) --> [galleryStill]
- GetUniqueId() --> string
- CreateSubtitlesFromAudio() --> Bool
- DetectSceneCuts() --> Bool

### TimelineItem

- GetName() --> string
- SetName(name) --> bool
- GetDuration() --> int
- GetEnd() --> int
- GetFusionCompCount() --> int
- GetFusionCompByIndex(compIndex) --> fusionComp
- GetFusionCompNameList() --> [names...]
- GetFusionCompByName(compName) --> fusionComp
- GetLeftOffset() --> int
- GetRightOffset() --> int
- GetStart() --> int
- SetProperty(propertyKey, propertyValue) --> Bool
- GetProperty(propertyKey) --> int/[key:value]
- AddMarker(frameId, color, name, note, duration, customData) --> Bool
- GetMarkers() --> {markers...}
- GetMarkerByCustomData(customData) --> {markers...}
- UpdateMarkerCustomData(frameId, customData) --> Bool
- GetMarkerCustomData(frameId) --> string
- DeleteMarkersByColor(color) --> Bool
- DeleteMarkerAtFrame(frameNum) --> Bool
- DeleteMarkerByCustomData(customData) --> Bool
- AddFlag(color) --> Bool
- GetFlagList() --> [colors...]
- ClearFlags(color) --> Bool
- GetClipColor() --> string
- SetClipColor(colorName) --> Bool
- ClearClipColor() --> Bool
- AddFusionComp() --> fusionComp
- ImportFusionComp(path) --> fusionComp
- ExportFusionComp(path, compIndex) --> Bool
- DeleteFusionCompByName(compName) --> Bool
- LoadFusionCompByName(compName) --> fusionComp
- RenameFusionCompByName(oldName, newName) --> Bool
- AddVersion(versionName, versionType) --> Bool
- GetCurrentVersion() --> {versionName...}
- DeleteVersionByName(versionName, versionType) --> Bool
- LoadVersionByName(versionName, versionType) --> Bool
- RenameVersionByName(oldName, newName, versionType) --> Bool
- GetVersionNameList(versionType) --> [names...]
- GetMediaPoolItem() --> MediaPoolItem
- GetStereoConvergenceValues() --> {keyframes...}
- GetStereoLeftFloatingWindowParams() --> {keyframes...}
- GetStereoRightFloatingWindowParams() --> {keyframes...}
- SetLUT(nodeIndex, lutPath) --> Bool
- GetLUT(nodeIndex) --> String
- SetCDL([CDL map]) --> Bool
- AddTake(mediaPoolItem, startFrame, endFrame) --> Bool
- GetSelectedTakeIndex() --> int
- GetTakesCount() --> int
- GetTakeByIndex(idx) --> {takeInfo...}
- DeleteTakeByIndex(idx) --> Bool
- SelectTakeByIndex(idx) --> Bool
- FinalizeTake() --> Bool
- CopyGrades([tgtTimelineItems]) --> Bool
- SetClipEnabled(Bool) --> Bool
- GetClipEnabled() --> Bool
- UpdateSidecar() --> Bool
- GetUniqueId() --> string
- LoadBurnInPreset(presetName) --> Bool
- GetNodeLabel(nodeIndex) --> string
- CreateMagicMask(mode) --> Bool — mode: "F", "B", "BI"
- RegenerateMagicMask() --> Bool
- Stabilize() --> Bool
- SmartReframe() --> Bool

### Gallery

- GetAlbumName(galleryStillAlbum) --> string
- SetAlbumName(galleryStillAlbum, albumName) --> Bool
- GetCurrentStillAlbum() --> galleryStillAlbum
- SetCurrentStillAlbum(galleryStillAlbum) --> Bool
- GetGalleryStillAlbums() --> [galleryStillAlbum]

### GalleryStillAlbum

- GetStills() --> [galleryStill]
- GetLabel(galleryStill) --> string
- SetLabel(galleryStill, label) --> Bool
- ImportStills([filePaths]) --> Bool
- ExportStills([galleryStill], folderPath, filePrefix, format) --> Bool
- DeleteStills([galleryStill]) --> Bool

### GalleryStill

(No API functions — object type used by other classes)

## Render Settings Keys

- "SelectAllFrames": Bool
- "MarkIn": int
- "MarkOut": int
- "TargetDir": string
- "CustomName": string
- "UniqueFilenameStyle": 0=Prefix, 1=Suffix
- "ExportVideo": Bool
- "ExportAudio": Bool
- "FormatWidth": int
- "FormatHeight": int
- "FrameRate": float
- "PixelAspectRatio": string
- "VideoQuality": int or string
- "AudioCodec": string
- "AudioBitDepth": int
- "AudioSampleRate": int
- "ColorSpaceTag": string
- "GammaTag": string
- "ExportAlpha": Bool
- "EncodingProfile": string
- "MultiPassEncode": Bool
- "AlphaMode": 0=Premultiplied, 1=Straight
- "NetworkOptimization": Bool

## Timeline Export Types

- resolve.EXPORT_AAF
- resolve.EXPORT_DRT
- resolve.EXPORT_EDL
- resolve.EXPORT_FCP_7_XML
- resolve.EXPORT_FCPXML_1_8
- resolve.EXPORT_FCPXML_1_9
- resolve.EXPORT_FCPXML_1_10
- resolve.EXPORT_HDR_10_PROFILE_A
- resolve.EXPORT_HDR_10_PROFILE_B
- resolve.EXPORT_TEXT_CSV
- resolve.EXPORT_TEXT_TAB
- resolve.EXPORT_DOLBY_VISION_VER_2_9
- resolve.EXPORT_DOLBY_VISION_VER_4_0
- resolve.EXPORT_DOLBY_VISION_VER_5_1
- resolve.EXPORT_OTIO

## Timeline Export Subtypes

- resolve.EXPORT_NONE
- resolve.EXPORT_AAF_NEW
- resolve.EXPORT_AAF_EXISTING
- resolve.EXPORT_CDL
- resolve.EXPORT_SDL
- resolve.EXPORT_MISSING_CLIPS

## Timeline Item Properties

- "Pan", "Tilt", "ZoomX", "ZoomY", "ZoomGang"
- "RotationAngle", "AnchorPointX", "AnchorPointY"
- "Pitch", "Yaw", "FlipX", "FlipY"
- "CropLeft", "CropRight", "CropTop", "CropBottom", "CropSoftness", "CropRetain"
- "DynamicZoomEase": DYNAMIC_ZOOM_EASE_LINEAR=0, _IN, _OUT, _IN_AND_OUT
- "CompositeMode": COMPOSITE_NORMAL=0, _ADD, _SUBTRACT, _DIFF, _MULTIPLY, _SCREEN, _OVERLAY, _HARDLIGHT, _SOFTLIGHT, _DARKEN, _LIGHTEN, _COLOR_DODGE, _COLOR_BURN, _EXCLUSION, _HUE, _SATURATE, _COLORIZE, _LUMA_MASK, _DIVIDE, _LINEAR_DODGE, _LINEAR_BURN, _LINEAR_LIGHT, _VIVID_LIGHT, _PIN_LIGHT, _HARD_MIX, _LIGHTER_COLOR, _DARKER_COLOR, _FOREGROUND, _ALPHA, _INVERTED_ALPHA, _LUM, _INVERTED_LUM
- "Opacity": 0.0 to 100.0
- "Distortion": -1.0 to 1.0
- "RetimeProcess": RETIME_USE_PROJECT=0, _NEAREST, _FRAME_BLEND, _OPTICAL_FLOW
- "MotionEstimation": MOTION_EST_USE_PROJECT=0, _STANDARD_FASTER, _STANDARD_BETTER, _ENHANCED_FASTER, _ENHANCED_BETTER, _SPEED_WRAP
- "Scaling": SCALE_USE_PROJECT=0, _CROP, _FIT, _FILL, _STRETCH
- "ResizeFilter": RESIZE_FILTER_USE_PROJECT=0, _SHARPER, _SMOOTHER, _BICUBIC, _BILINEAR, _BESSEL, _BOX, _CATMULL_ROM, _CUBIC, _GAUSSIAN, _LANCZOS, _MITCHELL, _NEAREST_NEIGHBOR, _QUADRATIC, _SINC, _LINEAR
