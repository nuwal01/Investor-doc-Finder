import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSSESearch } from '../hooks/useSSESearch';
import SearchBar from '../components/SearchBar';
import DocTypePills from '../components/DocTypePills';
import QuickPicks from '../components/QuickPicks';
import StatusLog from '../components/StatusLog';
import ResultCard from '../components/ResultCard';

import HistoryPanel from '../components/HistoryPanel';
import LibraryPanel from '../components/LibraryPanel';

export default function Search() {
  const [query, setQuery] = useState('');
  const [docType, setDocType] = useState('annual report');
  const [activeTab, setActiveTab] = useState('search');

  const { user, signOut } = useAuth();
  const { results, progress, isSearching, logVisible, backendOnline, startSearch, resetSearch } = useSSESearch();

  const handleSearch = () => {
    if (query.trim()) {
      startSearch(query, docType);
    }
  };

  const handleClear = () => {
    setQuery('');
    resetSearch();
  };

  const handleQuickPick = (pick) => {
    setQuery(pick);
    setTimeout(() => {
      startSearch(pick, docType);
    }, 100);
  };

  const userInitial = user?.displayName
    ? user.displayName[0].toUpperCase()
    : user?.email
      ? user.email[0].toUpperCase()
      : '?';

  return (
    <div>
      {/* App Navigation */}
      <nav className="app-nav">
        <div className="app-nav-left">
          <Link to="/" className="app-nav-logo">Investor-Doc-Finder</Link>
        </div>

        {/* Tab Navigation */}
        <div className="app-nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveTab('search')}
          >
            Search
          </button>
          <button
            className={`nav-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            History
          </button>
          <button
            className={`nav-tab ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
          >
            Library
          </button>
        </div>

        <div className="app-nav-right">
          <div className="user-pill">
            <div className="user-avatar">{userInitial}</div>
            <span className="user-email">{user?.email || 'User'}</span>
          </div>
          <button className="signout-btn" onClick={signOut}>
            Sign Out
          </button>
        </div>
      </nav>

      {/* Search Panel */}
      {activeTab === 'search' && (
        <div className="search-layout">
          <div className="search-col">
            <div className="search-header">
              <h1>Find Investor Documents</h1>
              <p>Search across 40+ global exchanges with AI-powered precision</p>
              {backendOnline === false && (
                <p style={{ color: 'var(--error, #ef4444)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                  Backend offline — start the server: <code>uvicorn main:app --reload --port 8000</code>
                </p>
              )}
            </div>

            <SearchBar
              value={query}
              onChange={setQuery}
              onSearch={handleSearch}
              onClear={handleClear}
              disabled={isSearching}
            />

            <DocTypePills selected={docType} onChange={setDocType} />
            <QuickPicks onPick={handleQuickPick} />
            <StatusLog isSearching={isSearching} progress={progress} />

            {results.length > 0 ? (
              <div className="results-container">
                {results.map((result, index) => (
                  <ResultCard key={index} result={result} />
                ))}
              </div>
            ) : (
              !isSearching && !logVisible && (
                <div className="empty-state">
                  <div className="empty-state-icon">📄</div>
                  <h3>Start Your Search</h3>
                  <p>Enter a company name and document type above, or try a quick pick</p>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {/* History Panel */}
      {activeTab === 'history' && (
        <div className="panel-page">
          <HistoryPanel />
        </div>
      )}

      {/* Library Panel */}
      {activeTab === 'library' && (
        <div className="panel-page">
          <LibraryPanel />
        </div>
      )}
    </div>
  );
}
