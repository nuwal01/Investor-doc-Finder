// Utility helper functions for Investor-Doc-Finder

/**
 * Escapes HTML special characters to prevent XSS
 */
export function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

/**
 * Sanitizes a filename for safe download
 */
export function sanitizeFilename(name) {
  if (!name) return 'document';
  return name
    .replace(/[^a-z0-9\s\-_.]/gi, '_')
    .replace(/\s+/g, '_')
    .toLowerCase()
    .slice(0, 100);
}

/**
 * Delays execution for specified milliseconds
 */
export function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Maps confidence score to badge class
 */
export function getConfidenceClass(score) {
  if (score >= 1.80) return 'high';
  if (score >= 1.20) return 'medium';
  return 'low';
}

/**
 * Triggers a document download
 */
export function downloadDocument(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = sanitizeFilename(filename);
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Opens a document in a new tab
 */
export function openDocument(url) {
  window.open(url, '_blank', 'noopener,noreferrer');
}

/**
 * Formats a company name + doc type into a readable title
 */
export function formatDocumentTitle(companyName, docType, year) {
  if (!companyName) return 'Document';
  let title = companyName;
  if (docType) {
    title += ` - ${docType}`;
  }
  if (year) {
    title += ` (${year})`;
  }
  return title;
}
