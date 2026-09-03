"""
Configuration settings for Agenica S - Executive Assistant Agent.
"""

import os
from dataclasses import dataclass

# Principal Identity
PRINCIPAL_NAME = os.environ.get("PRINCIPAL_NAME", "Abhi Sethi")
PRINCIPAL_EMAIL = os.environ.get("PRINCIPAL_EMAIL", "aset@google.com")
DEFAULT_TIMEZONE = os.environ.get("USER_TIMEZONE", "Asia/Singapore")

# Agent Identity & Branding
AGENT_NAME = "Agenica S"
AGENT_DISPLAY_NAME = f"Agenica S (EA to {PRINCIPAL_NAME})"
AGENT_EMAIL = os.environ.get("AGENT_EMAIL", "agenica@google.com")
DELEGATE_AGENT_EMAIL = os.environ.get("DELEGATE_AGENT_EMAIL", "corpagent-eng-aset@google.com")
CALENDAR_TARGET = os.environ.get("CALENDAR_TARGET", PRINCIPAL_EMAIL)
AGENT_ACCESS_PORTAL = "http://an/groupagent-agenica"

# Office & Location Defaults (Google Singapore MBC2)
OFFICE_LOCATION = "Google Singapore MBC2 (Mapletree Business City II)"
OFFICE_PRIMARY_FLOOR = 29
OFFICE_FALLBACK_FLOORS = [28, 30]
BUILDING_CODE = "SIN-MBC2"

# Official Signature
AGENT_SIGNATURE = f"""--
{AGENT_NAME}
Executive Assistant to {PRINCIPAL_NAME}
Google Workspace Executive Assistant Agent
{AGENT_EMAIL}"""

# Default Model (gemini-2.5-flash for reliable high quota, or gemini-3.7-flash)
DEFAULT_MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

# Google Cloud Settings
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "cowork-aset-6tnf0w")
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"


@dataclass(frozen=True)
class ExecutiveBrandTheme:
    """Executive branding palette and typography for Slide Decks & Briefing Memos."""
    PRIMARY_COLOR: str = "#002B49"       # Executive Deep Navy
    SECONDARY_COLOR: str = "#1A73E8"     # Google / Royal Blue
    ACCENT_COLOR: str = "#00A3E0"        # Vibrant Cyan
    LIGHT_BG: str = "#F8F9FA"            # Off-white background
    TEXT_DARK: str = "#202124"           # Charcoal body text
    WHITE: str = "#FFFFFF"               # Crisp white
    PRIMARY_FONT: str = "Arial"
    ASPECT_RATIO: str = "16:9"
    WIDTH_PT: int = 720
    HEIGHT_PT: int = 405


BRAND_THEME = ExecutiveBrandTheme()
