"""
Agenica S — Live Conversational Executive Assistant Web Portal.

Features:
1. Continuous Hands-Free Conversation:
   - Always listening once activated (hands-free back-and-forth dialogue).
   - Natural, casual, friendly persona (speaks like a real EA in Australian English).
   - Audio barge-in: starts listening immediately when you speak.
   - Dual output: casual spoken response for voice + rich visual cards on screen.
2. Powered by Gemini 3.7 Flash on global Vertex AI.
3. Full integration with Abhi Sethi's Google Workspace (Calendar, Level 29 MBC2 rooms, Gmail).
"""

import os
import re
import json
import logging
import asyncio
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Configure environment for Gemini 3.7 Flash on global Vertex AI
os.environ["GOOGLE_CLOUD_PROJECT"] = "cowork-aset-6tnf0w"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["ADK_MODEL"] = "gemini-3.7-flash"
os.environ["GOOGLE_GENAI_MODEL"] = "gemini-3.7-flash"

from agent.config import (
    AGENT_NAME,
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
)
from agent.agent import _run_query_async

logger = logging.getLogger("agenica.web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S — Live Conversational Assistant", version="2.5.0")


def generate_conversational_speech(text: str) -> str:
    """Extract a warm, casual, human spoken sentence for voice output."""
    import re
    # Remove code blocks and markdown links
    s = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    s = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", s)
    # Remove markdown headers and formatting
    s = re.sub(r"[*#_`>~]", "", s)
    # Remove common emoji unicode blocks
    s = re.sub(r"[\U00010000-\U0010ffff]", "", s)
    
    clean_lines = []
    for line in s.splitlines():
        line = line.strip()
        if not line or line.startswith(("-", "•", "1.", "2.", "3.", "4.", "Date:", "Time:", "Status:", "Room:", "Event:", "Current Time:")):
            continue
        if len(line) > 12 and not line.startswith("http"):
            clean_lines.append(line)
            
    if clean_lines:
        res = clean_lines[0]
        if len(clean_lines) > 1 and len(res) < 120:
            res += " " + clean_lines[1]
    else:
        res = "All set, Abhi! Let me know if you need anything else."
    res = re.sub(r"\s+", " ", res).strip()
    return res[:250]


HTML_LIVE_PORTAL = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{AGENT_NAME} — Live Executive Voice Assistant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #070B14;
      --card: #0F172A;
      --border: #1E293B;
      --accent: #38BDF8;
      --accent-glow: rgba(56, 189, 248, 0.4);
      --text: #F8FAFC;
      --text-muted: #94A3B8;
      --agent-bubble: #1E293B;
      --user-bubble: #0284C7;
      --active-green: #10B981;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Google Sans', -apple-system, sans-serif;
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

    .header-controls {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .live-status-pill {{
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
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      padding: 20px;
      overflow: hidden;
    }}

    /* Voice Center Orb */
    .voice-stage {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      margin-bottom: 18px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
      position: relative;
    }}
    .orb-container {{
      width: 90px;
      height: 90px;
      border-radius: 50%;
      background: radial-gradient(circle, #38BDF8 0%, #0369A1 70%, #070B14 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 0 25px var(--accent-glow);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .orb-container:hover {{
      transform: scale(1.06);
      box-shadow: 0 0 35px rgba(56, 189, 248, 0.6);
    }}
    .orb-container.listening {{
      animation: orbListen 1.5s infinite alternate;
      background: radial-gradient(circle, #10B981 0%, #047857 70%, #070B14 100%);
      box-shadow: 0 0 40px rgba(16, 185, 129, 0.8);
    }}
    .orb-container.speaking {{
      animation: orbSpeak 0.8s infinite alternate;
      background: radial-gradient(circle, #F59E0B 0%, #B45309 70%, #070B14 100%);
      box-shadow: 0 0 40px rgba(245, 158, 11, 0.8);
    }}
    @keyframes orbListen {{
      from {{ transform: scale(1); }}
      to {{ transform: scale(1.12); }}
    }}
    @keyframes orbSpeak {{
      from {{ transform: scale(1); }}
      to {{ transform: scale(1.18); }}
    }}

    .voice-state-label {{
      margin-top: 14px;
      font-size: 15px;
      font-weight: 600;
      color: #F8FAFC;
    }}
    .voice-sub-label {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
    }}
    .live-transcript {{
      margin-top: 10px;
      font-size: 13px;
      color: var(--accent);
      font-style: italic;
      min-height: 20px;
      text-align: center;
    }}

    /* Chat Stream */
    .chat-stream {{
      flex: 1;
      overflow-y: auto;
      padding-right: 6px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .chat-stream::-webkit-scrollbar {{ width: 5px; }}
    .chat-stream::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

    .msg {{
      display: flex;
      gap: 12px;
      max-width: 85%;
    }}
    .msg.user {{
      align-self: flex-end;
      flex-direction: row-reverse;
    }}
    .msg.agent {{
      align-self: flex-start;
    }}
    .msg-content {{
      padding: 12px 18px;
      border-radius: 18px;
      font-size: 14px;
      line-height: 1.55;
    }}
    .msg.user .msg-content {{
      background: var(--user-bubble);
      color: white;
      border-bottom-right-radius: 4px;
    }}
    .msg.agent .msg-content {{
      background: var(--agent-bubble);
      border: 1px solid var(--border);
      color: var(--text);
      border-bottom-left-radius: 4px;
    }}
    .msg.agent .msg-content a {{
      color: var(--accent);
      text-decoration: underline;
    }}
    .msg.agent .msg-content pre {{
      background: #070B14;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 12px;
      margin: 8px 0;
      border: 1px solid var(--border);
    }}

    /* Controls Bar */
    .bottom-bar {{
      margin-top: 12px;
      display: flex;
      gap: 10px;
    }}
    .bottom-bar input {{
      flex: 1;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 28px;
      padding: 12px 20px;
      color: white;
      font-size: 14px;
      outline: none;
    }}
    .bottom-bar input:focus {{
      border-color: var(--accent);
    }}
    .send-btn {{
      background: var(--accent);
      color: #070B14;
      border: none;
      padding: 0 24px;
      border-radius: 28px;
      font-weight: 600;
      font-size: 14px;
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="avatar">AS</div>
      <div class="brand-titles">
        <h1>{AGENT_NAME}</h1>
        <p>Conversational Executive Assistant to {PRINCIPAL_NAME} • Australian English</p>
      </div>
    </div>
    <div class="header-controls">
      <div class="live-status-pill">
        <div class="pulse-dot"></div>
        <span>Live Audio Ready • Gemini 3.7 Flash</span>
      </div>
    </div>
  </header>

  <div class="portal-body">
    <!-- Center Live Voice Stage -->
    <div class="voice-stage">
      <div class="orb-container" id="voiceOrb" onclick="toggleLiveVoice()">
        <span style="font-size:28px;" id="orbIcon">🎙️</span>
      </div>
      <div class="voice-state-label" id="voiceStateLabel">Tap Orb to Start Hands-Free Conversation</div>
      <div class="voice-sub-label" id="voiceSubLabel">Continuous conversational listening with Australian English female voice</div>
      <div class="live-transcript" id="liveTranscript"></div>
    </div>

    <!-- Live Action & Message Stream -->
    <div class="chat-stream" id="chatStream">
      <div class="msg agent">
        <div class="avatar" style="width:32px; height:32px; font-size:12px;">AS</div>
        <div class="msg-content">
          Hey Abhi! I'm <b>{AGENT_NAME}</b>. Tap the microphone orb above and talk to me naturally—I'm listening constantly so we can have a real conversation, or you can type below anytime.
        </div>
      </div>
    </div>

    <!-- Bottom Input Backup -->
    <form class="bottom-bar" onsubmit="handleTextSubmit(event)">
      <input type="text" id="textInput" placeholder="Or type a message here..." autocomplete="off">
      <button type="submit" class="send-btn">Send</button>
    </form>
  </div>

  <script>
    const voiceOrb = document.getElementById('voiceOrb');
    const orbIcon = document.getElementById('orbIcon');
    const voiceStateLabel = document.getElementById('voiceStateLabel');
    const voiceSubLabel = document.getElementById('voiceSubLabel');
    const liveTranscript = document.getElementById('liveTranscript');
    const chatStream = document.getElementById('chatStream');
    const textInput = document.getElementById('textInput');

    let isLiveActive = false;
    let recognition = null;
    let auFemaleVoice = null;
    let isSpeaking = false;

    // --- Voice Synthesis Setup (Australian English Female) ---
    function initSpeech() {{
      const synth = window.speechSynthesis;
      function pickVoice() {{
        const voices = synth.getVoices();
        if (!voices || voices.length === 0) return;

        // Find Australian English female voice
        let v = voices.find(x => x.lang.startsWith('en-AU') && (x.name.includes('Karen') || x.name.includes('Female') || x.name.includes('Catherine') || x.name.includes('Google') || x.name.includes('Natural')));
        if (!v) v = voices.find(x => x.lang.startsWith('en-AU'));
        if (!v) v = voices.find(x => x.lang.startsWith('en-GB') && x.name.includes('Female'));
        if (!v) v = voices.find(x => x.lang.startsWith('en'));

        auFemaleVoice = v || voices[0];
      }}

      pickVoice();
      if (synth.onvoiceschanged !== undefined) {{
        synth.onvoiceschanged = pickVoice;
      }}
    }}

    function speakCasualReply(text, onComplete = null) {{
      if (!('speechSynthesis' in window)) return;
      window.speechSynthesis.cancel();

      const utter = new SpeechSynthesisUtterance(text);
      if (auFemaleVoice) {{
        utter.voice = auFemaleVoice;
        utter.lang = auFemaleVoice.lang || 'en-AU';
      }} else {{
        utter.lang = 'en-AU';
      }}
      utter.pitch = 1.08;
      utter.rate = 1.05;

      utter.onstart = () => {{
        isSpeaking = true;
        voiceOrb.className = 'orb-container speaking';
        orbIcon.textContent = '🔊';
        voiceStateLabel.textContent = 'Agenica S is speaking...';
        voiceSubLabel.textContent = text;
      }};

      utter.onend = () => {{
        isSpeaking = false;
        if (isLiveActive) {{
          // Immediately resume hands-free listening!
          startListening();
        }} else {{
          resetOrbState();
        }}
        if (onComplete) onComplete();
      }};

      utter.onerror = () => {{
        isSpeaking = false;
        if (isLiveActive) startListening();
      }};

      window.speechSynthesis.speak(utter);
    }}

    // --- Continuous Hands-Free Speech Recognition ---
    function initRecognition() {{
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {{
        voiceStateLabel.textContent = 'Speech recognition not supported in this browser.';
        return;
      }}

      recognition = new SpeechRec();
      recognition.lang = 'en-AU';
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {{
        voiceOrb.className = 'orb-container listening';
        orbIcon.textContent = '🟢';
        voiceStateLabel.textContent = 'I am listening... (speak freely)';
        voiceSubLabel.textContent = 'Speak naturally in Australian English';
        liveTranscript.textContent = '';
      }};

      recognition.onresult = (event) => {{
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {{
          if (event.results[i].isFinal) {{
            final += event.results[i][0].transcript;
          }} else {{
            interim += event.results[i][0].transcript;
          }}
        }}
        liveTranscript.textContent = final || interim;
        if (final) {{
          recognition.stop();
          processLiveInput(final.trim());
        }}
      }};

      recognition.onerror = (e) => {{
        console.warn('Speech rec error:', e.error);
        if (isLiveActive && !isSpeaking) {{
          setTimeout(() => {{
            if (isLiveActive && !isSpeaking) startListening();
          }}, 800);
        }}
      }};

      recognition.onend = () => {{
        if (isLiveActive && !isSpeaking) {{
          // Re-arm automatically for continuous listening loop
          startListening();
        }}
      }};
    }}

    function startListening() {{
      if (!recognition || isSpeaking) return;
      try {{
        recognition.start();
      }} catch (err) {{
        // Already active
      }}
    }}

    function toggleLiveVoice() {{
      if (isLiveActive) {{
        // Turn off live mode
        isLiveActive = false;
        if (recognition) recognition.stop();
        window.speechSynthesis.cancel();
        resetOrbState();
      }} else {{
        // Turn on continuous live mode
        isLiveActive = true;
        window.speechSynthesis.cancel();
        startListening();
      }}
    }}

    function resetOrbState() {{
      voiceOrb.className = 'orb-container';
      orbIcon.textContent = '🎙️';
      voiceStateLabel.textContent = 'Tap Orb to Start Hands-Free Conversation';
      voiceSubLabel.textContent = 'Continuous conversational listening with Australian English female voice';
      liveTranscript.textContent = '';
    }}

    // --- Message Stream & Processing ---
    function appendMsg(sender, text) {{
      const d = document.createElement('div');
      d.className = `msg ${{sender}}`;

      const av = document.createElement('div');
      av.className = 'avatar';
      av.style.width = '32px';
      av.style.height = '32px';
      av.style.fontSize = '12px';
      av.textContent = sender === 'user' ? 'A' : 'AS';

      const c = document.createElement('div');
      c.className = 'msg-content';
      c.innerHTML = text
        .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
        .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
        .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\\n/g, '<br>');

      d.appendChild(av);
      d.appendChild(c);
      chatStream.appendChild(d);
      chatStream.scrollTop = chatStream.scrollHeight;
    }}

    async function processLiveInput(text) {{
      if (!text) return;
      appendMsg('user', text);
      voiceStateLabel.textContent = 'Thinking...';
      voiceOrb.className = 'orb-container';
      orbIcon.textContent = '⚡';

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ message: text }})
        }});
        const data = await res.json();
        
        // Show rich details in chat
        appendMsg('agent', data.reply);

        // Speak back ONLY the casual, friendly spoken sentence
        const speech = data.spoken_reply || "Done, Abhi!";
        speakCasualReply(speech);
      }} catch (e) {{
        appendMsg('agent', 'Sorry Abhi, I had a hiccup processing that: ' + e.message);
        if (isLiveActive) startListening();
      }}
    }}

    function handleTextSubmit(e) {{
      e.preventDefault();
      const val = textInput.value.trim();
      if (!val) return;
      textInput.value = '';
      processLiveInput(val);
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      initSpeech();
      initRecognition();
    }});
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_live_portal(request: Request):
    """Serve the Live Hands-Free Conversational Voice Portal."""
    return HTMLResponse(content=HTML_LIVE_PORTAL)


@app.post("/api/chat")
async def handle_conversational_chat(request: Request):
    """
    Process request with Gemini 3.7 Flash and return:
    1. reply: Detailed markdown / cards for visual chat.
    2. spoken_reply: Warm, casual 1-2 sentence spoken reply for the Australian EA voice.
    """
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        if not message:
            return JSONResponse({
                "reply": "Please let me know what you'd like me to do.",
                "spoken_reply": "I'm listening, Abhi. What can I do for you?"
            })

        # Run query through ADK runner with Gemini 3.7 Flash
        try:
            reply = await _run_query_async(message, user_id="aset", session_id="live-voice-session")
        except Exception as query_err:
            logger.warning("Primary 3.7 flash encountered preemption, falling back to 2.5-flash: %s", query_err)
            os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
            os.environ["ADK_MODEL"] = "gemini-2.5-flash"
            reply = await _run_query_async(message, user_id="aset", session_id="live-voice-session-fb")
        spoken_reply = generate_conversational_speech(reply)

        return JSONResponse({
            "reply": reply,
            "spoken_reply": spoken_reply
        })
    except Exception as e:
        logger.error("Error in conversational chat: %s", e, exc_info=True)
        return JSONResponse({
            "reply": f"Encountered an issue: {e}",
            "spoken_reply": "Sorry Abhi, I hit a slight snag with that request."
        })


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "agent": AGENT_NAME,
        "principal": PRINCIPAL_NAME,
        "mode": "live_conversational_voice"
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Live Conversational Portal on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
