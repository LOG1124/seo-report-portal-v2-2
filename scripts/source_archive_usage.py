"""Non-public provenance for the Google archives used by a generated report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath
from typing import Any

from customer_registry import CustomerRecord


USAGE_FILE = "source-archive-usage.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def usage_entry(archive_root: Path, role: str, path: Path) -> dict[str, str]:
    root = Path(archive_root).resolve()
    resolved = Path(path).resolve()
    return {
        "role": role,
        "relative_path": str(resolved.relative_to(root)),
        "sha256": sha256(resolved),
    }


def write_usage(
    report_dir: Path,
    archive_root: Path,
    record: CustomerRecord,
    report_type: str,
    label: str,
    current: list[Path],
    previous: list[Path],
    comparison_mode: str,
) -> Path:
    payload = {
        "domain": record.canonical_domain,
        "portal_slug": record.portal_slug,
        "report_type": report_type,
        "label": label,
        "comparison_mode": comparison_mode,
        "archives": [
            *(usage_entry(archive_root, "current", path) for path in current),
            *(usage_entry(archive_root, "previous", path) for path in previous),
        ],
    }
    path = Path(report_dir) / USAGE_FILE
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _source_path(root: Path, relative_path: str) -> Path:
    windows_path = PureWindowsPath(relative_path)
    if Path(relative_path).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError("来源使用记录包含档案根目录外路径")
    try:
        source = (root / relative_path).resolve()
        source.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError("来源使用记录包含档案根目录外路径") from exc
    return source


def verify_usage(
    report_dir: Path,
    archive_root: Path,
    record: CustomerRecord,
    report_type: str,
    label: str,
    allow_current_only: bool,
) -> dict[str, Any]:
    """Verify the local provenance record before an exception report can publish."""
    payload = json.loads((Path(report_dir) / USAGE_FILE).read_text(encoding="utf-8"))
    expected = {
        "domain": record.canonical_domain,
        "portal_slug": record.portal_slug,
        "report_type": report_type,
        "label": label,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("来源使用记录与报告身份不一致")

    comparison_mode = payload.get("comparison_mode")
    if comparison_mode not in {"complete", "current_only_exception"}:
        raise ValueError("来源使用记录的对比模式无效")
    if comparison_mode == "current_only_exception" and not allow_current_only:
        raise ValueError("仅当期报告必须显式允许发布")

    entries = payload.get("archives")
    if not isinstance(entries, list):
        raise ValueError("来源使用记录格式无效")
    roles = [item.get("role") for item in entries if isinstance(item, dict)]
    if "current" not in roles:
        raise ValueError("来源使用记录缺少当期档案")
    if comparison_mode == "complete" and "previous" not in roles:
        raise ValueError("来源使用记录缺少对比期档案")

    root = Path(archive_root).resolve()
    customer_root = (root / "ga4-gsc" / record.canonical_domain).resolve()
    for item in entries:
        if (
            not isinstance(item, dict)
            or item.get("role") not in {"current", "previous"}
            or not isinstance(item.get("relative_path"), str)
            or not isinstance(item.get("sha256"), str)
        ):
            raise ValueError("来源使用记录格式无效")
        source = _source_path(root, item["relative_path"])
        try:
            source.relative_to(customer_root)
        except ValueError as exc:
            raise ValueError("来源使用记录包含其他客户档案") from exc
        if not source.is_file() or sha256(source) != item["sha256"]:
            raise ValueError("源档案 SHA-256 不一致")
        try:
            archived_domain = json.loads(source.read_text(encoding="utf-8")).get("domain")
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("源档案身份不一致") from exc
        if archived_domain != record.canonical_domain:
            raise ValueError("源档案身份不一致")
    return payload
