"""
Agenica S — Production FastAPI Gateway & Gemini Multimodal Live Server.
Modular, high-performance, asynchronous entrypoint for live audio and web services.
Hardened with security headers, origin validation, access gatekeeping, and lightweight logging.
"""

import os
import hmac
import logging
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from agent.config import AGENICA_ACCESS_KEY
from agent.live import LiveSessionManager
from agent.services.auth_service import AuthService

# Lightweight production logging (suppress non-critical spam)
log_level_name = os.environ.get("LOG_LEVEL", "WARNING").upper()
log_level = getattr(logging, log_level_name, logging.WARNING)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agenica.server")

app = FastAPI(
    title="Agenica S",
    description="Executive Assistant Live Voice Portal",
    version="2.2.0",
    docs_url=None,   # Disable interactive docs in production to prevent schema scraping
    redoc_url=None,
    openapi_url=None,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject production HTTP security headers on all web responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "microphone=(self)"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' wss: ws: https:; "
            "img-src 'self' data: https:;"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Mount static frontend assets
WEB_DIR = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

session_manager = LiveSessionManager()


def is_origin_allowed(origin_header: str, host_header: str) -> bool:
    """Verify origin to prevent Cross-Site WebSocket Hijacking (CSWSH)."""
    if not origin_header:
        return True
    parsed = urlparse(origin_header)
    origin_netloc = parsed.netloc.lower()
    host_clean = host_header.split(":")[0].lower() if host_header else ""

    # Allow localhost, same-host, or Google Cloud Run host
    if origin_netloc.startswith("localhost") or origin_netloc.startswith("127.0.0.1"):
        return True
    if host_clean and (origin_netloc == host_clean or origin_netloc.startswith(host_clean)):
        return True
    if origin_netloc.endswith(".run.app") or origin_netloc.endswith(".google.com"):
        return True
    return False


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve single-page voice assistant portal."""
    index_file = WEB_DIR / "index.html"
    return FileResponse(str(index_file))


@app.get("/api/auth/status")
def get_auth_status():
    """Report whether access key authentication is enabled."""
    return {"auth_required": bool(AGENICA_ACCESS_KEY)}


@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    Bidirectional WebSocket stream between browser audio and Gemini Live API.
    Secured by origin checking and optional access key validation.
    """
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")

    # 1. Cross-Site WebSocket Hijacking Protection
    if not is_origin_allowed(origin, host):
        await websocket.close(code=1008, reason="Unauthorized origin")
        return

    # 2. Access Key Gatekeeper (if configured)
    if AGENICA_ACCESS_KEY:
        token = websocket.query_params.get("token") or websocket.headers.get("x-access-token") or ""
        if not hmac.compare_digest(token, AGENICA_ACCESS_KEY):
            await websocket.close(code=1008, reason="Unauthorized access key")
            return

    # 3. Delegate to LiveSessionManager
    await session_manager.handle_websocket(websocket)


@app.get("/health")
@app.get("/status")
def health_check():
    """Sanitized, lightweight health probe for Cloud Run and monitoring."""
    auth_svc = AuthService.get_instance()
    auth_ok = True
    try:
        cal = auth_svc.get_calendar_service()
        auth_ok = cal is not None
    except Exception:
        auth_ok = False

    return {
        "status": "healthy" if auth_ok else "degraded",
        "service": "Agenica S Live Assistant",
        "version": "2.2.0",
        "auth_configured": bool(auth_ok),
        "access_gate_enabled": bool(AGENICA_ACCESS_KEY),
    }


def main():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        ws_ping_interval=20,
        ws_ping_timeout=20,
        access_log=False,
    )


if __name__ == "__main__":
    main()
