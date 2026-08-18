"""
Contact and Audience Classification Tools for Ms. Agenica S.
"""

from typing import Dict, Any, List
import re
import json

# Known external partner domain keywords
KNOWN_EXTERNAL_PARTNER_PATTERNS = [
    r"flinders\.edu\.au",
    r"dict\.gov",
    r"rch\.org\.au",
    r"health\.gov",
    r"unimelb\.edu\.au",
    r"monash\.edu",
]


def classify_contact(email: str) -> str:
    """
    Classify whether a contact/sender is an Internal Googler or an External Partner,
    and determine the mandatory processing protocol.

    Args:
        email: Email address of the sender or recipient (e.g. 'colleague@google.com', 'partner@flinders.edu.au').

    Returns:
        JSON string indicating audience type ('INTERNAL_GOOGLER' or 'EXTERNAL_PARTNER')
        and the required action protocol ('FULL_AUTONOMOUS_WITH_HITL' or 'DRAFT_DELEGATE_PROTOCOL').
    """
    email_clean = email.strip().lower()
    
    if email_clean.endswith("@google.com"):
        res = {
            "email": email_clean,
            "audience": "INTERNAL_GOOGLER",
            "protocol": "FULL_AUTONOMOUS_WITH_HITL",
            "description": "Internal Googler. Allowed direct email responses from agenica@google.com and calendar event creation upon Google Chat HITL approval."
        }
    else:
        # Check if matched known partner or general external
        is_known_partner = any(re.search(p, email_clean) for p in KNOWN_EXTERNAL_PARTNER_PATTERNS)
        res = {
            "email": email_clean,
            "audience": "EXTERNAL_PARTNER",
            "is_known_vip_partner": is_known_partner,
            "protocol": "DRAFT_DELEGATE_PROTOCOL",
            "description": "External Contact/Partner. MUST use Draft-Delegate Protocol: create a pending Gmail draft under aset@google.com signed as Ms. Agenica S and send a 1-click review link in Google Chat."
        }
        
    return json.dumps(res, indent=2)


def get_contact_directory_info(identifier: str) -> str:
    """
    Look up contact details, title, and organization for a given person or email address.

    Args:
        identifier: Name or email address (e.g., 'Abhi Sethi', 'alice@google.com').
    """
    id_clean = identifier.strip().lower()
    if "abhi" in id_clean or "aset" in id_clean:
        return json.dumps({
            "name": "Abhi Sethi",
            "email": "aset@google.com",
            "title": "Principal / Leader",
            "organization": "Google",
            "timezone": "America/Los_Angeles",
            "assistant": "Ms. Agenica S (agenica@google.com)"
        }, indent=2)
    elif id_clean.endswith("@google.com"):
        username = id_clean.split("@")[0]
        return json.dumps({
            "name": username.capitalize(),
            "email": id_clean,
            "organization": "Google",
            "audience": "INTERNAL_GOOGLER"
        }, indent=2)
    else:
        return json.dumps({
            "identifier": identifier,
            "organization": "External",
            "audience": "EXTERNAL_PARTNER"
        }, indent=2)
