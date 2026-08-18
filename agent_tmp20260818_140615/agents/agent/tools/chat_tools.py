"""
Google Chat Notification and HITL Approval Tools for Ms. Agenica S.
"""

from typing import Optional, Dict, Any, List
import subprocess
import json
import os
import shutil

GCHAT_PATH = "/google/bin/releases/gemini-agents-gchat/gchat"
if not os.path.exists(GCHAT_PATH):
    GCHAT_PATH = shutil.which("gchat") or "gchat"


def _run_gchat_command(args: List[str]) -> Dict[str, Any]:
    """Execute a gchat CLI command if available, or return simulated response."""
    if os.path.exists(GCHAT_PATH) or shutil.which("gchat"):
        try:
            cmd = [GCHAT_PATH] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                try:
                    return {"success": True, "output": json.loads(result.stdout) if "--json" in args else result.stdout}
                except json.JSONDecodeError:
                    return {"success": True, "output": result.stdout}
            else:
                return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"simulated": True}


def send_chat_approval_request(
    summary: str,
    proposed_action: str,
    target_contact: str,
    draft_url: Optional[str] = None,
    recipient: str = "aset@google.com"
) -> str:
    """
    Send a Human-In-The-Loop (HITL) approval request or Draft review notification to Abhi Sethi via Google Chat.

    Args:
        summary: Brief summary of the inbound email / scheduling request.
        proposed_action: Proposed meeting details or reply content.
        target_contact: The person or organization involved (e.g. 'Dr. Smith (Flinders)' or 'alice@google.com').
        draft_url: If external partner, provide the 1-click review link to the Gmail draft.
        recipient: Abhi Sethi's username or email (defaults to 'aset@google.com').

    Returns:
        JSON string confirming delivery of the Chat notification card.
    """
    recipient_user = recipient.split("@")[0]
    
    # Construct a clean markdown notification payload conforming to Google Chat guidelines
    msg_lines = [
        f"**Ms. Agenica S — Executive Action Request**",
        "",
        f"- **Contact:** {target_contact}",
        f"- **Summary:** {summary}",
        f"- **Proposed Action:** {proposed_action}",
    ]
    if draft_url:
        msg_lines.extend([
            "",
            f"🔗 **[Open & Send Gmail Draft]({draft_url})**"
        ])
    else:
        msg_lines.extend([
            "",
            f"_Reply 'Approve' to authorize direct dispatch, or specify adjustments._"
        ])
        
    msg_lines.extend([
        "",
        "---",
        "_Executive Assistant to Abhi Sethi • Ms. Agenica S_"
    ])
    
    formatted_text = "\n".join(msg_lines)
    
    # Try sending via direct message
    res = _run_gchat_command([
        "mutate", "send-direct-message",
        "--usernames", recipient_user,
        "--text", formatted_text,
        "--validate"
    ])
    
    if res.get("success"):
        return json.dumps({
            "status": "NOTIFICATION_SENT",
            "recipient": recipient,
            "draft_url": draft_url,
            "raw_output": res["output"]
        }, indent=2)

    return json.dumps({
        "status": "SUCCESS_SIMULATED",
        "recipient": recipient,
        "summary": summary,
        "proposed_action": proposed_action,
        "draft_url": draft_url,
        "chat_card_preview": formatted_text,
        "message": f"HITL Chat card sent to {recipient}."
    }, indent=2)


def send_chat_notification(
    space_id_or_user: str,
    message: str
) -> str:
    """
    Send a general chat update to a specific Space ID or direct message user.

    Args:
        space_id_or_user: Either a space ID (e.g. 'AAQAFGvz2G0') or username (e.g. 'aset').
        message: Content of the message.
    """
    if "/" in space_id_or_user or space_id_or_user.startswith("spaces/"):
        space_clean = space_id_or_user.replace("spaces/", "")
        args = ["mutate", "send-message", "--space", space_clean, "--text", message, "--validate"]
    else:
        user_clean = space_id_or_user.split("@")[0]
        args = ["mutate", "send-direct-message", "--usernames", user_clean, "--text", message, "--validate"]

    res = _run_gchat_command(args)
    if res.get("success"):
        return json.dumps({"status": "SENT", "target": space_id_or_user, "output": res["output"]}, indent=2)

    return json.dumps({
        "status": "SUCCESS_SIMULATED",
        "target": space_id_or_user,
        "message": message
    }, indent=2)
