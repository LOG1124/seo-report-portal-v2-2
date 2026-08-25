"""Regression tests for optional DataForSEO and SEOAgent archive scope guards."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from build_google_seo_dashboard import build_dashboard_data  # noqa: E402


def google_archive() -> dict:
    return {
        "domain": "example.com", "period": ["2026-06-01", "2026-06-30"],
        "gsc": {
            "organic_clicks": 1, "organic_impressions": 10, "organic_ctr": 10, "average_position": 11,
            "gsc_queries": [{"query": "approved product", "clicks": 1, "impressions": 10, "ctr": 10, "position": 11}],
            "gsc_pages": [], "gsc_index_status": [], "gsc_countries": [], "gsc_daily": [],
        },
        "ga4": {
            "ga4_total_users": 1, "ga4_page_views": 1, "session_count": 1,
            "ga4_avg_session_duration": 10, "ga4_avg_engagement_time_per_session": 5,
            "ga4_bounce_rate": 0, "ga4_key_events": 0, "ga4_landing_pages": [],
            "ga4_channels": [{"sessionDefaultChannelGroup": "Direct", "sessions": 1, "keyEvents": 0}],
            "ga4_sources": [], "ga4_countries": [], "ga4_daily": [],
        },
    }


class ExtensionArchiveScopeTests(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_dataforseo_wrong_period_or_unselected_keyword_is_hidden_without_changing_first_party_metrics(self) -> None:
        """An out-of-scope market snapshot cannot leak a keyword into a first-party report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "google" / "2026-06.json"
            self.write_json(archive_path, google_archive())
            enrichment_dir = root / "dataforseo"
            self.write_json(enrichment_dir / "2026-06.json", {
                "domain": "example.com", "month": "2026-05",
                "market": {"location_code": 2840, "language_code": "en"},
                "selected_keywords": [{"query": "unapproved keyword"}],
                "search_volume": {"keywords": [{"keyword": "unapproved keyword", "search_volume": 900}]},
            })
            payload = build_dashboard_data([archive_path], report_months=None, enrichment_archive_dir=enrichment_dir)

        self.assertEqual(payload["months"][0]["marketKeywords"], [])
        self.assertEqual(payload["quarterComparison"]["current"]["metrics"]["clicks"], 1)
        self.assertIn("DATAFORSEO_ARCHIVE_SCOPE_MISMATCH", [item["code"] for item in payload["diagnostics"]])

    def test_stale_seoagent_snapshot_is_hidden_and_report_stays_first_party_only(self) -> None:
        """A strategy archive outside the report period is not a substitute for a current strategy view."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "google" / "2026-06.json"
            self.write_json(archive_path, google_archive())
            strategy_dir = root / "seoagent"
            self.write_json(strategy_dir / "2026-05.json", {
                "provider": "seoagent", "domain": "example.com", "status": "complete", "collection_month": "2026-05",
                "query_scope": {"location": "United States", "language": "English"},
                "responses": {"domain_keyword_opportunities": {"keywords": [{"keyword": "approved product", "priority": "P1", "intent": "commercial"}]}, "domain_keywords": {"keywords": []}, "competitor_keyword_strategy": {"competitors": [], "keywords": []}},
            })
            payload = build_dashboard_data([archive_path], report_months=None, seoagent_archive_dir=strategy_dir)

        self.assertNotIn("strategyOpportunities", payload)
        self.assertEqual(payload["quarterComparison"]["current"]["metrics"]["sessions"], 1)
        self.assertIn("SEOAGENT_ARCHIVE_SCOPE_MISMATCH", [item["code"] for item in payload["diagnostics"]])


if __name__ == "__main__":
    unittest.main()
