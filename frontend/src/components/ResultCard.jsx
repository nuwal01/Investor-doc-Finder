import { useState } from 'react';
import { auth } from '../firebase-config';
import { getConfidenceClass, openDocument, downloadDocument, formatDocumentTitle } from '../utils/helpers';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default function ResultCard({ result }) {
  const { url, source, confidence, score, company_name, doc_type, year, country, sector } = result;
  const confidenceClass = getConfidenceClass(confidence || 0);
  const title = formatDocumentTitle(company_name, doc_type, year);
  const filename = `${company_name || 'document'}_${doc_type || 'report'}_${year || ''}`.replace(/\s+/g, '_');

  const [saveState, setSaveState] = useState('idle'); // idle | saving | saved | error

  const handleSave = async () => {
    if (saveState === 'saved' || saveState === 'saving') return;
    setSaveState('saving');
    try {
      const u = auth.currentUser;
      if (!u) throw new Error('Not authenticated');
      const token = await u.getIdToken();
      const res = await fetch(`${BACKEND_URL}/user/library`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          url: url || '',
          company_name: company_name || '',
          doc_type: doc_type || '',
          year: year || 0,
          source: source || '',
          confidence: typeof confidence === 'string' ? confidence : (confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low'),
          score: score || 0,
          country: country || '',
          sector: sector || '',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaveState('saved');
    } catch {
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 3000);
    }
  };

  return (
    <div className="result-card">
      <div className="result-label">Document Found</div>

      <div className="result-header">
        <h3 className="result-title">{title}</h3>
        <span className={`confidence-badge ${confidenceClass}`}>
          {confidenceClass}
        </span>
      </div>

      <a
        href={url}
        className="result-url"
        target="_blank"
        rel="noopener noreferrer"
      >
        {url}
      </a>

      <div className="result-meta">
        Source: {source || 'Unknown'}
        {score != null && <span style={{ marginLeft: '12px' }}>Score: {Number(score).toFixed(2)}</span>}
      </div>

      <div className="result-actions">
        <button
          className="result-btn"
          onClick={() => openDocument(url)}
        >
          Open ↗
        </button>
        <button
          className="result-btn"
          onClick={() => downloadDocument(url, filename)}
        >
          Download ↓
        </button>
        <button
          className={`save-btn ${saveState === 'saved' ? 'saved' : ''}`}
          onClick={handleSave}
          disabled={saveState === 'saving' || saveState === 'saved'}
          title="Save to Library"
        >
          {saveState === 'saved' ? '✅ Saved' : saveState === 'saving' ? 'Saving…' : saveState === 'error' ? 'Failed to save' : '⭐ Save'}
        </button>
      </div>
    </div>
  );
}
