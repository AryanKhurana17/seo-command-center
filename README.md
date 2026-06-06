# SEO Command Center — Forge Sprint 01

A Claude Code **plugin** that ingests a **Screaming Frog SEO export**, audits it against
the full 17-rule rulebook, prioritizes every issue by severity, writes model-driven fixes,
and renders a **live dashboard** at `http://localhost:7700` plus an exportable client-ready
HTML report.

## Quick start

```bash
pip install mcp                    # MCP SDK for Claude Code tool integration
python run.py sample-export/       # runs the full pipeline
# → dashboard live at http://localhost:7700
# → outputs: outputs/report.json + outputs/report.html
```

## Inside Claude Code

```
/seo-audit sample-export/
```

The `/seo-audit` slash command triggers the full pipeline via the skill orchestrator and
sub-agents, streaming results to the live dashboard in real time.

## Architecture

```
seo-command-center/
├── .claude-plugin/plugin.json     Plugin manifest (skill + command + agents + MCP)
├── .claude/                       Audit hooks (settings.json + hooks/) → process recording
├── skills/seo-audit/SKILL.md      Orchestrator: ingest → audit → fix → recommend → deliver
├── agents/                        Sub-agents: ingest, auditor, fixer, reporter
├── commands/seo-audit.md          /seo-audit slash command
├── mcp/server.py                  MCP server (stdio tools) + HTTP dashboard host (:7700)
├── seo/detector.py                All 17 deterministic issue detectors
├── dashboard/                     index.html + app.js (live cockpit with SSE)
├── scripts/export-transcript.sh   Exports Claude Code session → agent-log.md
├── run.py                         Headless runner (grader entry point)
├── report.schema.json             JSON Schema for report.json validation
├── rulebook.md                    17 detection rules with exact thresholds
└── outputs/                       report.json + report.html (generated)
```

## What was built

### Detection (all 17 rules from `rulebook.md`)
All 17 issue detectors are implemented in `seo/detector.py` using pure Python (csv module, no external deps):

| Category | Detectors |
|----------|-----------|
| **Titles** | `missing_title` (High), `duplicate_title` (High), `title_too_long` (Medium), `title_too_short` (Low) |
| **Meta Descriptions** | `missing_meta_description` (Medium), `duplicate_meta_description` (Medium), `meta_description_too_long` (Low) |
| **H1 Headers** | `missing_h1` (Medium), `duplicate_h1` (Low) |
| **Status Codes** | `broken_link` / 4xx (High), `server_error` / 5xx (High), `redirect` / 3xx (Medium), `redirect_chain` (High) |
| **Content & Links** | `thin_content` (Low), `orphan_page` (Medium), `non_indexable_but_linked` (Medium) |
| **Performance** | `slow_page` (Low) |
| **Images** | `missing_image_alt` (Medium) |

### Live Dashboard (`http://localhost:7700`)
- Real-time SSE-powered cockpit
- KPI cards (total, high, medium, low)
- Sortable issue table with severity badges
- Status indicator (idle → running → done)
- Recommendations panel

### Client Report (`outputs/report.html`)
- Standalone dark-theme HTML — no external dependencies except Google Fonts
- Executive summary with KPI cards
- Prioritized issue table with expandable affected URLs
- Numbered recommendations with visual priority
- Print-friendly CSS for PDF export
- Responsive layout

### MCP Tools
The server exposes 6 tools: `load`, `detect_issues`, `set_fixes`, `recommend`, `write_report`, `export_report`.

## Pipeline

```
1. Ingest   → load(export_dir)      reads internal_all.csv, reports URL count + site
2. Detect   → detect_issues()       runs all 17 rulebook detectors, streams to dashboard
3. Fix      → set_fixes(...)        model-driven title/meta rewrites + redirect map (champion)
4. Recommend → recommend([...])     prioritized action items
5. Deliver  → write_report()        outputs/report.json (matches schema)
             → export_report()      outputs/report.html (client deliverable)
```

## Process files (graded)
- `CLAUDE.md` — project memory and agent instructions, updated throughout the build
- `PROMPTS.md` — key prompts that moved the build forward
- `DECISIONS.md` — engineering decisions and learnings log
- `.claude/audit.jsonl` — auto-recorded by hooks (every tool call)
- `agent-log.md` — exported session transcript

## Model
Built on the free local stack: **Claude Code + Ollama** (`qwen3.5:9b`).
Set `OLLAMA_CONTEXT_LENGTH=65536` for optimal performance.
