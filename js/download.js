// ──────────────────────────────────────────────
// download.js  –  Open in tab + one-click download
// ──────────────────────────────────────────────

const DownloadService = (() => {

    /**
     * Open a document URL in a new tab.
     * @param {string} url
     */
    function openInTab(url) {
        if (!url) return;
        window.open(url, '_blank', 'noopener,noreferrer');
    }

    /**
     * Trigger a download for the given URL.
     * For PDFs and other same-origin files the browser will download directly.
     * For cross-origin files we open in a new tab (browser decides download vs display).
     * @param {string} url
     * @param {string} filename  – Suggested file name
     */
    function download(url, filename) {
        if (!url) return;

        // Try using an anchor with download attribute
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';

        // If we can suggest a filename, do so
        if (filename) {
            // Clean the filename for safe filesystem use
            const safe = filename
                .replace(/[^a-zA-Z0-9\s\-_.()]/g, '')
                .trim()
                .substring(0, 100);
            a.download = safe.endsWith('.pdf') ? safe : safe + '.pdf';
        }

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    /**
     * Try to fetch the file as a blob and trigger a true download.
     * Falls back to the simple method if CORS blocks us.
     * @param {string} url
     * @param {string} filename
     */
    async function forceDownload(url, filename) {
        try {
            const response = await fetch(url, { mode: 'cors' });
            if (!response.ok) throw new Error('Fetch failed');

            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename || 'document.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            // Clean up
            setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
        } catch (err) {
            // Fallback: opening in a new tab if CORS prevents blob download
            console.warn('Blob download failed, falling back to open:', err.message);
            download(url, filename);
        }
    }

    // Public API
    return {
        openInTab,
        download,
        forceDownload
    };
})();
