from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .model import SourceKind, UsageEvent
from .pricing import DEFAULT_MODEL_PRICES, CostBreakdown, cost_breakdown
from .timeutil import day_from_ms, iso_from_ms


ONE_YI = 100_000_000
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


@dataclass(slots=True)
class Aggregate:
    group: str
    events: int = 0
    sessions: int = 0
    processed_tokens: int = 0
    input_tokens_total: int = 0
    non_cached_input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    provider_total_tokens: int = 0
    cost_usd: float = 0.0
    costed_events: int = 0
    zero_cost_events: int = 0
    cost_estimated_usd: float = 0.0
    cost_estimated_events: int = 0
    cost_unpriced_events: int = 0
    cost_implicit_model_events: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    agents: set[str] = field(default_factory=set)
    source_kinds: set[str] = field(default_factory=set)
    quality: set[str] = field(default_factory=set)
    session_ids: set[str] = field(default_factory=set)

    def add(self, event: UsageEvent) -> None:
        self.events += 1
        self.processed_tokens += event.processed_tokens
        self.input_tokens_total += event.input_tokens_total
        self.non_cached_input_tokens += event.non_cached_input_tokens
        self.cached_input_tokens += event.cached_input_tokens
        self.cache_write_tokens += event.cache_write_tokens
        self.output_tokens += event.output_tokens
        self.reasoning_output_tokens += event.reasoning_output_tokens
        self.provider_total_tokens += event.provider_total_tokens or 0
        if event.cost_usd is not None:
            self.costed_events += 1
            self.cost_usd += event.cost_usd
            if event.cost_usd == 0:
                self.zero_cost_events += 1
        self.agents.add(event.agent)
        self.source_kinds.add(str(event.source_kind))
        self.quality.add(str(event.quality))
        if event.session_id:
            self.session_ids.add(event.session_id)
        if self.first_timestamp_ms is None or event.timestamp_ms < self.first_timestamp_ms:
            self.first_timestamp_ms = event.timestamp_ms
        if self.last_timestamp_ms is None or event.timestamp_ms > self.last_timestamp_ms:
            self.last_timestamp_ms = event.timestamp_ms

    @property
    def session_count(self) -> int:
        return len(self.session_ids)

    @property
    def cost_total_usd(self) -> float:
        return self.cost_usd + self.cost_estimated_usd

    def apply_cost_breakdown(self, value: CostBreakdown) -> None:
        self.cost_usd = value.known_usd
        self.cost_estimated_usd = value.estimated_usd
        self.cost_estimated_events = value.estimated_events
        self.cost_unpriced_events = value.unpriced_events
        self.cost_implicit_model_events = value.implicit_model_events

    def cost_status(self) -> str:
        if not self.events or self.cost_total_usd <= 0:
            return "missing"
        if (
            self.costed_events >= self.events
            and self.cost_estimated_events == 0
            and self.cost_unpriced_events == 0
        ):
            return "complete"
        if self.costed_events:
            return "partial"
        return "estimated"

    def to_dict(self) -> dict[str, Any]:
        estimated_coverage = (
            self.cost_estimated_events / self.events if self.events else 0.0
        )
        return {
            "group": self.group,
            "events": self.events,
            "sessions": self.session_count,
            "processed_tokens": self.processed_tokens,
            "processed_yi": self.processed_tokens / ONE_YI,
            "input_tokens_total": self.input_tokens_total,
            "input_tokens_total_yi": self.input_tokens_total / ONE_YI,
            "non_cached_input_tokens": self.non_cached_input_tokens,
            "non_cached_input_tokens_yi": self.non_cached_input_tokens / ONE_YI,
            "cached_input_tokens": self.cached_input_tokens,
            "cached_input_tokens_yi": self.cached_input_tokens / ONE_YI,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_write_tokens_yi": self.cache_write_tokens / ONE_YI,
            "output_tokens": self.output_tokens,
            "output_tokens_yi": self.output_tokens / ONE_YI,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "provider_total_tokens": self.provider_total_tokens,
            "provider_total_yi": self.provider_total_tokens / ONE_YI,
            "cost_usd": round(self.cost_usd, 8),
            "cost_known_usd": round(self.cost_usd, 8),
            "cost_estimated_usd": round(self.cost_estimated_usd, 8),
            "cost_total_usd": round(self.cost_total_usd, 8),
            "costed_events": self.costed_events,
            "zero_cost_events": self.zero_cost_events,
            "cost_estimated_events": self.cost_estimated_events,
            "cost_unpriced_events": self.cost_unpriced_events,
            "cost_implicit_model_events": self.cost_implicit_model_events,
            "cost_event_coverage": (
                self.costed_events / self.events if self.events else 0.0
            ),
            "cost_estimated_coverage": estimated_coverage,
            "cost_status": self.cost_status(),
            "first_timestamp_ms": self.first_timestamp_ms,
            "first_time": (
                iso_from_ms(self.first_timestamp_ms)
                if self.first_timestamp_ms is not None
                else ""
            ),
            "last_timestamp_ms": self.last_timestamp_ms,
            "last_time": (
                iso_from_ms(self.last_timestamp_ms)
                if self.last_timestamp_ms is not None
                else ""
            ),
            "agents": sorted(self.agents),
            "source_kinds": sorted(self.source_kinds),
            "quality": sorted(self.quality),
        }


@dataclass(slots=True)
class Report:
    scope: str
    dimension: str
    generated_at_ms: int
    overall: Aggregate
    groups: list[Aggregate]
    filters: dict[str, Any]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "dimension": self.dimension,
            "generated_at_ms": self.generated_at_ms,
            "filters": self.filters,
            "overall": self.overall.to_dict(),
            "groups": [group.to_dict() for group in self.groups],
            "notes": self.notes,
        }


def report(
    events: list[UsageEvent],
    *,
    scope: str = "primary",
    dimension: str = "agent",
    agent: str = "",
    model: str = "",
    account: str = "",
    start_ms: int | None = None,
    end_ms: int | None = None,
    generated_at_ms: int | None = None,
    prices: Mapping[str, Mapping[str, float]] | None = None,
) -> Report:
    if dimension not in {"agent", "source", "model", "account", "date", "kind"}:
        raise ValueError(f"不支持的分组维度：{dimension}")
    if scope not in {"primary", "native", "visible"}:
        raise ValueError(f"不支持的统计口径：{scope}")
    selected = [
        event
        for event in events
        if _scope_matches(event, scope)
        and (not agent or event.agent.casefold() == agent.casefold())
        and (not model or event.model.casefold() == model.casefold())
        and (not account or event.account.casefold() == account.casefold())
        and (start_ms is None or event.timestamp_ms >= start_ms)
        and (end_ms is None or event.timestamp_ms <= end_ms)
    ]
    grouped: dict[str, Aggregate] = {}
    overall = Aggregate(group="all")
    selected_by_group: dict[str, list[UsageEvent]] = {}
    for event in selected:
        overall.add(event)
        group_name = _group_value(event, dimension)
        grouped.setdefault(group_name, Aggregate(group=group_name)).add(event)
        selected_by_group.setdefault(group_name, []).append(event)
    active_prices = prices or DEFAULT_MODEL_PRICES
    overall.apply_cost_breakdown(cost_breakdown(selected, active_prices))
    for group_name, aggregate in grouped.items():
        aggregate.apply_cost_breakdown(
            cost_breakdown(selected_by_group[group_name], active_prices)
        )
    groups = sorted(
        grouped.values(),
        key=lambda item: (-item.processed_tokens, item.group.casefold()),
    )
    notes = _scope_notes(scope)
    if any(event.quality != event.quality.EXACT for event in selected):
        notes.append("包含聚合或估算事件，无法与逐请求账本同等精确。")
    if overall.cost_estimated_events:
        notes.append(
            "参考总费用由实采金额和未采集费用的参考估算组成，不等同于实际账单。"
        )
    return Report(
        scope=scope,
        dimension=dimension,
        generated_at_ms=generated_at_ms or int(datetime.now().timestamp() * 1000),
        overall=overall,
        groups=groups,
        filters={
            "agent": agent,
            "model": model,
            "account": account,
            "start_ms": start_ms,
            "end_ms": end_ms,
        },
        notes=notes,
    )


def format_yi(tokens: int, *, digits: int = 4) -> str:
    return f"{tokens / ONE_YI:,.{digits}f} 亿"


def render_text(report_value: Report, *, max_groups: int = 50) -> str:
    lines = [
        "本地 Agent Token 用量报告（只读汇总）",
        f"口径：{SCOPE_LABELS.get(report_value.scope, report_value.scope)} / "
        f"维度：{DIMENSION_LABELS.get(report_value.dimension, report_value.dimension)}",
        (
            "总处理量: "
            f"{format_yi(report_value.overall.processed_tokens)}"
            f" ({report_value.overall.processed_tokens:,} 个 Token)"
        ),
        (
            "  输入合计: "
            f"{format_yi(report_value.overall.input_tokens_total)}"
            " / 其中缓存读取: "
            f"{format_yi(report_value.overall.cached_input_tokens)}"
        ),
        (
            "  非缓存输入+输出: "
            f"{format_yi(report_value.overall.non_cached_input_tokens + report_value.overall.output_tokens)}"
        ),
        f"  输出: {format_yi(report_value.overall.output_tokens)}",
        (
            "费用参考: "
            f"${report_value.overall.cost_total_usd:,.6f} "
            f"(实采 ${report_value.overall.cost_usd:,.6f} + "
            f"估算补充 ${report_value.overall.cost_estimated_usd:,.6f})"
        ),
        (
            "事件/会话: "
            f"{report_value.overall.events:,} / {report_value.overall.session_count:,}"
        ),
    ]
    if report_value.overall.first_timestamp_ms and report_value.overall.last_timestamp_ms:
        lines.append(
            "时间范围: "
            f"{iso_from_ms(report_value.overall.first_timestamp_ms)} 至 "
            f"{iso_from_ms(report_value.overall.last_timestamp_ms)}"
        )
    lines.append("")
    lines.append(f"{'分组':<28} {'总处理量':>14} {'非缓存I/O':>14} {'输出':>12} {'事件':>9}")
    for item in report_value.groups[:max_groups]:
        lines.append(
            f"{_clip(item.group, 28):<28} "
            f"{format_yi(item.processed_tokens):>14} "
            f"{format_yi(item.non_cached_input_tokens + item.output_tokens):>14} "
            f"{format_yi(item.output_tokens):>12} "
            f"{item.events:>9,}"
        )
    if len(report_value.groups) > max_groups:
        lines.append(f"... 另有 {len(report_value.groups) - max_groups} 个分组")
    if report_value.notes:
        lines.append("")
        for note in report_value.notes:
            lines.append(f"说明: {note}")
    return "\n".join(lines)


def render_csv(report_value: Report) -> str:
    fieldnames = [
        "group",
        "events",
        "sessions",
        "processed_tokens",
        "processed_yi",
        "input_tokens_total",
        "input_tokens_total_yi",
        "non_cached_input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "output_tokens_yi",
        "provider_total_tokens",
        "cost_usd",
        "cost_known_usd",
        "cost_estimated_usd",
        "cost_total_usd",
        "costed_events",
        "cost_estimated_events",
        "cost_unpriced_events",
        "cost_status",
        "first_time",
        "last_time",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in report_value.groups:
        data = item.to_dict()
        writer.writerow({key: data.get(key, "") for key in fieldnames})
    return output.getvalue()


def _scope_matches(event: UsageEvent, scope: str) -> bool:
    if scope == "visible":
        return True
    if scope == "native":
        return event.source_kind == SourceKind.NATIVE
    return event.source_kind in {SourceKind.NATIVE, SourceKind.AGGREGATE}


def _scope_notes(scope: str) -> list[str]:
    if scope == "primary":
        return [
            "日常总用量排除了会话镜像、网关代理和第三方代理统计，避免同一个请求被重复计算。",
            "聚合来源（如 DSH）只保留日志已有的日/路由汇总，不伪装成逐请求精确数据。",
        ]
    if scope == "native":
        return [
            "原始记录只包含来源明确、能直接定位到本机原始日志的记录。",
        ]
    return [
        "全部来源包含镜像、网关和代理记录，可能与原始记录重复，适合核对数据覆盖情况。",
    ]


def _group_value(event: UsageEvent, dimension: str) -> str:
    if dimension == "agent":
        return event.agent or "未标注"
    if dimension == "source":
        return event.source or "未标注"
    if dimension == "model":
        return event.model or "未标注"
    if dimension == "account":
        return event.account or "未标注"
    if dimension == "date":
        return day_from_ms(event.timestamp_ms) if event.timestamp_ms else "未标注"
    kind = str(event.source_kind)
    return KIND_LABELS.get(kind, kind)


def _clip(text: str, length: int) -> str:
    return text if len(text) <= length else text[: max(length - 1, 1)] + "…"
