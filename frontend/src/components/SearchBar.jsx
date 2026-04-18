export default function SearchBar({
  value,
  onChange,
  onSearch,
  onClear,
  disabled,
  placeholder = "e.g. Apple annual report 2023"
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !disabled) {
      onSearch();
    }
  };

  return (
    <div className="search-bar">
      <div className="search-input-wrapper">
        <span className="search-icon">⌕</span>
        <input
          type="text"
          className="search-input"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        {value && (
          <button
            className={`clear-btn ${value ? 'visible' : ''}`}
            onClick={onClear}
            aria-label="Clear search"
          >
            ✕
          </button>
        )}
        <button
          className="search-btn"
          onClick={onSearch}
          disabled={disabled || !value.trim()}
        >
          {disabled ? 'Searching...' : 'Search'}
        </button>
      </div>
    </div>
  );
}
