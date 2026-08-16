"""
Tools package for Ms. Agenica S ADK Agent.
"""

from .contact_tools import classify_contact, get_contact_directory_info
from .calendar_tools import (
    get_current_datetime,
    check_calendar_availability,
    find_next_free_slot,
    create_calendar_event,
    list_upcoming_events,
)
from .gmail_tools import (
    search_emails,
    read_email_thread,
    create_gmail_draft,
    send_email_response,
)
from .chat_tools import (
    send_chat_approval_request,
    send_chat_notification,
)

__all__ = [
    "get_current_datetime",
    "classify_contact",
    "get_contact_directory_info",
    "check_calendar_availability",
    "find_next_free_slot",
    "create_calendar_event",
    "list_upcoming_events",
    "search_emails",
    "read_email_thread",
    "create_gmail_draft",
    "send_email_response",
    "send_chat_approval_request",
    "send_chat_notification",
]
