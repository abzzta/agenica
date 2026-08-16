# Ms. Agenica S — ADK Executive Assistant Agent for Gemini Enterprise

Automated Executive Assistant Agent (**"Ms. Agenica S"**) for **Abhi Sethi (`aset@google.com`)**, built with the **Google Agent Development Kit (ADK)** and ready for registration on the **Gemini Enterprise App** and deployment to **Vertex AI Agent Engine (Reasoning Engine)**.

---

## 🌟 Identity & Display Branding

- **Display Name**: `Ms. Agenica S (EA to Abhi Sethi)`
- **Primary Alias**: `agenica@google.com`
- **Underlying Group Account**: `groupagent-agenica@google.com`
- **Access Portal**: `http://an/groupagent-agenica`
- **Executive Signature**:
  ```text
  --
  Ms. Agenica S
  Executive Assistant to Abhi Sethi
  Google Workspace Executive Assistant Agent
  agenica@google.com
  ```

---

## 🔒 Mandatory Processing Protocols

| Target Audience | Processing Protocol | Agent Execution Action |
| :--- | :--- | :--- |
| **Internal Googlers (`@google.com`)** | **Full Autonomous Execution** *(with HITL Approval)* | Checks calendar availability, sends a Google Chat Human-In-The-Loop approval card to Abhi Sethi, and upon approval, dispatches the email response from `agenica@google.com` and creates the Google Calendar event with Google Meet. |
| **External Partners** *(Flinders, DICT, RCH, etc.)* | **Draft-Delegate Protocol** | Checks calendar availability, creates a pending Gmail draft in `aset@google.com` signed as **Ms. Agenica S**, and sends a Google Chat ping to Abhi Sethi with a direct 1-click link to review and send. |

---

## 🏗️ Architecture & Project Structure

```text
agenica/
├── agent/
│   ├── __init__.py                 # Exports root_agent, app, run_query
│   ├── agent.py                    # Root ADK LlmAgent & session runner
│   ├── prompt.py                   # System prompt & operating instructions
│   ├── config.py                   # Principal & agent configuration settings
│   ├── requirements.txt            # Package dependencies
│   └── tools/
│       ├── __init__.py             # Exports all tools
│       ├── contact_tools.py        # Internal vs External audience classification
│       ├── calendar_tools.py       # Availability checking & event scheduling
│       ├── gmail_tools.py          # Inbox search, drafting & email dispatch
│       └── chat_tools.py           # Google Chat HITL cards & 1-click draft links
├── sidecars/
│   └── agenica-ea/
│       └── sidecar.json            # Scheduled background automation (cron)
├── .agent_engine_config.json       # Vertex AI Agent Engine deployment configuration
├── mcp_server.py                   # JSON-RPC 2.0 stdio MCP server
├── deploy.py                       # Automated deployment & Gemini Enterprise publisher
├── Dockerfile                      # Container definition for Cloud Run / GKE
├── pyproject.toml                  # Python package configuration
├── requirements.txt                # Root dependencies
├── AGENTS.md                       # Persona and operating guidelines
└── README.md                       # Documentation & deployment guide
```

---

## 🚀 Quickstart & Local Testing

### 1. Interactive Agent CLI Testing

Run a single prompt through the ADK agent:

```bash
uv run python -m agent.agent "Dr. John from Flinders University emailed requesting 30 min next Tuesday at 2pm to discuss AI research."
```

Or start the interactive REPL:

```bash
uv run python -m agent.agent --interactive
```

---

### 2. Local Web Playground

Launch the ADK web playground interface:

```bash
agents-cli playground
# or:
adk web agent
```

---

### 3. MCP Server Mode

To connect Ms. Agenica S tools to `gemini-cli` or other MCP clients, add this to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "agenica-ea": {
      "command": "python3",
      "args": ["/usr/local/google/home/aset/agenica/mcp_server.py"]
    }
  }
}
```

---

## ☁️ Deployment & Gemini Enterprise Registration

### Option A: One-Click Deploy Script

```bash
python3 deploy.py --project ag-test-1310 --region us-central1
```

### Option B: Step-by-Step CLI Deployment

#### Step 1: Deploy to Vertex AI Agent Engine (Reasoning Engine)

```bash
adk deploy agent_engine \
  --project ag-test-1310 \
  --region us-central1 \
  --display_name "Ms. Agenica S (EA to Abhi Sethi)" \
  --description "Executive Assistant AI Agent managing Google Calendar, Gmail, and Google Chat HITL workflows."
```

#### Step 2: Register on Gemini Enterprise App

```bash
agents-cli publish gemini-enterprise \
  --project ag-test-1310 \
  --display-name "Ms. Agenica S (EA to Abhi Sethi)" \
  --description "Executive Assistant for calendar scheduling, Gmail triage, and Google Chat HITL approvals." \
  --interactive
```

---

## ⏱️ Background Scheduled Automation

To run autonomous inbox and schedule triage every 15 minutes, enable the sidecar configuration in `sidecars/agenica-ea/sidecar.json`.
