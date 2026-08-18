"""
Configuration settings for Ms. Agenica S - Executive Assistant Agent.
"""

import os
from dataclasses import dataclass

# Principal Identity
PRINCIPAL_NAME = os.environ.get("PRINCIPAL_NAME", "Abhi Sethi")
PRINCIPAL_EMAIL = os.environ.get("PRINCIPAL_EMAIL", "aset@google.com")
DEFAULT_TIMEZONE = os.environ.get("USER_TIMEZONE", "Australia/Adelaide")

# Agent Identity & Branding
AGENT_NAME = "Ms. Agenica S"
AGENT_DISPLAY_NAME = f"Ms. Agenica S (EA to {PRINCIPAL_NAME})"
AGENT_EMAIL = "agenica@google.com"
AGENT_GROUP_ACCOUNT = "groupagent-agenica@google.com"
AGENT_ACCESS_PORTAL = "http://an/groupagent-agenica"

# Official Signature
AGENT_SIGNATURE = f"""--
{AGENT_NAME}
Executive Assistant to {PRINCIPAL_NAME}
Google Workspace Executive Assistant Agent
{AGENT_EMAIL}"""

# Default Model (gemini-3.7-flash, gemini-3.6-flash, or gemini-2.5-flash)
DEFAULT_MODEL = os.environ.get("ADK_MODEL", "gemini-3.7-flash")

# Google Cloud Settings
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ag-test-1310")
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")


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
