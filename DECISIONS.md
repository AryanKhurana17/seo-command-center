# DECISIONS.md — decision & learnings log

A running note of the real choices made: what was tried, what failed and why, what
changed. This is engineering judgement on the record — graded (challenge brief section 08).

---

## My log

- `[10:05]` Fixed `.claude/settings.json` — hook format was incorrect, matchers needed `".*"` regex pattern for PreToolUse/PostToolUse. Without this, audit.jsonl was not recording tool calls.

- `[10:20]` MCP server wouldn't start — `mcp/server.py` import path was broken due to relative imports. Fixed by inserting `sys.path` manipulation in both `server.py` and `run.py` so `seo.detector` resolves correctly regardless of entry point.

- `[10:40]` Chose plain `csv.DictReader` over pandas → fewer deps (requirement says standard library), fast enough for 5k+ rows, and avoids model quota for what should be deterministic Python.

- `[11:00]` Dashboard at `:7700` was unreachable → `start_dashboard()` was never being called in headless mode. Fixed `run.py` to call it before the pipeline runs. Also verified SSE event streaming works.

- `[11:15]` Added `title_too_short` detector (rule: `Title 1 Length < 30` AND title not empty, on indexable 200 pages, severity Low). Verified count matches Screaming Frog's own issue CSV. 8/17 detectors done.

- `[11:30]` Added 3 meta description detectors (`missing_meta_description`, `duplicate_meta_description`, `meta_description_too_long`). Used the same `defaultdict` grouping pattern as title duplicate detection. 11/17.

- `[11:45]` Added H1 detectors. **Key insight from rulebook**: `missing_h1` applies to ALL 200 HTML pages (not just indexable), but `duplicate_h1` uses indexable pages only. This distinction matters for accuracy. 13/17 done.

- `[12:00]` Added remaining detectors: `thin_content`, `non_indexable_but_linked`, `slow_page`, `missing_image_alt`. All 17 detectors now present. `missing_image_alt` tries both column names (`Alt Text 1` and `Alt Text`) since SF export versions differ.

- `[12:15]` `thin_content` was incorrectly flagging pages with empty `Word Count` (treated as 0). Added `Word Count > 0` filter to only flag pages that genuinely have few words, not pages where the count wasn't measured.

- `[12:30]` Redirect chain detection: built a `{Address → Redirect URL}` map for all 3xx rows, then checked if any Redirect URL target is also a key (another redirect). Also added loop detection with a visited-set traversal. Sample export has no chains, but the detector is ready for hidden export.

- `[13:00]` Rewrote the dashboard: dark theme matching NMG brand, KPI cards with severity coloring, live issue table with animated fade-in rows and severity badges, SSE events populate data in real-time. Replaced the minimal starter UI with a professional cockpit.

- `[13:30]` Rewrote `report.html` template: executive summary with KPI grid, prioritized issue table with severity badges, expandable `<details>` for affected URLs per issue (shows top 5 + "more" count), numbered recommendations, proper print CSS, responsive layout. Looks genuinely client-ready now.

- `[14:00]` Verified `report.json` against `report.schema.json` — all required fields present, severity values correct, issue counts match. 5 issue types produce 0 results on the sample export (`missing_title`, `missing_meta_description`, `server_error`, `redirect_chain`, `orphan_page`) which is correct behavior — those detectors will fire on the hidden export if those issues exist.

- `[14:15]` Fixed `app.js` bug: dead code variable `badgeClass` had a typo (`badge- ${...}` with extra space). Removed the unused variable — the correct `sevClass` was already being used on the next line.

- `[14:30]` Updated all process files (`CLAUDE.md`, `README.md`, `PROMPTS.md`, `DECISIONS.md`) with accurate, detailed content reflecting the actual build. CLAUDE.md now has the full detector reference table. README.md documents all 17 detectors and the architecture.
