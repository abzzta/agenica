"""
Singapore MBC2 & Global Room Booking Tool Adapter.
Delegates to dynamic, high-performance RoomService.
"""

import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    AGENT_NAME,
    DEFAULT_TIMEZONE,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
    BUILDING_CODE,
)
from ..services.room_service import RoomService, RoomResource
from ..services.calendar_service import CalendarService
from .hitl_tools import normalize_time_str

logger = logging.getLogger("agenica.tools.rooms")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def dynamic_calendar_room_discovery(query: str) -> List[Dict[str, Any]]:
    """Dynamically search Google Calendar for rooms matching query."""
    room_svc = RoomService.get_instance()
    rooms = room_svc.dynamic_discovery(query)
    return [r.to_dict() for r in rooms]


def check_room_availability(
    room_email: str,
    start_iso: str,
    end_iso: str,
) -> bool:
    """Query real-time free/busy status for a Google Calendar room resource."""
    room_svc = RoomService.get_instance()
    r = room_svc._rooms.get(room_email)
    if not r:
        r = RoomResource(
            email=room_email,
            name=room_email,
            clean_name=room_email.split("@")[0],
            building="OTHER",
        )
    result = room_svc.check_availability([r], start_iso, end_iso)
    return len(result.get("available", [])) > 0


def find_available_mbc_room(
    floor: Optional[int] = None,
    start_iso: str = "",
    end_iso: str = "",
    preferred_type: Optional[str] = None,
    building: Optional[str] = None,
    room_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find a verified room on the given floor or building that is free for the requested window."""
    room_svc = RoomService.get_instance()
    found = room_svc.find_available_room(
        floor=floor,
        building=building,
        room_name=room_name,
        room_type=preferred_type,
        start_iso=start_iso,
        end_iso=end_iso,
    )
    return found.to_dict() if found else None


def check_floor_room_availability(
    target_date: str,
    start_time: str,
    end_time: str,
    floor: Optional[int] = None,
    building: Optional[str] = None,
    office: Optional[str] = None,
    location: Optional[str] = None,
    room_name: Optional[str] = None,
    room_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Check availability across rooms on a given floor, office, or building."""
    room_svc = RoomService.get_instance()
    cal_svc = CalendarService.get_instance()

    try:
        s_dt = datetime.strptime(f"{target_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
        e_dt = datetime.strptime(f"{target_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
        s_iso = cal_svc.to_rfc3339(s_dt)
        e_iso = cal_svc.to_rfc3339(e_dt)
    except Exception as ex:
        return {"status": "error", "error": f"Invalid date or time: {ex}"}

    target_loc = office or location or building
    candidate_rooms = room_svc.search_rooms(
        query=room_name,
        building=building,
        office=office,
        location=location,
        floor=floor,
        room_type=room_type,
        limit=20,
    )

    if not candidate_rooms:
        loc_desc = target_loc or "Singapore MBC2"
        floor_desc = f" on Floor {floor}" if floor is not None else ""
        return {
            "status": "not_found",
            "floor": floor,
            "office": loc_desc,
            "building": loc_desc,
            "available_count": 0,
            "summary": f"No rooms found matching{floor_desc} in {loc_desc}.",
        }

    batch_result = room_svc.check_availability(candidate_rooms, s_iso, e_iso)
    avail = batch_result.get("available", [])
    busy = batch_result.get("busy", [])

    avail_names = [r.clean_name for r in avail]
    loc_name = candidate_rooms[0].building if candidate_rooms else (target_loc or "Singapore MBC2")
    if floor is not None:
        scope_label = f"Level {floor} ({loc_name})"
    elif target_loc:
        scope_label = f"{target_loc} ({loc_name})"
    else:
        scope_label = f"{loc_name}"

    summary_text = (
        f"In {scope_label} for {start_time} – {end_time} SGT on {target_date}: "
        f"{len(avail)} available ({', '.join(avail_names[:5]) if avail_names else 'none'}), "
        f"{len(busy)} occupied."
    )

    return {
        "status": "success",
        "floor": floor,
        "office": target_loc,
        "building": loc_name,
        "target_date": target_date,
        "time_window": f"{start_time} - {end_time}",
        "available_count": len(avail),
        "busy_count": len(busy),
        "available_rooms": [r.to_dict() for r in avail],
        "summary": summary_text,
    }


def book_meeting_room(
    target_date: str,
    start_time: str,
    end_time: str,
    floor: Optional[int] = None,
    building: Optional[str] = None,
    room_name: Optional[str] = None,
    room_type: Optional[str] = None,
    title: str = "Focus / Meeting",
    attendees: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Book a meeting room or phone booth dynamically."""
    room_svc = RoomService.get_instance()
    cal_svc = CalendarService.get_instance()

    try:
        s_dt = datetime.strptime(f"{target_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
        e_dt = datetime.strptime(f"{target_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
        s_iso = cal_svc.to_rfc3339(s_dt)
        e_iso = cal_svc.to_rfc3339(e_dt)
    except Exception as ex:
        return {"status": "error", "error": f"Invalid date or time: {ex}"}

    room = room_svc.find_available_room(
        floor=floor,
        building=building,
        room_name=room_name,
        room_type=room_type,
        start_iso=s_iso,
        end_iso=e_iso,
    )

    if not room:
        target_desc = f"Floor {floor}" if floor else (room_name or "requested criteria")
        return {
            "status": "unavailable",
            "message": f"No rooms available matching {target_desc} between {start_time} and {end_time} SGT.",
        }

    return room_svc.book_room(
        room=room,
        start_iso=s_iso,
        end_iso=e_iso,
        summary=title,
        attendees=attendees,
    )


def book_mbc_room_for_chunk(
    chunk: Dict[str, Any],
    room_preference: Optional[str] = None,
    floor: Optional[int] = None,
    room_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Book room for a focus chunk."""
    s_iso = chunk.get("start", "")
    e_iso = chunk.get("end", "")
    room_svc = RoomService.get_instance()
    room = room_svc.find_available_room(
        floor=floor,
        room_name=room_name,
        room_type=room_preference,
        start_iso=s_iso,
        end_iso=e_iso,
    )
    if not room:
        return {"status": "unavailable", "message": "No room available for chunk."}

    return room_svc.book_room(
        room=room,
        start_iso=s_iso,
        end_iso=e_iso,
        summary="Deep Work / Focus Block",
    )


def find_daily_focus_chunks(
    target_date: Optional[str] = None,
    min_duration_minutes: int = 45,
    max_chunks: int = 3,
) -> List[Dict[str, Any]]:
    """Scan day's schedule for open focus blocks."""
    cal_svc = CalendarService.get_instance()
    d_str = target_date or datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    res = cal_svc.list_upcoming_events(start_date=d_str, end_date=d_str, max_events=50)
    events = res.get("events", [])

    busy_spans = []
    for ev in events:
        if ev.get("is_all_day"):
            continue
        try:
            s_dt = datetime.fromisoformat(ev["start"]).astimezone(SGT_TZ)
            e_dt = datetime.fromisoformat(ev["end"]).astimezone(SGT_TZ)
            busy_spans.append((s_dt, e_dt))
        except Exception:
            pass

    busy_spans.sort(key=lambda x: x[0])
    day_start = datetime.strptime(f"{d_str} 09:00", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
    day_end = datetime.strptime(f"{d_str} 18:00", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)

    chunks = []
    curr = day_start
    for b_start, b_end in busy_spans:
        if b_start > curr:
            delta = (b_start - curr).total_seconds() / 60
            if delta >= min_duration_minutes:
                chunks.append({
                    "start": cal_svc.to_rfc3339(curr),
                    "end": cal_svc.to_rfc3339(b_start),
                    "duration_minutes": int(delta),
                    "label": f"{curr.strftime('%I:%M %p')} – {b_start.strftime('%I:%M %p')} SGT ({int(delta)} min)",
                })
        if b_end > curr:
            curr = b_end

    if curr < day_end:
        delta = (day_end - curr).total_seconds() / 60
        if delta >= min_duration_minutes:
            chunks.append({
                "start": cal_svc.to_rfc3339(curr),
                "end": cal_svc.to_rfc3339(day_end),
                "duration_minutes": int(delta),
                "label": f"{curr.strftime('%I:%M %p')} – {day_end.strftime('%I:%M %p')} SGT ({int(delta)} min)",
            })

    return chunks[:max_chunks]


def reserve_daily_focus_rooms(target_date: Optional[str] = None) -> Dict[str, Any]:
    """Scan and reserve focus rooms for all open focus chunks."""
    chunks = find_daily_focus_chunks(target_date)
    if not chunks:
        return {"status": "no_chunks", "message": "No open focus blocks found."}
    results = []
    for c in chunks:
        r = book_mbc_room_for_chunk(c)
        results.append({"chunk": c, "booking": r})
    return {"status": "success", "reservations": results}
