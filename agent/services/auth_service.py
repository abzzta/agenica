"""
Central Authentication & Client Factory Service for Agenica S.
Handles Google Workspace API credentials, token refresh, and client lifecycle.
"""

import os
import time
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Callable

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import credentials as user_credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource

logger = logging.getLogger("agenica.services.auth")

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


class AuthService:
    """Thread-safe credentials and discovery client factory with connection self-healing."""

    _instance = None
    _lock = threading.Lock()
    _service_cache: Dict[str, Resource] = {}
    _cred_cache: Optional[Tuple[Any, str]] = None

    @classmethod
    def get_instance(cls) -> "AuthService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _safe_refresh(self, creds: Any, max_retries: int = 3) -> bool:
        """Attempt credential refresh with exponential backoff on transport errors."""
        for attempt in range(max_retries):
            try:
                creds.refresh(Request())
                return True
            except Exception as e:
                logger.warning("Token refresh attempt %d/%d encountered error: %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        return False

    def get_credentials(
        self,
        scopes: Optional[List[str]] = None,
        subject: Optional[str] = None
    ) -> Tuple[Any, str]:
        """
        Load credentials for Google Workspace APIs in priority order:
        1. Environment WORKSPACE_CREDENTIALS_JSON (Secret Manager secret)
        2. Authorized User Token JSON file (/secrets/token.json, WORKSPACE_TOKEN_PATH, etc.)
        3. Application Default Credentials (ADC) with quota project
        """
        scopes = scopes or ALL_WORKSPACE_SCOPES
        subject = subject or DEFAULT_PRINCIPAL

        # 0. Raw JSON credentials from environment variable (Secret Manager)
        raw_json = os.environ.get("WORKSPACE_CREDENTIALS_JSON")
        if raw_json:
            try:
                info = json.loads(raw_json)
                c_type = info.get("type")
                if c_type == "authorized_user":
                    creds = user_credentials.Credentials.from_authorized_user_info(info)
                    if hasattr(creds, "refresh") and not creds.valid:
                        self._safe_refresh(creds)
                    if creds and creds.valid:
                        return creds, "env:WORKSPACE_CREDENTIALS_JSON"
                elif c_type == "service_account":
                    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
                    if subject:
                        try:
                            creds = creds.with_subject(subject)
                        except Exception as ex:
                            logger.warning("Domain delegation failed: %s", ex)
                    if hasattr(creds, "refresh") and not creds.valid:
                        self._safe_refresh(creds)
                    if creds:
                        return creds, "env:WORKSPACE_CREDENTIALS_JSON:service_account"
            except Exception as e:
                logger.warning("Failed loading credentials from WORKSPACE_CREDENTIALS_JSON: %s", e)

        # 1. Candidate credential files
        file_candidates = [
            os.environ.get("WORKSPACE_TOKEN_PATH"),
            "/secrets/token.json",
            "/secrets/workspace_token.json",
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
            os.environ.get("SERVICE_ACCOUNT_FILE"),
            os.path.expanduser("~/.config/gcloud/application_default_credentials.json"),
            os.path.expanduser("~/.config/agenica/token.json"),
            os.path.expanduser("~/agenica/token.json"),
        ]
        for path in file_candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    c_type = data.get("type")
                    if c_type == "authorized_user":
                        creds = user_credentials.Credentials.from_authorized_user_info(data)
                        if hasattr(creds, "refresh") and not creds.valid:
                            self._safe_refresh(creds)
                        if creds and creds.valid:
                            return creds, f"authorized_user_file:{path}"
                    elif c_type == "service_account":
                        creds = service_account.Credentials.from_service_account_info(data, scopes=scopes)
                        if subject:
                            try:
                                creds = creds.with_subject(subject)
                            except Exception as ex:
                                logger.warning("Domain-wide delegation subject %s failed: %s", subject, ex)
                        if hasattr(creds, "refresh") and not creds.valid:
                            self._safe_refresh(creds)
                        if creds:
                            return creds, f"service_account:{path}"
                except Exception as e:
                    logger.warning("Failed loading credentials from %s: %s", path, e)

        # 2. Application Default Credentials (ADC) fallback
        try:
            creds, project = google.auth.default()
            quota_proj = os.environ.get("GOOGLE_CLOUD_PROJECT", "ag-test-1310")
            if hasattr(creds, "with_quota_project"):
                creds = creds.with_quota_project(quota_proj)
            if hasattr(creds, "refresh") and not creds.valid:
                self._safe_refresh(creds)
            if creds and creds.valid:
                return creds, f"adc_default:project={project or quota_proj}"
        except Exception as e:
            logger.debug("ADC resolution note: %s", e)

        from google.auth.credentials import AnonymousCredentials
        return AnonymousCredentials(), "anonymous_fallback"

    def invalidate_service(self, service_name: str, version: str):
        """Invalidate cached Google API client so a fresh connection is established."""
        key = f"{service_name}:{version}"
        with self._lock:
            if key in self._service_cache:
                del self._service_cache[key]
                logger.info("Invalidated cached service client for %s", key)

    def reset_cache(self):
        """Purge all cached service clients and credentials."""
        with self._lock:
            self._service_cache.clear()
            self._cred_cache = None

    def get_service(self, service_name: str, version: str, force_new: bool = False) -> Resource:
        """Get or create cached Google API client with automatic freshness validation."""
        key = f"{service_name}:{version}"
        with self._lock:
            if not force_new and key in self._service_cache:
                return self._service_cache[key]

            creds, source = self.get_credentials()
            logger.debug("Building Google API Client '%s' '%s' using %s", service_name, version, source)
            client = build(service_name, version, credentials=creds, cache_discovery=False)
            self._service_cache[key] = client
            return client

    def execute_call(self, service_name: str, version: str, call_fn: Callable[[Resource], Any]) -> Any:
        """Execute Google API request with transparent retry & connection recovery."""
        try:
            service = self.get_service(service_name, version)
            return call_fn(service)
        except Exception as err:
            err_str = str(err).lower()
            if any(term in err_str for term in ["unexpected_eof", "broken pipe", "connection aborted", "token expired", "invalid_grant", "unauthorized", "remote disconnected", "remote end closed"]):
                logger.warning("Transient connection/auth error on %s:%s (%s), refreshing client and retrying...", service_name, version, err)
                self.invalidate_service(service_name, version)
                service = self.get_service(service_name, version, force_new=True)
                return call_fn(service)
            raise

    def get_calendar_service(self) -> Resource:
        return self.get_service("calendar", "v3")

    def get_gmail_service(self) -> Resource:
        return self.get_service("gmail", "v1")

    def get_chat_service(self) -> Resource:
        return self.get_service("chat", "v1")
