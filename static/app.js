/* TelecomNL Voice Assistant — vanilla JS, no dependencies */

'use strict';

// ── API client ───────────────────────────────────────────────────────────────

const API = {
  async customers() {
    const r = await fetch('/api/customers');
    return r.json();
  },

  async greet(customer, language) {
    const r = await fetch('/api/greet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer, language }),
    });
    return r.json();
  },

  async transcribe(blob, language) {
    const form = new FormData();
    form.append('audio', blob, 'audio.webm');
    form.append('language', language);
    const r = await fetch('/api/transcribe', { method: 'POST', body: form });
    return r.json();
  },

  /**
   * Stream /api/chat. Calls onChunk(text) for each text chunk.
   * Returns the final state object from the 'done' event.
   */
  async chat(payload, onChunk) {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!r.ok) {
      throw new Error(`Chat API ${r.status}`);
    }

    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let finalState = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });

      const lines = buf.split('\n');
      buf = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const d = JSON.parse(line.slice(6));
          if (d.type === 'chunk') onChunk(d.text);
          else if (d.type === 'done') finalState = d.state;
        } catch (_) {
          // malformed event — ignore
        }
      }
    }
    return finalState;
  },

};

// ── App state ────────────────────────────────────────────────────────────────

let state = {
  customer: null,
  language: 'nl',
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

// ── DOM refs ─────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const micBtn        = $('micBtn');
const iconMic       = $('iconMic');
const iconStop      = $('iconStop');
const spin          = $('spin');
const micLabel      = $('micLabel');
const avatarWrap    = $('avatarWrap');
const statusText    = $('statusText');
const agentStatus   = $('agentStatus');
const transcript    = $('transcript');
const transcriptEmpty = $('transcriptEmpty');
const waveform      = $('waveform');
const customerSelect = $('customerSelect');
const langToggle    = $('langToggle');

// ── i18n strings ─────────────────────────────────────────────────────────────

const T = {
  nl: {
    idle:        'Klik om te spreken',
    recording:   'Luistert… klik om te stoppen',
    processing:  'Verwerken…',
    playing:     'Sarah spreekt…',
    available:   'Beschikbaar',
    listening:   'Luistert',
    thinking:    'Denkt na…',
    speaking:    'Sarah spreekt',
    newCall:     'Gesprek wordt geladen…',
    micDenied:   'Microfoon toegang geweigerd. Sta toegang toe in uw browser.',
  },
  en: {
    idle:        'Click to speak',
    recording:   'Listening… click to stop',
    processing:  'Processing…',
    playing:     'Sarah speaking…',
    available:   'Available',
    listening:   'Listening',
    thinking:    'Thinking…',
    speaking:    'Sarah speaking',
    newCall:     'Loading conversation…',
    micDenied:   'Microphone access denied. Please allow it in your browser.',
  },
};

function t(key) {
  return (T[state.language] || T.nl)[key] || key;
}

// ── UI mode ──────────────────────────────────────────────────────────────────

let uiMode = 'idle'; // idle | recording | processing | playing

const STATUS_COLORS = {
  idle:       'var(--sarah)',
  recording:  '#ef4444',
  processing: '#f59e0b',
  playing:    'var(--sarah)',
};

function setMode(mode) {
  uiMode = mode;

  // Button class
  micBtn.className = 'mic-btn' + (mode !== 'idle' ? ' ' + mode : '');
  micBtn.disabled = mode === 'processing' || mode === 'playing';

  // Icons
  iconMic.style.display  = (mode === 'idle' || mode === 'playing') ? '' : 'none';
  iconStop.style.display = mode === 'recording' ? '' : 'none';
  spin.style.display     = mode === 'processing' ? '' : 'none';

  // Label
  micLabel.textContent = t(mode);

  // Waveform
  waveform.className = 'waveform' + (mode === 'recording' ? ' active' : '');

  // Avatar
  avatarWrap.className = 'avatar-wrap' + (mode === 'playing' ? ' speaking' : '');

  // Status badge
  const color = STATUS_COLORS[mode] || 'var(--sarah)';
  agentStatus.style.color      = color;
  agentStatus.style.background = color + '20';
  agentStatus.style.borderColor = color + '35';

  const statusMap = {
    idle:       'available',
    recording:  'listening',
    processing: 'thinking',
    playing:    'speaking',
  };
  statusText.textContent = t(statusMap[mode] || 'available');
}

// ── Transcript helpers ────────────────────────────────────────────────────────

function clearTranscript() {
  transcript.innerHTML = '';
  transcriptEmpty.textContent = t('newCall');
  transcript.appendChild(transcriptEmpty);
}

function addBubble(role, text) {
  if (transcriptEmpty.parentNode) transcriptEmpty.remove();

  const wrap = document.createElement('div');
  wrap.className = `bubble ${role}`;

  const sender = document.createElement('div');
  sender.className = 'bubble-sender';
  sender.textContent = role === 'assistant'
    ? 'Sarah'
    : (state.customer?.name || 'Klant');

  const body = document.createElement('div');
  body.className = 'bubble-text';
  body.textContent = text;

  wrap.append(sender, body);
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  return body; // return text node for live updates
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

const INTENT_LABELS = {
  nl: {
    wifi_slow: '📶 Trage WiFi', wifi_down: '📶 WiFi storing',
    internet_down: '🚫 Geen internet', internet_unstable: '⚡ Onstabiel',
    mobile_data: '📱 Mobiele data', sim_activation: '📲 SIM',
    billing: '💶 Factuur', subscription_change: '📋 Abonnement',
    contract: '📄 Contract', outage: '⚡ Storing',
    escalation: '🚨 Escalatie', unknown: '❓ —',
  },
  en: {
    wifi_slow: '📶 Slow WiFi', wifi_down: '📶 WiFi down',
    internet_down: '🚫 No internet', internet_unstable: '⚡ Unstable',
    mobile_data: '📱 Mobile data', sim_activation: '📲 SIM',
    billing: '💶 Billing', subscription_change: '📋 Subscription',
    contract: '📄 Contract', outage: '⚡ Outage',
    escalation: '🚨 Escalation', unknown: '❓ —',
  },
};

const SENT_MAP = {
  positive: '😊', neutral: '😐', frustrated: '😤', angry: '😡', negative: '😟',
};

function updateDashboard(newState) {
  Object.assign(state, newState);

  const lang = state.language || 'nl';
  const labels = INTENT_LABELS[lang] || INTENT_LABELS.nl;

  $('dIntent').textContent  = labels[state.intent] || state.intent || '—';
  $('dSentiment').textContent = (SENT_MAP[state.sentiment] || '😐') + ' ' + (state.sentiment || '');
  $('dConf').textContent    = state.confidence ? Math.round(state.confidence * 100) + '%' : '—';
  $('dTurns').textContent   = state.turnCount ?? 0;

  if (state.escalated) {
    $('escChip').style.display = '';
  }
}

// ── Audio playback ────────────────────────────────────────────────────────────

let currentAudio = null;

// ── iOS audio unlock ─────────────────────────────────────────────────────────
// iOS blocks all audio until the user taps. Resuming an AudioContext on first
// tap unlocks subsequent audio.play() calls even after async operations.

let _audioCtx = null;

function _unlockAudio() {
  if (_audioCtx) return;
  try {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (_audioCtx.state === 'suspended') _audioCtx.resume();
    // Play a silent buffer so iOS registers the gesture
    const buf = _audioCtx.createBuffer(1, 1, 22050);
    const src = _audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(_audioCtx.destination);
    src.start(0);
  } catch (_) {}
}

// ── TTS — server audio (ElevenLabs → OpenAI TTS fallback) ────────────────────

async function playTTS(text) {
  if (!text) return;
  setMode('playing');

  try {
    const r = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });

    if (r.ok) {
      const blob = await r.blob();
      const url  = URL.createObjectURL(blob);
      currentAudio = new Audio(url);
      await new Promise((resolve) => {
        currentAudio.onended = resolve;
        currentAudio.onerror = resolve;
        currentAudio.play().catch(resolve);
      });
      URL.revokeObjectURL(url);
      currentAudio = null;
    }
  } catch (_) {}

  setMode('idle');
}

// ── Recording ─────────────────────────────────────────────────────────────────

let mediaRecorder = null;
let audioChunks   = [];

async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (_) {
    alert(t('micDenied'));
    return;
  }

  audioChunks = [];
  const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', '']
    .find((m) => !m || MediaRecorder.isTypeSupported(m));

  mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    processAudio();
  };
  mediaRecorder.start(100);
  setMode('recording');
}

function stopRecording() {
  if (mediaRecorder && uiMode === 'recording') mediaRecorder.stop();
}

async function processAudio() {
  setMode('processing');

  const blob = new Blob(audioChunks, {
    type: mediaRecorder?.mimeType || 'audio/webm',
  });

  // Step 1 — transcribe
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

  // Step 2 — stream LLM reply
  const textNode = addBubble('assistant', '');
  const cursor   = document.createElement('span');
  cursor.className = 'cursor';
  textNode.appendChild(cursor);

  let fullResponse = '';

  const payload = {
    message: text,
    messages: state.messages,
    customer: state.customer,
    language: state.language,
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
    newState = await API.chat(payload, (chunk) => {
      fullResponse += chunk;
      textNode.textContent = fullResponse;
      textNode.appendChild(cursor);
      transcript.scrollTop = transcript.scrollHeight;
    });
  } catch (err) {
    console.error('Chat failed:', err);
    textNode.textContent = '⚠️ Verbindingsfout. Probeer opnieuw.';
    setMode('idle');
    return;
  }

  cursor.remove();
  textNode.textContent = fullResponse;

  if (newState) updateDashboard(newState);

  // Step 3 — TTS
  await playTTS(fullResponse);
  setMode('idle');
}

// ── Conversation init ─────────────────────────────────────────────────────────

async function startConversation(customer, language) {
  state.language = language;
  state.customer = customer;
  clearTranscript();
  setMode('processing');

  const data = await API.greet(customer, language);
  state.voiceEnabled = data.voiceEnabled;
  updateDashboard(data.state);

  addBubble('assistant', data.greeting);

  await playTTS(data.greeting);
  setMode('idle');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function init() {
  // Loading overlay removed by giving it a brief delay
  const overlay = document.createElement('div');
  overlay.id = 'loadOverlay';
  overlay.innerHTML = '<div class="load-logo">📡</div><div class="load-text">TelecomNL laden…</div>';
  document.body.prepend(overlay);

  // Fetch customers
  let customers;
  try {
    customers = await API.customers();
  } catch (_) {
    overlay.querySelector('.load-text').textContent = 'Server niet bereikbaar. Herlaad de pagina.';
    return;
  }

  // Populate dropdown
  customers.forEach((c) => {
    const opt = new Option(c.name, c.id);
    customerSelect.append(opt);
  });

  // Event: customer switch
  customerSelect.addEventListener('change', () => {
    const c = customers.find((x) => x.id === customerSelect.value);
    if (c) startConversation(c, state.language);
  });

  // Event: language toggle
  let lang = 'nl';
  langToggle.addEventListener('click', () => {
    lang = lang === 'nl' ? 'en' : 'nl';
    langToggle.textContent = lang === 'nl' ? '🇳🇱 NL' : '🇬🇧 EN';
    state.language = lang;
    startConversation(state.customer, lang);
  });

  // Event: new call
  $('newCallBtn').addEventListener('click', () => {
    startConversation(state.customer, state.language);
  });

  // Event: mic button — unlock audio on first tap (required for iOS)
  micBtn.addEventListener('click', () => {
    _unlockAudio();
    if (uiMode === 'idle') startRecording();
    else if (uiMode === 'recording') stopRecording();
  });

  // Start first conversation
  await startConversation(customers[0], 'nl');

  // Fade out overlay
  overlay.style.transition = 'opacity 0.35s';
  overlay.style.opacity = '0';
  setTimeout(() => overlay.remove(), 400);
}

document.addEventListener('DOMContentLoaded', init);
