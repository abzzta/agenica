#!/usr/bin/env python3
"""
Deployment and Gemini Enterprise Registration Script for Ms. Agenica S.

This script:
1. Builds and validates the ADK Agent package.
2. Deploys the agent to Vertex AI Agent Engine (Reasoning Engine).
3. Registers/Publishes the agent runtime to the Gemini Enterprise App.
"""

import os
import sys
import subprocess
import argparse
import json


def run_command(cmd, cwd=None):
    print(f"▸ {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if res.returncode != 0:
        print(f"Error: {res.stderr.strip() or res.stdout.strip()}")
        return None
    print(res.stdout.strip())
    return res.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Deploy Ms. Agenica S ADK Agent to Vertex AI & Gemini Enterprise")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "cowork-aset-6tnf0w"), help="GCP Project ID")
    parser.add_argument("--region", default=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"), help="GCP Location / Region")
    parser.add_argument("--display-name", default="Ms. Agenica S (EA to Abhi Sethi)", help="Agent Display Name")
    parser.add_argument("--gemini-enterprise-app-id", default=os.environ.get("GEMINI_ENTERPRISE_APP_ID"), help="Gemini Enterprise App Full Resource Name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deployment steps without modifying cloud resources")

    args = parser.parse_args()

    print("=" * 70)
    print("Ms. Agenica S — ADK Deployment to Gemini Enterprise")
    print(f"Project:      {args.project}")
    print(f"Region:       {args.region}")
    print(f"Display Name: {args.display_name}")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN] Validating local ADK agent structure...")
        try:
            from agent.agent import root_agent, app
            print(f"✔ Root agent found: {root_agent.name if root_agent else 'N/A'}")
            print(f"✔ Tools registered: {len(root_agent.tools) if root_agent else 0}")
            print("✔ ADK agent structure verified successfully.")
        except Exception as e:
            print(f"❌ Verification failed: {e}")
        return

    # Step 1: Deploy to Vertex AI Agent Engine
    print("\n[Step 1/2] Deploying Agent to Vertex AI Agent Engine (Reasoning Engine)...")
    deploy_cmd = [
        "adk", "deploy", "agent_engine",
        "--project", args.project,
        "--region", args.region,
        "--display_name", args.display_name,
        "--description", "Executive Assistant AI Agent managing Google Calendar, Gmail, and Google Chat HITL workflows."
    ]
    out = run_command(deploy_cmd)
    if not out:
        print("\nNote: You can also deploy via Docker / Cloud Run using: adk deploy cloud_run")
        return

    # Step 2: Register on Gemini Enterprise
    print("\n[Step 2/2] Registering Agent on Gemini Enterprise App...")
    publish_cmd = [
        "agents-cli", "publish", "gemini-enterprise",
        "--project", args.project,
        "--display-name", args.display_name,
        "--description", "Executive Assistant agent for calendar scheduling, Gmail triage, and Google Chat HITL approvals."
    ]
    if args.gemini_enterprise_app_id:
        publish_cmd.extend(["--gemini-enterprise-app-id", args.gemini_enterprise_app_id])
    else:
        publish_cmd.append("--interactive")

    run_command(publish_cmd)
    print("\n✔ Deployment & Registration workflow completed.")


if __name__ == "__main__":
    main()
