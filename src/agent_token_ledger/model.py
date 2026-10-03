from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SourceKind(StrEnum):
    NATIVE = "native"
    DERIVED = "derived"
    GATEWAY = "gateway"
    AGGREGATE = "aggregate"
    PROXY = "proxy"


class Quality(StrEnum):
    EXACT = "exact"
    AGGREGATE = "aggregate"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class UsageEvent:
    event_key: str
    source: str
    agent: str
    source_kind: SourceKind
    timestamp_ms: int
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    provider_total_tokens: int | None = None
    account: str = ""
    model: str = ""
    session_id: str = ""
    turn_id: str = ""
    request_id: str = ""
    response_id: str = ""
    cost_usd: float | None = None
    input_includes_cached: bool | None = None
    input_includes_cache_write: bool | None = None
    quality: Quality = Quality.EXACT
    raw_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def non_cached_input_tokens(self) -> int:
        value = self.input_tokens
        if self.input_includes_cached:
            value -= self.cached_input_tokens
        if self.input_includes_cache_write:
            value -= self.cache_write_tokens
        return max(value, 0)

    @property
    def input_tokens_total(self) -> int:
        return (
            self.non_cached_input_tokens
            + self.cached_input_tokens
            + self.cache_write_tokens
        )

    @property
    def processed_tokens(self) -> int:
        return self.input_tokens_total + self.output_tokens

    @property
    def non_cached_input_and_output_tokens(self) -> int:
        return self.non_cached_input_tokens + self.output_tokens

    @property
    def cache_semantics_verified(self) -> bool:
        return (
            self.input_includes_cached is not None
            and self.input_includes_cache_write is not None
        )

    def usage_tuple(self) -> tuple[int, int, int, int]:
        return (
            self.input_tokens,
            self.cached_input_tokens,
            self.cache_write_tokens,
            self.output_tokens,
        )

    def canonical_usage_tuple(self) -> tuple[int, int, int, int]:
        return (
            self.non_cached_input_tokens,
            self.cached_input_tokens,
            self.cache_write_tokens,
            self.output_tokens,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_kind"] = str(self.source_kind)
        data["quality"] = str(self.quality)
        data["non_cached_input_tokens"] = self.non_cached_input_tokens
        data["input_tokens_total"] = self.input_tokens_total
        data["processed_tokens"] = self.processed_tokens
        data["non_cached_input_and_output_tokens"] = (
            self.non_cached_input_and_output_tokens
        )
        data["cache_semantics_verified"] = self.cache_semantics_verified
        return data


@dataclass(slots=True)
class ScanIssue:
    source: str
    severity: str
    code: str
    message: str
    raw_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SourceStat:
    source: str
    path: str
    size_bytes: int
    mtime_ns: int
    scanned_at_ms: int
    event_count: int
    error_count: int
    fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
