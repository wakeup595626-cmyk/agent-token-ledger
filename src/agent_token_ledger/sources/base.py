from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..model import ScanIssue, SourceStat, UsageEvent


@dataclass(slots=True)
class ScanContext:
    home: Path
    appdata: Path
    local_appdata: Path
    work_dir: Path
    max_file_bytes: int | None = None


@dataclass(slots=True)
class ScanResult:
    source: str
    events: list[UsageEvent] = field(default_factory=list)
    snapshots: list[SourceStat] = field(default_factory=list)
    issues: list[ScanIssue] = field(default_factory=list)


class SourceAdapter:
    name = "base"
    agent = "unknown"

    def scan(self, context: ScanContext) -> ScanResult:
        raise NotImplementedError
