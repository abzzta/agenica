"""
Scheduling Assistant Specialized Subagent for Agenica S.
"""

from typing import Dict, Any, List, Optional
import json
from ..config import DEFAULT_MODEL, PRINCIPAL_NAME, PRINCIPAL_EMAIL, AGENT_NAME, OFFICE_LOCATION, OFFICE_PRIMARY_FLOOR
from ..tools import (
    get_current_datetime,
    check_calendar_availability,
    find_next_free_slot,
    create_calendar_event,
    list_upcoming_events,
    check_calendar_clash,
    suggest_meeting_agenda,
    generate_prebooking_proposal,
    find_daily_focus_chunks,
    book_mbc_room_for_chunk,
    reserve_daily_focus_rooms,
)

SCHEDULING_INSTRUCTIONS = f"""
You are the `scheduling_assistant` specialized subagent for {AGENT_NAME} (EA to {PRINCIPAL_NAME}).

Your responsibilities:
1. **Real-World Date Grounding**:
   - ALWAYS call `get_current_datetime` first whenever relative dates ("tomorrow", "next Tuesday", "in 3 days") are mentioned.
   - Anchor all times in Singapore Time (SGT / UTC+8).
2. **Calendar Inquiries & Availability**:
   - Answer schedule queries ("What meetings do I have today?", "Am I free Thursday afternoon?").
3. **Clash Detection & Conflict Resolution**:
   - Verify if proposed slots conflict with existing commitments using `check_calendar_clash`.
   - Proactively suggest alternative slots if a clash is detected.
4. **On-Behalf-Of Invitations**:
   - When creating meetings, dispatch them as {AGENT_NAME} on behalf of {PRINCIPAL_NAME} ({PRINCIPAL_EMAIL}).
   - Always include {PRINCIPAL_NAME} as a confirmed attendee and attach Google Meet.
5. **Office Workspace & Room Booking ({OFFICE_LOCATION})**:
   - When requested to book rooms or phone booths for focus work or calls:
     - Target: Level {OFFICE_PRIMARY_FLOOR} (or nearby Level 28/30) in MBC2 Singapore.
     - Detect open chunks of the day using `find_daily_focus_chunks`.
     - Reserve phone booths or focus rooms using `reserve_daily_focus_rooms` or `book_mbc_room_for_chunk`.
"""


class SchedulingAssistantSubagent:
    """Subagent handling calendar management, clash detection, agenda suggestions, and workspace reservations."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.name = "scheduling_assistant"
        self.model_name = model_name
        self.instructions = SCHEDULING_INSTRUCTIONS

    def check_schedule(self, days: int = 7) -> str:
        """Inspect upcoming schedule for Abhi Sethi."""
        return list_upcoming_events(days=days)

    def propose_meeting(
        self,
        title: str,
        date_str: str,
        start_time: str,
        end_time: str,
        attendees: List[str],
        location: str = "Google Meet / Video Conference (Hybrid)",
        details: Optional[str] = None
    ) -> str:
        """Generate a 1-click calendar proposal card."""
        return generate_prebooking_proposal(
            title=title,
            date_str=date_str,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            location=location,
            details=details
        )

    def book_meeting(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: List[str],
        description: str = "",
        add_meet: bool = True
    ) -> str:
        """Dispatch a calendar invite on behalf of Abhi Sethi."""
        return create_calendar_event(
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            description=description,
            add_meet=add_meet
        )

    def reserve_focus_workspace(
        self,
        date_str: str,
        floor: int = OFFICE_PRIMARY_FLOOR
    ) -> str:
        """Reserve phone/focus rooms in MBC2 Singapore for all open chunks of the day."""
        return reserve_daily_focus_rooms(target_date=date_str, floor=floor)
