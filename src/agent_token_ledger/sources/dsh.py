from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..model import Quality, ScanIssue, SourceKind, UsageEvent
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_fingerprint, file_stat, first_int, first_text, issue

#: DSH 原生会话解析缓存版本。折叠逻辑或字段口径变化导致缓存不兼容时递增。
_CACHE_VERSION = 1
_CACHE_FILENAME = "dsh_native_cache_v1.json"
_ZSTD_MAGIC_BYTES = bytes((0x28, 0xB5, 0x2F, 0xFD))


@dataclass(slots=True)
class _ParsedSession:
    events: list[UsageEvent]
    issues: list[ScanIssue]
    errors: int
    calls: int


class DshAdapter(SourceAdapter):
    name = "dsh"
    agent = "DeepSeek Harness"

    def __init__(self, ledger_path: Path | None = None):
        # 保留 ledger_path 注入参数：测试直接喂一份账本时走纯账本路径，
        # 与历史行为保持一致。
        self.ledger_path = ledger_path

    def scan(self, context: ScanContext) -> ScanResult:
        result = ScanResult(source=self.name)
        if self.ledger_path is not None:
            self._scan_ledger(self.ledger_path, result)
            return result

        dsh_home = context.dsh_home or (context.home / ".dsh")
        session_files: list[tuple[Path, str]] = []
        for root in _session_roots(dsh_home, context.dsh_candidates):
            session_files.extend(_discover_session_files(root))

        if not session_files:
            # 没有原生日志时回退到插件账本（旧行为），避免本机用量凭空消失。
            self._scan_ledger(dsh_home / "token-ledger" / "ledger.json", result)
            return result

        return self._scan_native(session_files, context, result)

    def _scan_native(
        self,
        session_files: list[tuple[Path, str]],
        context: ScanContext,
        result: ScanResult,
    ) -> ScanResult:
        zstd = _load_zstd()
        cache = _load_cache(context)
        cached_files = cache.get("files", {})
        changed = False
        seen_paths: set[str] = set()
        zstd_error_reported = False

        for path, session_id in session_files:
            cache_key = str(path)
            seen_paths.add(cache_key)
            if path.name.endswith(".zstd") and zstd is None:
                if not zstd_error_reported:
                    result.issues.append(
                        issue(
                            self.name,
                            "zstd_unavailable",
                            "当前 Python 版本缺少 zstd 解压能力，无法读取 DSH 压缩会话日志",
                            raw_ref=str(path),
                            severity="error",
                        )
                    )
                    zstd_error_reported = True
                continue

            fingerprint = file_fingerprint(path)
            cached = cached_files.get(cache_key)
            parsed = None
            if isinstance(cached, dict) and cached.get("fingerprint") == fingerprint:
                parsed = _parsed_from_cache(cached)
            if parsed is None:
                parsed = _parse_session_file(
                    path, session_id, zstd, self.name, self.agent
                )
                cached_files[cache_key] = {
                    "fingerprint": fingerprint,
                    "events": [event.to_dict() for event in parsed.events],
                    "issues": [asdict(item) for item in parsed.issues],
                    "errors": parsed.errors,
                    "calls": parsed.calls,
                }
                changed = True

            result.events.extend(parsed.events)
            result.issues.extend(parsed.issues)
            result.snapshots.append(
                file_stat(
                    path,
                    source=self.name,
                    event_count=len(parsed.events),
                    error_count=parsed.errors,
                    metadata={
                        "format": _session_format(path),
                        "input_includes_cached": False,
                        "input_includes_cache_write": False,
                        "calls": parsed.calls,
                    },
                )
            )

        stale_keys = [key for key in cached_files if key not in seen_paths]
        for key in stale_keys:
            cached_files.pop(key, None)
        if stale_keys or changed:
            _save_cache(context, cache)
        return result

    def _scan_ledger(self, path: Path, result: ScanResult) -> None:
        if not path.exists():
            result.issues.append(
                issue(
                    self.name,
                    "ledger_missing",
                    "Token 账本不存在",
                    raw_ref=str(path),
                )
            )
            return
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                ledger = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            result.issues.append(
                issue(
                    self.name,
                    "ledger_parse_error",
                    str(exc),
                    raw_ref=str(path),
                    severity="error",
                )
            )
            return

        by_day_route = ledger.get("byDayRoute") or {}
        if not isinstance(by_day_route, dict):
            result.issues.append(
                issue(
                    self.name,
                    "ledger_shape_error",
                    "账本中的 byDayRoute 字段不是对象",
                    raw_ref=str(path),
                    severity="error",
                )
            )
            return

        for day, routes in by_day_route.items():
            if not isinstance(routes, dict):
                continue
            timestamp_ms = _day_timestamp_ms(str(day))
            for route, totals in routes.items():
                if not isinstance(totals, dict):
                    continue
                input_tokens = first_int(totals.get("input"))
                output_tokens = first_int(totals.get("output"))
                cache_read = first_int(totals.get("cacheRead"))
                cache_write = first_int(totals.get("cacheWrite"))
                if input_tokens + output_tokens + cache_read + cache_write == 0:
                    continue
                result.events.append(
                    UsageEvent(
                        event_key=f"dsh:{day}:{route}",
                        source=self.name,
                        agent=self.agent,
                        source_kind=SourceKind.AGGREGATE,
                        timestamp_ms=timestamp_ms,
                        input_tokens=input_tokens,
                        cached_input_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        output_tokens=output_tokens,
                        provider_total_tokens=(
                            input_tokens
                            + output_tokens
                            + cache_read
                            + cache_write
                        ),
                        model=first_text(route, default="unknown"),
                        input_includes_cached=False,
                        input_includes_cache_write=False,
                        quality=Quality.AGGREGATE,
                        raw_ref=str(path),
                        metadata={
                            "day": str(day),
                            "route": str(route),
                            "calls": first_int(totals.get("calls")),
                            "ledger_version": ledger.get("version"),
                            "ledger_updated_at_ms": ledger.get("updatedAt"),
                        },
                    )
                )
        result.snapshots.append(
            file_stat(
                path,
                source=self.name,
                event_count=len(result.events),
                error_count=0,
            )
        )


def _parse_session_file(
    path: Path,
    session_id: str,
    zstd,
    source: str,
    agent: str,
) -> _ParsedSession:
    events: list[UsageEvent] = []
    issues: list[ScanIssue] = []
    errors = 0
    route = "unknown"
    last_seq = -1
    current: dict | None = None
    call_index = 0

    try:
        records = list(_iter_records(path, zstd))
    except (OSError, ValueError) as exc:
        return _ParsedSession(
            events=[],
            issues=[
                issue(
                    source,
                    "session_parse_error",
                    str(exc),
                    raw_ref=str(path),
                    severity="error",
                )
            ],
            errors=1,
            calls=0,
        )

    for line_number, record, error in records:
        if error:
            errors += 1
            issues.append(
                issue(
                    source,
                    "jsonl_parse_error",
                    error,
                    raw_ref=f"{path}:{line_number}",
                )
            )
            continue
        if record is None:
            continue

        seq = record.get("seq")
        if isinstance(seq, int) and seq <= last_seq:
            continue

        event_type = str(record.get("type") or "")
        data = record.get("data") or {}

        if event_type == "request/header":
            config = (data.get("header") or {}).get("config") or {}
            provider = config.get("provider")
            model = config.get("model")
            if isinstance(provider, str) and isinstance(model, str):
                route = f"{provider}/{model}"
        elif event_type == "llm/retry-started":
            if (
                current is not None
                and current["turn"] == data.get("turn")
                and current["step"] == data.get("step")
            ):
                events.append(
                    _usage_event(current, source, agent, path, session_id, route)
                )
                current = None
        else:
            sample = _sample_from_record(event_type, data)
            if sample is not None:
                turn, step, usage = sample
                if isinstance(turn, int) and isinstance(step, int):
                    buckets = _buckets(usage)
                    if (
                        current is not None
                        and current["turn"] == turn
                        and current["step"] == step
                    ):
                        current["buckets"] = buckets
                        current["timestamp_ms"] = _record_time(record, path)
                        current["provider_total"] = _provider_total(usage)
                        current["line_number"] = line_number
                    else:
                        if current is not None:
                            events.append(
                                _usage_event(
                                    current, source, agent, path, session_id, route
                                )
                            )
                        call_index += 1
                        current = {
                            "turn": turn,
                            "step": step,
                            "call_index": call_index,
                            "buckets": buckets,
                            "timestamp_ms": _record_time(record, path),
                            "provider_total": _provider_total(usage),
                            "line_number": line_number,
                        }

        if isinstance(seq, int):
            last_seq = seq

    if current is not None:
        events.append(
            _usage_event(current, source, agent, path, session_id, route)
        )

    return _ParsedSession(
        events=events,
        issues=issues,
        errors=errors,
        calls=call_index,
    )


def _usage_event(
    current: dict,
    source: str,
    agent: str,
    path: Path,
    session_id: str,
    route: str,
) -> UsageEvent:
    input_tokens, output_tokens, cache_read, cache_write = current["buckets"]
    return UsageEvent(
        event_key=(
            f"dsh-native:{session_id}:{current['turn']}:"
            f"{current['step']}:{current['call_index']}"
        ),
        source=source,
        agent=agent,
        source_kind=SourceKind.NATIVE,
        timestamp_ms=current["timestamp_ms"],
        input_tokens=input_tokens,
        cached_input_tokens=cache_read,
        cache_write_tokens=cache_write,
        output_tokens=output_tokens,
        provider_total_tokens=current["provider_total"],
        model=first_text(route, default="unknown"),
        session_id=session_id,
        turn_id=str(current["turn"]),
        input_includes_cached=False,
        input_includes_cache_write=False,
        quality=Quality.EXACT,
        raw_ref=f"{path}:{current['line_number']}",
        metadata={
            "format": _session_format(path),
            "route": route,
            "turn": current["turn"],
            "step": current["step"],
            "call_index": current["call_index"],
            "session_file": str(path),
        },
    )


def _sample_from_record(event_type: str, data: dict) -> tuple | None:
    if event_type == "assistant/chunk":
        chunk = data.get("chunk") or {}
        if chunk.get("type") == "usage":
            return (data.get("turn"), data.get("step"), chunk.get("usage") or {})
    elif event_type == "assistant/message":
        usage = data.get("usage")
        if isinstance(usage, dict):
            return (data.get("turn"), data.get("step"), usage)
    return None


def _buckets(usage: dict) -> tuple[int, int, int, int]:
    def n(value):
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
        return 0

    return (
        n(usage.get("inputTokens")),
        n(usage.get("outputTokens")),
        n(usage.get("cacheReadTokens")),
        n(usage.get("cacheWriteTokens")),
    )


def _provider_total(usage: dict) -> int | None:
    value = usage.get("totalTokens")
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _record_time(record: dict, path: Path) -> int:
    value = record.get("time")
    if isinstance(value, (int, float)):
        return int(value)
    return int(path.stat().st_mtime * 1000)


def _session_format(path: Path) -> str:
    if path.name == "session.v3.jsonl.zstd":
        return "v3-zstd"
    if path.name == "session.jsonl.zstd":
        return "v2-zstd"
    return "plain"


def _session_roots(dsh_home: Path, candidates: list[Path] | None) -> list[Path]:
    roots = [dsh_home / "sessions"]
    for candidate in candidates or []:
        roots.append(candidate / "sessions")
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)
    return deduped


def _discover_session_files(sessions_root: Path) -> list[tuple[Path, str]]:
    if not sessions_root.is_dir():
        return []
    found: list[tuple[Path, str]] = []
    for workspace in _iter_dirs(sessions_root):
        direct = _pick_session_file(workspace)
        if direct is not None:
            found.append((direct, workspace.name))
        for session_dir in _iter_dirs(workspace):
            chosen = _pick_session_file(session_dir)
            if chosen is not None:
                found.append((chosen, session_dir.name))
    return found


def _iter_dirs(path: Path):
    try:
        entries = sorted(path.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_dir():
                yield entry
        except OSError:
            continue


def _pick_session_file(session_dir: Path) -> Path | None:
    for name in ("session.v3.jsonl.zstd", "session.jsonl.zstd", "session.jsonl"):
        candidate = session_dir / name
        if candidate.is_file():
            return candidate
    return None


def _load_zstd():
    try:
        from compression import zstd

        return zstd
    except Exception:
        return None


def _iter_records(path: Path, zstd):
    line_number = 0
    for text in _iter_lines(path, zstd):
        line_number += 1
        text = text.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError as exc:
            yield line_number, None, f"{exc.msg} at column {exc.colno}"
            continue
        if isinstance(record, dict):
            yield line_number, record, None


def _iter_lines(path: Path, zstd):
    if path.name.endswith(".zstd"):
        raw = path.read_bytes()
        for start, end in _scan_zstd_frames(raw):
            try:
                decoded = zstd.decompress(raw[start:end]).decode(
                    "utf-8", "replace"
                )
            except Exception as exc:
                raise ValueError(f"zstd 解压失败: {exc}") from exc
            yield from decoded.split("\n")
        return
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        yield from handle


def _scan_zstd_frames(buffer: bytes) -> list[tuple[int, int]]:
    frames: list[tuple[int, int]] = []
    offset = 0
    total = len(buffer)
    while offset < total:
        start = offset
        if total - offset < 4:
            break
        if buffer[offset : offset + 4] != _ZSTD_MAGIC_BYTES:
            raise ValueError("zstd 帧头魔数不匹配")
        offset += 4
        if offset >= total:
            break
        descriptor = buffer[offset]
        offset += 1
        if descriptor & 24:
            raise ValueError("zstd 帧头保留位异常")
        content_size_flag = descriptor >> 6
        single_segment = bool(descriptor & 32)
        checksum = bool(descriptor & 4)
        dictionary_flag = descriptor & 3
        dictionary_bytes = 4 if dictionary_flag == 3 else dictionary_flag
        content_size_bytes = (
            (1 if single_segment else 0)
            if content_size_flag == 0
            else (1 << content_size_flag)
        )
        remaining = (
            (0 if single_segment else 1)
            + dictionary_bytes
            + content_size_bytes
        )
        if total - offset < remaining:
            break
        offset += remaining
        while True:
            if total - offset < 3:
                return frames
            header = (
                buffer[offset]
                | (buffer[offset + 1] << 8)
                | (buffer[offset + 2] << 16)
            )
            offset += 3
            last_block = bool(header & 1)
            block_type = (header >> 1) & 3
            block_size = header >> 3
            if block_type == 3:
                raise ValueError("zstd 块类型异常")
            payload_bytes = 1 if block_type == 1 else block_size
            if total - offset < payload_bytes:
                return frames
            offset += payload_bytes
            if last_block:
                break
        if checksum:
            if total - offset < 4:
                break
            offset += 4
        frames.append((start, offset))
    return frames


def _load_cache(context: ScanContext) -> dict:
    empty = {"version": _CACHE_VERSION, "files": {}}
    path = context.work_dir / _CACHE_FILENAME
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
        return empty
    files = data.get("files")
    if not isinstance(files, dict):
        return empty
    return {"version": _CACHE_VERSION, "files": files}


def _save_cache(context: ScanContext, cache: dict) -> None:
    path = context.work_dir / _CACHE_FILENAME
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, separators=(",", ":"))
        try:
            tmp_path.replace(path)
        except OSError as exc:
            if getattr(exc, "winerror", None) != 17:
                raise
            shutil.copyfile(tmp_path, path)
            tmp_path.unlink(missing_ok=True)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _parsed_from_cache(cached: dict) -> _ParsedSession | None:
    events: list[UsageEvent] = []
    for item in cached.get("events") or []:
        if not isinstance(item, dict):
            return None
        try:
            events.append(UsageEvent.from_dict(item))
        except (TypeError, ValueError, KeyError):
            return None
    issues: list[ScanIssue] = []
    for item in cached.get("issues") or []:
        if not isinstance(item, dict):
            return None
        try:
            issues.append(ScanIssue(**item))
        except TypeError:
            return None
    return _ParsedSession(
        events=events,
        issues=issues,
        errors=int(cached.get("errors") or 0),
        calls=int(cached.get("calls") or 0),
    )


def _day_timestamp_ms(day: str) -> int:
    try:
        value = datetime.strptime(day, "%Y-%m-%d").replace(
            hour=12, tzinfo=timezone(timedelta(hours=8))
        )
    except ValueError:
        return 0
    return int(value.timestamp() * 1000)