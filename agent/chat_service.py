"""
Bidirectional Google Chat Service and Interactive Bot Server for Agenica S.
Receives Google Chat events (1:1 DMs, mentions, interactive card button clicks),
executes queries against the Agenica S agent runtime, and replies in real time.
"""

import os
import sys
import json
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import argparse

from .config import (
    AGENT_NAME,
    AGENT_EMAIL,
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
)
from .agent import _run_query_async, run_query
from .tools.room_booking_tools import reserve_daily_focus_rooms

logger = logging.getLogger("agenica.chat_service")


async def process_chat_event(event: dict) -> dict:
    """
    Process an incoming Google Chat event conforming to official Chat API specifications.
    Handles:
    - ADDED_TO_SPACE
    - MESSAGE
    - CARD_CLICKED
    """
    event_type = event.get("type", "MESSAGE")
    sender_email = event.get("user", {}).get("email", PRINCIPAL_EMAIL)
    sender_name = event.get("user", {}).get("displayName", PRINCIPAL_NAME)

    logger.info("Received Chat Event: %s from %s (%s)", event_type, sender_name, sender_email)

    if event_type == "ADDED_TO_SPACE":
        return {
            "text": (
                f"Hello {sender_name}! I am **{AGENT_NAME}**, Executive Assistant to {PRINCIPAL_NAME}.\n\n"
                f"I am at your service to manage:\n"
                f"• 📅 **Calendar & Scheduling:** Clash detection, on-behalf-of invitations, and thread delegation.\n"
                f"• 🏢 **Office Workspace:** Focus and phone room reservations on Level {OFFICE_PRIMARY_FLOOR} in {OFFICE_LOCATION}.\n"
                f"• 📬 **Inbox Triage:** 4-tier categorization and drafted correspondence.\n"
                f"• 🎨 **Executive Decks & Briefings:** 16:9 slides and Google Docs decision papers.\n\n"
                f"_How may I assist you today?_"
            )
        }

    if event_type == "CARD_CLICKED":
        action = event.get("action", {})
        action_method_name = action.get("actionMethodName") or action.get("function")
        params = {p.get("key"): p.get("value") for p in action.get("parameters", [])}

        if action_method_name == "reserve_mbc_room":
            target_date = params.get("date")
            floor = int(params.get("floor", OFFICE_PRIMARY_FLOOR))
            res_raw = reserve_daily_focus_rooms(target_date=target_date, floor=floor)
            res = json.loads(res_raw)
            return {
                "text": f"✔ **Workspace Reserved Successfully!**\n\n{res.get('summary', '')}"
            }
        elif action_method_name == "set_wfh":
            target_date = params.get("date")
            return {
                "text": f"🏠 Noted, Abhi! I have marked you as **Working From Home (WFH)** on {target_date}. No room bookings will be made."
            }
        elif action_method_name == "set_ooo":
            target_date = params.get("date")
            return {
                "text": f"✈️ Noted, Abhi! I have logged you as **Out of Office (OOO)** on {target_date}."
            }

    # Standard MESSAGE event
    msg_obj = event.get("message", {})
    user_text = msg_obj.get("argumentText") or msg_obj.get("text", "")

    cleaned_text = user_text.replace(f"@{AGENT_NAME}", "").strip()
    if not cleaned_text:
        cleaned_text = "Summarize today's agenda and any inbox items needing my attention."

    logger.info("Executing Agent Query: '%s'", cleaned_text)

    # Route asynchronously through Agenica S ADK agent runtime
    try:
        response_text = await _run_query_async(cleaned_text, user_id=sender_email.split("@")[0])
    except Exception as e:
        logger.error("Error executing query: %s", e, exc_info=True)
        response_text = f"I encountered an issue processing your request: {e}"

    return {
        "text": response_text
    }


def process_chat_event_sync(event: dict) -> dict:
    """Synchronous wrapper for process_chat_event."""
    return asyncio.run(process_chat_event(event))


class ChatWebhookHandler(BaseHTTPRequestHandler):
    """HTTP Handler for standalone HTTP server."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            event = json.loads(body) if body else {}
        except Exception:
            event = {"type": "MESSAGE", "message": {"text": body}}

        reply_payload = process_chat_event_sync(event)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(reply_payload).encode("utf-8"))

    def log_message(self, format, *args):
        return


def run_chat_server(port: int = 8080):
    """Start the Google Chat HTTP webhook server."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, ChatWebhookHandler)
    logger.info("🚀 %s Google Chat Service listening on port %d...", AGENT_NAME, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Chat service.")
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description=f"Run {AGENT_NAME} Google Chat Service")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--test-query", help="Simulate an inbound Google Chat query from Abhi Sethi")

    args = parser.parse_args()

    if args.test_query:
        print("=" * 70)
        print(f"Simulating Google Chat DM from {PRINCIPAL_NAME} ({PRINCIPAL_EMAIL})")
        print(f"Query: {args.test_query}")
        print("=" * 70)
        event = {
            "type": "MESSAGE",
            "user": {"email": PRINCIPAL_EMAIL, "displayName": PRINCIPAL_NAME},
            "message": {"text": args.test_query}
        }
        res = process_chat_event_sync(event)
        print(f"\n{AGENT_NAME} Response:")
        print(res.get("text"))
    else:
        run_chat_server(port=args.port)


if __name__ == "__main__":
    main()
