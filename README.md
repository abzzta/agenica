# Ms. Agenica S — Executive Assistant Agent

Automated Executive Assistant agent ("Ms. Agenica S") for Abhi Sethi, built on Google's Jetski & Marina agent harness.

## Identity & Display Branding
- **Name / Display Name**: Ms. Agenica S (EA to Abhi Sethi)
- **Primary Alias**: `agenica@google.com`
- **Underlying Group Account**: `groupagent-agenica@google.com`
- **Access Portal**: `http://an/groupagent-agenica`
- **Avatar Tool**: `/google/src/head/depot/google3/devtools/jetski/capsules/tools/update_agent_avatar.sh`
- **Signature**:
  ```text
  --
  Ms. Agenica S
  Executive Assistant to Abhi Sethi
  Google Workspace Executive Assistant Agent
  agenica@google.com
  ```

## Processing Protocols

| Target Audience | Processing Protocol | Agent Execution Action |
| :--- | :--- | :--- |
| **Internal Googlers (`@google.com`)** | **Full Autonomous Execution** (with HITL Approval) | Direct email reply & Calendar invite created automatically once approved in Google Chat. |
| **External Partners** *(Flinders, DICT, RCH, etc.)* | **Draft-Delegate Protocol** | Creates a pending Gmail draft under your inbox (`aset@google.com`) signed as **Ms. Agenica S**, then sends you a Chat link to click Send. |

## File Layout

* `AGENTS.md` — Global persona and operational rules.
* `agents/agenica.md` — Custom agent specification for Jetski/Marina.
* `sidecars/agenica-ea/sidecar.json` — Scheduled background automation configuration.

## Deployment & Activation

Deploy or renew the agent capsule with Google Chat enabled:

```bash
/google/bin/releases/jetski-devs/marina/marina deploy \
  --identity=corpagent-eng-aset \
  --name="Ms. Agenica S (EA to Abhi Sethi)" \
  --with_chat
```
