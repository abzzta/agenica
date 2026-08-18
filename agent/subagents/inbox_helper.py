"""
Inbox Helper Specialized Subagent for Ms. Agenica S.
"""

from typing import Dict, Any, List, Optional
import json
from ..config import DEFAULT_MODEL, PRINCIPAL_NAME, PRINCIPAL_EMAIL, AGENT_NAME
from ..tools import (
    scan_inbox_triage,
    search_emails,
    read_email_thread,
    create_gmail_draft,
    send_email_response,
    send_chat_approval_request,
    classify_contact,
)

INBOX_HELPER_INSTRUCTIONS = f"""
You are the `inbox_helper` specialized subagent for {AGENT_NAME} (EA to {PRINCIPAL_NAME}).

Your responsibilities:
1. **4-Tier Inbox Categorization**:
   - `Needs action`: Flag urgent correspondence with proposed next steps and drafted replies.
   - `Meeting invites`: Check calendar availability and clash status.
   - `Waiting response`: Track sent correspondence awaiting external replies.
   - `FYI`: Provide concise summaries of low-priority informational updates.
2. **Ad-hoc Email Queries**:
   - Answer queries like "Have I had a reply from Flinders on the AI grant?" or "List emails requiring my response".
3. **Draft-Delegate & HITL Protocol**:
   - External Partners: Always create a pending Gmail draft and generate a 1-click review link.
   - Internal Googlers: Draft proposed reply and generate Chat confirmation.
4. **Privacy Gating**: Deterministically exclude and protect confidential matters (HR, legal, compensation).

Style: Warm, composed, executive assistant register. Anticipate next steps without robotic filler.
"""


class InboxHelperSubagent:
    """Subagent handling email triage, drafting, follow-up tracking, and inbox queries."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.name = "inbox_helper"
        self.model_name = model_name
        self.instructions = INBOX_HELPER_INSTRUCTIONS

    def triage_inbox(self, max_results: int = 10) -> str:
        """Run standard 4-tier inbox triage scan."""
        return scan_inbox_triage(max_results=max_results)

    def query_email(self, query_str: str) -> str:
        """Search and analyze emails for specific inquiry."""
        return search_emails(query=query_str)
