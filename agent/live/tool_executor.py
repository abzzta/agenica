"""
Live Tool Execution Dispatcher and Action Card Formatter for Agenica S.
Routes tool invocations to underlying domain services, enforces HITL email safety guardrails,
and formats rich UI event cards and approval cards.
"""

import json
import logging
from datetime import datetime, timedelta
import zoneinfo
from typing import Dict, Any, Optional

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    DEFAULT_TIMEZONE,
)
from ..services.calendar_service import CalendarService
from ..services.room_service import RoomService, RoomResource
from ..services.gmail_service import GmailService
from ..tools.room_booking_tools import check_floor_room_availability, book_meeting_room

logger = logging.getLogger("agenica.live.executor")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def execute_live_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute tool against domain services and return structured payload."""
    cal_svc = CalendarService.get_instance()
    room_svc = RoomService.get_instance()
    gmail_svc = GmailService.get_instance()

    today_str = datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(SGT_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    def resolve_date(d: Optional[str]) -> str:
        if not d or str(d).lower() in ("today", "now"):
            return today_str
        if str(d).lower() == "tomorrow":
            return tomorrow_str
        return str(d)

    try:
        if name == "get_current_time":
            now = datetime.now(SGT_TZ)
            return {
                "current_time_sgt": now.strftime("%I:%M:%S %p"),
                "date": now.strftime("%A, %d %B %Y"),
                "iso": now.isoformat(),
                "timezone": DEFAULT_TIMEZONE,
            }

        elif name == "check_calendar_availability":
            date_val = resolve_date(args.get("date"))
            start_time = args.get("start_time", "09:00")
            end_time = args.get("end_time", "18:00")
            return cal_svc.check_availability(date_val, start_time, end_time)

        elif name == "create_calendar_event":
            return cal_svc.create_event(
                summary=args.get("summary", "New Meeting"),
                start_time=args.get("start_time", ""),
                end_time=args.get("end_time", ""),
                attendees=args.get("attendees"),
                description=args.get("description", ""),
                include_meet=True,
            )

        elif name == "list_upcoming_events":
            days = int(args.get("days", 7))
            max_events = int(args.get("max_events", 30))
            return cal_svc.list_upcoming_events(
                date_str=args.get("date_str"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                days=days,
                max_events=max_events,
                query=args.get("query"),
            )

        elif name == "check_room_availability":
            date_val = resolve_date(args.get("date"))
            start_time = args.get("start_time", "10:00")
            end_time = args.get("end_time", "11:00")
            floor = args.get("floor")
            office = args.get("office") or args.get("location") or args.get("city")
            building = args.get("building") or office
            room_name = args.get("room_name")
            room_type = args.get("room_type")
            return check_floor_room_availability(
                target_date=date_val,
                start_time=start_time,
                end_time=end_time,
                floor=floor,
                building=building,
                office=office,
                room_name=room_name,
                room_type=room_type,
            )

        elif name in ("book_singapore_room", "book_meeting_room"):
            date_val = resolve_date(args.get("target_date") or args.get("date"))
            office = args.get("office") or args.get("location") or args.get("city")
            building = args.get("building") or office
            return book_meeting_room(
                target_date=date_val,
                start_time=args.get("start_time", "10:00"),
                end_time=args.get("end_time", "11:00"),
                floor=args.get("floor"),
                building=building,
                room_name=args.get("room_name"),
                room_type=args.get("room_type"),
                title=args.get("title", "Focus / Meeting Block"),
                attendees=args.get("attendees"),
            )

        elif name == "create_gmail_draft":
            return gmail_svc.create_draft(
                recipient=args.get("recipient", ""),
                subject=args.get("subject", "Follow up"),
                body=args.get("body", ""),
                notify_chat=True,
            )

        elif name == "send_email":
            # Gated by explicit user_confirmed parameter
            user_confirmed = bool(args.get("user_confirmed", False))
            return gmail_svc.send_email(
                recipient=args.get("recipient", ""),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
                user_confirmed=user_confirmed,
            )

        elif name == "check_mailbox_invites":
            max_r = int(args.get("max_results", 10))
            return gmail_svc.scan_inbox_triage(max_results=max_r)

        elif name == "search_emails":
            query = args.get("query", "")
            max_r = int(args.get("max_results", 10))
            return gmail_svc.search_emails(query=query, max_results=max_r)

        else:
            return {"status": "error", "message": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error("Error executing live tool '%s': %s", name, e, exc_info=True)
        return {"status": "error", "message": f"Tool execution error: {e}"}


def format_action_card(fn_name: str, tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """Format rich UI action card for real-time browser feed."""
    action_title = "Action Completed"
    icon = "⚡"
    card_type = "tool_action"
    link = (
        tool_result.get("calendar_link")
        or tool_result.get("html_link")
        or tool_result.get("draft_url")
        or tool_result.get("inbox_url")
    )

    # Check for Gated Safety Guardrail
    if tool_result.get("status") == "approval_required" or tool_result.get("guardrail") == "EMAIL_SEND_GATED":
        card_type = "approval_card"
        icon = "🛡️"
        action_title = f"Approval Required: Email to {tool_result.get('recipient')}"
        details_text = tool_result.get("message")
        return {
            "type": card_type,
            "title": action_title,
            "icon": icon,
            "details": details_text,
            "recipient": tool_result.get("recipient"),
            "subject": tool_result.get("subject"),
            "draft_id": tool_result.get("draft_id"),
            "link": link,
            "requires_confirmation": True,
        }

    if fn_name in ("book_singapore_room", "book_meeting_room"):
        icon = "🏢"
        action_title = f"Room Reserved: {tool_result.get('room_name', 'Meeting Room')}"
        link = tool_result.get("calendar_link")
        details_text = tool_result.get("message")
    elif fn_name == "create_calendar_event":
        icon = "📅"
        action_title = f"Calendar Event: {tool_result.get('summary', 'Meeting')}"
        details_text = tool_result.get("message")
    elif fn_name == "check_calendar_availability":
        icon = "🕒"
        action_title = "Calendar Availability Checked"
        details_text = tool_result.get("message")
    elif fn_name == "list_upcoming_events":
        icon = "📋"
        period_str = tool_result.get("period", "Schedule")
        total_cnt = tool_result.get("total_events", 0)
        action_title = f"Schedule: {period_str} ({total_cnt} events)"
        link = f"https://calendar.google.com/calendar/u/{PRINCIPAL_EMAIL}/r"
        ebd = tool_result.get("events_by_day", {})
        if ebd:
            lines = []
            for d, evs in list(ebd.items())[:6]:
                lines.append(f"📅 {d}:")
                for ev in evs[:5]:
                    lines.append(f"  • {ev.get('time_display')}: {ev.get('summary')}")
                if len(evs) > 5:
                    lines.append(f"  • ... and {len(evs) - 5} more")
            details_text = "\n".join(lines)
        else:
            details_text = tool_result.get("summary", "No events found.")
    elif fn_name == "check_room_availability":
        icon = "🚪"
        fl = tool_result.get("floor")
        office = tool_result.get("office") or tool_result.get("building") or "Selected Rooms"
        floor_label = f"Level {fl} ({office})" if fl is not None else office
        action_title = f"Room Availability: {floor_label}"
        details_text = tool_result.get("summary") or "Room status retrieved."
        link = f"https://calendar.google.com/calendar/u/{PRINCIPAL_EMAIL}/r"
    elif fn_name == "create_gmail_draft":
        icon = "✉️"
        action_title = f"Gmail Draft Prepared: {tool_result.get('subject', 'Draft')}"
        link = tool_result.get("draft_url")
        details_text = tool_result.get("message")
        card_type = "approval_card"  # Give user 1-click approve right from the draft card
    elif fn_name == "send_email":
        icon = "📤"
        action_title = f"Email Sent: {tool_result.get('subject', 'Email')}"
        link = f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#sent"
        details_text = tool_result.get("message")
    elif fn_name == "check_mailbox_invites":
        icon = "📬"
        action_title = "Mailbox Invites Scanned"
        link = f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#inbox"
        details_text = tool_result.get("summary")
    elif fn_name == "search_emails":
        icon = "🔍"
        action_title = f"Gmail Search: {tool_result.get('query', '')}"
        link = f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#search/{tool_result.get('query', '')}"
        details_text = f"Found {tool_result.get('total_found', 0)} emails."
    else:
        details_text = tool_result.get("message") or json.dumps(tool_result, indent=2)

    return {
        "type": card_type,
        "title": action_title,
        "icon": icon,
        "details": details_text,
        "recipient": tool_result.get("recipient"),
        "subject": tool_result.get("subject"),
        "draft_id": tool_result.get("draft_id"),
        "link": link,
    }
