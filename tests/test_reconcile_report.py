from __future__ import annotations

import unittest

from agent_token_ledger.model import Quality, SourceKind, UsageEvent
from agent_token_ledger.pipeline import reconcile
from agent_token_ledger.reporting import (
    build_scope_summaries,
    report,
    report_dimensions,
)


def _event(
    *,
    source: str,
    agent: str,
    kind: SourceKind,
    event_key: str,
    timestamp_ms: int = 1_800_000_000_000,
    input_tokens: int = 100,
    cached_input_tokens: int = 60,
    output_tokens: int = 20,
    quality: Quality = Quality.EXACT,
    metadata: dict | None = None,
) -> UsageEvent:
    return UsageEvent(
        event_key=event_key,
        source=source,
        agent=agent,
        source_kind=kind,
        timestamp_ms=timestamp_ms,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        input_includes_cached=True,
        input_includes_cache_write=True,
        quality=quality,
        session_id="session-1",
        metadata=metadata or {},
    )


class ReconcileAndReportTests(unittest.TestCase):
    def test_cockpit_mirror_is_removed_by_multiset_match(self) -> None:
        native = _event(
            source="codex_native",
            agent="Codex",
            kind=SourceKind.NATIVE,
            event_key="native-1",
            metadata={
                "file_id": "file-1",
                "session_sequence": 1,
                "source_root": "sessions",
            },
        )
        cockpit_overlap = _event(
            source="cockpit_session",
            agent="Codex",
            kind=SourceKind.DERIVED,
            event_key="cockpit-1",
            metadata={"file_id": "file-1"},
        )
        cockpit_extra = _event(
            source="cockpit_session",
            agent="Codex",
            kind=SourceKind.DERIVED,
            event_key="cockpit-2",
            input_tokens=200,
            metadata={"file_id": "file-1"},
        )

        events, issues = reconcile([native, cockpit_overlap, cockpit_extra])

        self.assertEqual(
            {event.event_key for event in events}, {"native-1", "cockpit-2"}
        )
        self.assertTrue(
            any(issue.code == "cockpit_native_overlap" for issue in issues)
        )

    def test_scopes_do_not_add_gateway_into_primary_total(self) -> None:
        timestamp_ms = 1_800_000_000_000
        events = [
            _event(
                source="codex_native",
                agent="Codex",
                kind=SourceKind.NATIVE,
                event_key="native",
                timestamp_ms=timestamp_ms,
            ),
            _event(
                source="dsh",
                agent="DeepSeek Harness",
                kind=SourceKind.AGGREGATE,
                event_key="dsh",
                timestamp_ms=timestamp_ms,
                quality=Quality.AGGREGATE,
            ),
            _event(
                source="cockpit_gateway",
                agent="Cockpit Gateway",
                kind=SourceKind.GATEWAY,
                event_key="gateway",
                timestamp_ms=timestamp_ms,
            ),
        ]

        primary = report(events, scope="primary", dimension="agent")
        native = report(events, scope="native", dimension="agent")
        visible = report(events, scope="visible", dimension="date")

        self.assertEqual(primary.overall.processed_tokens, 240)
        self.assertEqual(native.overall.processed_tokens, 120)
        self.assertEqual(visible.overall.processed_tokens, 360)
        self.assertEqual(visible.groups[0].group, "2027-01-15")

    def test_report_dimensions_matches_individual_reports(self) -> None:
        events = [
            _event(
                source="codex_native",
                agent="Codex",
                kind=SourceKind.NATIVE,
                event_key="native-a",
            ),
            _event(
                source="codex_native",
                agent="Codex",
                kind=SourceKind.NATIVE,
                event_key="native-b",
                input_tokens=200,
                output_tokens=40,
            ),
            _event(
                source="dsh",
                agent="DeepSeek Harness",
                kind=SourceKind.AGGREGATE,
                event_key="dsh",
                quality=Quality.AGGREGATE,
            ),
        ]

        dimensions = ("agent", "source", "model", "account", "date", "kind")
        batched = report_dimensions(
            events,
            scope="primary",
            dimensions=dimensions,
        )
        self.assertEqual(set(batched), set(dimensions))

        for dimension in dimensions:
            single = report(events, scope="primary", dimension=dimension)
            self.assertEqual(
                batched[dimension].overall.to_dict(),
                single.overall.to_dict(),
            )
            self.assertEqual(
                [group.to_dict() for group in batched[dimension].groups],
                [group.to_dict() for group in single.groups],
            )
            self.assertEqual(batched[dimension].notes, single.notes)

    def test_build_scope_summaries_matches_agent_report_overall(self) -> None:
        events = [
            _event(
                source="codex_native",
                agent="Codex",
                kind=SourceKind.NATIVE,
                event_key="native",
            ),
            _event(
                source="dsh",
                agent="DeepSeek Harness",
                kind=SourceKind.AGGREGATE,
                event_key="dsh",
                quality=Quality.AGGREGATE,
            ),
            _event(
                source="cockpit_gateway",
                agent="Cockpit Gateway",
                kind=SourceKind.GATEWAY,
                event_key="gateway",
            ),
        ]

        summaries = build_scope_summaries(
            events,
            scopes=("primary", "native", "visible"),
        )
        self.assertEqual(set(summaries), {"primary", "native", "visible"})

        for scope in ("primary", "native", "visible"):
            single = report(events, scope=scope, dimension="agent")
            self.assertEqual(
                summaries[scope]["overall"].to_dict(),
                single.overall.to_dict(),
            )
            self.assertEqual(summaries[scope]["notes"], single.notes)


if __name__ == "__main__":
    unittest.main()
