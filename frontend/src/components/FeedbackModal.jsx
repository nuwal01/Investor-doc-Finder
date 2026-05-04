import { useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const ISSUE_OPTIONS = [
  { value: 'not_found',       label: 'Document not found' },
  { value: 'wrong_document',  label: 'Wrong document returned' },
  { value: 'wrong_year',      label: 'Wrong year' },
  { value: 'other',           label: 'Other' },
];

export default function FeedbackModal({
  onClose,
  company_name = '',
  doc_type = '',
  year = 0,
  original_query = '',
  url_returned = null,
  preset_issue_type = 'not_found',
}) {
  const [issueType, setIssueType]   = useState(preset_issue_type);
  const [userNote, setUserNote]     = useState('');
  const [submitState, setSubmitState] = useState('idle'); // idle | submitting | success | error

  const contextLabel = [
    company_name,
    doc_type ? doc_type.replace(/_/g, ' ') : '',
    year || '',
  ].filter(Boolean).join(' · ');

  const handleSubmit = async () => {
    if (submitState === 'submitting') return;
    setSubmitState('submitting');
    try {
      const res = await fetch(`${BACKEND_URL}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name,
          doc_type,
          year,
          original_query,
          url_returned,
          issue_type: issueType,
          user_note: userNote.slice(0, 500),
        }),
      });
      const data = await res.json();
      if (data.success) {
        setSubmitState('success');
        setTimeout(() => {
          setSubmitState('idle');
          setUserNote('');
          onClose();
        }, 2000);
      } else {
        setSubmitState('error');
        setTimeout(() => setSubmitState('idle'), 3000);
      }
    } catch {
      setSubmitState('error');
      setTimeout(() => setSubmitState('idle'), 3000);
    }
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.65)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--nav-bg)',
          border: '1px solid var(--accent)',
          borderRadius: '12px',
          padding: '32px',
          width: '100%',
          maxWidth: '480px',
          fontFamily: 'var(--font-mono)',
          color: 'var(--nav-text)',
        }}
        onClick={e => e.stopPropagation()}
      >
        <h2 style={{ fontSize: '1.05rem', marginBottom: '20px', color: 'var(--accent-light)' }}>
          Report an Issue
        </h2>

        {/* Search context — read-only */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px', letterSpacing: '0.05em' }}>
            SEARCH CONTEXT
          </label>
          <div style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '6px',
            padding: '10px 12px',
            fontSize: '0.82rem',
            opacity: 0.75,
          }}>
            {contextLabel || original_query || 'Unknown'}
          </div>
        </div>

        {/* Issue type */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px', letterSpacing: '0.05em' }}>
            WHAT WENT WRONG?
          </label>
          <select
            value={issueType}
            onChange={e => setIssueType(e.target.value)}
            style={{
              width: '100%',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid var(--accent)',
              borderRadius: '6px',
              padding: '10px 12px',
              fontSize: '0.85rem',
              color: 'var(--nav-text)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {ISSUE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} style={{ background: '#1c2b1c' }}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Additional notes */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px', letterSpacing: '0.05em' }}>
            ADDITIONAL NOTES (OPTIONAL)
          </label>
          <textarea
            value={userNote}
            onChange={e => setUserNote(e.target.value.slice(0, 500))}
            placeholder="e.g. The correct report is available at..."
            rows={3}
            style={{
              width: '100%',
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '6px',
              padding: '10px 12px',
              fontSize: '0.82rem',
              color: 'var(--nav-text)',
              fontFamily: 'var(--font-mono)',
              resize: 'vertical',
              outline: 'none',
            }}
          />
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textAlign: 'right', marginTop: '4px' }}>
            {userNote.length}/500
          </div>
        </div>

        {/* Feedback messages */}
        {submitState === 'success' && (
          <p style={{ color: 'var(--accent-light)', fontSize: '0.85rem', marginBottom: '16px' }}>
            ✓ Thanks — we'll look into this.
          </p>
        )}
        {submitState === 'error' && (
          <p style={{ color: 'var(--error)', fontSize: '0.85rem', marginBottom: '16px' }}>
            ✗ Submission failed. Please try again.
          </p>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.2)',
              color: 'var(--nav-text)',
              padding: '8px 18px',
              borderRadius: '6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitState === 'submitting' || submitState === 'success'}
            style={{
              background: 'var(--accent)',
              border: 'none',
              color: '#fff',
              padding: '8px 18px',
              borderRadius: '6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              cursor: (submitState === 'submitting' || submitState === 'success') ? 'not-allowed' : 'pointer',
              opacity: (submitState === 'submitting' || submitState === 'success') ? 0.65 : 1,
            }}
          >
            {submitState === 'submitting' ? 'Submitting…' : 'Submit Report'}
          </button>
        </div>
      </div>
    </div>
  );
}
