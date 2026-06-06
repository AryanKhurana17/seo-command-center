/* app.js — SEO Command Center live cockpit. Plain DOM + SSE, no build step. */
const $ = (id) => document.getElementById(id);

// Severity priority for sorting (lower is higher priority)
const SEVERITY_MAP = {
    'High': 0,
    'Medium': 1,
    'Low': 2
};

// Local state to keep track of issues and allow sorting
let state = {
    issues: [],
    summary: {
        total_issues: 0,
        by_severity: { High: 0, Medium: 0, Low: 0 }
    }
};

/**
 * Inject fade-in animation styles into the head
 */
function injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeInRow {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .fade-in-row {
            animation: fadeInRow 0.4s ease-out forwards;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Updates the KPI counters on the dashboard
 */
function updateKPIs(summary) {
    if (!summary) return;
    $("total-issues").textContent = summary.total_issues || 0;
    $("high-count").textContent = summary.by_severity?.High || 0;
    $("medium-count").textContent = summary.by_severity?.Medium || 0;
    $("low-count").textContent = summary.by_severity?.Low || 0;
}

/**
 * Updates the status bar and indicator dot
 */
function updateStatus(text, isRunning = false, isDone = false) {
    $("status-text").textContent = text;
    const dot = $("status-dot");
    dot.className = 'status-indicator';
    if (isRunning) dot.classList.add('running');
    if (isDone) dot.classList.add('done');
}

/**
 * Renders the issue table based on current state.issues
 * Sorts by severity (High > Medium > Low)
 */
function renderIssueTable() {
    const tbody = $("issues-table-body");

    // Sort issues by severity priority
    const sortedIssues = [...state.issues].sort((a, b) =>
        (SEVERITY_MAP[a.severity] ?? 99) - (SEVERITY_MAP[b.severity] ?? 99)
    );

    if (sortedIssues.length === 0) {
        tbody.innerHTML = `<tr class="empty"><td colspan="4" style="text-align: center; color: var(--muted); padding: 40px;">Awaiting audit data...</td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    sortedIssues.forEach(issue => {
        const tr = document.createElement('tr');
        tr.className = 'fade-in-row';

        const sevClass = `badge badge-${issue.severity.toLowerCase()}`;

        tr.innerHTML = `
            <td><span class="${sevClass}">${issue.severity}</span></td>
            <td>${issue.type}</td>
            <td style="text-align: center;">${issue.count}</td>
            <td>${issue.explanation || ''}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Updates the recommendations list
 */
function updateRecommendations(recs) {
    const list = $("recommendations-list");
    if (!recs || recs.length === 0) return;

    list.innerHTML = '';
    recs.forEach(text => {
        const div = document.createElement('div');
        div.className = 'rec-item';
        div.textContent = text;
        list.appendChild(div);
    });
}

/**
 * Main event handler for SSE and initial state
 */
function handleEvent({ event, data }) {
    console.log(`SSE Event: ${event}`, data);

    switch (event) {
        case 'snapshot':
            if (data.site) $("site-name").textContent = data.site;
            if (data.urls) $("url-count").textContent = data.urls;
            if (data.issues) {
                state.issues = data.issues;
                renderIssueTable();
            }
            if (data.summary) {
                state.summary = data.summary;
                updateKPIs(data.summary);
            }
            if (data.status) updateStatus(data.status);
            break;

        case 'loaded':
            if (data.site) $("site-name").textContent = data.site;
            if (data.urls) $("url-count").textContent = data.urls;
            updateStatus("Running audit pipeline...", true);
            break;

        case 'issue':
            state.issues.push(data);
            renderIssueTable();
            // We don't have the full summary yet, but we can increment local counters
            // if a summary event hasn't arrived. However, 'summary' event is the source of truth.
            break;

        case 'summary':
            state.summary = data;
            updateKPIs(data);
            break;

        case 'recommendations':
            updateRecommendations(data.recommendations);
            break;

        case 'saved':
        case 'exported':
            updateStatus("Done ✓", false, true);
            break;
    }
}

/**
 * Initializes the dashboard: fetches initial state then connects SSE
 */
async function init() {
    injectStyles();

    try {
        const response = await fetch('/state');
        if (response.ok) {
            const initial = await response.json();
            // The /state response is treated like a 'snapshot' event
            handleEvent({ event: 'snapshot', data: initial });
        }
    } catch (e) {
        console.error("Failed to fetch initial state:", e);
    }

    const es = new EventSource('/events');
    es.onmessage = (m) => {
        try {
            const parsed = JSON.parse(m.data);
            handleEvent(parsed);
        } catch (e) {
            console.error("Error parsing SSE message:", e, m.data);
        }
    };

    es.onerror = (e) => {
        console.error("SSE connection error:", e);
    };
}

init();
