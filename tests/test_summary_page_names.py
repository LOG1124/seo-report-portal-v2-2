import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from generate_dashboard_report import summary  # noqa: E402


class SummaryPageNamesTest(unittest.TestCase):
    def test_monthly_summary_uses_gsc_clicks_and_presents_root_as_homepage(self) -> None:
        """Monthly page ranking follows GSC clicks even when GA4 sessions differ."""
        payload = {
            "months": [{
                "label": "2026-07",
                "metrics": {"sessions": 10},
                "keywords": [],
                "channels": [],
                "pages": [
                    {"path": "/", "clicks": 2, "sessions": 10},
                    {"path": "/contact-us", "clicks": 9, "sessions": 1},
                ],
                "ga4Countries": [],
            }],
            "report": {"selectedMonths": ["2026-07"], "rangeLabel": "2026-07", "typeLabel": "月报", "comparison": {}},
            "quarterComparison": {"current": {"metrics": {"averagePosition": 20, "impressions": 100, "clicks": 4, "ctr": 4, "sessions": 10}}},
        }

        rendered = summary(payload, "example.com monthly（2026-07）", "example.com")

        self.assertIn("GSC 点击最高的页面为 /contact-us，其次是首页。", rendered)

    def test_quarterly_summary_uses_report_period_gsc_click_totals(self) -> None:
        """Quarterly page ranking must aggregate GSC clicks instead of taking one month."""
        payload = {
            "months": [
                {"label": "2026-05", "metrics": {"sessions": 1}, "keywords": [], "channels": [], "pages": [{"path": "/", "clicks": 5}, {"path": "/contact-us", "clicks": 2}], "ga4Countries": []},
                {"label": "2026-06", "metrics": {"sessions": 1}, "keywords": [], "channels": [], "pages": [{"path": "/", "clicks": 0}, {"path": "/contact-us", "clicks": 2}], "ga4Countries": []},
                {"label": "2026-07", "metrics": {"sessions": 1}, "keywords": [], "channels": [], "pages": [{"path": "/", "clicks": 0}, {"path": "/contact-us", "clicks": 2}], "ga4Countries": []},
            ],
            "report": {"selectedMonths": ["2026-05", "2026-06", "2026-07"], "rangeLabel": "2026-05 至 2026-07", "typeLabel": "季报", "comparison": {}},
            "quarterComparison": {"current": {"metrics": {"averagePosition": 20, "impressions": 100, "clicks": 11, "ctr": 11, "sessions": 3}}},
        }

        rendered = summary(payload, "example.com quarterly（2026-05_to_2026-07）", "example.com")

        self.assertIn("GSC 点击最高的页面为 /contact-us，其次是首页。", rendered)

    def test_quarterly_summary_uses_non_brand_gsc_period_average_positions(self) -> None:
        """Quarterly keyword summary uses non-brand GSC positions aggregated across the period."""
        payload = {
            "months": [
                {"label": "2026-05", "metrics": {"sessions": 1}, "keywords": [
                    {"query": "Acme", "clicks": 20, "impressions": 1000, "position": 1},
                    {"query": "widget supplier", "clicks": 1, "impressions": 20, "position": 8},
                    {"query": "widget manufacturer", "clicks": 1, "impressions": 20, "position": 12},
                    {"query": "high impression widget", "clicks": 1, "impressions": 20, "position": 50},
                ], "channels": [], "pages": [], "ga4Countries": []},
                {"label": "2026-06", "metrics": {"sessions": 1}, "keywords": [
                    {"query": "Acme", "clicks": 20, "impressions": 1000, "position": 1},
                    {"query": "widget supplier", "clicks": 1, "impressions": 20, "position": 9},
                    {"query": "widget manufacturer", "clicks": 1, "impressions": 20, "position": 12},
                    {"query": "high impression widget", "clicks": 1, "impressions": 20, "position": 50},
                ], "channels": [], "pages": [], "ga4Countries": []},
                {"label": "2026-07", "metrics": {"sessions": 1}, "keywords": [
                    {"query": "Acme", "clicks": 20, "impressions": 1000, "position": 1},
                    {"query": "widget supplier", "clicks": 1, "impressions": 20, "position": 10},
                    {"query": "widget manufacturer", "clicks": 1, "impressions": 20, "position": 12},
                    {"query": "high impression widget", "clicks": 1, "impressions": 20, "position": 50},
                ], "channels": [], "pages": [], "ga4Countries": []},
            ],
            "report": {"type": "quarterly", "selectedMonths": ["2026-05", "2026-06", "2026-07"], "rangeLabel": "2026-05 至 2026-07", "typeLabel": "季报", "comparison": {}},
            "quarterComparison": {"current": {"metrics": {"averagePosition": 20, "impressions": 100, "clicks": 11, "ctr": 11, "sessions": 3}}},
        }

        rendered = summary(payload, "acme.com quarterly（2026-05_to_2026-07）", "acme.com")

        self.assertIn("关键词 widget supplier 排名 9；关键词 widget manufacturer 排名 12。", rendered)
        self.assertNotIn("关键词 Acme", rendered)
        self.assertNotIn("关键词 high impression widget", rendered)


if __name__ == "__main__":
    unittest.main()
