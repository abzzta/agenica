"""
Tools package for Ms. Agenica S ADK Agent.
"""

from .contact_tools import (
    classify_contact,
    get_contact_directory_info,
)
from .calendar_tools import (
    get_current_datetime,
    check_calendar_availability,
    find_next_free_slot,
    create_calendar_event,
    list_upcoming_events,
    check_calendar_clash,
    suggest_meeting_agenda,
    generate_prebooking_proposal,
)
from .gmail_tools import (
    scan_inbox_triage,
    search_emails,
    read_email_thread,
    create_gmail_draft,
    send_email_response,
)
from .chat_tools import (
    send_chat_approval_request,
    send_chat_notification,
)
from .slides_tools import (
    create_presentation_deck,
)
from .docs_tools import (
    create_executive_briefing_doc,
    search_drive_files,
)
from .hitl_tools import (
    create_calendar_proposal_card,
    create_draft_review_card,
    create_presentation_card,
    create_briefing_doc_card,
    normalize_time_str,
)

__all__ = [
    "get_current_datetime",
    "classify_contact",
    "get_contact_directory_info",
    "check_calendar_availability",
    "find_next_free_slot",
    "create_calendar_event",
    "list_upcoming_events",
    "check_calendar_clash",
    "suggest_meeting_agenda",
    "generate_prebooking_proposal",
    "scan_inbox_triage",
    "search_emails",
    "read_email_thread",
    "create_gmail_draft",
    "send_email_response",
    "send_chat_approval_request",
    "send_chat_notification",
    "create_presentation_deck",
    "create_executive_briefing_doc",
    "search_drive_files",
    "create_calendar_proposal_card",
    "create_draft_review_card",
    "create_presentation_card",
    "create_briefing_doc_card",
    "normalize_time_str",
]
