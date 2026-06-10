/*
 * Transcription component — language + mode selection, starts a
 * transcription job on the bridge, polls it, shows the segments for
 * review and writes them to Resolve on confirmation.
 */

(function () {
  'use strict';

  const POLL_INTERVAL_MS = 2000;

  let segments = null;     // reviewed result of the last finished job
  let lastJob = null;      // {output_mode, track_index, language}

  const statusEl = document.getElementById('tr-status');
  const resultEl = document.getElementById('tr-result');
  const segmentsEl = document.getElementById('tr-segments');
  const reportEl = document.getElementById('tr-report');
  const trackField = document.getElementById('tr-track-field');
  const trackSelect = document.getElementById('tr-track');
  const tracknameField = document.getElementById('tr-trackname-field');
  const startBtn = document.getElementById('tr-start-btn');
  const writeBtn = document.getElementById('tr-write-btn');

  function mode() {
    return document.querySelector('input[name="tr-mode"]:checked').value;
  }

  function setReport(text, ok) {
    reportEl.textContent = text;
    reportEl.className = 'report ' + (ok ? 'ok' : 'err');
  }

  async function loadTracks() {
    trackSelect.textContent = '';
    try {
      const result = await Panel.api('/api/subtitle-tracks');
      if (!result.tracks.length) {
        const option = document.createElement('option');
        option.textContent = 'Ingen subtitle-tracks';
        option.disabled = true;
        trackSelect.appendChild(option);
        return;
      }
      for (const track of result.tracks) {
        const option = document.createElement('option');
        option.value = track.index;
        option.textContent = track.index + ': ' + track.name
          + ' (' + track.item_count + ' items)';
        trackSelect.appendChild(option);
      }
    } catch (e) {
      statusEl.textContent = 'Kunne ikke hente tracks: ' + e.message;
    }
  }

  function renderSegments(list) {
    segmentsEl.textContent = '';
    list.forEach(function (seg) {
      const div = document.createElement('div');
      div.className = 'seg';
      const time = document.createElement('span');
      time.className = 't';
      time.textContent = Panel.secondsToTimecode(seg.start);
      div.appendChild(time);
      div.appendChild(document.createTextNode(seg.text));
      segmentsEl.appendChild(div);
    });
  }

  function pollJob(jobId) {
    const timer = setInterval(async function () {
      let job;
      try {
        job = await Panel.api('/api/transcribe/' + jobId);
      } catch (e) {
        clearInterval(timer);
        startBtn.disabled = false;
        statusEl.textContent = 'Feil: ' + e.message;
        return;
      }
      if (job.state === 'running') {
        statusEl.textContent = 'Kjører: ' + (job.step || '…');
        return;
      }
      clearInterval(timer);
      startBtn.disabled = false;
      if (job.state === 'error') {
        statusEl.textContent = 'Feil: ' + job.error;
        return;
      }
      // done
      segments = job.segments;
      statusEl.textContent = job.segments.length + ' segmenter ('
        + (job.language || '?') + ')';
      tracknameField.classList.toggle('hidden', lastJob.output_mode !== 'new');
      renderSegments(segments);
      resultEl.classList.remove('hidden');
      setReport('', true);
    }, POLL_INTERVAL_MS);
  }

  async function start() {
    const body = { language: document.getElementById('tr-language').value, output_mode: mode() };
    if (body.output_mode === 'correct') {
      const trackIndex = parseInt(trackSelect.value, 10);
      if (isNaN(trackIndex)) {
        statusEl.textContent = 'Velg en subtitle-track først';
        return;
      }
      body.track_index = trackIndex;
    }
    startBtn.disabled = true;
    resultEl.classList.add('hidden');
    segments = null;
    lastJob = body;
    statusEl.textContent = 'Starter…';
    try {
      const result = await Panel.api('/api/transcribe', body);
      pollJob(result.job_id);
    } catch (e) {
      startBtn.disabled = false;
      statusEl.textContent = 'Feil: ' + e.message;
    }
  }

  async function write() {
    if (!segments || !lastJob) return;
    const body = { segments: segments, output_mode: lastJob.output_mode };
    if (lastJob.output_mode === 'new') {
      body.track_name = document.getElementById('tr-trackname').value.trim() || null;
    } else {
      body.track_index = lastJob.track_index;
    }
    writeBtn.disabled = true;
    setReport('Skriver…', true);
    try {
      const result = await Panel.api('/api/subtitles/write', body);
      let text = result.segments_written + ' segmenter skrevet til track '
        + result.track_index + (result.track_name ? ' ("' + result.track_name + '")' : '')
        + ' på "' + result.timeline + '"';
      if (result.original_track_disabled) {
        text += '\nOriginal track ' + result.original_track_disabled
          + ' er deaktivert (ikke slettet)';
      }
      setReport(text, true);
    } catch (e) {
      setReport('Feil: ' + e.message, false);
    } finally {
      writeBtn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input[name="tr-mode"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        const correct = mode() === 'correct';
        trackField.classList.toggle('hidden', !correct);
        if (correct) loadTracks();
      });
    });
    startBtn.addEventListener('click', start);
    writeBtn.addEventListener('click', write);
  });
})();
