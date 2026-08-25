"""Tests for staged v2 package parity before global replacement."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from check_package_parity import check_package_parity  # noqa: E402


FILES = (
    "SKILL.md",
    "assets/dashboard-template.html",
    "scripts/generate_dashboard_report.py",
    "scripts/publish_oss_report.py",
    "agents/openai.yaml",
)


class PackageParityTests(unittest.TestCase):
    def make_skill(self, root: Path, suffix: str = "") -> Path:
        for name in FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{name}{suffix}", encoding="utf-8")
        return root

    def make_zip(self, source: Path, destination: Path) -> Path:
        with zipfile.ZipFile(destination, "w") as archive:
            for name in FILES:
                archive.write(source / name, arcname=f"{source.name}/{name}")
        return destination

    def test_matching_source_staged_zip_and_global_copy_pass_parity(self) -> None:
        """A candidate release must be byte-identical across the three selectable forms."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_skill(root / "source")
            installed = self.make_skill(root / "installed")
            staged_zip = self.make_zip(source, root / "staged.zip")
            self.assertEqual(check_package_parity(source, staged_zip, installed), [])

    def test_out_of_sync_template_is_reported_before_installation(self) -> None:
        """A stale ZIP or global copy must be a visible release blocker, not silent drift."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_skill(root / "source")
            installed = self.make_skill(root / "installed", suffix="stale")
            staged_zip = self.make_zip(source, root / "staged.zip")
            codes = [item["code"] for item in check_package_parity(source, staged_zip, installed)]
            self.assertIn("SKILL_PACKAGE_OUT_OF_SYNC", codes)


if __name__ == "__main__":
    unittest.main()
