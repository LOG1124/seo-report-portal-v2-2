import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from generate_dashboard_report import summary  # noqa: E402


class SummaryCountryOrganicClicksTest(unittest.TestCase):
    def test_country_uses_ga4_google_organic_clicks_across_report_period(self) -> None:
        payload = {
            "months": [
                {"label": "2026-05", "metrics": {"sessions": 1}, "keywords": [], "channels": [], "pages": [], "ga4Countries": [{"country": "United States", "sessions": 99}], "ga4OrganicSearchCountries": [{"country": "Brazil", "organicGoogleSearchClicks": 3}, {"country": "United States", "organicGoogleSearchClicks": 1}]},
                {"label": "2026-06", "metrics": {"sessions": 1}, "keywords": [], "channels": [], "pages": [], "ga4Countries": [{"country": "United States", "sessions": 99}], "ga4OrganicSearchCountries": [{"country": "Brazil", "organicGoogleSearchClicks": 3}, {"country": "United States", "organicGoogleSearchClicks": 4}]},
            ],
            "report": {"selectedMonths": ["2026-05", "2026-06"], "rangeLabel": "2026-05 至 2026-06", "typeLabel": "季报", "comparison": {}},
            "quarterComparison": {"current": {"metrics": {"averagePosition": 20, "impressions": 100, "clicks": 8, "ctr": 8, "sessions": 2}}},
        }

        rendered = summary(payload, "example.com quarterly（2026-05_to_2026-06）", "example.com")

        self.assertIn("访问较多的国家/地区是 Brazil。", rendered)


if __name__ == "__main__":
    unittest.main()
