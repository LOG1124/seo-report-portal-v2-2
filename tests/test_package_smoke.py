"""Offline checks that ship with the distributable package."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from dataforseo_keyword_enrichment import load_trial_config  # noqa: E402
from generate_dashboard_report import month_range  # noqa: E402


class PackageSmokeTests(unittest.TestCase):
    def test_generic_dataforseo_example_is_a_valid_limited_trial_config(self) -> None:
        config = load_trial_config(PACKAGE / "assets" / "dataforseo-trial.example.json")
        self.assertEqual(config["domain"], "example.com")
        self.assertEqual(config["max_keywords"], 5)
        self.assertEqual(config["serp_device"], "desktop")

    def test_month_range_is_local_and_deterministic(self) -> None:
        self.assertEqual(month_range("2026-04", "2026-06"), ["2026-04", "2026-05", "2026-06"])


if __name__ == "__main__":
    unittest.main()
