from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.pricing import (
    COST_ANCHOR_FILE_NAME,
    DEFAULT_MODEL_PRICES,
    cost_breakdown,
    derive_cost_anchor,
    load_cost_anchor,
    merge_cost_anchors,
    save_cost_anchor,
)
from agent_token_ledger.reporting import report, report_dimensions
from agent_token_ledger.webapp import LedgerService, ScanPayload


def _event(
    *,
    event_key: str,
    agent: str = "Codex",
    source: str = "codex_native",
    kind: SourceKind = SourceKind.NATIVE,
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
) -> UsageEvent:
    return UsageEvent(
        event_key=event_key,
        source=source,
        agent=agent,
        source_kind=kind,
        timestamp_ms=1_800_000_000_000,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        input_includes_cached=True,
        input_includes_cache_write=True,
        cost_usd=cost_usd,
    )


class CostAnchorFileTests(unittest.TestCase):
    def test_derived_anchor_round_trips_through_the_data_file(self) -> None:
        event = _event(
            event_key="paid",
            model="paid-model",
            input_tokens=1_000_000,
            cost_usd=2.0,
        )
        anchor = derive_cost_anchor([event], updated_at_ms=1234)
        self.assertIsNotNone(anchor)
        assert anchor is not None
        self.assertAlmostEqual(anchor.global_rate_usd_per_million, 2.0)
        self.assertAlmostEqual(anchor.model_rate("paid-model"), 2.0)
        self.assertEqual(anchor.costed_events, 1)

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / COST_ANCHOR_FILE_NAME
            self.assertTrue(save_cost_anchor(path, anchor))
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            loaded = load_cost_anchor(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertAlmostEqual(
                loaded.global_rate_usd_per_million,
                anchor.global_rate_usd_per_million,
            )
            self.assertAlmostEqual(
                loaded.model_rate("paid-model"),
                anchor.model_rate("paid-model"),
            )
            self.assertEqual(loaded.costed_events, anchor.costed_events)
            self.assertEqual(loaded.updated_at_ms, 1234)
            data = json.loads(raw.decode("utf-8"))
            self.assertEqual(data["format"], "agent-token-ledger-cost-anchor")
            self.assertEqual(len(data["model_rates_usd_per_million"]), 1)

    def test_load_rejects_missing_broken_or_foreign_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / COST_ANCHOR_FILE_NAME
            self.assertIsNone(load_cost_anchor(path))

            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(load_cost_anchor(path))

            path.write_text(
                json.dumps({"format": "other-tool", "schema_version": 1}),
                encoding="utf-8",
            )
            self.assertIsNone(load_cost_anchor(path))

            path.write_text(
                json.dumps(
                    {
                        "format": "agent-token-ledger-cost-anchor",
                        "schema_version": 99,
                        "global_rate_usd_per_million": 3.0,
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(load_cost_anchor(path))

            for broken in (
                {"global_rate_usd_per_million": -5},
                {"global_rate_usd_per_million": "abc"},
                {"global_rate_usd_per_million": 0, "model_rates": {}},
                {"global_rate_usd_per_million": 0, "model_rates": {"m": 0}},
            ):
                payload = dict(broken)
                payload["format"] = "agent-token-ledger-cost-anchor"
                payload["schema_version"] = 1
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertIsNone(load_cost_anchor(path), payload)

    def test_derive_returns_none_when_nothing_real_was_collected(self) -> None:
        self.assertIsNone(
            derive_cost_anchor(
                [
                    _event(
                        event_key="free",
                        model="paid-model",
                        input_tokens=1_000_000,
                    )
                ]
            )
        )
        self.assertIsNone(
            derive_cost_anchor(
                [
                    _event(
                        event_key="zero",
                        model="paid-model",
                        input_tokens=1_000_000,
                        cost_usd=0.0,
                    )
                ]
            )
        )
        self.assertIsNone(
            derive_cost_anchor(
                [_event(event_key="tokenless", model="paid-model", cost_usd=1.5)]
            )
        )

    def test_merge_replaces_global_rate_and_merges_models(self) -> None:
        base = derive_cost_anchor(
            [
                _event(
                    event_key="a",
                    model="a-model",
                    input_tokens=1_000_000,
                    cost_usd=1.0,
                ),
                _event(
                    event_key="b",
                    model="b-model",
                    input_tokens=1_000_000,
                    cost_usd=2.0,
                ),
            ]
        )
        learned = derive_cost_anchor(
            [
                _event(
                    event_key="b2",
                    model="b-model",
                    input_tokens=1_000_000,
                    cost_usd=4.0,
                )
            ]
        )
        merged = merge_cost_anchors(base, learned)
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertAlmostEqual(merged.global_rate_usd_per_million, 4.0)
        self.assertAlmostEqual(merged.model_rate("a-model"), 1.0)
        self.assertAlmostEqual(merged.model_rate("b-model"), 4.0)
        self.assertIs(merge_cost_anchors(None, None), None)
        self.assertIs(merge_cost_anchors(base, None), base)


class CostAnchorEstimationTests(unittest.TestCase):
    def test_estimates_survive_a_source_that_disappeared(self) -> None:
        paid = _event(
            event_key="paid",
            model="paid-model",
            input_tokens=1_000_000,
            cost_usd=2.0,
        )
        survivor = _event(
            event_key="survivor",
            model="custom-model",
            input_tokens=1_000_000,
        )
        anchor = derive_cost_anchor([paid])

        without_anchor = cost_breakdown([survivor], DEFAULT_MODEL_PRICES)
        with_anchor = cost_breakdown(
            [survivor], DEFAULT_MODEL_PRICES, anchor=anchor
        )

        self.assertAlmostEqual(without_anchor.total_usd, 0.8)
        self.assertAlmostEqual(with_anchor.total_usd, 2.0)

    def test_snapshot_rate_beats_anchor_and_table_beats_anchor_global(self) -> None:
        anchor = derive_cost_anchor(
            [
                _event(
                    event_key="anchor",
                    model="custom-model",
                    input_tokens=1_000_000,
                    cost_usd=9.0,
                )
            ]
        )
        same_model_costed = _event(
            event_key="same-model",
            model="custom-model",
            input_tokens=1_000_000,
            cost_usd=5.0,
        )
        same_model_plain = _event(
            event_key="same-model-plain",
            model="custom-model",
            input_tokens=1_000_000,
        )
        breakdown = cost_breakdown(
            [same_model_costed, same_model_plain],
            DEFAULT_MODEL_PRICES,
            anchor=anchor,
        )
        self.assertAlmostEqual(breakdown.estimated_usd, 5.0)
        self.assertEqual(breakdown.implicit_model_events, 1)

        tabled = _event(
            event_key="tabled",
            model="gpt-5",
            input_tokens=1_000_000,
        )
        tabled_breakdown = cost_breakdown(
            [tabled], DEFAULT_MODEL_PRICES, anchor=anchor
        )
        self.assertAlmostEqual(tabled_breakdown.estimated_usd, 1.25)

        unknown = _event(
            event_key="unknown",
            model="misc-model",
            input_tokens=1_000_000,
        )
        unknown_breakdown = cost_breakdown(
            [unknown], DEFAULT_MODEL_PRICES, anchor=anchor
        )
        self.assertAlmostEqual(unknown_breakdown.estimated_usd, 9.0)

    def test_anchor_model_rate_beats_the_placeholder_table(self) -> None:
        anchor = derive_cost_anchor(
            [
                _event(
                    event_key="learned",
                    model="gpt-5-mini",
                    input_tokens=1_000_000,
                    cost_usd=7.0,
                )
            ]
        )
        event = _event(
            event_key="later",
            model="gpt-5-mini",
            input_tokens=1_000_000,
        )
        breakdown = cost_breakdown(
            [event], DEFAULT_MODEL_PRICES, anchor=anchor
        )
        self.assertAlmostEqual(breakdown.estimated_usd, 7.0)
        self.assertEqual(breakdown.implicit_model_events, 1)

    def test_grouped_reports_keep_the_same_reference_total(self) -> None:
        paid = _event(
            event_key="paid",
            agent="PaidAgent",
            model="paid-model",
            input_tokens=1_000_000,
            cost_usd=2.0,
        )
        plain = _event(
            event_key="plain",
            agent="PlainAgent",
            model="custom-model",
            input_tokens=1_000_000,
        )
        anchor = derive_cost_anchor([paid, plain])

        reports = report_dimensions(
            [plain],
            scope="primary",
            dimensions=("agent", "source", "model", "kind"),
            anchor=anchor,
        )
        group_total = sum(
            group.cost_total_usd for group in reports["agent"].groups
        )
        self.assertAlmostEqual(
            group_total, reports["agent"].overall.cost_total_usd
        )
        self.assertAlmostEqual(
            reports["agent"].overall.cost_estimated_usd, 2.0
        )

        collapsed = report([plain], scope="primary", dimension="agent")
        self.assertAlmostEqual(collapsed.overall.cost_estimated_usd, 0.8)
        group_collapsed = sum(
            group.cost_total_usd for group in collapsed.groups
        )
        self.assertAlmostEqual(group_collapsed, 0.8)


class GroupedReportConsistencyTests(unittest.TestCase):
    """分片（图表）之和必须等于整体（总额卡片）。

    真实故障：某个分组自己带着实采费用，别的分组没有，于是两组各自用组内
    证据定价，图表求和就与总额卡片对不上。现在由同一个证据全集决定单价。
    """

    def setUp(self) -> None:
        self.paid = _event(
            event_key="paid",
            agent="Codex",
            model="paid-model",
            input_tokens=1_000_000,
            cost_usd=2.0,
        )
        self.plain_same = _event(
            event_key="plain-same",
            agent="Codex",
            model="paid-model",
            input_tokens=1_000_000,
        )
        self.plain_other = _event(
            event_key="plain-other",
            agent="Other",
            source="other_native",
            model="mystery-model",
            input_tokens=1_000_000,
        )
        self.events = [self.paid, self.plain_same, self.plain_other]

    def _groups(self, reports):
        return sum(group.cost_total_usd for group in reports.groups)

    def test_parts_add_up_when_only_one_group_has_real_costs(self) -> None:
        for anchor in (None, derive_cost_anchor([self.paid])):
            with self.subTest(anchor=anchor is not None):
                reports = report_dimensions(
                    self.events,
                    scope="primary",
                    dimensions=("agent", "model", "source"),
                    anchor=anchor,
                )
                for dimension, value in reports.items():
                    self.assertAlmostEqual(
                        self._groups(value),
                        value.overall.cost_total_usd,
                        msg=dimension,
                    )

    def test_single_dimension_report_adds_up_too(self) -> None:
        collapsed = report(
            self.events, scope="primary", dimension="agent", prices={}
        )
        self.assertAlmostEqual(
            self._groups(collapsed), collapsed.overall.cost_total_usd
        )



class CostAnchorServiceTests(unittest.TestCase):
    def test_service_learns_and_reuses_the_anchor_after_a_source_is_lost(self) -> None:
        paid = _event(
            event_key="paid",
            model="paid-model",
            input_tokens=1_000_000,
            cost_usd=2.0,
        )
        plain = _event(
            event_key="plain",
            model="custom-model",
            input_tokens=1_000_000,
        )
        first_payload = ScanPayload(
            events=[paid, plain], issues=[], sources=[], snapshots=[]
        )
        second_payload = ScanPayload(
            events=[plain], issues=[], sources=[], snapshots=[]
        )
        payloads = [first_payload, second_payload]
        calls = {"index": 0}

        def scanner() -> ScanPayload:
            value = payloads[min(calls["index"], len(payloads) - 1)]
            calls["index"] += 1
            return value

        with tempfile.TemporaryDirectory() as temp:
            work_dir = Path(temp)
            service = LedgerService(
                work_dir=work_dir,
                refresh_seconds=30,
                scanner=scanner,
            )
            self.assertTrue(service.scan_once())
            first = service.snapshot()
            self.assertTrue((work_dir / COST_ANCHOR_FILE_NAME).is_file())
            self.assertTrue(first["cost_anchor"]["active"])
            self.assertAlmostEqual(
                first["scopes"]["primary"]["cost_estimated_usd"], 2.0
            )

            self.assertTrue(service.scan_once())
            second = service.snapshot()
            self.assertEqual(second["scopes"]["primary"]["costed_events"], 0)
            self.assertAlmostEqual(
                second["scopes"]["primary"]["cost_estimated_usd"], 2.0
            )
            self.assertTrue(
                any("单价锚点" in note for note in second["notes"]),
                second["notes"],
            )

            visible = service.filtered_report({"scope": "visible"})
            self.assertAlmostEqual(
                visible["overall"]["cost_estimated_usd"], 2.0
            )
            self.assertTrue(
                any("单价锚点" in note for note in visible["notes"]),
                visible["notes"],
            )


if __name__ == "__main__":
    unittest.main()
