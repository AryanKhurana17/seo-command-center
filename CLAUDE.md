# CLAUDE.md — project memory for the SEO Command Center build

## What this is
A Claude Code plugin (SEO Command Center) that ingests a Screaming Frog SEO export
(`internal_all.csv` + issue CSVs), audits it against the full 17-rule rulebook, prioritizes
issues by severity, generates model-driven fixes, serves a live dashboard at
`http://localhost:7700`, and outputs `outputs/report.json` + `outputs/report.html`.

## Hard rules (the agent must follow these)
- Detect issues in **plain Python** (csv only, no pandas). Use the model only for judgment
  (rewriting titles/metas, choosing redirect targets). Never feed raw crawl rows to the model.
- `outputs/report.json` MUST match `report.schema.json`. Validate before declaring done.
- Filter to `text/html` + indexable pages before title/meta checks (see `rulebook.md`).
- Do not hard-code anything to the sample export — it must work on an unseen export.
- Do not plan if the instructions are explicitly told to you.
- Severity strings must be exactly `High`, `Medium`, or `Low`.

## Architecture
```text
seo-command-center/
├── .claude-plugin/
│   └── plugin.json             # Plugin manifest: declares skill, command, agents, MCP server
├── .claude/
│   ├── settings.json           # Audit hooks config (auto-records every tool call)
│   └── hooks/
│       └── audit.sh            # Shell script that writes JSONL log entries
├── skills/
│   └── seo-audit/
│       └── SKILL.md            # Orchestrator prompt — pipeline: ingest → audit → fix → recommend → deliver
├── agents/                     # Sub-agent prompts (one per pipeline stage)
│   ├── ingest.md               # Loads export, confirms URL count and site
│   ├── auditor.md              # Runs rulebook detectors, verifies coverage
│   ├── fixer.md                # Model-driven title/meta rewrites + redirect map (champion)
│   └── reporter.md             # Writes report.json + report.html
├── commands/
│   └── seo-audit.md            # The /seo-audit slash command definition
├── mcp/
│   └── server.py               # MCP server (tools over stdio) + HTTP dashboard on :7700
│                                  Tools: load, detect_issues, set_fixes, recommend, write_report, export_report
├── seo/
│   ├── __init__.py
│   └── detector.py             # All 17 deterministic issue detectors
├── dashboard/
│   ├── index.html              # Live cockpit UI (dark theme, KPI cards, severity badges)
│   └── app.js                  # SSE-connected client logic (fetches /state, listens /events)
├── scripts/
│   └── export-transcript.sh    # Exports session transcript to agent-log.md
├── outputs/                    # Final deliverables (generated)
│   ├── report.json             # Machine-readable, matches report.schema.json
│   └── report.html             # Client-ready standalone report
├── run.py                      # Headless runner (grader's entry point): python run.py <export_dir>
├── report.schema.json          # JSON Schema for report.json validation
├── rulebook.md                 # 17 detection rules with exact thresholds
├── requirements.txt            # Just `mcp`
├── CLAUDE.md                   # This file — project memory
├── PROMPTS.md                  # Key prompts log (graded)
├── DECISIONS.md                # Engineering decisions log (graded)
└── README.md                   # Setup and usage instructions
```

## All 17 detectors implemented in `seo/detector.py`

| # | Type | Severity | Filter | Rule |
|---|------|----------|--------|------|
| 1 | `missing_title` | High | idx200 (indexable+200+html) | Title 1 empty |
| 2 | `duplicate_title` | High | idx200 | Same Title 1 on 2+ URLs |
| 3 | `title_too_long` | Medium | idx200 | Pixel Width > 561 OR Length > 60 |
| 4 | `title_too_short` | Low | idx200 | Length < 30, title not empty |
| 5 | `missing_meta_description` | Medium | idx200 | Meta Description 1 empty |
| 6 | `duplicate_meta_description` | Medium | idx200 | Same Meta Description 1 on 2+ |
| 7 | `meta_description_too_long` | Low | idx200 | Length > 155 |
| 8 | `missing_h1` | Medium | html 200 (NOT just indexable) | H1-1 empty |
| 9 | `duplicate_h1` | Low | idx200 | Same H1-1 on 2+ |
| 10 | `broken_link` | High | all rows | Status Code 400–499 |
| 11 | `server_error` | High | all rows | Status Code 500–599 |
| 12 | `redirect` | Medium | all rows | Status Code 300–399 |
| 13 | `redirect_chain` | High | all rows | Redirect URL is itself a redirect |
| 14 | `thin_content` | Low | idx200 | 0 < Word Count < 200 |
| 15 | `orphan_page` | Medium | idx200 | Inlinks = 0 |
| 16 | `non_indexable_but_linked` | Medium | html (non-indexable) | Inlinks > 0 |
| 17 | `slow_page` | Low | all rows | Response Time > 1.0 |

## Conventions
- Run `python run.py sample-export/` to test end to end (opens dashboard at :7700).
- Run `python run.py sample-export/ --no-dashboard` for headless (no HTTP server).
- Run `python seo/detector.py sample-export/` for detector-only testing.
- All issue types use the exact strings from `rulebook.md` — do NOT rename them.

## Key learnings during the build
- Screaming Frog leaves `Title 1` blank on redirected URLs — must filter to Status Code 200 first.
- `.claude/settings.json` format needed correction for hook matchers.
- `mcp/server.py` and `run.py` had coupling issues on initial startup — fixed by importing server module correctly.
- All 17 detectors implemented. Key filters: `idx200` for most title/meta checks, `html200` for `missing_h1`, full `rows` for status code checks.
- `missing_image_alt` may need column name adjustment depending on the SF export version — tries both `Alt Text 1` and `Alt Text`.
- `thin_content`: must filter `Word Count > 0` to avoid flagging pages with no word count data.
- Sample export has 0 instances of: `missing_title`, `missing_meta_description`, `server_error`, `redirect_chain`, `orphan_page` — all detectors are present but produce empty arrays (correct behavior, they will fire on hidden export if applicable).
- Dashboard SSE connection: `/state` returns full snapshot, `/events` streams live updates.
- Report HTML uses expandable `<details>` for affected URLs to keep it scannable.
