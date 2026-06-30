# BRIEF.md — resolve-mcp-studio
> Planleggingsdokument for prosjektet. Produsert fra samtale i Claude chat.
> Dato: 2026-06-11

---

## Idé & Problem

**Hva er idéen?**
En lokal MCP-server som kobler Claude Desktop direkte til DaVinci Resolve Studio, med et valgfritt innebygd Resolve-panel som frontend. Brukeren kan styre Resolve med naturlig språk fra Claude Desktop, eller bruke panelet for visuell kontroll.

**Problemet det løser:**
- Markers må settes manuelt én og én i Resolve — tidkrevende ved lange lister
- Resolves auto-transkripsjon fungerer dårlig på norsk
- Oppretting av bins og prosjektstruktur er repetitivt og tungvindt
- Ingen sømløs flyt mellom AI-assistent og NLE

**Hvem bruker den?**
Primært Stephan — men bygget som et åpent verktøy andre Resolve-brukere kan ta i bruk.

**Referanser og inspirasjon:**
- Fork av `barckley75/resolve-claude-mcp`
- Inspirert av `coreymaypray/sloth-skill-tree` (davinci-resolve-mcp skill)
- Auto-Subs av Tom Moroney som referanse for subtitle-skriving
- `samuelgursky/davinci-resolve-mcp` som referanse for API-dekning

---

## Features

### MVP (v1)

**Funksjon 1 — Markers**
- Claude parser en fritekst-liste med tidskoder og kommentarer
- Konverterer til riktig timecode-format basert på prosjektets fps
- Sender markers til en interaktiv editor (artifact i Claude Desktop eller panel)
- Brukeren kan redigere navn, farge og tid før godkjenning
- Claude setter markers direkte i aktiv timeline via MCP
- Alltid dobbeltsjekk: bekreft aktivt prosjekt og timeline før handling

**Funksjon 2 — Transkripsjon**
- Claude transkriberer med mlx-whisper lokalt (gratis, Apple Silicon-optimalisert)
- Spør om språk hvis ikke oppgitt
- Tre scenarioer:
  - Ingen subtitle-track: lag ny direkte i Resolve
  - Track finnes: velg korriger eksisterende ELLER lag ny parallell track
  - Korrigering: rett ord uten å endre timing eller formattering
- Panelet håndterer hele dialogen (språkvalg, track-valg) — ikke Claude Desktop

**Funksjon 3 — Prosjektmaler**
- JSON-basert malsystem
- Første mal: `_TEMPLATE_.drp` (3840×2160, 25fps, stereo, timelines: EDIT-9x16, EDIT-16x9, Selects)
- Velg mal ved oppstart av nytt prosjekt
- Enkelt å legge til nye maler

**Funksjon 4 — Media Pool ↔ Finder sync**
- Pek på en Finder-mappe
- Claude leser mappestruktur og oppretter tilsvarende bins i Media Pool
- Kobler bins til Finder-mapper via Resolves innebygde linked folder-funksjon
- Nye filer i Finder dukker automatisk opp i riktig bin

### Ikke i v1
- Windows-støtte
- Multi-bruker / sky-sync
- Andre NLE-er enn DaVinci Resolve
- Automatisk marker-fargesystem (brukeren styrer farger i editoren)

---

## Samspill mellom Claude og panel

**To moduser:**

*Instruksmodus* — Claude gjenkjenner en direkte kommando, forklarer hva den skal gjøre, venter på godkjenning, utfører.

*Spørsmålsmodus* — spørsmål svares på uten at Claude gjør noe i Resolve.

**Panel er valgfritt men anbefalt:**
- Marker-editor fungerer i panelet — Claude sender lista, bruker redigerer, godkjenner
- Transkripsjon: språkvalg + track-valg i panelet
- Status-display: aktivt prosjekt, aktiv timeline, render-kø
- Claude Desktop er alltid kjernen og må kjøre

---

## Platform & Distribusjon

- **macOS primær** (Apple Silicon, utviklet og testet på MacBook Pro)
- **Windows:** ikke i scope
- Krever DaVinci Resolve Studio (ikke gratis-versjonen)
- Krever Claude Desktop med MCP-støtte
- Distribueres som open source på GitHub

---

## UI & Design

**Resolve-panel (HTML/JS/CSS innebygd i Resolve):**
- Mørk bakgrunn — matcher Resolve sitt UI
- Teknisk/minimalistisk stil
- Aksentfarge: cyan (#00E5FF) med violet/magenta som sekundær
- Font: karakteristisk — ikke Inter/Roboto/Arial
- Referanse: Evervault, Wope — film+tech-kryssing
- Panel skal se ut som en del av Resolve, ikke et fremmedlegeme

**Marker-editor:**
- Tabell-visning med redigerbare celler (navn, farge, tid)
- Fargevelger med Resolves faktiske fargenavn
- Legg til / slett rows
- "Godkjenn og send til Resolve"-knapp

---

## Data & Lagring

- Prosjektmaler lagres som JSON i `templates/`-mappe i repoet
- `_TEMPLATE_.drp` legges i `templates/drp/`
- Ingen sky-lagring — alt lokalt
- Ingen sensitiv data — ingen API-nøkler nødvendig (mlx-whisper er lokal, Resolve API er lokal)
- Konfigurasjon (f.eks. standard fps, foretrukket språk) lagres i `.env` eller lokal config-fil

---

## Teknisk Kontekst

**Eksisterende kode:**
- Fork av `barckley75/resolve-claude-mcp` — allerede klonet som `stephanteig/resolve-mcp-studio`
- Eksisterende verktøy: `get_markers`, `add_marker`, `execute_resolve_code`, `stabilize`, `detect_scene_cuts`
- MCP-server kjøres via `uv run python -m resolve_claude_mcp.server`
- Stack: Python + FastMCP + DaVinciResolveScript

**Resolve panel:**
- Bygges som HTML/JS/CSS workspace panel i Resolve
- Kommuniserer med MCP-serveren direkte (samme backend som Claude Desktop)

**Transkripsjon:**
- mlx-whisper for Apple Silicon
- Auto-Subs-pluginen brukes som referanse for subtitle-skriving til Resolve

**Unngå:**
- Ingen ekstern API-avhengighet (alt skal fungere offline bortsett fra Claude Desktop)
- Ingen database — flat fil / JSON er nok
- Ingen Electron eller separate desktop-apper

---

## Scope

**Ferdig nok for v1 når:**
- Marker-funksjon fungerer end-to-end (liste → editor → Resolve)
- Transkripsjon fungerer med norsk og engelsk, og kan skrive til Resolve
- Prosjektmal kan opprette nytt prosjekt med riktig struktur
- Media Pool ↔ Finder sync fungerer for én mappe
- Resolve-panel fungerer for marker-editor og transkripsjon
- README med setup-instruksjoner

**Hastverk?** Nei — men Stephan bruker dette aktivt i produksjon hos Studio Wallin, så kvalitet over hastighet.

---

## Credits

- Fork av [barckley75/resolve-claude-mcp](https://github.com/barckley75/resolve-claude-mcp)
- Inspirert av [coreymaypray/sloth-skill-tree](https://github.com/coreymaypray/sloth-skill-tree)
- Subtitle-referanse: [Auto-Subs av Tom Moroney](https://tom-moroney.com/auto-subs/)

---

*BRIEF av Stephan Teig — generert med app-planner skill*
