// ──────────────────────────────────────────────
// download.js  –  Open in tab + download handler
// ──────────────────────────────────────────────

const DownloadService = (() => {

    /**
     * Open a document URL in a new tab.
     */
    function openInTab(url) {
        if (!url) return;
        window.open(url, '_blank', 'noopener,noreferrer');
    }

    /**
     * Download a document. For cross-origin files (sec.gov, etc.)
     * browsers block forced downloads. In that case we open in a new
     * tab and show a toast with Ctrl+S / Print-to-PDF tip.
     */
    function download(url, filename) {
        if (!url) return;

        // Check if it's a same-origin URL (rare in our case)
        const isSameOrigin = url.startsWith(window.location.origin);

        if (isSameOrigin) {
            // Same origin: force download via blob
            forceDownload(url, filename);
            return;
        }

        // Cross-origin (sec.gov, etc.): open in new tab + show tip
        window.open(url, '_blank', 'noopener,noreferrer');

        if (typeof showToast === 'function') {
            showToast('Document opened — press Ctrl+S to save, or Print → Save as PDF');
        }
    }

    /**
     * Force download via blob (only works for same-origin or CORS-enabled URLs).
     */
    async function forceDownload(url, filename) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Fetch failed');

            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = blobUrl;

            // Clean filename
            const safe = (filename || 'document')
                .replace(/[^a-zA-Z0-9\s\-_.()]/g, '')
                .trim()
                .substring(0, 100);
            a.download = safe.endsWith('.pdf') ? safe : safe + '.pdf';

            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

            if (typeof showToast === 'function') {
                showToast('Download started!');
            }
        } catch (err) {
            // Fallback: open in new tab
            console.warn('Blob download failed:', err.message);
            window.open(url, '_blank', 'noopener,noreferrer');
            if (typeof showToast === 'function') {
                showToast('Document opened — press Ctrl+S to save, or Print → Save as PDF');
            }
        }
    }

    return { openInTab, download, forceDownload };
})();
