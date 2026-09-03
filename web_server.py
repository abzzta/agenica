"""
Agenica S — Production Gemini Multimodal Live API Web Server.

Features:
1. Native Gemini Multimodal Live API (Bidirectional WebSocket):
   - Streams 16kHz PCM audio directly from browser microphone.
   - Streams 24kHz native neural audio back to browser using voice "Aoede".
   - Continuous server-side Voice Activity Detection (VAD) & hands-free conversation.
   - Real-time dual transcription (input & output) for live visual feedback.
   - Instant barge-in & interruption handling.
2. Live Workspace Tool Execution:
   - Real-time Google Calendar schedule queries.
   - Real-time Singapore MBC2 Level 29 room availability & booking.
"""

import os
import sys
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
from agent.tools.room_booking_tools import book_mbc_room_for_chunk

logger = logging.getLogger("agenica.live")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S — Gemini Multimodal Live Portal", version="3.1.0")

LIVE_SYSTEM_INSTRUCTION = f"""
You are {AGENT_NAME}, the world-class personal Executive Assistant to {PRINCIPAL_NAME} ({PRINCIPAL_EMAIL}).
You are speaking over a live, continuous two-way audio call with Abhi.

VOICE & CONVERSATIONAL RULES:
- Talk naturally, warmly, casually, and directly like a trusted real person with a friendly Australian accent and cadence.
- Keep your spoken responses concise and conversational (1 to 2 sentences).
- Never read out markdown headers, bullets, asterisk symbols, or web links.
- When Abhi asks about his schedule or wants to book a room, execute your tools immediately to get real facts, then casually share the outcome.
- If booking a room in Singapore MBC2 (Level {OFFICE_PRIMARY_FLOOR}), use your booking tool and confirm the room name and time casually.
"""

LIVE_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "check_calendar_schedule",
                "description": "Check Abhi's upcoming calendar events and meetings for today or upcoming days.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "days": {
                            "type": "INTEGER",
                            "description": "Number of days ahead to inspect (default 2)."
                        }
                    }
                }
            },
            {
                "name": "book_singapore_mbc_room",
                "description": f"Book a focus room or phone booth on Level {OFFICE_PRIMARY_FLOOR} at Google Singapore MBC2 in Abhi's calendar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "date_str": {
                            "type": "STRING",
                            "description": "Date in YYYY-MM-DD format (e.g. 2026-09-04)."
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in HH:MM format (e.g. 14:30)."
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in HH:MM format (e.g. 16:00)."
                        },
                        "room_type": {
                            "type": "STRING",
                            "description": "Room type preference: 'phone_booth' (1-2 persons) or 'focus_room' (5 persons)."
                        }
                    },
                    "required": ["date_str", "start_time", "end_time"]
                }
            }
        ]
    }
]


def execute_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute real Workspace tool for the live session."""
    logger.info("Executing Live Tool Call: %s with args: %s", name, args)
    try:
        if name == "check_calendar_schedule":
            days = args.get("days", 2)
            events_summary = list_upcoming_events(days=days, max_events=6)
            return {"schedule_summary": events_summary}
        elif name == "book_singapore_mbc_room":
            date_str = args.get("date_str", "2026-09-04")
            start_time = args.get("start_time", "14:30")
            end_time = args.get("end_time", "16:00")
            room_type = args.get("room_type", "phone_booth")
            res = book_mbc_room_for_chunk(
                date_str=date_str,
                start_time=start_time,
                end_time=end_time,
                preferred_floor=OFFICE_PRIMARY_FLOOR,
                room_type=room_type
            )
            return res
        else:
            return {"error": f"Unknown tool {name}"}
    except Exception as e:
        logger.error("Error running tool %s: %s", name, e, exc_info=True)
        return {"error": str(e)}


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
      padding: 16px 28px;
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
      padding: 24px 20px;
      overflow: hidden;
    }}

    /* Live Multimodal Voice Stage */
    .voice-stage {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 32px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5);
      position: relative;
      margin-bottom: 20px;
    }}

    .orb {{
      width: 110px;
      height: 110px;
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
      to {{ transform: scale(1.08); }}
    }}
    @keyframes liveSpeak {{
      from {{ transform: scale(1); }}
      to {{ transform: scale(1.15); }}
    }}

    .state-title {{
      margin-top: 18px;
      font-size: 16px;
      font-weight: 600;
      color: #FFFFFF;
    }}
    .state-subtitle {{
      margin-top: 4px;
      font-size: 13px;
      color: var(--text-muted);
    }}
    .waveform {{
      display: flex;
      gap: 4px;
      align-items: center;
      height: 20px;
      margin-top: 14px;
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
      gap: 12px;
    }}
    .activity-stream::-webkit-scrollbar {{ width: 5px; }}
    .activity-stream::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

    .chat-bubble {{
      padding: 12px 18px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      max-width: 82%;
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

    .bottom-hint {{
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 10px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="avatar">AS</div>
      <div class="brand-titles">
        <h1>{AGENT_NAME}</h1>
        <p>Gemini Multimodal Live API • Native Bidirectional Audio (Aoede Voice)</p>
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
      <div class="state-subtitle" id="stateSubtitle">Native bidirectional streaming: continuously listens and talks back automatically</div>
      <div class="waveform" id="waveform">
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div>
      </div>
    </div>

    <!-- Live Event Feed -->
    <div class="activity-stream" id="activityStream">
      <div class="chat-bubble agent">
        G'day Abhi! Tap the orb above to open the <b>Gemini Multimodal Live API</b> connection. I will listen constantly through your microphone and talk back to you in real time with native voice. You don't have to click anything between turns!
      </div>
    </div>

    <div class="bottom-hint">
      Powered by Google Vertex AI Gemini Live Native Audio • Voice: Aoede • Low-latency bidirectional audio
    </div>
  </div>

  <script>
    let ws = null;
    let audioCtxIn = null;
    let audioCtxOut = null;
    let micStream = null;
    let scriptProcessor = null;
    let isConnected = false;
    let nextPlayTime = 0;
    let activeSources = [];

    let currentAgentBubble = null;
    let currentUserBubble = null;

    const liveOrb = document.getElementById('liveOrb');
    const orbIcon = document.getElementById('orbIcon');
    const stateTitle = document.getElementById('stateTitle');
    const stateSubtitle = document.getElementById('stateSubtitle');
    const headerStatus = document.getElementById('headerStatus');
    const activityStream = document.getElementById('activityStream');
    const bars = document.querySelectorAll('.bar');

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
      if (audioCtxOut.state === 'suspended') {{
        audioCtxOut.resume();
      }}

      // Convert 16-bit PCM to Float32
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

      // Schedule seamless audio chunks
      const now = audioCtxOut.currentTime;
      if (isNaN(nextPlayTime) || nextPlayTime < now) {{
        nextPlayTime = now + 0.02; // tiny jitter buffer
      }}
      source.start(nextPlayTime);
      nextPlayTime += audioBuffer.duration;

      activeSources.push(source);
      source.onended = () => {{
        activeSources = activeSources.filter(s => s !== source);
        if (activeSources.length === 0 && isConnected) {{
          liveOrb.className = 'orb connected';
          orbIcon.textContent = '🟢';
          stateTitle.textContent = 'Listening... (Speak freely)';
          stateSubtitle.textContent = 'Continuous live audio: speak naturally anytime';
          currentAgentBubble = null;
        }}
      }};

      liveOrb.className = 'orb speaking';
      orbIcon.textContent = '🔊';
      stateTitle.textContent = 'Agenica is speaking...';
      stateSubtitle.textContent = 'Native Gemini voice output (Aoede)';
    }}

    function interruptPlayback() {{
      // Instant barge-in: stop all playing chunks immediately
      activeSources.forEach(s => {{
        try {{ s.stop(); }} catch(e) {{}}
      }});
      activeSources = [];
      if (audioCtxOut) nextPlayTime = audioCtxOut.currentTime;
      if (isConnected) {{
        liveOrb.className = 'orb connected';
        orbIcon.textContent = '🟢';
        stateTitle.textContent = 'Listening... (Speak freely)';
      }}
      currentAgentBubble = null;
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

      audioCtxIn = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtxIn.createMediaStreamSource(micStream);
      
      // Use ScriptProcessor to resample to 16kHz PCM
      scriptProcessor = audioCtxIn.createScriptProcessor(4096, 1, 1);
      const inSampleRate = audioCtxIn.sampleRate;

      scriptProcessor.onaudioprocess = (e) => {{
        if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);

        // Simple visualizer bar animation
        let sum = 0;
        for (let i = 0; i < inputData.length; i += 64) sum += Math.abs(inputData[i]);
        const amp = Math.min(24, Math.max(4, Math.round(sum * 4)));
        bars.forEach((b, idx) => {{
          b.style.height = `${{Math.max(4, amp + (idx % 3) * 3)}}px`;
        }});

        // Downsample inputData to 16000 Hz
        const ratio = inSampleRate / 16000;
        const outLength = Math.round(inputData.length / ratio);
        const pcm16 = new Int16Array(outLength);

        for (let i = 0; i < outLength; i++) {{
          const srcIdx = Math.round(i * ratio);
          let s = Math.max(-1, Math.min(1, inputData[srcIdx] || 0));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }}

        // Send raw binary PCM16 chunk directly to WebSocket
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
      stateSubtitle.textContent = 'Establishing bidirectional WebSocket stream...';

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
        stateSubtitle.textContent = 'Live continuous conversation in progress — no need to click anything';
        appendBubble("Connected to Gemini Live API. Speak whenever you are ready!", "agent");

        try {{
          await startMicCapture();
        }} catch (err) {{
          console.error("Microphone capture failed:", err);
          appendBubble("Microphone permission denied: " + err.message, "agent");
          disconnectLive();
        }}
      }};

      ws.onmessage = (event) => {{
        if (event.data instanceof ArrayBuffer) {{
          // Incoming 24kHz PCM chunk from Gemini Live API!
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
            }} else if (msg.type === 'status') {{
              if (msg.state === 'tool_calling') {{
                stateTitle.textContent = `Executing: ${{msg.tool}}...`;
                stateSubtitle.textContent = 'Looking up Google Workspace live...';
              }}
            }}
          }} catch (err) {{
            console.warn("WS JSON parse error:", err);
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
      stateSubtitle.textContent = 'Native bidirectional streaming: continuously listens and talks back automatically';
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
    - Browser -> Gemini: Streams 16kHz 16-bit PCM chunks.
    - Gemini -> Browser: Streams 24kHz 16-bit PCM native audio chunks.
    - Handles tool execution and interruption natively.
    """
    await websocket.accept()
    logger.info("Client connected to /ws/live WebSocket.")

    # Initialize Google GenAI client with explicit quota project cowork-aset-6tnf0w
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
            parts=[types.Part(text=LIVE_SYSTEM_INSTRUCTION)]
        ),
        tools=LIVE_TOOLS
    )

    model_name = "gemini-live-2.5-flash-native-audio"

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            logger.info("Established upstream session with Gemini Live API (%s)", model_name)

            # Task 1: Browser -> Gemini (Microphone audio chunks)
            async def forward_browser_to_gemini():
                try:
                    chunk_counter = 0
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"]:
                            raw_pcm = msg["bytes"]
                            # Forward real-time audio chunk to Gemini Live API
                            await session.send_realtime_input(
                                audio=types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")
                            )
                            chunk_counter += 1
                            if chunk_counter % 50 == 0:
                                logger.info("Forwarded 50 audio chunks to Gemini Live...")
                        elif "text" in msg and msg["text"]:
                            txt = msg["text"]
                            await session.send_client_content(
                                turns=[types.Content(role="user", parts=[types.Part(text=txt)])],
                                turn_complete=True
                            )
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from audio input.")
                except Exception as e:
                    logger.error("Error in forward_browser_to_gemini: %s", e)

            # Task 2: Gemini -> Browser (Native 24kHz audio + tool execution)
            async def forward_gemini_to_browser():
                try:
                    async for response in session.receive():
                        # 1. Handle native voice audio chunks and transcriptions
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
                                        # Send raw 24kHz PCM chunk as binary to browser!
                                        await websocket.send_bytes(part.inline_data.data)

                        # 2. Handle Live Tool Calls
                        if response.tool_call is not None:
                            fcalls = response.tool_call.function_calls or []
                            function_responses = []
                            for fc in fcalls:
                                call_id = fc.id
                                call_name = fc.name
                                call_args = fc.args or {}
                                await websocket.send_text(json.dumps({
                                    "type": "status",
                                    "state": "tool_calling",
                                    "tool": call_name
                                }))
                                result = execute_tool_call(call_name, call_args)
                                function_responses.append(types.FunctionResponse(
                                    id=call_id,
                                    name=call_name,
                                    response=result
                                ))
                                # Show summary card in chat feed
                                if "schedule_summary" in result:
                                    await websocket.send_text(json.dumps({
                                        "type": "transcript",
                                        "role": "agent",
                                        "text": f"📅 **Checked Schedule**:\n{result['schedule_summary']}"
                                    }))
                                elif "event_link" in result:
                                    await websocket.send_text(json.dumps({
                                        "type": "transcript",
                                        "role": "agent",
                                        "text": f"🏢 **Room Booked!** [{result.get('room_name')}]({result.get('event_link')})"
                                    }))

                            if function_responses:
                                logger.info("Sending tool response back to Gemini Live API...")
                                await session.send_tool_response(function_responses=function_responses)

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
        "voice": "Aoede (Native Audio)"
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Gemini Multimodal Live API Server on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
