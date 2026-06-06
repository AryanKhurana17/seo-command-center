# PROMPTS.md — my key prompts log

The prompts that actually moved the build. Not every message — the ones that
mattered: the system/sub-agent prompts, the ones iterated on, the "this finally worked"
moment. This shows how you direct an AI (graded, challenge brief section 08).

---

## 1. Fixing the plugin foundation

- **Prompt:** "The `.claude-plugin/plugin.json` and `.claude/settings.json` files have errors — fix the plugin manifest and audit hook configuration so the hooks record every tool call to `.claude/audit.jsonl`."
- **For:** Getting the plugin infrastructure working before any SEO logic
- **Revised?** No — straightforward config fix.

## 2. Getting the dashboard live

- **Prompt:** "The dashboard at localhost:7700 is unreachable (ERR_CONNECTION_REFUSED). Check if any process is listening on port 7700 (lsof -i :7700). Locate the startup command in mcp/server.py. Start the server and show me the error logs immediately if it fails."
- **For:** Debugging why the HTTP dashboard wasn't starting
- **Revised?** Yes — first version just said "start the server." Added the diagnostic steps (lsof, error logs) to get actionable output instead of a vague retry.

## 3. Title detectors (incremental, one at a time)

- **Prompt:** "Add a `title_too_short` detector to `seo/detector.py`. Rule: `Title 1 Length` < 30 AND title not empty, on indexable 200 pages. Severity Low. Run `python seo/detector.py sample-export/` and show the count."
- **For:** Adding one detector at a time with immediate verification
- **Revised?** No — worked first try. This pattern (one detector + verify) was used for all 17.

## 4. Meta description detectors (batch of 3)

- **Prompt:** "Add three meta description detectors to `seo/detector.py`: `missing_meta_description` (Medium, idx200, empty Meta Description 1), `duplicate_meta_description` (Medium, idx200, same value on 2+ URLs using defaultdict), `meta_description_too_long` (Low, idx200, Length > 155). Add after the title section with a `# --- Meta Descriptions ---` comment."
- **For:** Completing meta description detection in one shot
- **Revised?** No — the pattern from title detectors transferred cleanly.

## 5. H1 detectors (critical filter distinction)

- **Prompt:** "Add two H1 detectors. IMPORTANT: `missing_h1` uses ALL html 200 pages (not just indexable), but `duplicate_h1` uses only indexable pages (idx200). 1. `missing_h1` (Medium): H1-1 empty on a 200 HTML page. 2. `duplicate_h1` (Low): Same H1-1 on 2+ indexable URLs. Check @rulebook.md for details."
- **For:** H1 detection with the correct filter distinction from the rulebook
- **Revised?** Yes — first version didn't emphasize the filter difference. Added the "IMPORTANT" callout after re-reading rulebook.md which specifies `missing_h1` applies to ALL 200 pages, not just indexable.

## 6. Redirect chain detection

- **Prompt:** "Extend `seo/detector.py` to detect redirect chains: build a map of `{Address → Redirect URL}` for all 3xx rows, then a chain exists when a Redirect URL is itself a key in that map. Also detect loops by traversing the chain with a visited set. Add as `redirect_chain` issue (High). Run the detector and show counts."
- **For:** The most complex detector — chains AND loops
- **Revised?** Yes — first version only checked one hop. Added the visited-set loop detection after thinking about the grader's edge cases.

## 7. Remaining detectors (batch)

- **Prompt:** "Add four more detectors: `thin_content` (Low, idx200, 0 < Word Count < 200 — filter >0 to avoid blanks), `non_indexable_but_linked` (Medium, html non-indexable with Inlinks > 0), `slow_page` (Low, all rows, Response Time > 1.0), `missing_image_alt` (Medium, image rows with no Alt Text 1 or Alt Text). All 17 should now be complete."
- **For:** Finishing the full rulebook implementation
- **Revised?** Yes — added the `Word Count > 0` filter for thin_content after it was incorrectly counting pages with no word count data.

## 8. Dashboard rewrite

- **Prompt:** "Rewrite the dashboard UI: dark theme with Inter font, KPI cards (total/high/medium/low), live issue table with severity badges (red/yellow/gray pills), status indicator bar, recommendations panel, SSE streaming. Make it look like a professional operator cockpit."
- **For:** Replacing the minimal starter dashboard with a client-worthy UI
- **Revised?** No — the design spec was detailed enough for a single pass.

## 9. Report HTML redesign

- **Prompt:** "Rewrite `_render_html()` in `server.py`. The report.html must be client-ready: executive summary with KPI grid, severity-sorted issue table with badges, expandable affected URLs (top 5 + 'more' count) using `<details>`, numbered recommendations, print-friendly CSS, responsive. Include title rewrite and redirect map sections if fixes exist."
- **For:** Making report.html a deliverable you'd actually send a client
- **Revised?** Yes — first version didn't have the expandable URL sections. Added `<details>` after realizing 279 image URLs would destroy readability.