"""
Content Creator Specialized Subagent for Agenica S.
"""

from typing import Dict, Any, List, Optional
import json
from ..config import DEFAULT_MODEL, PRINCIPAL_NAME, PRINCIPAL_EMAIL, AGENT_NAME
from ..tools import (
    create_presentation_deck,
    create_executive_briefing_doc,
    search_drive_files,
)

CONTENT_CREATOR_INSTRUCTIONS = f"""
You are the `content_creator` specialized subagent for {AGENT_NAME} (EA to {PRINCIPAL_NAME}).

Your responsibilities:
1. **Executive 16:9 Slide Decks**:
   - Generate widescreen presentations adhering to executive styling (Deep Navy `#002B49`, Royal Blue `#1A73E8`, Vibrant Cyan `#00A3E0`).
   - Provide bespoke, tailored speaker notes for **every single slide**.
   - Output 1-click Google Slides creation and Drive review links (`create_presentation_deck`).
2. **Executive Briefing Memos & Decision Papers**:
   - Structure strategic briefing documents in Google Docs with Context, Strategic Objectives, Discussion Items, and Recommendations (`create_executive_briefing_doc`).
3. **Grounded Review Tags**:
   - Explicitly tag preliminary metrics, dependencies, or unconfirmed points:
     - `[NEEDS HUMAN REVIEW: specific detail to verify]`
     - `[ASSUMPTION: detail assumed from context]`
4. **Handoff to Inbox Helper**:
   - Once slide decks or briefing docs are prepared, proactively coordinate with `inbox_helper` to draft an email sharing the materials.
"""


class ContentCreatorSubagent:
    """Subagent handling presentation slide deck generation, executive briefing docs, and speaker notes."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.name = "content_creator"
        self.model_name = model_name
        self.instructions = CONTENT_CREATOR_INSTRUCTIONS

    def build_slide_deck(
        self,
        topic: str,
        subtitle: str = "Executive Strategy & Action Plan",
        slide_count: int = 5,
        custom_slides: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Create executive 16:9 presentation deck with speaker notes and 1-click Slides link."""
        return create_presentation_deck(
            topic=topic,
            subtitle=subtitle,
            slide_count=slide_count,
            custom_slides=custom_slides
        )

    def build_briefing_doc(
        self,
        title: str,
        topic: str,
        attendees: Optional[List[str]] = None,
        executive_summary: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        gaps: Optional[List[str]] = None,
        recommended_actions: Optional[List[str]] = None
    ) -> str:
        """Create structured executive briefing memo in Google Docs."""
        return create_executive_briefing_doc(
            title=title,
            topic=topic,
            attendees=attendees,
            executive_summary=executive_summary,
            key_points=key_points,
            assumptions=assumptions,
            gaps=gaps,
            recommended_actions=recommended_actions
        )
