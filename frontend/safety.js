/* Session-backed Safety Station. Findings are never inferred in the browser. */
(() => {
  'use strict';
  const images = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const videos = new Set(['video/mp4', 'video/webm', 'video/x-msvideo', 'video/avi']);
  const terminal = new Set(['completed', 'failed', 'cancelled']);
  const human = value => String(value ?? '').replaceAll('_', ' ');
  const time = value => {
    if (!Number.isFinite(value) || value < 0) return '—';
    const sec = Math.floor(value / 1000);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}.${String(Math.floor(value % 1000)).padStart(3, '0')}`;
  };
  function validateQuad(quad) {
    if (!Array.isArray(quad) || quad.length !== 4 || quad.some(p => !Array.isArray(p) || p.length !== 2 || p.some(v => !Number.isFinite(v) || v < 0 || v > 1))) throw new Error('Enter four panel corners between 0 and 1.');
    const crosses = quad.map((a, i) => {
      const b = quad[(i + 1) % 4], c = quad[(i + 2) % 4];
      return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
    });
    const area = quad.reduce((sum, a, i) => { const b = quad[(i + 1) % 4]; return sum + a[0] * b[1] - b[0] * a[1]; }, 0) / 2;
    if (crosses.some(v => v <= 0) || area < 0.12) throw new Error('Use a convex panel covering at least 12% of the frame, clockwise from top left.');
    return quad;
  }
  function validateFile(file, mode) {
    if (!file || !Number.isFinite(file.size) || file.size <= 0) throw new Error('Choose a nonempty source file.');
    const still = mode === 'STILL_IMAGE';
    if (!(still ? images : videos).has(file.type)) throw new Error(still ? 'Choose a PNG, JPEG or WebP image.' : 'Choose an MP4, WebM or AVI video.');
    if (file.size > (still ? 12 : 50) * 1024 * 1024) throw new Error(still ? 'Images must be 12 MiB or smaller.' : 'Videos must be 50 MiB or smaller.');
    return true;
  }
  function protectedURL(path, id, origin) {
    const base = `/api/safety/sessions/${encodeURIComponent(id)}`;
    const url = new URL(path, origin);
    if (url.origin !== new URL(origin).origin || !(url.pathname === base || url.pathname.startsWith(base + '/')) || url.username || url.password) throw new Error('Refused an evidence URL outside this session.');
    if (url.searchParams.has('access_token') || url.searchParams.has('token')) throw new Error('Session keys must never be placed in URLs.');
    return url.href;
  }
  async function authorized(path, capability, options = {}, fetcher = globalThis.fetch, origin = globalThis.location?.origin) {
    if (!capability?.id || !capability?.access_token) throw new Error('This tab does not have the session key. Create a new inspection.');
    const url = protectedURL(path, capability.id, origin), headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${capability.access_token}`);
    const response = await fetcher(url, { ...options, headers, redirect: 'error' });
    if (!response.ok) {
      let body; try { body = await response.json(); } catch { /* HTTP status remains available. */ }
      const detail = body?.detail?.message || body?.detail || body?.message || `Request failed (${response.status}).`;
      throw new Error((typeof detail === 'string' ? detail : JSON.stringify(detail)).split(capability.access_token).join('[session key redacted]'));
    }
    return response;
  }
  function identity(run) {
    const c = run.configuration || run;
    const media = run.media?.sha256, recipe = run.recipe_state?.recipe_sha256 || run.recipe_sha256;
    if (!media || !recipe || !Array.isArray(c.calibration_quad) || !['unknown', 'empty_observed'].includes(c.start_state) || typeof c.final_checkpoint !== 'boolean') return null;
    return JSON.stringify([media, recipe, c.calibration_quad, c.start_state, c.final_checkpoint, run.source_mode || c.source_mode]);
  }
  function compareRuns(a, b) {
    if (a.id === b.id) throw new Error('Choose two different saved runs.');
    if (a.state !== 'completed' || b.state !== 'completed') throw new Error('Compare completed runs only.');
    if (a.policy === b.policy) throw new Error('Choose runs with different policies.');
    if (!identity(a) || !identity(b)) throw new Error('Comparison unavailable: media, recipe or calibration identity is missing.');
    if (identity(a) !== identity(b)) throw new Error('These runs use different media, recipes or settings. Use the same input for both policies.');
    return true;
  }
  function stopStream(stream) { for (const track of stream?.getTracks() || []) { track.onended = null; track.stop(); } }
  const core = { validateQuad, validateFile, protectedURL, authorized, identity, compareRuns, time, stopStream };
  if (typeof module !== 'undefined' && module.exports) module.exports = core;
  if (typeof document === 'undefined') return;

  const $ = s => document.querySelector(s);
  const put = (s, value) => { $(s).textContent = String(value ?? '—'); };
  const node = (tag, value, cls) => { const e = document.createElement(tag); if (value !== undefined) e.textContent = String(value); if (cls) e.className = cls; return e; };
  const pretty = value => JSON.stringify(value ?? {}, null, 2);
  const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const storeKey = 'reflex-safety-capabilities-v1';
  const S = { recipes: [], fixtures: [], registry: [], run: null, file: null, epoch: 0, poll: null, busy: false, urls: new Set(), sourceURL: null, sourceType: null, sourceSession: null, frame: null, selection: 0, stickyFrame: false, renderKey: '', stream: null, captureTimer: null, captureStart: 0, captureCount: 0, framePromise: null, stopping: false, controller: null, refreshErrors: 0 };
  const message = (value, error = false) => { put('#ss-status', value); $('#ss-status').classList.toggle('error', error); };
  const endpoint = (suffix = '', run = S.run) => `/api/safety/sessions/${encodeURIComponent(run.id)}${suffix}`;
  const cap = run => ({ id: run.id, access_token: S.registry.find(item => item.id === run.id)?.access_token || run.access_token });
  const req = (suffix, options = {}, run = S.run) => authorized(endpoint(suffix, run), cap(run), options);
  const json = async (suffix, options, run) => (await req(suffix, options, run)).json();
  function blobURL(blob) { const url = URL.createObjectURL(blob); S.urls.add(url); return url; }
  function revoke(url) { if (S.urls.delete(url)) URL.revokeObjectURL(url); }
  function releaseMedia() {
    for (const url of S.urls) URL.revokeObjectURL(url); S.urls.clear(); S.sourceURL = null; S.sourceType = null; S.sourceSession = null;
    $('#ss-video').removeAttribute('src'); $('#ss-video').load(); $('#ss-frame').removeAttribute('src');
  }
  function show(kind) {
    $('#ss-empty').hidden = kind !== 'empty'; $('#ss-video').hidden = kind !== 'video'; $('#ss-frame').hidden = kind !== 'frame';
    if (kind !== 'video' && !S.stream) $('#ss-video').pause();
  }
  function controls() {
    const run = S.run, active = run && !terminal.has(run.state), camera = Boolean(S.stream), lock = S.busy || camera || Boolean(active);
    $('#ss-run').disabled = lock || !S.recipes.length;
    $('#ss-cancel').disabled = !active;
    $('#ss-stop-camera').disabled = !camera || S.stopping;
    for (const id of ['ss-recipe', 'ss-policy', 'ss-source', 'ss-file', 'ss-fixture', 'ss-use-fixture']) $('#' + id).disabled = lock || !S.recipes.length || (['ss-fixture', 'ss-use-fixture'].includes(id) && !S.fixtures.length);
    for (const id of ['ss-next-frames', 'ss-request-view', 'ss-new-view']) $('#' + id).disabled = !run || S.busy || camera || ['running', 'queued', 'cancelled', 'failed'].includes(run.state);
    $('#ss-new-view').disabled = !run || S.busy || camera || run.source_mode !== 'STILL_IMAGE' || terminal.has(run.state);
    $('#ss-review-note').disabled = !run || S.busy;
    $('#ss-review-form').querySelectorAll('button').forEach(b => { b.disabled = !run || S.busy; });
    for (const id of ['ss-export-json', 'ss-export-html']) $('#' + id).disabled = !run;
    $('#ss-load-session').disabled = !$('#ss-saved-session').value || S.busy || camera || Boolean(active) && $('#ss-saved-session').value !== run.id;
    $('#ss-compare').disabled = S.busy;
  }
  function busy(value) { S.busy = value; $('#ss-form').setAttribute('aria-busy', String(value)); controls(); }
  function renderSaved() {
    for (const id of ['ss-saved-session', 'ss-compare-a', 'ss-compare-b']) {
      const select = $('#' + id), selected = select.value; select.replaceChildren(new Option('Choose a saved run', ''));
      for (const item of S.registry) select.add(new Option(`${human(item.policy)} · ${item.created_at_utc ? new Date(item.created_at_utc).toLocaleString() : item.id.slice(0, 8)} · ${human(item.state)}`, item.id));
      if (S.registry.some(item => item.id === selected)) select.value = selected;
    }
    controls();
  }
  function remember(run) {
    const item = S.registry.find(item => item.id === run.id);
    if (item) Object.assign(item, { policy: run.policy, state: run.state });
    else if (run.access_token) S.registry.unshift({ id: run.id, access_token: run.access_token, policy: run.policy, state: run.state, created_at_utc: run.created_at_utc });
    try { sessionStorage.setItem(storeKey, JSON.stringify(S.registry)); }
    catch { message('Browser session storage is unavailable. Keep this page open to retain the session key.', true); }
    renderSaved();
  }
  async function publicJSON(path) { const r = await fetch(path, { redirect: 'error' }); if (!r.ok) throw new Error(`Service request failed (${r.status}).`); return r.json(); }
  function sourceChanged() {
    const still = $('#ss-source').value === 'STILL_IMAGE', camera = $('#ss-source').value === 'LIVE_CAMERA';
    $('#ss-file-label').hidden = camera;
    $('#ss-file-label').firstChild.textContent = still ? 'Choose image' : 'Choose video';
    $('#ss-file').accept = still ? 'image/png,image/jpeg,image/webp' : 'video/mp4,video/webm,video/x-msvideo';
    put('#ss-run', camera ? 'Create & start camera' : 'Create & inspect');
    put('#ss-limits', camera ? 'Video frames only, one upload at a time. Capture stops at 120 seconds / 200 submitted frames. Live capture-to-alert latency is unverified.' : still ? 'PNG, JPEG or WebP · 12 MiB maximum. A still image cannot establish an assembly sequence.' : 'Video: 50 MiB, 120 seconds and 600 decoded frames maximum. Audio is never requested.');
    S.file = null; $('#ss-file').value = '';
  }
  async function metadata(file, mode) {
    validateFile(file, mode);
    if (mode === 'STILL_IMAGE') {
      const bitmap = await createImageBitmap(file);
      try { if (bitmap.width > 4096 || bitmap.height > 4096 || bitmap.width * bitmap.height > 20_000_000) throw new Error('Image exceeds 4096 px per edge or 20 million pixels.'); }
      finally { bitmap.close(); }
      return;
    }
    return await new Promise((resolve, reject) => {
      const video = document.createElement('video'), url = URL.createObjectURL(file); let settled = false;
      const done = (error, decodable = true) => { if (settled) return; settled = true; clearTimeout(timer); video.onloadedmetadata = null; video.onerror = null; video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url); error ? reject(error) : resolve(decodable); };
      const timer = setTimeout(() => done(new Error('Video metadata could not be read. Try MP4 or WebM.')), 10000);
      video.onloadedmetadata = () => done(Number.isFinite(video.duration) && video.duration > 120.001 ? new Error('Video exceeds the 120-second limit.') : null);
      video.onerror = () => done(null, false);
      video.preload = 'metadata'; video.src = url;
    });
  }
  async function chooseFile(file, fixture = false) {
    if (!file) return;
    try {
      const decodable = await metadata(file, $('#ss-source').value); S.file = file;
      if (!S.run || terminal.has(S.run.state)) {
        S.run = null; S.frame = null; S.stickyFrame = false; S.renderKey = ''; ++S.epoch; clearTimeout(S.poll);
        put('#ss-decision', 'Awaiting evidence'); put('#ss-reasons', 'New source loaded. No decision has been made for this input.'); put('#ss-human-action', ''); $('#ss-gate').className = 'safety-gate';
        put('#ss-session-state', 'NO SESSION'); put('#ss-source-badge', fixture ? 'PREVIEW / SYNTHETIC SOFTWARE TEST' : 'PREVIEW / USER SUPPLIED');
        put('#ss-source-description', 'Local preview only. Source has not been processed.'); put('#ss-processing', 'Processing time —'); put('#ss-clock', 'Source timestamp —');
        put('#ss-events', 'No session events yet.'); put('#ss-agent-trace', 'No backend actions recorded for this source.'); put('#ss-event-count', '0 RECORDED EVENTS');
        $('#ss-original').disabled = true; $('#ss-overlay').disabled = true; $('#ss-show-video').disabled = $('#ss-source').value === 'STILL_IMAGE';
        releaseMedia(); S.sourceURL = blobURL(file); S.sourceSession = null;
        const still = $('#ss-source').value === 'STILL_IMAGE'; S.sourceType = still ? 'image' : 'video'; $(still ? '#ss-frame' : '#ss-video').src = S.sourceURL; show(still ? 'frame' : 'video');
      }
      put('#ss-scope-label', fixture ? 'SYNTHETIC SOFTWARE TEST' : 'USER SUPPLIED · UNBENCHMARKED');
      controls();
      message(decodable === false ? `${file.name} loaded. This browser cannot preview its codec; the service will enforce duration/frame limits. Use the decoded JPEG evidence timeline after processing.` : `${file.name} loaded. Check panel alignment and source permission before processing.`);
    } catch (error) { S.file = null; $('#ss-file').value = ''; message(error.message, true); }
  }
  async function loadFixture() {
    const fixture = S.fixtures.find(f => f.id === $('#ss-fixture').value);
    if (!fixture) return message('Choose a generated fixture first.', true);
    busy(true);
    try {
      $('#ss-source').value = 'STREAM_REPLAY'; sourceChanged();
      const url = new URL(fixture.url, location.origin); if (url.origin !== location.origin) throw new Error('Fixture must come from this REFLEX service.');
      const r = await fetch(url, { redirect: 'error' }); if (!r.ok) throw new Error(`Fixture unavailable (${r.status}).`);
      const blob = await r.blob(); if (blob.size > 50 * 1024 * 1024) throw new Error('Fixture exceeds the upload limit.');
      const actual = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()))].map(v => v.toString(16).padStart(2, '0')).join('');
      if (actual !== fixture.sha256) throw new Error('Fixture bytes do not match its source hash.');
      await chooseFile(new File([blob], new URL(fixture.url, location.origin).pathname.split('/').pop(), { type: blob.type || 'video/mp4' }), true);
    } catch (error) { message(error.message, true); } finally { busy(false); }
  }
  function configuration() {
    if (!$('#ss-consent').checked) throw new Error('Confirm source permission first.');
    if (!$('#ss-alignment').checked) throw new Error('Verify the actual panel corners first.');
    const values = [...$('#ss-corners').querySelectorAll('input')].map(e => e.value.trim() === '' ? NaN : Number(e.value));
    return { recipe_id: $('#ss-recipe').value, policy: $('#ss-policy').value, source_mode: $('#ss-source').value, consent: true, calibration_quad: validateQuad(Array.from({ length: 4 }, (_, i) => values.slice(i * 2, i * 2 + 2))), start_state: $('#ss-empty-start').checked ? 'empty_observed' : 'unknown', final_checkpoint: $('#ss-checkpoint').checked };
  }
  async function createSession(event) {
    event.preventDefault(); if (S.busy || S.stream || S.run && !terminal.has(S.run.state)) return;
    let config; try { config = configuration(); if (config.source_mode !== 'LIVE_CAMERA') validateFile(S.file, config.source_mode); }
    catch (error) { return message(error.message, true); }
    busy(true); const epoch = ++S.epoch; S.controller = new AbortController(); clearTimeout(S.poll);
    try {
      const response = await fetch('/api/safety/sessions', { ...post(config), signal: S.controller.signal, redirect: 'error' });
      if (!response.ok) { let b; try { b = await response.json(); } catch { /* Use status. */ } throw new Error(typeof b?.detail === 'string' ? b.detail : `Session creation failed (${response.status}).`); }
      const run = await response.json(); if (!run.id || !run.access_token) throw new Error('No session key returned. Source was not uploaded.');
      S.run = run; S.frame = null; S.stickyFrame = false; S.renderKey = ''; remember(run); render(run);
      if (config.source_mode === 'LIVE_CAMERA') { busy(false); await startCamera(epoch); return; }
      const form = new FormData(); form.append('file', S.file, S.file.name);
      if (config.source_mode === 'STILL_IMAGE') { form.append('source_timestamp_ms', '0'); await json('/frames', { method: 'POST', body: form, signal: S.controller.signal }); if (epoch !== S.epoch) return; S.run = await json('/finish', post({ final_checkpoint: config.final_checkpoint })); }
      else { await json('/video', { method: 'POST', body: form, signal: S.controller.signal }); if (epoch !== S.epoch) return; S.run = await json('/start', { method: 'POST', signal: S.controller.signal }); S.sourceSession = S.run.id; }
      if (epoch !== S.epoch) return; render(S.run); poll(epoch); message('Source accepted. Progress and decisions come from the processing service.');
    } catch (error) {
      if (epoch !== S.epoch || error.name === 'AbortError') return;
      message(error.message, true); if (S.run) { try { S.run = await json(''); render(S.run); } catch { /* Retain last observed state. */ } }
    } finally { if (epoch === S.epoch) { S.controller = null; busy(false); } }
  }
  function cameraOff() { clearTimeout(S.captureTimer); S.captureTimer = null; const stream = S.stream; S.stream = null; stopStream(stream); $('#ss-video').srcObject = null; controls(); }
  async function startCamera(epoch) {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires HTTPS or loopback and a supported browser. Use an uploaded video.');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      if (epoch !== S.epoch) { stopStream(stream); return; }
      releaseMedia(); S.stream = stream; S.captureStart = performance.now(); S.captureCount = 0;
      const video = $('#ss-video'); video.srcObject = stream; video.controls = false; $('#ss-camera-error').hidden = true; show('video'); await video.play();
      for (const track of stream.getVideoTracks()) track.onended = () => { put('#ss-camera-error', 'Camera disconnected. Capture stopped; existing evidence remains available.'); $('#ss-camera-error').hidden = false; finishCamera(false); };
      message('Camera active. Video frames only; audio is not requested.'); controls(); scheduleFrame(epoch); poll(epoch);
    } catch (error) {
      cameraOff();
      const errors = { NotAllowedError: 'Camera permission denied. Choose Uploaded video / replay to continue.', NotFoundError: 'No camera found. Choose Uploaded video / replay.', NotReadableError: 'Camera unavailable or in use. Choose an uploaded video.' };
      put('#ss-camera-error', errors[error.name] || error.message); $('#ss-camera-error').hidden = false; message(errors[error.name] || error.message, true);
      try { S.run = await json('/cancel', { method: 'POST' }); render(S.run); } catch { /* Do not assume cancellation succeeded. */ }
    }
  }
  function scheduleFrame(epoch) {
    if (!S.stream || epoch !== S.epoch || S.stopping) return;
    if (performance.now() - S.captureStart >= 120000 || S.captureCount >= 200) { finishCamera(false, 'Capture bound reached. No final checkpoint is assumed.'); return; }
    S.framePromise = sendFrame(epoch);
    S.framePromise.then(() => { S.framePromise = null; if (S.stream && epoch === S.epoch) S.captureTimer = setTimeout(() => scheduleFrame(epoch), 500); }).catch(error => { S.framePromise = null; message('Frame upload stopped: ' + error.message, true); finishCamera(false); });
  }
  async function sendFrame(epoch) {
    const video = $('#ss-video'); if (!video.videoWidth || video.readyState < 2) return;
    const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight; canvas.getContext('2d').drawImage(video, 0, 0);
    const timestamp = Math.round(performance.now() - S.captureStart), blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (!blob || !S.stream || epoch !== S.epoch) return;
    const form = new FormData(); form.append('file', blob, 'camera-frame.jpg'); form.append('source_timestamp_ms', String(timestamp));
    const run = await json('/frames', { method: 'POST', body: form }); S.captureCount++;
    if (epoch === S.epoch && S.stream) { S.run = run; render(run); }
  }
  async function finishCamera(checkpoint = $('#ss-checkpoint').checked, note = '') {
    if (S.stopping) return; S.stopping = true; cameraOff(); $('#ss-video').controls = true;
    try { if (S.framePromise) await S.framePromise.catch(() => {}); S.run = await json('/finish', post({ final_checkpoint: checkpoint })); render(S.run); poll(S.epoch); message(note || 'Camera stopped. The recorded observations were finalized by the service.'); }
    catch (error) { message('Camera stopped; finalization failed: ' + error.message, true); } finally { S.stopping = false; controls(); }
  }
  async function poll(epoch) {
    clearTimeout(S.poll); if (!S.run || epoch !== S.epoch) return;
    try { const run = await json(''); if (epoch !== S.epoch) return; S.run = run; S.refreshErrors = 0; render(run); if (terminal.has(run.state) && !S.stream) return; }
    catch (error) { if (epoch !== S.epoch) return; S.refreshErrors++; message('Status refresh failed: ' + error.message, true); if (S.refreshErrors >= 3) return message('Status refresh stopped after three failures. Reopen this saved session to retry; no new result is assumed.', true); }
    S.poll = setTimeout(() => poll(epoch), 1000 * Math.min(3, S.refreshErrors + 1));
  }
  const evidence = (run = S.run) => Array.isArray(run?.evidence) ? run.evidence : [];
  function renderRecipe(recipe, recorded = null) {
    if (!recipe) return;
    put('#ss-recipe-name', recipe.name || recipe.recipe_id); put('#ss-recipe-scope', recipe.scope);
    $('#ss-steps').replaceChildren(...(recorded?.steps || recipe.steps || []).map(step => {
      const item = node('li'), button = node('button'); button.type = 'button';
      button.append(node('span', step.title || human(step.step_id || step.id)), node('span', human(step.state || 'UNOBSERVED')));
      button.addEventListener('click', () => { put('#ss-step-evidence', pretty(step)); const related = (S.run?.observations || []).filter(o => (step.slot_ids || step.slots || []).includes(o.slot_id)); if (related.length) selectFrame(related[related.length - 1].evidence_id); });
      item.append(button); return item;
    }));
    const slots = recorded?.slots || Object.entries(recipe.slots || {}).map(([slot_id, value]) => ({ slot_id, expected_classes: recipe.parts?.[value.requires]?.classes || [], ...value }));
    $('#ss-slots').replaceChildren(...slots.map(slot => {
      const button = node('button', `${human(slot.slot_id)} · expected ${(slot.expected_classes || []).join(', ')} · observed ${slot.observed_class || 'unobserved'}`, 'safety-slot'); button.type = 'button';
      button.addEventListener('click', () => { const observations = (S.run?.observations || []).filter(o => o.slot_id === slot.slot_id); put('#ss-step-evidence', pretty({ slot, observations })); if (observations.length) selectFrame(observations[observations.length - 1].evidence_id); }); return button;
    }));
  }
  function render(run) {
    remember(run); const mode = run.source_mode || run.configuration?.source_mode;
    const source = run.media?.source || (mode === 'LIVE_CAMERA' ? 'USER_SUPPLIED_UNBENCHMARKED' : 'PROVENANCE PENDING');
    put('#ss-session-state', human(run.state).toUpperCase()); put('#ss-policy-label', human(run.policy).toUpperCase()); put('#ss-scope-label', human(source));
    put('#ss-source-badge', `${mode === 'STREAM_REPLAY' ? 'REPLAY' : mode === 'LIVE_CAMERA' && S.stream ? 'ACTIVE CAMERA' : human(mode || 'SESSION')} / ${human(source)}`);
    put('#ss-source-description', `${run.media?.filename || 'Session source'} · ${run.media?.sha256 ? 'SHA256 ' + run.media.sha256 : 'Source hash not available yet'}. Source event time and processing time are separate. Live capture-to-alert latency is unverified.`);
    const decision = run.decision?.status; put('#ss-decision', decision ? human(decision) : 'Awaiting evidence');
    $('#ss-gate').className = 'safety-gate' + (decision === 'PASS' ? ' pass' : decision === 'HOLD_FOR_REVIEW' ? ' hold' : decision === 'REJECT_RECOMMENDATION' ? ' reject' : '');
    put('#ss-reasons', run.decision?.reason_codes?.length ? run.decision.reason_codes.map(human).join('\n') : 'No supported decision reasons recorded yet.'); put('#ss-human-action', run.decision?.required_human_action || '');
    const p = run.progress || {}, processing = run.processing || {}; $('#ss-progress').hidden = !Number.isFinite(p.fraction);
    if (Number.isFinite(p.fraction)) $('#ss-progress').value = Math.max(0, Math.min(1, p.fraction));
    put('#ss-progress-text', `${Number.isFinite(p.analyzed_frames) ? p.analyzed_frames + ' frames analyzed' : Number.isFinite(processing.analyzed_frames) ? processing.analyzed_frames + ' frames analyzed' : 'Frame count unavailable'}${processing.truncated ? ' · processing bound reached' : ''}${processing.cancelled ? ' · cancelled' : ''}`);
    put('#ss-processing', Number.isFinite(processing.elapsed_ms) ? `Processing elapsed ${processing.elapsed_ms.toFixed(1)} ms` : 'Processing time —');
    const key = JSON.stringify([run.recipe_state, run.events, run.agent_trace, run.acknowledgements]);
    if (key !== S.renderKey) { S.renderKey = key; renderRecipe(run.recipe || S.recipes.find(r => r.recipe_id === run.recipe_id), run.recipe_state); renderEvents(run); renderTrace(run); put('#ss-observations', pretty(run.observations || [])); put('#ss-acknowledgements', run.acknowledgements?.length ? 'Appended operator review records:\n' + pretty(run.acknowledgements) : 'Operator review appends a record. It never changes the machine finding.'); }
    const frames = evidence(run); if (!S.stickyFrame && frames.length && !S.stream) selectFrame(frames[frames.length - 1].id, false);
    $('#ss-show-video').disabled = !S.stream && !(S.sourceURL && S.sourceType === 'video') && !run.media?.video_url; controls();
  }
  function renderEvents(run) {
    const events = run.events || []; put('#ss-event-count', `${events.length} RECORDED EVENTS`);
    $('#ss-events').replaceChildren(...(events.length ? events.map(event => {
      const li = node('li'), button = node('button', undefined, 'safety-event'); button.type = 'button'; const stamp = event.source_timestamp_ms ?? event.observed_at_ms;
      const info = node('span'); info.append(node('strong', human(event.reason_code || event.state)), node('small', `${human(event.step_id || 'session')} · ${human(event.state)}`)); button.append(node('time', time(stamp)), info);
      button.addEventListener('click', () => { const frame = evidence().find(e => event.evidence_ids?.includes(e.id)) || evidence().find(e => e.source_timestamp_ms === stamp); put('#ss-step-evidence', pretty(event)); if (S.sourceType === 'video' && S.sourceURL && Number.isFinite(stamp)) $('#ss-video').currentTime = stamp / 1000; if (frame) selectFrame(frame.id); else message('No accessible supporting frame is recorded for this event. Its audit record is retained.', true); }); li.append(button); return li;
    }) : [node('li', 'No session events yet.', 'safety-muted')]));
  }
  function renderTrace(run) {
    $('#ss-agent-trace').replaceChildren(...(run.agent_trace?.length ? run.agent_trace.map(action => {
      const item = node('article'); item.append(node('h3', `${human(action.action)} · ${action.executed ? 'executed' : 'requested / not executed'}`), node('p', action.reason || 'Reason not recorded'), node('p', `${time(action.source_timestamp_ms)} · ${action.is_new_capture ? 'distinct source frame / capture' : 'same capture / no fresh evidence'} · ${human(action.capture_kind || 'kind not recorded')}${Number.isFinite(action.cost_ms) ? ' · ' + action.cost_ms.toFixed(1) + ' ms' : ''}`));
      const details = node('details'); details.append(node('summary', 'Action & budget record'), node('pre', pretty(action))); item.append(details); return item;
    }) : [node('p', 'No executed backend actions recorded.', 'safety-muted')]));
  }
  async function imageURL(path, run) { const r = await authorized(path, cap(run)); if (!(r.headers.get('content-type') || '').startsWith('image/')) throw new Error('Evidence response is not an image.'); return blobURL(await r.blob()); }
  async function selectFrame(id, selected = true) {
    const frame = evidence().find(f => f.id === id); if (!frame || !selected && S.frame?.id === id) return;
    S.stickyFrame ||= selected; const epoch = S.epoch, selection = ++S.selection;
    try { const url = await imageURL(frame.overlay_url || frame.original_url, S.run); if (epoch !== S.epoch || selection !== S.selection) { revoke(url); return; } revoke($('#ss-frame').getAttribute('src')); $('#ss-frame').src = url; S.frame = frame; show('frame'); put('#ss-clock', `Source ${time(frame.source_timestamp_ms)} · frame ${frame.frame_index}`); $('#ss-original').disabled = !frame.original_url; $('#ss-overlay').disabled = !frame.overlay_url; }
    catch (error) { if (epoch === S.epoch) message('Evidence unavailable: ' + error.message, true); }
  }
  async function switchLayer(kind) {
    const path = S.frame?.[kind + '_url']; if (!path) return;
    const epoch = S.epoch, selection = ++S.selection;
    try { const url = await imageURL(path, S.run); if (epoch !== S.epoch || selection !== S.selection) { revoke(url); return; } revoke($('#ss-frame').getAttribute('src')); $('#ss-frame').src = url; show('frame'); } catch (error) { message(error.message, true); }
  }
  async function showVideo() {
    if (S.stream) return show('video');
    try { if (S.sourceSession !== S.run?.id && S.run?.media?.video_url) { const epoch = S.epoch, response = await authorized(S.run.media.video_url, cap(S.run)), blob = await response.blob(); if (epoch !== S.epoch) return; revoke(S.sourceURL); S.sourceURL = blobURL(blob); S.sourceType = 'video'; S.sourceSession = S.run.id; } if (!S.sourceURL || S.sourceType !== 'video') throw new Error('This session has no source video.'); $('#ss-video').controls = true; $('#ss-video').src = S.sourceURL; show('video'); } catch (error) { message(error.message, true); }
  }
  async function cancel() {
    if (!S.run) return; const run = S.run; ++S.epoch; S.controller?.abort(); clearTimeout(S.poll); cameraOff();
    try { if (S.framePromise) await S.framePromise.catch(() => {}); S.run = await json('/cancel', { method: 'POST' }, run); render(S.run); poll(S.epoch); message('Cancellation requested. The service state confirms when processing stops; partial evidence remains.'); } catch (error) { message('Capture stopped; server cancellation unconfirmed: ' + error.message, true); } finally { busy(false); }
  }
  async function reinspect(action) {
    if (!S.run || S.busy) return; busy(true);
    try {
      const result = await json('/reinspect', post({ action }));
      if (result.child_session) {
        const parent = S.run.id; remember(result.child_session); ++S.epoch; clearTimeout(S.poll); releaseMedia();
        S.run = await json('', {}, result.child_session); S.frame = null; S.stickyFrame = false; S.renderKey = '';
        render(S.run); show('empty'); message(`Fresh-view session opened, linked to ${parent.slice(0, 8)}. Supply an actual image below; the original finding remains in the parent record.`);
      } else { S.run = result.id && result.state ? result : await json(''); render(S.run); message('Reinspection request recorded. Only executed service actions appear in the trace.'); }
      poll(S.epoch);
    } catch (error) { message(error.message, true); } finally { busy(false); }
  }
  async function newView(file) {
    if (!file || !S.run || S.busy) return; busy(true);
    try {
      await metadata(file, 'STILL_IMAGE'); const form = new FormData(); form.append('file', file, file.name); form.append('source_timestamp_ms', '0');
      await json('/frames', { method: 'POST', body: form });
      S.run = await json('/finish', post({ final_checkpoint: S.run.configuration?.final_checkpoint ?? S.run.final_checkpoint ?? false }));
      S.stickyFrame = false; render(S.run); poll(S.epoch); message('Actual supplied view analyzed and finalized. A still does not establish a temporal assembly sequence.');
    } catch (error) { message(error.message, true); } finally { $('#ss-new-view').value = ''; busy(false); }
  }
  async function review(event) {
    event.preventDefault(); if (!S.run || S.busy) return; const decision = event.submitter?.value, note = $('#ss-review-note').value.trim();
    if (!['acknowledge', 'refute'].includes(decision) || !note) return message('Add an explanation before acknowledging or refuting.', true);
    busy(true); try { const result = await json('/acknowledgements', post({ decision, note })); S.run = result.id && result.state ? result : await json(''); render(S.run); $('#ss-review-note').value = ''; message('Operator review appended. The original machine finding is preserved.'); } catch (error) { message(error.message, true); } finally { busy(false); }
  }
  async function exportReport(format) {
    if (!S.run) return;
    try { const response = await req('/report?format=' + format), url = blobURL(await response.blob()), link = node('a'); link.href = url; link.download = `REFLEX-safety-${S.run.id}.${format === 'json' ? 'json' : 'html'}`; document.body.append(link); link.click(); link.remove(); setTimeout(() => revoke(url), 1000); message(format === 'html' ? 'Printable HTML downloaded. Open it and use the browser print command.' : 'Actual session evidence JSON downloaded.'); } catch (error) { message(error.message, true); }
  }
  async function openSaved() {
    const id = $('#ss-saved-session').value; if (!id || S.busy || S.stream) return; busy(true); const epoch = ++S.epoch; clearTimeout(S.poll);
    try { const run = await json('', {}, { id }); if (epoch !== S.epoch) return; releaseMedia(); S.run = run; S.frame = null; S.stickyFrame = false; S.renderKey = ''; render(run); poll(epoch); message('Loaded the actual saved session record.'); } catch (error) { message(error.message, true); } finally { busy(false); }
  }
  async function compare() {
    const a = $('#ss-compare-a').value, b = $('#ss-compare-b').value; if (!a || !b) return message('Choose two saved runs.', true); busy(true);
    try { const [first, second] = await Promise.all([json('', {}, { id: a }), json('', {}, { id: b })]); compareRuns(first, second); const table = node('table'), head = node('tr'); head.append(node('th', 'Recorded measure'), node('th', human(first.policy)), node('th', human(second.policy))); table.append(head);
      for (const [label, value] of [['Quality gate', r => human(r.decision?.status)], ['Reasons', r => r.decision?.reason_codes?.map(human).join(', ')], ['Analyzed frames', r => r.processing?.analyzed_frames], ['Extra inspections', r => r.processing?.extra_inspections], ['Processing elapsed ms', r => r.processing?.elapsed_ms], ['Source label', r => human(r.media?.source)]]) { const row = node('tr'); row.append(node('th', label), node('td', value(first) ?? 'Not recorded'), node('td', value(second) ?? 'Not recorded')); table.append(row); }
      $('#ss-comparison').replaceChildren(node('p', 'Same source and recipe/settings; two actual policy records. One source is not a real-assembly benchmark.'), table);
    } catch (error) { put('#ss-comparison', error.message); message(error.message, true); } finally { busy(false); }
  }
  async function boot() {
    try { const stored = JSON.parse(sessionStorage.getItem(storeKey) || '[]'); if (Array.isArray(stored)) S.registry = stored.filter(r => typeof r.id === 'string' && typeof r.access_token === 'string'); } catch { /* This tab can still create a session. */ }
    renderSaved(); try { document.body.classList.toggle('reduced-motion', localStorage.getItem('reflex-reduced-motion') === 'true'); } catch { /* System preference is still respected. */ }
    try { const [recipes, fixtures] = await Promise.all([publicJSON('/api/safety/recipes'), publicJSON('/api/safety/fixtures')]); S.recipes = recipes.recipes || []; S.fixtures = fixtures.fixtures || []; if (!S.recipes.length) throw new Error('No validated teaching recipe is available.'); $('#ss-recipe').replaceChildren(...S.recipes.map(r => new Option(`${r.name} · ${r.version}`, r.recipe_id))); $('#ss-fixture').replaceChildren(new Option('Choose a generated software test', ''), ...S.fixtures.map(f => new Option(f.name, f.id))); renderRecipe(S.recipes[0]); put('#ss-runtime', 'Safety service connected'); $('#ss-runtime-dot').classList.add('online'); message('Recipe loaded. Choose a source and verify panel alignment.'); controls(); }
    catch (error) { put('#ss-runtime', 'Safety service unavailable'); message(error.message + ' The original Inspection Studio remains available.', true); controls(); }
  }
  $('#ss-form').addEventListener('submit', createSession); $('#ss-source').addEventListener('change', sourceChanged); $('#ss-file').addEventListener('change', e => chooseFile(e.target.files[0])); $('#ss-use-fixture').addEventListener('click', loadFixture); $('#ss-recipe').addEventListener('change', () => renderRecipe(S.recipes.find(r => r.recipe_id === $('#ss-recipe').value)));
  $('#ss-cancel').addEventListener('click', cancel); $('#ss-stop-camera').addEventListener('click', () => finishCamera()); $('#ss-show-video').addEventListener('click', showVideo); $('#ss-original').addEventListener('click', () => switchLayer('original')); $('#ss-overlay').addEventListener('click', () => switchLayer('overlay')); $('#ss-next-frames').addEventListener('click', () => reinspect('OBSERVE_NEXT_FRAMES')); $('#ss-request-view').addEventListener('click', () => reinspect('REQUEST_SECOND_VIEW')); $('#ss-new-view').addEventListener('change', e => newView(e.target.files[0])); $('#ss-review-form').addEventListener('submit', review); $('#ss-export-json').addEventListener('click', () => exportReport('json')); $('#ss-export-html').addEventListener('click', () => exportReport('html')); $('#ss-saved-session').addEventListener('change', controls); $('#ss-load-session').addEventListener('click', openSaved); $('#ss-compare').addEventListener('click', compare);
  $('#ss-video').addEventListener('timeupdate', () => { if (!S.stream && !$('#ss-video').hidden) put('#ss-clock', 'Replay ' + time($('#ss-video').currentTime * 1000)); });
  $('#ss-video').addEventListener('error', () => { if (S.sourceURL) message('This browser cannot play the source codec. Processing uses the original clip; select JPEG frames in the evidence timeline after analysis.', true); });
  window.addEventListener('pagehide', () => { ++S.epoch; S.controller?.abort(); clearTimeout(S.poll); cameraOff(); releaseMedia(); });
  boot();
})();
