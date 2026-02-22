// ──────────────────────────────────────────────
// search.js  –  Call Cloud Function & render results
// ──────────────────────────────────────────────
// This file runs on results.html.
// It reads ?q= from the URL, calls the searchDocuments
// Cloud Function, and renders cards into #resultsGrid.

document.addEventListener('DOMContentLoaded', () => {

    // ── Configuration ──────────────────────────
    // Auto-detect: local dev server vs deployed Cloud Function
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    // Automatically points to local dev-server, Render server, or Vercel serverless function
    const FUNCTION_URL = '/api/searchDocuments';

    // ── DOM refs ───────────────────────────────
    const searchTitle = document.getElementById('searchTitle');
    const resultCount = document.getElementById('resultCount');
    const loadingEl = document.getElementById('loadingIndicator');
    const resultsGrid = document.getElementById('resultsGrid');
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');

    // ── Read query from URL ────────────────────
    const params = new URLSearchParams(window.location.search);
    const query = params.get('q') || '';

    if (searchInput && query) searchInput.value = query;

    if (query) {
        searchTitle.textContent = `Results for "${query}"`;
        performSearch(query);
    } else {
        searchTitle.textContent = 'Enter a search query';
        if (loadingEl) loadingEl.classList.add('hidden');
    }

    // ── Re-search from this page ───────────────
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const newQuery = searchInput.value.trim();
            if (!newQuery) return;
            // Update URL so the page can be refreshed / shared
            window.location.href = `results.html?q=${encodeURIComponent(newQuery)}`;
        });
    }

    // ── Main search function ───────────────────
    async function performSearch(q) {
        showLoading(true);

        try {
            const url = `${FUNCTION_URL}?q=${encodeURIComponent(q)}`;
            const res = await fetch(url);

            if (!res.ok) throw new Error(`Server returned ${res.status}`);

            const data = await res.json();
            const results = data.results || [];

            // Record search in Firestore (if user is logged in)
            if (typeof FirestoreService !== 'undefined' && typeof auth !== 'undefined' && auth.currentUser) {
                FirestoreService.recordSearch(q, results.length).catch(() => { });
            }

            renderResults(results, q);
        } catch (err) {
            console.error('Search error:', err);
            showError(q);
        }
    }

    // ── Render result cards ────────────────────
    function renderResults(results, query) {
        showLoading(false);

        if (results.length === 0) {
            resultsGrid.classList.remove('hidden');
            resultsGrid.innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:3rem 0;">
          <h3 style="margin-bottom:1rem;">No documents found</h3>
          <p style="color:var(--text-muted);">Try a different search query, e.g. "Apple 10-K 2023"</p>
        </div>`;
            resultCount.textContent = '0 documents found';
            return;
        }

        resultCount.textContent = `${results.length} document${results.length !== 1 ? 's' : ''} found`;
        resultsGrid.innerHTML = '';
        resultsGrid.classList.remove('hidden');

        results.forEach((doc, idx) => {
            const card = document.createElement('div');
            card.className = 'doc-card';
            card.style.animationDelay = `${idx * 0.05}s`;

            const tickerBadge = doc.ticker
                ? `<span class="doc-tag" style="background:var(--primary-color);color:#fff;">${escHtml(doc.ticker)}</span>`
                : '';

            card.innerHTML = `
        <div class="doc-meta">
          <span class="doc-tag">${escHtml(doc.type || 'Document')}</span>
          ${tickerBadge}
          <span>${escHtml(doc.source || '')}</span>
        </div>
        <h3 class="doc-title">${escHtml(doc.title || 'Untitled')}</h3>
        <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:0.5rem;">
          ${escHtml(doc.company || '')}${doc.date ? ' · ' + escHtml(doc.date) : ''}
        </p>
        ${doc.description ? `<p style="color:var(--text-muted);font-size:0.8rem;margin-bottom:0.75rem;opacity:0.7;">${escHtml(doc.description).substring(0, 150)}${doc.description.length > 150 ? '…' : ''}</p>` : ''}
        <div class="doc-actions" style="margin-top:auto;">
          <a href="${escHtml(doc.url)}" target="_blank" rel="noopener" class="btn-primary">Open</a>
          <button class="btn-outline download-btn" data-url="${escHtml(doc.url)}" data-title="${escHtml(doc.title)}">Download</button>
          <button class="btn-outline save-btn"
                  data-title="${escHtml(doc.title)}"
                  data-company="${escHtml(doc.company)}"
                  data-type="${escHtml(doc.type)}"
                  data-url="${escHtml(doc.url)}"
                  data-date="${escHtml(doc.date)}"
                  data-source="${escHtml(doc.source)}">Save</button>
        </div>
      `;
            resultsGrid.appendChild(card);
        });

        // Wire Download buttons
        resultsGrid.querySelectorAll('.download-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (typeof DownloadService !== 'undefined') {
                    DownloadService.download(btn.dataset.url, btn.dataset.title);
                } else {
                    window.open(btn.dataset.url, '_blank');
                }
            });
        });

        // Wire Save buttons
        resultsGrid.querySelectorAll('.save-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!auth.currentUser) {
                    showToast('Please sign in to save documents.');
                    return;
                }
                try {
                    btn.disabled = true;
                    btn.textContent = 'Saving…';

                    await FirestoreService.saveDocument({
                        title: btn.dataset.title,
                        company: btn.dataset.company,
                        docType: btn.dataset.type,
                        url: btn.dataset.url,
                        date: btn.dataset.date,
                        source: btn.dataset.source
                    });

                    btn.textContent = '✓ Saved';
                    btn.classList.add('btn-saved');
                    showToast('Document saved to your dashboard!');
                } catch (err) {
                    btn.disabled = false;
                    btn.textContent = 'Save';
                    showToast('Failed to save. Please try again.');
                    console.error(err);
                }
            });
        });
    }

    // ── Error state ────────────────────────────
    function showError(query) {
        showLoading(false);
        resultsGrid.classList.remove('hidden');
        resultsGrid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:3rem 0;">
        <h3 style="margin-bottom:1rem;">Something went wrong</h3>
        <p style="color:var(--text-muted);margin-bottom:1.5rem;">
          Unable to fetch results for "${escHtml(query)}". Please check your connection or try again later.
        </p>
        <button class="btn-primary" onclick="location.reload()">Retry</button>
      </div>`;
        resultCount.textContent = '';
    }

    // ── Helpers ────────────────────────────────
    function showLoading(show) {
        if (loadingEl) {
            if (show) loadingEl.classList.remove('hidden');
            else loadingEl.classList.add('hidden');
        }
    }

    function escHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
});
