"""
Evening Office Check-In Routine for Agenica S.
Scheduled daily at 18:00 SGT (Monday - Thursday).
Prompts Abhi Sethi about tomorrow's workspace plan and reserves phone/focus rooms
on Level 29 (or fallback floors) in MBC2 Singapore for open chunks of the day.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
import zoneinfo

from ..config import (
    PRINCIPAL_NAME,
    PRINCIPAL_EMAIL,
    AGENT_NAME,
    AGENT_EMAIL,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
    DEFAULT_TIMEZONE,
)
from ..tools.room_booking_tools import find_daily_focus_chunks, reserve_daily_focus_rooms
from ..tools.chat_tools import build_evening_office_card, send_chat_notification

SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def run_evening_checkin(
    target_date: str = None,
    preferred_floor: int = OFFICE_PRIMARY_FLOOR,
    auto_reserve: bool = False,
    dispatch_chat: bool = True
) -> dict:
    """
    Execute the evening office check-in workflow.
    """
    now = datetime.now(SGT_TZ)
    if not target_date:
        # Default to tomorrow (or Monday if Friday)
        days_ahead = 3 if now.weekday() == 4 else (2 if now.weekday() == 5 else 1)
        target_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # 1. Identify large open chunks of the day
    chunks = find_daily_focus_chunks(target_date)
    chunk_labels = [c["label"] for c in chunks]
    chunks_summary = "<br>• " + "<br>• ".join(chunk_labels) if chunk_labels else "Full working day open for booking."

    # 2. Build interactive Google Chat Card v2
    card_v2 = build_evening_office_card(
        target_date=target_date,
        open_chunks_summary=chunks_summary,
        floor=preferred_floor
    )

    reservation_results = None
    if auto_reserve:
        res_raw = reserve_daily_focus_rooms(target_date=target_date, floor=preferred_floor)
        reservation_results = json.loads(res_raw)

    result_payload = {
        "status": "CHECKIN_PREPARED",
        "routine": "evening_office_checkin",
        "target_date": target_date,
        "principal": f"{PRINCIPAL_NAME} ({PRINCIPAL_EMAIL})",
        "assistant": f"{AGENT_NAME} ({AGENT_EMAIL})",
        "location": OFFICE_LOCATION,
        "preferred_floor": preferred_floor,
        "open_chunks_count": len(chunks),
        "open_chunks": chunks,
        "chat_card_v2": card_v2,
        "auto_reserve": auto_reserve,
        "reservation_results": reservation_results
    }

    if dispatch_chat:
        msg_text = (
            f"**Workspace Check-in: Tomorrow ({target_date})**\n"
            f"Hi Abhi, will you be working from **{OFFICE_LOCATION}** tomorrow?\n"
            f"Open working blocks identified:\n" +
            "\n".join([f"• {c['label']}" for c in chunks])
        )
        if reservation_results:
            msg_text += f"\n\n{reservation_results.get('summary', '')}"
        send_chat_notification(PRINCIPAL_EMAIL, msg_text)

    return result_payload


def main():
    parser = argparse.ArgumentParser(description="Run Agenica S Evening Office Check-In Routine")
    parser.add_argument("--date", default=None, help="Target date in YYYY-MM-DD (defaults to tomorrow)")
    parser.add_argument("--floor", type=int, default=OFFICE_PRIMARY_FLOOR, help="Preferred floor (default: 29)")
    parser.add_argument("--auto-reserve", action="store_true", help="Automatically book phone/focus rooms on preferred floor")
    parser.add_argument("--no-dispatch", action="store_true", help="Print payload without sending live Chat message")

    args = parser.parse_args()

    print("=" * 70)
    print(f"{AGENT_NAME} — Evening Office & Workspace Routine")
    print("=" * 70)

    res = run_evening_checkin(
        target_date=args.date,
        preferred_floor=args.floor,
        auto_reserve=args.auto_reserve,
        dispatch_chat=not args.no_dispatch
    )

    print(f"Target Date: {res['target_date']}")
    print(f"Open Chunks Found: {res['open_chunks_count']}")
    for c in res['open_chunks']:
        print(f"  • {c['label']}")

    if res.get("reservation_results"):
        print("\n" + res["reservation_results"].get("summary", ""))
    else:
        print(f"\n✔ Interactive Chat Card prepared for {PRINCIPAL_EMAIL} with Level {args.floor} booking action.")


if __name__ == "__main__":
    main()
