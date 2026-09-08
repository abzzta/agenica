/**
 * Agenica S — Gemini Multimodal Live Audio Client Application.
 * Full-duplex 16kHz PCM recording & 24kHz native audio playback with rich action cards.
 */

let ws = null;
let audioCtxIn = null;
let audioCtxOut = null;
let micStream = null;
let scriptProcessor = null;
let isConnected = false;
let isConnecting = false;
let isAgentSpeaking = false;
let nextPlayTime = 0;
let heartbeatTimer = null;
let activeSources = [];
let turnCompletionTimer = null;

let currentAgentBubble = null;
let currentUserBubble = null;

const liveOrb = document.getElementById('liveOrb');
const orbIcon = document.getElementById('orbIcon');
const stateTitle = document.getElementById('stateTitle');
const stateSubtitle = document.getElementById('stateSubtitle');
const headerStatus = document.getElementById('headerStatus');
const activityStream = document.getElementById('activityStream');
const bars = document.querySelectorAll('.bar');
const textInput = document.getElementById('textInput');

function appendBubble(text, role = 'agent') {
  const b = document.createElement('div');
  b.className = `chat-bubble ${role}`;
  b.innerHTML = text
    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/\n/g, '<br>');
  activityStream.appendChild(b);
  activityStream.scrollTop = activityStream.scrollHeight;
  return b;
}

function appendActionCard(msg) {
  const isApproval = msg.type === 'approval_card' || msg.requires_confirmation;
  const card = document.createElement('div');
  card.className = isApproval ? 'chat-bubble action-card approval-card' : 'chat-bubble action-card';
  
  let html = `<div class="action-card-header"><span>${msg.icon || (isApproval ? '🛡️' : '📅')}</span><span>${msg.title}</span></div>`;
  if (msg.details) {
    html += `<div class="action-card-body">${msg.details.replace(/\n/g, '<br>')}</div>`;
  }

  if (isApproval && msg.recipient) {
    const safeRecipient = encodeURIComponent(msg.recipient);
    const draftId = msg.draft_id || 'draft';
    html += `
      <div class="approval-actions">
        <button class="approval-btn approve-btn" onclick="approveDraft('${safeRecipient}', '${draftId}', this)">
          ✓ Approve & Send Email
        </button>
        ${msg.link ? `<a href="${msg.link}" target="_blank" class="approval-btn draft-link-btn">Review in Gmail ↗</a>` : ''}
      </div>
      <div class="approval-status-hint">🔒 Strict Guardrail: Send is gated until you confirm verbally or click above.</div>
    `;
  } else if (msg.link) {
    const linkLabel = msg.link.includes('mail.google.com') ? 'Open in Gmail ↗' : 'View in Google Calendar ↗';
    html += `<div style="margin-top:8px;"><a href="${msg.link}" target="_blank" style="color:var(--accent);font-weight:600;text-decoration:underline;">${linkLabel}</a></div>`;
  }

  card.innerHTML = html;
  activityStream.appendChild(card);
  activityStream.scrollTop = activityStream.scrollHeight;
}

function approveDraft(recipientEnc, draftId, btn) {
  const recipient = decodeURIComponent(recipientEnc);
  if (btn) {
    btn.disabled = true;
    btn.innerText = "✓ Sending Authorized...";
    btn.style.opacity = "0.7";
    btn.style.cursor = "default";
  }
  const prompt = `I explicitly approve sending the draft email to ${recipient}. Please send it now.`;
  appendBubble(prompt, 'user');
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "text", text: prompt }));
  }
}

function appendTranscriptChunk(text, role = 'agent') {
  if (role === 'user') {
    if (!currentUserBubble) {
      currentUserBubble = appendBubble(text, 'user');
    } else {
      currentUserBubble.textContent += text;
    }
  } else {
    if (!currentAgentBubble) {
      currentAgentBubble = appendBubble(text, 'agent');
    } else {
      currentAgentBubble.textContent += text;
    }
  }
  activityStream.scrollTop = activityStream.scrollHeight;
}

// --- Audio Output Playback (24kHz Raw PCM from Gemini Live API) ---
function initPlaybackContext() {
  if (!audioCtxOut) {
    audioCtxOut = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
  }
  if (audioCtxOut.state === 'suspended') {
    audioCtxOut.resume();
  }
}

function playPCMChunk(arrayBuffer) {
  initPlaybackContext();

  isAgentSpeaking = true;
  liveOrb.className = 'orb speaking';
  orbIcon.textContent = '🔊';
  stateTitle.textContent = 'Agenica is speaking...';
  stateSubtitle.textContent = 'Native Gemini voice output (Aoede)';

  const int16Array = new Int16Array(arrayBuffer);
  if (int16Array.length === 0) return;

  const float32 = new Float32Array(int16Array.length);
  for (let i = 0; i < int16Array.length; i++) {
    float32[i] = int16Array[i] / 32768.0;
  }

  const audioBuffer = audioCtxOut.createBuffer(1, float32.length, 24000);
  audioBuffer.copyToChannel(float32, 0);

  const source = audioCtxOut.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioCtxOut.destination);

  const now = audioCtxOut.currentTime;
  if (isNaN(nextPlayTime) || nextPlayTime < now) {
    nextPlayTime = now + 0.02;
  }
  source.start(nextPlayTime);
  nextPlayTime += audioBuffer.duration;

  activeSources.push(source);
  source.onended = () => {
    activeSources = activeSources.filter(s => s !== source);
  };
}

function finishAgentTurn() {
  isAgentSpeaking = false;
  if (isConnected) {
    liveOrb.className = 'orb connected';
    orbIcon.textContent = '🟢';
    stateTitle.textContent = 'I am listening... (Speak freely)';
    stateSubtitle.textContent = 'Continuous multi-turn live conversation active';
  }
  currentAgentBubble = null;
  currentUserBubble = null;
}

function onTurnCompleteReceived() {
  if (turnCompletionTimer) clearTimeout(turnCompletionTimer);
  const remainingSeconds = audioCtxOut ? Math.max(0, nextPlayTime - audioCtxOut.currentTime) : 0;
  turnCompletionTimer = setTimeout(() => {
    finishAgentTurn();
  }, Math.ceil(remainingSeconds * 1000) + 80);
}

function interruptPlayback() {
  activeSources.forEach(s => {
    try { s.stop(); } catch(e) {}
  });
  activeSources = [];
  if (audioCtxOut) {
    nextPlayTime = audioCtxOut.currentTime;
  }
  if (turnCompletionTimer) {
    clearTimeout(turnCompletionTimer);
    turnCompletionTimer = null;
  }
  finishAgentTurn();
}

// --- Audio Input Processing (Microphone -> 16kHz PCM -> WebSocket) ---
function startAudioProcessing() {
  if (!micStream || !audioCtxIn) return;

  if (audioCtxIn.state === 'suspended') {
    audioCtxIn.resume();
  }

  const source = audioCtxIn.createMediaStreamSource(micStream);
  scriptProcessor = audioCtxIn.createScriptProcessor(4096, 1, 1);

  scriptProcessor.onaudioprocess = (e) => {
    if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

    const inputData = e.inputBuffer.getChannelData(0);

    // Calculate RMS audio energy
    let sum = 0;
    for (let i = 0; i < inputData.length; i++) {
      sum += inputData[i] * inputData[i];
    }
    const rms = Math.sqrt(sum / inputData.length);

    // Animate visualizer
    const amp = Math.min(24, Math.max(4, Math.round(rms * 150)));
    bars.forEach((b, idx) => {
      b.style.height = `${Math.max(4, amp + (idx % 3) * 3)}px`;
    });

    // Echo Guard & Interruption detection:
    if (isAgentSpeaking) {
      if (rms > 0.035) {
        interruptPlayback();
      } else {
        return;
      }
    }

    // Convert Float32 directly to 16-bit PCM (audioCtxIn sampleRate is 16kHz)
    const pcm16 = new Int16Array(inputData.length);
    for (let i = 0; i < inputData.length; i++) {
      let s = Math.max(-1, Math.min(1, inputData[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    ws.send(pcm16.buffer);
  };

  source.connect(scriptProcessor);
  scriptProcessor.connect(audioCtxIn.destination);
}

function stopMicCapture() {
  if (scriptProcessor) {
    try { scriptProcessor.disconnect(); } catch (e) {}
    scriptProcessor = null;
  }
  if (micStream) {
    try { micStream.getTracks().forEach(t => t.stop()); } catch (e) {}
    micStream = null;
  }
  if (audioCtxIn) {
    try { audioCtxIn.close(); } catch (e) {}
    audioCtxIn = null;
  }
  bars.forEach(b => b.style.height = '6px');
}

// --- WebSocket Connection Management ---
async function toggleLiveConnection() {
  if (isConnecting) return;
  if (isConnected) {
    disconnectLive();
  } else {
    await connectLive();
  }
}

async function connectLive() {
  if (isConnecting || isConnected) return;
  isConnecting = true;

  // 1. Critical: Initialize & resume AudioContexts directly in the user click gesture!
  try {
    initPlaybackContext();
    if (!audioCtxIn) {
      audioCtxIn = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (audioCtxIn.state === 'suspended') {
      await audioCtxIn.resume();
    }

    if (!micStream) {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
    }
  } catch (err) {
    console.error("Microphone or AudioContext initialization failed:", err);
    appendBubble("Microphone permission or audio error: " + err.message, "agent");
    isConnecting = false;
    return;
  }

  liveOrb.className = 'orb connecting';
  orbIcon.textContent = '⏳';
  stateTitle.textContent = 'Connecting to Gemini Live API...';
  stateSubtitle.textContent = 'Activating microphone and neural stream...';
  headerStatus.textContent = 'Connecting...';

  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = sessionStorage.getItem('agenica_token') || '';
  const wsUrl = `${proto}//${window.location.host}/ws/live${token ? '?token=' + encodeURIComponent(token) : ''}`;
  ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    isConnecting = false;
    isConnected = true;
    headerStatus.textContent = 'Live Audio Connected';
    liveOrb.className = 'orb connected';
    orbIcon.textContent = '🟢';
    stateTitle.textContent = 'I am listening... (Speak freely)';
    stateSubtitle.textContent = 'Continuous multi-turn live conversation active';
    appendBubble("Connected to Gemini Live API. I'm ready, Abhi! Speak anytime.", "agent");

    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 10000);

    startAudioProcessing();
  };

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      playPCMChunk(event.data);
    } else {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'interrupted') {
          interruptPlayback();
        } else if (msg.type === 'transcript_chunk') {
          appendTranscriptChunk(msg.text, msg.role || 'agent');
        } else if (msg.type === 'transcript') {
          appendBubble(msg.text, msg.role || 'agent');
        } else if (msg.type === 'tool_action' || msg.type === 'approval_card') {
          appendActionCard(msg);
        } else if (msg.type === 'turn_complete') {
          onTurnCompleteReceived();
        }
      } catch (err) {}
    }
  };

  ws.onerror = (e) => {
    isConnecting = false;
  };

  ws.onclose = (e) => {
    isConnecting = false;
    if (e.code === 1008) {
      sessionStorage.removeItem('agenica_token');
      showAuthModal(true);
      appendBubble("Access Denied: Authentication required or invalid access key.", "agent");
    } else if (e.code === 1013) {
      appendBubble("System is currently busy (maximum concurrent active sessions reached). Please try again shortly.", "agent");
    }
    disconnectLive();
  };
}

function disconnectLive() {
  isConnecting = false;
  isConnected = false;
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  stopMicCapture();
  interruptPlayback();
  currentUserBubble = null;
  currentAgentBubble = null;
  headerStatus.textContent = 'Disconnected';
  liveOrb.className = 'orb';
  orbIcon.textContent = '🎙️';
  stateTitle.textContent = 'Click to Start Live Voice Conversation';
  stateSubtitle.textContent = 'Continuous hands-free dialogue: speak naturally across multiple turns';
}

function sendTextMessage(e) {
  e.preventDefault();
  const val = textInput.value.trim();
  if (!val) return;
  textInput.value = '';

  if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
    appendBubble("Please connect by tapping the orb first!", "agent");
    return;
  }

  appendBubble(val, "user");
  ws.send(JSON.stringify({ type: "text", text: val }));
}

// --- Security & Access Gatekeeper Integration ---
function initSecurity() {
  const params = new URLSearchParams(window.location.search);
  const keyParam = params.get('key') || params.get('token');
  if (keyParam) {
    sessionStorage.setItem('agenica_token', keyParam);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  fetch('/api/auth/status')
    .then(r => r.json())
    .then(d => {
      if (d.auth_required && !sessionStorage.getItem('agenica_token')) {
        showAuthModal(false);
      }
    })
    .catch(() => {});
}

function showAuthModal(hasError = false) {
  const modal = document.getElementById('authModal');
  const err = document.getElementById('authError');
  if (modal) modal.style.display = 'flex';
  if (err) err.style.display = hasError ? 'block' : 'none';
  const inp = document.getElementById('authKeyInput');
  if (inp) {
    inp.value = '';
    inp.focus();
  }
}

function handleAuthSubmit(e) {
  e.preventDefault();
  const inp = document.getElementById('authKeyInput');
  const val = inp ? inp.value.trim() : '';
  if (val) {
    sessionStorage.setItem('agenica_token', val);
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
    connectLive();
  }
}

document.addEventListener('DOMContentLoaded', initSecurity);
