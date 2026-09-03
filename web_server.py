"""
Unified Web Interface and Google Chat Webhook Server for Agenica S.
Serves:
1. Executive Web Dashboard (GET /)
2. Interactive Web Chat API (POST /api/chat)
3. Google Chat Webhook Endpoint (POST / and POST /chat)
"""

import os
import sys
import json
import logging
import asyncio
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from agent.config import (
    AGENT_NAME,
    AGENT_EMAIL,
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
)
from agent.agent import _run_query_async
from agent.chat_service import process_chat_event
from agent.tools.room_booking_tools import reserve_daily_focus_rooms, find_daily_focus_chunks
from agent.tools.calendar_tools import get_current_datetime

logger = logging.getLogger("agenica.web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S Executive Assistant Portal", version="1.0.0")

HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{AGENT_NAME} — Executive Assistant Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #002B49;
      --accent: #1A73E8;
      --accent-hover: #1557b0;
      --bg: #F8F9FA;
      --card-bg: #FFFFFF;
      --text: #202124;
      --text-muted: #5F6368;
      --border: #DADCE0;
      --chip-bg: #E8F0FE;
      --chip-text: #1967D2;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    header {{
      background: var(--primary);
      color: white;
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }}
    .header-left {{ display: flex; align-items: center; gap: 14px; }}
    .avatar {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: #1A73E8;
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 20px;
    }}
    .header-titles h1 {{ font-size: 18px; font-weight: 500; }}
    .header-titles p {{ font-size: 12px; color: #BDC1C6; }}
    .header-status {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      background: rgba(255,255,255,0.1);
      padding: 6px 14px;
      border-radius: 20px;
    }}
    .status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #34A853; }}

    .main-container {{
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      padding: 16px 20px;
      overflow: hidden;
    }}

    .quick-chips {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 12px;
      white-space: nowrap;
    }}
    .chip {{
      background: var(--chip-bg);
      color: var(--chip-text);
      border: 1px solid rgba(26,115,232,0.2);
      padding: 7px 14px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .chip:hover {{ background: #D2E3FC; }}

    .chat-box {{
      flex: 1;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}

    .message {{ display: flex; gap: 12px; max-width: 85%; }}
    .message.user {{ align-self: flex-end; flex-direction: row-reverse; }}
    .message-content {{
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
    }}
    .message.user .message-content {{
      background: var(--accent);
      color: white;
      border-bottom-right-radius: 4px;
    }}
    .message.agent .message-content {{
      background: #F1F3F4;
      color: var(--text);
      border-bottom-left-radius: 4px;
    }}
    .message.agent .message-content a {{
      color: var(--accent);
      font-weight: 500;
      text-decoration: underline;
    }}
    .message.agent .message-content pre {{
      background: #E8EAED;
      padding: 8px 12px;
      border-radius: 6px;
      font-family: 'Roboto Mono', monospace;
      font-size: 12px;
      margin: 8px 0;
      overflow-x: auto;
    }}
    .message.agent .message-content h3 {{
      font-size: 15px;
      margin: 10px 0 6px 0;
      color: var(--primary);
    }}
    .message.agent .message-content ul {{
      margin-left: 20px;
      margin-top: 4px;
    }}

    .input-bar {{
      display: flex;
      gap: 10px;
      margin-top: 14px;
    }}
    .input-bar input {{
      flex: 1;
      padding: 14px 18px;
      border: 1px solid var(--border);
      border-radius: 28px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }}
    .input-bar input:focus {{ border-color: var(--accent); }}
    .input-bar button {{
      background: var(--accent);
      color: white;
      border: none;
      padding: 0 24px;
      border-radius: 28px;
      font-weight: 500;
      font-size: 14px;
      cursor: pointer;
      transition: background 0.2s;
    }}
    .input-bar button:hover {{ background: var(--accent-hover); }}
    .loading-indicator {{ display: none; font-size: 12px; color: var(--text-muted); font-style: italic; margin-top: 4px; }}
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <div class="avatar">AS</div>
      <div class="header-titles">
        <h1>{AGENT_NAME}</h1>
        <p>Executive Assistant to {PRINCIPAL_NAME} • {OFFICE_LOCATION}</p>
      </div>
    </div>
    <div class="header-status">
      <div class="status-dot"></div>
      <span>Gemini 3.7 Flash Active (SGT UTC+8)</span>
    </div>
  </header>

  <div class="main-container">
    <div class="quick-chips">
      <div class="chip" onclick="sendPrompt('I will be in the office tomorrow. Please book a phone or focus room on Level 29 in MBC2 Singapore for large chunks of the day.')">🏢 Reserve Level 29 Focus Room</div>
      <div class="chip" onclick="sendPrompt('I was added to an email thread with Dr. Lee from Flinders asking for 30 mins next Tuesday. Please find time for us on behalf of Abhi.')">📧 Thread: Find Time with Dr. Lee</div>
      <div class="chip" onclick="sendPrompt('Scan my inbox, perform a 4-tier triage scan, and summarize items requiring action.')">📬 4-Tier Inbox Triage</div>
      <div class="chip" onclick="sendPrompt('Summarize my calendar schedule for today and check if I have any meeting clashes.')">📅 Check Today\'s Schedule</div>
      <div class="chip" onclick="sendPrompt('Prepare an executive briefing document in Google Docs for an upcoming public sector enterprise architecture review.')">📄 Create Briefing Memo</div>
    </div>

    <div class="chat-box" id="chatBox">
      <div class="message agent">
        <div class="avatar" style="width:32px; height:32px; font-size:14px;">AS</div>
        <div class="message-content">
          Good day, Abhi. I am <b>{AGENT_NAME}</b>, your executive assistant.<br><br>
          I am connected to your workspace to manage scheduling on your behalf, book focus and phone rooms on <b>Level {OFFICE_PRIMARY_FLOOR} in MBC2 Singapore</b>, handle email thread delegations, and prepare executive briefings.<br><br>
          <i>How may I assist you today?</i>
        </div>
      </div>
    </div>

    <div class="loading-indicator" id="loading">Agenica S is analyzing your schedule and drafting response...</div>

    <form class="input-bar" id="chatForm" onsubmit="handleSend(event)">
      <input type="text" id="userInput" placeholder="Ask Agenica S to book a room, find time on an email thread, or triage inbox..." autocomplete="off">
      <button type="submit">Send</button>
    </form>
  </div>

  <script>
    const chatBox = document.getElementById('chatBox');
    const userInput = document.getElementById('userInput');
    const loading = document.getElementById('loading');

    function appendMessage(sender, text) {{
      const msgDiv = document.createElement('div');
      msgDiv.className = `message ${{sender}}`;
      
      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.style.width = '32px';
      avatar.style.height = '32px';
      avatar.style.fontSize = '14px';
      avatar.textContent = sender === 'user' ? 'A' : 'AS';

      const content = document.createElement('div');
      content.className = 'message-content';
      
      // Basic markdown parsing
      let formatted = text
        .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
        .replace(/\\*(.*?)\\*/g, '<i>$1</i>')
        .replace(/\\[(.*?)\\]\\((.*?)\\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\\n/g, '<br>');
      content.innerHTML = formatted;

      msgDiv.appendChild(avatar);
      msgDiv.appendChild(content);
      chatBox.appendChild(msgDiv);
      chatBox.scrollTop = chatBox.scrollHeight;
    }}

    async function sendPrompt(text) {{
      appendMessage('user', text);
      loading.style.display = 'block';

      try {{
        const res = await fetch('/api/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ message: text }})
        }});
        if (!res.ok) {{
          const errText = await res.text();
          throw new Error(`Server returned ${{res.status}}: ${{errText.slice(0, 120)}}`);
        }}
        const data = await res.json();
        appendMessage('agent', data.reply);
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
      sendPrompt(text);
    }}
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serve the interactive Executive Assistant web dashboard."""
    return HTMLResponse(content=HTML_TEMPLATE)


@app.post("/api/chat")
async def handle_web_chat(request: Request):
    """API endpoint for web dashboard chat."""
    try:
        data = await request.json()
        msg = data.get("message", "").strip()
        if not msg:
            return JSONResponse({"reply": "Please specify a request for Agenica S."})

        # Asynchronously run query to avoid blocking or event loop conflicts
        reply = await _run_query_async(msg, user_id="aset")
        return JSONResponse({"reply": reply})
    except Exception as e:
        logger.error("Error handling web chat query: %s", e, exc_info=True)
        return JSONResponse({"reply": f"I encountered an issue processing your request: {e}"})


@app.post("/")
@app.post("/chat")
async def handle_chat_webhook(request: Request):
    """
    Google Chat API Webhook Endpoint.
    Receives events from Google Chat (DMs, Space mentions, Card button clicks)
    and replies formatted according to Google Chat API specs.
    """
    try:
        body_bytes = await request.body()
        event = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        logger.info("Received Google Chat Webhook Event: %s", event.get("type"))
        reply_payload = await process_chat_event(event)
        return JSONResponse(reply_payload)
    except Exception as e:
        logger.error("Error handling chat webhook: %s", e, exc_info=True)
        return JSONResponse({"text": f"Error processing chat event: {e}"})


@app.get("/healthz")
def healthz():
    return {"status": "ok", "agent": AGENT_NAME, "principal": PRINCIPAL_NAME}


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Web & Google Chat Server on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
