"""
Declarative Tool Registry for Gemini Multimodal Live API.
Modular function declarations for real-time calendar, global dynamic room discovery, and Gmail with HITL guardrails.
"""

from typing import List, Dict, Any

LIVE_TOOLS: List[Dict[str, Any]] = [
    {
        "function_declarations": [
            {
                "name": "get_current_time",
                "description": "Get current live date, time, and day of week in Singapore Standard Time (SGT).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                },
            },
            {
                "name": "check_calendar_availability",
                "description": "Check if Abhi Sethi is free at a specific date and time on his Google Calendar in SGT.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "date": {
                            "type": "STRING",
                            "description": "Target date in YYYY-MM-DD format (or 'today' / 'tomorrow').",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in HH:MM format (24-hour, SGT).",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in HH:MM format (24-hour, SGT).",
                        },
                    },
                    "required": ["date"],
                },
            },
            {
                "name": "create_calendar_event",
                "description": "Schedule a new meeting on Abhi's primary Google Calendar with Google Meet link.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {
                            "type": "STRING",
                            "description": "Meeting title or topic.",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start datetime in ISO-8601 format (e.g. '2026-09-09T10:00:00+08:00').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End datetime in ISO-8601 format (e.g. '2026-09-09T10:30:00+08:00').",
                        },
                        "attendees": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of participant email addresses.",
                        },
                        "description": {
                            "type": "STRING",
                            "description": "Meeting description or agenda.",
                        },
                    },
                    "required": ["summary", "start_time", "end_time"],
                },
            },
            {
                "name": "check_room_availability",
                "description": (
                    "Dynamically check real-time availability of meeting rooms or phone booths across any Google office "
                    "globally (e.g. Sydney, Melbourne, Tokyo, London, Singapore MBC2, Mountain View, Sunnyvale, Zurich, Dublin). "
                    "You can specify an office/city, floor, building, room name, or room type."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "office": {
                            "type": "STRING",
                            "description": "City or office name, e.g. 'Sydney', 'Melbourne', 'Tokyo', 'London', 'Singapore', 'Mountain View', 'Sunnyvale', 'Zurich', 'Dublin'.",
                        },
                        "building": {
                            "type": "STRING",
                            "description": "Building code or name (e.g. 'AU-SYD-PIR', 'SG-SIN-MBC2', 'UK-LON-CSG', 'JP-TOK-STRM', 'US-MTV').",
                        },
                        "floor": {
                            "type": "INTEGER",
                            "description": "Floor or level number (e.g. 4, 10, 27, 28, 29, 30).",
                        },
                        "room_name": {
                            "type": "STRING",
                            "description": "Specific room name to check (e.g. 'Bayfront', 'Corallum', 'Philosoraptor').",
                        },
                        "room_type": {
                            "type": "STRING",
                            "description": "Type filter: 'phone_booth' or 'meeting_room'.",
                        },
                        "date": {
                            "type": "STRING",
                            "description": "Target date in YYYY-MM-DD format (or 'today', 'tomorrow'). Defaults to today.",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in HH:MM format (SGT, e.g. '10:00').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in HH:MM format (SGT, e.g. '11:00').",
                        },
                    },
                },
            },
            {
                "name": "book_singapore_room",
                "description": (
                    "Reserve a meeting room or phone booth dynamically across any office or floor globally. "
                    "Creates a Google Calendar event with the verified room resource attached and Google Meet link."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "office": {
                            "type": "STRING",
                            "description": "Target office or city (e.g. 'Sydney', 'Tokyo', 'London', 'Singapore').",
                        },
                        "floor": {
                            "type": "INTEGER",
                            "description": "Floor or level (e.g. 4, 10, 28, 29).",
                        },
                        "building": {
                            "type": "STRING",
                            "description": "Building code (default 'SG-SIN-MBC2').",
                        },
                        "room_name": {
                            "type": "STRING",
                            "description": "Specific room name (e.g. 'Bayfront', 'Corallum').",
                        },
                        "room_type": {
                            "type": "STRING",
                            "description": "'meeting_room' or 'phone_booth'.",
                        },
                        "target_date": {
                            "type": "STRING",
                            "description": "Date in YYYY-MM-DD format (or 'today', 'tomorrow').",
                        },
                        "start_time": {
                            "type": "STRING",
                            "description": "Start time in HH:MM format (SGT, e.g. '14:00').",
                        },
                        "end_time": {
                            "type": "STRING",
                            "description": "End time in HH:MM format (SGT, e.g. '15:00').",
                        },
                        "title": {
                            "type": "STRING",
                            "description": "Title for the room reservation.",
                        },
                        "attendees": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Optional additional attendee emails.",
                        },
                    },
                    "required": ["start_time", "end_time"],
                },
            },
            {
                "name": "create_gmail_draft",
                "description": (
                    "Create a pending email draft in Abhi's Gmail account signed officially as Agenica S, "
                    "and dispatch an interactive approval card to Google Chat. "
                    "DOES NOT send the email directly or touch Google Calendar."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "recipient": {
                            "type": "STRING",
                            "description": "Target email address (e.g. 'colleague@google.com').",
                        },
                        "subject": {
                            "type": "STRING",
                            "description": "Email subject line.",
                        },
                        "body": {
                            "type": "STRING",
                            "description": "Main body text of the email message.",
                        },
                    },
                    "required": ["recipient", "subject", "body"],
                },
            },
            {
                "name": "send_email",
                "description": (
                    "Directly send an email via Gmail API to a recipient. "
                    "CRITICAL SAFETY GUARDRAIL: Must have user_confirmed=True. "
                    "If Abhi has not explicitly approved sending, this tool will reject and create a draft instead."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "recipient": {
                            "type": "STRING",
                            "description": "Target email address.",
                        },
                        "subject": {
                            "type": "STRING",
                            "description": "Email subject line.",
                        },
                        "body": {
                            "type": "STRING",
                            "description": "Email message body.",
                        },
                        "user_confirmed": {
                            "type": "BOOLEAN",
                            "description": "Set to True ONLY if Abhi has explicitly confirmed verbal or written approval to send this email now.",
                        },
                    },
                    "required": ["recipient", "subject", "body"],
                },
            },
            {
                "name": "check_mailbox_invites",
                "description": (
                    "Scan Abhi Sethi's Gmail inbox for incoming unread emails, meeting invites, or action items. "
                    "CRITICAL: Always use this tool (NOT calendar tools) when Abhi asks about emails, mailbox, or inbox invites."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "max_results": {
                            "type": "INTEGER",
                            "description": "Maximum number of unread emails to inspect (default 10).",
                        },
                    },
                },
            },
            {
                "name": "search_emails",
                "description": "Search Abhi Sethi's Gmail messages using a query (e.g. sender, subject keyword).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "Gmail search query (e.g. 'from:chris', 'subject:Q3', 'has:attachment').",
                        },
                        "max_results": {
                            "type": "INTEGER",
                            "description": "Max search results to return.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_upcoming_events",
                "description": (
                    "Retrieve events from Abhi's Google Calendar. Supports single days (date_str='Thursday', 'Friday'), "
                    "multi-day horizons (date_str='Thursday and Friday', 'next week', 'this week', 'today', 'tomorrow'), "
                    "specific dates (date_str='2026-09-10'), or date ranges (start_date, end_date). "
                    "ALWAYS call this tool whenever Abhi asks about his schedule or meetings."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "date_str": {
                            "type": "STRING",
                            "description": "Specific day or phrase to check, e.g. 'Thursday', 'Friday', 'Thursday and Friday', 'next week', 'tomorrow', 'today', or '2026-09-10'.",
                        },
                        "start_date": {
                            "type": "STRING",
                            "description": "Optional start date in YYYY-MM-DD format (e.g. '2026-09-10').",
                        },
                        "end_date": {
                            "type": "STRING",
                            "description": "Optional end date in YYYY-MM-DD format (e.g. '2026-09-11').",
                        },
                        "days": {
                            "type": "INTEGER",
                            "description": "Number of days ahead to look (default 7).",
                        },
                        "max_events": {
                            "type": "INTEGER",
                            "description": "Maximum number of events to retrieve (default 30).",
                        },
                        "query": {
                            "type": "STRING",
                            "description": "Optional keyword filter for event topic, participant, or title.",
                        },
                    },
                },
            },
        ]
    }
]
