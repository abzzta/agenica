"""
Google Calendar Service for Agenica S.
Handles event scheduling, multi-day horizon resolution, clash analysis, and FreeBusy queries.
"""

import os
import re
import logging
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    DEFAULT_TIMEZONE,
    OFFICE_LOCATION,
)
from .auth_service import AuthService

logger = logging.getLogger("agenica.services.calendar")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


class CalendarService:
    """Enterprise Google Calendar Integration Service."""

    _instance = None

    def __init__(self):
        self.auth_service = AuthService.get_instance()

    @classmethod
    def get_instance(cls) -> "CalendarService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def to_rfc3339(dt: datetime) -> str:
        """Convert a datetime object to RFC 3339 string with proper Singapore timezone offset."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SGT_TZ)
        return dt.isoformat()

    @classmethod
    def resolve_time_range(
        cls,
        date_str: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 7,
    ) -> Tuple[str, str, str]:
        """
        Dynamically resolve natural language phrases, relative terms, or explicit dates
        into Singapore SGT RFC 3339 boundaries (timeMin, timeMax, label).
        """
        now_sgt = datetime.now(SGT_TZ)
        today_date = now_sgt.date()

        # 1. Explicit start_date and end_date provided
        if start_date and end_date:
            try:
                s_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, tzinfo=SGT_TZ
                )
                e_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=SGT_TZ
                )
                return cls.to_rfc3339(s_dt), cls.to_rfc3339(e_dt), f"{start_date} to {end_date}"
            except ValueError:
                pass

        if start_date and not end_date:
            try:
                s_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, tzinfo=SGT_TZ
                )
                e_dt = s_dt.replace(hour=23, minute=59, second=59)
                return cls.to_rfc3339(s_dt), cls.to_rfc3339(e_dt), f"{start_date}"
            except ValueError:
                pass

        phrase = (date_str or "").lower().strip()

        # 2. Match specific ISO format inside phrase
        iso_match = re.search(r"\b(202\d-[01]\d-[0-3]\d)\b", phrase)
        if iso_match:
            try:
                d_val = datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
                s_dt = datetime.combine(d_val, datetime.min.time(), tzinfo=SGT_TZ)
                e_dt = datetime.combine(d_val, datetime.max.time(), tzinfo=SGT_TZ)
                return cls.to_rfc3339(s_dt), cls.to_rfc3339(e_dt), d_val.strftime("%A, %d %b %Y")
            except ValueError:
                pass

        # 3. Next Week
        if "next week" in phrase:
            days_ahead = (7 - today_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_monday = today_date + timedelta(days=days_ahead)
            next_sunday = next_monday + timedelta(days=6)
            s_dt = datetime.combine(next_monday, datetime.min.time(), tzinfo=SGT_TZ)
            e_dt = datetime.combine(next_sunday, datetime.max.time(), tzinfo=SGT_TZ)
            return (
                cls.to_rfc3339(s_dt),
                cls.to_rfc3339(e_dt),
                f"Next week ({next_monday.strftime('%d %b')} – {next_sunday.strftime('%d %b')})",
            )

        # 4. This Week / Remainder of Week
        if "this week" in phrase:
            sunday = today_date + timedelta(days=(6 - today_date.weekday()))
            s_dt = now_sgt
            e_dt = datetime.combine(sunday, datetime.max.time(), tzinfo=SGT_TZ)
            return (
                cls.to_rfc3339(s_dt),
                cls.to_rfc3339(e_dt),
                f"This week (through {sunday.strftime('%d %b')})",
            )

        # 5. Compound: "Thursday and Friday"
        if ("thursday" in phrase or "thu" in phrase) and ("friday" in phrase or "fri" in phrase):
            days_to_thu = (3 - today_date.weekday()) % 7
            thu_date = today_date + timedelta(days=days_to_thu)
            fri_date = thu_date + timedelta(days=1)
            s_dt = datetime.combine(thu_date, datetime.min.time(), tzinfo=SGT_TZ)
            e_dt = datetime.combine(fri_date, datetime.max.time(), tzinfo=SGT_TZ)
            return (
                cls.to_rfc3339(s_dt),
                cls.to_rfc3339(e_dt),
                f"Thursday ({thu_date.strftime('%d %b')}) and Friday ({fri_date.strftime('%d %b')})",
            )

        # 6. Single day of week
        weekdays = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }
        for name, target_idx in weekdays.items():
            if re.search(rf"\b{name}\b", phrase):
                days_ahead = (target_idx - today_date.weekday()) % 7
                if days_ahead == 0 and "next" in phrase:
                    days_ahead = 7
                target_date = today_date + timedelta(days=days_ahead)
                s_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=SGT_TZ)
                e_dt = datetime.combine(target_date, datetime.max.time(), tzinfo=SGT_TZ)
                return (
                    cls.to_rfc3339(s_dt),
                    cls.to_rfc3339(e_dt),
                    f"{target_date.strftime('%A')} ({target_date.strftime('%a, %d %b')})",
                )

        # 7. Tomorrow
        if "tomorrow" in phrase:
            t_date = today_date + timedelta(days=1)
            s_dt = datetime.combine(t_date, datetime.min.time(), tzinfo=SGT_TZ)
            e_dt = datetime.combine(t_date, datetime.max.time(), tzinfo=SGT_TZ)
            return (
                cls.to_rfc3339(s_dt),
                cls.to_rfc3339(e_dt),
                f"Tomorrow ({t_date.strftime('%a, %d %b')})",
            )

        # 8. Today / Default rolling window
        if "today" in phrase:
            s_dt = now_sgt
            e_dt = datetime.combine(today_date, datetime.max.time(), tzinfo=SGT_TZ)
            return cls.to_rfc3339(s_dt), cls.to_rfc3339(e_dt), "Today"

        s_dt = now_sgt
        e_dt = now_sgt + timedelta(days=max(1, days))
        return cls.to_rfc3339(s_dt), cls.to_rfc3339(e_dt), f"Next {days} days"

    def list_upcoming_events(
        self,
        date_str: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 7,
        max_events: int = 30,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch calendar events for the resolved date window.
        Returns day-by-day grouped events and natural spoken summaries.
        """
        time_min, time_max, period_label = self.resolve_time_range(
            date_str=date_str,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )

        try:
            list_params: Dict[str, Any] = {
                "calendarId": "primary",
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": min(100, max(max_events, 25)),
            }
            if query:
                list_params["q"] = query

            events_result = self.auth_service.execute_call(
                "calendar", "v3",
                lambda s: s.events().list(**list_params).execute()
            )
            items = events_result.get("items", [])

            processed_events = []
            events_by_day: Dict[str, List[Dict[str, Any]]] = {}

            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                start_raw = start.get("dateTime") or start.get("date")
                end_raw = end.get("dateTime") or end.get("date")

                is_all_day = "date" in start and "dateTime" not in start
                day_key = "Upcoming"
                time_display = "All day"

                if is_all_day:
                    try:
                        d_obj = datetime.strptime(start_raw, "%Y-%m-%d")
                        day_key = d_obj.strftime("%A, %d %b %Y")
                    except Exception:
                        day_key = str(start_raw)
                else:
                    try:
                        dt_start = datetime.fromisoformat(start_raw)
                        dt_start_sgt = dt_start.astimezone(SGT_TZ)
                        dt_end = datetime.fromisoformat(end_raw)
                        dt_end_sgt = dt_end.astimezone(SGT_TZ)
                        day_key = dt_start_sgt.strftime("%A, %d %b %Y")
                        time_display = f"{dt_start_sgt.strftime('%I:%M %p')} – {dt_end_sgt.strftime('%I:%M %p')} SGT"
                    except Exception:
                        time_display = f"{start_raw} to {end_raw}"

                event_summary = {
                    "id": item.get("id"),
                    "summary": item.get("summary", "(No Title)"),
                    "start": start_raw,
                    "end": end_raw,
                    "day": day_key,
                    "time_display": time_display,
                    "location": item.get("location", ""),
                    "is_all_day": is_all_day,
                    "hangoutLink": item.get("hangoutLink", ""),
                    "htmlLink": item.get("htmlLink", ""),
                }
                processed_events.append(event_summary)
                events_by_day.setdefault(day_key, []).append(event_summary)

            # Build concise summary for speech
            if not processed_events:
                spoken_summary = f"You have no meetings scheduled for {period_label}."
            else:
                day_counts = [f"{len(evs)} on {d.split(',')[0]}" for d, evs in events_by_day.items()]
                highlights = [ev["summary"] for ev in processed_events if not ev["is_all_day"]][:3]
                spoken_summary = (
                    f"Found {len(processed_events)} event(s) for {period_label}: "
                    f"{', '.join(day_counts[:4])}. "
                    f"Highlights: {'; '.join(highlights) if highlights else 'All day events'}."
                )

            return {
                "status": "success",
                "period": period_label,
                "time_min": time_min,
                "time_max": time_max,
                "total_events": len(processed_events),
                "summary": spoken_summary,
                "events_by_day": events_by_day,
                "events": processed_events,
            }
        except Exception as e:
            logger.error("Error listing calendar events: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "period": period_label,
                "total_events": 0,
                "summary": f"Could not retrieve calendar events: {e}",
            }

    def check_availability(
        self,
        target_date: str,
        start_time: str = "09:00",
        end_time: str = "18:00",
    ) -> Dict[str, Any]:
        """Query real-time FreeBusy availability for the principal user."""
        try:
            s_dt = datetime.strptime(f"{target_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)
            e_dt = datetime.strptime(f"{target_date} {end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=SGT_TZ)

            body = {
                "timeMin": self.to_rfc3339(s_dt),
                "timeMax": self.to_rfc3339(e_dt),
                "items": [{"id": PRINCIPAL_EMAIL}],
            }
            res = self.auth_service.execute_call(
                "calendar", "v3",
                lambda s: s.freebusy().query(body=body).execute()
            )
            busy_slots = res.get("calendars", {}).get(PRINCIPAL_EMAIL, {}).get("busy", [])

            is_free = len(busy_slots) == 0
            return {
                "status": "success",
                "date": target_date,
                "is_free": is_free,
                "busy_slots": busy_slots,
                "message": (
                    f"You are completely free between {start_time} and {end_time} SGT on {target_date}."
                    if is_free
                    else f"You have {len(busy_slots)} conflicting event(s) on {target_date} during that time."
                ),
            }
        except Exception as e:
            logger.error("Error checking availability: %s", e)
            return {"status": "error", "error": str(e), "is_free": False}

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: Optional[List[str]] = None,
        description: str = "",
        location: str = "",
        include_meet: bool = True,
    ) -> Dict[str, Any]:
        """Create a new Google Calendar event with Google Meet conferencing and notifications."""
        try:
            attendee_list = [{"email": PRINCIPAL_EMAIL, "responseStatus": "accepted"}]
            if attendees:
                for a in attendees:
                    clean_a = a.strip()
                    if clean_a and clean_a not in (PRINCIPAL_EMAIL,):
                        attendee_list.append({"email": clean_a})

            event_body = {
                "summary": summary,
                "description": description or f"Organized by Agenica S for {PRINCIPAL_NAME}",
                "location": location or OFFICE_LOCATION,
                "start": {"dateTime": start_time, "timeZone": DEFAULT_TIMEZONE},
                "end": {"dateTime": end_time, "timeZone": DEFAULT_TIMEZONE},
                "attendees": attendee_list,
            }
            if include_meet:
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meet-{int(datetime.now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            created = self.auth_service.execute_call(
                "calendar", "v3",
                lambda s: s.events().insert(
                    calendarId="primary",
                    body=event_body,
                    conferenceDataVersion=1 if include_meet else 0,
                    sendUpdates="all",
                ).execute()
            )

            meet_link = created.get("hangoutLink", "")
            cal_link = created.get("htmlLink", f"https://calendar.google.com/calendar/u/{PRINCIPAL_EMAIL}/r")

            return {
                "status": "confirmed",
                "id": created.get("id"),
                "summary": created.get("summary"),
                "start": start_time,
                "end": end_time,
                "meet_link": meet_link,
                "calendar_link": cal_link,
                "attendees": [a.get("email") for a in created.get("attendees", [])],
                "message": f"Successfully created event '{summary}' with Google Meet.",
            }
        except Exception as e:
            logger.error("Error creating calendar event: %s", e)
            return {"status": "failed", "error": str(e), "message": f"Could not create calendar event: {e}"}
