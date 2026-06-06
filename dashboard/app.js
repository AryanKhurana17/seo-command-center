/* app.js — SEO Command Center live cockpit. Plain DOM + SSE, no build step. */
const $ = (id) => document.getElementById(id);

const SEVERITY_MAP = { 'High': 0, 'Medium': 1, 'Low': 2 };

let state = {
    urls: 0,
    issues: [],
    summary: { total_issues: 0, by_severity: { High: 0, Medium: 0, Low: 0 } }
};

// Build a human-readable detail string for each issue type
function getDetail(issue, url) {
    switch (issue.type) {
        case 'missing_title':          return 'Missing title tag';
        case 'duplicate_title':        return `Duplicate title`;
        case 'title_too_long':         return 'Title too long (> 60 chars / 561px)';
        case 'title_too_short':        return 'Title too short (< 30 chars)';
        case 'missing_meta_description': return 'Missing meta description';
        case 'duplicate_meta_description': return 'Duplicate meta description';
        case 'meta_description_too_long': return 'Meta description too long (> 155 chars)';
        case 'missing_h1':             return 'No H1 on page';
        case 'duplicate_h1':           return 'Duplicate H1';
        case 'broken_link':            return 'Returns 4xx client error';
        case 'server_error':           return 'Returns 5xx server error';
        case 'redirect':               return 'Returns 3xx redirect';
        case 'redirect_chain':         return 'Part of a redirect chain or loop';
        case 'thin_content':           return 'Fewer than 200 words';
        case 'orphan_page':            return 'Zero internal inlinks';
        case 'non_indexable_but_linked': return 'Non-indexable but receives internal links';
        case 'slow_page':              return 'Response time > 1.0s';
        case 'missing_image_alt':      return 'Image missing alt text';
        default:                       return issue.explanation || issue.type;
    }
}

function updateKPIs() {
    const s = state.summary;
    $('total-urls').textContent  = state.urls;
    $('total-issues').textContent = s.total_issues || 0;
    $('high-count').textContent   = s.by_severity?.High   || 0;
    $('medium-count').textContent = s.by_severity?.Medium || 0;
    $('low-count').textContent    = s.by_severity?.Low    || 0;
}

function renderTable() {
    const tbody = $('issues-table-body');

    // Flatten: one row per affected URL per issue, sorted by severity then issue type
    const rows = [];
    const sorted = [...state.issues].sort((a, b) =>
        (SEVERITY_MAP[a.severity] ?? 99) - (SEVERITY_MAP[b.severity] ?? 99)
    );

    for (const issue of sorted) {
        for (const url of (issue.affected_urls || [])) {
            rows.push({ url, issue });
        }
    }

    if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-msg">Awaiting audit data...</td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    for (const { url, issue } of rows) {
        const sev = issue.severity.toLowerCase();
        const tr = document.createElement('tr');
        // truncate URL for display
        const displayUrl = url.replace(/^https?:\/\/[^/]+/, '').replace(/^$/, '/') || url;
        const detail = getDetail(issue, url);

        tr.innerHTML = `
            <td class="url-cell" title="${url}">${displayUrl}</td>
            <td style="font-size:12px;font-weight:500;color:var(--text)">${issue.type}</td>
            <td><span class="badge badge-${sev}">${issue.severity}</span></td>
            <td class="detail-cell">${detail}</td>
        `;
        tbody.appendChild(tr);
    }
}

function handleEvent({ event, data }) {
    switch (event) {
        case 'snapshot':
            if (data.site)    $('site-name').textContent = data.site;
            if (data.urls)  { state.urls = data.urls; $('url-count').textContent = data.urls; }
            if (data.issues) { state.issues = data.issues; }
            if (data.summary) { state.summary = data.summary; }
            updateKPIs();
            renderTable();
            break;

        case 'loaded':
            if (data.site) $('site-name').textContent = data.site;
            if (data.urls) { state.urls = data.urls; $('url-count').textContent = data.urls; $('total-urls').textContent = data.urls; }
            break;

        case 'issue':
            state.issues.push(data);
            renderTable();
            break;

        case 'summary':
            state.summary = data;
            updateKPIs();
            break;

        case 'saved':
        case 'exported':
            break;
    }
}

async function init() {
    try {
        const r = await fetch('/state');
        if (r.ok) {
            const d = await r.json();
            handleEvent({ event: 'snapshot', data: d });
        }
    } catch (e) { console.error('Failed to fetch initial state:', e); }

    const es = new EventSource('/events');
    es.onmessage = (m) => {
        try { handleEvent(JSON.parse(m.data)); }
        catch (e) { console.error('SSE parse error:', e); }
    };
    es.onerror = (e) => console.error('SSE error:', e);
}

init();
