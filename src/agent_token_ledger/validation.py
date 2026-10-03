from __future__ import annotations

from .model import ScanIssue, UsageEvent


def validate_snapshot(
    events: list[UsageEvent],
    issues: list[dict],
) -> dict:
    semantic_unknown = [
        event
        for event in events
        if event.input_includes_cached is None
        or event.input_includes_cache_write is None
    ]
    provider_mismatches = [
        event
        for event in events
        if event.provider_total_tokens is not None
        and event.provider_total_tokens != event.processed_tokens
    ]
    known_reasoning_mismatches = [
        event
        for event in provider_mismatches
        if event.source == "codex_native"
        and event.metadata.get("format") == "legacy"
        and event.provider_total_tokens
        == event.input_tokens + event.output_tokens + event.reasoning_output_tokens
    ]
    known_ids = {id(event) for event in known_reasoning_mismatches}
    unknown_provider_mismatches = [
        event for event in provider_mismatches if id(event) not in known_ids
    ]
    errors = [item for item in issues if item["severity"] == "error"]
    warnings = [item for item in issues if item["severity"] == "warning"]
    return {
        "events": len(events),
        "errors": len(errors),
        "warnings": len(warnings),
        "semantic_unknown": len(semantic_unknown),
        "provider_total_mismatches": len(provider_mismatches),
        "known_reasoning_total_mismatches": len(known_reasoning_mismatches),
        "unknown_provider_total_mismatches": len(unknown_provider_mismatches),
        "passed": (
            not errors
            and not semantic_unknown
            and not unknown_provider_mismatches
        ),
    }
