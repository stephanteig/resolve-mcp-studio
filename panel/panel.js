/*
 * Panel core — shared API helper and constants for the components.
 * Loaded first; components (status.js, marker-editor.js, transcription.js)
 * use window.Panel. No external dependencies.
 */

(function () {
  'use strict';

  // API base: same-origin when served by the bridge; when opened as a
  // local file, default to the bridge's default port. Override with
  // ?api=http://127.0.0.1:PORT
  const qs = new URLSearchParams(location.search);
  const base = qs.get('api')
    || (location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '');

  /**
   * fetch wrapper: JSON in/out, throws Error with the server's message
   * on non-2xx responses or {"error": ...} payloads.
   */
  async function api(path, body) {
    const opts = body === undefined
      ? { method: 'GET' }
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        };
    const res = await fetch(base + path, opts);
    let data;
    try {
      data = await res.json();
    } catch (_) {
      throw new Error('Ugyldig svar fra MCP-broen (' + res.status + ')');
    }
    if (!res.ok || (data && data.error)) {
      throw new Error((data && data.error) || 'HTTP ' + res.status);
    }
    return data;
  }

  // Resolve's actual marker color names with approximate swatch values
  const RESOLVE_COLORS = {
    Blue: '#1f6fc4',
    Cyan: '#13c2c2',
    Green: '#39b54a',
    Yellow: '#f6d51f',
    Red: '#e02929',
    Orange: '#f08c1a',
    Pink: '#ff79c2',
    Purple: '#8f4ad6',
    Fuchsia: '#c544c0',
    Rose: '#f4a6a6',
    Lavender: '#a7a1e0',
    Sky: '#74c3e8',
    Mint: '#5fd6a8',
    Lemon: '#e9f06e',
    Sand: '#d6b780',
    Cocoa: '#8a5a3c',
    Cream: '#efe3c4',
  };

  /** "1:23:45.6" seconds → "HH:MM:SS" display string */
  function secondsToTimecode(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    const hh = String(Math.floor(s / 3600)).padStart(2, '0');
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    return hh + ':' + mm + ':' + ss;
  }

  window.Panel = { api, RESOLVE_COLORS, secondsToTimecode };
})();
