/*
 * Media Pool sync component — enter a root folder and mirror it into the
 * Media Pool with one click. The sync is idempotent (handled backend-side):
 * re-running imports only new files.
 */

(function () {
  'use strict';

  const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

  const pathEl = document.getElementById('sync-path');
  const btn = document.getElementById('sync-btn');
  const statusEl = document.getElementById('sync-status');
  const reportEl = document.getElementById('sync-report');

  function setReport(text, ok) {
    reportEl.textContent = text;
    reportEl.className = 'report ' + (ok ? 'ok' : 'err');
  }

  async function sync() {
    const folderPath = pathEl.value.trim();
    if (!folderPath) {
      setReport('Skriv inn en mappesti først', false);
      return;
    }

    btn.disabled = true;
    setReport('', true);
    let frame = 0;
    const spinner = setInterval(function () {
      statusEl.textContent = SPINNER_FRAMES[frame++ % SPINNER_FRAMES.length] + ' Synker…';
    }, 100);

    try {
      const result = await Panel.api('/api/media-pool/sync', { folder_path: folderPath });
      const totals = result.totals;
      let text = totals.bins_created + ' bins opprettet, '
        + totals.imported + ' filer importert, '
        + totals.errors.length + ' feil';
      if (totals.bins_reused) text += '\n' + totals.bins_reused + ' bins gjenbrukt';
      if (totals.skipped_existing) {
        text += '\n' + totals.skipped_existing + ' filer hoppet over (allerede importert)';
      }
      if (totals.errors.length) text += '\n\n' + totals.errors.join('\n');
      setReport(text, totals.errors.length === 0);
    } catch (e) {
      setReport('Feil: ' + e.message, false);
    } finally {
      clearInterval(spinner);
      statusEl.textContent = '';
      btn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    btn.addEventListener('click', sync);
    pathEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') sync();
    });
  });
})();
