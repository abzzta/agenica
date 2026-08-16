"""
Configuration settings for Ms. Agenica S - Executive Assistant Agent.
"""

import os

# Principal Identity
PRINCIPAL_NAME = os.environ.get("PRINCIPAL_NAME", "Abhi Sethi")
PRINCIPAL_EMAIL = os.environ.get("PRINCIPAL_EMAIL", "aset@google.com")

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
