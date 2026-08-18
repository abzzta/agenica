"""
Scheduling Assistant Specialized Subagent for Ms. Agenica S.
"""

from typing import Dict, Any, List, Optional
import json
from ..config import DEFAULT_MODEL, PRINCIPAL_NAME, PRINCIPAL_EMAIL, AGENT_NAME
from ..tools import (
    get_current_datetime,
    check_calendar_availability,
    find_next_free_slot,
    create_calendar_event,
    list_upcoming_events,
    check_calendar_clash,
    suggest_meeting_agenda,
    generate_prebooking_proposal,
)

SCHEDULING_INSTRUCTIONS = f"""
You are the `scheduling_assistant` specialized subagent for {AGENT_NAME} (EA to {PRINCIPAL_NAME}).

Your responsibilities:
1. **Real-World Date Grounding**:
   - ALWAYS call `get_current_datetime` first whenever relative dates ("tomorrow", "next Tuesday", "in 3 days") are mentioned.
2. **Calendar Inquiries & Availability**:
   - Answer schedule queries ("What meetings do I have today?", "Am I free Thursday afternoon?").
3. **Clash Detection & Conflict Resolution**:
   - Verify if proposed slots conflict with existing commitments using `check_calendar_clash`.
   - Proactively suggest alternative slots if a clash is detected.
4. **Pre-Booking Proposal Cards**:
   - Apply executive defaults (Business hours 09:00 - 17:00, Hybrid / Google Meet, 10-minute notification).
   - Generate interactive 1-click Google Calendar proposal cards (`generate_prebooking_proposal`).
5. **Agenda & Material Handoff**:
   - Formulate tailored 3-to-4 point agendas based on meeting context (`suggest_meeting_agenda`).
   - If a meeting requires executive materials (Board review, strategic sync, partnership discussion), proactively trigger or offer `content_creator`.
"""


class SchedulingAssistantSubagent:
    """Subagent handling calendar management, clash detection, agenda suggestions, and pre-booking proposals."""

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
        """Generate structured pre-booking proposal with clash detection and 1-click link."""
        return generate_prebooking_proposal(
            title=title,
            date_str=date_str,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            location=location,
            details=details
        )
