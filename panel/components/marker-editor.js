/*
 * Marker editor — editable table of markers (timecode | name | color |
 * delete), paste-and-parse from free text, and "Send til Resolve".
 *
 * State lives in the `markers` array; the table is re-rendered from it.
 * Rows added or edited in the panel carry only a timecode — the bridge
 * converts timecode → frame against the active timeline's fps on send.
 */

(function () {
  'use strict';

  /** @type {Array<{timecode: string, name: string, color: string, note: string}>} */
  let markers = [];

  const rowsEl = document.getElementById('marker-rows');
  const reportEl = document.getElementById('marker-report');
  const parseInfoEl = document.getElementById('marker-parse-info');
  const pasteEl = document.getElementById('marker-paste');

  function colorSelect(selected, onChange) {
    const wrapper = document.createElement('span');
    wrapper.className = 'color-cell';

    const swatch = document.createElement('span');
    swatch.className = 'color-swatch';
    swatch.style.background = Panel.RESOLVE_COLORS[selected] || '#666';

    const select = document.createElement('select');
    for (const name of Object.keys(Panel.RESOLVE_COLORS)) {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      option.selected = name === selected;
      select.appendChild(option);
    }
    select.addEventListener('change', function () {
      swatch.style.background = Panel.RESOLVE_COLORS[select.value] || '#666';
      onChange(select.value);
    });

    wrapper.appendChild(swatch);
    wrapper.appendChild(select);
    return wrapper;
  }

  function editableCell(value, className, onChange) {
    const td = document.createElement('td');
    td.contentEditable = 'true';
    td.spellcheck = false;
    td.className = className;
    td.textContent = value;
    td.addEventListener('blur', function () {
      onChange(td.textContent.trim());
    });
    td.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); td.blur(); }
    });
    return td;
  }

  function render() {
    rowsEl.textContent = '';
    markers.forEach(function (marker, i) {
      const tr = document.createElement('tr');

      tr.appendChild(editableCell(marker.timecode, 'tc', function (v) { marker.timecode = v; }));
      tr.appendChild(editableCell(marker.name, '', function (v) { marker.name = v; }));

      const colorTd = document.createElement('td');
      colorTd.appendChild(colorSelect(marker.color, function (v) { marker.color = v; }));
      tr.appendChild(colorTd);

      const delTd = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.className = 'del-btn';
      delBtn.textContent = '✕';
      delBtn.title = 'Slett rad';
      delBtn.addEventListener('click', function () {
        markers.splice(i, 1);
        render();
      });
      delTd.appendChild(delBtn);
      tr.appendChild(delTd);

      rowsEl.appendChild(tr);
    });
  }

  function setReport(text, ok) {
    reportEl.textContent = text;
    reportEl.className = 'report ' + (ok ? 'ok' : 'err');
  }

  async function parsePasted() {
    const text = pasteEl.value;
    if (!text.trim()) return;
    parseInfoEl.textContent = 'Parser…';
    try {
      const result = await Panel.api('/api/markers/parse', { text: text });
      markers = result.markers.map(function (m) {
        return { timecode: m.timecode, name: m.name, color: m.color, note: m.note || '' };
      });
      render();
      parseInfoEl.textContent = result.markers.length + ' markers'
        + (result.skipped_lines.length
            ? ' — hoppet over ' + result.skipped_lines.length + ' linje(r)'
            : '');
    } catch (e) {
      parseInfoEl.textContent = 'Feil: ' + e.message;
    }
  }

  async function sendToResolve() {
    if (!markers.length) {
      setReport('Ingen markers å sende', false);
      return;
    }
    const btn = document.getElementById('marker-send-btn');
    btn.disabled = true;
    setReport('Sender…', true);
    try {
      const result = await Panel.api('/api/markers/set', { markers: markers });
      const ok = result.failures.length === 0;
      let text = result.set + ' av ' + result.requested + ' markers satt på "'
        + result.timeline + '" (' + result.project + ')';
      if (!ok) {
        text += '\nFeil:\n' + result.failures
          .map(function (f) { return '  rad ' + (f.index + 1) + ': ' + f.reason; })
          .join('\n');
      }
      setReport(text, ok);
    } catch (e) {
      setReport('Feil: ' + e.message, false);
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('marker-add-btn').addEventListener('click', function () {
      markers.push({ timecode: '00:00:00:00', name: '', color: 'Blue', note: '' });
      render();
    });
    document.getElementById('marker-parse-btn').addEventListener('click', parsePasted);
    document.getElementById('marker-send-btn').addEventListener('click', sendToResolve);
    render();
  });
})();
