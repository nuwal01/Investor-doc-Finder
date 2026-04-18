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

export default function HistoryPanel() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchHistory = async () => {
    setLoading(true);
    setError('');
    try {
      const token = await getToken();
      const res = await fetch(`${BACKEND_URL}/user/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load history. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchHistory(); }, []);

  const deleteItem = async (searchId) => {
    try {
      const token = await getToken();
      await fetch(`${BACKEND_URL}/user/history/${searchId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setHistory(prev => prev.filter(h => h.searchId !== searchId));
    } catch {}
  };

  const clearAll = async () => {
    try {
      const token = await getToken();
      await fetch(`${BACKEND_URL}/user/history`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setHistory([]);
    } catch {}
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <h2 className="panel-title">Search History</h2>
        {history.length > 0 && (
          <button className="clear-all-btn" onClick={clearAll}>Clear All History</button>
        )}
      </div>

      {loading && <p className="panel-loading">Loading history...</p>}
      {error && <p className="panel-error">{error}</p>}

      {!loading && !error && history.length === 0 && (
        <div className="empty-panel-state">
          <div className="empty-panel-icon">📋</div>
          <p>No search history yet.</p>
          <p>Run a search to see results here.</p>
        </div>
      )}

      <div className="doc-cards-list">
        {history.map((item) => (
          <div key={item.searchId} className="doc-panel-card">
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
              <span>{formatDate(item.fetched_at)}</span>
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
              <button className="doc-delete-btn" onClick={() => deleteItem(item.searchId)}>
                🗑️ Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
