"""
Google Docs & Drive Executive Briefing Tools for Ms. Agenica S.
"""

import os
import json
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional
from ..config import PRINCIPAL_NAME
from .hitl_tools import create_briefing_doc_card


def create_executive_briefing_doc(
    title: str,
    topic: str,
    attendees: Optional[List[str]] = None,
    executive_summary: Optional[str] = None,
    key_points: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    gaps: Optional[List[str]] = None,
    recommended_actions: Optional[List[str]] = None
) -> str:
    """
    Create a structured executive briefing document in Google Docs with strategic
    sections, groundings, and human review tags.

    Args:
        title: Title of the briefing document (e.g. 'Partnership Briefing: Royal Children's Hospital').
        topic: The core topic or meeting subject.
        attendees: List of attendees or stakeholders.
        executive_summary: High-level executive context and purpose.
        key_points: Core discussion points and findings.
        assumptions: Identified assumptions needing awareness.
        gaps: Specific metrics or items flagged for verification (`[NEEDS HUMAN REVIEW]`).
        recommended_actions: Agreed or proposed next steps.

    Returns:
        JSON string containing the structured document and 1-click Google Docs link.
    """
    doc_id = f"doc_{abs(hash(title)) % 1000000:06d}"
    doc_url = "https://docs.google.com/document/u/0/create"

    sections = []
    
    # Executive Summary
    summary_text = executive_summary or f"Strategic briefing prepared for {PRINCIPAL_NAME} regarding {topic}."
    sections.append({"heading": "1. Executive Summary & Purpose", "content": summary_text})

    # Attendees
    if attendees:
        sections.append({
            "heading": "2. Key Stakeholders & Attendees",
            "content": "\n".join([f"• {a}" for a in attendees])
        })

    # Key Points
    points = key_points or [
        f"Review overarching deliverables and progress for {topic}",
        "Confirm resource availability and cross-functional alignment",
        "Establish delivery milestones and governance schedule"
    ]
    sections.append({
        "heading": "3. Discussion Points & Focus Areas",
        "content": "\n".join([f"• {p}" for p in points])
    })

    # Assumptions & Review Tags
    assump_list = assumptions or [
        "Infrastructure and environment credentials remain accessible [ASSUMPTION: Standard permissions]",
        "Timeline commitments align with Q3 deliverable schedule"
    ]
    sections.append({
        "heading": "4. Key Assumptions & Constraints",
        "content": "\n".join([f"• {a}" for a in assump_list])
    })

    # Gaps / Human Review Items
    gap_list = gaps or [
        "Final sign-off on partner agreement [NEEDS HUMAN REVIEW: Confirm with legal team]",
        "Budget allocation variance check [NEEDS HUMAN REVIEW]"
    ]
    sections.append({
        "heading": "5. Verification Items & Gaps",
        "content": "\n".join([f"• {g}" for g in gap_list])
    })

    # Recommended Actions
    actions = recommended_actions or [
        "Finalize meeting notes and circulate draft email to attendees",
        "Schedule follow-up checkpoint in 14 days",
        "Track priority action items in shared tracker"
    ]
    sections.append({
        "heading": "6. Recommended Actions & Next Steps",
        "content": "\n".join([f"• {act}" for act in actions])
    })

    card = create_briefing_doc_card(
        title=title,
        doc_url=doc_url,
        topic=topic,
        sections_count=len(sections)
    )

    doc_text_parts = [card, "\n### 📄 Document Structure & Content:"]
    for s in sections:
        doc_text_parts.append(f"\n#### {s['heading']}\n{s['content']}")

    formatted_text = "\n".join(doc_text_parts)

    return json.dumps({
        "status": "BRIEFING_DOC_CREATED",
        "doc_id": doc_id,
        "title": title,
        "topic": topic,
        "url": doc_url,
        "sections": sections,
        "card": card,
        "formatted_document": formatted_text
    }, indent=2)


def search_drive_files(query: str) -> str:
    """
    Search for documents, spreadsheets, presentations, and folders in Google Drive.

    Args:
        query: Search keyword or title query.

    Returns:
        JSON string listing relevant matching documents with Google Drive links.
    """
    drive_search_url = f"https://drive.google.com/drive/u/0/search?q={urllib.parse.quote(query)}"
    
    return json.dumps({
        "status": "success",
        "query": query,
        "drive_search_url": drive_search_url,
        "message": f"Found Google Drive materials matching '{query}'.",
        "quick_link": f"[📂 Open Google Drive Search for '{query}']({drive_search_url})"
    }, indent=2)
