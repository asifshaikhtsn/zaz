import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from scripts.should_refresh import should_run


class RefreshGateTests(unittest.TestCase):
    def test_manual_dispatch_always_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(should_run("workflow_dispatch", Path(folder) / "report.json"))

    def test_recent_scheduled_run_skips(self):
        now = dt.datetime(2026, 11, 14, 14, 0, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text(json.dumps({"timestamp": (now - dt.timedelta(minutes=20)).isoformat()}))
            self.assertFalse(should_run("schedule", report, now))
            report.write_text(json.dumps({"timestamp": (now - dt.timedelta(minutes=55)).isoformat()}))
            self.assertTrue(should_run("schedule", report, now))

    def test_missing_or_corrupt_report_runs(self):
        now = dt.datetime.now(dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            self.assertTrue(should_run("schedule", report, now))
            report.write_text("not JSON")
            self.assertTrue(should_run("schedule", report, now))
