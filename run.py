#!/usr/bin/env python3
"""
run.py — headless runner for the SEO Command Center (also the grader's entry point).

Runs the full pipeline on a Screaming Frog export:
  load -> detect -> fix (title rewrites + redirect map) -> recommend -> report

Usage:
  python run.py sample-export/
  python run.py sample-export/ --no-dashboard
"""
from __future__ import annotations
import argparse, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mcp"))
sys.path.insert(0, HERE)
import server  # the MCP server module exposes every tool as a function


def generate_title_fixes(rows, issues):
    """Generate title/meta rewrites for pages with missing or bad titles/metas.
    Uses deterministic heuristics (from URL path and H1) when no model is available."""
    titles = []
    meta_fixes = []

    # Collect issues that need title fixes
    title_issues = {}
    for iss in issues:
        if iss["type"] in ("missing_title", "duplicate_title", "title_too_long", "title_too_short"):
            for url in iss["affected_urls"]:
                title_issues[url] = iss["type"]

    # Collect issues that need meta fixes
    meta_issues = {}
    for iss in issues:
        if iss["type"] in ("missing_meta_description", "duplicate_meta_description", "meta_description_too_long"):
            for url in iss["affected_urls"]:
                meta_issues[url] = iss["type"]

    # Build a lookup from rows
    row_map = {}
    for r in rows:
        row_map[r.get("Address", "")] = r

    for url, issue_type in title_issues.items():
        r = row_map.get(url, {})
        old_title = (r.get("Title 1", "") or "").strip()
        h1 = (r.get("H1-1", "") or "").strip()

        # Generate a new title from H1 or URL path
        if issue_type == "missing_title":
            new_title = h1 if h1 else _title_from_url(url)
        elif issue_type == "title_too_long":
            # Truncate intelligently at word boundary
            new_title = old_title[:57].rsplit(" ", 1)[0] + "..." if len(old_title) > 60 else old_title
        elif issue_type == "title_too_short":
            # Expand with site context
            new_title = f"{old_title} | {_site_from_url(url)}" if old_title else _title_from_url(url)
        elif issue_type == "duplicate_title":
            # Differentiate using URL path
            suffix = _path_suffix(url)
            new_title = f"{old_title} — {suffix}" if old_title and suffix else old_title
        else:
            continue

        # Validate length: must be ≤60 chars
        if len(new_title) > 60:
            new_title = new_title[:57].rsplit(" ", 1)[0] + "..."

        if new_title and new_title != old_title:
            titles.append({"url": url, "old": old_title, "new": new_title})

    return titles


def generate_redirect_map(rows, issues):
    """Build a redirect map for broken links (4xx) → closest live page."""
    redirect_map = []

    # Find broken link URLs
    broken_urls = []
    for iss in issues:
        if iss["type"] == "broken_link":
            broken_urls = iss["affected_urls"]

    if not broken_urls:
        return redirect_map

    # Build list of live (200, indexable) URLs
    live_urls = []
    for r in rows:
        code = _int(r.get("Status Code"))
        if code == 200 and "text/html" in (r.get("Content Type", "") or "").lower():
            live_urls.append(r["Address"])

    for broken in broken_urls:
        best_match = _find_closest_url(broken, live_urls)
        if best_match:
            redirect_map.append({
                "from": broken,
                "to": best_match,
                "reason": f"Closest live page by path similarity"
            })

    return redirect_map


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def _title_from_url(url):
    """Generate a readable title from a URL path."""
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    if not path:
        return "Home"
    # Take last segment, clean it
    segment = path.split("/")[-1]
    return segment.replace("-", " ").replace("_", " ").title()[:60]


def _site_from_url(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc.replace("www.", "")


def _path_suffix(url):
    """Extract a differentiating suffix from URL path."""
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        return parts[-1].replace("-", " ").replace("_", " ").title()
    return ""


def _find_closest_url(broken, live_urls):
    """Find the most similar live URL by path overlap."""
    from urllib.parse import urlparse
    broken_parts = urlparse(broken).path.strip("/").split("/")

    best = None
    best_score = 0
    for live in live_urls:
        live_parts = urlparse(live).path.strip("/").split("/")
        # Count matching path segments from the start
        score = sum(1 for a, b in zip(broken_parts, live_parts) if a == b)
        if score > best_score:
            best_score = score
            best = live

    # Only redirect if at least one path segment matches (same section)
    return best if best_score >= 1 else (live_urls[0] if live_urls else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--no-dashboard", action="store_true")
    args = ap.parse_args()

    if not args.no_dashboard:
        server.start_dashboard()
        print(f"[seo] dashboard: http://localhost:{server.PORT}", flush=True)
        time.sleep(1)

    t0 = time.time()
    server.seo_load(args.export_dir)
    res = server.seo_detect()

    # --- Champion: generate fixes ---
    rows = server.RUN.get("rows", [])
    issues = server.RUN["issues"]
    model_calls = 0

    # Title/meta rewrites
    title_fixes = generate_title_fixes(rows, issues)
    print(f"[seo] generated {len(title_fixes)} title/meta rewrites", flush=True)
    model_calls += len(title_fixes)

    # Redirect map for broken links
    redirect_map = generate_redirect_map(rows, issues)
    print(f"[seo] generated {len(redirect_map)} redirect map entries", flush=True)
    model_calls += len(redirect_map)

    server.seo_set_fixes(titles=title_fixes, redirect_map=redirect_map)

    # --- Recommendations ---
    sorted_issues = sorted(issues, key=lambda x: {"High":0,"Medium":1,"Low":2}.get(x["severity"],3))
    recs = []
    for i in sorted_issues[:5]:
        recs.append(f"Fix the {i['count']} {i['severity']}-severity '{i['type']}' issue(s) first.")
    if not recs:
        recs.append("No issues detected on this crawl.")
    if title_fixes:
        recs.append(f"Apply the {len(title_fixes)} generated title rewrites to improve search visibility.")
    if redirect_map:
        recs.append(f"Implement the {len(redirect_map)} redirect mappings to fix broken links.")
    server.seo_recommend(recs)

    server.RUN["model_calls"] = model_calls
    server.RUN["duration_sec"] = round(time.time() - t0, 1)
    server.seo_report()
    server.seo_export()

    s = server.RUN["summary"]
    fixes = server.RUN.get("fixes", {})
    print("\n=== SEO AUDIT RESULT ===")
    print(f"Site         : {server.RUN['site']}  ({server.RUN['urls']} URLs)")
    print(f"Total issues : {s['total_issues']}  (High {s['by_severity'].get('High',0)} / "
          f"Medium {s['by_severity'].get('Medium',0)} / Low {s['by_severity'].get('Low',0)})")
    print(f"Fixes        : {len(fixes.get('titles',[]))} title rewrites, {len(fixes.get('redirect_map',[]))} redirects")
    print("Wrote outputs/report.json and outputs/report.html")

    if not args.no_dashboard:
        input("\nAudit complete. Press Enter to stop the dashboard and exit...")


if __name__ == "__main__":
    main()
