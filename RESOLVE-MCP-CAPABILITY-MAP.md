# resolve-mcp-studio: Capability Map
> Auto-generert fra Resolve 21 Scripting API (26 May 2026) og eksisterende MCP server-kode.
> Kilde: `RESOLVE-DOCS/05_resolve_v21_readme_official.txt` er autoritativ (v21).
> Eldre kilder (01–04) brukt kun for kontekst og diff-identifikasjon.

---

## EKSISTERENDE TOOLS (allerede implementert)

| Tool-navn | Resolve API-metode(r) | Beskrivelse |
|---|---|---|
| `get_project_info` | `Project.GetName()`, `Resolve.GetVersionString()`, `Resolve.GetCurrentPage()`, `Project.GetTimelineCount()`, `Project.GetSetting()` | Henter prosjektnavn, versjon, aktiv side og innstillinger |
| `open_page` | `Resolve.OpenPage(pageName)` | Bytter til angitt side (media, cut, edit, fusion, color, fairlight, deliver) |
| `get_current_page` | `Resolve.GetCurrentPage()` | Returnerer aktiv side |
| `get_media_pool_structure` | `MediaPool.GetRootFolder()`, `Folder.GetClipList()`, `Folder.GetSubFolderList()` | Henter mappe- og klipp-struktur i Media Pool |
| `import_media` | `MediaPool.ImportMedia([paths])` | Importerer mediafiler til Media Pool |
| `create_timeline` | `MediaPool.CreateEmptyTimeline(name)` | Oppretter en tom timeline |
| `get_current_timeline_info` | `Project.GetCurrentTimeline()`, `Timeline.GetName()` m.fl. | Henter detaljinfo om aktiv timeline |
| `get_timeline_items` | `Timeline.GetItemListInTrack(trackType, index)` | Lister klipp på en spesifikk spor |
| `append_to_timeline` | `MediaPool.AppendToTimeline([clips])` | Legger til klipp fra Media Pool i aktiv timeline |
| `add_marker` | `Timeline.AddMarker(frameId, color, name, note, duration, customData)` | Legger til marker på aktiv timeline |
| `get_markers` | `Timeline.GetMarkers()` | Henter alle markers fra aktiv timeline |
| `parse_and_preview_markers` | `parse_marker_list()` (intern), `Timeline.GetSetting("timelineFrameRate")` | Parser fritekst til strukturerte markers, pusher til panel |
| `set_markers_from_list` | `Timeline.AddMarker()` | Setter godkjent marker-liste på aktiv timeline |
| `set_current_timecode` | `Timeline.SetCurrentTimecode(timecode)` | Flytter playhead til timecode |
| `get_current_timecode` | `Timeline.GetCurrentTimecode()` | Leser nåværende playhead-timecode |
| `get_timeline_item_properties` | `TimelineItem.GetProperty()` | Henter alle properties for et timeline-klipp |
| `set_timeline_item_property` | `TimelineItem.SetProperty(key, value)` | Setter property på et timeline-klipp |
| `get_node_graph` | `TimelineItem.GetNodeGraph()` | Henter fargekorreksjons-nodegraf |
| `set_lut` | `Graph.SetLUT(nodeIndex, lutPath)` | Setter LUT på en node |
| `set_cdl` | `TimelineItem.SetCDL([CDL map])` | Setter CDL-verdier på en node |
| `get_render_formats` | `Project.GetRenderFormats()`, `Project.GetRenderCodecs()` | Henter tilgjengelige renderformater og kodeker |
| `get_render_settings` | `Project.GetCurrentRenderFormatAndCodec()`, `Project.GetCurrentRenderMode()`, `Project.GetRenderJobList()`, `Project.GetRenderPresetList()`, `Project.IsRenderingInProgress()` | Henter gjeldende render-innstillinger |
| `set_render_settings` | `Project.SetCurrentRenderFormatAndCodec()`, `Project.SetRenderSettings()` | Konfigurerer render-innstillinger |
| `add_render_job` | `Project.AddRenderJob()` | Legger til en render-jobb i køen |
| `start_rendering` | `Project.StartRendering()` | Starter rendering av jobbkøen |
| `get_render_status` | `Project.GetRenderJobStatus(jobId)` | Sjekker status på render-jobb |
| `stop_rendering` | `Project.StopRendering()` | Stopper pågående rendering |
| `create_magic_mask` | `TimelineItem.CreateMagicMask(mode)` | Oppretter AI-drevet Magic Mask |
| `regenerate_magic_mask` | `TimelineItem.RegenerateMagicMask()` | Regenererer eksisterende Magic Mask |
| `smart_reframe` | `TimelineItem.SmartReframe()` | AI-basert reframing |
| `stabilize` | `TimelineItem.Stabilize()` | Stabiliserer klipp med Neural Engine |
| `detect_scene_cuts` | `Timeline.DetectSceneCuts()` | Detekterer scene-kutt med AI |
| `create_subtitles_from_audio` | `Timeline.CreateSubtitlesFromAudio({autoCaptionSettings})` | Genererer undertekster fra lyd via Resolve AI |
| `get_timeline_subtitle_tracks` | `Timeline.GetTrackCount("subtitle")`, `Timeline.GetTrackName()` | Lister subtitle-spor på aktiv timeline |
| `transcribe_timeline_audio` | `Project.AddRenderJob()`, `Project.StartRendering()` + mlx-whisper | Transkriberer timeline-lyd lokalt |
| `write_subtitles_to_resolve` | `MediaPool.ImportMedia()`, `Timeline.GetItemListInTrack("subtitle")` m.fl. | Skriver godkjent transkripsjon til Resolve |
| `list_project_templates` | `_list_templates()` (intern, leser `templates/configs/`) | Lister tilgjengelige prosjektmaler |
| `create_project_from_template` | `ProjectManager.CreateProject()`, `MediaPool.CreateEmptyTimeline()`, `MediaPool.AddSubFolder()` | Oppretter prosjekt fra mal |
| `sync_finder_folder_to_media_pool` | `MediaPool.AddSubFolder()`, `MediaPool.SetCurrentFolder()`, `MediaPool.ImportMedia()` | Speiler Finder-mappestruktur som bins i Media Pool |
| `auto_color_clips` | `MediaPoolItem.GetClipProperty()`, `MediaPoolItem.SetClipColor()`, `MediaPoolItem.GetClipColor()` | Foreslår og setter klippfarger basert på filnavn/metadata |
| `get_fusion_comp_list` | `TimelineItem.GetFusionCompCount()`, `TimelineItem.GetFusionCompNameList()` | Lister Fusion-komposisjoner på et klipp |
| `add_fusion_comp` | `TimelineItem.AddFusionComp()` | Legger til ny Fusion-komposisjon |
| `import_fusion_comp` | `TimelineItem.ImportFusionComp(path)` | Importerer Fusion-komposisjon fra fil |
| `export_fusion_comp` | `TimelineItem.ExportFusionComp(path, compIndex)` | Eksporterer Fusion-komposisjon til fil |
| `load_fusion_comp` | `TimelineItem.LoadFusionCompByName(name)` | Laster navngitt Fusion-komposisjon |
| `delete_fusion_comp` | `TimelineItem.DeleteFusionCompByName(name)` | Sletter navngitt Fusion-komposisjon |
| `rename_fusion_comp` | `TimelineItem.RenameFusionCompByName(old, new)` | Gir nytt navn til Fusion-komposisjon |
| `create_fusion_clip` | `Timeline.CreateFusionClip([timelineItems])` | Oppretter Fusion-klipp fra timeline-elementer |
| `insert_fusion_generator` | `Timeline.InsertFusionGeneratorIntoTimeline(name)` | Setter inn Fusion-generator i timeline |
| `insert_fusion_composition` | `Timeline.InsertFusionCompositionIntoTimeline()` | Setter inn blank Fusion-komposisjon |
| `insert_fusion_title` | `Timeline.InsertFusionTitleIntoTimeline(name)` | Setter inn Fusion-tittel |
| `export_timeline` | `Timeline.Export(fileName, exportType, exportSubtype)` | Eksporterer timeline (AAF, EDL, FCPXML, OTIO, ALE osv.) |
| `get_current_thumbnail` | `Timeline.GetCurrentClipThumbnailImage()` | Henter thumbnail fra Color-siden |
| `export_current_frame` | `Project.ExportCurrentFrameAsStill(filePath)` | Eksporterer nåværende frame som stillbilde |
| `screenshot` | macOS `screencapture` (ikke Resolve API) | Tar skjermbilde av Resolve-vinduet |
| `get_voice_isolation_state` | `Timeline.GetVoiceIsolationState(trackIndex)` | Henter Voice Isolation-status for lydspor |
| `set_voice_isolation_state` | `Timeline.SetVoiceIsolationState(trackIndex, {state})` | Aktiverer/deaktiverer Voice Isolation |
| `execute_resolve_code` | Vilkårlig Python i Resolve-miljøet | Kjører Python-kode direkte i Resolve |
| `transcribe_audio` | mlx-whisper lokalt | Transkriberer lydfil lokalt, lagrer SRT |
| `transcribe_and_add_subtitles` | mlx-whisper + `Timeline.AddMarker()` | Transkriberer og legger til marker-undertekster |
| `export_srt` | mlx-whisper lokalt | Transkriberer og lagrer SRT-fil |
| `list_whisper_models` | (intern konstant) | Lister tilgjengelige mlx-whisper modeller |

**Totalt: 56 implementerte tools**

---

## NYE MULIGHETER — ETTER RESOLVE API-KLASSE

### Resolve (root)

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `Fusion()` | Returnerer Fusion-objektet — startpunkt for Fusion-scripting | LAV | Fusion API er svært dypt; dekkes delvis av `execute_resolve_code` |
| `GetProductName()` | Returnerer produktnavn ("DaVinci Resolve Studio") | LAV | Informasjons-tool |
| `GetVersion()` | Returnerer versjonsfelt som liste `[major, minor, patch, build, suffix]` | LAV | Dekkes delvis av `get_project_info` via `GetVersionString()` |
| `LoadLayoutPreset(presetName)` | Laster UI-layout fra lagret preset | MEDIUM | Nyttig for å bytte arbeidsflyt-oppsett |
| `UpdateLayoutPreset(presetName)` | Overskriver eksisterende layout-preset med gjeldende UI | MEDIUM | Lagre gjeldende layout |
| `ExportLayoutPreset(presetName, filePath)` | Eksporterer layout-preset til fil | LAV | Backup-formål |
| `DeleteLayoutPreset(presetName)` | Sletter navngitt layout-preset | LAV | Ryddeverktøy |
| `SaveLayoutPreset(presetName)` | Lagrer gjeldende UI-layout som ny preset | MEDIUM | Komplementær til `LoadLayoutPreset` |
| `ImportLayoutPreset(filePath, presetName)` | Importerer layout-preset fra fil | LAV | Del av layout-preset-workflow |
| `Quit()` | Avslutter Resolve-applikasjonen | LAV | Farlig — bruk med forsiktighet |
| `ImportRenderPreset(presetPath)` | Importerer render-preset fra fil | MEDIUM | Gjenbruk av preset på tvers av maskiner |
| `ExportRenderPreset(presetName, exportPath)` | Eksporterer render-preset til fil | MEDIUM | Backup/deling av render-presets |
| `ImportBurnInPreset(presetPath)` | Importerer data burn-in preset fra fil | LAV | Nisje-funksjon |
| `ExportBurnInPreset(presetName, exportPath)` | Eksporterer burn-in preset til fil | LAV | Nisje-funksjon |
| `GetKeyframeMode()` | Returnerer nåværende keyframe-modus (int) | LAV | Informasjons-query |
| `SetKeyframeMode(keyframeMode)` | Setter keyframe-modus (ALL=0, COLOR=1, SIZING=2) | MEDIUM | Relevant for grading-workflow |
| `GetFairlightPresets()` | Returnerer liste over Fairlight-presets | MEDIUM | Nyttig for lyd-workflow |
| `DisableBackgroundTasksForCurrentResolveSession()` | **NY i v21** — Deaktiverer alle bakgrunnsoppgaver for gjeldende session | HØY | Kritisk for scripting-ytelse; hindrer AI-analyse som forstyrrer |

---

### ProjectManager

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `ArchiveProject(projectName, filePath, ...)` | Arkiverer prosjekt til fil med konfiguerbare alternativer | HØY | Svært nyttig for backup-workflow |
| `DeleteProject(projectName)` | Sletter prosjekt i gjeldende mappe | MEDIUM | Bruk med bekreftelse |
| `LoadProject(projectName)` | Laster prosjekt etter navn | HØY | Grunnleggende prosjektstyring |
| `GetCurrentProject()` | Returnerer aktivt prosjektobjekt | — | Brukes internt, ikke nyttig som MCP-tool alene |
| `SaveProject()` | Lagrer gjeldende prosjekt | HØY | Mangler! Viktig safety-tool |
| `CloseProject(project)` | Lukker prosjekt uten lagring | MEDIUM | Del av prosjektstyring |
| `CreateFolder(folderName)` | Oppretter mappe i prosjektdatabasen | MEDIUM | Organisering av prosjekter |
| `DeleteFolder(folderName)` | Sletter mappe i prosjektdatabasen | LAV | Ryddeverktøy |
| `GetProjectListInCurrentFolder()` | Lister prosjekter i gjeldende mappe | HØY | Navigasjon og oversikt |
| `GetFolderListInCurrentFolder()` | Lister mapper i gjeldende mappe | MEDIUM | Navigasjon i prosjektdatabase |
| `GotoRootFolder()` | Navigerer til rotmappe i databasen | MEDIUM | Navigasjon |
| `GotoParentFolder()` | Navigerer til foreldremappen | MEDIUM | Navigasjon |
| `GetCurrentFolder()` | Returnerer gjeldende mappenavn | MEDIUM | Navigasjon |
| `OpenFolder(folderName)` | Åpner navngitt mappe | MEDIUM | Navigasjon |
| `ImportProject(filePath, projectName)` | Importerer prosjekt fra fil | MEDIUM | Allerede delvis dekket via `create_project_from_template` med .drp |
| `ExportProject(projectName, filePath, withStillsAndLUTs)` | Eksporterer prosjekt til fil | HØY | Backup og deling |
| `RestoreProject(filePath, projectName)` | Gjenoppretter prosjekt fra backup | MEDIUM | Disaster recovery |
| `GetCurrentDatabase()` | Returnerer info om aktiv database | MEDIUM | Nyttig for multi-database-workflow |
| `GetDatabaseList()` | Lister alle konfigurerte databaser | MEDIUM | Database-oversikt |
| `SetCurrentDatabase({dbInfo})` | Bytter aktiv database | MEDIUM | Multi-database-workflow |
| `CreateCloudProject({cloudSettings})` | **Ny API** — Oppretter skybasert prosjekt | LAV | Krever cloud-oppsett |
| `LoadCloudProject({cloudSettings})` | Laster skybasert prosjekt | LAV | Krever cloud-oppsett |
| `ImportCloudProject(filePath, {cloudSettings})` | Importerer skybasert prosjekt | LAV | Krever cloud-oppsett |
| `RestoreCloudProject(folderPath, {cloudSettings})` | Gjenoppretter skybasert prosjekt | LAV | Krever cloud-oppsett |

---

### Project

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetTimelineByIndex(idx)` | Henter timeline-objekt via indeks | HØY | Grunnleggende for multi-timeline-workflow |
| `SetCurrentTimeline(timeline)` | Setter aktiv timeline | HØY | Mangler! Grunnleggende navigasjon |
| `GetGallery()` | Returnerer Gallery-objektet | MEDIUM | Startpunkt for grade-album-workflow |
| `SetName(projectName)` | Endrer prosjektnavn | MEDIUM | Grunnleggende prosjektstyring |
| `GetPresetList()` | Returnerer liste over project presets | MEDIUM | Preset-oversikt |
| `SetPreset(presetName)` | Setter project preset | MEDIUM | Preset-styring |
| `DeleteRenderJob(jobId)` | Sletter render-jobb fra kø | MEDIUM | Mangler — trengs for opprydding |
| `DeleteAllRenderJobs()` | Sletter alle render-jobber | MEDIUM | Bulk-opprydding |
| `LoadRenderPreset(presetName)` | Laster render-preset (brukes internt) | — | Allerede brukt internt |
| `SaveAsNewRenderPreset(presetName)` | Lagrer gjeldende innstillinger som ny render-preset | HØY | Svært nyttig for gjenbruk |
| `DeleteRenderPreset(presetName)` | Sletter render-preset | LAV | Ryddeverktøy |
| `SetCurrentRenderMode(renderMode)` | Setter render-modus (0=individual, 1=single clip) | MEDIUM | Render-konfigurasjon |
| `GetRenderResolutions(format, codec)` | Returnerer tilgjengelige oppløsninger for format/kodek | MEDIUM | Render-konfigurasjon |
| `RefreshLUTList()` | Oppdaterer LUT-listen fra disk | MEDIUM | Nødvendig etter LUT-installasjon |
| `GetUniqueId()` | Returnerer unik prosjekt-ID | LAV | Identifikasjon |
| `InsertAudioToCurrentTrackAtPlayhead(mediaPath, startOffset, duration)` | Setter inn lydfil på aktivt lydspor ved playhead | HØY | Fairlight-workflow |
| `LoadBurnInPreset(presetName)` | Laster data burn-in preset for prosjekt | LAV | Nisje |
| `GetColorGroupsList()` | Returnerer liste over alle ColorGroup-objekter | MEDIUM | Color grouping-workflow |
| `AddColorGroup(groupName)` | Oppretter ny ColorGroup | MEDIUM | Grading-workflow |
| `DeleteColorGroup(colorGroup)` | Sletter ColorGroup | MEDIUM | Grading-workflow |
| `ApplyFairlightPresetToCurrentTimeline(name)` | **NY i v21** — Bruker Fairlight-preset på gjeldende timeline | HØY | Lyd-workflow |
| `ResetIntellisearchAnalysis()` | **NY i v21** — Sletter IntelliSearch-analysedata | MEDIUM | IntelliSearch-vedlikehold |
| `GenerateSpeech({settings}, timecode)` | **NY i v21** — Genererer AI-talesyntese og legger til i timeline | HØY | Kreativ produksjon, voiceover-automatisering |
| `GetQuickExportRenderPresets()` | Returnerer Quick Export render presets | MEDIUM | Rask eksport-workflow |
| `RenderWithQuickExport(preset_name, {params})` | Starter Quick Export render | HØY | Rask eksport uten full render-konfigurasjon |

---

### MediaStorage

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetMountedVolumeList()` | Lister monterte volumer i Resolve Media Storage | MEDIUM | Filsystem-navigasjon |
| `GetSubFolderList(folderPath)` | Lister undermapper fra en gitt sti | MEDIUM | Filsystem-navigasjon |
| `GetFileList(folderPath)` | Lister mediafiler i en gitt mappe | MEDIUM | Alternativ til OS-basert fillesing |
| `RevealInStorage(path)` | Ekspanderer og viser sti i Resolve Media Storage | MEDIUM | UI-navigasjon |
| `AddItemListToMediaPool(items)` | Legger til filer/mapper fra Media Storage i Media Pool | MEDIUM | Alternativ til `ImportMedia` |
| `AddItemListToMediaPool([{itemInfo}])` | Legger til med start/end-frame | MEDIUM | Sub-clip import |
| `AddClipMattesToMediaPool(item, [paths], stereoEye)` | Legger til matte-filer for et klipp | LAV | Compositing-workflow |
| `AddTimelineMattesToMediaPool([paths])` | Legger til timeline mattes i Media Pool | LAV | Compositing-workflow |

---

### MediaPool

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `RefreshFolders()` | Oppdaterer mapper i collaboration-modus | MEDIUM | Samarbeid |
| `CreateTimelineFromClips(name, clips)` | Oppretter ny timeline direkte fra klipp | HØY | Raskere enn create+append |
| `ImportTimelineFromFile(filePath, {options})` | Importerer timeline fra AAF/EDL/XML/FCPXML/DRT/ADL/OTIO | HØY | Workflow-integrasjon |
| `DeleteTimelines([timelines])` | Sletter spesifiserte timelines | MEDIUM | Opprydding |
| `SetCurrentFolder(folder)` | Setter aktiv bin i Media Pool | HØY | Mangler — trengs for bin-navigasjon |
| `DeleteClips([clips])` | Sletter klipp fra Media Pool | MEDIUM | Opprydding |
| `ImportFolderFromFile(filePath, sourceClipsPath)` | Importerer mappe fra DRB-fil | LAV | Nisje |
| `DeleteFolders([subfolders])` | Sletter spesifiserte undermapper | MEDIUM | Opprydding |
| `MoveClips([clips], targetFolder)` | Flytter klipp til annen bin | HØY | Media Pool-organisering |
| `MoveFolders([folders], targetFolder)` | Flytter mapper til annen mappe | MEDIUM | Media Pool-organisering |
| `GetClipMatteList(MediaPoolItem)` | Henter liste over matte-filer for et klipp | LAV | Compositing-info |
| `GetTimelineMatteList(Folder)` | Henter timeline mattes i mappe | LAV | Compositing-info |
| `DeleteClipMattes(MediaPoolItem, [paths])` | Sletter matte-filer | LAV | Opprydding |
| `RelinkClips([MediaPoolItems], folderPath)` | Relinkerer offline klipp til ny mappe | HØY | Kritisk for offline-media-håndtering |
| `UnlinkClips([MediaPoolItems])` | Fjerner link mellom klipp og mediafil | MEDIUM | Offline-workflow |
| `ExportMetadata(fileName, [clips])` | Eksporterer metadata for klipp til CSV | MEDIUM | Metadata-workflow |
| `GetUniqueId()` | Returnerer unik Media Pool-ID | LAV | Identifikasjon |
| `CreateStereoClip(left, right)` | Oppretter stereoskopisk 3D-klipp | LAV | Krever Studio |
| `AutoSyncAudio([items], {settings})` | Synkroniserer lyd automatisk (waveform eller timecode) | HØY | Svært nyttig for multi-cam/dobbel-lyd-workflow |
| `GetSelectedClips()` | Returnerer valgte klipp i Media Pool | MEDIUM | UI-interaksjon |
| `SetSelectedClip(MediaPoolItem)` | Velger et spesifikt klipp i Media Pool | MEDIUM | UI-interaksjon |

---

### Folder

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetIsFolderStale()` | Returnerer True hvis mappe er utdatert (collaboration) | LAV | Collaboration-modus |
| `GetUniqueId()` | Returnerer unik mappe-ID | LAV | Identifikasjon |
| `Export(filePath)` | Eksporterer mappe som DRB-fil | MEDIUM | Backup av bin-innhold |
| `TranscribeAudio(useSpeakerDetection)` | **NY i v21** — Transkriberer lyd for alle klipp i mappen | HØY | Batch-transkripsjon med speaker detection |
| `ClearTranscription()` | **NY i v21** — Sletter transkripsjon for alle klipp i mappen | MEDIUM | Vedlikehold |
| `PerformAudioClassification()` | **NY i v21** — Klassifiserer lyd i kategorier for alle klipp | HØY | Automatisk organisering av lydmateriale |
| `ClearAudioClassification()` | **NY i v21** — Sletter lydklassifisering for alle klipp | MEDIUM | Vedlikehold |
| `RemoveMotionBlur({deblurOption})` | **NY i v21** — Fjerner bevegelsesblur fra klipp i mappen | HØY | AI-bildekvalitet; batch-prosessering |
| `AnalyzeForIntellisearch(identifyFaces, isBetterMode)` | **NY i v21** — Analyserer klipp for IntelliSearch (ansiktsgjenkjenning m.m.) | HØY | Intelligent søk i media |
| `AnalyzeForSlate(markerColor)` | **NY i v21** — Analyserer klapre/slate for alle klipp i mappen | HØY | Automatisk klipp-identifikasjon |

---

### MediaPoolItem

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `SetName(name)` | Endrer klippnavn | MEDIUM | Grunnleggende metadata |
| `GetMetadata(metadataType)` | Henter metadata (eller alle hvis uten argument) | HØY | Metadata-lesing |
| `SetMetadata(type, value)` | Setter spesifikk metadata-verdi | HØY | Metadata-skriving |
| `SetMetadata({metadata})` | Setter flere metadata-verdier på én gang | HØY | Batch metadata-skriving |
| `GetThirdPartyMetadata(metadataType)` | Henter tredjepartmetadata | MEDIUM | Integrasjon med kameraer/produksjonssystemer |
| `SetThirdPartyMetadata(type, value)` | Setter tredjepartmetadata | MEDIUM | Integrasjon |
| `GetMediaId()` | Returnerer unik media-ID | LAV | Identifikasjon |
| `AddMarker(frameId, color, name, note, duration, customData)` | Legger til marker på klipp (i Media Pool, ikke timeline) | HØY | Klipp-annotasjon i Media Pool |
| `GetMarkers()` | Henter alle markers på klippet | MEDIUM | Klipp-annotasjon |
| `GetMarkerByCustomData(customData)` | Finn marker via custom data | LAV | Scripting-marker-lookup |
| `UpdateMarkerCustomData(frameId, customData)` | Oppdaterer custom data på marker | LAV | Scripting-marker-vedlikehold |
| `GetMarkerCustomData(frameId)` | Henter custom data fra marker | LAV | Scripting-marker-lesing |
| `DeleteMarkersByColor(color)` | Sletter markers av angitt farge | MEDIUM | Bulk-opprydding |
| `DeleteMarkerAtFrame(frameNum)` | Sletter marker ved angitt frame | MEDIUM | Presis sletting |
| `DeleteMarkerByCustomData(customData)` | Sletter marker via custom data | LAV | Scripting-marker-sletting |
| `AddFlag(color)` | Legger til flagg på klipp | MEDIUM | Klipp-organisering |
| `GetFlagList()` | Henter liste over flaggfarger | MEDIUM | Klipp-status |
| `ClearFlags(color)` | Fjerner flagg (eller alle med "All") | MEDIUM | Klipp-organisering |
| `SetClipProperty(propertyName, propertyValue)` | Setter klipp-property (format, retime osv.) | MEDIUM | Klipp-konfigurasjon |
| `LinkProxyMedia(proxyMediaFilePath)` | Linker proxy-media til klipp | HØY | Proxy-workflow |
| `LinkFullResolutionMedia(fullResMediaPath)` | Linker full-res media til proxy | HØY | Proxy-workflow |
| `UnlinkProxyMedia()` | Fjerner proxy-link | MEDIUM | Proxy-workflow |
| `ReplaceClip(filePath)` | Erstatter klippets mediafil | HØY | Offline/online-workflow |
| `ReplaceClipPreserveSubClip(filePath)` | Erstatter mediafil, bevarer sub-clip-grenser | MEDIUM | Avansert offline/online |
| `GetUniqueId()` | Returnerer unik klipp-ID | LAV | Identifikasjon |
| `TranscribeAudio(useSpeakerDetection)` | **NY i v21** — Transkriberer lyd for dette klippet (Resolve AI) | HØY | IntelliSearch-integrasjon |
| `ClearTranscription()` | **NY i v21** — Sletter transkripsjon | MEDIUM | Vedlikehold |
| `PerformAudioClassification()` | **NY i v21** — Klassifiserer lyden i klippet | HØY | Automatisk lydkategorisering |
| `ClearAudioClassification()` | **NY i v21** — Sletter lydklassifisering | MEDIUM | Vedlikehold |
| `GetAudioMapping()` | Returnerer JSON-streng med lydmapping-info | MEDIUM | Avansert lydkonfigurasjon |
| `GetMarkInOut()` | Henter inn/ut-markerte punkter | MEDIUM | Klipp-redigering |
| `SetMarkInOut(in, out, type)` | Setter inn/ut-punkter | MEDIUM | Klipp-redigering |
| `ClearMarkInOut(type)` | Fjerner inn/ut-markering | MEDIUM | Klipp-redigering |
| `MonitorGrowingFile()` | Overvåker en fil som vokser (live-opptak) | MEDIUM | Live-opptak-workflow |
| `RemoveMotionBlur({deblurOption})` | **NY i v21** — Fjerner bevegelsesblur fra klippet | HØY | AI-bildekvalitet |
| `AnalyzeForIntellisearch(identifyFaces, isBetterMode)` | **NY i v21** — Analyserer klipp for IntelliSearch | HØY | Intelligent søk |
| `AnalyzeForSlate(markerColor)` | **NY i v21** — Analyserer klapre/slate for dette klippet | HØY | Automatisk klipp-ID |

---

### Timeline

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `SetName(timelineName)` | Endrer timeline-navn | MEDIUM | Grunnleggende |
| `GetStartFrame()` | Returnerer startframe-nummer | — | Brukes internt |
| `GetEndFrame()` | Returnerer sluttframe-nummer | MEDIUM | Nyttig for beregninger |
| `SetStartTimecode(timecode)` | Setter starttimecode for timeline | MEDIUM | Timeline-konfigurasjon |
| `GetStartTimecode()` | Henter starttimecode | MEDIUM | Timeline-info |
| `GetTrackCount(trackType)` | Returnerer antall spor | — | Brukes internt |
| `AddTrack(trackType, subTrackType)` | Legger til nytt spor | HØY | Timeline-struktur |
| `DeleteTrack(trackType, trackIndex)` | Sletter spor | MEDIUM | Timeline-struktur |
| `GetTrackSubType(trackType, trackIndex)` | Returnerer lydspor-format | MEDIUM | Lydspor-info |
| `SetTrackEnable(trackType, trackIndex, Bool)` | Aktiverer/deaktiverer spor | MEDIUM | Redigering |
| `GetIsTrackEnabled(trackType, trackIndex)` | Sjekker om spor er aktivert | MEDIUM | Sporstatus |
| `SetTrackLock(trackType, trackIndex, Bool)` | Låser/låser opp spor | MEDIUM | Beskyttelse mot utilsiktede endringer |
| `GetIsTrackLocked(trackType, trackIndex)` | Sjekker om spor er låst | MEDIUM | Sporstatus |
| `DeleteClips([timelineItems], ripple)` | Sletter klipp fra timeline | HØY | Redigering |
| `SetClipsLinked([timelineItems], Bool)` | Linker/fjerner link mellom klipp | MEDIUM | Synkronisert redigering |
| `GetMarkerByCustomData(customData)` | Finn timeline-marker via custom data | LAV | Scripting-marker |
| `UpdateMarkerCustomData(frameId, customData)` | Oppdaterer custom data på timeline-marker | LAV | Scripting-marker |
| `GetMarkerCustomData(frameId)` | Henter custom data fra timeline-marker | LAV | Scripting-marker |
| `DeleteMarkersByColor(color)` | Sletter alle markers av angitt farge fra timeline | MEDIUM | Bulk-opprydding |
| `DeleteMarkerAtFrame(frameNum)` | Sletter timeline-marker ved frame | MEDIUM | Presis sletting |
| `DeleteMarkerByCustomData(customData)` | Sletter timeline-marker via custom data | LAV | Scripting |
| `GetCurrentVideoItem()` | Returnerer gjeldende video-klipp | MEDIUM | Navigasjon |
| `GetTrackName(trackType, trackIndex)` | Henter spornavnet | MEDIUM | Sporinformasjon |
| `SetTrackName(trackType, trackIndex, name)` | Setter spornavn | MEDIUM | Spororganisering |
| `DuplicateTimeline(timelineName)` | Dupliserer timeline | HØY | Svært nyttig for versjonering |
| `CreateCompoundClip([items], {clipInfo})` | Oppretter compound clip | MEDIUM | Compositing-workflow |
| `ImportIntoTimeline(filePath, {options})` | Importerer fra AAF-fil til aktiv timeline | MEDIUM | AAF-workflow |
| `GetSetting(settingName)` | Henter timeline-innstilling | — | Brukes internt |
| `SetSetting(settingName, settingValue)` | Setter timeline-innstilling | MEDIUM | Timeline-konfigurasjon |
| `InsertGeneratorIntoTimeline(generatorName)` | Setter inn standard generator | MEDIUM | Mangler for standard-generatorer |
| `InsertOFXGeneratorIntoTimeline(generatorName)` | Setter inn OFX-generator | MEDIUM | OFX-workflow |
| `InsertTitleIntoTimeline(titleName)` | Setter inn standard tittel | MEDIUM | Mangler for standard-titler |
| `GrabStill()` | Tar still fra gjeldende videoklipp | HØY | Gallery-workflow |
| `GrabAllStills(stillFrameSource)` | Tar stills fra alle klipp i timeline | MEDIUM | Batch gallery-workflow |
| `ConvertTimelineToStereo()` | Konverterer timeline til stereo | LAV | Stereoskopisk workflow |
| `GetNodeGraph()` | Returnerer timeline-nodegraf | MEDIUM | Timeline-nivå fargekorrektur |
| `AnalyzeDolbyVision([items], analysisType)` | Analyserer Dolby Vision på klipp | MEDIUM | HDR-workflow |
| `GetMediaPoolItem()` | Returnerer Media Pool-elementet for timeline | LAV | Kryss-referanse |
| `GetMarkInOut()` | Henter inn/ut-punkter for timeline | MEDIUM | Redigering |
| `SetMarkInOut(in, out, type)` | Setter inn/ut-punkter | MEDIUM | Redigering |
| `ClearMarkInOut(type)` | Fjerner inn/ut-markering | MEDIUM | Redigering |
| `GetUniqueId()` | Returnerer unik timeline-ID | LAV | Identifikasjon |

---

### TimelineItem

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `SetName(name)` | Endrer klippnavn i timeline | MEDIUM | Grunnleggende |
| `GetDuration(subframe_precision)` | Returnerer varigheten | — | Brukes internt |
| `GetEnd(subframe_precision)` | Returnerer sluttposisjon på timeline | MEDIUM | Posisjonering |
| `GetSourceEndFrame()` | Returnerer slutt-frame i source-klippet | MEDIUM | Sub-clip-info |
| `GetSourceEndTime()` | Returnerer sluttid i source-klippet | MEDIUM | Sub-clip-info |
| `GetFusionCompByIndex(compIndex)` | Returnerer Fusion comp-objekt via indeks | LAV | Intern bruk |
| `GetFusionCompByName(compName)` | Returnerer Fusion comp-objekt via navn | LAV | Intern bruk |
| `GetLeftOffset(subframe_precision)` | Maks utvidelse til venstre i frames | MEDIUM | Trimming-info |
| `GetRightOffset(subframe_precision)` | Maks utvidelse til høyre i frames | MEDIUM | Trimming-info |
| `GetStart(subframe_precision)` | Startposisjon på timeline | MEDIUM | Posisjonering |
| `GetSourceStartFrame()` | Startframe i source-klippet | MEDIUM | Sub-clip-info |
| `GetSourceStartTime()` | Starttid i source-klippet | MEDIUM | Sub-clip-info |
| `GetMarkerByCustomData(customData)` | Finn klipp-marker via custom data | LAV | Scripting |
| `UpdateMarkerCustomData(frameId, customData)` | Oppdaterer custom data på klipp-marker | LAV | Scripting |
| `GetMarkerCustomData(frameId)` | Henter custom data fra klipp-marker | LAV | Scripting |
| `DeleteMarkersByColor(color)` | Sletter markers av angitt farge fra klipp | MEDIUM | Klipp-marker-opprydding |
| `DeleteMarkerAtFrame(frameNum)` | Sletter klipp-marker ved frame | MEDIUM | Klipp-marker-sletting |
| `DeleteMarkerByCustomData(customData)` | Sletter klipp-marker via custom data | LAV | Scripting |
| `AddFlag(color)` | Legger til flagg på timeline-klipp | MEDIUM | Klipp-status |
| `GetFlagList()` | Henter flaggfarger for timeline-klipp | MEDIUM | Klipp-status |
| `ClearFlags(color)` | Fjerner flagg | MEDIUM | Klipp-status |
| `GetClipColor()` | Henter klippfarge | — | Brukes internt |
| `ClearClipColor()` | Fjerner klippfarge | MEDIUM | Farge-opprydding |
| `AddVersion(versionName, versionType)` | Legger til ny fargeversjon (lokal/remote) | HØY | Versjonert grading-workflow |
| `GetCurrentVersion()` | Returnerer gjeldende fargeversjon | MEDIUM | Grade-info |
| `DeleteVersionByName(versionName, versionType)` | Sletter fargeversjon | MEDIUM | Grade-vedlikehold |
| `LoadVersionByName(versionName, versionType)` | Laster navngitt fargeversjon | HØY | Grade-workflow |
| `RenameVersionByName(oldName, newName, type)` | Gir nytt navn til fargeversjon | MEDIUM | Grade-organisering |
| `GetVersionNameList(versionType)` | Lister alle fargeversjonsnavn | MEDIUM | Grade-oversikt |
| `GetStereoConvergenceValues()` | Returnerer stereoskopiske konvergerings-keyframes | LAV | Stereo-workflow |
| `GetStereoLeftFloatingWindowParams()` | Returnerer venstre øye floating window-params | LAV | Stereo-workflow |
| `GetStereoRightFloatingWindowParams()` | Returnerer høyre øye floating window-params | LAV | Stereo-workflow |
| `AddTake(mediaPoolItem, startFrame, endFrame)` | Legger til take i take-selector | MEDIUM | Multi-take-workflow |
| `GetSelectedTakeIndex()` | Returnerer valgt take-indeks | MEDIUM | Take-info |
| `GetTakesCount()` | Returnerer antall takes | MEDIUM | Take-info |
| `GetTakeByIndex(idx)` | Returnerer take-info via indeks | MEDIUM | Take-info |
| `DeleteTakeByIndex(idx)` | Sletter take | MEDIUM | Take-vedlikehold |
| `SelectTakeByIndex(idx)` | Velger take | MEDIUM | Take-workflow |
| `FinalizeTake()` | Sluttfører take-valg | MEDIUM | Take-workflow |
| `CopyGrades([tgtTimelineItems])` | Kopierer grade til andre klipp | HØY | Batch-grading |
| `SetClipEnabled(Bool)` | Aktiverer/deaktiverer klipp | MEDIUM | Redigering |
| `GetClipEnabled()` | Sjekker om klipp er aktivert | MEDIUM | Klipp-status |
| `UpdateSidecar()` | Oppdaterer sidecar-fil (BRAW/R3D) | MEDIUM | RAW-workflow |
| `LoadBurnInPreset(presetName)` | Laster burn-in preset for klipp | LAV | Nisje |
| `ExportLUT(exportType, path)` | Eksporterer LUT fra klippets grade | HØY | Grading-workflow |
| `GetLinkedItems()` | Returnerer liste over lenkede klipp | MEDIUM | Synkronisert redigering |
| `GetTrackTypeAndIndex()` | Returnerer klippets sportype og indeks | MEDIUM | Klipp-lokalisering |
| `GetSourceAudioChannelMapping()` | Returnerer JSON med lydkanal-mapping | MEDIUM | Lydkonfigurasjon |
| `GetIsColorOutputCacheEnabled()` | Sjekker om farge-cache er aktivert | LAV | Cache-management |
| `GetIsFusionOutputCacheEnabled()` | Sjekker om Fusion-cache er aktivert | LAV | Cache-management |
| `SetColorOutputCache(cache_value)` | Setter farge-cache (aktivert/deaktivert) | MEDIUM | Cache-management |
| `SetFusionOutputCache(cache_value)` | Setter Fusion-cache (auto/aktivert/deaktivert) | MEDIUM | Cache-management |
| `GetVoiceIsolationState()` | Henter Voice Isolation-status for klipp | MEDIUM | Lydkvalitet per klipp |
| `SetVoiceIsolationState({state})` | Setter Voice Isolation for klipp | MEDIUM | Lydkvalitet per klipp |
| `AssignToColorGroup(ColorGroup)` | Tilordner klipp til ColorGroup | MEDIUM | Grading-workflow |
| `RemoveFromColorGroup()` | Fjerner klipp fra ColorGroup | MEDIUM | Grading-workflow |
| `GetColorGroup()` | Returnerer klippets ColorGroup | MEDIUM | Grading-info |
| `ResetAllNodeColors()` | **NY i v21** — Nullstiller nodefarger for alle noder i aktiv versjon | MEDIUM | Grade-vedlikehold |

---

### Gallery

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetAlbumName(galleryStillAlbum)` | Henter albumnavn | MEDIUM | Gallery-info |
| `SetAlbumName(galleryStillAlbum, albumName)` | Endrer albumnavn | MEDIUM | Gallery-organisering |
| `GetCurrentStillAlbum()` | Returnerer aktivt still-album | MEDIUM | Gallery-navigasjon |
| `SetCurrentStillAlbum(galleryStillAlbum)` | Setter aktivt still-album | MEDIUM | Gallery-navigasjon |
| `GetGalleryStillAlbums()` | Returnerer alle still-album | HØY | Gallery-oversikt |
| `GetGalleryPowerGradeAlbums()` | **NY i v21** — Returnerer alle PowerGrade-album | HØY | PowerGrade-workflow |
| `CreateGalleryStillAlbum()` | **NY i v21** — Oppretter nytt still-album | MEDIUM | Gallery-organisering |
| `CreateGalleryPowerGradeAlbum()` | **NY i v21** — Oppretter nytt PowerGrade-album | MEDIUM | PowerGrade-organisering |

---

### GalleryStillAlbum

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetStills()` | Returnerer alle stills i albumet | MEDIUM | Gallery-oversikt |
| `GetLabel(galleryStill)` | Henter etikett for et still | MEDIUM | Gallery-annotasjon |
| `SetLabel(galleryStill, label)` | Setter etikett for et still | MEDIUM | Gallery-annotasjon |
| `ImportStills([filePaths])` | Importerer stills fra filer | MEDIUM | Grade-import |
| `ExportStills([stills], folder, prefix, format)` | Eksporterer stills til mappe | HØY | Grade-deling/backup |
| `DeleteStills([stills])` | Sletter stills fra albumet | MEDIUM | Gallery-vedlikehold |

---

### Graph

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetNumNodes()` | Returnerer antall noder i grafen | MEDIUM | Node-info |
| `GetLUT(nodeIndex)` | Henter relativ LUT-sti for en node | MEDIUM | Grade-info |
| `SetNodeCacheMode(nodeIndex, cache_value)` | Setter cache-modus for node | MEDIUM | Cache-management |
| `GetNodeCacheMode(nodeIndex)` | Henter cache-modus for node | LAV | Cache-info |
| `GetNodeLabel(nodeIndex)` | Henter etikett for node | MEDIUM | Node-info |
| `GetToolsInNode(nodeIndex)` | Henter liste over verktøy i en node | MEDIUM | Grade-analyse |
| `SetNodeEnabled(nodeIndex, isEnabled)` | Aktiverer/deaktiverer node | HØY | Grade-workflow; bypass en node |
| `ApplyGradeFromDRX(path, gradeMode)` | Laster still fra DRX og applicerer grade | MEDIUM | Grade-import |
| `ApplyArriCdlLut()` | Applicerer ARRI CDL og LUT | MEDIUM | ARRI-workflow |
| `ResetAllGrades()` | Nullstiller alle grades i grafen | MEDIUM | Grade-vedlikehold |

---

### ColorGroup

| API-metode | Beskrivelse | Prioritet | Notater |
|---|---|---|---|
| `GetName()` | Returnerer ColorGroup-navn | MEDIUM | Group-info |
| `SetName(groupName)` | Endrer ColorGroup-navn | MEDIUM | Group-organisering |
| `GetClipsInTimeline(Timeline)` | Returnerer klipp i ColorGroup for gitt timeline | MEDIUM | Group-oversikt |
| `GetPreClipNodeGraph()` | Returnerer pre-clip nodegraf for gruppen | HØY | Batch-grading |
| `GetPostClipNodeGraph()` | Returnerer post-clip nodegraf for gruppen | HØY | Batch-grading |

---

## v21-SPESIFIKKE NYE API-ER (SAMMENDRAG)

Følgende metoder er nye i v21 (26 May 2026) og finnes ikke i v20.3-dokumentasjonen:

### Resolve (root)
- `DisableBackgroundTasksForCurrentResolveSession()` — Deaktiverer alle bakgrunnsoppgaver

### Project
- `ApplyFairlightPresetToCurrentTimeline(name)` — Bruker Fairlight-preset på gjeldende timeline
- `ResetIntellisearchAnalysis()` — Sletter IntelliSearch-analysedata
- `GenerateSpeech({speechGenerationSettings}, timecode)` — AI-talesyntese; legger til i timeline
- `GetQuickExportRenderPresets()` — Lister Quick Export presets
- `RenderWithQuickExport(preset_name, {params})` — Rask eksport uten full render-konfigurasjon

### Folder (alle nye i v21)
- `TranscribeAudio(useSpeakerDetection)` — Batch-transkripsjon med valgfri speaker detection
- `ClearTranscription()` — Sletter transkripsjon for alle klipp i mappen
- `PerformAudioClassification()` — AI-lydklassifisering (batch)
- `ClearAudioClassification()` — Sletter lydklassifisering (batch)
- `RemoveMotionBlur({deblurOption})` — AI motion deblur (batch)
- `AnalyzeForIntellisearch(identifyFaces, isBetterMode)` — IntelliSearch-analyse (batch)
- `AnalyzeForSlate(markerColor)` — Slate-analyse (batch)

### MediaPoolItem (alle nye i v21)
- `TranscribeAudio(useSpeakerDetection)` — Resolve AI-transkripsjon per klipp
- `ClearTranscription()` — Sletter transkripsjon
- `PerformAudioClassification()` — AI-lydklassifisering per klipp
- `ClearAudioClassification()` — Sletter lydklassifisering
- `RemoveMotionBlur({deblurOption})` — AI motion deblur per klipp
- `AnalyzeForIntellisearch(identifyFaces, isBetterMode)` — IntelliSearch-analyse per klipp
- `AnalyzeForSlate(markerColor)` — Slate-analyse per klipp
- `SetName(name)` — Sette klippnavn (ble trolig formalisert i v21)
- `GetThirdPartyMetadata()` / `SetThirdPartyMetadata()` — Tredjepartmetadata
- `GetMarkInOut()` / `SetMarkInOut()` / `ClearMarkInOut()` — Inn/ut-markering
- `MonitorGrowingFile()` — Live-fil overvåking
- `ReplaceClipPreserveSubClip(filePath)` — Erstatt og bevar sub-clip

### MediaPool (nye i v21)
- `AutoSyncAudio([items], {settings})` — Auto-lydsynkronisering
- `GetSelectedClips()` / `SetSelectedClip()` — UI-seleksjon

### Timeline (nye i v21)
- `GetNodeGraph()` — Timeline-nivå nodegraf
- `GetMediaPoolItem()` — Media Pool-referanse
- `GetMarkInOut()` / `SetMarkInOut()` / `ClearMarkInOut()` — Inn/ut-markering
- `ConvertTimelineToStereo()` — Konvertering til stereo
- `AnalyzeDolbyVision()` — Dolby Vision-analyse
- `AddTrack(trackType, newTrackOptions)` — Utvidet sportype med indeks-parameter
- `GetTrackSubType()` — Lydspor-format-info

### TimelineItem (nye/oppdaterte i v21)
- `GetSourceStartFrame()` / `GetSourceEndFrame()` — Source-klipp grenser
- `GetSourceStartTime()` / `GetSourceEndTime()` — Source-klipp tider
- `GetTrackTypeAndIndex()` — Sportype og indeks
- `GetSourceAudioChannelMapping()` — Lydkanal-mapping JSON
- `GetIsColorOutputCacheEnabled()` / `GetIsFusionOutputCacheEnabled()` — Cache-status
- `SetColorOutputCache()` / `SetFusionOutputCache()` — Cache-konfigurasjon
- `GetVoiceIsolationState()` / `SetVoiceIsolationState()` per klipp
- `GetColorGroup()` / `AssignToColorGroup()` / `RemoveFromColorGroup()` — ColorGroup per klipp
- `ResetAllNodeColors()` — Nullstill nodefarger
- `GetLinkedItems()` — Lenkede klipp

### Gallery (nye i v21)
- `GetGalleryPowerGradeAlbums()` — PowerGrade-album-liste
- `CreateGalleryStillAlbum()` — Opprett still-album
- `CreateGalleryPowerGradeAlbum()` — Opprett PowerGrade-album

### OpenPage (oppdatert i v21)
- `"photo"` er nå en gyldig sideverdi for `OpenPage()` og `GetCurrentPage()`

---

## PHOTO PAGE-INTEGRASJON

### Hva KAN gjøres via API for Photo Page

- **Navigere til siden**: `resolve.OpenPage("photo")` fungerer i v21
- **Sjekke om man er på siden**: `resolve.GetCurrentPage()` returnerer `"photo"`
- **Importere media**: Via `MediaPool.ImportMedia()` som normalt — bilder importert her er tilgjengelige i Photo Page
- **Gallery/stills**: `Timeline.GrabStill()`, `GalleryStillAlbum.ExportStills()` — stills fra Color Page kan brukes
- **Color grading**: Fargekorrektur på stillbilder via Color Page-APIet (noder, LUT, CDL) er teknisk sett mulig via klipp-objekter
- **MediaPoolItem metadata**: Metadata kan leses og skrives på importerte stillbilder som på andre klipp

### Hva KAN IKKE gjøres via API for Photo Page

- **Photo Page-spesifikk UI-kontroll**: Ingen API for Photo Page-layout, visningsmoduser, eller egne Photo Page-funksjoner
- **Album-navigasjon i Photo Page**: Ingen API for å administrere Photo-albums (distinkt fra Gallery-albums)
- **Eksportinnstillinger for Photo Page**: Ingen API for Photo Page-spesifikk eksport
- **Bildebehandlingsparametere**: Lokale justeringer, spotverktøy, osv. — ikke tilgjengelig via scripting

### Indirekte tilnærminger

- Import av stillbilder via `MediaPool.ImportMedia()` gjør dem tilgjengelige
- `Timeline.GrabStill()` og `GalleryStillAlbum` API-et kan brukes til grade-stills
- Color Page-grading via node-API-et er mulig på stillfoto behandlet som klipp
- `Project.ExportCurrentFrameAsStill(filePath)` eksporterer gjeldende frame

### Hva å overvåke i fremtidige oppdateringer

- Photo Page-spesifikke API-metoder — Photo Page er ny i v21 og API-støtte vil trolig vokse
- Album-administrasjon for Photo Page via scripting
- Eksportinnstillinger og output-profiler for Photo Page

---

## PRIORITERT BACKLOG

### 🔴 HØY — Umiddelbar verdi for daglig bruk

1. **`save_project`** — `ProjectManager.SaveProject()` — Mangler! Grunnleggende sikkerhet
2. **`switch_timeline`** — `Project.SetCurrentTimeline(timeline)` + `Project.GetTimelineByIndex()` + `Project.GetTimelineCount()` — Navigere mellom timelines
3. **`list_projects`** — `ProjectManager.GetProjectListInCurrentFolder()` — Oversikt
4. **`load_project`** — `ProjectManager.LoadProject(name)` — Grunnleggende prosjektstyring
5. **`export_project`** — `ProjectManager.ExportProject()` — Backup
6. **`archive_project`** — `ProjectManager.ArchiveProject()` — Langtidslagring
7. **`relink_clips`** — `MediaPool.RelinkClips()` — Offline-media-håndtering (svært vanlig problem)
8. **`get_all_timelines`** — `Project.GetTimelineByIndex()` i løkke — Oversikt over alle timelines
9. **`duplicate_timeline`** — `Timeline.DuplicateTimeline()` — Versjonering
10. **`add_timeline_track`** — `Timeline.AddTrack()` — Legg til spor
11. **`delete_timeline_clips`** — `Timeline.DeleteClips()` — Slette klipp
12. **`auto_sync_audio`** — `MediaPool.AutoSyncAudio()` — Dobbel lyd/multi-cam
13. **`render_with_quick_export`** — `Project.RenderWithQuickExport()` — Rask eksport (NY i v21)
14. **`generate_speech`** — `Project.GenerateSpeech()` — AI-talesyntese (NY i v21)
15. **`analyze_for_intellisearch`** — `MediaPoolItem.AnalyzeForIntellisearch()` + `Folder.AnalyzeForIntellisearch()` — AI-søk (NY i v21)
16. **`remove_motion_blur`** — `MediaPoolItem.RemoveMotionBlur()` + `Folder.RemoveMotionBlur()` — AI-bildekvalitet (NY i v21)
17. **`analyze_for_slate`** — `MediaPoolItem.AnalyzeForSlate()` / `Folder.AnalyzeForSlate()` — Automatisk klippgjenkjenning (NY i v21)
18. **`perform_audio_classification`** — `MediaPoolItem.PerformAudioClassification()` — Automatisk lydorganisering (NY i v21)
19. **`transcribe_clip_audio`** — `MediaPoolItem.TranscribeAudio()` — Resolve AI-transkripsjon per klipp (NY i v21)
20. **`set_node_enabled`** — `Graph.SetNodeEnabled()` — Bypass noder

### 🟡 MEDIUM — Nyttig men ikke kritisk

21. **`set_current_media_pool_folder`** — `MediaPool.SetCurrentFolder()` — Bin-navigasjon
22. **`move_clips_to_folder`** — `MediaPool.MoveClips()` — Organisering
23. **`export_gallery_stills`** — `GalleryStillAlbum.ExportStills()` — Grade-backup
24. **`grab_still`** — `Timeline.GrabStill()` — Still til gallery
25. **`add_color_version`** — `TimelineItem.AddVersion()` + `LoadVersionByName()` — Versjonert grading
26. **`copy_grades`** — `TimelineItem.CopyGrades()` — Batch grading
27. **`assign_color_group`** — `TimelineItem.AssignToColorGroup()` + `Project.GetColorGroupsList()` — Gruppe-grading
28. **`link_proxy_media`** — `MediaPoolItem.LinkProxyMedia()` / `UnlinkProxyMedia()` — Proxy-workflow
29. **`replace_clip`** — `MediaPoolItem.ReplaceClip()` — Online-workflow
30. **`get_clip_metadata`** — `MediaPoolItem.GetMetadata()` — Metadata-lesing
31. **`set_clip_metadata`** — `MediaPoolItem.SetMetadata()` — Metadata-skriving
32. **`add_clip_markers`** — `MediaPoolItem.AddMarker()` — Markers på klipp i Media Pool
33. **`add_timeline_flags`** — `TimelineItem.AddFlag()` / `GetFlagList()` — Klipp-flagging
34. **`add_take`** — `TimelineItem.AddTake()` + take-management — Multi-take-workflow
35. **`set_clip_enabled`** — `TimelineItem.SetClipEnabled()` — Klipp-aktivering
36. **`manage_render_presets`** — `Project.SaveAsNewRenderPreset()`, `DeleteRenderPreset()` — Preset-organisering
37. **`get_project_list`** — `ProjectManager.GetProjectListInCurrentFolder()` — Prosjektoversikt
38. **`manage_project_database`** — `ProjectManager.GetCurrentDatabase()`, `GetDatabaseList()`, `SetCurrentDatabase()` — Database-bytte
39. **`apply_fairlight_preset`** — `Project.ApplyFairlightPresetToCurrentTimeline()` — Lyd (NY i v21)
40. **`get_node_graph_info`** — `Graph.GetNumNodes()`, `GetNodeLabel()`, `GetToolsInNode()`, `GetLUT()` — Node-analyse
41. **`set_track_properties`** — `Timeline.SetTrackEnable()`, `SetTrackLock()`, `SetTrackName()` — Spororganisering
42. **`delete_timeline_markers`** — `Timeline.DeleteMarkersByColor()`, `DeleteMarkerAtFrame()` — Marker-opprydding
43. **`create_timeline_from_clips`** — `MediaPool.CreateTimelineFromClips()` — Raskere enn create+append
44. **`import_timeline_from_file`** — `MediaPool.ImportTimelineFromFile()` — AAF/EDL/FCPXML-import
45. **`export_metadata_csv`** — `MediaPool.ExportMetadata()` — Metadata-eksport for produksjonsstyring

### 🟢 LAV — Nice-to-have eller nisje

46. **`manage_layout_presets`** — `Resolve.LoadLayoutPreset()`, `SaveLayoutPreset()` — UI-layout
47. **`get_mounted_volumes`** — `MediaStorage.GetMountedVolumeList()` — Filsystem-info
48. **`browse_media_storage`** — `MediaStorage.GetFileList()`, `GetSubFolderList()` — Mediasøk
49. **`create_stereo_clip`** — `MediaPool.CreateStereoClip()` — Stereo-workflow
50. **`convert_timeline_stereo`** — `Timeline.ConvertTimelineToStereo()` — Stereo-konvertering
51. **`analyze_dolby_vision`** — `Timeline.AnalyzeDolbyVision()` — Dolby Vision
52. **`cloud_project_management`** — `ProjectManager.CreateCloudProject()` m.fl. — Cloud-workflow
53. **`manage_gallery_albums`** — `Gallery.GetGalleryStillAlbums()`, `CreateGalleryStillAlbum()`, `GetGalleryPowerGradeAlbums()` — Gallery-administrasjon (delvis NY i v21)
54. **`disable_background_tasks`** — `Resolve.DisableBackgroundTasksForCurrentResolveSession()` — Ytelsesoptimering (NY i v21)
55. **`set_keyframe_mode`** — `Resolve.SetKeyframeMode()` / `GetKeyframeMode()` — Keyframe-modus
56. **`manage_color_groups`** — `Project.AddColorGroup()`, `DeleteColorGroup()`, `GetColorGroupsList()` — ColorGroup-administrasjon

---

## BEGRENSNINGER

### Fairlight-begrensninger
- Ingen tilgang til Fairlight-mixer, bussruting, EQ, kompressor, reverb, delay osv. via scripting
- `InsertAudioToCurrentTrackAtPlayhead()` er den eneste direkte Fairlight-operasjonen
- Lyd-automating er ikke tilgjengelig via scripting
- Fairlight MIDI-routing er ikke scriptbar
- `ApplyFairlightPresetToCurrentTimeline()` (NY i v21) er den eneste preset-operasjonen

### Color Page-begrensninger
- Fargehjul (Lift/Gamma/Gain), kurver, qualifier, vinduer/masks (utenfor Magic Mask) og OFX-effekter kan IKKE konfigureres via scripting
- Node-struktur (legge til, slette, koble noder) er ikke tilgjengelig via scripting — kun LUT, CDL og enable/disable per node
- Parallell-noder og layer-noder er ikke direkte scriptbare
- Hue vs. Hue/Sat/Lum-kurver er ikke tilgjengelige via scripting
- Noise reduction og sharpening er ikke scriptbare (unntatt SuperScale)
- Gallery PowerGrade-import til klipp via scripting er ikke direkte mulig

### AI-verktøy som kan trigges men ikke konfigureres fullt ut
- `CreateMagicMask()` — kan trigges (F/B/BI), men ingen scripting-tilgang til brush-justeringer
- `SmartReframe()` — kan trigges, men ingen konfigurasjon av reframe-parametere
- `Stabilize()` — kan trigges, men stabiliseringsparametere (strength, smooth, zoom) er ikke scriptbare
- `DetectSceneCuts()` — kan trigges, men threshold-konfigurasjon er ikke scriptbar
- `CreateSubtitlesFromAudio()` — kan trigges med begrenset konfigurasjon (språk, preset, chars/line)
- `AnalyzeForIntellisearch()` — kan trigges, men søke-UI er ikke scriptbart
- `AnalyzeForSlate()` — kan trigges, slate-konfigurasjon er kun markerColor
- `RemoveMotionBlur()` — kan trigges med output-innstillinger, men ikke AI-parametere
- `GenerateSpeech()` — kan trigges med tekst og stemmevalg

### Ting som krever manuell UI-interaksjon
- Fusion-noder og Fusion-komposisjoner internt (kan opprettes/importeres, ikke redigeres node-for-node via MCP)
- Color Page-vindu/tracker (automatisk tracking er ikke scriptbart)
- Multicam-klipp-synkronisering via UI (AutoSyncAudio er tilgjengelig via scripting fra v21)
- Render-kø-manuell rekkefølgesortering
- Media Pool sortering og filtrering via UI
- Photo Page-spesifikke justeringer
- Fairlight Audio Editing-side (er separat fra Fairlight-siden i nyere versjoner)
- Collaboration-modus bruker-administrasjon
- DaVinci Remote Grading (hardware-panel) er ikke scriptbart

### Generelle API-begrensninger
- Scripting API er Python/Lua — ikke tilgjengelig fra JavaScript uten wrapper
- Alle operasjoner er synkrone og blokkerende i Resolve sin UI-tråd
- Ingen event/callback-system — polling er nødvendig for å overvåke tilstand
- `execute_resolve_code` er den ultimate fallback for alt som ikke har dedikert API

---

*Generert: 2026-06-30 | Kilde: Resolve 21 Scripting README (26 May 2026)*
