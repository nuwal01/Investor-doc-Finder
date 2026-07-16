// IDF frontend logic. Every card field is bound live to /search JSON — nothing
// hardcoded, no field displayed that the payload doesn't actually carry.

const EXAMPLES = [
  "Apple 2022 annual report",
  "Microsoft 2023 10-K",
  "Tesla 2021 annual report",
  "Infosys FY2023 annual report",
];

const $ = (id) => document.getElementById(id);
const form = $("search-form");
const input = $("query");
const sendBtn = $("send-btn");
const output = $("output");

// Escape everything from the payload — company names / reasons are untrusted text.
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Anonymous session id: generated client-side, stored in localStorage (not a
// cookie — no server round-trip or consent needed, and it's passed as a query
// param, which EventSource requires since it can't set custom headers).
function sessionId() {
  let sid = localStorage.getItem("idf_session_id");
  if (!sid) {
    sid = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    localStorage.setItem("idf_session_id", sid);
  }
  return sid;
}

// ── Search history (per session) ─────────────────────────────────────────────
async function loadHistory() {
  try {
    const resp = await fetch("/history?session_id=" + encodeURIComponent(sessionId()));
    const data = await resp.json();
    renderHistory(data.history || []);
  } catch (_) {
    /* history is a non-critical panel — never block search on it */
  }
}

function renderHistory(items) {
  const panel = $("history");
  const list = $("history-list");
  if (!items.length) {
    panel.hidden = true;
    list.innerHTML = "";
    return;
  }
  panel.hidden = false;
  list.innerHTML = items.map((it) => {
    const ok = it.status === "ok";
    const badge = ok
      ? '<span class="hbadge ok">found</span>'
      : '<span class="hbadge miss">not found</span>';
    const sub = ok && it.resolved_company
      ? esc(it.resolved_company) + (it.matched_fy ? " · " + esc(String(it.matched_fy)) : "")
      : "";
    return `<li class="history-item" data-q="${esc(it.query_text)}">
              <div class="hq">${esc(it.query_text)}</div>
              ${sub ? `<div class="hsub">${sub}</div>` : ""}
              ${badge}
            </li>`;
  }).join("");
  // Click a past search → re-populate the box and re-run it.
  list.querySelectorAll(".history-item").forEach((el) => {
    el.addEventListener("click", () => { input.value = el.dataset.q; submit(); });
  });
}

// Example chips populate + submit the box on click.
const examplesEl = $("examples");
EXAMPLES.forEach((ex) => {
  const b = document.createElement("button");
  b.className = "chip";
  b.type = "button";
  b.textContent = ex;
  b.addEventListener("click", () => { input.value = ex; submit(); });
  examplesEl.appendChild(b);
});

form.addEventListener("submit", (e) => { e.preventDefault(); submit(); });

// Populate the history panel for this session on load.
loadHistory();

// Live progress via SSE (/search/stream). The status line updates in place with
// each pipeline step in plain language; completed steps stack below it. The full
// raw-log trace is still rendered from the final result (renderTrace), unchanged.
function submit() {
  const query = input.value.trim();
  if (!query) return;

  sendBtn.disabled = true;
  output.innerHTML =
    '<ul class="steps" id="steps" style="list-style:none;padding:0;margin:0;"></ul>';
  const stepsEl = $("steps");
  let done = false;

  const es = new EventSource(
    "/search/stream?query=" + encodeURIComponent(query) +
    "&session_id=" + encodeURIComponent(sessionId()));

  es.onmessage = (e) => {
    let ev;
    try { ev = JSON.parse(e.data); } catch (_) { return; }

    if (ev.type === "step") {
      // Settle the previously-active step (drop its spinner, mark it done),
      // then append the new active step with a live spinner.
      const prev = stepsEl.lastElementChild;
      if (prev) prev.textContent = "✓ " + prev.dataset.msg;
      const li = document.createElement("li");
      li.className = "status";
      li.style.margin = "0.35rem 0 0";
      li.dataset.msg = ev.message;
      li.innerHTML = '<span class="spinner"></span>' + esc(ev.message);
      stepsEl.appendChild(li);
    } else if (ev.type === "result") {
      done = true;
      es.close();
      render({ ...ev.result, logs: ev.logs });
      sendBtn.disabled = false;
      loadHistory();  // refresh the panel with this just-completed search
    }
  };

  // EventSource fires onerror both on real connection failure and when the
  // server closes the stream. If we already rendered a result, ignore it;
  // otherwise surface a failure card (and stop the auto-reconnect).
  es.onerror = () => {
    if (done) return;
    es.close();
    output.innerHTML =
      '<div class="card giveup"><p class="reason">Request failed</p>' +
      '<p class="suggest">The live search stream was interrupted. Please try again.</p></div>';
    sendBtn.disabled = false;
  };
}

function render(d) {
  const trace = renderTrace(d.logs);
  output.innerHTML = (d.ok ? successCard(d) : giveupCard(d)) + trace;
  if (d.ok) wireDownload(d);
}

// A PDF is servable when the result is already a PDF, or it's an EDGAR filing we
// convert on the fly. Other HTML sources have no PDF → only the "Open original" link.
function canDownloadPdf(d) {
  return !!d.is_pdf || d.source === "edgar";
}

function downloadUrl(d) {
  const p = new URLSearchParams({
    url: d.url || "",
    source: d.source || "",
    is_pdf: d.is_pdf ? "true" : "false",
    company: d.company || "",
    fy: d.matched_fy || d.fiscal_year || "",
  });
  return "/download?" + p.toString();
}

// Fetch the bytes and trigger a real file download via a Blob + temporary <a
// download> click — no new tab. On failure, show the error and leave the
// "Open original" link as the fallback.
function wireDownload(d) {
  const btn = $("dl-btn");
  if (!btn) return;
  const msg = $("dl-msg");
  btn.addEventListener("click", async () => {
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Preparing…";
    if (msg) msg.textContent = "";
    try {
      const resp = await fetch(downloadUrl(d));
      if (!resp.ok) {
        let detail = `Download failed (${resp.status})`;
        try { detail = (await resp.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const blob = await resp.blob();
      const cd = resp.headers.get("Content-Disposition") || "";
      const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
      const plain = /filename="?([^";]+)"?/i.exec(cd);
      const name = star ? decodeURIComponent(star[1]) : (plain ? plain[1] : "document.pdf");
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (err) {
      if (msg) msg.textContent = err.message || String(err);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });
}

function successCard(d) {
  const fmt = d.is_pdf ? '<span class="badge pdf">PDF</span>'
                       : '<span class="badge html">HTML</span>';
  // form_type can be "" (e.g. Apple) — omit it rather than render a bare " · FY".
  const parts = [];
  if (d.form_type) parts.push(esc(d.form_type));
  // matched_fy is inconsistent: EDGAR → "2022", Indian web_search → "FY2022-23".
  // Prefix "FY" only when it isn't already there, else it doubles to "FYFY...".
  if (d.matched_fy) {
    const fy = String(d.matched_fy);
    parts.push(esc(/^fy/i.test(fy) ? fy : "FY" + fy));
  }
  const subline = parts.join(" · ");

  return `
    <div class="card success">
      <h2>${esc(d.company)} <span class="country">${esc(d.country)}</span>${fmt}</h2>
      ${subline ? `<p class="subline">${subline}</p>` : ""}
      <div class="meta">
        <div class="row"><span class="label">Document:</span> ${esc(d.doc_returned)}</div>
        <div class="row"><span class="label">Source:</span> ${esc(d.source)}</div>
      </div>
      <div class="urlbox">${esc(d.url)}</div>
      ${canDownloadPdf(d) ? '<button class="btn primary" id="dl-btn">Download PDF</button>' : ""}
      <a class="btn ${canDownloadPdf(d) ? "neutral" : "primary"}" href="${esc(d.url)}" target="_blank" rel="noopener">Open original</a>
      <span id="dl-msg" class="dl-msg"></span>
    </div>`;
}

// Exact 3-tier treatment mirrored from streamlit_app.py.
const FALLBACK_TIERS = {
  verified: {
    cls: "verified",
    title: "Company investor-relations site (verified)",
    body: "Curated official domain.",
    btn: "primary",
    btnLabel: "Open IR site",
  },
  uncertain: {
    cls: "uncertain",
    title: "Possible investor-relations site — may not be an exact match",
    body: "This may not be the exact company if your search terms were ambiguous.",
    btn: "amber",
    btnLabel: "Open (uncertain match)",
  },
  unverified: {
    cls: "unverified",
    title: "Unverified suggestion — treat as a lead, not a verified document",
    body: "A best-effort “investor relations” web-search result. Not checked: it may be the wrong company or not a report at all.",
    btn: "neutral",
    btnLabel: "Open suggestion",
  },
};

function giveupCard(d) {
  let html = `<div class="card giveup"><p class="reason">${esc(d.reason)}</p>`;

  const fb = d.fallback;
  if (fb && fb.url) {
    const t = FALLBACK_TIERS[fb.confidence] || FALLBACK_TIERS.unverified;
    html += `
      <div class="notice ${t.cls}">
        <span class="title">${t.title}</span>
        ${t.body}
      </div>
      <a class="btn ${t.btn}" href="${esc(fb.url)}" target="_blank" rel="noopener">${t.btnLabel}</a>
      <p class="caption">Fallback: tier ${esc(fb.tier)} · confidence ${esc(fb.confidence)}</p>`;
  } else {
    html +=
      '<p class="suggest">Try a more specific query, check the company name spelling, ' +
      "or add the country name (e.g. “Reliance Industries India 2022 annual report”).</p>";
  }

  return html + "</div>";
}

function renderTrace(logs) {
  if (!logs || !logs.length) return "";
  return `
    <details class="trace">
      <summary>Pipeline trace (${logs.length} log lines)</summary>
      <pre>${esc(logs.join("\n"))}</pre>
    </details>`;
}
