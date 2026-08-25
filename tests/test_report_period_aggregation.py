"""Regression tests for first-party report-period aggregation."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from build_google_seo_dashboard import build_dashboard_data  # noqa: E402
from generate_dashboard_report import main as generate_report  # noqa: E402


def archive(domain: str, *, clicks: int, impressions: int, sessions: int, key_events: int, channels: list[dict]) -> dict:
    """Small hand-checked GA4/GSC archive fixture; channel totals equal GA4 totals."""
    return {
        "domain": domain,
        "period": ["2026-06-01", "2026-06-30"],
        "gsc": {
            "organic_clicks": clicks,
            "organic_impressions": impressions,
            "organic_ctr": clicks / impressions * 100,
            "average_position": 12.5,
            "gsc_queries": [],
            "gsc_pages": [],
            "gsc_index_status": [],
            "gsc_countries": [],
            "gsc_daily": [],
        },
        "ga4": {
            "ga4_total_users": sessions,
            "ga4_page_views": sessions * 2,
            "session_count": sessions,
            "ga4_avg_session_duration": 20,
            "ga4_avg_engagement_time_per_session": 15,
            "ga4_bounce_rate": 0.4,
            "ga4_key_events": key_events,
            "ga4_landing_pages": [],
            "ga4_channels": channels,
            "ga4_sources": [],
            "ga4_countries": [],
            "ga4_daily": [],
        },
    }


class ReportPeriodAggregationTests(unittest.TestCase):
    def write_archive(self, directory: Path, label: str, payload: dict) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{label}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_report_ga4_is_derived_from_monthly_archives_and_matches_channel_totals(self) -> None:
        """Removing or independently altering reportGa4 must not change canonical GA4 totals."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            june = self.write_archive(directory, "2026-06", archive(
                "example.com", clicks=4, impressions=100, sessions=10, key_events=2,
                channels=[
                    {"sessionDefaultChannelGroup": "Direct", "sessions": 6, "keyEvents": 1, "averageEngagementTimePerSession": 10},
                    {"sessionDefaultChannelGroup": "Organic Search", "sessions": 4, "keyEvents": 1, "averageEngagementTimePerSession": 20},
                ],
            ))
            july = self.write_archive(directory, "2026-07", archive(
                "example.com", clicks=6, impressions=200, sessions=5, key_events=1,
                channels=[
                    {"sessionDefaultChannelGroup": "Direct", "sessions": 2, "keyEvents": 0, "averageEngagementTimePerSession": 30},
                    {"sessionDefaultChannelGroup": "Organic Search", "sessions": 3, "keyEvents": 1, "averageEngagementTimePerSession": 40},
                ],
            ))

            payload = build_dashboard_data([june, july], report_months=None)

        report_ga4 = payload.get("reportGa4")
        self.assertEqual(report_ga4["sessions"], 15)
        self.assertEqual(report_ga4["keyEvents"], 3)
        self.assertEqual(sum(row["sessions"] for row in report_ga4["channels"]), 15)
        self.assertEqual(sum(row["keyEvents"] for row in report_ga4["channels"]), 3)
        self.assertEqual(payload["quarterComparison"]["current"]["metrics"]["sessions"], 15)

    def test_mixed_domain_archives_are_rejected_before_a_report_is_aggregated(self) -> None:
        """A misplaced client archive must never become part of another client's report."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            first = self.write_archive(directory, "2026-06", archive(
                "example.com", clicks=1, impressions=10, sessions=1, key_events=0,
                channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
            ))
            second = self.write_archive(directory, "2026-07", archive(
                "other.example", clicks=1, impressions=10, sessions=1, key_events=0,
                channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
            ))

            with self.assertRaisesRegex(ValueError, "归档域名不一致"):
                build_dashboard_data([first, second], report_months=None)

    def test_predecessor_archives_for_another_domain_block_comparison_generation(self) -> None:
        """A complete but wrong-client predecessor period must not silently become a comparison."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_dir = root / "archives"
            archive_dir.mkdir()
            for label in ("2026-06", "2026-07", "2026-08"):
                self.write_archive(archive_dir, label, archive(
                    "example.com", clicks=1, impressions=10, sessions=1, key_events=0,
                    channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
                ))
            for label in ("2026-03", "2026-04", "2026-05"):
                self.write_archive(archive_dir, label, archive(
                    "other.example", clicks=1, impressions=10, sessions=1, key_events=0,
                    channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
                ))
            template = root / "template.html"
            template.write_text('<script id="google-seo-data" type="application/json">{}</script>', encoding="utf-8")
            args = [
                "generate_dashboard_report.py", "--type", "quarterly", "--start-month", "2026-06", "--end-month", "2026-08",
                "--domain", "example.com", "--archive-dir", str(archive_dir), "--template", str(template),
                "--output-root", str(root / "output"),
            ]
            with patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "归档域名不匹配"):
                    generate_report()

    def test_generated_report_keeps_diagnostic_newlines_as_valid_embedded_json(self) -> None:
        """A missing predecessor warning must not corrupt the HTML data block with a raw newline."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_dir = root / "archives"
            self.write_archive(archive_dir, "2026-06", archive(
                "example.com", clicks=1, impressions=10, sessions=1, key_events=0,
                channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
            ))
            template = PACKAGE / "assets" / "dashboard-template.html"
            output_root = root / "dashboards"
            args = [
                "generate_dashboard_report.py", "--type", "monthly", "--start-month", "2026-06", "--domain", "example.com",
                "--archive-dir", str(archive_dir), "--template", str(template), "--output-root", str(output_root),
                "--diagnostics-root", str(root / "diagnostics"),
            ]
            with patch.object(sys, "argv", args):
                self.assertEqual(generate_report(), 0)
            html = (output_root / "example.com" / "monthly" / "2026-06" / "index.html").read_text(encoding="utf-8")
            embedded = re.search(r'<script id="google-seo-data" type="application/json">(.*?)</script>', html, re.S)
            self.assertIsNotNone(embedded)
            payload = json.loads(embedded.group(1))
            self.assertIn("PREVIOUS_PERIOD_ARCHIVE_MISSING", [item["code"] for item in payload["diagnostics"]])

    def test_user_selected_in_progress_month_generates_without_preview_label(self) -> None:
        """A present-month archive is publishable as the requested period, not silently reclassified."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_dir = root / "archives"
            current = archive(
                "example.com", clicks=1, impressions=10, sessions=1, key_events=0,
                channels=[{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
            )
            current["period"] = ["2026-08-01", "2026-08-25"]
            self.write_archive(archive_dir, "2026-08", current)
            output_root = root / "dashboards"
            args = [
                "generate_dashboard_report.py", "--type", "monthly", "--start-month", "2026-08", "--domain", "example.com",
                "--archive-dir", str(archive_dir), "--template", str(PACKAGE / "assets" / "dashboard-template.html"),
                "--output-root", str(output_root), "--diagnostics-root", str(root / "diagnostics"),
            ]
            with patch.object(sys, "argv", args):
                self.assertEqual(generate_report(), 0)
            report_dir = output_root / "example.com" / "monthly" / "2026-08"
            payload = json.loads((report_dir / "dashboard-data.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["report"]["selectedMonths"], ["2026-08"])
            self.assertNotIn("预览", (report_dir / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
