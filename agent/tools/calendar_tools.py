"""
Google Calendar Tool Adapter for Agenica S.
Delegates to CalendarService for enterprise scheduling and multi-day resolution.
"""

import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    DEFAULT_TIMEZONE,
    OFFICE_LOCATION,
)
from ..services.calendar_service import CalendarService
from .auth import get_calendar_service

logger = logging.getLogger("agenica.tools.calendar")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def _to_rfc3339(dt: datetime) -> str:
    return CalendarService.to_rfc3339(dt)


def resolve_calendar_time_range(
    date_str: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 7,
):
    return CalendarService.resolve_time_range(date_str, start_date, end_date, days)


def get_current_datetime(timezone_str: str = DEFAULT_TIMEZONE) -> Dict[str, str]:
    """Return the current date, time, day of week, and timezone in Singapore Standard Time."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
    except Exception:
        tz = SGT_TZ

    now = datetime.now(tz)
    return {
        "datetime_iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": str(tz),
        "formatted": now.strftime("%A, %d %B %Y at %I:%M %p %Z"),
    }


def check_calendar_availability(
    target_date: str,
    start_time: str = "09:00",
    end_time: str = "18:00",
    attendees: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check availability for target date and time."""
    cal_svc = CalendarService.get_instance()
    return cal_svc.check_availability(target_date, start_time, end_time)


def find_next_free_slot(
    duration_minutes: int = 30,
    preferred_date: Optional[str] = None,
    preferred_window: str = "morning",
) -> Dict[str, Any]:
    """Find the next available free calendar slot."""
    cal_svc = CalendarService.get_instance()
    d_str = preferred_date or datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    w_start, w_end = ("09:00", "12:00") if preferred_window == "morning" else ("14:00", "17:00")

    res = cal_svc.list_upcoming_events(start_date=d_str, end_date=d_str, max_events=30)
    busy_spans = []
    for ev in res.get("events", []):
        if ev.get("is_all_day"):
            continue
        try:
            s_dt = datetime.fromisoformat(ev["start"]).astimezone(SGT_TZ)
            e_dt = datetime.fromisoformat(ev["end"]).astimezone(SGT_TZ)
            busy_spans.append((s_dt, e_dt))
        except Exception:
            pass

    win_start_dt = datetime.strptime(f"{d_str} {w_start}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
    win_end_dt = datetime.strptime(f"{d_str} {w_end}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)

    curr = max(datetime.now(SGT_TZ), win_start_dt)
    busy_spans.sort(key=lambda x: x[0])

    for b_start, b_end in busy_spans:
        if curr + timedelta(minutes=duration_minutes) <= b_start:
            slot_end = curr + timedelta(minutes=duration_minutes)
            return {
                "date": d_str,
                "start_time": curr.strftime("%H:%M"),
                "end_time": slot_end.strftime("%H:%M"),
                "start_iso": cal_svc.to_rfc3339(curr),
                "end_iso": cal_svc.to_rfc3339(slot_end),
                "duration_minutes": duration_minutes,
                "status": "available",
            }
        if b_end > curr:
            curr = b_end

    if curr + timedelta(minutes=duration_minutes) <= win_end_dt:
        slot_end = curr + timedelta(minutes=duration_minutes)
        return {
            "date": d_str,
            "start_time": curr.strftime("%H:%M"),
            "end_time": slot_end.strftime("%H:%M"),
            "start_iso": cal_svc.to_rfc3339(curr),
            "end_iso": cal_svc.to_rfc3339(slot_end),
            "duration_minutes": duration_minutes,
            "status": "available",
        }

    return {"status": "not_found", "message": f"No open {duration_minutes}m slot found in {preferred_window}."}


def list_upcoming_events(
    days: int = 7,
    max_events: int = 30,
    date_str: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve upcoming calendar events."""
    cal_svc = CalendarService.get_instance()
    return cal_svc.list_upcoming_events(
        date_str=date_str,
        start_date=start_date,
        end_date=end_date,
        days=days,
        max_events=max_events,
        query=query,
    )


def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    attendees: Optional[List[str]] = None,
    description: str = "",
    location: str = "",
    include_meet: bool = True,
) -> Dict[str, Any]:
    """Insert a new calendar event with Google Meet."""
    cal_svc = CalendarService.get_instance()
    return cal_svc.create_event(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
        location=location,
        include_meet=include_meet,
    )


def check_calendar_clash(
    start_time: str,
    end_time: str,
    attendee_email: str = PRINCIPAL_EMAIL,
) -> Dict[str, Any]:
    """Check for clashes in the requested window."""
    try:
        s_dt = datetime.fromisoformat(start_time).astimezone(SGT_TZ)
        e_dt = datetime.fromisoformat(end_time).astimezone(SGT_TZ)
        d_str = s_dt.strftime("%Y-%m-%d")
        res = check_calendar_availability(d_str, s_dt.strftime("%H:%M"), e_dt.strftime("%H:%M"))
        has_clash = not res.get("is_free", False)
        return {
            "has_clash": has_clash,
            "conflicting_slots": res.get("busy_slots", []),
            "message": "Clash detected." if has_clash else "No clash detected.",
        }
    except Exception as e:
        return {"has_clash": False, "error": str(e)}


def suggest_meeting_agenda(topic: str, duration_minutes: int = 30) -> List[str]:
    """Generate structured meeting agenda."""
    return [
        f"00-05m: Objectives & Context: {topic}",
        "05-20m: Core Technical / Architecture Discussion",
        "20-25m: Decisions, Trade-offs & Blockers",
        "25-30m: Action Items & Owners",
    ]


def generate_prebooking_proposal(
    requestor_email: str,
    topic: str,
    preferred_date: Optional[str] = None,
    duration_minutes: int = 30,
) -> Dict[str, Any]:
    """Generate prebooking proposal."""
    slot = find_next_free_slot(duration_minutes=duration_minutes, preferred_date=preferred_date)
    return {
        "requestor": requestor_email,
        "topic": topic,
        "slot": slot,
        "agenda": suggest_meeting_agenda(topic, duration_minutes),
    }
