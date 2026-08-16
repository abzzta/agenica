#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Server for Ms. Agenica S Tools.
Exposes calendar, email, and notification tools via JSON-RPC 2.0 stdio.
"""

import sys
import json
import os

from agent.tools import (
    get_current_datetime,
    classify_contact,
    get_contact_directory_info,
    check_calendar_availability,
    find_next_free_slot,
    create_calendar_event,
    list_upcoming_events,
    search_emails,
    read_email_thread,
    create_gmail_draft,
    send_email_response,
    send_chat_approval_request,
    send_chat_notification,
)

TOOLS_METADATA = [
    {
        "name": "get_current_datetime",
        "description": "Get current real-world date, time, day of the week, timezone, and computed relative dates (today, tomorrow, next weekdays). Call this first for all relative date queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timezone_name": {"type": "string", "default": "America/Los_Angeles"}
            }
        }
    },
    {
        "name": "classify_contact",
        "description": "Classify if contact is Internal Googler (HITL) or External Partner (Draft-Delegate).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to classify"}
            },
            "required": ["email"]
        }
    },
    {
        "name": "check_calendar_availability",
        "description": "Check free/busy status for Abhi Sethi.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "description": "RFC3339 start timestamp"},
                "end_time": {"type": "string", "description": "RFC3339 end timestamp"},
                "email": {"type": "string", "default": "aset@google.com"}
            },
            "required": ["start_time", "end_time"]
        }
    },
    {
        "name": "find_next_free_slot",
        "description": "Find next available meeting slot for Abhi Sethi.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "duration_minutes": {"type": "integer", "default": 30},
                "after_time": {"type": "string"}
            }
        }
    },
    {
        "name": "create_calendar_event",
        "description": "Create a Google Calendar meeting with optional Google Meet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "description": {"type": "string"},
                "add_meet": {"type": "boolean", "default": True}
            },
            "required": ["summary", "start_time", "end_time", "attendees"]
        }
    },
    {
        "name": "create_gmail_draft",
        "description": "Create a pending Gmail draft signed as Ms. Agenica S under Draft-Delegate protocol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to_recipients": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc_recipients": {"type": "array", "items": {"type": "string"}},
                "in_reply_to_message_id": {"type": "string"}
            },
            "required": ["to_recipients", "subject", "body"]
        }
    },
    {
        "name": "send_chat_approval_request",
        "description": "Send HITL approval card or draft review link to Abhi Sethi in Google Chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "proposed_action": {"type": "string"},
                "target_contact": {"type": "string"},
                "draft_url": {"type": "string"}
            },
            "required": ["summary", "proposed_action", "target_contact"]
        }
    }
]


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS_METADATA}
        }
    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        func_map = {
            "get_current_datetime": get_current_datetime,
            "classify_contact": classify_contact,
            "check_calendar_availability": check_calendar_availability,
            "find_next_free_slot": find_next_free_slot,
            "create_calendar_event": create_calendar_event,
            "create_gmail_draft": create_gmail_draft,
            "send_chat_approval_request": send_chat_approval_request,
        }

        if name in func_map:
            try:
                res = func_map[name](**args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(res)}]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Tool '{name}' not found"}
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32600, "message": f"Method '{method}' unsupported"}
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
