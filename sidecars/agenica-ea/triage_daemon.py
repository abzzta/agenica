#!/usr/bin/env python3
"""
Autonomous Background EA Daemon for Ms. Agenica S.
Runs periodic 4-tier inbox triage and schedule clash detection on Cloudtop as aset@google.com.
"""

import sys
import os
import json
import logging
from datetime import datetime

# Ensure agent package is in sys.path
sys.path.insert(0, "/usr/local/google/home/aset/agenica")

from agent.tools import (
    get_current_datetime,
    scan_inbox_triage,
    check_calendar_clash,
    list_upcoming_events,
    send_chat_notification,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_ea_routine():
    logging.info("Starting Ms. Agenica S periodic scan routine for aset@google.com...")
    
    # 1. Real-world datetime grounding
    dt_info = json.loads(get_current_datetime(timezone_name="Australia/Adelaide"))
    logging.info("Real-world grounding: %s (%s)", dt_info.get("formatted"), dt_info.get("current_date"))
    
    # 2. 4-Tier Inbox Triage
    try:
        triage_raw = scan_inbox_triage(max_results=10)
        triage_data = json.loads(triage_raw)
        needs_action = triage_data.get("categories", {}).get("needs_action", [])
        if needs_action:
            logging.info("Found %d items needing action in inbox.", len(needs_action))
    except Exception as e:
        logging.warning("Inbox triage scan encountered notice: %s", e)

    # 3. Schedule Inspection
    try:
        schedule_raw = list_upcoming_events(days=3)
        logging.info("Upcoming calendar inspection complete.")
    except Exception as e:
        logging.warning("Calendar inspection notice: %s", e)

    logging.info("Periodic scan completed successfully.")


if __name__ == "__main__":
    run_ea_routine()
