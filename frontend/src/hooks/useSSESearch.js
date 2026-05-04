import { useState, useEffect } from 'react';
import { auth } from '../firebase-config';

const BACKEND_URL = 'http://localhost:8000';

/**
 * Custom hook for SSE-based document search
 * Handles streaming server-sent events from the search API
 */
export function useSSESearch() {
  const [results, setResults] = useState([]);
  const [progress, setProgress] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [logVisible, setLogVisible] = useState(false);
  const [backendOnline, setBackendOnline] = useState(null); // null = unknown, true/false
  const [error, setError] = useState(null);

  // Health check on mount and every 30 seconds
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`);
        if (!res.ok) { setBackendOnline(false); return; }
        const data = await res.json();
        setBackendOnline(data.status === 'ok');
      } catch {
        setBackendOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, []);

  /**
   * Starts a new search with SSE streaming
   */
  const startSearch = async (query, docType = 'annual report', year = null) => {
    // Reset state
    setIsSearching(true);
    setProgress(0);
    setResults([]);
    setLogVisible(true);
    setError(null);

    let statusCount = 0;

    const updateProgress = (count) => {
      const mapping = {
        1: 15,
        2: 30,
        3: 48,
        4: 62,
        5: 75,
      };
      if (count >= 6) return 85;
      return mapping[count] || 0;
    };

    /**
     * Handles incoming SSE events
     */
    const handleEvent = (payload) => {
      const { event, data } = payload;

      switch (event) {
        case 'status':
          statusCount++;
          setProgress(updateProgress(statusCount));
          break;

        case 'result': {
          // Data might be a stringified JSON or already parsed
          const result = typeof data === 'string' ? JSON.parse(data) : data;
          setResults(prev => [...prev, result]);
          setProgress(95);
          break;
        }

        case 'error':
          setError(data);
          break;

        case 'done':
          setProgress(100);
          break;

        default:
          console.warn('Unknown event type:', event);
      }
    };

    try {
      // Get Firebase ID token for authentication
      const user = auth.currentUser;
      if (!user) {
        throw new Error('Not authenticated');
      }

      const idToken = await user.getIdToken();

      // Make POST request to search endpoint
      const response = await fetch(`${BACKEND_URL}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`,
        },
        body: JSON.stringify({ query, docType, year }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Set up streaming reader
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Read the stream
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Split by newlines
        const lines = buffer.split('\n');

        // Keep the last incomplete line in buffer
        buffer = lines.pop() || '';

        // Process complete lines
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const payload = JSON.parse(raw);
            handleEvent(payload);
          } catch (e) {
            console.error('Failed to parse SSE data:', raw, e);
          }
        }
      }

      // Process remaining buffer if it exists
      if (buffer.trim() && buffer.startsWith('data: ')) {
        const raw = buffer.slice(6).trim();
        if (raw) {
          try {
            const payload = JSON.parse(raw);
            handleEvent(payload);
          } catch (e) {
            console.error('Failed to parse final SSE data:', raw, e);
          }
        }
      }

      // Stream ended — ensure progress is always 100% when complete
      setProgress(100);

    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  /**
   * Resets the search state
   */
  const resetSearch = () => {
    setResults([]);
    setProgress(0);
    setIsSearching(false);
    setLogVisible(false);
    setError(null);
  };

  return {
    results,
    progress,
    isSearching,
    logVisible,
    backendOnline,
    error,
    setError,
    startSearch,
    resetSearch,
  };
}
