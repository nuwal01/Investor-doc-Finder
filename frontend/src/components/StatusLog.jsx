import React from 'react';

const MESSAGES = [
  "Looking up the company...",
  "Locating investor relations page...",
  "Scanning available documents...",
  "Retrieving the document...",
  "Verifying the file...",
  "Almost there...",
];

function StatusLog({ isSearching, progress }) {
  const msgIndex = Math.min(
    Math.floor((progress / 100) * MESSAGES.length),
    MESSAGES.length - 1
  );
  const currentMessage = isSearching ? MESSAGES[msgIndex] : "";

  if (!isSearching && progress === 0) return null;

  return (
    <div style={{
      background: '#f2f4f0',
      border: '1px solid #c8d4c4',
      borderRadius: '12px',
      padding: '24px',
      marginBottom: '20px',
    }}>

      {/* Status message */}
      <p style={{
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: '0.82rem',
        color: '#3a5a3a',
        marginBottom: '16px',
        minHeight: '20px',
      }}>
        {progress >= 100 ? '✓ Document located' : `⟳  ${currentMessage}`}
      </p>

      {/* Progress bar track */}
      <div style={{
        width: '100%',
        height: '6px',
        background: '#e6e9e3',
        borderRadius: '4px',
        overflow: 'hidden',
      }}>
        {/* Progress bar fill */}
        <div style={{
          height: '100%',
          width: `${progress}%`,
          background: progress >= 100 ? '#4a8a4a' : '#3a5a3a',
          borderRadius: '4px',
          transition: 'width 0.5s ease',
        }} />
      </div>

      {/* Percentage */}
      <p style={{
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: '0.72rem',
        color: '#7a9a7a',
        marginTop: '8px',
        textAlign: 'right',
      }}>
        {progress >= 100 ? 'Complete' : `${Math.round(progress)}%`}
      </p>

    </div>
  );
}

export default StatusLog;
