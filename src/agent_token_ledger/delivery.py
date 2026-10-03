from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .inventory import inventory
from .model import UsageEvent
from .pipeline import default_context
from .reporting import report, render_csv, render_text
from .storage import LedgerDatabase
from .timeutil import iso_from_ms, now_ms
from .validation import validate_snapshot


SCOPES = ("primary", "native", "visible")
DIMENSIONS = ("agent", "source", "model", "account", "date", "kind")
FORMATS = ("text", "json", "csv")
SCOPE_LABELS = {
    "primary": "主口径",
    "native": "原始口径",
    "visible": "全部来源口径",
}
DIMENSION_LABELS = {
    "agent": "智能体",
    "source": "来源",
    "model": "模型",
    "account": "账号",
    "date": "日期",
    "kind": "记录类型",
}
KIND_LABELS = {
    "native": "原始记录",
    "derived": "会话镜像",
    "gateway": "网关日志",
    "aggregate": "汇总记录",
    "proxy": "代理统计",
    "plugin": "插件记录",
}
STATUS_LABELS = {
    "detected": "已发现，可采集",
    "missing": "本机未发现",
    "unsupported": "已复核，不支持可靠采集",
    "error": "已发现，但读取失败",
}
VALIDATION_LABELS = {
    "scan_id": "扫描编号",
    "events": "记录数",
    "errors": "错误",
    "warnings": "警告",
    "semantic_unknown": "语义未明确",
    "provider_total_mismatches": "服务商总用量差异",
    "known_reasoning_total_mismatches": "已知推理 Token 口径差异",
    "unknown_provider_total_mismatches": "未知服务商总用量差异",
    "passed": "是否通过",
}


def export_delivery(
    *,
    db_path: str | Path,
    output_dir: str | Path,
    work_dir: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated_at_ms = now_ms()

    with LedgerDatabase(db_path) as database:
        scan_id = database.latest_scan_id()
        scan_run = database.scan_run(scan_id)
        events = database.events(scan_id)
        snapshots = database.snapshots(scan_id)
        issues = database.issues(scan_id)

    validation = {"scan_id": scan_id, **validate_snapshot(events, issues)}
    reports: list[dict[str, Any]] = []
    for scope in SCOPES:
        scope_dir = output / scope
        scope_dir.mkdir(parents=True, exist_ok=True)
        for dimension in DIMENSIONS:
            value = report(
                events,
                scope=scope,
                dimension=dimension,
                generated_at_ms=generated_at_ms,
            )
            _write_text(scope_dir / f"{dimension}.txt", render_text(value))
            _write_json(scope_dir / f"{dimension}.json", value.to_dict())
            _write_text(scope_dir / f"{dimension}.csv", render_csv(value))
            reports.append(
                {
                    "scope": scope,
                    "dimension": dimension,
                    "processed_tokens": value.overall.processed_tokens,
                    "events": value.overall.events,
                    "groups": len(value.groups),
                }
            )

    context = default_context(Path(work_dir))
    sources = [item.to_dict() for item in inventory(context)]
    summary = _summary(
        events=events,
        snapshots=snapshots,
        issues=issues,
        validation=validation,
        scan_id=scan_id,
        scan_run=scan_run,
        generated_at_ms=generated_at_ms,
        db_path=Path(db_path),
    )
    _write_json(output / "summary.json", summary)
    _write_text(output / "summary.md", _summary_markdown(summary))
    _write_json(output / "sources.json", sources)
    _write_text(output / "sources.txt", _sources_text(sources))
    _write_json(output / "validation.json", validation)
    _write_text(output / "validation.txt", _validation_text(validation))
    _write_text(output / "source_coverage.md", _source_coverage_markdown(sources))
    _write_json(output / "scan_summary.json", summary["scan"])
    _write_csv(output / "source_snapshots.csv", snapshots)
    _write_csv(output / "issues.csv", issues)
    _write_text(output / "reports_index.md", _reports_index(reports))
    manifest = _write_manifest(output)

    result = {
        "output_dir": str(output.resolve()),
        "scan_id": scan_id,
        "reports": len(reports),
        "validation": validation,
        "manifest": str(manifest.resolve()),
    }
    return result


def _summary(
    *,
    events: list[UsageEvent],
    snapshots: list[dict],
    issues: list[dict],
    validation: dict,
    scan_id: int,
    scan_run: dict[str, Any],
    generated_at_ms: int,
    db_path: Path,
) -> dict[str, Any]:
    scopes = {}
    for scope in SCOPES:
        value = report(
            events,
            scope=scope,
            dimension="agent",
            generated_at_ms=generated_at_ms,
        )
        scopes[scope] = value.overall.to_dict()

    source_counts: Counter[tuple[str, str]] = Counter()
    source_tokens: Counter[tuple[str, str]] = Counter()
    for event in events:
        key = (event.source, event.agent)
        source_counts[key] += 1
        source_tokens[key] += event.processed_tokens
    sources = [
        {
            "source": source,
            "agent": agent,
            "events": count,
            "processed_tokens": source_tokens[(source, agent)],
            "processed_yi": source_tokens[(source, agent)] / 100_000_000,
        }
        for (source, agent), count in source_counts.items()
    ]
    sources.sort(key=lambda item: (-item["processed_tokens"], item["source"]))
    return {
        "generated_at_ms": generated_at_ms,
        "generated_at": iso_from_ms(generated_at_ms),
        "database": str(db_path.resolve()),
        "scan": {
            "scan_id": scan_id,
            "status": scan_run.get("status"),
            "started_at_ms": scan_run.get("started_at_ms"),
            "started_at": iso_from_ms(scan_run["started_at_ms"]),
            "finished_at_ms": scan_run.get("finished_at_ms"),
            "finished_at": (
                iso_from_ms(scan_run["finished_at_ms"])
                if scan_run.get("finished_at_ms")
                else ""
            ),
            "notes": scan_run.get("notes", ""),
            "events": len(events),
            "snapshots": len(snapshots),
            "issues": len(issues),
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
        "scopes": scopes,
        "sources": sources,
        "validation": validation,
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    scan = summary["scan"]
    primary = summary["scopes"]["primary"]
    lines = [
        "# 智能体 Token 用量账本交付摘要",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 数据库：`{summary['database']}`",
        f"- 扫描编号：`{scan['scan_id']}`",
        f"- 扫描时段：{scan['started_at']} 至 {scan['finished_at']}",
        f"- 对账后事件：{scan['events']:,}",
        f"- 来源快照：{scan['snapshots']:,}",
        f"- 错误 / 警告：{scan['errors']:,} / {scan['warnings']:,}",
        f"- 校验结果：{'通过' if summary['validation']['passed'] else '未通过'}",
        "",
        "## 主口径三项总量",
        "",
        f"- 总输入 Token：{primary['input_tokens_total']:,}",
        f"- 总输出 Token：{primary['output_tokens']:,}",
        f"- 缓存命中 Token：{primary['cached_input_tokens']:,}",
        f"- 去重后总处理量：{primary['processed_tokens']:,}",
        f"- 记录数 / 会话数：{primary['events']:,} / {primary['sessions']:,}",
        "",
        "## 全部统计口径",
        "",
        "| 口径 | 处理量（亿） | 输入合计 | 缓存读取 | 输出 | 事件 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scope in SCOPES:
        item = summary["scopes"][scope]
        lines.append(
            f"| {SCOPE_LABELS[scope]} | {item['processed_yi']:.8f} | "
            f"{item['input_tokens_total']:,} | "
            f"{item['cached_input_tokens']:,} | "
            f"{item['output_tokens']:,} | {item['events']:,} |"
        )
    lines += [
        "",
        "## 来源明细",
        "",
        "| 来源 | Agent | 事件 | 处理量（亿） |",
        "| --- | --- | ---: | ---: |",
    ]
    for item in summary["sources"]:
        lines.append(
            f"| {item['source']} | {item['agent']} | "
            f"{item['events']:,} | {item['processed_yi']:.8f} |"
        )
    lines += [
        "",
        "## 交付内容",
        "",
        "- `primary/`、`native/`、`visible/`：每个口径 6 个维度，分别提供 TXT、JSON、CSV。",
        "- `sources.*`：来源可用性与本次只读复核证据。",
        "- `validation.*`：语义、错误和 provider total 一致性校验。",
        "- `source_snapshots.csv`：扫描到的文件/数据库指纹与事件数。",
        "- `issues.csv`：扫描问题与来源不可用说明。",
        "- `manifest.sha256`：报告目录内文件完整性清单。",
        "",
    ]
    return "\n".join(lines)


def _sources_text(sources: list[dict]) -> str:
    lines = []
    for item in sources:
        status = STATUS_LABELS.get(item["status"], item["status"])
        lines.append(
            f"{item['agent']} | {KIND_LABELS.get(item['kind'], item['kind'])} | "
            f"{status} | {'存在' if item['exists'] else '未发现'}"
        )
        lines.append(f"  说明：{item['note']}")
        for path in item["paths"]:
            marker = "[存在]" if path in item["existing_paths"] else "[缺失]"
            lines.append(f"  {marker} {path}")
    return "\n".join(lines) + "\n"


def _validation_text(validation: dict) -> str:
    lines = []
    for key, value in validation.items():
        label = VALIDATION_LABELS.get(key, key)
        if key == "passed":
            value = "通过" if value else "未通过"
        lines.append(f"{label}：{value}")
    return "\n".join(lines) + "\n"


def _source_coverage_markdown(sources: list[dict]) -> str:
    detected = sum(1 for item in sources if item["status"] == "detected")
    missing = sum(1 for item in sources if item["status"] == "missing")
    unsupported = sum(1 for item in sources if item["status"] == "unsupported")
    errors = sum(1 for item in sources if item["status"] == "error")
    lines = [
        "# 来源覆盖复核",
        "",
        f"- 本机已发现且可采集：{detected}",
        f"- 支持采集但本机未发现：{missing}",
        f"- 已复核但无可靠 Token 账本：{unsupported}",
        f"- 已发现但读取失败：{errors}",
        "- 本轮复核为只读：仅检查路径元数据、文件结构、SQLite schema 和定向 token 字段。",
        "",
        "| Agent | 类型 | 状态 | 本地路径 | 结论 / 证据 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in sources:
        paths = "<br>".join(
            f"{'存在' if path in item['existing_paths'] else '缺失'} `{path}`"
            for path in item["paths"]
        )
        note = item["note"].replace("|", "\\|")
        lines.append(
            f"| {item['agent']} | "
            f"{KIND_LABELS.get(item['kind'], item['kind'])} | "
            f"{STATUS_LABELS.get(item['status'], item['status'])} | "
            f"{paths} | {note} |"
        )
    lines += [
        "",
        "“已复核但无可靠 Token 账本”不等于软件未安装；这些位置可能只有界面状态、配置、日志或加密数据库，",
        "没有能够稳定还原模型 token 用量的只读账本。",
        "",
    ]
    return "\n".join(lines)


def _reports_index(reports: list[dict]) -> str:
    lines = [
        "# 报告索引",
        "",
        f"共 {len(reports)} 份矩阵报告：3 个口径 × 6 个维度 × 3 种格式。",
        "",
        "| 口径 | 维度 | 事件 | 处理量（亿） | 分组数 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for item in reports:
        lines.append(
            f"| {SCOPE_LABELS.get(item['scope'], item['scope'])} | "
            f"{DIMENSION_LABELS.get(item['dimension'], item['dimension'])} | "
            f"{item['events']:,} | "
            f"{item['processed_tokens'] / 100_000_000:.8f} | {item['groups']:,} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_manifest(output: Path) -> Path:
    entries = []
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name == "manifest.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(f"{digest}  {path.relative_to(output).as_posix()}")
    manifest = output / "manifest.sha256"
    _write_text(manifest, "\n".join(entries) + "\n")
    return manifest


def _write_json(path: Path, value: Any) -> None:
    _write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        _write_text(path, "")
        return
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=list(rows[0].keys()),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    _write_text(path, output.getvalue())


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
