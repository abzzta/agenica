"""
Gmail Integration Service for Agenica S.
Handles 4-Tier Inbox Triage, Email Search, Draft Creation, and Sending.
Strict domain separation: all email operations exclusively interact with Gmail.
"""

import os
import base64
import logging
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    AGENT_NAME,
    AGENT_EMAIL,
)
from .auth_service import AuthService

logger = logging.getLogger("agenica.services.gmail")

OFFICIAL_SIGNATURE = f"""--
{AGENT_NAME}
Executive Assistant to {PRINCIPAL_NAME}
{AGENT_EMAIL}"""


class GmailService:
    """Enterprise Gmail API Service."""

    _instance = None

    def __init__(self):
        self.auth_service = AuthService.get_instance()

    @classmethod
    def get_instance(cls) -> "GmailService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def scan_inbox_triage(self, max_results: int = 15) -> Dict[str, Any]:
        """
        Scan unread messages in user's INBOX and categorize by urgency.
        """
        try:
            service = self.auth_service.get_gmail_service()
            res = service.users().messages().list(
                userId="me",
                q="is:unread label:INBOX",
                maxResults=max_results,
            ).execute()

            messages = res.get("messages", [])
            unread_items: List[Dict[str, Any]] = []

            for m in messages:
                msg_data = service.users().messages().get(
                    userId="me",
                    id=m["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()

                headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                snippet = msg_data.get("snippet", "")
                subject = headers.get("Subject", "(No Subject)")
                sender = headers.get("From", "(Unknown Sender)")

                # Urgent triage heuristic
                is_urgent = any(w in subject.lower() or w in snippet.lower() for w in ["urgent", "asap", "action required", "invite", "meeting"])
                unread_items.append({
                    "id": m["id"],
                    "threadId": msg_data.get("threadId"),
                    "from": sender,
                    "subject": subject,
                    "date": headers.get("Date", ""),
                    "snippet": snippet,
                    "tier": "P0_URGENT" if is_urgent else "P2_NORMAL",
                })

            p0_items = [i for i in unread_items if i["tier"] == "P0_URGENT"]
            summary_str = f"Found {len(unread_items)} unread email(s) in your inbox ({len(p0_items)} flagged urgent/action-required)."

            return {
                "status": "success",
                "total_unread": len(unread_items),
                "urgent_count": len(p0_items),
                "summary": summary_str,
                "inbox_url": f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#inbox",
                "emails": unread_items,
            }
        except Exception as e:
            logger.error("Error scanning inbox: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "total_unread": 0,
                "summary": f"Could not scan inbox: {e}",
                "inbox_url": f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#inbox",
            }

    def search_emails(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search user's Gmail using standard Gmail query syntax."""
        try:
            service = self.auth_service.get_gmail_service()
            res = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()

            messages = res.get("messages", [])
            results = []
            for m in messages:
                msg_data = service.users().messages().get(
                    userId="me",
                    id=m["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                results.append({
                    "id": m["id"],
                    "threadId": msg_data.get("threadId"),
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg_data.get("snippet", ""),
                })

            return {
                "status": "success",
                "query": query,
                "total_found": len(results),
                "search_url": f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#search/{query}",
                "emails": results,
            }
        except Exception as e:
            logger.error("Error searching emails: %s", e)
            return {"status": "error", "error": str(e), "total_found": 0, "emails": []}

    def create_draft(
        self,
        recipient: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        notify_chat: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a pending Gmail draft signed with official Agenica S signature.
        Dispatches a HITL approval request to Google Chat.
        Never touches the Google Calendar API.
        """
        try:
            service = self.auth_service.get_gmail_service()
            full_body = f"{body.strip()}\n\n{OFFICIAL_SIGNATURE}"

            mime_msg = MIMEMultipart()
            mime_msg["to"] = recipient
            mime_msg["subject"] = subject
            mime_msg.attach(MIMEText(full_body, "plain"))

            raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            draft_body: Dict[str, Any] = {"message": {"raw": raw}}
            if thread_id:
                draft_body["message"]["threadId"] = thread_id

            draft = service.users().drafts().create(userId="me", body=draft_body).execute()
            draft_id = draft.get("id")
            draft_url = f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#drafts"

            chat_status = "not_notified"
            if notify_chat:
                try:
                    from .chat_service import ChatService
                    chat_res = ChatService.get_instance().send_approval_request(
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        draft_id=draft_id,
                        draft_url=draft_url,
                    )
                    chat_status = chat_res.get("channel", "dispatched")
                except Exception as ex:
                    logger.warning("Chat approval notification failed: %s", ex)

            return {
                "status": "created",
                "draft_id": draft_id,
                "recipient": recipient,
                "subject": subject,
                "draft_url": draft_url,
                "chat_status": chat_status,
                "message": (
                    f"Draft created for {recipient} with subject '{subject}'. "
                    f"Approval request sent to Google Chat. Review in Gmail or confirm to send."
                ),
            }
        except Exception as e:
            logger.error("Error creating draft: %s", e)
            return {"status": "failed", "error": str(e), "message": f"Failed creating draft: {e}"}

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        user_confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Send an email directly through Gmail API.
        MANDATORY SAFETY GUARDRAIL: Requires user_confirmed=True.
        If user_confirmed is False, automatically creates a draft instead and requests approval on Google Chat.
        """
        if not user_confirmed:
            logger.warning("SAFETY GUARDRAIL: Direct email send blocked without user confirmation for %s", recipient)
            draft_res = self.create_draft(recipient=recipient, subject=subject, body=body, thread_id=thread_id, notify_chat=True)
            return {
                "status": "approval_required",
                "guardrail": "EMAIL_SEND_GATED",
                "message": (
                    f"Outbound emails to {recipient} require explicit human confirmation. "
                    f"I have created a draft in your Gmail account and requested approval on Google Chat. "
                    f"Would you like me to go ahead and send it?"
                ),
                "draft_id": draft_res.get("draft_id"),
                "draft_url": draft_res.get("draft_url"),
                "recipient": recipient,
                "subject": subject,
                "requires_confirmation": True,
            }

        try:
            service = self.auth_service.get_gmail_service()
            full_body = f"{body.strip()}\n\n{OFFICIAL_SIGNATURE}"

            mime_msg = MIMEMultipart()
            mime_msg["to"] = recipient
            mime_msg["subject"] = subject
            mime_msg.attach(MIMEText(full_body, "plain"))

            raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            msg_body: Dict[str, Any] = {"raw": raw}
            if thread_id:
                msg_body["threadId"] = thread_id

            sent = service.users().messages().send(userId="me", body=msg_body).execute()
            sent_url = f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#sent"

            return {
                "status": "sent",
                "message_id": sent.get("id"),
                "recipient": recipient,
                "subject": subject,
                "sent_url": sent_url,
                "message": f"Email authorized and sent successfully to {recipient}.",
            }
        except Exception as e:
            logger.error("Error sending email: %s", e)
            return {"status": "failed", "error": str(e), "message": f"Failed sending email: {e}"}
