import { useState, useEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';
import { auth, db } from '../firebase-config';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const ISSUE_LABELS = {
  not_found:      'Not Found',
  wrong_document: 'Wrong Doc',
  wrong_year:     'Wrong Year',
  other:          'Other',
};

export default function AdminFeedback() {
  const [authState, setAuthState] = useState('loading'); // loading | denied | allowed
  const [feedback, setFeedback]   = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  // Auth + admin role check
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) {
        setAuthState('denied');
        return;
      }
      try {
        console.log('Auth user:', user?.uid);
        console.log('Firestore doc path:', `users/${user?.uid}`);
        const snap = await getDoc(doc(db, 'users', user.uid));
        console.log('Doc exists:', snap.exists());
        console.log('Doc data:', snap.data());
        console.log('isAdmin value:', snap.data()?.isAdmin);
        if (snap.exists() && snap.data().isAdmin === true) {
          setAuthState('allowed');
        } else {
          setAuthState('denied');
        }
      } catch {
        setAuthState('denied');
      }
    });
    return () => unsubscribe();
  }, []);

  // Fetch feedback only after access is confirmed
  useEffect(() => {
    if (authState !== 'allowed') return;
    setLoading(true);
    fetch(`${BACKEND_URL}/api/feedback`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setFeedback(data.feedback || []);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [authState]);

  if (authState === 'loading') {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontFamily: 'IBM Plex Mono, monospace',
        color: 'var(--text-muted)', background: 'var(--bg)',
      }}>
        Checking access…
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontFamily: 'IBM Plex Mono, monospace',
        background: 'var(--bg)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: 'var(--error)', fontSize: '1rem', marginBottom: '8px' }}>
            Access denied
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
            Admin access required. Sign in with an admin account.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '40px 48px', fontFamily: 'IBM Plex Mono, monospace', background: 'var(--bg)', minHeight: '100vh' }}>
      <h1 style={{ fontSize: '1.3rem', color: 'var(--accent)', marginBottom: '8px' }}>
        Feedback Reports
      </h1>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '28px' }}>
        {feedback.length} report{feedback.length !== 1 ? 's' : ''} · sorted by newest first
      </p>

      {loading && <p style={{ color: 'var(--text-secondary)' }}>Loading…</p>}
      {error   && <p style={{ color: 'var(--error)' }}>Error: {error}</p>}

      {!loading && !error && feedback.length === 0 && (
        <p style={{ color: 'var(--text-muted)' }}>No feedback submitted yet.</p>
      )}

      {!loading && !error && feedback.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left' }}>
                {['Timestamp', 'Company', 'Doc Type', 'Year', 'Issue', 'URL Returned', 'Note', 'Status'].map(h => (
                  <th
                    key={h}
                    style={{ padding: '8px 12px', color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {feedback.map((item, i) => (
                <tr
                  key={item.id}
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: i % 2 === 0 ? 'var(--card-bg)' : 'transparent',
                  }}
                >
                  <td style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                    {item.timestamp ? new Date(item.timestamp).toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text)' }}>
                    {item.company_name || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                    {item.doc_type ? item.doc_type.replace(/_/g, ' ') : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                    {item.year || '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      background: item.issue_type === 'not_found' ? 'var(--error)' : 'var(--accent)',
                      color: '#fff',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      whiteSpace: 'nowrap',
                    }}>
                      {ISSUE_LABELS[item.issue_type] || item.issue_type}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', maxWidth: '220px' }}>
                    {item.url_returned
                      ? <a href={item.url_returned} target="_blank" rel="noopener noreferrer"
                           style={{ color: 'var(--accent)', wordBreak: 'break-all', fontSize: '0.72rem' }}>
                          {item.url_returned}
                        </a>
                      : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td style={{ padding: '10px 12px', maxWidth: '240px', color: 'var(--text-secondary)' }}>
                    {item.user_note || '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      color: item.status === 'resolved' ? 'var(--success)' : 'var(--warning)',
                      fontWeight: 600,
                    }}>
                      {item.status || 'pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
