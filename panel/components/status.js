/*
 * Status component — polls the bridge for connection state and the
 * active project/timeline, always visible at the top of the panel.
 */

(function () {
  'use strict';

  const POLL_INTERVAL_MS = 5000;

  const dot = document.getElementById('status-dot');
  const projectEl = document.getElementById('status-project');
  const timelineEl = document.getElementById('status-timeline');

  async function refresh() {
    try {
      const status = await Panel.api('/api/status');
      dot.classList.toggle('connected', !!status.connected);
      dot.title = status.connected
        ? 'Tilkoblet Resolve'
        : 'Ikke tilkoblet: ' + (status.error || 'ukjent feil');
      projectEl.textContent = status.project || '–';
      timelineEl.textContent = status.timeline || '–';
    } catch (e) {
      // Bridge itself unreachable
      dot.classList.remove('connected');
      dot.title = 'MCP-bro utilgjengelig: ' + e.message;
      projectEl.textContent = '–';
      timelineEl.textContent = '–';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    refresh();
    setInterval(refresh, POLL_INTERVAL_MS);
  });
})();
