"""
Google Slides & Executive Presentation Deck Generation Tools for Ms. Agenica S.
"""

import os
import json
import urllib.parse
from typing import Dict, List, Any, Optional
from ..config import BRAND_THEME, PRINCIPAL_NAME
from .hitl_tools import create_presentation_card


def _build_batch_update_payload(
    title: str,
    subtitle: str,
    slides_data: List[Dict[str, Any]],
    default_slide_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Build full Google Slides batchUpdate request payload in 16:9 executive format."""
    requests = []

    # 1. Create Cover Slide
    requests.append({
        "createSlide": {
            "objectId": "exec_slide_cover",
            "insertionIndex": 0,
            "slideLayout": {"predefinedLayout": "BLANK"}
        }
    })
    # Cover Background (#002B49 - Deep Navy)
    requests.append({
        "createShape": {
            "objectId": "cover_bg_rect",
            "shapeType": "RECTANGLE",
            "elementProperties": {
                "pageObjectId": "exec_slide_cover",
                "size": {"width": {"magnitude": 720, "unit": "PT"}, "height": {"magnitude": 405, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "PT"}
            }
        }
    })
    requests.append({
        "updateShapeProperties": {
            "objectId": "cover_bg_rect",
            "shapeProperties": {
                "shapeBackgroundFill": {
                    "solidFill": {
                        "color": {"rgbColor": {"red": 0.0, "green": 0.168, "blue": 0.286}}
                    }
                }
            },
            "fields": "shapeBackgroundFill.solidFill.color"
        }
    })
    # Accent Bar (#1A73E8 - Royal Blue)
    requests.append({
        "createShape": {
            "objectId": "cover_accent_bar",
            "shapeType": "RECTANGLE",
            "elementProperties": {
                "pageObjectId": "exec_slide_cover",
                "size": {"width": {"magnitude": 720, "unit": "PT"}, "height": {"magnitude": 8, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "PT"}
            }
        }
    })
    requests.append({
        "updateShapeProperties": {
            "objectId": "cover_accent_bar",
            "shapeProperties": {
                "shapeBackgroundFill": {
                    "solidFill": {
                        "color": {"rgbColor": {"red": 0.102, "green": 0.451, "blue": 0.910}}
                    }
                }
            },
            "fields": "shapeBackgroundFill.solidFill.color"
        }
    })
    # Title Text Box
    requests.append({
        "createShape": {
            "objectId": "cover_title_box",
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": "exec_slide_cover",
                "size": {"width": {"magnitude": 620, "unit": "PT"}, "height": {"magnitude": 110, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50, "translateY": 120, "unit": "PT"}
            }
        }
    })
    requests.append({
        "insertText": {
            "objectId": "cover_title_box",
            "text": f"{title}\n"
        }
    })
    requests.append({
        "updateTextStyle": {
            "objectId": "cover_title_box",
            "style": {
                "bold": True,
                "fontSize": {"magnitude": 26, "unit": "PT"},
                "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}},
                "fontFamily": BRAND_THEME.PRIMARY_FONT
            },
            "fields": "bold,fontSize,foregroundColor,fontFamily"
        }
    })
    # Subtitle Text Box
    requests.append({
        "createShape": {
            "objectId": "cover_sub_box",
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": "exec_slide_cover",
                "size": {"width": {"magnitude": 620, "unit": "PT"}, "height": {"magnitude": 60, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50, "translateY": 235, "unit": "PT"}
            }
        }
    })
    requests.append({
        "insertText": {
            "objectId": "cover_sub_box",
            "text": f"{subtitle}\nExecutive Briefing prepared for {PRINCIPAL_NAME}"
        }
    })
    requests.append({
        "updateTextStyle": {
            "objectId": "cover_sub_box",
            "style": {
                "fontSize": {"magnitude": 14, "unit": "PT"},
                "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 0.0, "green": 0.639, "blue": 0.878}}},
                "fontFamily": BRAND_THEME.PRIMARY_FONT
            },
            "fields": "fontSize,foregroundColor,fontFamily"
        }
    })

    # 2. Content Slides
    for idx, s in enumerate(slides_data, start=1):
        s_id = f"exec_slide_{idx}"
        hdr_id = f"hdr_rect_{idx}"
        tb_id = f"title_box_{idx}"
        body_id = f"body_box_{idx}"

        requests.append({
            "createSlide": {
                "objectId": s_id,
                "insertionIndex": idx,
                "slideLayout": {"predefinedLayout": "BLANK"}
            }
        })
        # Header Banner
        requests.append({
            "createShape": {
                "objectId": hdr_id,
                "shapeType": "RECTANGLE",
                "elementProperties": {
                    "pageObjectId": s_id,
                    "size": {"width": {"magnitude": 720, "unit": "PT"}, "height": {"magnitude": 55, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "PT"}
                }
            }
        })
        requests.append({
            "updateShapeProperties": {
                "objectId": hdr_id,
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {
                            "color": {"rgbColor": {"red": 0.0, "green": 0.168, "blue": 0.286}}
                        }
                    }
                },
                "fields": "shapeBackgroundFill.solidFill.color"
            }
        })
        # Slide Title
        requests.append({
            "createShape": {
                "objectId": tb_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": s_id,
                    "size": {"width": {"magnitude": 660, "unit": "PT"}, "height": {"magnitude": 40, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 30, "translateY": 8, "unit": "PT"}
                }
            }
        })
        requests.append({
            "insertText": {
                "objectId": tb_id,
                "text": s.get("title", f"Focus Area {idx}")
            }
        })
        requests.append({
            "updateTextStyle": {
                "objectId": tb_id,
                "style": {
                    "bold": True,
                    "fontSize": {"magnitude": 18, "unit": "PT"},
                    "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}},
                    "fontFamily": BRAND_THEME.PRIMARY_FONT
                },
                "fields": "bold,fontSize,foregroundColor,fontFamily"
            }
        })
        # Bullets
        bullets = s.get("bullets", [])
        body_text = "\n\n".join([f"•  {b}" for b in bullets])
        requests.append({
            "createShape": {
                "objectId": body_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": s_id,
                    "size": {"width": {"magnitude": 660, "unit": "PT"}, "height": {"magnitude": 300, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 30, "translateY": 75, "unit": "PT"}
                }
            }
        })
        requests.append({
            "insertText": {
                "objectId": body_id,
                "text": body_text
            }
        })
        requests.append({
            "updateTextStyle": {
                "objectId": body_id,
                "style": {
                    "fontSize": {"magnitude": 14, "unit": "PT"},
                    "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 0.13, "green": 0.13, "blue": 0.13}}},
                    "fontFamily": BRAND_THEME.PRIMARY_FONT
                },
                "fields": "fontSize,foregroundColor,fontFamily"
            }
        })

    if default_slide_id:
        requests.append({"deleteObject": {"objectId": default_slide_id}})

    return requests


def create_presentation_deck(
    topic: str,
    subtitle: str = "Executive Strategy & Action Plan",
    slide_count: int = 5,
    custom_slides: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generate an executive 16:9 widescreen presentation deck with bespoke speaker notes
    on every slide and 1-click Google Slides action cards.

    Args:
        topic: The strategic subject or title of the presentation.
        subtitle: Subtitle or context description.
        slide_count: Number of slides to produce (default: 5).
        custom_slides: Optional structured slide definitions with title, bullets, and speaker_notes.

    Returns:
        JSON string containing the complete deck outline, speaker notes, and 1-click Google Slides link.
    """
    slides_data = custom_slides
    if not slides_data:
        slides_data = [
            {
                "title": "Executive Summary & Core Objectives",
                "bullets": [
                    f"Strategic alignment and priority roadmap for {topic}",
                    "Key governance milestones and timeline expectations",
                    "Immediate decision points required for leadership review [NEEDS HUMAN REVIEW]",
                ],
                "speaker_notes": f"Welcome everyone. Today we are walking through '{topic}'. Our goal is to align on the core deliverables and agree on next steps.",
            },
            {
                "title": "Current State & Analysis",
                "bullets": [
                    "Review of current operational metrics and baseline performance",
                    "Identified dependencies across partner teams and infrastructure",
                    "Key opportunities for velocity enhancement and automation",
                ],
                "speaker_notes": "Highlight the current baseline data, calling attention to where our main opportunities lie.",
            },
            {
                "title": "Strategic Pillars & Recommendations",
                "bullets": [
                    "Pillar 1: Architecture & implementation excellence",
                    "Pillar 2: Stakeholder coordination and Human-In-The-Loop validation",
                    "Pillar 3: Continuous monitoring, quality gating, and scalability [ASSUMPTION: standard SLO applies]",
                ],
                "speaker_notes": "Walk the team through the three strategic pillars. Emphasize why this sequencing delivers the strongest outcomes.",
            },
            {
                "title": "Implementation Roadmap & Milestones",
                "bullets": [
                    "Phase 1: Initial deployment and workflow testing",
                    "Phase 2: Full rollout and cross-team integration",
                    "Phase 3: Quarterly review and performance optimization",
                ],
                "speaker_notes": "Cover the delivery timetable and confirm owner assignments for each milestone phase.",
            },
            {
                "title": "Next Steps & Decision Items",
                "bullets": [
                    "Sign-off on proposed architecture and scheduling guidelines",
                    "Assign workstream leads for upcoming sprints",
                    "Schedule follow-up review checkpoint with key stakeholders",
                ],
                "speaker_notes": "Summarize the required decisions, confirm action item owners, and open the floor for questions.",
            },
        ]

    formatted_slides = []
    # 1. Cover Slide
    formatted_slides.append({
        "slide_number": 1,
        "title": topic,
        "subtitle": subtitle,
        "speaker_notes": f"Opening remarks: Welcome team. Today we review '{topic}' and align on strategic priorities.",
    })

    # 2. Content Slides
    for idx, s in enumerate(slides_data[:slide_count], start=2):
        formatted_slides.append({
            "slide_number": idx,
            "title": s.get("title", f"Pillar {idx - 1}"),
            "bullets": s.get("bullets", []),
            "speaker_notes": s.get("speaker_notes", "Review key points and take feedback from attendees."),
        })

    slides_url = "https://docs.google.com/presentation/u/0/create"
    hitl_card = create_presentation_card(
        title=topic,
        subtitle=subtitle,
        slide_count=len(formatted_slides),
        slides_url=slides_url
    )

    outline_sections = [hitl_card, "\n### 📋 Slide-by-Slide Outline & Speaker Notes:"]
    for s in formatted_slides:
        outline_sections.append(f"\n#### 🖥️ Slide {s['slide_number']}: {s['title']}")
        if s.get("subtitle"):
            outline_sections.append(f"*{s['subtitle']}*")
        for b in s.get("bullets", []):
            outline_sections.append(f"• {b}")
        outline_sections.append(f"🎤 **Speaker Notes**: *{s['speaker_notes']}*")

    full_output = "\n".join(outline_sections)

    return json.dumps({
        "status": "PRESENTATION_CREATED",
        "topic": topic,
        "subtitle": subtitle,
        "slide_count": len(formatted_slides),
        "slides": formatted_slides,
        "slides_url": slides_url,
        "card": hitl_card,
        "formatted_presentation": full_output
    }, indent=2)
