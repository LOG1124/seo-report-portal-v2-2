"""Offline checks that ship with the distributable package."""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from dataforseo_keyword_enrichment import load_trial_config  # noqa: E402
from generate_dashboard_report import month_range  # noqa: E402
from publish_oss_report import load_env_file, main as publish_main  # noqa: E402


class PackageSmokeTests(unittest.TestCase):
    def test_generic_dataforseo_example_is_a_valid_limited_trial_config(self) -> None:
        config = load_trial_config(PACKAGE / "assets" / "dataforseo-trial.example.json")
        self.assertEqual(config["domain"], "example.com")
        self.assertEqual(config["max_keywords"], 5)
        self.assertEqual(config["serp_device"], "desktop")

    def test_month_range_is_local_and_deterministic(self) -> None:
        self.assertEqual(month_range("2026-04", "2026-06"), ["2026-04", "2026-05", "2026-06"])

    def test_windows_unc_env_value_is_preserved_without_shell_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "oss.env"
            path.write_text("OSS_ARCHIVE_ROOT=\\\\server\\共享盘\\seo-report-portal\n", encoding="utf-8")
            self.assertEqual(load_env_file(path)["OSS_ARCHIVE_ROOT"], r"\\server\共享盘\seo-report-portal")

    def test_cross_platform_publisher_dry_run_checks_smb_path_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "report"
            report_dir.mkdir()
            for name in ("index.html", "dashboard-data.json", "summary.md"):
                (report_dir / name).write_text(name, encoding="utf-8")
            archive_root = root / "mapped-drive"
            archive_root.mkdir()
            private = root / "private"
            private.mkdir()
            (private / "oss.env").write_text(f"OSS_ARCHIVE_ROOT={archive_root}\n", encoding="utf-8")
            with patch.object(sys, "argv", [
                "publish_oss_report.py", "--local-report-dir", str(report_dir),
                "--client-slug", "example-com", "--type", "monthly", "--period", "2026-06",
                "--oss-env", str(private / "oss.env"), "--dry-run",
            ]):
                self.assertEqual(publish_main(), 0)
            self.assertFalse((archive_root / "example-com").exists())


if __name__ == "__main__":
    unittest.main()
