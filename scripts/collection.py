"""Shared storage and project-context primitives for the bundled collector."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse


REQUIRED_COLLECTED_FIELDS = (
    "client_company", "onsite_articles", "offsite_articles", "product_count",
    "google_indexed", "bing_indexed", "brand_keyword", "keywords",
    "traffic_primary_channel", "traffic_secondary_channel", "session_count",
    "engaged_session_count", "session_top_source", "country_region_count",
    "top_country_region", "top_landing_page_type", "second_landing_page_type",
    "ranked_keyword_count", "remaining_articles",
)


def normalized_domain(website_url: str) -> str:
    """Return the lower-case hostname without a leading ``www.``."""
    parsed = urlparse(website_url.strip() if "://" in website_url else f"https://{website_url.strip()}")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise ValueError(f"无法从 website_url 解析域名: {website_url}")
    return host[4:] if host.startswith("www.") else host


def _load_object(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return payload


def _parse_date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} 必须使用 YYYY-MM-DD 格式") from exc


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    return bool(value.strip()) if isinstance(value, str) else bool(value) if isinstance(value, (list, dict)) else True


@dataclass(frozen=True)
class ProjectContext:
    website_url: str
    domain: str
    report_start: str
    report_end: str
    cooperation_level: str
    manual_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "ProjectContext":
        payload = _load_object(path)
        website_url = str(payload.get("website_url", "")).strip()
        start = _parse_date(payload.get("report_start"), "report_start")
        end = _parse_date(payload.get("report_end"), "report_end")
        if end < start:
            raise ValueError("report_end 不能早于 report_start")
        cooperation_level = str(payload.get("cooperation_level", "")).strip()
        if not cooperation_level:
            raise ValueError("cooperation_level 不能为空")
        manual_data = payload.get("manual_data") or {}
        if not isinstance(manual_data, dict):
            raise ValueError("project_input.json 中的 manual_data 必须是对象")
        return cls(website_url, normalized_domain(website_url), start.isoformat(), end.isoformat(), cooperation_level, manual_data)


class CollectedDataStore:
    """Read and update one ``collected_data.json`` without losing prior data."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"_provenance": {}}
        payload = _load_object(self.path)
        provenance = payload.get("_provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("_provenance 必须是对象")
        payload["_provenance"] = provenance
        return payload

    def record(
        self,
        field: str,
        value: Any,
        *,
        source_type: str,
        source_name: str,
        source_url: Optional[str] = None,
        screenshot: Optional[str] = None,
        screenshots: Optional[Iterable[str]] = None,
        rule_id: Optional[str] = None,
        captured_at: Optional[str] = None,
        raw_value: Any = None,
    ) -> None:
        if not _nonempty(value):
            raise ValueError(f"{field} 未取得有效值；请不要用空值伪造采集结果")
        if not source_type.strip() or not source_name.strip():
            raise ValueError("source_type 和 source_name 为必填来源信息")
        if field not in REQUIRED_COLLECTED_FIELDS and not field.startswith(("organic_", "average_", "bing_", "ga4_", "gsc_")):
            raise ValueError(f"未知采集字段: {field}")
        payload = self.load()
        provenance: Dict[str, Any] = {
            "source_type": source_type.strip(), "source_name": source_name.strip(),
            "captured_at": captured_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        if source_url:
            provenance["source_url"] = source_url
        if screenshot:
            provenance["screenshot"] = screenshot
        if screenshots:
            provenance["screenshots"] = list(screenshots)
        if rule_id:
            provenance["rule_id"] = rule_id
        if raw_value is not None:
            provenance["raw_value"] = raw_value
        payload[field] = value
        payload["_provenance"][field] = provenance
        self.save(payload)

    def save(self, payload: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temporary_name, self.path)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
