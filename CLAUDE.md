# CLAUDE.md — project memory for the SEO Command Center build


## What we are building
A Claude Code plugin that ingests a Screaming Frog SEO export (`internal_all.csv` + issue
CSVs), audits it against the rulebook, prioritizes issues, writes fixes, serves a live
dashboard at localhost:7700, and outputs `outputs/report.json` + `outputs/report.html`.

## Hard rules (the agent must follow these)
- Detect issues in **plain Python** (csv/pandas). Use the model only for judgment
  (rewriting titles/metas, choosing redirect targets). Never feed raw crawl rows to the model.
- `outputs/report.json` MUST match `report.schema.json`. Validate before declaring done.
- Filter to `text/html` + indexable pages before title/meta checks (see `rulebook.md`).
- Do not hard-code anything to the sample export — it must work on an unseen export.

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
│       └── SKILL.md            # Orchestrator prompt — tells the agent the pipeline order
├── agents/                     # Sub-agent prompts
│   ├── ingest.md
│   ├── auditor.md
│   ├── fixer.md
│   └── reporter.md
├── commands/
│   └── seo-audit.md            # The /seo-audit slash command definition
├── mcp/
│   └── server.py               # MCP server (tools over stdio) + HTTP dashboard on :7700
├── seo/
│   └── detector.py             # Issue detection — STARTER had only 7/17 rules
├── dashboard/
│   ├── index.html              # Cockpit UI
│   └── app.js                  # SSE-connected client logic
├── scripts/
│   └── export-transcript.sh    # Exports session transcript to agent-log.md
├── outputs/                    # Final deliverables
│   ├── report.json             # Must match report.schema.json
│   └── report.html
├── run.py                      # Headless runner (grader's entry point)
├── report.schema.json          # Output validation schema
├── rulebook.md                 # 17 detection rules with exact thresholds
├── CLAUDE.md                   # Project memory (System prompt)
├── PROMPTS.md                  # Process log (graded)
├── DECISIONS.md                # Engineering log (graded)
└── README.md                   # Project overview and instructions
```

## Conventions
- Run `python run.py sample-export/` to test end to end.

## Things I have learned during the build (update this as you go)
- (e.g. "SF leaves Title 1 blank on redirected URLs — must filter Status Code 200 first")
- claude-plugin format was wrong
