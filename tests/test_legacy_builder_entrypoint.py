"""The legacy builder command must not bypass v2.3 source-archive controls."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from build_google_seo_dashboard import main  # noqa: E402


class LegacyBuilderEntrypointTest(unittest.TestCase):
    def test_legacy_archive_dir_cli_is_disabled_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_dir = root / "legacy-archives"
            archive_dir.mkdir()
            output = root / "dashboard.json"
            stderr = io.StringIO()
            with patch.object(sys, "argv", [
                "build_google_seo_dashboard.py", "--archive-dir", str(archive_dir), "--output", str(output),
            ]), redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                main()
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("此入口已禁用", stderr.getvalue())
            self.assertIn("generate_dashboard_report.py --archive-root", stderr.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
