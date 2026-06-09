'use strict';

// ── Backend routing ───────────────────────────────────────────────────────────
const API_BASE = (() => {
  const h = window.location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return '';
  if (h.includes('onrender.com')) return '';
  return 'https://telecom-voice-assistant.onrender.com';
})();

// ── API client ────────────────────────────────────────────────────────────────
const API = {
  async customers() {
    return (await fetch(API_BASE + '/api/customers')).json();
  },
  async agents() {
    return (await fetch(API_BASE + '/api/agents')).json();
  },
  async greet(customer, language, agentId) {
    const r = await fetch(API_BASE + '/api/greet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer, language, agent_id: agentId }),
    });
    return r.json();
  },
  async transcribe(blob, language) {
    const form = new FormData();
    form.append('audio', blob, 'audio.webm');
    form.append('language', language);
    return (await fetch(API_BASE + '/api/transcribe', { method: 'POST', body: form })).json();
  },
  async chat(payload, onEvent) {
    const r = await fetch(API_BASE + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`Chat API ${r.status}`);

    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let finalState = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const d = JSON.parse(line.slice(6));
          if (d.type === 'done') finalState = d.state;
          else onEvent(d);
        } catch (_) {}
      }
    }
    return finalState;
  },
  async speakBytes(text, agentId, frustrationLevel) {
    const r = await fetch(API_BASE + '/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        agent_id: agentId,
        frustration_level: frustrationLevel,
      }),
    });
    if (!r.ok) return null;
    return r.arrayBuffer();
  },
};

// ── App state ─────────────────────────────────────────────────────────────────
let state = {
  customer: null,
  language: 'nl',
  agentId: 'sarah',
  messages: [],
  intent: 'unknown',
  confidence: 0,
  sentiment: 'neutral',
  frustrationLevel: 1,
  turnCount: 0,
  escalated: false,
  escalationNeeded: false,
  keyIssue: '',
  troubleshootingStep: 0,
  summary: {},
  voiceEnabled: false,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $  = id => document.getElementById(id);
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
const vadBtn          = $('vadBtn');
const exportBtn       = $('exportBtn');
const surveyModal     = $('surveyModal');

// ── i18n ──────────────────────────────────────────────────────────────────────
const T = {
  nl: {
    idle: 'Klik om te spreken', recording: 'Luistert… klik om te stoppen',
    processing: 'Verwerken…', playing: 'spreekt…', interrupt: 'Klik om te onderbreken',
    available: 'Beschikbaar', listening: 'Luistert', thinking: 'Denkt na…',
    speaking: 'spreekt', newCall: 'Gesprek wordt geladen…',
    micDenied: 'Microfoon toegang geweigerd. Sta toegang toe in uw browser.',
    vadOn: '🎙️ Auto AAN', vadOff: '🎙️ Auto',
  },
  en: {
    idle: 'Click to speak', recording: 'Listening… click to stop',
    processing: 'Processing…', playing: 'speaking…', interrupt: 'Click to interrupt',
    available: 'Available', listening: 'Listening', thinking: 'Thinking…',
    speaking: 'speaking', newCall: 'Loading conversation…',
    micDenied: 'Microphone access denied. Please allow it in your browser.',
    vadOn: '🎙️ Auto ON', vadOff: '🎙️ Auto',
  },
};
function t(key) { return (T[state.language] || T.nl)[key] || key; }

// ── Agent color theming ───────────────────────────────────────────────────────
const AGENT_META = {
  sarah: { color: '#10b981', emoji: '🎧', name: 'Sarah' },
  alex:  { color: '#6366f1', emoji: '🎯', name: 'Alex'  },
  nina:  { color: '#f59e0b', emoji: '💼', name: 'Nina'  },
};

function applyAgentTheme(agentId) {
  const meta = AGENT_META[agentId] || AGENT_META.sarah;
  document.documentElement.style.setProperty('--agent-color', meta.color);
  if (agentAvatar)  agentAvatar.textContent  = meta.emoji;
  if (agentNameEl)  agentNameEl.textContent   = meta.name;

  // Update active card in picker
  agentPicker.querySelectorAll('.agt-card').forEach(c => {
    const isActive = c.dataset.agent === agentId;
    c.classList.toggle('active', isActive);
    c.style.setProperty('--agent-color', meta.color);
  });
}

// ── UI mode ───────────────────────────────────────────────────────────────────
let uiMode = 'idle';

function setMode(mode) {
  uiMode = mode;
  micBtn.className = 'mic-btn' + (mode !== 'idle' ? ' ' + mode : '');
  micBtn.disabled  = mode === 'processing';   // only locked during processing

  iconMic.style.display       = (mode === 'idle') ? '' : 'none';
  iconStop.style.display      = (mode === 'recording') ? '' : 'none';
  iconInterrupt.style.display = (mode === 'playing') ? '' : 'none';
  spin.style.display          = (mode === 'processing') ? '' : 'none';

  if (mode === 'playing') {
    micLabel.textContent = (AGENT_META[state.agentId]?.name || 'Agent') + ' ' + t('playing');
  } else if (mode === 'recording') {
    micLabel.textContent = t('interrupt');  // repurposed — was recording label
    micLabel.textContent = t('recording');
  } else {
    micLabel.textContent = t(mode) || t('idle');
  }

  waveform.classList.toggle('active', mode === 'recording');
  avatarWrap.className = 'avatar-wrap' + (mode === 'playing' ? ' speaking' : '');

  const colorMap = { idle: 'var(--agent-color)', recording: '#ef4444',
                     processing: '#f59e0b', playing: 'var(--agent-color)' };
  const color = colorMap[mode] || 'var(--agent-color)';
  agentStatus.style.color       = color;
  agentStatus.style.background  = `color-mix(in srgb, ${color} 15%, transparent)`;
  agentStatus.style.borderColor = `color-mix(in srgb, ${color} 25%, transparent)`;

  const statusMap = { idle: 'available', recording: 'listening',
                      processing: 'thinking', playing: 'speaking' };
  const key = statusMap[mode] || 'available';
  const label = t(key);
  statusText.textContent = (key === 'speaking')
    ? (AGENT_META[state.agentId]?.name || 'Agent') + ' ' + label
    : label;
}

// ── Transcript helpers ─────────────────────────────────────────────────────────
function clearTranscript() {
  transcript.innerHTML = '';
  transcriptEmpty.textContent = t('newCall');
  transcript.appendChild(transcriptEmpty);
}

function addBubble(role, text) {
  if (transcriptEmpty.parentNode) transcriptEmpty.remove();
  const wrap   = document.createElement('div');
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
  return body;
}

function addToolBubble(name, label, icon) {
  if (transcriptEmpty.parentNode) transcriptEmpty.remove();
  const wrap = document.createElement('div');
  wrap.className = 'bubble tool';
  wrap.dataset.toolName = name;

  const header = document.createElement('div');
  header.className = 'tool-header';

  const sp = document.createElement('div');
  sp.className = 'tool-spinner';

  const lbl = document.createElement('span');
  lbl.textContent = `${icon} ${label}`;

  header.append(sp, lbl);
  wrap.appendChild(header);
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  return wrap;
}

function resolveToolBubble(wrap, result) {
  const header = wrap.querySelector('.tool-header');
  const sp = header.querySelector('.tool-spinner');
  if (sp) { sp.outerHTML = '<span class="tool-check">✓</span>'; }

  const resultDiv = document.createElement('div');
  resultDiv.className = 'tool-result';

  // Show first 5 key-value pairs from the result
  const SKIP = new Set(['account', 'bericht', 'message', 'fout', 'error']);
  let count = 0;
  for (const [k, v] of Object.entries(result)) {
    if (SKIP.has(k) || count >= 5) continue;
    const row = document.createElement('div');
    row.className = 'tool-result-row';
    row.innerHTML = `<span class="tool-result-key">${k.replace(/_/g,' ')}</span>`
      + `<span class="tool-result-value">${v}</span>`;
    resultDiv.appendChild(row);
    count++;
  }
  if (count > 0) wrap.appendChild(resultDiv);
  transcript.scrollTop = transcript.scrollHeight;
}

// ── Dashboard & chart ─────────────────────────────────────────────────────────
const INTENT_LABELS = {
  nl: {
    wifi_slow:'📶 Trage WiFi', wifi_down:'📶 WiFi storing',
    internet_down:'🚫 Geen internet', internet_unstable:'⚡ Onstabiel',
    mobile_data:'📱 Mobiele data', sim_activation:'📲 SIM',
    billing:'💶 Factuur', subscription_change:'📋 Abonnement',
    contract:'📄 Contract', outage:'⚡ Storing',
    escalation:'🚨 Escalatie', unknown:'❓ —',
  },
  en: {
    wifi_slow:'📶 Slow WiFi', wifi_down:'📶 WiFi down',
    internet_down:'🚫 No internet', internet_unstable:'⚡ Unstable',
    mobile_data:'📱 Mobile data', sim_activation:'📲 SIM',
    billing:'💶 Billing', subscription_change:'📋 Subscription',
    contract:'📄 Contract', outage:'⚡ Outage',
    escalation:'🚨 Escalation', unknown:'❓ —',
  },
};

const SENT_MAP = { positive:'😊', neutral:'😐', frustrated:'😤', angry:'😡', negative:'😟' };
const SENT_SCORE = { positive:5, neutral:3, frustrated:2, angry:1, negative:1 };

let sentimentChart = null;

function initChart() {
  if (!window._chartJsLoaded || sentimentChart) return;
  const ctx = $('sentimentChart').getContext('2d');
  sentimentChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        data: [],
        borderColor: AGENT_META[state.agentId]?.color || '#10b981',
        backgroundColor: 'rgba(16,185,129,0.08)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: AGENT_META[state.agentId]?.color || '#10b981',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: { legend: { display: false } },
      scales: {
        y: {
          min: 0, max: 5, stepSize: 1,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#5a6070', stepSize: 1 },
        },
        x: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#5a6070' },
        },
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
  const color = AGENT_META[state.agentId]?.color || '#10b981';
  sentimentChart.data.datasets[0].borderColor = color;
  sentimentChart.data.datasets[0].pointBackgroundColor = color;
  sentimentChart.update('none');
}

function updateDashboard(newState) {
  Object.assign(state, newState);
  const labels = INTENT_LABELS[state.language] || INTENT_LABELS.nl;
  $('dIntent').textContent    = labels[state.intent] || state.intent || '—';
  $('dSentiment').textContent = (SENT_MAP[state.sentiment] || '😐') + ' ' + (state.sentiment || '');
  $('dConf').textContent      = state.confidence ? Math.round(state.confidence * 100) + '%' : '—';
  $('dTurns').textContent     = state.turnCount ?? 0;
  if (state.escalated) $('escChip').style.display = '';
}

// ── AudioContext + Web Audio ──────────────────────────────────────────────────
let _audioCtx      = null;
let _currentSource = null;   // active BufferSourceNode (for barge-in stop)

function _unlockAudio() {
  if (_audioCtx) return;
  try {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  } catch (_) { return; }
  const resume = _audioCtx.state === 'suspended' ? _audioCtx.resume() : Promise.resolve();
  resume.then(() => {
    try {
      const buf = _audioCtx.createBuffer(1, 1, 22050);
      const src = _audioCtx.createBufferSource();
      src.buffer = buf; src.connect(_audioCtx.destination); src.start(0);
    } catch (_) {}
  });
}

async function _playBuffer(arrayBuffer) {
  if (!_audioCtx) return;
  if (_audioCtx.state === 'suspended') await _audioCtx.resume();
  const decoded = await _audioCtx.decodeAudioData(arrayBuffer.slice(0));
  const src = _audioCtx.createBufferSource();
  src.buffer = decoded;
  src.connect(_audioCtx.destination);
  _currentSource = src;
  await new Promise(resolve => { src.onended = resolve; src.start(0); });
  _currentSource = null;
}

function _stopCurrentAudio() {
  if (_currentSource) {
    try { _currentSource.stop(); } catch (_) {}
    _currentSource = null;
  }
}

// ── TTS (single call per response, AbortController) ──────────────────────────
let _activeTTSCtrl = null;

function abortTTS() {
  if (_activeTTSCtrl) { _activeTTSCtrl.abort(); _activeTTSCtrl = null; }
  _stopCurrentAudio();
}

async function speakText(text) {
  if (!text.trim() || !state.voiceEnabled) { setMode('idle'); return; }

  abortTTS();
  const ctrl = new AbortController();
  _activeTTSCtrl = ctrl;
  setMode('playing');

  try {
    const r = await fetch(API_BASE + '/api/speak-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        agent_id: state.agentId,
        frustration_level: state.frustrationLevel,
      }),
      signal: ctrl.signal,
    });

    if (!r.ok) throw new Error(`TTS ${r.status}`);

    // Collect the streaming response — ElevenLabs starts sending chunks
    // immediately so this resolves faster than the old non-streaming endpoint.
    const buf = await r.arrayBuffer();
    if (ctrl.signal.aborted) return;

    await _playBuffer(buf);
  } catch (e) {
    if (e.name !== 'AbortError') console.warn('[TTS]', e.message);
  } finally {
    if (_activeTTSCtrl === ctrl) _activeTTSCtrl = null;
  }

  if (!ctrl.signal.aborted) setMode('idle');
}

// ── Waveform: real AnalyserNode ───────────────────────────────────────────────
let _analyser  = null;
let _animFrame = null;
const _bars    = () => waveform.querySelectorAll('span');

function startWaveform(stream) {
  if (!_audioCtx || !stream) {
    waveform.classList.add('fallback');
    return;
  }
  waveform.classList.remove('fallback');
  const src = _audioCtx.createMediaStreamSource(stream);
  _analyser = _audioCtx.createAnalyser();
  _analyser.fftSize = 64;
  src.connect(_analyser);
  const data = new Uint8Array(_analyser.frequencyBinCount);

  function draw() {
    _animFrame = requestAnimationFrame(draw);
    _analyser.getByteFrequencyData(data);
    _bars().forEach((bar, i) => {
      const v = data[i * 2] || 0;
      bar.style.height = Math.max(4, (v / 255) * 26) + 'px';
    });
  }
  draw();
}

function stopWaveform() {
  if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
  _bars().forEach(b => { b.style.height = '4px'; });
  _analyser = null;
  waveform.classList.remove('fallback');
}

// ── Voice Activity Detection ──────────────────────────────────────────────────
let _vadEnabled = false;
let _vadStream  = null;
let _silenceTimer = null;
let _speechActive = false;

async function startVAD() {
  if (_vadStream) return;
  try {
    _vadStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (_) { stopVAD(); return; }

  _unlockAudio();
  if (!_audioCtx) { stopVAD(); return; }

  const src      = _audioCtx.createMediaStreamSource(_vadStream);
  const analyser = _audioCtx.createAnalyser();
  analyser.fftSize = 512;
  src.connect(analyser);
  const data = new Uint8Array(analyser.fftSize);

  function check() {
    if (!_vadEnabled) { cleanupVAD(); return; }
    requestAnimationFrame(check);
    analyser.getByteTimeDomainData(data);

    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length) * 100;

    if (rms > 12 && uiMode === 'idle' && !_speechActive) {
      _speechActive = true;
      clearTimeout(_silenceTimer);
      _silenceTimer = null;
      startRecording();
    } else if (rms < 8 && uiMode === 'recording' && _speechActive) {
      if (!_silenceTimer) {
        _silenceTimer = setTimeout(() => {
          _speechActive = false;
          _silenceTimer = null;
          stopRecording();
        }, 900);
      }
    }
  }
  check();
}

function cleanupVAD() {
  if (_vadStream) { _vadStream.getTracks().forEach(t => t.stop()); _vadStream = null; }
  _speechActive = false;
  clearTimeout(_silenceTimer);
  _silenceTimer = null;
}

function stopVAD() {
  _vadEnabled = false;
  cleanupVAD();
  vadBtn.textContent = t('vadOff');
  vadBtn.classList.remove('vad-active');
}

function toggleVAD() {
  _vadEnabled = !_vadEnabled;
  if (_vadEnabled) {
    vadBtn.textContent = t('vadOn');
    vadBtn.classList.add('vad-active');
    startVAD();
  } else {
    stopVAD();
  }
}

// ── Recording ─────────────────────────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let _micStream    = null;

async function startRecording() {
  if (uiMode === 'playing') { bargeIn(); return; }
  if (uiMode !== 'idle') return;

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    _micStream = stream;
  } catch (_) {
    alert(t('micDenied'));
    return;
  }

  audioChunks = [];
  const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', '']
    .find(m => !m || MediaRecorder.isTypeSupported(m));

  mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
  mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach(t => t.stop());
    _micStream = null;
    stopWaveform();
    processAudio();
  };
  mediaRecorder.start(100);
  setMode('recording');
  startWaveform(stream);
}

function stopRecording() {
  if (mediaRecorder && uiMode === 'recording') mediaRecorder.stop();
}

function bargeIn() {
  abortTTS();
  setMode('idle');
  setTimeout(() => startRecording(), 80);
}

// ── Chat processing ───────────────────────────────────────────────────────────
async function processAudio() {
  setMode('processing');

  const blob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
  let text;
  try {
    const res = await API.transcribe(blob, state.language);
    text = res.text;
  } catch (err) {
    console.error('Transcribe failed:', err);
    setMode('idle');
    return;
  }

  if (!text || text.startsWith('[')) {
    if (text) addBubble('assistant', '⚠️ ' + text);
    setMode('idle');
    return;
  }

  addBubble('user', text);
  const textNode = addBubble('assistant', '');
  const cursor   = document.createElement('span');
  cursor.className = 'cursor';
  textNode.appendChild(cursor);

  let fullResponse   = '';
  let activeToolWrap = null;

  const payload = {
    message: text,
    messages: state.messages,
    customer: state.customer,
    language: state.language,
    agent_id: state.agentId,
    intent: state.intent,
    confidence: state.confidence,
    sentiment: state.sentiment,
    frustration_level: state.frustrationLevel,
    turn_count: state.turnCount,
    escalated: state.escalated,
    key_issue: state.keyIssue,
    troubleshooting_step: state.troubleshootingStep,
    summary: state.summary,
  };

  let newState = null;
  try {
    newState = await API.chat(payload, event => {
      if (event.type === 'tool_call') {
        activeToolWrap = addToolBubble(event.name, event.label, event.icon);
        setMode('processing');
      } else if (event.type === 'tool_done') {
        if (activeToolWrap) resolveToolBubble(activeToolWrap, event.result);
        activeToolWrap = null;
      } else if (event.type === 'chunk') {
        fullResponse += event.text;
        textNode.textContent = fullResponse;
        textNode.appendChild(cursor);
        transcript.scrollTop = transcript.scrollHeight;
      }
    });
  } catch (err) {
    console.error('Chat failed:', err);
    textNode.textContent = '⚠️ Verbindingsfout. Probeer opnieuw.';
    cursor.remove();
    setMode('idle');
    return;
  }

  cursor.remove();
  textNode.textContent = fullResponse;

  if (newState) {
    updateDashboard(newState);
    pushChartPoint(newState.sentiment, newState.turnCount);
  }

  // Speak full response in one TTS call — text is already visible while it loads
  await speakText(fullResponse);
}

// ── Call history (localStorage) ───────────────────────────────────────────────
const HISTORY_KEY = 'tnl_call_history';

function saveCall(data) {
  const history = loadHistory();
  history.unshift({
    id: Date.now(),
    agentId: data.agentId,
    agentName: data.agentName,
    customerName: data.customerName,
    intent: data.intent,
    turns: data.turns,
    sentiment: data.sentiment,
    escalated: data.escalated,
    resolved: data.resolved,
    rating: data.rating,
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
  if (!history.length) {
    list.innerHTML = '<div class="history-empty">Nog geen gesprekken.</div>';
    return;
  }
  list.innerHTML = history.map(h => {
    const time = new Date(h.ts).toLocaleString('nl-NL', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' });
    const stars = h.rating ? '★'.repeat(h.rating) : '';
    const intentLabel = h.intent.replace(/_/g, ' ');
    const meta = AGENT_META[h.agentId] || AGENT_META.sarah;
    return `
      <div class="history-item">
        <div class="history-emoji">${meta.emoji}</div>
        <div class="history-info">
          <div class="history-top">
            <span class="history-name">${h.customerName || 'Onbekend'}</span>
            <span class="history-time">${time}</span>
          </div>
          <div class="history-sub">${meta.name} · ${h.turns} beurten · ${intentLabel}</div>
          <div class="history-pills">
            ${h.resolved ? '<span class="history-pill resolved">✓ Opgelost</span>' : ''}
            ${h.escalated ? '<span class="history-pill escalated">🚨 Escalatie</span>' : ''}
            ${stars ? `<span class="history-stars">${stars}</span>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');
}

// ── Post-call survey ──────────────────────────────────────────────────────────
let _surveyRating   = 0;
let _surveyResolved = null;
let _surveyPending  = null;   // call data waiting for survey

function showSurvey(callData) {
  if (!state.messages.length) return;
  _surveyPending  = callData;
  _surveyRating   = 0;
  _surveyResolved = null;

  surveyModal.querySelectorAll('.star').forEach(s => s.classList.remove('lit'));
  $('surveyYes').classList.remove('selected-yes');
  $('surveyNo').classList.remove('selected-no');
  surveyModal.style.display = 'flex';
}

function hideSurvey(rating, resolved) {
  surveyModal.style.display = 'none';
  if (_surveyPending) {
    saveCall({ ..._surveyPending, rating: rating || 0, resolved: resolved ?? null });
    renderHistory();
    _surveyPending = null;
  }
}

function initSurveyEvents() {
  surveyModal.querySelectorAll('.star').forEach(star => {
    star.addEventListener('click', () => {
      _surveyRating = +star.dataset.val;
      surveyModal.querySelectorAll('.star').forEach((s, i) => {
        s.classList.toggle('lit', i < _surveyRating);
      });
    });
  });

  $('surveyYes').addEventListener('click', () => {
    _surveyResolved = true;
    $('surveyYes').classList.add('selected-yes');
    $('surveyNo').classList.remove('selected-no');
    if (_surveyRating) hideSurvey(_surveyRating, true);
  });

  $('surveyNo').addEventListener('click', () => {
    _surveyResolved = false;
    $('surveyNo').classList.add('selected-no');
    $('surveyYes').classList.remove('selected-yes');
    if (_surveyRating) hideSurvey(_surveyRating, false);
  });

  $('surveySkip').addEventListener('click', () => hideSurvey(0, null));
}

// ── Call export ───────────────────────────────────────────────────────────────
function exportCall() {
  if (!state.messages.length) return;
  const agentMeta = AGENT_META[state.agentId] || AGENT_META.sarah;
  const lines = [
    'TelecomNL AI Support — Gespreksverslag',
    '========================================',
    `Datum:   ${new Date().toLocaleString('nl-NL')}`,
    `Agent:   ${agentMeta.name} ${agentMeta.emoji}`,
    `Klant:   ${state.customer?.name || 'Onbekend'}`,
    `Issue:   ${state.intent.replace(/_/g, ' ')}`,
    `Beurten: ${state.turnCount}`,
    `Escalatie: ${state.escalated ? 'Ja' : 'Nee'}`,
    '',
    '--- GESPREK ---',
    ...state.messages.map(m => {
      const role = m.role === 'assistant' ? agentMeta.name : (state.customer?.name || 'Klant');
      return `[${role}] ${m.content}`;
    }),
  ];

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `gesprek-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Collapsible sections ──────────────────────────────────────────────────────
function initCollapsible(toggleId, bodyId) {
  const btn  = $(toggleId);
  const body = $(bodyId);
  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!expanded));
    body.style.display = expanded ? 'none' : 'block';
    if (!expanded && toggleId === 'chartToggle') initChart();
    if (!expanded && toggleId === 'historyToggle') renderHistory();
  });
}

// ── Conversation start ────────────────────────────────────────────────────────
async function startConversation(customer, language, agentId) {
  state.language = language || state.language;
  state.agentId  = agentId  || state.agentId;
  state.customer = customer;
  stopVAD();
  abortTTS();
  clearTranscript();
  resetChart();
  $('escChip').style.display = 'none';
  applyAgentTheme(state.agentId);
  setMode('processing');

  const data = await API.greet(customer, state.language, state.agentId);
  state.voiceEnabled = data.voiceEnabled;
  updateDashboard(data.state);
  addBubble('assistant', data.greeting);

  await speakText(data.greeting);
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

  // Populate customer dropdown
  customers.forEach(c => customerSelect.append(new Option(c.name, c.id)));

  // Build agent picker
  agentList.forEach(agent => {
    const card = document.createElement('div');
    card.className = 'agt-card';
    card.dataset.agent = agent.id;
    card.style.setProperty('--agent-color', agent.color);
    card.innerHTML = `
      <div class="agt-emoji">${agent.emoji}</div>
      <div class="agt-name">${agent.name}</div>
      <div class="agt-lang">${agent.language.toUpperCase()}</div>`;
    card.addEventListener('click', () => {
      const lang = agent.language === 'en' ? 'en' : state.language;
      langToggle.textContent = lang === 'en' ? '🇬🇧 EN' : '🇳🇱 NL';
      startConversation(state.customer, lang, agent.id);
    });
    agentPicker.appendChild(card);
  });

  // Events
  customerSelect.addEventListener('change', () => {
    const c = customers.find(x => x.id === customerSelect.value);
    if (c) startConversation(c, state.language, state.agentId);
  });

  langToggle.addEventListener('click', () => {
    const lang = state.language === 'nl' ? 'en' : 'nl';
    langToggle.textContent = lang === 'nl' ? '🇳🇱 NL' : '🇬🇧 EN';
    startConversation(state.customer, lang, state.agentId);
  });

  $('newCallBtn').addEventListener('click', () => {
    // Show survey for completed call before resetting
    if (state.messages.length >= 2) {
      showSurvey({
        agentId: state.agentId,
        agentName: AGENT_META[state.agentId]?.name,
        customerName: state.customer?.name,
        intent: state.intent,
        turns: state.turnCount,
        sentiment: state.sentiment,
        escalated: state.escalated,
      });
    }
    startConversation(state.customer, state.language, state.agentId);
  });

  micBtn.addEventListener('click', () => {
    _unlockAudio();
    if (uiMode === 'idle')      startRecording();
    else if (uiMode === 'recording') stopRecording();
    else if (uiMode === 'playing')   bargeIn();
  });

  vadBtn.addEventListener('click',    toggleVAD);
  exportBtn.addEventListener('click', exportCall);

  initCollapsible('chartToggle',   'chartBody');
  initCollapsible('historyToggle', 'historyBody');
  initSurveyEvents();

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.code === 'Space') {
      e.preventDefault();
      micBtn.click();
    } else if (e.code === 'Escape') {
      $('newCallBtn').click();
    } else if (e.key === 'v' || e.key === 'V') {
      toggleVAD();
    }
  });

  // Add keyboard hint
  const hint = document.createElement('div');
  hint.className = 'kbd-hint';
  hint.innerHTML = '<kbd>Space</kbd> mic &nbsp;·&nbsp; <kbd>Esc</kbd> nieuw gesprek &nbsp;·&nbsp; <kbd>V</kbd> auto';
  $('micBtn').closest('.mic-area').appendChild(hint);

  // Start first conversation
  await startConversation(customers[0], 'nl', 'sarah');

  overlay.style.transition = 'opacity 0.35s';
  overlay.style.opacity    = '0';
  setTimeout(() => overlay.remove(), 400);
}

document.addEventListener('DOMContentLoaded', init);
