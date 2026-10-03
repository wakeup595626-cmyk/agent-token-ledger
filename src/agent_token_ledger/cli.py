from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .delivery import export_delivery
from .inventory import inventory
from .pipeline import default_adapters, default_context, persist_scan, scan_all
from .reporting import report, render_csv, render_text
from .storage import LedgerDatabase
from .timeutil import now_ms
from .validation import validate_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = PROJECT_ROOT / "var"
DEFAULT_DB = DEFAULT_WORK_DIR / "ledger.sqlite"


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            return _scan(args)
        if args.command == "report":
            return _report(args)
        if args.command == "sources":
            return _sources(args)
        if args.command == "validate":
            return _validate(args)
        if args.command == "export":
            return _export(args)
    except (RuntimeError, ValueError, OSError, sqlite3.Error) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-token-ledger",
        description="只读扫描本地 Agent 账本并按亿汇总 token 用量",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="只读扫描所有已知来源")
    scan.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    scan.add_argument(
        "--skip-gateway",
        action="store_true",
        help="不扫描实时增长的 Cockpit 网关请求日志",
    )
    scan.add_argument("--json", action="store_true")

    report_parser = subparsers.add_parser("report", help="从账本生成汇总")
    report_parser.add_argument(
        "--scope",
        choices=("primary", "native", "visible"),
        default="primary",
    )
    report_parser.add_argument(
        "--dimension",
        choices=("agent", "source", "model", "account", "date", "kind"),
        default="agent",
    )
    report_parser.add_argument("--agent", default="")
    report_parser.add_argument("--model", default="")
    report_parser.add_argument("--account", default="")
    report_parser.add_argument("--start", default="")
    report_parser.add_argument("--end", default="")
    report_parser.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
    )
    report_parser.add_argument("--max-groups", type=int, default=50)

    sources = subparsers.add_parser("sources", help="列出来源和可用状态")
    sources.add_argument("--json", action="store_true")

    validate = subparsers.add_parser("validate", help="核验扫描快照和事件一致性")
    validate.add_argument("--json", action="store_true")

    export = subparsers.add_parser(
        "export",
        help="一次生成全部口径、维度和格式的报告",
    )
    export.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports",
    )
    export.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    export.add_argument("--json", action="store_true")
    return parser


def _scan(args: argparse.Namespace) -> int:
    context = default_context(args.work_dir)
    adapters = default_adapters(include_gateway=not args.skip_gateway)
    results = scan_all(context, adapters=adapters)
    with LedgerDatabase(args.db) as database:
        scan_id = persist_scan(
            database,
            results,
            context=context,
            command={
                "command": "scan",
                "work_dir": str(args.work_dir),
                "include_gateway": not args.skip_gateway,
            },
        )
        events = database.events(scan_id)
        issues = database.issues(scan_id)
        snapshots = database.snapshots(scan_id)
    raw_count = sum(len(result.events) for result in results)
    summary = {
        "scan_id": scan_id,
        "db": str(args.db),
        "raw_events": raw_count,
        "deduped_events": len(events),
        "duplicate_events": raw_count - len(events),
        "source_snapshots": len(snapshots),
        "issues": len(issues),
        "errors": sum(1 for item in issues if item["severity"] == "error"),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("只读扫描完成")
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0


def _report(args: argparse.Namespace) -> int:
    start_ms = _parse_boundary(args.start, end=False)
    end_ms = _parse_boundary(args.end, end=True)
    with LedgerDatabase(args.db) as database:
        scan_id = database.latest_scan_id()
        events = database.events(scan_id)
    value = report(
        events,
        scope=args.scope,
        dimension=args.dimension,
        agent=args.agent,
        model=args.model,
        account=args.account,
        start_ms=start_ms,
        end_ms=end_ms,
        generated_at_ms=now_ms(),
    )
    if args.format == "json":
        print(json.dumps(value.to_dict(), ensure_ascii=False, indent=2))
    elif args.format == "csv":
        print(render_csv(value), end="")
    else:
        print(render_text(value, max_groups=args.max_groups))
    return 0


def _sources(args: argparse.Namespace) -> int:
    context = default_context(DEFAULT_WORK_DIR)
    items = inventory(context)
    if args.json:
        print(json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2))
        return 0
    for item in items:
        print(
            f"{item.agent:<24} {item.kind:<10} {item.status:<12} "
            f"exists={'Y' if item.to_dict()['exists'] else 'N'} {item.note}"
        )
        for path in item.paths:
            print(f"  {path}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    with LedgerDatabase(args.db) as database:
        scan_id = database.latest_scan_id()
        events = database.events(scan_id)
        issues = database.issues(scan_id)
    result = {"scan_id": scan_id, **validate_snapshot(events, issues)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if result["passed"] else 1


def _export(args: argparse.Namespace) -> int:
    result = export_delivery(
        db_path=args.db,
        output_dir=args.output_dir,
        work_dir=args.work_dir,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"报告输出目录: {result['output_dir']}")
        print(f"scan_id: {result['scan_id']}")
        print(f"报告数量: {result['reports']}")
        print(f"校验通过: {result['validation']['passed']}")
        print(f"完整性清单: {result['manifest']}")
    return 0


def _parse_boundary(value: str, *, end: bool) -> int | None:
    if not value:
        return None
    try:
        date_value = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        # Also accept a full ISO timestamp.
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
        return int(parsed.timestamp() * 1000)
    timezone_cn = timezone(timedelta(hours=8))
    if end:
        date_value = date_value + timedelta(days=1)
    return int(date_value.replace(tzinfo=timezone_cn).timestamp() * 1000) - (
        1 if end else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
