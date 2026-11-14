#!/usr/bin/env python3
"""Skip duplicate scheduled refreshes when last successful run is recent."""
import datetime as dt
import json
import os
from pathlib import Path

MIN_REFRESH_AGE_MINUTES = 50


def should_run(event, report_path=Path("last_run.json"), now=None):
    if event != "schedule":
        return True
    if not report_path.is_file():
        return True
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        stamp = dt.datetime.fromisoformat(report["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return True
        age = (now - stamp).total_seconds() / 60
        return not (0 <= age < MIN_REFRESH_AGE_MINUTES)
    except (OSError, ValueError, KeyError, TypeError):
        # If the existing report is malformed, run instead of losing a refresh.
        return True


if __name__ == "__main__":
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    result = should_run(event)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"should_run={str(result).lower()}\n")
    print("Refresh requested" if result else "Skipping scheduled refresh: previous output is still fresh")
