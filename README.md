# Ms. Agenica S — Enterprise Executive Assistant (EA) & Gemini Multimodal Live Voice Portal

[![Cloud Run](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run-blue?logo=googlecloud)](https://agenica-assistant-537097709161.us-central1.run.app)
[![Gemini Live API](https://img.shields.io/badge/Gemini%20Live-2.5%20Flash%20Native%20Audio-orange?logo=google)](https://cloud.google.com/vertex-ai)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Google Workspace](https://img.shields.io/badge/Google%20Workspace-Calendar%20%7C%20Gmail%20%7C%20Meet-4285F4?logo=google)](https://workspace.google.com)

**Agenica S** is a production-grade, real-time **Personal Executive Assistant (EA)** and **Multimodal Voice Agent** designed for **Abhi Sethi (`aset@google.com`)**. Powered by Google's **Gemini Multimodal Live API** (`gemini-live-2.5-flash-native-audio`) on Vertex AI, Agenica provides seamless hands-free conversational voice interaction, bidirectional low-latency audio streaming, live speech transcription, real-time Google Workspace operations, and intelligent Singapore office meeting room reservations (Mapletree Business City II - MBC2).

---

## 🌐 Production Cloud Run Deployment

Agenica is deployed live on **Google Cloud Run**:

* **Live Web Portal**: [https://agenica-assistant-537097709161.us-central1.run.app](https://agenica-assistant-537097709161.us-central1.run.app)
* **Direct Service URL**: [https://agenica-assistant-33hogzjfjq-uc.a.run.app](https://agenica-assistant-33hogzjfjq-uc.a.run.app)
* **Live WebSocket Endpoint**: `wss://agenica-assistant-537097709161.us-central1.run.app/ws/live`
* **Healthcheck**: [https://agenica-assistant-537097709161.us-central1.run.app/healthz](https://agenica-assistant-537097709161.us-central1.run.app/healthz)

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Browser (Single-Click Orb Voice UI)"]
        Mic["Microphone Input (16kHz PCM)"]
        AudioCtx["AudioContext (Synchronous Lock & Playback)"]
        UI["Live Orb Visualizer & Dual Transcripts"]
        Cards["Human-In-The-Loop 1-Click Action Cards"]
    end

    subgraph CloudRun ["Google Cloud Run (agenica-assistant)"]
        FastAPI["FastAPI App & Uvicorn ASGI"]
        WSHandler["/ws/live WebSocket Stream Router"]
        AudioBridge["Bidirectional Audio & Session State Engine"]
        ToolExecutor["Autonomous Tool Dispatcher"]
    end

    subgraph VertexAI ["Google Cloud Vertex AI (us-central1)"]
        GeminiLive["Gemini Live API (gemini-live-2.5-flash-native-audio)"]
        Aoede["Aoede Neural Voice (24kHz Native Audio Stream)"]
        VAD["Server-side Voice Activity Detection & Interruption Handler"]
    end

    subgraph WorkspaceAPIs ["Google Workspace & Enterprise Infrastructure"]
        GCal["Google Calendar v3 (freebusy, event insert, Google Meet)"]
        MBC2["Singapore MBC2 Levels 28/29/30 Room Booking System"]
        GMail["Gmail v1 (4-Tier Inbox Triage & Draft Creation)"]
    end

    Mic -->|16kHz PCM Chunks| WSHandler
    WSHandler <--> AudioBridge
    AudioBridge <-->|Bidirectional Session| GeminiLive
    GeminiLive --> Aoede
    Aoede -->|24kHz Audio Stream| WSHandler
    WSHandler -->|Binary PCM Audio| AudioCtx
    WSHandler -->|Real-Time Text Transcripts| UI

    GeminiLive -->|Function Call Event| ToolExecutor
    ToolExecutor --> GCal
    ToolExecutor --> MBC2
    ToolExecutor --> GMail
    GCal -->|Event Created + Meet Link| ToolExecutor
    MBC2 -->|Room Reserved| ToolExecutor
    ToolExecutor -->|Function Response| GeminiLive
    ToolExecutor -->|Action Card JSON| WSHandler
    WSHandler -->|Render Card| Cards
```

---

## ✨ Key Features & Capabilities

### 🎙️ 1. Gemini Multimodal Live API Voice Engine
* **Single-Click Instant Activation**: Synchronously initializes browser `AudioContext` and microphone input on the very first tap of the animated Orb—no double clicks or audio dropouts.
* **Low-Latency Bidirectional Audio Streaming**: 
  * Captures browser microphone audio downsampled to **16kHz mono PCM** and streams binary packets over WebSockets.
  * Receives **24kHz native neural audio** generated directly by Gemini's native audio decoder using the warm, professional voice **"Aoede"**.
* **Continuous Multi-Turn Dialogue with Hands-Free VAD**: Server-side Voice Activity Detection (VAD) automatically handles natural conversational pauses, turn switches, and multi-turn exchanges without requiring push-to-talk.
* **Barge-In Interruption Handling**: Real-time cancellation of audio buffer playback whenever you interrupt or begin speaking mid-sentence.
* **Live Dual Speech Transcription**: Displays both real-time user speech recognition and agent spoken response bubbles simultaneously in the chat feed.

### 📅 2. Google Workspace & Calendar Integration
* **Production-Grade `google-api-python-client`**: Uses authentic Google Calendar v3 Discovery APIs (no CLI workarounds or simulations).
* **Automatic Google Meet Injection**: Dynamically generates and attaches conference links (`meet.google.com/...`) for all scheduled meetings.
* **Timezone Anchoring**: Strictly grounds every relative reference ("today", "tomorrow", "this afternoon", "next Monday") in **Asia/Singapore (SGT / UTC+8)**.
* **Free/Busy Availability Queries**: Checks Abhi's primary calendar (`aset@google.com`) using `freebusy.query` to detect clashes before creating appointments.

### 🏢 3. Singapore MBC2 Office Room Booking Engine
* **MBC2 Level 28, 29, and 30 Coverage**: Intelligent room selector with floor, capacity, and resource mapping across Mapletree Business City II (Singapore).
* **Direct Room Reservation**: Reserves room resources directly onto the primary calendar and outputs direct Google Calendar links.
* **Smart Fallbacks**: Suggests available alternatives on adjacent floors if the requested room is busy.

### ✉️ 4. 4-Tier Inbox Triage & Executive Communication
* **Deterministic Triage**: Scans inbox and classifies messages into `Needs Action`, `Meeting Invites`, `Waiting Response`, and `FYI`.
* **Draft-Delegate Protocol**: Prepares professional executive email drafts in Gmail signed by **Ms. Agenica S** for Abhi's one-click review.

---

## 🛠️ Registered Live Tool Declarations

| Tool Name | Purpose | Parameters |
| :--- | :--- | :--- |
| `get_current_datetime` | Grounds relative time references in Asia/Singapore (SGT) timezone. | `timezone_name` (optional) |
| `list_upcoming_events` | Fetches upcoming appointments from Abhi Sethi's calendar. | `max_results`, `days_ahead` |
| `check_calendar_availability` | Checks free/busy intervals on `aset@google.com` to prevent clashes. | `start_time`, `end_time` |
| `create_calendar_event` | Books a calendar event with attendees, description, and Google Meet. | `summary`, `start_time`, `end_time`, `attendees`, `location` |
| `book_singapore_room` | Checks availability and books an MBC2 Level 28/29/30 room resource. | `summary`, `start_time`, `end_time`, `room_name`, `floor`, `attendees` |

---

## 🚀 Local Development & Quickstart

### Prerequisites
* Python 3.11+
* Google Cloud SDK (`gcloud`) authenticated with access to Vertex AI
* Virtual environment (`venv` or `uv`)

### 1. Installation

```bash
git clone git@github.com:abzzta/agenica.git
cd agenica

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r agent/requirements.txt
```

### 2. Run the Live Voice Web Server Locally

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT="ag-test-1310"
export GOOGLE_CLOUD_LOCATION="us-central1"
export PRINCIPAL_EMAIL="aset@google.com"
export DEFAULT_TIMEZONE="Asia/Singapore"

# Launch server
python web_server.py
```

Open your browser at **`http://localhost:8080`** and click the animated Orb to start speaking!

### 3. Verify Healthcheck

```bash
curl http://localhost:8080/healthz
```

Expected response:
```json
{
  "status": "ok",
  "service": "Gemini Multimodal Live Voice Portal",
  "model": "gemini-live-2.5-flash-native-audio",
  "voice": "Aoede (Native Audio)",
  "multi_turn": true,
  "tools_enabled": true
}
```

---

## ☁️ Cloud Run Deployment Guide

To deploy updates to Google Cloud Run:

```bash
gcloud run deploy agenica-assistant \
  --source . \
  --region us-central1 \
  --project ag-test-1310 \
  --allow-unauthenticated \
  --timeout 3600 \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=ag-test-1310,GOOGLE_CLOUD_LOCATION=us-central1"
```

### Configuration Options:
* `--timeout=3600`: Cloud Run allows up to 3600 seconds (60 minutes) for long-lived WebSocket sessions.
* `--memory=1Gi`: Allocates sufficient memory for high-frequency audio buffer queuing.
* `--allow-unauthenticated`: Enables direct web portal access for authenticated users.

---

## 🔒 Security & Authentication Architecture

1. **User Credentials (Local / Workspace)**: Reads tokens from `~/.config/agenica/token.json` or active `gcloud auth` credentials to interact with Google Workspace APIs on behalf of `aset@google.com`.
2. **Cloud Run Service Account**: The Cloud Run instance runs under `537097709161-compute@developer.gserviceaccount.com` with `roles/aiplatform.user` permission to access Vertex AI Gemini Live API.
3. **Sensitive Email Safeguards**: Executive triage includes deterministic confidential topic masking for privacy-sensitive subjects.

---

## 👥 Persona & Tone

Agenica S speaks with an **unflappable, warm, Australian executive assistant register**:
* Crisp, competent, and discreet.
* Uses direct, natural phrasing ("Right away, Abhi", "I've reserved the room for you on Level 28", "No worries, I'll block that out").
* Avoids robotic filler, excessive emojis, and system log syntax.
