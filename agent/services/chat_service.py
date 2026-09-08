"""
Google Chat Service & HITL Approval Engine for Agenica S.
Supports Incoming Webhooks, Cards v2 payloads, gchat CLI fallback, and in-portal approval events.
"""

import os
import json
import logging
import urllib.request
import urllib.error
import subprocess
import shutil
from typing import Dict, List, Optional, Any

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    AGENT_NAME,
    AGENT_EMAIL,
)
from .auth_service import AuthService

logger = logging.getLogger("agenica.services.chat")


class ChatService:
    """Enterprise Google Chat Notification & HITL Approval Service."""

    _instance = None

    def __init__(self):
        self.auth_service = AuthService.get_instance()
        self.webhook_url = (
            os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")
            or os.environ.get("CHAT_WEBHOOK_URL")
        )

    @classmethod
    def get_instance(cls) -> "ChatService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def build_cards_v2_payload(
        self,
        title: str,
        subtitle: str,
        recipient: str,
        subject: str,
        body_preview: str,
        draft_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct Google Chat Cards v2 payload conforming to official Google Workspace specifications."""
        buttons = []
        if draft_url:
            buttons.append({
                "text": "Open & Review in Gmail ↗",
                "icon": {"knownIcon": "EMAIL"},
                "color": {"red": 0.1, "green": 0.45, "blue": 0.91, "alpha": 1.0},
                "onClick": {"openLink": {"url": draft_url}},
            })

        return {
            "cardsV2": [
                {
                    "cardId": f"approval-{int(os.times().system * 1000)}",
                    "card": {
                        "header": {
                            "title": title,
                            "subtitle": subtitle,
                            "imageUrl": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/shield_person/default/48px.svg",
                            "imageType": "CIRCLE",
                        },
                        "sections": [
                            {
                                "header": "Outbound Email Summary",
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "topLabel": "Recipient",
                                            "text": f"<b>{recipient}</b>",
                                            "startIcon": {"knownIcon": "MEMBERSHIP"},
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Subject",
                                            "text": f"<b>{subject}</b>",
                                            "startIcon": {"knownIcon": "DESCRIPTION"},
                                        }
                                    },
                                    {
                                        "textParagraph": {
                                            "text": f"<i>Body excerpt:</i>\n{body_preview[:300]}..."
                                        }
                                    },
                                ],
                            },
                            {
                                "header": "Human-In-The-Loop (HITL) Authorization",
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "topLabel": "Guardrail Status",
                                            "text": "⚠️ <b>Awaiting Explicit Approval</b> — Direct send is gated.",
                                            "startIcon": {"knownIcon": "STAR"},
                                        }
                                    },
                                    {"buttonList": {"buttons": buttons}},
                                ],
                            },
                        ],
                    },
                }
            ]
        }

    def send_approval_request(
        self,
        recipient: str,
        subject: str,
        body: str,
        draft_id: Optional[str] = None,
        draft_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch approval request across available Google Chat channels:
        1. Google Chat Incoming Webhook (if configured via GOOGLE_CHAT_WEBHOOK_URL)
        2. gchat CLI fallback (if available locally)
        3. Google Chat REST API (if scopes permitted)
        """
        title = "Approval Required: Outbound Email"
        subtitle = f"{AGENT_NAME} • Executive Assistant to {PRINCIPAL_NAME}"
        draft_link = draft_url or f"https://mail.google.com/mail/u/{PRINCIPAL_EMAIL}/#drafts"
        plain_text = (
            f"🔔 **{title}**\n\n"
            f"- **Recipient:** `{recipient}`\n"
            f"- **Subject:** {subject}\n"
            f"- **Preview:** {body[:250]}...\n\n"
            f"🔗 [Open & Review Draft in Gmail]({draft_link})\n\n"
            f"_Reply 'Yes, send it' to approve, or click the link above._"
        )

        delivery_channel = "in_app_card"
        webhook_status = "unconfigured"

        # Channel 1: Webhook
        if self.webhook_url:
            try:
                payload = self.build_cards_v2_payload(
                    title=title,
                    subtitle=subtitle,
                    recipient=recipient,
                    subject=subject,
                    body_preview=body,
                    draft_url=draft_link,
                )
                payload["text"] = plain_text
                req = urllib.request.Request(
                    self.webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json; charset=UTF-8"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status in (200, 201):
                        delivery_channel = "google_chat_webhook"
                        webhook_status = "delivered"
            except Exception as e:
                logger.warning("Webhook dispatch failed: %s", e)
                webhook_status = f"failed: {e}"

        # Channel 2: Google Chat REST API (if OAuth token has chat scopes)
        if delivery_channel == "in_app_card":
            try:
                chat_svc = self.auth_service.get_chat_service()
                space_name = f"users/{PRINCIPAL_EMAIL.split('@')[0]}"
                payload = self.build_cards_v2_payload(
                    title=title,
                    subtitle=subtitle,
                    recipient=recipient,
                    subject=subject,
                    body_preview=body,
                    draft_url=draft_link,
                )
                payload["text"] = plain_text
                res = chat_svc.spaces().messages().create(parent=space_name, body=payload).execute()
                delivery_channel = "google_chat_api"
            except Exception:
                pass

        return {
            "status": "approval_dispatched",
            "channel": delivery_channel,
            "webhook_status": webhook_status,
            "recipient": recipient,
            "subject": subject,
            "draft_id": draft_id,
            "draft_url": draft_link,
            "plain_text": plain_text,
            "message": (
                f"I've drafted that email to {recipient} regarding '{subject}' and requested your approval. "
                f"Review in Gmail drafts or confirm to send."
            ),
        }
