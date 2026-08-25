#!/usr/bin/env python3
"""Structured, secret-safe diagnostics for local SEO report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


SENSITIVE_MARKERS = ("authorization", "token", "cookie", "password", "secret", "private_key", "api_key", "credential")
STAGE_LABELS = {
    "archive_validation": "归档校验",
    "aggregation": "第一方指标汇总",
    "extension_validation": "扩展数据源校验",
    "artifact_validation": "报告产物校验",
    "package_validation": "技能包校验",
    "publish_review": "发布前复核",
}
DEFAULT_WRITE_STATE = {"archives": "unchanged", "report": "unchanged", "publish": "not_started"}


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items() if not any(marker in str(key).lower() for marker in SENSITIVE_MARKERS)}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, str) and any(marker in value.lower() for marker in ("bearer ", "-----begin", "authorization:")):
        return "[已省略敏感内容]"
    return value


def diagnostic(
    code: str,
    *,
    stage: str,
    scope: Mapping[str, Any],
    detected: Mapping[str, Any],
    impact: str,
    next_action: str,
    status: str = "blocked",
    safe_actions: Iterable[str] = (),
    write_state: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Create a stable diagnostic that can be shown to a non-technical report user."""
    clean_scope = _safe(dict(scope))
    clean_detected = _safe(dict(detected))
    resolved_state = dict(DEFAULT_WRITE_STATE)
    resolved_state.update(_safe(dict(write_state or {})))
    stage_label = STAGE_LABELS.get(stage, stage)
    message = (
        f"执行状态：{'已阻断' if status == 'blocked' else '需注意'}（{code}）。\n"
        f"问题位置：{stage_label}。\n"
        f"已验证：{json.dumps(clean_detected, ensure_ascii=False, sort_keys=True)}。\n"
        f"影响：{impact}\n"
        f"安全处理：{'；'.join(safe_actions) if list(safe_actions) else '未改写归档，未发布报告。'}\n"
        f"下一步：{next_action}"
    )
    return {
        "status": status,
        "stage": stage,
        "code": code,
        "scope": clean_scope,
        "detected": clean_detected,
        "impact": impact,
        "safe_actions": list(safe_actions),
        "next_action": next_action,
        "write_state": resolved_state,
        "user_message": message,
    }


def write_diagnostics(destination: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Persist internal-only JSON and Chinese Markdown; reject a public dashboard path."""
    destination = Path(destination)
    if "dashboards" in destination.parts:
        raise ValueError("诊断文件必须写入内部目录，不能写入公开 dashboards 路径")
    clean_records: List[Dict[str, Any]] = [_safe(dict(record)) for record in records]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "diagnostic.json").write_text(
        json.dumps({"diagnostics": clean_records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = ["# 报告生成诊断", ""]
    if not clean_records:
        lines.append("- 执行状态：正常。未发现需提示的问题。")
    for record in clean_records:
        lines.extend([f"## {record.get('code', 'UNKNOWN')}", "", str(record.get("user_message", "")), ""])
    (destination / "diagnostic.md").write_text("\n".join(lines), encoding="utf-8")
    return destination
