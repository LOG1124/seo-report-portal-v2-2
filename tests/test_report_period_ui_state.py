"""Regression checks for report-period versus selected-month UI state."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "dashboard-template.html"
GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_dashboard_report.py"


class ReportPeriodUiStateTests(unittest.TestCase):
    def test_month_selection_only_calls_selected_month_renderer(self) -> None:
        """A month switch must not re-render management summary or report-period panels."""
        html = TEMPLATE.read_text(encoding="utf-8")
        listener = re.search(
            r"monthSelect\.addEventListener\('change',\s*\(\)\s*=>\s*\{(?P<body>.*?)\}\);",
            html,
            re.S,
        )
        self.assertIsNotNone(listener, "month selector must have an explicit change handler")
        body = listener.group("body")
        self.assertIn("renderSelectedMonthDetails()", body)
        self.assertNotIn("renderReportPeriodPanels()", body)
        self.assertNotIn("renderAll()", body)

    def test_management_summary_has_one_report_period_writer_and_no_literal_previous_quarter(self) -> None:
        """The selected month cannot overwrite the report summary with a fixed historic range."""
        html = TEMPLATE.read_text(encoding="utf-8")
        runtime = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("function renderReportPeriodPanels()", html)
        self.assertIn("function renderSelectedMonthDetails()", html)
        self.assertNotIn("2025-12 至 2026-02", html)
        self.assertNotIn("google-seo-executive-summary", runtime)

    def test_channel_panel_aggregates_the_report_month_channels(self) -> None:
        """The UI must render the canonical monthly channel rows for the report period."""
        html = TEMPLATE.read_text(encoding="utf-8")
        channel_function = re.search(r"function renderChannels\(\) \{(?P<body>.*?)\n      \}\n\n      function renderReportPeriodPanels", html, re.S)
        self.assertIsNotNone(channel_function)
        body = channel_function.group("body")
        self.assertIn("months.forEach", body)
        self.assertNotIn("const reportGa4 = seoData.reportGa4", body)
        self.assertIn("row.engagementSeconds / row.engagementSessions", body)


if __name__ == "__main__":
    unittest.main()
