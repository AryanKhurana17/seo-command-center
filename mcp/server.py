"""
server.py — local MCP server + live dashboard host (one process, two faces).

  1. MCP tools over stdio  -> Claude Code calls: seo_load, seo_detect, seo_report, seo_export
  2. HTTP + SSE on localhost:7700 -> the live cockpit that fills as issues are found.

STARTER: works end to end out of the box. Extend the detectors (seo/detector.py) and
the fixes (the model-driven title rewriting / redirect map) during the Sprint.

Needs the MCP SDK to expose tools to Claude (`pip install mcp`); without it the dashboard
still runs so you can use run.py. Standard library otherwise.
"""
from __future__ import annotations
import json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASH_DIR = os.path.join(ROOT, "dashboard")
OUT_DIR = os.path.join(ROOT, "outputs")
PORT = int(os.environ.get("SEO_PORT", "7700"))
MODEL = os.environ.get("RADAR_MODEL", "gemma4:31b-cloud")

import sys
sys.path.insert(0, ROOT)
from seo import detector  # noqa: E402

RUN = {"site": None, "urls": 0, "issues": [], "summary": None, "status": "idle"}
_subs: list[queue.Queue] = []
_lock = threading.Lock()


def _emit(event, data):
    payload = json.dumps({"event": event, "data": data})
    with _lock:
        for q in list(_subs):
            try: q.put_nowait(payload)
            except Exception: pass


# ----- pipeline tools (importable by run.py without MCP) -----
def seo_load(export_dir: str) -> dict:
    rows = detector.load_rows(export_dir)
    RUN.update({"rows": rows, "urls": len(rows), "issues": [], "summary": None,
                "site": _guess_site(rows), "status": "running"})
    _emit("loaded", {"site": RUN["site"], "urls": len(rows)})
    return {"urls": len(rows), "site": RUN["site"]}


def _guess_site(rows):
    if not rows: return "unknown"
    addr = rows[0].get("Address", "")
    try:
        from urllib.parse import urlparse
        return urlparse(addr).netloc or "unknown"
    except Exception:
        return "unknown"


def seo_detect() -> dict:
    issues = detector.detect(RUN.get("rows", []))
    RUN["issues"] = issues
    RUN["summary"] = detector.summarize(issues)
    for i in issues:
        _emit("issue", i)
    _emit("summary", RUN["summary"])
    return {"detected": len(issues), "summary": RUN["summary"]}


def _report_obj() -> dict:
    return {
        "site": RUN["site"],
        "urls_crawled": RUN["urls"],
        "summary": RUN["summary"] or {"total_issues": 0, "by_severity": {}},
        "issues": RUN["issues"],
        "fixes": RUN.get("fixes", {"titles": [], "redirect_map": []}),
        "recommendations": RUN.get("recommendations", []),
        "run_meta": {"model": MODEL, "model_calls": RUN.get("model_calls", 0),
                     "duration_sec": RUN.get("duration_sec", 0)},
    }


def seo_set_fixes(titles=None, redirect_map=None) -> dict:
    RUN["fixes"] = {"titles": titles or [], "redirect_map": redirect_map or []}
    _emit("fixes", RUN["fixes"]); return {"titles": len(titles or []), "redirects": len(redirect_map or [])}


def seo_recommend(recommendations: list) -> dict:
    RUN["recommendations"] = recommendations
    _emit("recommendations", {"recommendations": recommendations}); return {"count": len(recommendations)}


def seo_report() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.json")
    json.dump(_report_obj(), open(p, "w", encoding="utf-8"), indent=2)
    RUN["status"] = "done"; _emit("saved", {"path": p}); return {"path": p}


def seo_export() -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "report.html")
    open(p, "w", encoding="utf-8").write(_render_html(_report_obj()))
    _emit("exported", {"path": p}); return {"path": p}


def _render_html(o) -> str:
    import datetime
    sev = (o["summary"] or {}).get("by_severity", {})
    total = (o["summary"] or {}).get("total_issues", 0)
    sorted_issues = sorted(o["issues"], key=lambda x: {"High":0,"Medium":1,"Low":2}.get(x["severity"],3))

    # Build issue rows
    issue_rows = ""
    for i in sorted_issues:
        top_urls = i.get("affected_urls", [])[:5]
        urls_html = "".join(f'<div class="url-item">{u}</div>' for u in top_urls)
        more = len(i.get("affected_urls", [])) - 5
        if more > 0:
            urls_html += f'<div class="url-more">+ {more} more</div>'
        issue_rows += f"""
            <tr>
                <td><span class="badge badge-{i['severity'].lower()}">{i['severity']}</span></td>
                <td class="issue-type">{i['type'].replace('_', ' ').title()}</td>
                <td class="count">{i['count']}</td>
                <td>{i.get('explanation', '')}</td>
            </tr>
            <tr class="url-row">
                <td colspan="4">
                    <details>
                        <summary class="url-toggle">View affected URLs ({i['count']})</summary>
                        <div class="url-list">{urls_html}</div>
                    </details>
                </td>
            </tr>"""

    # Build recommendations
    recs_html = ""
    for idx, r in enumerate(o.get("recommendations", []), 1):
        recs_html += f'<div class="rec-item"><span class="rec-num">{idx}</span><span>{r}</span></div>\n'

    # Build fixes section
    fixes = o.get("fixes", {})
    titles_fixes = fixes.get("titles", [])
    redirect_fixes = fixes.get("redirect_map", [])
    fixes_html = ""
    if titles_fixes:
        fix_rows = ""
        for f in titles_fixes[:10]:
            fix_rows += f"""
                <tr>
                    <td class="url-item">{f.get('url','')}</td>
                    <td class="old-val">{f.get('old','—')}</td>
                    <td class="new-val">{f.get('new','')}</td>
                </tr>"""
        more_t = len(titles_fixes) - 10
        fixes_html += f"""
            <div class="card">
                <h3>Title Rewrites ({len(titles_fixes)})</h3>
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>URL</th><th>Old Title</th><th>New Title</th></tr></thead>
                        <tbody>{fix_rows}</tbody>
                    </table>
                </div>
                {'<p class="muted">+ ' + str(more_t) + ' more rewrites</p>' if more_t > 0 else ''}
            </div>"""
    if redirect_fixes:
        redir_rows = ""
        for f in redirect_fixes[:10]:
            redir_rows += f"""
                <tr>
                    <td class="url-item">{f.get('from','')}</td>
                    <td>{f.get('to','')}</td>
                    <td>{f.get('reason','')}</td>
                </tr>"""
        more_r = len(redirect_fixes) - 10
        fixes_html += f"""
            <div class="card">
                <h3>Redirect Map ({len(redirect_fixes)})</h3>
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>From</th><th>To</th><th>Reason</th></tr></thead>
                        <tbody>{redir_rows}</tbody>
                    </table>
                </div>
                {'<p class="muted">+ ' + str(more_r) + ' more redirects</p>' if more_r > 0 else ''}
            </div>"""

    meta = o.get("run_meta", {})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SEO Audit Report — {o['site']}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #1a1a1f;
            --card: #242428;
            --border: #3a3a42;
            --text: #f8f7f4;
            --muted: #c8c5be;
            --accent: #FF0000;
            --yellow: #e2b53e;
            --green: #22c55e;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 0;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        .wrap {{ max-width: 900px; margin: 0 auto; padding: 48px 32px; }}

        /* Header */
        .report-header {{
            margin-bottom: 40px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        .report-header h1 {{
            font-size: 32px;
            font-weight: 700;
            margin: 0 0 8px;
            letter-spacing: -0.02em;
        }}
        .report-header .sub {{
            color: var(--muted);
            font-size: 16px;
            margin: 0;
        }}
        .report-header .date {{
            color: var(--muted);
            font-size: 13px;
            margin-top: 8px;
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        .kpi-value {{
            font-size: 36px;
            font-weight: 700;
            display: block;
            margin-bottom: 4px;
        }}
        .kpi-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            font-weight: 600;
        }}
        .kpi.high .kpi-value {{ color: var(--accent); }}
        .kpi.medium .kpi-value {{ color: var(--yellow); }}

        /* Cards */
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .card h3 {{
            font-size: 18px;
            margin: 0 0 16px;
            font-weight: 600;
        }}

        /* Tables */
        .table-wrap {{ overflow-x: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            font-size: 11px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 600;
            text-align: left;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            background: rgba(0,0,0,0.15);
        }}
        td {{
            text-align: left;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }}
        tr:last-child td {{ border-bottom: none; }}
        .count {{ text-align: center; font-weight: 600; }}
        .issue-type {{ font-weight: 500; }}

        /* Badges */
        .badge {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        .badge-high {{ background: var(--accent); color: #fff; }}
        .badge-medium {{ background: var(--yellow); color: var(--bg); }}
        .badge-low {{ background: var(--border); color: var(--muted); }}

        /* URL details */
        .url-row td {{
            padding: 0 16px 12px;
            border-bottom: 1px solid var(--border);
        }}
        .url-toggle {{
            cursor: pointer;
            color: var(--muted);
            font-size: 12px;
            font-weight: 500;
            padding: 4px 0;
        }}
        .url-toggle:hover {{ color: var(--accent); }}
        .url-list {{
            margin-top: 8px;
            padding: 12px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
        }}
        .url-item {{
            font-size: 12px;
            color: var(--muted);
            padding: 3px 0;
            word-break: break-all;
        }}
        .url-more {{
            font-size: 11px;
            color: var(--accent);
            margin-top: 4px;
            font-weight: 500;
        }}
        .old-val {{ color: var(--accent); text-decoration: line-through; opacity: 0.7; }}
        .new-val {{ color: var(--green); font-weight: 500; }}

        /* Recommendations */
        .rec-item {{
            display: flex;
            gap: 12px;
            align-items: flex-start;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
            color: var(--muted);
            font-size: 14px;
        }}
        .rec-item:last-child {{ border-bottom: none; }}
        .rec-num {{
            background: var(--accent);
            color: #fff;
            font-size: 11px;
            font-weight: 700;
            min-width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}

        /* Footer */
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            color: var(--muted);
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .muted {{ color: var(--muted); font-size: 13px; }}

        /* Print styles */
        @media print {{
            body {{ background: #fff; color: #1a1a1f; padding: 20px; }}
            .card {{ border-color: #ddd; background: #f9f9f9; }}
            .kpi {{ background: #f9f9f9; border-color: #ddd; }}
            .badge-high {{ background: #dc2626; }}
            .url-list {{ background: #f0f0f0; }}
        }}
        @media (max-width: 640px) {{
            .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .wrap {{ padding: 24px 16px; }}
        }}
    </style>
</head>
<body>
<div class="wrap">
    <div class="report-header">
        <h1>SEO Audit Report</h1>
        <p class="sub">{o['site']} &middot; {o['urls_crawled']} URLs crawled</p>
        <div class="date">Generated {now} &middot; Model: {meta.get('model', 'N/A')} &middot; {meta.get('model_calls', 0)} model calls &middot; {meta.get('duration_sec', 0)}s runtime</div>
    </div>

    <div class="kpi-grid">
        <div class="kpi">
            <span class="kpi-value">{total}</span>
            <span class="kpi-label">Total Issues</span>
        </div>
        <div class="kpi high">
            <span class="kpi-value">{sev.get('High', 0)}</span>
            <span class="kpi-label">High</span>
        </div>
        <div class="kpi medium">
            <span class="kpi-value">{sev.get('Medium', 0)}</span>
            <span class="kpi-label">Medium</span>
        </div>
        <div class="kpi">
            <span class="kpi-value">{sev.get('Low', 0)}</span>
            <span class="kpi-label">Low</span>
        </div>
    </div>

    <div class="card">
        <h3>Issues (Prioritized by Severity)</h3>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr><th style="width:100px">Severity</th><th>Issue</th><th style="width:80px;text-align:center">Count</th><th>Description</th></tr>
                </thead>
                <tbody>
                    {issue_rows or '<tr><td colspan="4" class="muted" style="text-align:center;padding:32px">No issues detected.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    {fixes_html}

    <div class="card">
        <h3>Recommendations</h3>
        {recs_html or '<p class="muted">No recommendations generated.</p>'}
    </div>

    <div class="footer">
        <span>Generated by SEO Command Center</span>
        <span>Model: {meta.get('model', '')} &middot; {o['urls_crawled']} URLs &middot; {total} issues</span>
    </div>
</div>
</body>
</html>"""


# ----- dashboard HTTP host -----
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache"); self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            p = os.path.join(DASH_DIR, "index.html")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "no dashboard")
        elif self.path == "/app.js":
            p = os.path.join(DASH_DIR, "app.js")
            self._send(200, open(p, encoding="utf-8").read() if os.path.exists(p) else "", "application/javascript")
        elif self.path == "/state":
            self._send(200, json.dumps({k: v for k, v in RUN.items() if k != "rows"}), "application/json")
        elif self.path == "/events":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            q = queue.Queue()
            with _lock: _subs.append(q)
            try:
                snap = {k: v for k, v in RUN.items() if k != "rows"}
                self.wfile.write(f"data: {json.dumps({'event':'snapshot','data':snap})}\n\n".encode()); self.wfile.flush()
                while True:
                    try: self.wfile.write(f"data: {q.get(timeout=15)}\n\n".encode())
                    except queue.Empty: self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception: pass
            finally:
                with _lock:
                    if q in _subs: _subs.remove(q)
        else: self._send(404, "not found")


def start_dashboard(port=PORT):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _run_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print(f"[seo] MCP SDK not found. Dashboard only at http://localhost:{PORT}", flush=True)
        while True: time.sleep(3600)
    mcp = FastMCP("seo-command-center")

    @mcp.tool()
    def load(export_dir: str) -> dict:
        """Load a Screaming Frog export directory (expects internal_all.csv)."""
        return seo_load(export_dir)

    @mcp.tool()
    def detect_issues() -> dict:
        """Run the SEO rulebook detectors over the loaded crawl."""
        return seo_detect()

    @mcp.tool()
    def set_fixes(titles: list = None, redirect_map: list = None) -> dict:
        """Attach the model-written title rewrites and the redirect map."""
        return seo_set_fixes(titles, redirect_map)

    @mcp.tool()
    def recommend(recommendations: list) -> dict:
        """Attach the prioritized recommendations."""
        return seo_recommend(recommendations)

    @mcp.tool()
    def write_report() -> dict:
        """Write outputs/report.json."""
        return seo_report()

    @mcp.tool()
    def export_report() -> dict:
        """Write outputs/report.html (the client deliverable)."""
        return seo_export()

    mcp.run()


if __name__ == "__main__":
    start_dashboard()
    print(f"[seo] dashboard live at http://localhost:{PORT}", flush=True)
    _run_mcp()
