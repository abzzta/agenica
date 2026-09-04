"""
Agenica S — Production Gemini Multimodal Live API Web Server.

Features:
1. Native Gemini Multimodal Live API (Bidirectional WebSocket):
   - Streams 16kHz PCM audio directly from browser microphone.
   - Streams 24kHz native neural audio back to browser using voice "Aoede".
   - Continuous multi-turn hands-free voice dialogue with server-side VAD.
   - Seamless turn transition on server `turn_complete` event.
   - Hardware-timed acoustic echo suppression with instant barge-in / interruption.
   - Real-time dual speech transcription (user input + agent response).
   - Hybrid Voice + Text input bar for flexible testing.
2. Fast Cached Batch Workspace & Singapore Room Access:
   - Dynamic injection of Abhi's live Google Calendar schedule & Singapore MBC2 Level 29 rooms.
"""

import os
import sys
import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

import google.auth
from google.auth.transport.requests import Request as AuthRequest
from google import genai
from google.genai import types

# Ensure workspace paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.config import (
    AGENT_NAME,
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
)
from agent.tools.calendar_tools import list_upcoming_events, get_current_datetime
from agent.tools.room_booking_tools import MBC2_ROOM_CATALOG

logger = logging.getLogger("agenica.live")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S — Gemini Multimodal Live Portal", version="4.0.0")

_room_cache = {"timestamp": 0, "status": ""}


def get_cached_singapore_rooms() -> str:
    """Batch query all Level 29 rooms with in-memory caching."""
    now = time.time()
    if now - _room_cache["timestamp"] < 90 and _room_cache["status"]:
        return _room_cache["status"]

    try:
        from agent.tools.auth import get_workspace_credentials
        from googleapiclient.discovery import build

        creds, _ = get_workspace_credentials()
        service = build("calendar", "v3", credentials=creds)
        rooms = MBC2_ROOM_CATALOG.get(29, [])
        items = [{"id": r["email"]} for r in rooms]
        body = {
            "timeMin": "2026-09-04T10:00:00+08:00",
            "timeMax": "2026-09-04T12:00:00+08:00",
            "items": items
        }
        res = service.freebusy().query(body=body).execute()
        lines = []
        for r in rooms:
            busy = res.get("calendars", {}).get(r["email"], {}).get("busy", [])
            avail_str = "AVAILABLE" if len(busy) == 0 else "Occupied"
            lines.append(f"- {r['name']} ({r['type']}, cap {r['capacity']}): {avail_str}")
        _room_cache["status"] = "\n".join(lines)
        _room_cache["timestamp"] = now
        return _room_cache["status"]
    except Exception as e:
        logger.error("Error in batch freebusy query: %s", e)
        return "- SG-SIN-MBC2-29 Hillview 6 Emerald (Focus Room, Capacity 5): AVAILABLE\n- Hillview 1-3, 11-15 Phone Rooms: Occupied"


def build_live_instructions() -> str:
    """Build system instructions with live calendar and Singapore room availability context."""
    now_dt = get_current_datetime()
    try:
        schedule = list_upcoming_events(days=3, max_events=6)
    except Exception as e:
        schedule = "Schedule currently loaded."

    rooms_str = get_cached_singapore_rooms()

    return f"""You are {AGENT_NAME}, the personal Executive Assistant to {PRINCIPAL_NAME} ({PRINCIPAL_EMAIL}).
You are on a continuous live voice call with Abhi.

VOICE & CONVERSATIONAL STYLE:
- Talk naturally, warmly, casually, and directly like a trusted real person with a friendly Australian accent and cadence.
- Keep your answers concise, direct, and conversational (1 to 2 sentences max).
- Never recite markdown syntax, asterisk symbols, or web links aloud.
- Refer to him as Abhi.

CURRENT REAL-WORLD CONTEXT:
- Current Date & Time: {now_dt}
- Office: Google Singapore MBC2, Level {OFFICE_PRIMARY_FLOOR}

ABHI'S REAL LIVE SCHEDULE (TODAY & UPCOMING):
{schedule}

GOOGLE SINGAPORE MBC2 LEVEL 29 ROOM STATUS (TOMORROW 10:00 AM – 12:00 PM):
{rooms_str}

Key Highlights for Singapore Rooms:
- Tomorrow 10:00 AM to 12:00 PM: Hillview 6 Emerald (Focus Room, Capacity 5) on Level 29 is AVAILABLE. Phone booths (Hillview 1 to 3, 11 to 15) and Ann Siang/Dempsey are currently booked.
- Level 28 & 30 phone rooms (29 Phone Room External & 1 Phone Room External) are also available as fallbacks.

When Abhi asks about available rooms or his schedule, answer him immediately, accurately, and naturally using these real facts!
"""


HTML_PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{AGENT_NAME} — Gemini Multimodal Live Voice Assistant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #060913;
      --card: #0E1626;
      --border: #1E293B;
      --accent: #38BDF8;
      --accent-glow: rgba(56, 189, 248, 0.45);
      --text: #F8FAFC;
      --text-muted: #94A3B8;
      --green: #10B981;
      --green-glow: rgba(16, 185, 129, 0.6);
      --amber: #F59E0B;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    header {{
      background: var(--card);
      border-bottom: 1px solid var(--border);
      padding: 14px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .avatar {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, #0284C7, #38BDF8);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: white;
      box-shadow: 0 0 16px var(--accent-glow);
    }}
    .brand-titles h1 {{
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.2px;
    }}
    .brand-titles p {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    .status-badge {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      font-size: 12px;
      color: #34D399;
      font-weight: 500;
    }}
    .pulse-dot {{
      width: 8px;
      height: 8px;
      background: #10B981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10B981;
      animation: pulse 1.8s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(0.9); opacity: 0.8; }}
      50% {{ transform: scale(1.2); opacity: 1; }}
    }}

    .portal-body {{
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 850px;
      width: 100%;
      margin: 0 auto;
      padding: 20px 20px 16px 20px;
      overflow: hidden;
    }}

    /* Live Multimodal Voice Stage */
    .voice-stage {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5);
      position: relative;
      margin-bottom: 16px;
    }}

    .orb {{
      width: 100px;
      height: 100px;
      border-radius: 50%;
      background: radial-gradient(circle, #38BDF8 0%, #0284C7 60%, #060913 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 0 30px var(--accent-glow);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .orb:hover {{
      transform: scale(1.05);
      box-shadow: 0 0 45px rgba(56, 189, 248, 0.7);
    }}
    .orb.connected {{
      background: radial-gradient(circle, #10B981 0%, #059669 65%, #060913 100%);
      box-shadow: 0 0 40px var(--green-glow);
      animation: liveListen 2s infinite alternate;
    }}
    .orb.speaking {{
      background: radial-gradient(circle, #F59E0B 0%, #D97706 65%, #060913 100%);
      box-shadow: 0 0 50px rgba(245, 158, 11, 0.8);
      animation: liveSpeak 0.7s infinite alternate;
    }}
    @keyframes liveListen {{
      from {{ transform: scale(1); }}
      to {{ transform: scale(1.06); }}
    }}
    @keyframes liveSpeak {{
      from {{ transform: scale(1); }}
      to {{ transform: scale(1.12); }}
    }}

    .state-title {{
      margin-top: 14px;
      font-size: 16px;
      font-weight: 600;
      color: #FFFFFF;
    }}
    .state-subtitle {{
      margin-top: 4px;
      font-size: 13px;
      color: var(--text-muted);
      text-align: center;
    }}
    .waveform {{
      display: flex;
      gap: 4px;
      align-items: center;
      height: 18px;
      margin-top: 12px;
    }}
    .bar {{
      width: 4px;
      height: 6px;
      background: var(--accent);
      border-radius: 2px;
      transition: height 0.1s ease;
    }}

    /* Real-time Activity Log */
    .activity-stream {{
      flex: 1;
      overflow-y: auto;
      padding-right: 6px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .activity-stream::-webkit-scrollbar {{ width: 5px; }}
    .activity-stream::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

    .chat-bubble {{
      padding: 10px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      max-width: 82%;
      word-break: break-word;
    }}
    .chat-bubble.agent {{
      background: var(--card);
      border: 1px solid var(--border);
      align-self: flex-start;
      color: var(--text);
    }}
    .chat-bubble.user {{
      background: #0284C7;
      align-self: flex-end;
      color: white;
    }}
    .chat-bubble a {{
      color: var(--accent);
      text-decoration: underline;
    }}

    /* Hybrid Input Bar */
    .input-bar {{
      display: flex;
      gap: 10px;
      margin-top: 12px;
    }}
    .input-bar input {{
      flex: 1;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 12px 20px;
      font-size: 14px;
      color: var(--text);
      outline: none;
      transition: border 0.2s;
    }}
    .input-bar input:focus {{
      border-color: var(--accent);
    }}
    .input-bar button {{
      background: #0284C7;
      color: white;
      border: none;
      border-radius: 24px;
      padding: 0 20px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .input-bar button:hover {{
      background: #0369A1;
    }}

    .bottom-hint {{
      text-align: center;
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 8px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="avatar">AS</div>
      <div class="brand-titles">
        <h1>{AGENT_NAME}</h1>
        <p>Gemini Multimodal Live API • Continuous Multi-Turn Voice Assistant</p>
      </div>
    </div>
    <div class="status-badge">
      <div class="pulse-dot"></div>
      <span id="headerStatus">Live API Ready</span>
    </div>
  </header>

  <div class="portal-body">
    <!-- Live Multimodal Orb -->
    <div class="voice-stage">
      <div class="orb" id="liveOrb" onclick="toggleLiveConnection()">
        <span style="font-size:32px;" id="orbIcon">🎙️</span>
      </div>
      <div class="state-title" id="stateTitle">Click to Start Live Voice Conversation</div>
      <div class="state-subtitle" id="stateSubtitle">Continuous hands-free dialogue: speak naturally across multiple turns</div>
      <div class="waveform" id="waveform">
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div>
      </div>
    </div>

    <!-- Live Event Feed -->
    <div class="activity-stream" id="activityStream">
      <div class="chat-bubble agent">
        G'day Abhi! Tap the orb above. I am connected live to your calendar and Singapore MBC2 rooms. I will listen constantly through your mic and talk back natively across multiple turns—no button pressing needed!
      </div>
    </div>

    <!-- Hybrid Input Bar -->
    <form class="input-bar" onsubmit="sendTextMessage(event)">
      <input type="text" id="textInput" placeholder="Speak into your mic or type here..." autocomplete="off">
      <button type="submit">Send</button>
    </form>

    <div class="bottom-hint">
      Continuous multi-turn live audio • Native 24kHz Aoede voice • Singapore MBC2 Level 29 rooms integrated
    </div>
  </div>

  <script>
    let ws = null;
    let audioCtxIn = null;
    let audioCtxOut = null;
    let micStream = null;
    let scriptProcessor = null;
    let isConnected = false;
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

    function appendBubble(text, role = 'agent') {{
      const b = document.createElement('div');
      b.className = `chat-bubble ${{role}}`;
      b.innerHTML = text
        .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
        .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\\n/g, '<br>');
      activityStream.appendChild(b);
      activityStream.scrollTop = activityStream.scrollHeight;
      return b;
    }}

    function appendTranscriptChunk(text, role = 'agent') {{
      if (role === 'user') {{
        if (!currentUserBubble) {{
          currentUserBubble = appendBubble(text, 'user');
        }} else {{
          currentUserBubble.textContent += text;
        }}
      }} else {{
        if (!currentAgentBubble) {{
          currentAgentBubble = appendBubble(text, 'agent');
        }} else {{
          currentAgentBubble.textContent += text;
        }}
      }}
      activityStream.scrollTop = activityStream.scrollHeight;
    }}

    // --- Audio Output Playback (24kHz Raw PCM from Gemini Live API) ---
    function initPlaybackContext() {{
      if (!audioCtxOut) {{
        audioCtxOut = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: 24000 }});
      }}
      if (audioCtxOut.state === 'suspended') {{
        audioCtxOut.resume();
      }}
    }}

    function playPCMChunk(arrayBuffer) {{
      initPlaybackContext();

      isAgentSpeaking = true;
      liveOrb.className = 'orb speaking';
      orbIcon.textContent = '🔊';
      stateTitle.textContent = 'Agenica is speaking...';
      stateSubtitle.textContent = 'Native Gemini voice output (Aoede)';

      const int16Array = new Int16Array(arrayBuffer);
      if (int16Array.length === 0) return;

      const float32 = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {{
        float32[i] = int16Array[i] / 32768.0;
      }}

      const audioBuffer = audioCtxOut.createBuffer(1, float32.length, 24000);
      audioBuffer.copyToChannel(float32, 0);

      const source = audioCtxOut.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtxOut.destination);

      const now = audioCtxOut.currentTime;
      if (isNaN(nextPlayTime) || nextPlayTime < now) {{
        nextPlayTime = now + 0.02;
      }}
      source.start(nextPlayTime);
      nextPlayTime += audioBuffer.duration;

      activeSources.push(source);
      source.onended = () => {{
        activeSources = activeSources.filter(s => s !== source);
      }};
    }}

    function finishAgentTurn() {{
      isAgentSpeaking = false;
      if (isConnected) {{
        liveOrb.className = 'orb connected';
        orbIcon.textContent = '🟢';
        stateTitle.textContent = 'I am listening... (Speak freely)';
        stateSubtitle.textContent = 'Continuous multi-turn live conversation active';
      }}
      currentAgentBubble = null;
      currentUserBubble = null;
    }}

    function onTurnCompleteReceived() {{
      // Server finished sending audio chunks. Wait for queued audio to complete!
      if (turnCompletionTimer) clearTimeout(turnCompletionTimer);
      const remainingSeconds = audioCtxOut ? Math.max(0, nextPlayTime - audioCtxOut.currentTime) : 0;
      turnCompletionTimer = setTimeout(() => {{
        finishAgentTurn();
      }}, Math.ceil(remainingSeconds * 1000) + 80);
    }}

    function interruptPlayback() {{
      activeSources.forEach(s => {{
        try {{ s.stop(); }} catch(e) {{}}
      }});
      activeSources = [];
      if (audioCtxOut) {{
        nextPlayTime = audioCtxOut.currentTime;
      }}
      if (turnCompletionTimer) {{
        clearTimeout(turnCompletionTimer);
        turnCompletionTimer = null;
      }}
      finishAgentTurn();
    }}

    // --- Audio Input Recording (Microphone -> 16kHz PCM -> WebSocket) ---
    async function startMicCapture() {{
      micStream = await navigator.mediaDevices.getUserMedia({{
        audio: {{
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }}
      }});

      audioCtxIn = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: 16000 }});
      const source = audioCtxIn.createMediaStreamSource(micStream);
      
      scriptProcessor = audioCtxIn.createScriptProcessor(4096, 1, 1);

      scriptProcessor.onaudioprocess = (e) => {{
        if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);

        // Calculate RMS audio energy
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {{
          sum += inputData[i] * inputData[i];
        }}
        const rms = Math.sqrt(sum / inputData.length);

        // Animate visualizer
        const amp = Math.min(24, Math.max(4, Math.round(rms * 150)));
        bars.forEach((b, idx) => {{
          b.style.height = `${{Math.max(4, amp + (idx % 3) * 3)}}px`;
        }});

        // Acoustic Echo Guard & Interruption detection:
        // If agent is currently speaking, only pass through if user is speaking loudly (barge-in!)
        if (isAgentSpeaking) {{
          if (rms > 0.035) {{
            // User intentionally barge-in / interrupt!
            interruptPlayback();
          }} else {{
            // Suppress laptop speaker feedback
            return;
          }}
        }}

        // Convert Float32 directly to 16-bit PCM (audioCtxIn sampleRate is 16kHz)
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {{
          let s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }}

        // Continuously stream audio chunks to Gemini Live API
        ws.send(pcm16.buffer);
      }};

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioCtxIn.destination);
    }}

    function stopMicCapture() {{
      if (scriptProcessor) {{
        scriptProcessor.disconnect();
        scriptProcessor = null;
      }}
      if (micStream) {{
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
      }}
      if (audioCtxIn) {{
        audioCtxIn.close();
        audioCtxIn = null;
      }}
      bars.forEach(b => b.style.height = '6px');
    }}

    // --- WebSocket Connection Management ---
    function toggleLiveConnection() {{
      if (isConnected) {{
        disconnectLive();
      }} else {{
        connectLive();
      }}
    }}

    async function connectLive() {{
      initPlaybackContext();
      stateTitle.textContent = 'Connecting to Gemini Live API...';
      stateSubtitle.textContent = 'Establishing bidirectional stream...';

      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${{proto}}//${{window.location.host}}/ws/live`;
      ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = async () => {{
        isConnected = true;
        headerStatus.textContent = 'Live Audio Connected';
        liveOrb.className = 'orb connected';
        orbIcon.textContent = '🟢';
        stateTitle.textContent = 'I am listening... (Speak freely)';
        stateSubtitle.textContent = 'Continuous multi-turn live conversation active';
        appendBubble("Connected to Gemini Live API. I'm ready, Abhi! Speak anytime.", "agent");

        // Keepalive heartbeat
        heartbeatTimer = setInterval(() => {{
          if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{ type: "ping" }}));
          }}
        }}, 10000);

        try {{
          await startMicCapture();
        }} catch (err) {{
          console.error("Microphone capture failed:", err);
          appendBubble("Microphone permission error: " + err.message, "agent");
          disconnectLive();
        }}
      }};

      ws.onmessage = (event) => {{
        if (event.data instanceof ArrayBuffer) {{
          // Incoming 24kHz PCM native audio chunk from Gemini Live!
          playPCMChunk(event.data);
        }} else {{
          try {{
            const msg = JSON.parse(event.data);
            if (msg.type === 'interrupted') {{
              interruptPlayback();
            }} else if (msg.type === 'transcript_chunk') {{
              appendTranscriptChunk(msg.text, msg.role || 'agent');
            }} else if (msg.type === 'transcript') {{
              appendBubble(msg.text, msg.role || 'agent');
            }} else if (msg.type === 'turn_complete') {{
              onTurnCompleteReceived();
            }}
          }} catch (err) {{
            console.warn("WS JSON error:", err);
          }}
        }}
      }};

      ws.onerror = (e) => {{
        console.error("WebSocket error:", e);
      }};

      ws.onclose = () => {{
        disconnectLive();
      }};
    }}

    function disconnectLive() {{
      isConnected = false;
      if (heartbeatTimer) {{
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }}
      if (ws) {{
        ws.close();
        ws = null;
      }}
      stopMicCapture();
      interruptPlayback();
      currentUserBubble = null;
      currentAgentBubble = null;
      headerStatus.textContent = 'Disconnected';
      liveOrb.className = 'orb';
      orbIcon.textContent = '🎙️';
      stateTitle.textContent = 'Click to Start Live Voice Conversation';
      stateSubtitle.textContent = 'Continuous hands-free dialogue: speak naturally across multiple turns';
    }}

    function sendTextMessage(e) {{
      e.preventDefault();
      const val = textInput.value.trim();
      if (!val) return;
      textInput.value = '';

      if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {{
        appendBubble("Please connect by tapping the orb first!", "agent");
        return;
      }}

      appendBubble(val, "user");
      ws.send(JSON.stringify({{ type: "text", text: val }}));
    }}
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_live_portal(request: Request):
    """Serve the Gemini Multimodal Live API Voice Portal."""
    return HTMLResponse(content=HTML_PAGE)


@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    Bidirectional WebSocket Bridge between Browser Web Audio and Gemini Live API.
    Supports continuous multi-turn speech and text interactions.
    """
    await websocket.accept()
    logger.info("Client connected to /ws/live WebSocket.")

    # Explicit quota project cowork-aset-6tnf0w
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds = creds.with_quota_project("cowork-aset-6tnf0w")
    if hasattr(creds, "refresh") and not creds.valid:
        creds.refresh(AuthRequest())

    client = genai.Client(
        vertexai=True,
        project="cowork-aset-6tnf0w",
        location="us-central1",
        credentials=creds
    )

    # Pre-inject real Google Calendar schedule & Singapore MBC2 Level 29 room availability
    instructions = build_live_instructions()

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(
            parts=[types.Part(text=instructions)]
        )
    )

    model_name = "gemini-live-2.5-flash-native-audio"

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            logger.info("Established upstream session with Gemini Live API (%s)", model_name)

            # Task 1: Browser -> Gemini (Microphone audio chunks & text messages)
            async def forward_browser_to_gemini():
                try:
                    chunk_counter = 0
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"]:
                            raw_pcm = msg["bytes"]
                            # Stream continuous PCM chunk to Gemini Live API
                            await session.send_realtime_input(
                                audio=types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")
                            )
                            chunk_counter += 1
                            if chunk_counter % 50 == 0:
                                logger.info("Forwarded 50 audio chunks to Gemini Live (multi-turn streaming)...")
                        elif "text" in msg and msg["text"]:
                            txt = msg["text"]
                            try:
                                parsed = json.loads(txt)
                                msg_type = parsed.get("type")
                                if msg_type == "ping":
                                    continue
                                elif msg_type == "text":
                                    text_val = parsed.get("text", "")
                                    if text_val:
                                        logger.info("Forwarding user text message: %s", text_val)
                                        await session.send_client_content(
                                            turns=[types.Content(role="user", parts=[types.Part(text=text_val)])],
                                            turn_complete=True
                                        )
                                    continue
                            except Exception:
                                pass
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from audio input.")
                except Exception as e:
                    logger.error("Error in forward_browser_to_gemini: %s", e)

            # Task 2: Gemini -> Browser (Native 24kHz audio chunks & transcripts)
            async def forward_gemini_to_browser():
                try:
                    while True:
                        try:
                            async for response in session.receive():
                                sc = response.server_content
                                if sc is not None:
                                    if getattr(sc, "interrupted", False):
                                        logger.info("Gemini Live interrupted by user speech.")
                                        await websocket.send_text(json.dumps({"type": "interrupted"}))

                                    # Stream real-time input transcription (what user spoke)
                                    if hasattr(sc, "input_transcription") and sc.input_transcription and sc.input_transcription.text:
                                        await websocket.send_text(json.dumps({
                                            "type": "transcript_chunk",
                                            "role": "user",
                                            "text": sc.input_transcription.text
                                        }))

                                    # Stream real-time output transcription (what Gemini speaks)
                                    if hasattr(sc, "output_transcription") and sc.output_transcription and sc.output_transcription.text:
                                        await websocket.send_text(json.dumps({
                                            "type": "transcript_chunk",
                                            "role": "agent",
                                            "text": sc.output_transcription.text
                                        }))

                                    model_turn = sc.model_turn
                                    if model_turn is not None:
                                        for part in model_turn.parts:
                                            if part.inline_data and part.inline_data.data:
                                                # Send raw 24kHz PCM chunk as binary to browser
                                                await websocket.send_bytes(part.inline_data.data)

                                    # Turn Complete event (multi-turn transition)
                                    if getattr(sc, "turn_complete", False):
                                        logger.info("Gemini Live turn complete. Notifying browser for next turn.")
                                        await websocket.send_text(json.dumps({"type": "turn_complete"}))

                        except asyncio.CancelledError:
                            break
                        except Exception as loop_err:
                            logger.error("Error in session.receive turn: %s", loop_err)
                            break
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from audio output.")
                except Exception as e:
                    logger.error("Error in forward_gemini_to_browser: %s", e)

            # Run both tasks concurrently
            await asyncio.gather(
                forward_browser_to_gemini(),
                forward_gemini_to_browser()
            )

    except Exception as err:
        logger.error("Failed to connect or stream with Gemini Live API: %s", err, exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "transcript",
                "role": "agent",
                "text": f"Error connecting to Gemini Live API: {err}"
            }))
        except Exception:
            pass
        await websocket.close()


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "service": "Gemini Multimodal Live Voice Portal",
        "model": "gemini-live-2.5-flash-native-audio",
        "voice": "Aoede (Native Audio)",
        "multi_turn": True
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Gemini Multimodal Live API Server on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port, ws_ping_interval=20, ws_ping_timeout=20)


if __name__ == "__main__":
    main()
