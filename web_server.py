"""
Agenica S — Production Executive Assistant Web Portal with Natural Voice Interaction.

Features:
1. Powered by Gemini 3.7 Flash in Vertex AI (global routing).
2. Natural Voice Interaction:
   - Voice Recognition (Speech-to-Text) with Australian English (en-AU).
   - Voice Synthesis (Text-to-Speech) using Australian English Female voice.
   - Live speech transcription and audio wave animations.
3. Full integration with Abhi Sethi's Google Workspace:
   - Direct calendar creation on primary calendar (aset@google.com).
   - Real-time room availability verification for Google Singapore MBC2 Level 29.
   - 4-Tier Gmail triage, thread delegation, and executive briefing generation.
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
    AGENT_EMAIL,
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
    BUILDING_CODE,
    DEFAULT_TIMEZONE
)
from agent.agent import _run_query_async

logger = logging.getLogger("agenica.web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S — Executive Assistant Portal", version="2.0.0")


def clean_text_for_speech(text: str) -> str:
    """Clean markdown, links, bullet points, and code blocks for smooth natural speech synthesis."""
    # Remove code blocks
    s = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Convert markdown links [Label](url) -> Label
    s = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", s)
    # Remove bold, italics, headers
    s = re.sub(r"[*#_`>~]", "", s)
    # Replace bullet dashes/asterisks
    s = re.sub(r"^\s*[-*•]\s+", "", s, flags=re.MULTILINE)
    # Collapse whitespace
    s = re.sub(r"\n+", ". ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:800]


HTML_PORTAL = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{AGENT_NAME} — Executive Assistant Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0A0F1D;
      --card-bg: #131B2E;
      --border: #1E293B;
      --primary: #38BDF8;
      --primary-hover: #0EA5E9;
      --text: #F1F5F9;
      --text-muted: #94A3B8;
      --bubble-user: #0369A1;
      --bubble-agent: #1E293B;
      --accent-green: #10B981;
      --accent-pulse: rgba(56, 189, 248, 0.35);
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
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 14px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .avatar {{
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: linear-gradient(135deg, #0284C7, #38BDF8);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      color: white;
      box-shadow: 0 0 16px var(--accent-pulse);
    }}
    .titles h1 {{
      font-size: 17px;
      font-weight: 700;
      color: #FFFFFF;
      letter-spacing: -0.2px;
    }}
    .titles p {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }}
    .header-right {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .badge {{
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
      color: #34D399;
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      background: #10B981;
      border-radius: 50%;
      box-shadow: 0 0 10px #10B981;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.95); opacity: 0.8; }}
      50% {{ transform: scale(1.15); opacity: 1; }}
      100% {{ transform: scale(0.95); opacity: 0.8; }}
    }}

    .voice-settings {{
      display: flex;
      align-items: center;
      gap: 8px;
      background: #1E293B;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      color: var(--text-muted);
    }}
    .voice-toggle {{
      background: none;
      border: none;
      color: var(--primary);
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
    }}

    .main-container {{
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 1050px;
      width: 100%;
      margin: 0 auto;
      padding: 20px 24px;
      overflow: hidden;
    }}

    .quick-chips {{
      display: flex;
      gap: 10px;
      overflow-x: auto;
      padding-bottom: 12px;
      margin-bottom: 10px;
      scrollbar-width: none;
    }}
    .quick-chips::-webkit-scrollbar {{ display: none; }}
    .chip {{
      white-space: nowrap;
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: #E2E8F0;
      padding: 9px 16px;
      border-radius: 20px;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .chip:hover {{
      border-color: var(--primary);
      background: rgba(56, 189, 248, 0.1);
      transform: translateY(-1px);
    }}

    .chat-box {{
      flex: 1;
      overflow-y: auto;
      padding-right: 8px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .chat-box::-webkit-scrollbar {{
      width: 6px;
    }}
    .chat-box::-webkit-scrollbar-thumb {{
      background: var(--border);
      border-radius: 3px;
    }}

    .message {{
      display: flex;
      gap: 14px;
      max-width: 82%;
    }}
    .message.user {{
      align-self: flex-end;
      flex-direction: row-reverse;
    }}
    .message.agent {{
      align-self: flex-start;
    }}
    .message-content {{
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
    }}
    .message.user .message-content {{
      background: var(--bubble-user);
      color: white;
      border-bottom-right-radius: 4px;
    }}
    .message.agent .message-content {{
      background: var(--bubble-agent);
      border: 1px solid var(--border);
      color: #F8FAFC;
      border-bottom-left-radius: 4px;
    }}
    .message.agent .message-content a {{
      color: #38BDF8;
      font-weight: 500;
      text-decoration: underline;
    }}
    .message.agent .message-content pre {{
      background: #0B1120;
      padding: 10px 14px;
      border-radius: 8px;
      font-family: 'Roboto Mono', monospace;
      font-size: 12px;
      margin: 10px 0;
      overflow-x: auto;
      border: 1px solid var(--border);
    }}
    .message.agent .message-content h3 {{
      font-size: 15px;
      margin: 12px 0 6px 0;
      color: #38BDF8;
    }}
    .message.agent .message-content ul {{
      margin-left: 20px;
      margin-top: 6px;
    }}
    .speak-btn {{
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 14px;
      margin-top: 6px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: color 0.2s;
    }}
    .speak-btn:hover {{ color: var(--primary); }}

    .voice-visualizer {{
      display: none;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 10px;
      margin-top: 8px;
      background: rgba(56, 189, 248, 0.08);
      border-radius: 12px;
      border: 1px dashed var(--primary);
    }}
    .wave-bar {{
      width: 4px;
      height: 14px;
      background: var(--primary);
      border-radius: 2px;
      animation: wave 1s ease-in-out infinite;
    }}
    .wave-bar:nth-child(2) {{ animation-delay: 0.15s; }}
    .wave-bar:nth-child(3) {{ animation-delay: 0.3s; }}
    .wave-bar:nth-child(4) {{ animation-delay: 0.45s; }}
    .wave-bar:nth-child(5) {{ animation-delay: 0.6s; }}
    @keyframes wave {{
      0%, 100% {{ height: 6px; }}
      50% {{ height: 24px; }}
    }}

    .input-container {{
      margin-top: 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .input-bar {{
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 32px;
      padding: 6px 8px 6px 18px;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .input-bar:focus-within {{
      border-color: var(--primary);
      box-shadow: 0 0 14px var(--accent-pulse);
    }}
    .input-bar input {{
      flex: 1;
      background: transparent;
      border: none;
      color: white;
      font-size: 14px;
      outline: none;
    }}
    .mic-btn {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: #1E293B;
      border: 1px solid var(--border);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 18px;
      transition: all 0.2s;
    }}
    .mic-btn:hover {{
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--primary);
      transform: scale(1.05);
    }}
    .mic-btn.recording {{
      background: #EF4444;
      color: white;
      border-color: #DC2626;
      animation: micPulse 1.2s infinite;
    }}
    @keyframes micPulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }}
      70% {{ box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
    }}
    .send-btn {{
      background: var(--primary);
      color: #0A0F1D;
      border: none;
      padding: 0 20px;
      height: 42px;
      border-radius: 24px;
      font-weight: 600;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .send-btn:hover {{
      background: var(--primary-hover);
      transform: scale(1.02);
    }}
    .loading-text {{
      display: none;
      font-size: 12px;
      color: var(--primary);
      margin-left: 14px;
      font-style: italic;
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <div class="avatar">AS</div>
      <div class="titles">
        <h1>{AGENT_NAME}</h1>
        <p>Executive Assistant to {PRINCIPAL_NAME} • {OFFICE_LOCATION}</p>
      </div>
    </div>
    <div class="header-right">
      <div class="voice-settings">
        <span>🗣️ Voice: <b id="voiceNameLabel">Australian English (Female)</b></span>
        <button class="voice-toggle" id="audioToggleBtn" onclick="toggleAudio()" title="Mute/Unmute Speech Output">🔊</button>
      </div>
      <div class="badge">
        <div class="status-dot"></div>
        <span>Gemini 3.7 Flash Active (SGT UTC+8)</span>
      </div>
    </div>
  </header>

  <div class="main-container">
    <div class="quick-chips">
      <div class="chip" onclick="sendPrompt('I will be in the office tomorrow. Please verify availability and book a focus or phone room on Level 29 in MBC2 Singapore for large chunks of the day.')">🏢 Reserve Level 29 Focus Room</div>
      <div class="chip" onclick="sendPrompt('I was added to an email thread with Dr. Lee from Flinders asking for 30 mins next Tuesday. Please find a time for us on behalf of Abhi.')">📧 Thread: Find Time with Dr. Lee</div>
      <div class="chip" onclick="sendPrompt('Scan my inbox, perform a 4-tier triage scan, and summarize items requiring action.')">📬 4-Tier Inbox Triage</div>
      <div class="chip" onclick="sendPrompt('Summarize my calendar schedule for today and check if I have any meeting clashes.')">📅 Check Today\'s Schedule</div>
      <div class="chip" onclick="sendPrompt('Prepare an executive briefing document in Google Docs for an upcoming public sector enterprise architecture review.')">📄 Create Briefing Memo</div>
    </div>

    <div class="chat-box" id="chatBox">
      <div class="message agent">
        <div class="avatar" style="width:34px; height:34px; font-size:13px;">AS</div>
        <div class="message-content">
          Good day, Abhi. I am <b>{AGENT_NAME}</b>, your executive assistant.<br><br>
          I am connected to your Google Workspace with direct calendar write access, real-time room availability verification for <b>Level {OFFICE_PRIMARY_FLOOR} in MBC2 Singapore</b>, email thread delegation, and briefing document authoring.<br><br>
          <i>You can speak directly using the microphone button below or type your request.</i>
        </div>
      </div>
    </div>

    <div class="voice-visualizer" id="visualizer">
      <div class="wave-bar"></div>
      <div class="wave-bar"></div>
      <div class="wave-bar"></div>
      <div class="wave-bar"></div>
      <div class="wave-bar"></div>
      <span style="font-size:13px; color:var(--primary); margin-left:8px;" id="liveTranscript">Listening in Australian English...</span>
    </div>

    <div class="input-container">
      <div class="loading-text" id="loading">Agenica S is analyzing your calendar and executing requests...</div>
      <form class="input-bar" id="chatForm" onsubmit="handleSend(event)">
        <input type="text" id="userInput" placeholder="Speak or type a request (e.g. 'Book a room tomorrow on level 29')..." autocomplete="off">
        <button type="button" class="mic-btn" id="micBtn" onclick="toggleVoiceRecording()" title="Click to speak in Australian English">🎙️</button>
        <button type="submit" class="send-btn">Send</button>
      </form>
    </div>
  </div>

  <script>
    const chatBox = document.getElementById('chatBox');
    const userInput = document.getElementById('userInput');
    const loading = document.getElementById('loading');
    const micBtn = document.getElementById('micBtn');
    const visualizer = document.getElementById('visualizer');
    const liveTranscript = document.getElementById('liveTranscript');
    const voiceNameLabel = document.getElementById('voiceNameLabel');
    const audioToggleBtn = document.getElementById('audioToggleBtn');

    let audioEnabled = true;
    let selectedVoice = null;
    let recognition = null;
    let isRecording = false;

    // --- Voice Synthesis Setup (Australian English Female) ---
    function initSpeechSynthesis() {{
      const synth = window.speechSynthesis;
      function setVoice() {{
        const voices = synth.getVoices();
        if (!voices || voices.length === 0) return;

        // 1. Look for Australian English female voice (e.g. Karen, Catherine, Lee, or en-AU female)
        let best = voices.find(v => v.lang.startsWith('en-AU') && (v.name.includes('Karen') || v.name.includes('Female') || v.name.includes('Catherine') || v.name.includes('Natural')));
        // 2. Fallback to any en-AU voice
        if (!best) best = voices.find(v => v.lang.startsWith('en-AU'));
        // 3. Fallback to British English female (e.g. en-GB)
        if (!best) best = voices.find(v => v.lang.startsWith('en-GB') && v.name.includes('Female'));
        // 4. Fallback to any English voice
        if (!best) best = voices.find(v => v.lang.startsWith('en'));

        selectedVoice = best || voices[0];
        if (selectedVoice) {{
          voiceNameLabel.textContent = `${{selectedVoice.name}} (${{selectedVoice.lang}})`;
        }}
      }}

      setVoice();
      if (synth.onvoiceschanged !== undefined) {{
        synth.onvoiceschanged = setVoice;
      }}
    }}

    function speakText(text) {{
      if (!audioEnabled || !('speechSynthesis' in window)) return;
      window.speechSynthesis.cancel(); // Stop any previous utterance

      const utterance = new SpeechSynthesisUtterance(text);
      if (selectedVoice) {{
        utterance.voice = selectedVoice;
        utterance.lang = selectedVoice.lang || 'en-AU';
      }} else {{
        utterance.lang = 'en-AU';
      }}
      utterance.pitch = 1.05; // Slightly higher pitch for crisp executive clarity
      utterance.rate = 1.02;  // Natural conversational tempo
      window.speechSynthesis.speak(utterance);
    }}

    function toggleAudio() {{
      audioEnabled = !audioEnabled;
      audioToggleBtn.textContent = audioEnabled ? '🔊' : '🔇';
      audioToggleBtn.title = audioEnabled ? 'Audio Output ON' : 'Audio Output Muted';
      if (!audioEnabled) window.speechSynthesis.cancel();
    }}

    // --- Voice Recognition Setup (Speech-to-Text en-AU) ---
    function initSpeechRecognition() {{
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {{
        micBtn.style.display = 'none';
        return;
      }}

      recognition = new SpeechRecognition();
      recognition.lang = 'en-AU'; // Australian English
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {{
        isRecording = true;
        micBtn.classList.add('recording');
        visualizer.style.display = 'flex';
        liveTranscript.textContent = 'Listening (Australian English)...';
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
        userInput.value = final || interim;
        liveTranscript.textContent = final || interim || 'Listening...';
        if (final) {{
          stopVoiceRecording();
          sendPrompt(final.trim(), true);
        }}
      }};

      recognition.onerror = (e) => {{
        console.warn('Speech recognition error:', e.error);
        stopVoiceRecording();
      }};

      recognition.onend = () => {{
        stopVoiceRecording();
      }};
    }}

    function toggleVoiceRecording() {{
      if (!recognition) return;
      if (isRecording) {{
        recognition.stop();
        stopVoiceRecording();
      }} else {{
        try {{
          recognition.start();
        }} catch (err) {{
          console.error(err);
        }}
      }}
    }}

    function stopVoiceRecording() {{
      isRecording = false;
      micBtn.classList.remove('recording');
      visualizer.style.display = 'none';
    }}

    // --- Chat Flow & Rendering ---
    function appendMessage(sender, text, spokenText = '') {{
      const msgDiv = document.createElement('div');
      msgDiv.className = `message ${{sender}}`;

      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.style.width = '34px';
      avatar.style.height = '34px';
      avatar.style.fontSize = '13px';
      avatar.textContent = sender === 'user' ? 'A' : 'AS';

      const content = document.createElement('div');
      content.className = 'message-content';

      // Markdown formatting
      let formatted = text
        .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
        .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
        .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\\n/g, '<br>');
      content.innerHTML = formatted;

      if (sender === 'agent' && spokenText) {{
        const spkBtn = document.createElement('button');
        spkBtn.className = 'speak-btn';
        spkBtn.innerHTML = '🔊 <span>Listen</span>';
        spkBtn.onclick = () => speakText(spokenText);
        content.appendChild(document.createElement('br'));
        content.appendChild(spkBtn);
      }}

      msgDiv.appendChild(avatar);
      msgDiv.appendChild(content);
      chatBox.appendChild(msgDiv);
      chatBox.scrollTop = chatBox.scrollHeight;
    }}

    async function sendPrompt(text, spokeQuery = false) {{
      if (!text) return;
      appendMessage('user', text);
      loading.style.display = 'block';

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ message: text }})
        }});
        if (!res.ok) {{
          const err = await res.text();
          throw new Error(`Server returned ${{res.status}}: ${{err.slice(0, 100)}}`);
        }}
        const data = await res.json();
        appendMessage('agent', data.reply, data.spoken_text);
        
        // Auto-speak response if query was spoken or audio is active
        if (spokeQuery || audioEnabled) {{
          speakText(data.spoken_text || data.reply);
        }}
      }} catch (err) {{
        appendMessage('agent', 'Error processing request: ' + err.message);
      }} finally {{
        loading.style.display = 'none';
      }}
    }}

    function handleSend(e) {{
      e.preventDefault();
      const text = userInput.value.trim();
      if (!text) return;
      userInput.value = '';
      sendPrompt(text, false);
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      initSpeechSynthesis();
      initSpeechRecognition();
    }});
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_portal(request: Request):
    """Serve the interactive Voice-Enabled Executive Assistant Web Portal."""
    return HTMLResponse(content=HTML_PORTAL)


@app.post("/api/chat")
async def handle_api_chat(request: Request):
    """Execute query with Gemini 3.7 Flash and return reply with speech-optimized text."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        if not message:
            return JSONResponse({"reply": "Please state your request for Agenica S.", "spoken_text": "Please state your request."})

        # Run query through ADK runner with Gemini 3.7 Flash
        reply = await _run_query_async(message, user_id="aset", session_id="voice-web-session")
        spoken_text = clean_text_for_speech(reply)

        return JSONResponse({
            "reply": reply,
            "spoken_text": spoken_text
        })
    except Exception as e:
        logger.error("Error executing web chat query: %s", e, exc_info=True)
        return JSONResponse({
            "reply": f"I encountered an error executing your request: {e}",
            "spoken_text": f"I encountered an error executing your request: {e}"
        })


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "agent": AGENT_NAME,
        "principal": PRINCIPAL_NAME,
        "model": "gemini-3.7-flash (global Vertex AI)"
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Voice Portal on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
