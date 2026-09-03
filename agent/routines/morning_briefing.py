"""
Morning Executive Briefing Routine for Agenica S.
Scheduled daily at 08:30 SGT (Monday - Friday).
Pulls today's calendar schedule, confirmed room bookings, and unread priority emails,
and delivers a concise executive briefing card to Abhi Sethi in Google Chat.
"""

import os
import sys
import json
import argparse
from datetime import datetime
import zoneinfo

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    AGENT_NAME,
    AGENT_EMAIL,
    OFFICE_LOCATION,
    DEFAULT_TIMEZONE,
)
from ..tools.calendar_tools import list_upcoming_events, get_current_datetime
from ..tools.gmail_tools import scan_inbox_triage
from ..tools.chat_tools import send_chat_notification

SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def run_morning_briefing(dispatch_chat: bool = True) -> dict:
    """
    Execute the morning executive briefing workflow.
    """
    now = datetime.now(SGT_TZ)
    today_str = now.strftime("%Y-%m-%d")

    # 1. Today's Calendar Events
    events_raw = json.loads(list_upcoming_events(days=1, max_events=10))
    events = events_raw.get("events", [])

    # Filter to today
    today_events = []
    for ev in events:
        st = ev.get("start", "")
        if today_str in st:
            today_events.append(ev)

    # 2. Inbox Triage Scan
    triage_raw = json.loads(scan_inbox_triage(max_results=5))
    needs_action = triage_raw.get("categories", {}).get("needs_action", [])

    # 3. Format Briefing Message
    briefing_lines = [
        f"**☀️ Good Morning, Abhi — Executive Briefing for {now.strftime('%A, %b %d')}**",
        f"_Prepared by {AGENT_NAME} (Singapore Time / SGT)_",
        "",
        f"### 📅 Today's Schedule ({len(today_events)} Commitments)",
    ]

    if today_events:
        for ev in today_events:
            st = ev.get("start", "")
            time_part = st.split("T")[1][:5] if "T" in st else "All Day"
            loc = ev.get("location", "Google Meet")
            meet = ev.get("hangout_link") or ev.get("html_link")
            link_str = f" • [Join / View]({meet})" if meet else ""
            briefing_lines.append(f"- **`{time_part}`** {ev.get('summary')} ({loc}){link_str}")
    else:
        briefing_lines.append("- _No scheduled meetings today. Open for deep work and strategic focus._")

    briefing_lines.extend([
        "",
        f"### 📬 Inbox Highlights ({len(needs_action)} Items Needing Attention)",
    ])

    if needs_action:
        for act in needs_action[:3]:
            sender = act.get("from", "External")
            subj = act.get("subject", "No subject")
            briefing_lines.append(f"- **From {sender}:** {subj}")
    else:
        briefing_lines.append("- _Inbox is clear of urgent action items._")

    briefing_lines.extend([
        "",
        "---",
        f"_{AGENT_NAME} • {AGENT_EMAIL}_"
    ])

    briefing_text = "\n".join(briefing_lines)

    if dispatch_chat:
        send_chat_notification(PRINCIPAL_EMAIL, briefing_text)

    return {
        "status": "BRIEFING_DELIVERED",
        "date": today_str,
        "event_count": len(today_events),
        "needs_action_count": len(needs_action),
        "briefing_text": briefing_text
    }


def main():
    parser = argparse.ArgumentParser(description="Run Agenica S Morning Executive Briefing")
    parser.add_argument("--no-dispatch", action="store_true", help="Print briefing without dispatching live Chat")
    args = parser.parse_args()

    print("=" * 70)
    print(f"{AGENT_NAME} — Morning Executive Briefing")
    print("=" * 70)

    res = run_morning_briefing(dispatch_chat=not args.no_dispatch)
    print(res["briefing_text"])


if __name__ == "__main__":
    main()
