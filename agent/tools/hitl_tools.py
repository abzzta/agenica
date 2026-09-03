"""
Human-In-The-Loop (HITL) Interactive 1-Click Action Cards and Safety Primitives.
"""

from typing import Dict, List, Any, Optional
import urllib.parse
import json


def normalize_time_str(t: str) -> str:
    """Standardize time strings like '4.30pm', '4:30pm', '16:30' into standard 24h 'HH:MM' format."""
    t = str(t).strip().lower()
    is_pm = 'pm' in t or 'p' in t
    is_am = 'am' in t or 'a' in t
    t_clean = t.replace('pm', '').replace('am', '').replace('p', '').replace('a', '').replace('.', ':').strip()
    if ':' in t_clean:
        parts = t_clean.split(':')
        h, m = parts[0], parts[1]
    else:
        h, m = t_clean, '00'
    try:
        h_int = int(h)
    except ValueError:
        h_int = 9
    if is_pm and h_int < 12:
        h_int += 12
    elif is_am and h_int == 12:
        h_int = 0
    return f"{h_int:02d}:{m.zfill(2)[:2]}"


def create_calendar_proposal_card(
    title: str,
    date_str: str,
    start_time: str,
    end_time: str,
    attendees: List[str],
    location: str = "Google Meet / Video Conference (Hybrid)",
    details: Optional[str] = None,
    clash_note: Optional[str] = None,
    timezone_str: str = "Asia/Singapore"
) -> Dict[str, Any]:
    """
    Generate an interactive Pre-Booking Proposal Card with 1-click Google Calendar link.
    """
    st_norm = normalize_time_str(start_time)
    et_norm = normalize_time_str(end_time)

    d_clean = date_str.replace("-", "")
    st_clean = st_norm.replace(":", "")[:4]
    et_clean = et_norm.replace(":", "")[:4]
    dates_param = f"{d_clean}T{st_clean}00/{d_clean}T{et_clean}00"

    valid_emails = [a.strip() for a in attendees if "@" in a]
    event_details = details or f"Organized by Agenica S (EA to Abhi Sethi)."

    cal_params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": dates_param,
        "details": event_details,
        "location": location,
        "ctz": timezone_str,
    }
    if valid_emails:
        cal_params["add"] = ",".join(valid_emails)

    calendar_compose_url = f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(cal_params)}"
    calendar_view_url = "https://calendar.google.com/calendar/r"

    card_lines = [
        "📅 **Meeting Proposal Ready for Review**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• **Title**: {title}",
        f"• **Date & Time**: {date_str} ({st_norm} to {et_norm})",
        f"• **Attendees**: {', '.join(attendees)}",
        f"• **Format / Location**: {location}",
    ]
    if clash_note:
        card_lines.append(f"• **Schedule Notice**: ⚠️ {clash_note}")
    if details:
        card_lines.append(f"• **Agenda / Notes**:\n{details}")
        
    card_lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "👉 **Interactive 1-Click Actions:**",
        f"* [📅 **Open & Edit in Google Calendar**]({calendar_compose_url})",
        f"* [👀 **View Today's Calendar**]({calendar_view_url})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ])

    return {
        "title": title,
        "date": date_str,
        "time": f"{st_norm} to {et_norm}",
        "location": location,
        "attendees": attendees,
        "calendar_compose_url": calendar_compose_url,
        "calendar_view_url": calendar_view_url,
        "card_markdown": "\n".join(card_lines)
    }


def create_draft_review_card(
    recipient: str,
    subject: str,
    body_preview: str,
    draft_url: str,
    protocol: str = "DRAFT_DELEGATE_PROTOCOL"
) -> str:
    """Format an interactive Gmail Draft Review Card."""
    card = f"""✉️ **Gmail Draft Prepared for Review**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **To**: {recipient}
• **Subject**: {subject}
• **Protocol**: `{protocol}`
• **Preview**:
> {body_preview.strip().replace(chr(10), chr(10) + '> ')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👉 **Interactive 1-Click Action:**
* [✉️ **Open & Send Draft in Gmail**]({draft_url})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return card


def create_presentation_card(
    title: str,
    subtitle: str,
    slide_count: int,
    slides_url: str,
    drive_url: str = "https://drive.google.com/drive/u/0/my-drive"
) -> str:
    """Format an interactive Google Slides Deck Card."""
    card = f"""🎨 **Executive Presentation Deck Created**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **Title**: {title}
• **Subtitle**: {subtitle}
• **Format**: 16:9 Widescreen Executive Layout
• **Total Slides**: {slide_count} slides (with speaker notes on every slide)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👉 **Interactive 1-Click Actions:**
* [🎨 **Open Presentation in Google Slides**]({slides_url})
* [📂 **View All Materials in Google Drive**]({drive_url})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return card


def create_briefing_doc_card(
    title: str,
    doc_url: str,
    topic: str,
    sections_count: int
) -> str:
    """Format an interactive Google Docs Briefing Memo Card."""
    card = f"""📄 **Executive Briefing Document Created**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• **Title**: {title}
• **Topic**: {topic}
• **Structure**: {sections_count} structured sections with groundings and review tags
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👉 **Interactive 1-Click Action:**
* [📄 **Open Briefing Document in Google Docs**]({doc_url})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    return card
