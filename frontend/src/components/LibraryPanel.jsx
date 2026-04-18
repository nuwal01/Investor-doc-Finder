import { useState, useEffect } from 'react';
import { auth } from '../firebase-config';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function confClass(c) {
  return ['high', 'medium', 'low'].includes(c) ? c : 'low';
}

async function getToken() {
  const u = auth.currentUser;
  if (!u) throw new Error('Not authenticated');
  return u.getIdToken();
}

export default function LibraryPanel() {
  const [library, setLibrary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchLibrary = async () => {
    setLoading(true);
    setError('');
    try {
      const token = await getToken();
      const res = await fetch(`${BACKEND_URL}/user/library`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLibrary(Array.isArray(data.library) ? data.library : []);
    } catch {
      setError('Failed to load library. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLibrary(); }, []);

  const removeItem = async (docId) => {
    try {
      const token = await getToken();
      await fetch(`${BACKEND_URL}/user/library/${docId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setLibrary(prev => prev.filter(d => d.doc_id !== docId));
    } catch {}
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <h2 className="panel-title">Document Library</h2>
      </div>

      {loading && <p className="panel-loading">Loading library...</p>}
      {error && <p className="panel-error">{error}</p>}

      {!loading && !error && library.length === 0 && (
        <div className="empty-panel-state">
          <div className="empty-panel-icon">⭐</div>
          <p>No saved documents yet.</p>
          <p>Star a search result to save it here.</p>
        </div>
      )}

      <div className="doc-cards-list">
        {library.map((item) => (
          <div key={item.doc_id} className="doc-panel-card">
            <div className="doc-card-header">
              <h3 className="doc-card-title">
                {item.company_name || 'Unknown'} &mdash;{' '}
                {(item.doc_type || '').replace(/_/g, ' ')} {item.year}
              </h3>
              <span className={`confidence-badge ${confClass(item.confidence)}`}>
                {item.confidence || 'low'}
              </span>
            </div>

            <div className="doc-card-tags">
              {item.source && <span className="source-badge">{item.source}</span>}
              {item.country && <span className="doc-tag">{item.country}</span>}
              {item.sector && <span className="doc-tag">{item.sector}</span>}
            </div>

            <div className="doc-card-meta">
              <span>Score: {(item.score || 0).toFixed(2)}</span>
              <span className="meta-sep">·</span>
              <span>Saved {formatDate(item.saved_at)}</span>
            </div>

            {item.url && (
              <a
                href={item.url}
                className="result-url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.url}
              </a>
            )}

            <div className="doc-card-actions">
              {item.url && (
                <button
                  className="result-btn"
                  onClick={() => window.open(item.url, '_blank', 'noopener,noreferrer')}
                >
                  📄 Open Document
                </button>
              )}
              <button className="doc-delete-btn" onClick={() => removeItem(item.doc_id)}>
                🗑️ Remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
