# PROMPTS.md — my key prompts log

Keep the handful of prompts that actually moved the build. Not every message — the ones that
mattered: the system/sub-agent prompts, the ones you iterated on, the "this finally worked"
moment. This shows how you direct an AI, which is graded (challenge brief section 08).

Format per entry:
- **Prompt** (paste it)
- **For:** what you were trying to do
- **Revised?** did you have to change it, and why

---

## Example (replace with your own)

- **Prompt:** "Extend seo/detector.py to detect redirect chains: build a map of {Address ->
  Redirect URL} for all 3xx rows, then a chain exists when a Redirect URL is itself a key in
  that map. Add a redirect_chain issue (High). Run python seo/detector.py and show counts."
- **For:** adding the redirect-chain detector
- **Revised?** Yes — first version flagged single redirects as chains; added the "target is
  also a redirecting URL" condition.

---

## My prompts
1. "Fixed the errors in the claude-plugin"
2. "The dashboard at localhost:7700 is unreachable (ERR_CONNECTION_REFUSED). Please perform these steps:

Check if any process is currently listening on port 7700 (e.g., using lsof -i :7700).

Locate the startup command for the MCP server in mcp/server.py or the plugin manifest.

Attempt to start the server in a background process or a separate terminal session.

If it fails to start, show me the error logs immediately so we can fix the initialization logic."
3. **Prompt:** "Add a title_too_short detector to seo/detector.py. Rule: Title 1 Length < 30 AND title not empty, on indexable 200 pages. Severity Low."
   **For:** Adding the missing title detector
   **Revised?** No — worked first try.
4. **Prompt:** "Add three meta description detectors: missing, duplicate, too_long with specific rules and code patterns"
   **For:** Completing meta description detection
   **Revised?** No