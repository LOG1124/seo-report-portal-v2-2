"""Offline source-closure tests for the capped DataForSEO trial CLI."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import dataforseo_keyword_enrichment as enrichment  # noqa: E402


def write_registry(root: Path) -> None:
    (root / "customer-registry.json").write_text(json.dumps({"customers": [{
        "canonical_domain": "example.com", "portal_slug": "example-com", "status": "active",
    }]}), encoding="utf-8")


def config_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "domain": "example.com", "month": "2026-07", "location_code": 2840,
        "language_code": "en", "serp_device": "desktop", "max_keywords": 5,
        "include_terms": ["product"], "exclude_terms": [], "output_archive_dir": "third-party",
    }
    payload.update(changes)
    return payload


def complete_source(domain: str = "example.com") -> dict[str, object]:
    return {
        "domain": domain, "period": ["2026-07-01", "2026-07-31"],
        "ga4": {"session_count": 1},
        "gsc": {"gsc_queries": [{"query": f"product {number}", "impressions": number} for number in range(1, 6)]},
    }


class DataForSEOSourceClosureTests(unittest.TestCase):
    def write_config(self, root: Path, payload: dict[str, object]) -> Path:
        path = root / "trial.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def run_main(self, config: Path, archive_root: Path, action: str = "--dry-run") -> int:
        with patch.object(sys, "argv", [
            "dataforseo_keyword_enrichment.py", "--config", str(config),
            "--archive-root", str(archive_root), "--credentials", "missing.env", action,
        ]):
            return enrichment.main()

    def test_legacy_source_archive_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), config_payload(source_archive="C:/legacy/other.json"))
            with self.assertRaisesRegex(ValueError, "source_archive 已不受支持"):
                enrichment.load_trial_config(config)

    def test_automatic_selection_only_reads_registered_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            (Path(tmp) / "legacy.json").write_text(json.dumps(complete_source()), encoding="utf-8")
            expected = root / "ga4-gsc" / "example.com" / "2026-07.json"
            expected.parent.mkdir(parents=True)
            expected.write_text(json.dumps(complete_source("other.example")), encoding="utf-8")
            config = self.write_config(Path(tmp), config_payload())
            with self.assertRaisesRegex(ValueError, "归档域名不匹配"):
                self.run_main(config, root)

    def test_source_validation_happens_before_credentials_or_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            source = root / "ga4-gsc" / "example.com" / "2026-07.json"
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps(complete_source() | {"ga4": {}}), encoding="utf-8")
            config = self.write_config(Path(tmp), config_payload())
            with patch.object(enrichment, "load_credentials", side_effect=AssertionError("credentials loaded")), patch.object(enrichment, "DataForSEOClient", side_effect=AssertionError("network client created")):
                with self.assertRaisesRegex(ValueError, "非空的 GA4 与 GSC"):
                    self.run_main(config, root, "--execute")

    def test_selected_keywords_still_require_registered_customer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            selected = [{"query": f"keyword {number}"} for number in range(1, 6)]
            payload = config_payload(
                domain="other.example", selected_keywords=selected, primary_serp_keyword="keyword 1"
            )
            payload.pop("include_terms")
            payload.pop("exclude_terms")
            config = self.write_config(Path(tmp), payload)
            with self.assertRaisesRegex(ValueError, "客户未在注册表中登记"):
                self.run_main(config, root)


if __name__ == "__main__":
    unittest.main()
