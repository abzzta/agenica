"""
Central Authentication Utility for Agenica S Google Workspace & Cloud APIs.

Supports:
1. User OAuth 2.0 Token (via WORKSPACE_TOKEN_PATH or ~/.config/agenica/token.json)
2. Service Account Key with Domain-Wide Delegation (SERVICE_ACCOUNT_FILE or GOOGLE_APPLICATION_CREDENTIALS)
3. Direct Access Token (WORKSPACE_ACCESS_TOKEN or gcloud auth print-access-token)
4. Application Default Credentials (ADC) fallback
"""

import os
import json
import logging
import shutil
import subprocess
from typing import List, Optional, Tuple, Any

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import credentials as user_credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource

logger = logging.getLogger("agenica.auth")

DEFAULT_PRINCIPAL = os.environ.get("PRINCIPAL_EMAIL", "aset@google.com")

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CHAT_SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.bot",
]

CLOUD_PLATFORM_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
]

ALL_WORKSPACE_SCOPES = list(dict.fromkeys(CLOUD_PLATFORM_SCOPES + CALENDAR_SCOPES + GMAIL_SCOPES + CHAT_SCOPES))


def get_workspace_credentials(
    scopes: Optional[List[str]] = None,
    subject: Optional[str] = None
) -> Tuple[Any, str]:
    """
    Load credentials for Google Workspace APIs in priority order:
    1. Authorized User Token JSON file
    2. Service Account Key file (with optional subject delegation)
    3. Explicit Environment Access Token or active gcloud access token
    4. Application Default Credentials (ADC) fallback

    Returns:
        Tuple of (credentials, credential_source_description)
    """
    scopes = scopes or ALL_WORKSPACE_SCOPES
    subject = subject or DEFAULT_PRINCIPAL

    # 1. User OAuth Token file
    token_candidates = [
        os.environ.get("WORKSPACE_TOKEN_PATH"),
        os.path.expanduser("~/.config/agenica/token.json"),
        os.path.expanduser("~/.config/google/token.json"),
        os.path.expanduser("~/agenica/token.json"),
    ]
    for path in token_candidates:
        if path and os.path.isfile(path):
            try:
                creds = user_credentials.Credentials.from_authorized_user_file(path, scopes=scopes)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                if creds and creds.valid:
                    logger.info("Loaded valid User OAuth credentials from %s", path)
                    return creds, f"user_token_file:{path}"
            except Exception as e:
                logger.warning("Failed loading user token from %s: %s", path, e)

    # 2. Service Account Key file
    sa_candidates = [
        os.environ.get("SERVICE_ACCOUNT_FILE"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        os.path.expanduser("~/.config/agenica/service_account.json"),
    ]
    for sa_path in sa_candidates:
        if sa_path and os.path.isfile(sa_path):
            try:
                with open(sa_path, "r", encoding="utf-8") as f:
                    sa_info = json.load(f)
                if sa_info.get("type") == "service_account":
                    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
                    if subject:
                        try:
                            creds = creds.with_subject(subject)
                        except Exception as ex:
                            logger.warning("Domain-wide delegation subject %s failed: %s", subject, ex)
                    if creds:
                        logger.info("Loaded Service Account credentials from %s (subject=%s)", sa_path, subject)
                        return creds, f"service_account:{sa_path}"
            except Exception as e:
                logger.warning("Failed loading service account from %s: %s", sa_path, e)

    # 3. Direct Access Token (Environment variable or gcloud CLI)
    env_token = os.environ.get("WORKSPACE_ACCESS_TOKEN") or os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
    if env_token:
        try:
            creds = user_credentials.Credentials(token=env_token, scopes=scopes)
            return creds, "environment_access_token"
        except Exception as e:
            logger.warning("Failed loading credentials from WORKSPACE_ACCESS_TOKEN: %s", e)

    gcloud_candidates = [
        shutil.which("gcloud"),
        os.path.expanduser("~/google-cloud-sdk/bin/gcloud"),
        "/usr/local/google/home/aset/google-cloud-sdk/bin/gcloud",
        "gcloud"
    ]
    gcloud_bin = next((p for p in gcloud_candidates if p and os.path.exists(p)), "gcloud")

    try:
        tok = subprocess.check_output(
            [gcloud_bin, "auth", "print-access-token"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL
        ).strip()
        if tok:
            creds = user_credentials.Credentials(token=tok, scopes=scopes)
            return creds, "gcloud_access_token"
    except Exception:
        pass

    # 4. Fallback to ADC
    try:
        creds, project = google.auth.default(scopes=scopes)
        if creds and creds.expired and hasattr(creds, "refresh"):
            creds.refresh(Request())
        return creds, f"adc_default:project={project}"
    except Exception as e:
        logger.error("All credential resolution strategies failed: %s", e)
        from google.auth.credentials import AnonymousCredentials
        return AnonymousCredentials(), "anonymous_fallback"


def get_calendar_service() -> Resource:
    """Build and return an authorized Google Calendar v3 API client."""
    creds, source = get_workspace_credentials(CALENDAR_SCOPES)
    logger.debug("Building Calendar v3 service using %s", source)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def get_gmail_service() -> Resource:
    """Build and return an authorized Gmail v1 API client."""
    creds, source = get_workspace_credentials(GMAIL_SCOPES)
    logger.debug("Building Gmail v1 service using %s", source)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_chat_service() -> Resource:
    """Build and return an authorized Google Chat v1 API client."""
    creds, source = get_workspace_credentials(CHAT_SCOPES)
    logger.debug("Building Chat v1 service using %s", source)
    return build("chat", "v1", credentials=creds, cache_discovery=False)
