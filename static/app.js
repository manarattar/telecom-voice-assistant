'use strict';

// ── Backend URL ───────────────────────────────────────────────────────────────
const API_BASE = (() => {
  const h = window.location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return '';
  if (h.includes('onrender.com')) return '';
  return 'https://telecom-voice-assistant.onrender.com';
})();

// ── API client ────────────────────────────────────────────────────────────────
const API = {
  async customers()   { return (await fetch(API_BASE + '/api/customers')).json(); },
  async agents()      { return (await fetch(API_BASE + '/api/agents')).json(); },
  async realtimeSession(agentId, customer, language) {
    const r = await fetch(API_BASE + '/api/realtime-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId, customer, language }),
    });
    if (!r.ok) throw new Error((await r.json()).error || r.status);
    return r.json();
  },
  async analyze(text, language) {
    const r = await fetch(API_BASE + '/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language }),
    });
    return r.ok ? r.json() : null;
  },
};

// ── App state ─────────────────────────────────────────────────────────────────
let state = {
  customer: null,
  language: 'nl',
  agentId: 'sarah',
  intent: 'unknown',
  confidence: 0,
  sentiment: 'neutral',
  frustrationLevel: 1,
  turnCount: 0,
  escalated: false,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const micBtn          = $('micBtn');
const iconMic         = $('iconMic');
const iconStop        = $('iconStop');
const iconInterrupt   = $('iconInterrupt');
const spin            = $('spin');
const micLabel        = $('micLabel');
const avatarWrap      = $('avatarWrap');
const agentAvatar     = $('agentAvatar');
const agentNameEl     = $('agentName');
const statusText      = $('statusText');
const agentStatus     = $('agentStatus');
const transcript      = $('transcript');
const transcriptEmpty = $('transcriptEmpty');
const waveform        = $('waveform');
const customerSelect  = $('customerSelect');
const langToggle      = $('langToggle');
const agentPicker     = $('agentPicker');
const exportBtn       = $('exportBtn');
const surveyModal     = $('surveyModal');

// ── i18n ──────────────────────────────────────────────────────────────────────
const T = {
  nl: {
    idle: 'Klik om gesprek te starten',
    active: 'Gesprek actief — klik om te beëindigen',
    connecting: 'Verbinden…',
    speaking: 'spreekt',
    available: 'Beschikbaar',
    listening: 'Luistert',
    thinking: 'Verbinden…',
    micDenied: 'Microfoon toegang geweigerd. Sta toegang toe in uw browser.',
    sessionError: 'Kon geen verbinding openen. Probeer opnieuw.',
  },
  en: {
    idle: 'Click to start conversation',
    active: 'Conversation active — click to end',
    connecting: 'Connecting…',
    speaking: 'speaking',
    available: 'Available',
    listening: 'Listening',
    thinking: 'Connecting…',
    micDenied: 'Microphone access denied. Please allow it in your browser.',
    sessionError: 'Could not open session. Please try again.',
  },
};
function t(key) { return (T[state.language] || T.nl)[key] || key; }

// ── Agent metadata ────────────────────────────────────────────────────────────
const AGENT_META = {
  sarah: { color: '#10b981', emoji: '🎧', name: 'Sarah' },
  alex:  { color: '#6366f1', emoji: '🎯', name: 'Alex'  },
  nina:  { color: '#f59e0b', emoji: '💼', name: 'Nina'  },
};

function applyAgentTheme(agentId) {
  const meta = AGENT_META[agentId] || AGENT_META.sarah;
  document.documentElement.style.setProperty('--agent-color', meta.color);
  if (agentAvatar) agentAvatar.textContent = meta.emoji;
  if (agentNameEl) agentNameEl.textContent  = meta.name;
  agentPicker.querySelectorAll('.agt-card').forEach(c => {
    c.classList.toggle('active', c.dataset.agent === agentId);
    c.style.setProperty('--agent-color', meta.color);
  });
}

// ── UI mode ───────────────────────────────────────────────────────────────────
// States: idle | connecting | active | speaking
let uiMode = 'idle';

const TRY_SAYING = {
  nl: ['"Mijn internet doet het niet"', '"Ik heb een vraag over mijn factuur"', '"Mijn wifi is erg langzaam"'],
  en: ['"My internet is not working"', '"I have a question about my bill"', '"My wifi is very slow"'],
};

function updateTrySaying() {
  const el = $('trySaying');
  if (!el) return;
  const chips = $('trySayingChips');
  const label = $('trySayingLabel');
  const phrases = TRY_SAYING[state.language] || TRY_SAYING.nl;
  if (label) label.textContent = state.language === 'en' ? 'Try saying:' : 'Probeer te zeggen:';
  if (chips) chips.innerHTML = phrases.map(p => `<span class="try-chip">${p}</span>`).join('');
}

function setMode(mode) {
  uiMode = mode;

  micBtn.className = 'mic-btn' + (mode !== 'idle' ? ' ' + mode : '');
  micBtn.disabled  = mode === 'connecting';

  iconMic.style.display       = mode === 'idle' ? '' : 'none';
  iconStop.style.display      = mode === 'active' ? '' : 'none';
  iconInterrupt.style.display = mode === 'speaking' ? '' : 'none';
  spin.style.display          = mode === 'connecting' ? '' : 'none';

  const agentName = AGENT_META[state.agentId]?.name || 'Agent';
  if (mode === 'speaking')    micLabel.textContent = agentName + ' ' + t('speaking') + '…';
  else if (mode === 'active') micLabel.textContent = t('active');
  else                        micLabel.textContent = t(mode) || t('idle');

  waveform.classList.toggle('active', mode === 'active');
  avatarWrap.className = 'avatar-wrap' + (mode === 'speaking' ? ' speaking' : '');

  const trySaying = $('trySaying');
  if (trySaying) trySaying.classList.toggle('hidden', mode !== 'idle');

  const color = mode === 'connecting' ? '#f59e0b' : 'var(--agent-color)';
  agentStatus.style.color       = color;
  agentStatus.style.background  = `color-mix(in srgb, ${color} 15%, transparent)`;
  agentStatus.style.borderColor = `color-mix(in srgb, ${color} 25%, transparent)`;

  const statusKey = { idle: 'available', connecting: 'thinking',
                      active: 'listening', speaking: 'speaking' }[mode] || 'available';
  const lbl = t(statusKey);
  statusText.textContent = statusKey === 'speaking' ? agentName + ' ' + lbl : lbl;
}

// ── Transcript helpers ────────────────────────────────────────────────────────
let _transcript = [];   // [{role, content}] — used for export

function clearTranscript() {
  transcript.innerHTML = '';
  transcriptEmpty.textContent = t('connecting');
  transcript.appendChild(transcriptEmpty);
  _transcript = [];
}

function addBubble(role, text) {
  if (transcriptEmpty.parentNode) transcriptEmpty.remove();
  const wrap = document.createElement('div');
  wrap.className = `bubble ${role}`;
  const sender = document.createElement('div');
  sender.className = 'bubble-sender';
  sender.textContent = role === 'assistant'
    ? (AGENT_META[state.agentId]?.name || 'Agent')
    : (state.customer?.name || 'Klant');
  const body = document.createElement('div');
  body.className = 'bubble-text';
  body.textContent = text;
  wrap.append(sender, body);
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  _transcript.push({ role: role === 'assistant' ? 'assistant' : 'user', content: text });
  return body;
}

// ── Dashboard & chart ─────────────────────────────────────────────────────────
const INTENT_LABELS = {
  nl: { wifi_slow:'📶 Trage WiFi', wifi_down:'📶 WiFi storing', internet_down:'🚫 Geen internet',
        internet_unstable:'⚡ Onstabiel', mobile_data:'📱 Mobiele data', sim_activation:'📲 SIM',
        billing:'💶 Factuur', subscription_change:'📋 Abonnement', contract:'📄 Contract',
        outage:'⚡ Storing', escalation:'🚨 Escalatie', unknown:'❓ —' },
  en: { wifi_slow:'📶 Slow WiFi', wifi_down:'📶 WiFi down', internet_down:'🚫 No internet',
        internet_unstable:'⚡ Unstable', mobile_data:'📱 Mobile data', sim_activation:'📲 SIM',
        billing:'💶 Billing', subscription_change:'📋 Subscription', contract:'📄 Contract',
        outage:'⚡ Outage', escalation:'🚨 Escalation', unknown:'❓ —' },
};
const SENT_MAP   = { positive:'😊', neutral:'😐', frustrated:'😤', angry:'😡', negative:'😟' };
const SENT_SCORE = { positive:5, neutral:3, frustrated:2, angry:1, negative:1 };

let sentimentChart = null;

function initChart() {
  if (!window._chartJsLoaded || sentimentChart) return;
  const ctx = $('sentimentChart').getContext('2d');
  sentimentChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{
      data: [], borderColor: AGENT_META[state.agentId]?.color || '#10b981',
      backgroundColor: 'rgba(16,185,129,0.08)', fill: true, tension: 0.4,
      pointRadius: 4, pointBackgroundColor: AGENT_META[state.agentId]?.color || '#10b981',
    }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: { legend: { display: false } },
      scales: {
        y: { min:0, max:5, grid:{ color:'rgba(255,255,255,0.05)' }, ticks:{ color:'#5a6070', stepSize:1 } },
        x: { grid:{ color:'rgba(255,255,255,0.05)' }, ticks:{ color:'#5a6070' } },
      },
    },
  });
}

function pushChartPoint(sentiment, turn) {
  if (!sentimentChart) return;
  sentimentChart.data.labels.push('T' + turn);
  sentimentChart.data.datasets[0].data.push(SENT_SCORE[sentiment] || 3);
  sentimentChart.update('none');
}

function resetChart() {
  if (!sentimentChart) return;
  sentimentChart.data.labels = [];
  sentimentChart.data.datasets[0].data = [];
  sentimentChart.update('none');
}

function updateDashboard() {
  const labels = INTENT_LABELS[state.language] || INTENT_LABELS.nl;
  $('dIntent').textContent    = labels[state.intent] || state.intent || '—';
  $('dSentiment').textContent = (SENT_MAP[state.sentiment] || '😐') + ' ' + (state.sentiment || '');
  $('dConf').textContent      = state.confidence ? Math.round(state.confidence * 100) + '%' : '—';
  $('dTurns').textContent     = state.turnCount ?? 0;
  if (state.escalated || state.frustrationLevel >= 3) $('escChip').style.display = '';
}

// ── AudioContext ──────────────────────────────────────────────────────────────
let _audioCtx = null;

function _unlockAudio() {
  if (_audioCtx) return;
  try { _audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (_) {}
}

// ── PCM playback — gapless scheduling ────────────────────────────────────────
let _nextPlayAt    = 0;
let _activeSrcs    = [];
let _speechEndTmr  = null;

function _schedulePCM16(b64) {
  if (!_audioCtx) return;
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const i16   = new Int16Array(bytes.buffer);
  const f32   = new Float32Array(i16.length);
  for (let j = 0; j < i16.length; j++) f32[j] = i16[j] / 32768;

  const buf = _audioCtx.createBuffer(1, f32.length, 16000);
  buf.copyToChannel(f32, 0);

  const src = _audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(_audioCtx.destination);

  const now     = _audioCtx.currentTime;
  const startAt = Math.max(now + 0.01, _nextPlayAt);
  src.start(startAt);
  _nextPlayAt = startAt + buf.duration;
  _activeSrcs.push(src);

  src.onended = () => {
    _activeSrcs = _activeSrcs.filter(s => s !== src);
    if (_activeSrcs.length === 0 && uiMode === 'speaking') {
      clearTimeout(_speechEndTmr);
      _speechEndTmr = setTimeout(() => {
        if (_ws && uiMode === 'speaking') setMode('active');
      }, 200);
    }
  };
}

function _clearAudio() {
  clearTimeout(_speechEndTmr);
  _activeSrcs.forEach(s => { try { s.stop(); } catch (_) {} });
  _activeSrcs = [];
  _nextPlayAt  = 0;
}

// ── PCM capture — ScriptProcessorNode ────────────────────────────────────────
let _scriptNode    = null;
let _captureSource = null;
let _analyser      = null;
let _animFrame     = null;

function _downsample(buf, fromRate, toRate) {
  if (fromRate === toRate) return buf;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(buf.length / ratio));
  for (let i = 0; i < out.length; i++) out[i] = buf[Math.floor(i * ratio)];
  return out;
}

function _f32toI16(f32) {
  const i16 = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    i16[i] = s < 0 ? s * 32768 : s * 32767;
  }
  return i16;
}

function _toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let b = '';
  for (let i = 0; i < bytes.length; i += 8192)
    b += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(b);
}

function _startCapture(stream) {
  if (!_audioCtx || _scriptNode) return;
  if (_audioCtx.state === 'suspended') _audioCtx.resume();

  _captureSource = _audioCtx.createMediaStreamSource(stream);
  _scriptNode    = _audioCtx.createScriptProcessor(4096, 1, 1);

  // Silent sink — avoids mic feedback while keeping the graph active
  const sink = _audioCtx.createGain();
  sink.gain.value = 0;
  _scriptNode.connect(sink);
  sink.connect(_audioCtx.destination);

  _captureSource.connect(_scriptNode);

  _scriptNode.onaudioprocess = e => {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return;
    const raw  = e.inputBuffer.getChannelData(0);
    const down = _downsample(raw, _audioCtx.sampleRate, 16000);
    const i16  = _f32toI16(down);
    _ws.send(JSON.stringify({ user_audio_chunk: _toBase64(i16.buffer) }));
  };

  // Waveform visualisation from mic
  _analyser = _audioCtx.createAnalyser();
  _analyser.fftSize = 64;
  _captureSource.connect(_analyser);
  const data = new Uint8Array(_analyser.frequencyBinCount);
  const bars = () => waveform.querySelectorAll('span');
  waveform.classList.remove('fallback');
  const draw = () => {
    _animFrame = requestAnimationFrame(draw);
    _analyser.getByteFrequencyData(data);
    bars().forEach((b, i) => { b.style.height = Math.max(4, (data[i * 2] || 0) / 255 * 26) + 'px'; });
  };
  draw();
}

function _stopCapture() {
  if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
  waveform.querySelectorAll('span').forEach(b => { b.style.height = '4px'; });
  if (_scriptNode)    { _scriptNode.disconnect();    _scriptNode    = null; }
  if (_captureSource) { _captureSource.disconnect(); _captureSource = null; }
  if (_analyser)      { _analyser.disconnect();      _analyser      = null; }
  waveform.classList.remove('fallback');
}

// ── ConvAI session ────────────────────────────────────────────────────────────
let _ws             = null;
let _micStream      = null;
let _userBubbleBody = null;   // body element of current user turn bubble
let _convTurns      = 0;

async function startSession() {
  if (_ws) { endSession(); return; }

  _unlockAudio();
  if (!_audioCtx) { alert('Web Audio niet beschikbaar.'); return; }

  setMode('connecting');

  // 1. Signed URL + per-session context from backend
  let session;
  try {
    session = await API.realtimeSession(state.agentId, state.customer, state.language);
  } catch (e) {
    addBubble('assistant', '⚠️ ' + t('sessionError'));
    setMode('idle');
    return;
  }

  // 2. Mic permission
  try {
    _micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  } catch (_) {
    alert(t('micDenied'));
    setMode('idle');
    return;
  }

  clearTranscript();
  resetChart();
  $('escChip').style.display = 'none';
  _convTurns = 0;
  applyAgentTheme(session.agent?.id || state.agentId);

  // 3. WebSocket
  _ws = new WebSocket(session.signed_url);

  _ws.onopen = () => {
    const salutation = state.customer?.name ? `, ${state.customer.name}` : '';
    _ws.send(JSON.stringify({
      type: 'conversation_initiation_client_data',
      dynamic_variables: {
        customer_context: session.customer_context || '',
        customer_salutation: salutation,
      },
    }));
    // Do NOT start audio here — wait for conversation_initiation_metadata
    // so the server has finished initializing the session before we send audio.
  };

  _ws.onmessage = _handleMsg;

  _ws.onclose = e => {
    console.warn('[ConvAI] closed', e.code, e.reason);
    _cleanup();
    setMode('idle');
  };

  _ws.onerror = err => {
    console.error('[ConvAI] error', err);
    _cleanup();
    setMode('idle');
  };
}

function endSession() {
  if (!_ws) return;
  const turns = _convTurns;
  _ws.onclose = null;
  try { _ws.close(); } catch (_) {}
  _ws = null;
  _cleanup();
  setMode('idle');

  if (turns >= 2) {
    showSurvey({
      agentId: state.agentId,
      agentName: AGENT_META[state.agentId]?.name,
      customerName: state.customer?.name,
      intent: state.intent,
      turns,
      sentiment: state.sentiment,
      escalated: state.escalated,
    });
  }
}

function _cleanup() {
  _stopCapture();
  _clearAudio();
  if (_micStream) { _micStream.getTracks().forEach(t => t.stop()); _micStream = null; }
  _userBubbleBody = null;
}

function _handleMsg(evt) {
  let msg;
  try { msg = JSON.parse(evt.data); } catch (_) { return; }

  switch (msg.type) {

    case 'conversation_initiation_metadata':
      setMode('active');
      _startCapture(_micStream);
      break;

    case 'user_transcript': {
      const text = msg.user_transcription_event?.user_transcript;
      if (!text) break;
      if (_userBubbleBody) {
        _userBubbleBody.textContent = text;
        // Update transcript record
        const last = _transcript[_transcript.length - 1];
        if (last?.role === 'user') last.content = text;
      } else {
        _userBubbleBody = addBubble('user', text);
        _convTurns++;
        state.turnCount = _convTurns;
        // Background intent/sentiment analysis
        API.analyze(text, state.language).then(d => {
          if (!d) return;
          state.intent           = d.intent;
          state.sentiment        = d.sentiment;
          state.frustrationLevel = d.frustration_level;
          state.confidence       = d.confidence;
          updateDashboard();
          pushChartPoint(d.sentiment, _convTurns);
        }).catch(() => {});
      }
      break;
    }

    case 'agent_response': {
      const text = msg.agent_response_event?.agent_response;
      if (text) {
        addBubble('assistant', text);
        _userBubbleBody = null;   // next user speech → new bubble
      }
      break;
    }

    case 'audio': {
      const b64 = msg.audio_event?.audio_base_64;
      if (!b64) break;
      if (_audioCtx.state === 'suspended') _audioCtx.resume();
      _schedulePCM16(b64);
      if (uiMode !== 'speaking') setMode('speaking');
      break;
    }

    case 'interruption':
      _clearAudio();
      _userBubbleBody = null;
      if (_ws) setMode('active');
      break;

    case 'ping':
      if (_ws?.readyState === WebSocket.OPEN)
        _ws.send(JSON.stringify({ type: 'pong', event_id: msg.ping_event?.event_id }));
      break;
  }
}

// ── Call history (localStorage) ───────────────────────────────────────────────
const HISTORY_KEY = 'tnl_call_history';

function saveCall(data) {
  const history = loadHistory();
  history.unshift({
    id: Date.now(), agentId: data.agentId, agentName: data.agentName,
    customerName: data.customerName, intent: data.intent, turns: data.turns,
    sentiment: data.sentiment, escalated: data.escalated,
    resolved: data.resolved, rating: data.rating,
    ts: new Date().toISOString(),
  });
  history.splice(20);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch (_) { return []; }
}

function renderHistory() {
  const list = $('historyList');
  const history = loadHistory();
  if (!history.length) { list.innerHTML = '<div class="history-empty">Nog geen gesprekken.</div>'; return; }
  list.innerHTML = history.map(h => {
    const time = new Date(h.ts).toLocaleString('nl-NL', { hour:'2-digit', minute:'2-digit', day:'numeric', month:'short' });
    const meta = AGENT_META[h.agentId] || AGENT_META.sarah;
    return `<div class="history-item">
      <div class="history-emoji">${meta.emoji}</div>
      <div class="history-info">
        <div class="history-top"><span class="history-name">${h.customerName||'Onbekend'}</span><span class="history-time">${time}</span></div>
        <div class="history-sub">${meta.name} · ${h.turns} beurten · ${h.intent.replace(/_/g,' ')}</div>
        <div class="history-pills">
          ${h.resolved ? '<span class="history-pill resolved">✓ Opgelost</span>' : ''}
          ${h.escalated ? '<span class="history-pill escalated">🚨 Escalatie</span>' : ''}
          ${h.rating ? '<span class="history-stars">' + '★'.repeat(h.rating) + '</span>' : ''}
        </div>
      </div></div>`;
  }).join('');
}

// ── Post-call survey ──────────────────────────────────────────────────────────
let _surveyRating = 0, _surveyPending = null;

function showSurvey(callData) {
  _surveyPending = callData; _surveyRating = 0;
  surveyModal.querySelectorAll('.star').forEach(s => s.classList.remove('lit'));
  $('surveyYes').classList.remove('selected-yes');
  $('surveyNo').classList.remove('selected-no');
  surveyModal.style.display = 'flex';
}

function hideSurvey(rating, resolved) {
  surveyModal.style.display = 'none';
  if (_surveyPending) {
    const callData = { ..._surveyPending, rating: rating || 0, resolved: resolved ?? null };
    saveCall(callData);
    renderHistory();
    // Also log to dedicated feedback store for analytics
    const log = JSON.parse(localStorage.getItem('voice_feedback') || '[]');
    log.push({ rating: rating || 0, resolved, intent: _surveyPending.intent, turns: _surveyPending.turns, timestamp: new Date().toISOString() });
    localStorage.setItem('voice_feedback', JSON.stringify(log));
    _surveyPending = null;
  }
}

function initSurveyEvents() {
  surveyModal.querySelectorAll('.star').forEach(star => {
    star.addEventListener('click', () => {
      _surveyRating = +star.dataset.val;
      surveyModal.querySelectorAll('.star').forEach((s, i) => s.classList.toggle('lit', i < _surveyRating));
    });
  });
  $('surveyYes').addEventListener('click', () => {
    $('surveyYes').classList.add('selected-yes');
    $('surveyNo').classList.remove('selected-no');
    if (_surveyRating) hideSurvey(_surveyRating, true);
  });
  $('surveyNo').addEventListener('click', () => {
    $('surveyNo').classList.add('selected-no');
    $('surveyYes').classList.remove('selected-yes');
    if (_surveyRating) hideSurvey(_surveyRating, false);
  });
  $('surveySkip').addEventListener('click', () => hideSurvey(0, null));
}

// ── Export ────────────────────────────────────────────────────────────────────
function exportCall() {
  if (!_transcript.length) return;
  const meta = AGENT_META[state.agentId] || AGENT_META.sarah;
  const lines = [
    'TelecomNL AI Support — Gespreksverslag',
    '========================================',
    `Datum:   ${new Date().toLocaleString('nl-NL')}`,
    `Agent:   ${meta.name} ${meta.emoji}`,
    `Klant:   ${state.customer?.name || 'Onbekend'}`,
    `Beurten: ${_convTurns}`,
    '',
    '--- GESPREK ---',
    ..._transcript.map(m => `[${m.role === 'assistant' ? meta.name : (state.customer?.name||'Klant')}] ${m.content}`),
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `gesprek-${Date.now()}.txt`; a.click();
  URL.revokeObjectURL(url);
}

// ── Collapsibles ──────────────────────────────────────────────────────────────
function initCollapsible(toggleId, bodyId) {
  const btn = $(toggleId), body = $(bodyId);
  btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!open));
    body.style.display = open ? 'none' : 'block';
    if (!open && toggleId === 'chartToggle')   initChart();
    if (!open && toggleId === 'historyToggle') renderHistory();
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function init() {
  const overlay = document.createElement('div');
  overlay.id = 'loadOverlay';
  overlay.innerHTML = '<div class="load-logo">📡</div><div class="load-text">TelecomNL laden…</div>';
  document.body.prepend(overlay);

  let customers, agentList;
  try {
    [customers, agentList] = await Promise.all([API.customers(), API.agents()]);
  } catch (_) {
    overlay.querySelector('.load-text').textContent = 'Server niet bereikbaar. Herlaad de pagina.';
    return;
  }

  // Customer dropdown
  customers.forEach(c => customerSelect.append(new Option(c.name, c.id)));
  state.customer = customers[0];

  function updateCustomerCard(customer) {
    const card = $('customerCard');
    if (!card || !customer) return;
    const lang = state.language;
    $('customerCardLabel').textContent = lang === 'en' ? 'Scenario' : 'Klantscenario';
    $('customerCardName').textContent = customer.name || '';
    const plan = customer.plan_name || customer.plan || '';
    const balance = customer.outstanding_balance != null ? `€${Number(customer.outstanding_balance).toFixed(2)} open` : '';
    $('customerCardDetail').textContent = [plan, balance].filter(Boolean).join(' · ') || (lang === 'en' ? 'No plan info' : 'Geen planinfo');
    card.style.display = 'flex';
  }

  updateCustomerCard(state.customer);

  // Agent picker
  agentList.forEach(agent => {
    const card = document.createElement('div');
    card.className = 'agt-card';
    card.dataset.agent = agent.id;
    card.style.setProperty('--agent-color', agent.color);
    card.innerHTML = `<div class="agt-emoji">${agent.emoji}</div>
      <div class="agt-name">${agent.name}</div>
      <div class="agt-lang">${agent.language.toUpperCase()}</div>`;
    card.addEventListener('click', () => {
      state.agentId  = agent.id;
      state.language = agent.language === 'en' ? 'en' : state.language;
      langToggle.textContent = state.language === 'en' ? '🇬🇧 EN' : '🇳🇱 NL';
      applyAgentTheme(agent.id);
      // Restart active session with new agent
      if (_ws) { endSession(); setTimeout(startSession, 300); }
    });
    agentPicker.appendChild(card);
  });

  // Customer change
  customerSelect.addEventListener('change', () => {
    state.customer = customers.find(x => x.id === customerSelect.value) || state.customer;
    updateCustomerCard(state.customer);
    if (_ws) { endSession(); setTimeout(startSession, 300); }
  });

  // Language toggle
  langToggle.addEventListener('click', () => {
    state.language = state.language === 'nl' ? 'en' : 'nl';
    langToggle.textContent = state.language === 'nl' ? '🇳🇱 NL' : '🇬🇧 EN';
    updateTrySaying();
    if (_ws) { endSession(); setTimeout(startSession, 300); }
  });

  // New call button — end current session (survey fires inside endSession)
  $('newCallBtn').addEventListener('click', () => {
    if (_ws) endSession();
    else { clearTranscript(); resetChart(); $('escChip').style.display = 'none'; }
  });

  // Mic button — toggle session
  micBtn.addEventListener('click', () => {
    _unlockAudio();
    if (uiMode === 'idle') startSession();
    else endSession();
  });

  exportBtn.addEventListener('click', exportCall);

  initCollapsible('chartToggle',   'chartBody');
  initCollapsible('historyToggle', 'historyBody');
  initSurveyEvents();
  updateTrySaying();

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.code === 'Space')  { e.preventDefault(); micBtn.click(); }
    if (e.code === 'Escape') { if (_ws) endSession(); }
  });

  // Keyboard hint
  const hint = document.createElement('div');
  hint.className = 'kbd-hint';
  hint.innerHTML = '<kbd>Space</kbd> start/stop &nbsp;·&nbsp; <kbd>Esc</kbd> einde gesprek';
  micBtn.closest('.mic-area').appendChild(hint);

  applyAgentTheme('sarah');
  setMode('idle');

  overlay.style.transition = 'opacity 0.35s';
  overlay.style.opacity    = '0';
  setTimeout(() => overlay.remove(), 400);
}

document.addEventListener('DOMContentLoaded', init);
