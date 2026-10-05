#!/usr/bin/env python3
"""Refresh Breadth only during the post-close Stockbee publishing window."""
from datetime import datetime, time
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from breadth_dashboard import main


def should_check(now: datetime) -> bool:
    evening_window = now.weekday() < 5 and now.time() >= time(16, 20)
    # Tuesday-Saturday morning is the final catch-up for the preceding
    # Monday-Friday session, including an unusually late Friday publish.
    morning_catch_up = 1 <= now.weekday() <= 5 and now.time() < time(10)
    return evening_window or morning_catch_up


if __name__ == "__main__":
    new_york = datetime.now(ZoneInfo("America/New_York"))
    if should_check(new_york):
        print(f"Checking Stockbee after close at {new_york:%Y-%m-%d %H:%M %Z}")
        main()
    else:
        print(f"Skipping Breadth refresh before close/weekend at {new_york:%Y-%m-%d %H:%M %Z}")
