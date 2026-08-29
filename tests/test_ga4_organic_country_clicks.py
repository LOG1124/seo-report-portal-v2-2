import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from google_api_collector import collect_ga4  # noqa: E402


class Ga4OrganicCountryClicksTest(unittest.TestCase):
    def test_collector_archives_country_google_organic_clicks(self) -> None:
        calls = []

        def report(_client, _property, _start, _end, dimensions, metrics, _limit):
            calls.append((dimensions, metrics))
            if dimensions == ["country"] and metrics == ["organicGoogleSearchClicks"]:
                return [{"country": "Brazil", "organicGoogleSearchClicks": 5}]
            if dimensions == ["country"]:
                return [{"country": "United States", "sessions": 10, "totalUsers": 8, "engagedSessions": 6}]
            if not dimensions:
                return [{"sessions": 1, "engagedSessions": 1, "totalUsers": 1, "screenPageViews": 1, "averageSessionDuration": 1, "userEngagementDuration": 1, "bounceRate": 0, "keyEvents": 0}]
            return []

        with patch("google_api_collector._ga4_report", side_effect=report):
            result = collect_ga4(object(), "123", "2026-07-01", "2026-07-31")

        self.assertEqual(result["ga4_organic_search_countries"], [{"country": "Brazil", "organicGoogleSearchClicks": 5}])
        self.assertIn((["country"], ["organicGoogleSearchClicks"]), calls)


if __name__ == "__main__":
    unittest.main()
