"""
Agenica S — ADK & Vertex AI Agent Package.
Exposes root_agent and app for deployment to Vertex AI Agent Engine (Reasoning Engine)
and registration with Gemini Enterprise App.
"""

from typing import Dict, List, Any, Optional
import os
import sys
import asyncio
import json

# Ensure local imports work across both local and deployed container environments
try:
    from .prompt import AGENT_INSTRUCTIONS
    from .config import DEFAULT_MODEL, AGENT_NAME, AGENT_DISPLAY_NAME
    from .tools import (
        get_current_datetime,
        classify_contact,
        get_contact_directory_info,
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
        scan_inbox_triage,
        search_emails,
        read_email_thread,
        create_gmail_draft,
        send_email_response,
        handle_thread_delegation,
        send_chat_approval_request,
        send_chat_notification,
        build_chat_card_v2,
        build_evening_office_card,
        create_presentation_deck,
        create_executive_briefing_doc,
        search_drive_files,
        create_calendar_proposal_card,
        create_draft_review_card,
        create_presentation_card,
        create_briefing_doc_card,
    )
except (ImportError, ValueError):
    from prompt import AGENT_INSTRUCTIONS
    from config import DEFAULT_MODEL, AGENT_NAME, AGENT_DISPLAY_NAME
    from tools import (
        get_current_datetime,
        classify_contact,
        get_contact_directory_info,
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
        scan_inbox_triage,
        search_emails,
        read_email_thread,
        create_gmail_draft,
        send_email_response,
        handle_thread_delegation,
        send_chat_approval_request,
        send_chat_notification,
        build_chat_card_v2,
        build_evening_office_card,
        create_presentation_deck,
        create_executive_briefing_doc,
        search_drive_files,
        create_calendar_proposal_card,
        create_draft_review_card,
        create_presentation_card,
        create_briefing_doc_card,
    )

ALL_AGENT_TOOLS = [
    get_current_datetime,
    classify_contact,
    get_contact_directory_info,
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
    scan_inbox_triage,
    search_emails,
    read_email_thread,
    create_gmail_draft,
    send_email_response,
    handle_thread_delegation,
    send_chat_approval_request,
    send_chat_notification,
    create_presentation_deck,
    create_executive_briefing_doc,
    search_drive_files,
]

# ---------------------------------------------------------------------------
# ADK Agent Definition with Global Vertex AI Routing
# ---------------------------------------------------------------------------
try:
    from functools import cached_property
    from google.adk.models import Gemini
    from google.adk.agents import Agent
    from google.adk.apps import App
    from google.genai import Client

    class GlobalGemini(Gemini):
        """Custom Gemini model provider that explicitly routes to Vertex AI global location for gemini-3.7-flash."""
        @cached_property
        def api_client(self) -> Client:
            try:
                from .tools.auth import get_workspace_credentials
                creds, _ = get_workspace_credentials(["https://www.googleapis.com/auth/cloud-platform"])
            except Exception:
                creds = None
            return Client(
                vertexai=True,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
                project=os.environ.get("GOOGLE_CLOUD_PROJECT", "cowork-aset-6tnf0w"),
                credentials=creds
            )

    root_agent = Agent(
        name="agenica_agent",
        model=GlobalGemini(model=DEFAULT_MODEL),
        description="Executive Assistant AI Agent managing Google Calendar scheduling, Singapore MBC2 workspace reservations, email thread delegation, 4-tier Gmail triage, 16:9 Google Slides deck generation with speaker notes, Google Docs briefing memos, and Google Chat HITL workflows for Abhi Sethi.",
        instruction=AGENT_INSTRUCTIONS,
        tools=ALL_AGENT_TOOLS
    )

    app = App(name="agenica", root_agent=root_agent)
except ImportError:
    root_agent = None
    app = None

# ---------------------------------------------------------------------------
# ADK CLI Runner & Session Handling
# ---------------------------------------------------------------------------
_session_service = None


def _ensure_runner():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    global _session_service
    if root_agent is None:
        raise RuntimeError("root_agent is not initialized. Ensure google-adk is installed.")
    if _session_service is None:
        _session_service = InMemorySessionService()
    return Runner(app_name="agenica", agent=root_agent, session_service=_session_service)


async def _ensure_session_async(user_id: str, session_id: str):
    try:
        await _session_service.create_session(
            app_name="agenica", user_id=user_id, session_id=session_id
        )
    except Exception:
        pass


async def _run_query_async(query: str, user_id: str = "aset", session_id: str = "session-1") -> str:
    from google.genai import types

    runner = _ensure_runner()
    await _ensure_session_async(user_id, session_id)
    message = types.Content(role="user", parts=[types.Part(text=query)])
    final = ""

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        if not (event.content and event.content.parts):
            continue
        if event.is_final_response() and event.content.parts:
            texts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if texts:
                final = "\n".join(texts)

    return final or "Action completed."


def run_query(query: str, user_id: str = "aset", session_id: str = "session-1") -> str:
    """Execute a single-turn query against Agenica S."""
    return asyncio.run(_run_query_async(query, user_id, session_id))


def _interactive():
    print("=" * 70)
    print("Agenica S — Enterprise Executive Assistant Agent (ADK)")
    print("Identity: agenica@google.com | Principal: Abhi Sethi (aset@google.com)")
    print("Capabilities: 4-Tier Inbox Scan | Clash Detection | MBC2 L29 Rooms | Decks")
    print("Protocols: Internal Googler (HITL) | External Partner (Draft-Delegate)")
    print("Type 'exit' or 'quit' to end session.")
    print("=" * 70)
    while True:
        try:
            q = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            print(f"\nagent > {run_query(q)}")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--interactive":
        _interactive()
    elif argv:
        print(run_query(" ".join(argv)))
    else:
        print('Usage: uv run python -m agent.agent "<request>"  |  --interactive')


if __name__ == "__main__":
    main()
