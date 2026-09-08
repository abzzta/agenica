"""
Singapore MBC2 Level 29 Room Booking Engine for Agenica S.

Provides:
1. Verified Room Resource Registry for Google Singapore MBC2 (Levels 29, 28, 30).
2. Real-time availability verification via Google Calendar FreeBusy API.
3. Direct calendar event creation on primary calendar (aset@google.com) with room resource attachment.
4. Autonomous detection of open focus chunks and room allocation.
"""

import os
import json
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
    BUILDING_CODE
)
from .auth import get_calendar_service
from .calendar_tools import _to_rfc3339
from .hitl_tools import normalize_time_str

logger = logging.getLogger("agenica.rooms")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)

# Verified Google Singapore MBC2 Room Resource Catalog
MBC2_ROOM_CATALOG: Dict[int, List[Dict[str, Any]]] = {
    29: [
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 1 Phone Room (1)",
            "type": "phone_booth",
            "capacity": 1,
            "email": "c_1886jiupqc3dsilbnh5qsjo3n4dc24gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3gd8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 2 Phone Room (1)",
            "type": "phone_booth",
            "capacity": 1,
            "email": "c_1883srbno3st0jdjlnj7iev1e655u4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3gdg@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 3 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_188bju082q2oci34njdb89fs8vg0o4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3gdo@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 11 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_188ftvjd1gkiqhlnhsq2iegg565r64gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ec0@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 12 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_18849eljddta4il6n5m9fua0p5g964gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ce8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 13 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_1889f8o4sn0uiifgmofi9v8tv9fk44gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ad8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 14 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_18826t8a6ilbsimaint14phr9pa6a4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ad0@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 15 Phone Room (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_1887rc2uf77pojn7gnai0rc0opmlu4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3aco@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 4 Ann Siang (5)",
            "type": "focus_room",
            "capacity": 5,
            "email": "c_188ae8it5va6ijlanna95a2ne023q4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ic0@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 5 Dempsey (5)",
            "type": "focus_room",
            "capacity": 5,
            "email": "c_1884v2g527neqga4mtp1a76qnd8t04gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ic8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 6 Emerald (5)",
            "type": "focus_room",
            "capacity": 5,
            "email": "c_1886le8luk554h1ogs29su5f2ntnm4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3icg@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 8 Faber (5)",
            "type": "focus_room",
            "capacity": 5,
            "email": "c_188anj14shn9mid3jr2mkpq8pimgc4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ed8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-29-B-B80 Hillview 10 Serapong (9)",
            "type": "large_room",
            "capacity": 9,
            "email": "c_1880698i1vcauiorl3r46l9og48di4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi75fj4eb270o3ec8@resource.calendar.google.com"
        }
    ],
    28: [
        {
            "name": "SG-SIN-MBC2-28-B-B80 29 Phone Room - External (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_188bn1gj187ach0lkei0e29bl62gc4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npi71fj4e3270o3gd0@resource.calendar.google.com"
        }
    ],
    30: [
        {
            "name": "SG-SIN-MBC2-30-B-B80 1 Phone Room - External (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_1881uj9kh3vmki0bioh1hdsdhkk6m4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npj61fj6c3270o32e8@resource.calendar.google.com"
        },
        {
            "name": "SG-SIN-MBC2-30-B-B80 2 Phone Room - External (2)",
            "type": "phone_booth",
            "capacity": 2,
            "email": "c_1881o34eh99iiikkjdttrnvks0giq4gactnmuprcckn66rrd38dn4rrfdlfn6pqvedkmsnrdc9hj4npj61fj6c3270o32do@resource.calendar.google.com"
        }
    ]
}


def check_room_availability(
    room_email: str,
    start_iso: str,
    end_iso: str
) -> bool:
    """Query real-time free/busy status for a Google Calendar room resource."""
    try:
        service = get_calendar_service()
        body = {
            "timeMin": start_iso,
            "timeMax": end_iso,
            "items": [{"id": room_email}]
        }
        res = service.freebusy().query(body=body).execute()
        busy_list = res.get("calendars", {}).get(room_email, {}).get("busy", [])
        return len(busy_list) == 0
    except Exception as e:
        logger.warning("Error checking room availability for %s: %s", room_email, e)
        return False


def find_available_mbc_room(
    floor: int,
    start_iso: str,
    end_iso: str,
    preferred_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find a verified MBC2 room on the given floor that is free for the entire requested window."""
    candidate_rooms = list(MBC2_ROOM_CATALOG.get(floor, []))
    if preferred_type:
        candidate_rooms = sorted(candidate_rooms, key=lambda r: 0 if r.get("type") == preferred_type else 1)

    for room in candidate_rooms:
        if check_room_availability(room["email"], start_iso, end_iso):
            return room

    # If no room on preferred floor, check adjacent floors (28, 30)
    for alt_floor in [28, 30]:
        if alt_floor != floor:
            for room in MBC2_ROOM_CATALOG.get(alt_floor, []):
                if check_room_availability(room["email"], start_iso, end_iso):
                    return room
    return None


def find_daily_focus_chunks(
    target_date: str,
    email: str = PRINCIPAL_EMAIL,
    min_chunk_minutes: int = 60
) -> List[Dict[str, Any]]:
    """
    Scan Abhi Sethi's calendar for large uninterrupted open time blocks during business hours (09:00 - 18:00 SGT).
    """
    day_start = f"{target_date}T09:00:00+08:00"
    day_end = f"{target_date}T18:00:00+08:00"

    try:
        service = get_calendar_service()
        fb_query = {
            "timeMin": day_start,
            "timeMax": day_end,
            "items": [{"id": email}]
        }
        res = service.freebusy().query(body=fb_query).execute()
        busy_spans = res.get("calendars", {}).get(email, {}).get("busy", [])
    except Exception as e:
        logger.error("Live freebusy check error: %s", e)
        return []

    # Parse busy spans
    parsed_busy = []
    for b in busy_spans:
        st = datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(SGT_TZ)
        et = datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(SGT_TZ)
        parsed_busy.append((st, et))

    parsed_busy.sort(key=lambda x: x[0])

    work_start = datetime.fromisoformat(day_start)
    work_end = datetime.fromisoformat(day_end)

    free_chunks = []
    curr = work_start

    for b_st, b_et in parsed_busy:
        if b_st > curr:
            dur = (b_st - curr).total_seconds() / 60
            if dur >= min_chunk_minutes:
                free_chunks.append({
                    "start": curr.strftime("%H:%M"),
                    "end": b_st.strftime("%H:%M"),
                    "duration_minutes": int(dur),
                    "start_iso": curr.isoformat(),
                    "end_iso": b_st.isoformat()
                })
        if b_et > curr:
            curr = b_et

    if curr < work_end:
        dur = (work_end - curr).total_seconds() / 60
        if dur >= min_chunk_minutes:
            free_chunks.append({
                "start": curr.strftime("%H:%M"),
                "end": work_end.strftime("%H:%M"),
                "duration_minutes": int(dur),
                "start_iso": curr.isoformat(),
                "end_iso": work_end.isoformat()
            })

    return free_chunks


def check_floor_room_availability(
    date_str: str,
    start_time: str,
    end_time: str,
    floor: int = OFFICE_PRIMARY_FLOOR,
    room_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query real-time availability for all MBC2 rooms on a given floor for a requested time window.
    """
    if not date_str or str(date_str).lower() in ("today", "now"):
        date_str = datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    elif str(date_str).lower() == "tomorrow":
        date_str = (datetime.now(SGT_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

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

    rooms = list(MBC2_ROOM_CATALOG.get(floor, []))
    if room_type and room_type.lower() != "all":
        rooms = [r for r in rooms if r.get("type") == room_type.lower()]

    try:
        service = get_calendar_service()
        body = {
            "timeMin": start_iso,
            "timeMax": end_iso,
            "items": [{"id": r["email"]} for r in rooms]
        }
        res = service.freebusy().query(body=body).execute()
        avail = []
        occupied = []
        for r in rooms:
            busy = res.get("calendars", {}).get(r["email"], {}).get("busy", [])
            item = {
                "name": r["name"],
                "type": r["type"],
                "capacity": r["capacity"]
            }
            if not busy:
                avail.append(item)
            else:
                occupied.append(item)

        avail_names = [r["name"].replace("SG-SIN-MBC2-29-B-B80 ", "").replace("SG-SIN-MBC2-28-B-B80 ", "").replace("SG-SIN-MBC2-30-B-B80 ", "") for r in avail]
        summary = (
            f"On Level {floor} for {st_norm} – {et_norm} SGT on {date_str}: "
            f"{len(avail)} available ({', '.join(avail_names) if avail_names else 'none'}), "
            f"{len(occupied)} occupied."
        )
        return {
            "status": "SUCCESS",
            "floor": floor,
            "date": date_str,
            "time_window": f"{st_norm} – {et_norm} SGT",
            "available_count": len(avail),
            "available_rooms": avail,
            "occupied_rooms": occupied,
            "summary": summary
        }
    except Exception as e:
        logger.error("Error querying floor room availability: %s", e)
        return {
            "status": "ERROR",
            "floor": floor,
            "date": date_str,
            "error": str(e),
            "available_rooms": [],
            "occupied_rooms": [],
            "summary": f"Unable to retrieve room availability due to Google Calendar API error: {e}"
        }


def book_mbc_room_for_chunk(
    date_str: str,
    start_time: str,
    end_time: str,
    preferred_floor: int = OFFICE_PRIMARY_FLOOR,
    room_type: str = "phone_booth"
) -> Dict[str, Any]:
    """
    Verify room availability and directly book a verified room in Google Singapore MBC2
    by creating an event on Abhi Sethi's primary Google Calendar with the room resource attached.
    """
    # Normalize date
    if not date_str or str(date_str).lower() in ("today", "now"):
        date_str = datetime.now(SGT_TZ).strftime("%Y-%m-%d")
    elif str(date_str).lower() == "tomorrow":
        date_str = (datetime.now(SGT_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    if "T" in str(start_time):
        start_iso = _to_rfc3339(start_time)
        end_iso = _to_rfc3339(end_time)
        st_label = start_iso.split("T")[1][:5]
        et_label = end_iso.split("T")[1][:5]
    else:
        st_norm = normalize_time_str(start_time)
        et_norm = normalize_time_str(end_time)
        # In business hours, hour 1..6 defaults to PM unless AM explicitly stated
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
        st_label = st_norm
        et_label = et_norm

    # 1. Check real availability across verified rooms
    available_room = find_available_mbc_room(preferred_floor, start_iso, end_iso, room_type)
    if not available_room:
        return {
            "status": "UNAVAILABLE",
            "floor": preferred_floor,
            "date": date_str,
            "time_block": f"{st_label} – {et_label} SGT",
            "message": f"No phone or meeting rooms on Level {preferred_floor} (or adjacent floors) are available for {st_label} – {et_label} SGT."
        }

    # 2. Directly create the event in Abhi Sethi's primary calendar with room resource
    event_body = {
        "summary": f"Focus Work & Calls: {available_room['name']}",
        "description": (
            f"Reserved by Agenica S on behalf of {PRINCIPAL_NAME} ({PRINCIPAL_EMAIL}).\n"
            f"Location: {OFFICE_LOCATION}, Level {preferred_floor}\n"
            f"Room: {available_room['name']}\n"
            f"Purpose: Dedicated focus work and private calls."
        ),
        "start": {"dateTime": start_iso, "timeZone": DEFAULT_TIMEZONE},
        "end": {"dateTime": end_iso, "timeZone": DEFAULT_TIMEZONE},
        "location": f"{OFFICE_LOCATION}, Level {preferred_floor} — {available_room['name']}",
        "attendees": [
            {"email": PRINCIPAL_EMAIL, "displayName": PRINCIPAL_NAME, "responseStatus": "accepted"},
            {"email": available_room["email"], "displayName": available_room["name"], "resource": True}
        ]
    }

    try:
        service = get_calendar_service()
        created = service.events().insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all"
        ).execute()

        event_id = created.get("id")
        html_link = created.get("htmlLink")

        return {
            "status": "RESERVED",
            "event_id": event_id,
            "room_name": available_room["name"],
            "floor": preferred_floor,
            "building": BUILDING_CODE,
            "date": date_str,
            "time_block": f"{st_label} – {et_label} SGT",
            "calendar_link": html_link,
            "message": f"Successfully created event on your Google Calendar and reserved {available_room['name']} for {st_label} – {et_label} SGT."
        }
    except Exception as e:
        logger.error("Direct calendar event creation failed: %s", e)
        return {
            "status": "FAILED",
            "room_name": available_room["name"],
            "error": str(e),
            "message": f"Failed to book {available_room['name']} due to calendar API error: {e}"
        }


def reserve_daily_focus_rooms(
    target_date: str,
    floor: int = OFFICE_PRIMARY_FLOOR
) -> str:
    """
    Scan Abhi Sethi's calendar for large open chunks of the day, verify room availability,
    and directly book verified rooms on Level 29 in MBC2 Singapore into his primary Google Calendar.

    Args:
        target_date: Date in YYYY-MM-DD format (e.g. '2026-09-04').
        floor: Preferred floor number (default: 29).

    Returns:
        JSON string containing the list of reserved rooms, time blocks, and calendar links.
    """
    chunks = find_daily_focus_chunks(target_date)
    reservations = []

    for c in chunks:
        res = book_mbc_room_for_chunk(
            date_str=target_date,
            start_time=c["start"],
            end_time=c["end"],
            preferred_floor=floor,
            room_type="phone_booth" if c.get("duration_minutes", 0) <= 120 else "focus_room"
        )
        reservations.append(res)

    summary_lines = [
        f"🏢 **Workspace Reserved: {OFFICE_LOCATION} — Level {floor}**",
        f"**Date:** {target_date}",
        ""
    ]
    for r in reservations:
        if r.get("status") == "RESERVED":
            summary_lines.append(
                f"- ✅ **{r['room_name']}** (Level {r['floor']}): `{r['time_block']}` [📅 View Event]({r['calendar_link']})"
            )
        elif r.get("status") == "UNAVAILABLE":
            summary_lines.append(
                f"- ⚠️ `{r['time_block']}`: All Level {floor} rooms currently occupied."
            )
        else:
            summary_lines.append(
                f"- ❌ `{r.get('time_block', '')}`: Booking failed ({r.get('error', 'unknown error')})"
            )

    return json.dumps({
        "status": "SUCCESS",
        "target_date": target_date,
        "floor": floor,
        "building": BUILDING_CODE,
        "reservation_count": sum(1 for r in reservations if r.get("status") == "RESERVED"),
        "reservations": reservations,
        "summary": "\n".join(summary_lines)
    }, indent=2)
