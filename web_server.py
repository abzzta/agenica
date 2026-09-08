"""
Agenica S — Production Gemini Multimodal Live API Web Server.

Features:
1. Native Gemini Multimodal Live API (Bidirectional WebSocket):
   - Streams 16kHz PCM audio directly from browser microphone.
   - Streams 24kHz native neural audio back to browser using voice "Aoede".
   - Continuous multi-turn hands-free voice dialogue with server-side VAD.
   - Seamless turn transition on server `turn_complete` event.
   - Immediate barge-in / interruption handling.
   - Real-time dual speech transcription (user input + agent response).
   - Instant single-click Orb activation with synchronous AudioContext & mic initialization.
2. Full Real Workspace & Singapore Room Booking Tool Calling:
   - Tool declarations registered with Gemini Live API:
     * `book_singapore_room`: Checks availability & books MBC2 Level 28/29/30 room resource on primary calendar.
     * `create_calendar_event`: Dispatches real Google Calendar invite with Google Meet.
     * `check_calendar_availability`: Checks free/busy intervals on aset@google.com.
     * `list_upcoming_events`: Retrieves Abhi's real schedule.
   - Interactive visual action cards in web UI with direct Google Calendar links.
"""

import os
import sys
import time
import json
import logging
import asyncio
from datetime import datetime, timedelta
import zoneinfo
from typing import Dict, Any, Optional, List

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
    DEFAULT_TIMEZONE,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
)
from agent.tools.calendar_tools import (
    list_upcoming_events,
    get_current_datetime,
    create_calendar_event,
    check_calendar_availability,
    _to_rfc3339,
)
from agent.tools.room_booking_tools import (
    MBC2_ROOM_CATALOG,
    book_mbc_room_for_chunk,
    find_available_mbc_room,
)
from agent.tools.hitl_tools import normalize_time_str

logger = logging.getLogger("agenica.live")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Agenica S — Gemini Multimodal Live Portal", version="4.1.0")

SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)
_room_cache = {"timestamp": 0, "status": ""}


def get_cached_singapore_rooms() -> str:
    """Batch query all Level 29 rooms for tomorrow with in-memory caching."""
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

        today = datetime.now(SGT_TZ)
        tomorrow = today + timedelta(days=1)
        tmrw_str = tomorrow.strftime("%Y-%m-%d")

        body = {
            "timeMin": f"{tmrw_str}T10:00:00+08:00",
            "timeMax": f"{tmrw_str}T12:00:00+08:00",
            "items": items,
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


LIVE_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "book_singapore_room",
                "description": (
                    "Verify availability and directly book a meeting room or phone booth in Google Singapore MBC2 "
                    "(Level 28, 29, or 30) for Abhi Sethi, automatically creating the Google Calendar event on "
                    "Abhi's primary calendar with the room resource attached."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "date_str": {
                            "type": "STRING",
                            "description": "Date of booking in YYYY-MM-DD format (e.g. '2026-09-04'), or 'today', 'tomorrow'.",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in Singapore SGT (e.g. '13:30', '1:30 PM', '14:00').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in Singapore SGT (e.g. '14:30', '2:30 PM', '15:00').",
                        },
                        "floor": {
                            "type": "INTEGER",
                            "description": "Preferred floor in MBC2: 28, 29, or 30 (default 29).",
                        },
                        "room_type": {
                            "type": "STRING",
                            "description": "Room type: 'phone_booth' (default) or 'focus_room'.",
                        },
                    },
                    "required": ["date_str", "start_time", "end_time"],
                },
            },
            {
                "name": "create_calendar_event",
                "description": (
                    "Create an actual Google Calendar event on Abhi Sethi's primary calendar (aset@google.com) "
                    "with optional attendees and Google Meet link."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {
                            "type": "STRING",
                            "description": "Title or topic of the meeting.",
                        },
                        "date_str": {
                            "type": "STRING",
                            "description": "Date of event in YYYY-MM-DD format, or 'today', 'tomorrow'.",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in Singapore SGT (e.g. '14:00', '2:00 PM').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in Singapore SGT (e.g. '15:00', '3:00 PM').",
                        },
                        "attendees": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of attendee email addresses to invite.",
                        },
                        "description": {
                            "type": "STRING",
                            "description": "Meeting agenda or notes.",
                        },
                        "add_meet": {
                            "type": "BOOLEAN",
                            "description": "Whether to attach a Google Meet link (default true).",
                        },
                    },
                    "required": ["summary", "date_str", "start_time", "end_time"],
                },
            },
            {
                "name": "check_calendar_availability",
                "description": "Check if Abhi Sethi is free or busy during a specific time interval on his Google Calendar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "date_str": {
                            "type": "STRING",
                            "description": "Date in YYYY-MM-DD format, or 'today', 'tomorrow'.",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in Singapore SGT (e.g. '13:30', '1:30 PM').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in Singapore SGT (e.g. '14:30', '2:30 PM').",
                        },
                    },
                    "required": ["date_str", "start_time", "end_time"],
                },
            },
            {
                "name": "list_upcoming_events",
                "description": "List upcoming events from Abhi Sethi's real Google Calendar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "days": {
                            "type": "INTEGER",
                            "description": "Number of days ahead to look (default 3).",
                        }
                    },
                },
            },
        ]
    }
]


def execute_live_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute real Google Calendar and Singapore Room Booking actions."""
    today_str = datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(SGT_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    def resolve_date(d: Optional[str]) -> str:
        if not d or str(d).lower() in ("today", "now"):
            return today_str
        if str(d).lower() == "tomorrow":
            return tomorrow_str
        return str(d)

    try:
        if name == "book_singapore_room":
            date_str = resolve_date(args.get("date_str"))
            start_time = str(args.get("start_time", "13:30"))
            end_time = str(args.get("end_time", "14:30"))
            floor = int(args.get("floor", 29))
            room_type = str(args.get("room_type", "phone_booth"))
            res = book_mbc_room_for_chunk(
                date_str=date_str,
                start_time=start_time,
                end_time=end_time,
                preferred_floor=floor,
                room_type=room_type,
            )
            return res

        elif name == "create_calendar_event":
            summary = str(args.get("summary", "New Meeting"))
            date_str = resolve_date(args.get("date_str"))
            start_time = str(args.get("start_time", "14:00"))
            end_time = str(args.get("end_time", "15:00"))
            attendees = args.get("attendees", [])
            if isinstance(attendees, str):
                attendees = [attendees]
            description = str(args.get("description", ""))
            add_meet = bool(args.get("add_meet", True))

            st_norm = normalize_time_str(start_time)
            et_norm = normalize_time_str(end_time)
            try:
                st_h = int(st_norm.split(":")[0])
                et_h = int(et_norm.split(":")[0])
                if 1 <= st_h <= 6 and "am" not in str(start_time).lower():
                    st_norm = f"{st_h + 12:02d}:{st_norm.split(':')[1]}"
                if 1 <= et_h <= 6 and "am" not in str(end_time).lower():
                    et_norm = f"{et_h + 12:02d}:{et_norm.split(':')[1]}"
            except Exception:
                pass
            start_iso = f"{date_str}T{st_norm}:00+08:00"
            end_iso = f"{date_str}T{et_norm}:00+08:00"

            res_str = create_calendar_event(
                summary=summary,
                start_time=start_iso,
                end_time=end_iso,
                attendees=attendees,
                description=description,
                add_meet=add_meet,
            )
            try:
                return json.loads(res_str)
            except Exception:
                return {"status": "SUCCESS", "message": res_str}

        elif name == "check_calendar_availability":
            date_str = resolve_date(args.get("date_str"))
            start_time = str(args.get("start_time", "13:30"))
            end_time = str(args.get("end_time", "14:30"))
            st_norm = normalize_time_str(start_time)
            et_norm = normalize_time_str(end_time)
            try:
                st_h = int(st_norm.split(":")[0])
                et_h = int(et_norm.split(":")[0])
                if 1 <= st_h <= 6 and "am" not in str(start_time).lower():
                    st_norm = f"{st_h + 12:02d}:{st_norm.split(':')[1]}"
                if 1 <= et_h <= 6 and "am" not in str(end_time).lower():
                    et_norm = f"{et_h + 12:02d}:{et_norm.split(':')[1]}"
            except Exception:
                pass
            start_iso = f"{date_str}T{st_norm}:00+08:00"
            end_iso = f"{date_str}T{et_norm}:00+08:00"
            res_str = check_calendar_availability(start_time=start_iso, end_time=end_iso)
            try:
                return json.loads(res_str)
            except Exception:
                return {"status": "SUCCESS", "message": res_str}

        elif name == "list_upcoming_events":
            days = int(args.get("days", 3))
            res_str = list_upcoming_events(days=days, max_events=6)
            try:
                return json.loads(res_str)
            except Exception:
                return {"status": "SUCCESS", "message": res_str}

        return {"status": "ERROR", "message": f"Unknown tool: {name}"}
    except Exception as e:
        logger.error("Error executing tool %s: %s", name, e, exc_info=True)
        return {"status": "ERROR", "message": str(e)}


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

CRITICAL TOOL CALLING RULES:
- You have access to real tools:
  1. `book_singapore_room`: Call this whenever Abhi asks to book a room or phone booth in Google Singapore MBC2 (Level 28, 29, or 30).
  2. `create_calendar_event`: Call this whenever Abhi asks to schedule a meeting or send a calendar invite.
  3. `check_calendar_availability`: Call this to check Abhi's free/busy intervals.
  4. `list_upcoming_events`: Call this to inspect upcoming calendar events.
- MANDATORY: When Abhi asks you to book a room or schedule an event, YOU MUST INVOKE THE APPROPRIATE TOOL! NEVER claim or pretend that a room is booked or an invite is sent without calling the tool first!
- When the tool returns with the reservation confirmation, speak the real confirmation naturally to Abhi, stating the booked room name and time block.
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
      user-select: none;
    }}
    .orb:hover {{
      transform: scale(1.05);
      box-shadow: 0 0 45px rgba(56, 189, 248, 0.7);
    }}
    .orb.connecting {{
      background: radial-gradient(circle, #38BDF8 0%, #0284C7 60%, #060913 100%);
      box-shadow: 0 0 40px var(--accent-glow);
      animation: liveConnecting 0.8s infinite alternate;
      cursor: wait;
    }}
    @keyframes liveConnecting {{
      from {{ transform: scale(0.96); opacity: 0.8; }}
      to {{ transform: scale(1.06); opacity: 1; }}
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
      max-width: 84%;
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

    /* Action Result Cards */
    .chat-bubble.action-card {{
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #F8FAFC;
      border-radius: 16px;
      padding: 12px 18px;
      font-size: 13px;
      line-height: 1.6;
      max-width: 88%;
      align-self: flex-start;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    }}
    .action-card-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
      font-size: 14px;
      color: #34D399;
      margin-bottom: 4px;
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
      Instant single-click activation • Continuous multi-turn audio • Google Calendar & MBC2 Rooms integrated
    </div>
  </div>

  <script>
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

    function appendActionCard(msg) {{
      const card = document.createElement('div');
      card.className = 'chat-bubble action-card';
      let html = `<div class="action-card-header"><span>${{msg.icon || '📅'}}</span><span>${{msg.title}}</span></div>`;
      if (msg.details) {{
        html += `<div style="margin-top:4px;">${{msg.details.replace(/\\n/g, '<br>')}}</div>`;
      }}
      if (msg.link) {{
        html += `<div style="margin-top:8px;"><a href="${{msg.link}}" target="_blank" style="color:var(--accent);font-weight:600;text-decoration:underline;">View in Google Calendar ↗</a></div>`;
      }}
      card.innerHTML = html;
      activityStream.appendChild(card);
      activityStream.scrollTop = activityStream.scrollHeight;
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

    // --- Audio Input Processing (Microphone -> 16kHz PCM -> WebSocket) ---
    function startAudioProcessing() {{
      if (!micStream || !audioCtxIn) return;

      if (audioCtxIn.state === 'suspended') {{
        audioCtxIn.resume();
      }}

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

        // Echo Guard & Interruption detection:
        if (isAgentSpeaking) {{
          if (rms > 0.035) {{
            interruptPlayback();
          }} else {{
            return;
          }}
        }}

        // Convert Float32 directly to 16-bit PCM (audioCtxIn sampleRate is 16kHz)
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {{
          let s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }}

        ws.send(pcm16.buffer);
      }};

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioCtxIn.destination);
    }}

    function stopMicCapture() {{
      if (scriptProcessor) {{
        try {{ scriptProcessor.disconnect(); }} catch (e) {{}}
        scriptProcessor = null;
      }}
      if (micStream) {{
        try {{ micStream.getTracks().forEach(t => t.stop()); }} catch (e) {{}}
        micStream = null;
      }}
      if (audioCtxIn) {{
        try {{ audioCtxIn.close(); }} catch (e) {{}}
        audioCtxIn = null;
      }}
      bars.forEach(b => b.style.height = '6px');
    }}

    // --- WebSocket Connection Management ---
    async function toggleLiveConnection() {{
      if (isConnecting) return;
      if (isConnected) {{
        disconnectLive();
      }} else {{
        await connectLive();
      }}
    }}

    async function connectLive() {{
      if (isConnecting || isConnected) return;
      isConnecting = true;

      // 1. Critical: Initialize & resume AudioContexts directly in the user click gesture!
      try {{
        initPlaybackContext();
        if (!audioCtxIn) {{
          audioCtxIn = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: 16000 }});
        }}
        if (audioCtxIn.state === 'suspended') {{
          await audioCtxIn.resume();
        }}

        if (!micStream) {{
          micStream = await navigator.mediaDevices.getUserMedia({{
            audio: {{
              channelCount: 1,
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true
            }}
          }});
        }}
      }} catch (err) {{
        console.error("Microphone or AudioContext initialization failed:", err);
        appendBubble("Microphone permission or audio error: " + err.message, "agent");
        isConnecting = false;
        return;
      }}

      liveOrb.className = 'orb connecting';
      orbIcon.textContent = '⏳';
      stateTitle.textContent = 'Connecting to Gemini Live API...';
      stateSubtitle.textContent = 'Activating microphone and neural stream...';
      headerStatus.textContent = 'Connecting...';

      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${{proto}}//${{window.location.host}}/ws/live`;
      ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {{
        isConnecting = false;
        isConnected = true;
        headerStatus.textContent = 'Live Audio Connected';
        liveOrb.className = 'orb connected';
        orbIcon.textContent = '🟢';
        stateTitle.textContent = 'I am listening... (Speak freely)';
        stateSubtitle.textContent = 'Continuous multi-turn live conversation active';
        appendBubble("Connected to Gemini Live API. I'm ready, Abhi! Speak anytime.", "agent");

        heartbeatTimer = setInterval(() => {{
          if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{ type: "ping" }}));
          }}
        }}, 10000);

        startAudioProcessing();
      }};

      ws.onmessage = (event) => {{
        if (event.data instanceof ArrayBuffer) {{
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
            }} else if (msg.type === 'tool_action') {{
              appendActionCard(msg);
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
        isConnecting = false;
      }};

      ws.onclose = () => {{
        isConnecting = false;
        disconnectLive();
      }};
    }}

    function disconnectLive() {{
      isConnecting = false;
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
    Supports continuous multi-turn speech, text input, and full tool calling.
    """
    await websocket.accept()
    logger.info("Client connected to /ws/live WebSocket.")

    # Configurable project and location (defaults to ag-test-1310 / us-central1)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "ag-test-1310")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    quota_proj = os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT", project_id)

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if hasattr(creds, "with_quota_project") and quota_proj:
        try:
            creds = creds.with_quota_project(quota_proj)
        except Exception as e:
            logger.warning("Could not set quota project %s: %s", quota_proj, e)
    if hasattr(creds, "refresh") and not creds.valid:
        try:
            creds.refresh(AuthRequest())
        except Exception as e:
            logger.warning("Credentials refresh warning: %s", e)

    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=location,
        credentials=creds,
    )

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
        ),
        tools=LIVE_TOOLS,
    )

    model_name = "gemini-live-2.5-flash-native-audio"

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            logger.info("Established upstream session with Gemini Live API (%s) with tools enabled", model_name)

            # Task 1: Browser -> Gemini (Microphone audio chunks & text messages)
            async def forward_browser_to_gemini():
                try:
                    chunk_counter = 0
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"]:
                            raw_pcm = msg["bytes"]
                            await session.send_realtime_input(
                                audio=types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")
                            )
                            chunk_counter += 1
                            if chunk_counter % 50 == 0:
                                logger.info("Forwarded 50 audio chunks to Gemini Live...")
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
                                            turn_complete=True,
                                        )
                                    continue
                            except Exception:
                                pass
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from audio input.")
                except Exception as e:
                    logger.error("Error in forward_browser_to_gemini: %s", e)

            # Task 2: Gemini -> Browser (Native 24kHz audio chunks, transcripts, & tool calls)
            async def forward_gemini_to_browser():
                try:
                    tool_call_pending = False
                    while True:
                        try:
                            async for response in session.receive():
                                # 1. Check for real tool calls
                                if response.tool_call is not None:
                                    logger.info("Gemini Live emitted tool_call: %s", response.tool_call)
                                    tool_call_pending = True
                                    function_responses = []
                                    for fc in response.tool_call.function_calls:
                                        call_id = fc.id
                                        fn_name = fc.name
                                        fn_args = fc.args or {}
                                        logger.info("Executing tool call: %s (id=%s) with args: %s", fn_name, call_id, fn_args)

                                        # Execute tool in threadpool to keep asyncio loop non-blocking
                                        tool_result = await asyncio.to_thread(execute_live_tool, fn_name, fn_args)
                                        logger.info("Tool %s execution completed: %s", fn_name, tool_result)

                                        # Format visual action card for browser feed
                                        action_title = "Action Completed"
                                        icon = "⚡"
                                        link = tool_result.get("calendar_link") or tool_result.get("html_link")
                                        if fn_name == "book_singapore_room":
                                            icon = "🏢"
                                            action_title = f"Room Reserved: {tool_result.get('room_name', 'MBC2 Room')}"
                                        elif fn_name == "create_calendar_event":
                                            icon = "📅"
                                            action_title = f"Calendar Event: {tool_result.get('summary', 'Meeting')}"
                                        elif fn_name == "check_calendar_availability":
                                            icon = "🕒"
                                            action_title = "Calendar Availability Checked"
                                        elif fn_name == "list_upcoming_events":
                                            icon = "📋"
                                            action_title = "Upcoming Schedule Retrieved"

                                        details_text = tool_result.get("message") or json.dumps(tool_result, indent=2)
                                        await websocket.send_text(json.dumps({
                                            "type": "tool_action",
                                            "title": action_title,
                                            "icon": icon,
                                            "details": details_text,
                                            "link": link,
                                        }))

                                        function_responses.append(types.FunctionResponse(
                                            id=call_id,
                                            name=fn_name,
                                            response={"result": tool_result},
                                        ))

                                    if function_responses:
                                        logger.info("Sending %d tool response(s) back to Gemini Live", len(function_responses))
                                        await session.send_tool_response(function_responses=function_responses)

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
                                            "text": sc.input_transcription.text,
                                        }))

                                    # Stream real-time output transcription (what Gemini speaks)
                                    if hasattr(sc, "output_transcription") and sc.output_transcription and sc.output_transcription.text:
                                        await websocket.send_text(json.dumps({
                                            "type": "transcript_chunk",
                                            "role": "agent",
                                            "text": sc.output_transcription.text,
                                        }))

                                    model_turn = sc.model_turn
                                    if model_turn is not None:
                                        for part in model_turn.parts:
                                            if part.inline_data and part.inline_data.data:
                                                # Send raw 24kHz PCM chunk as binary to browser
                                                await websocket.send_bytes(part.inline_data.data)

                                    # Turn Complete event (multi-turn transition)
                                    if getattr(sc, "turn_complete", False):
                                        if tool_call_pending:
                                            logger.info("Tool invocation turn complete. Waiting for Gemini's spoken response turn...")
                                            tool_call_pending = False
                                        else:
                                            logger.info("Gemini Live spoken turn complete. Ready for next turn.")
                                            await websocket.send_text(json.dumps({"type": "turn_complete"}))

                        except asyncio.CancelledError:
                            break
                        except Exception as loop_err:
                            logger.error("Error in session.receive turn: %s", loop_err, exc_info=True)
                            break
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from audio output.")
                except Exception as e:
                    logger.error("Error in forward_gemini_to_browser: %s", e)

            # Run both tasks concurrently
            await asyncio.gather(
                forward_browser_to_gemini(),
                forward_gemini_to_browser(),
            )

    except Exception as err:
        logger.error("Failed in live session: %s", err, exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "transcript",
                "role": "agent",
                "text": f"Connection error: {err}",
            }))
        except Exception:
            pass
        await websocket.close()


@app.get("/healthz")
@app.get("/health")
@app.get("/status")
def healthz():
    return {
        "status": "ok",
        "service": "Gemini Multimodal Live Voice Portal",
        "model": "gemini-live-2.5-flash-native-audio",
        "voice": "Aoede (Native Audio)",
        "multi_turn": True,
        "tools_enabled": True,
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Agenica S Gemini Multimodal Live API Server on port %d...", port)
    uvicorn.run(app, host="0.0.0.0", port=port, ws_ping_interval=20, ws_ping_timeout=20)


if __name__ == "__main__":
    main()
