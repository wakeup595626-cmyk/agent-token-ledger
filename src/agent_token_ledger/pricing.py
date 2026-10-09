"""Model price table and reference cost estimation.

The ledger never invents a bill. It keeps two numbers apart:

* ``known`` - cost that a source log already provided.
* ``estimated`` - a reference supplement for events that carry tokens but no
  cost, priced with the best available rate.

Rate lookup order for a token event without a collected cost:

1. the implied blended rate of the same model (derived from its own costed
   events), which self-calibrates to whatever the user actually pays;
2. the persisted per-model rate of the cost anchor file, which remembers what
   real cost data taught earlier snapshots;
3. an explicit per-model price entry in the editable table stored in
   ``settings.json``;
4. the implied blended rate of the whole snapshot;
5. the persisted global rate of the cost anchor;
6. the ``"*"`` fallback entry of the price table.

The anchor exists because a snapshot can lose every costed event - for example
when the single source that collected real charges is uninstalled or its data
is removed. Without it, every remaining event would silently fall back to the
low placeholder prices and the reference total would collapse.

This guarantees a reference amount whenever tokens exist, which is what the
dashboard shows as the ``estimated supplement`` and ``reference total``.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model import UsageEvent

MILLION = 1_000_000.0
PRICE_FIELDS = ("input", "cached_input", "output")
FALLBACK_MODEL_KEY = "*"
COST_ANCHOR_FORMAT = "agent-token-ledger-cost-anchor"
COST_ANCHOR_SCHEMA_VERSION = 1
COST_ANCHOR_FILE_NAME = "cost_anchor_v1.json"
COST_ANCHOR_MAX_MODELS = 200

# USD per one million tokens. Values are deliberately moderate reference
# figures, not a claim about any specific contract price. Users can edit them
# in Settings and restore these defaults at any time.
DEFAULT_MODEL_PRICES: dict[str, dict[str, float]] = {
    FALLBACK_MODEL_KEY: {"input": 0.8, "cached_input": 0.08, "output": 4.0},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.0},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.0},
    "gpt-4.1": {"input": 2.0, "cached_input": 0.5, "output": 8.0},
    "gpt-4o": {"input": 2.5, "cached_input": 1.25, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.6},
    "o3": {"input": 2.0, "cached_input": 0.5, "output": 8.0},
    "o4-mini": {"input": 1.1, "cached_input": 0.275, "output": 4.4},
    "claude-opus-4": {"input": 15.0, "cached_input": 1.5, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "cached_input": 0.3, "output": 15.0},
    "claude-3-7-sonnet": {"input": 3.0, "cached_input": 0.3, "output": 15.0},
    "claude-3-5-haiku": {"input": 0.8, "cached_input": 0.08, "output": 4.0},
    "gemini-2.5-pro": {"input": 1.25, "cached_input": 0.31, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.3, "cached_input": 0.075, "output": 2.5},
    "deepseek-chat": {"input": 0.27, "cached_input": 0.07, "output": 1.1},
    "deepseek-reasoner": {"input": 0.55, "cached_input": 0.14, "output": 2.19},
    "qwen-max": {"input": 1.6, "cached_input": 0.4, "output": 6.4},
    "qwen-plus": {"input": 0.4, "cached_input": 0.1, "output": 1.2},
}


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Normalized price for one model, expressed in USD per million tokens."""

    input: float
    cached_input: float
    output: float

    def cost_usd(
        self,
        *,
        non_cached_input_tokens: int,
        cached_input_tokens: int,
        cache_write_tokens: int,
        output_tokens: int,
    ) -> float:
        # Cache writes are billed like fresh input by every provider that
        # exposes them, so they share the standard input rate.
        input_like = max(0, non_cached_input_tokens) + max(0, cache_write_tokens)
        return (
            input_like * self.input
            + max(0, cached_input_tokens) * self.cached_input
            + max(0, output_tokens) * self.output
        ) / MILLION

    def to_dict(self) -> dict[str, float]:
        return {
            "input": round(self.input, 6),
            "cached_input": round(self.cached_input, 6),
            "output": round(self.output, 6),
        }


@dataclass(slots=True)
class CostBreakdown:
    """Known and estimated cost for a set of events."""

    known_usd: float = 0.0
    estimated_usd: float = 0.0
    costed_events: int = 0
    estimated_events: int = 0
    unpriced_events: int = 0
    events: int = 0
    implicit_model_events: int = 0

    @property
    def total_usd(self) -> float:
        return self.known_usd + self.estimated_usd

    def to_dict(self) -> dict[str, float | int]:
        return {
            "cost_known_usd": round(self.known_usd, 6),
            "cost_estimated_usd": round(self.estimated_usd, 6),
            "cost_total_usd": round(self.total_usd, 6),
            "costed_events": self.costed_events,
            "cost_estimated_events": self.estimated_events,
            "cost_unpriced_events": self.unpriced_events,
            "cost_implicit_model_events": self.implicit_model_events,
        }


@dataclass(slots=True)
class CostAnchor:
    """Persisted implied rates learned from events that carried a real cost.

    The anchor is written to cost_anchor_v1.json in the data directory and is
    only consulted when the current snapshot has no costed evidence for an
    event. It lets the reference total survive a source whose data disappears.
    """

    global_rate_usd_per_million: float = 0.0
    model_rates_usd_per_million: dict[str, float] = field(default_factory=dict)
    costed_events: int = 0
    costed_tokens: int = 0
    known_usd: float = 0.0
    updated_at_ms: int = 0

    @property
    def usable(self) -> bool:
        return self.global_rate_usd_per_million > 0 or any(
            rate > 0 for rate in self.model_rates_usd_per_million.values()
        )

    def model_rate(self, model: str) -> float:
        """Return the learned blended rate (USD per million tokens) or 0."""

        return _anchor_model_rate(self.model_rates_usd_per_million, model)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": COST_ANCHOR_FORMAT,
            "schema_version": COST_ANCHOR_SCHEMA_VERSION,
            "updated_at_ms": int(self.updated_at_ms),
            "global_rate_usd_per_million": round(
                self.global_rate_usd_per_million, 9
            ),
            "model_rates_usd_per_million": {
                name: round(rate, 9)
                for name, rate in sorted(self.model_rates_usd_per_million.items())
                if rate > 0
            },
            "costed_events": int(self.costed_events),
            "costed_tokens": int(self.costed_tokens),
            "known_usd": round(self.known_usd, 8),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CostAnchor | None":
        if not isinstance(value, Mapping):
            return None
        declared_format = str(value.get("format") or "").strip()
        if declared_format and declared_format != COST_ANCHOR_FORMAT:
            return None
        try:
            schema_version = int(value.get("schema_version") or 0)
        except (TypeError, ValueError):
            return None
        if schema_version > COST_ANCHOR_SCHEMA_VERSION:
            return None
        raw_models = value.get("model_rates_usd_per_million")
        model_rates: dict[str, float] = {}
        if isinstance(raw_models, Mapping):
            for raw_name, raw_rate in raw_models.items():
                name = str(raw_name or "").strip()
                if not name or len(name) > 120:
                    continue
                rate = _bounded_price(raw_rate)
                if rate <= 0:
                    continue
                model_rates[name.casefold()] = rate
                if len(model_rates) >= COST_ANCHOR_MAX_MODELS:
                    break
        anchor = cls(
            global_rate_usd_per_million=_bounded_price(
                value.get("global_rate_usd_per_million")
            ),
            model_rates_usd_per_million=model_rates,
            costed_events=_non_negative_int(value.get("costed_events")),
            costed_tokens=_non_negative_int(value.get("costed_tokens")),
            known_usd=_bounded_price(value.get("known_usd")),
            updated_at_ms=_non_negative_int(value.get("updated_at_ms")),
        )
        return anchor if anchor.usable else None


def derive_cost_anchor(
    events: Iterable[UsageEvent],
    *,
    updated_at_ms: int = 0,
) -> CostAnchor | None:
    """Learn implied rates from events that already carry a real cost.

    Returns None when the snapshot holds no usable costed evidence, so a
    snapshot that never had real prices can not fabricate an anchor.
    """

    costed_events = 0
    known_usd = 0.0
    rate_cost = 0.0
    rate_tokens = 0
    model_totals: dict[str, list[float]] = {}
    for event in events:
        if event.cost_usd is None:
            continue
        costed_events += 1
        known_usd += event.cost_usd
        if event.processed_tokens <= 0 or event.cost_usd <= 0:
            continue
        rate_cost += event.cost_usd
        rate_tokens += event.processed_tokens
        name = str(event.model or "").strip().casefold()
        if name:
            bucket = model_totals.setdefault(name, [0.0, 0])
            bucket[0] += event.cost_usd
            bucket[1] += event.processed_tokens
    if costed_events <= 0 or rate_tokens <= 0 or rate_cost <= 0:
        return None
    model_rates: dict[str, float] = {}
    for name, (cost, tokens) in sorted(model_totals.items()):
        if tokens <= 0 or cost <= 0:
            continue
        rate = _bounded_price(cost / tokens * MILLION)
        if rate > 0:
            model_rates[name] = rate
        if len(model_rates) >= COST_ANCHOR_MAX_MODELS:
            break
    anchor = CostAnchor(
        global_rate_usd_per_million=_bounded_price(
            rate_cost / rate_tokens * MILLION
        ),
        model_rates_usd_per_million=model_rates,
        costed_events=costed_events,
        costed_tokens=rate_tokens,
        known_usd=known_usd,
        updated_at_ms=_non_negative_int(updated_at_ms),
    )
    return anchor if anchor.usable else None


def merge_cost_anchors(
    base: CostAnchor | None,
    learned: CostAnchor | None,
) -> CostAnchor | None:
    """Keep the newest evidence: global rate replaced, model rates merged."""

    if learned is None or not learned.usable:
        return base
    if base is None or not base.usable:
        return learned
    model_rates = dict(base.model_rates_usd_per_million)
    model_rates.update(learned.model_rates_usd_per_million)
    if len(model_rates) > COST_ANCHOR_MAX_MODELS:
        newest = set(learned.model_rates_usd_per_million)
        ordered = sorted(
            model_rates.items(),
            key=lambda item: (item[0] not in newest, item[0]),
        )
        model_rates = dict(ordered[:COST_ANCHOR_MAX_MODELS])
    return CostAnchor(
        global_rate_usd_per_million=(
            learned.global_rate_usd_per_million
            or base.global_rate_usd_per_million
        ),
        model_rates_usd_per_million=model_rates,
        costed_events=learned.costed_events,
        costed_tokens=learned.costed_tokens,
        known_usd=learned.known_usd,
        updated_at_ms=learned.updated_at_ms or base.updated_at_ms,
    )


def load_cost_anchor(path: str | Path) -> CostAnchor | None:
    """Read the persisted anchor; missing, broken or empty files return None."""

    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    try:
        return CostAnchor.from_dict(value)
    except Exception:  # A broken anchor must never break the dashboard.
        return None


def save_cost_anchor(path: str | Path, anchor: CostAnchor | None) -> bool:
    """Atomically persist the anchor; returns False instead of raising."""

    if anchor is None or not anchor.usable:
        return False
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(anchor.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            temporary.replace(target)
        except OSError as exc:
            # EFS-encrypted directories can reject os.replace with WinError 17
            # even when the temporary and target files are in the same folder.
            if getattr(exc, "winerror", None) != 17:
                raise
            shutil.copyfile(temporary, target)
            temporary.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def normalize_model_prices(value: Any) -> dict[str, dict[str, float]]:
    """Validate a persisted price table and merge it over the defaults."""

    normalized = {
        name: dict(price) for name, price in DEFAULT_MODEL_PRICES.items()
    }
    if not isinstance(value, Mapping):
        return normalized
    for raw_name, raw_price in value.items():
        name = str(raw_name or "").strip()
        if not name or len(name) > 120 or not isinstance(raw_price, Mapping):
            continue
        entry = normalized.get(name) or normalized.get(name.casefold())
        base = dict(entry) if entry else {
            "input": float(DEFAULT_MODEL_PRICES[FALLBACK_MODEL_KEY]["input"]),
            "cached_input": float(
                DEFAULT_MODEL_PRICES[FALLBACK_MODEL_KEY]["cached_input"]
            ),
            "output": float(DEFAULT_MODEL_PRICES[FALLBACK_MODEL_KEY]["output"]),
        }
        for field_name in PRICE_FIELDS:
            if field_name in raw_price:
                base[field_name] = _bounded_price(raw_price.get(field_name))
        normalized[name] = base
    return normalized


def resolve_price(
    model: str,
    prices: Mapping[str, Mapping[str, float]],
    *,
    include_fallback: bool = True,
) -> ModelPrice | None:
    """Find the best price entry for a model name."""

    name = str(model or "").strip()
    if not name:
        return (
            _as_price(prices.get(FALLBACK_MODEL_KEY)) if include_fallback else None
        )
    folded = name.casefold()
    direct = _lookup(prices, folded)
    if direct is not None:
        return direct

    best: tuple[int, ModelPrice] | None = None
    for key, value in prices.items():
        if key == FALLBACK_MODEL_KEY:
            continue
        candidate = str(key).strip().casefold()
        if len(candidate) < 3:
            continue
        if candidate in folded or folded in candidate:
            price = _as_price(value)
            if price is None:
                continue
            if best is None or len(candidate) > best[0]:
                best = (len(candidate), price)
    if best is not None:
        return best[1]
    if include_fallback:
        return _as_price(prices.get(FALLBACK_MODEL_KEY))
    return None


def estimate_event_cost_usd(
    event: UsageEvent,
    prices: Mapping[str, Mapping[str, float]],
    *,
    fallback_rate: float = 0.0,
    anchor: CostAnchor | None = None,
) -> tuple[float, str]:
    """Return ``(usd, source)`` for one event that has no collected cost."""

    if event.processed_tokens <= 0:
        return 0.0, "empty"
    if anchor is not None:
        anchor_rate = anchor.model_rate(event.model)
        if anchor_rate > 0:
            return (
                event.processed_tokens * anchor_rate / MILLION,
                "anchor_model",
            )
    price = resolve_price(event.model, prices, include_fallback=False)
    if price is not None:
        value = price.cost_usd(
            non_cached_input_tokens=event.non_cached_input_tokens,
            cached_input_tokens=event.cached_input_tokens,
            cache_write_tokens=event.cache_write_tokens,
            output_tokens=event.output_tokens,
        )
        if value > 0:
            return value, "table"
    if fallback_rate > 0:
        return event.processed_tokens * fallback_rate, "implied"
    if anchor is not None and anchor.global_rate_usd_per_million > 0:
        return (
            event.processed_tokens
            * anchor.global_rate_usd_per_million
            / MILLION,
            "anchor_global",
        )
    fallback_price = resolve_price(event.model, prices)
    if fallback_price is not None:
        value = fallback_price.cost_usd(
            non_cached_input_tokens=event.non_cached_input_tokens,
            cached_input_tokens=event.cached_input_tokens,
            cache_write_tokens=event.cache_write_tokens,
            output_tokens=event.output_tokens,
        )
        if value > 0:
            return value, "fallback"
    return 0.0, "unpriced"


def cost_breakdown(
    events: Iterable[UsageEvent],
    prices: Mapping[str, Mapping[str, float]],
    *,
    anchor: CostAnchor | None = None,
    baseline: Iterable[UsageEvent] | None = None,
) -> CostBreakdown:
    """Split known and estimated cost for a set of events.

    ``baseline`` is the evidence universe the implied rates are learned from.
    It defaults to ``events`` itself, which is right for a whole report. A
    caller that splits one set into several groups (the dashboard chart) must
    pass the same baseline to every group, otherwise each group would price
    itself with its own evidence and the parts would not add up to the whole.
    """

    items = list(events)
    breakdown = CostBreakdown(events=len(items))
    evidence = items if baseline is None else list(baseline)

    model_totals: dict[str, list[float]] = {}
    total_cost = 0.0
    total_tokens = 0
    for event in evidence:
        if event.cost_usd is None:
            continue
        total_cost += event.cost_usd
        total_tokens += event.processed_tokens
        if event.processed_tokens > 0:
            bucket = model_totals.setdefault(event.model.casefold(), [0.0, 0])
            bucket[0] += event.cost_usd
            bucket[1] += event.processed_tokens

    global_rate = total_cost / total_tokens if total_tokens else 0.0
    model_rates = {
        name: cost / tokens
        for name, (cost, tokens) in model_totals.items()
        if tokens > 0 and cost > 0
    }

    for event in items:
        if event.cost_usd is not None:
            breakdown.costed_events += 1
            breakdown.known_usd += event.cost_usd
            continue
        if event.processed_tokens <= 0:
            breakdown.unpriced_events += 1
            continue
        model_rate = model_rates.get(event.model.casefold(), 0.0)
        if model_rate > 0:
            breakdown.estimated_usd += event.processed_tokens * model_rate
            breakdown.estimated_events += 1
            breakdown.implicit_model_events += 1
            continue
        value, source = estimate_event_cost_usd(
            event,
            prices,
            fallback_rate=global_rate,
            anchor=anchor,
        )
        if source == "unpriced" or value <= 0:
            breakdown.unpriced_events += 1
            continue
        breakdown.estimated_usd += value
        breakdown.estimated_events += 1
        if source == "anchor_model":
            # The persisted per-model rate is an implied model rate as well.
            breakdown.implicit_model_events += 1

    return breakdown


def _lookup(
    prices: Mapping[str, Mapping[str, float]],
    folded_name: str,
) -> ModelPrice | None:
    if folded_name in prices:
        return _as_price(prices[folded_name])
    for key, value in prices.items():
        if str(key).strip().casefold() == folded_name:
            return _as_price(value)
    return None


def _as_price(value: Any) -> ModelPrice | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return ModelPrice(
            input=_bounded_price(value.get("input")),
            cached_input=_bounded_price(value.get("cached_input")),
            output=_bounded_price(value.get("output")),
        )
    except (TypeError, ValueError):
        return None


def _anchor_model_rate(rates: Mapping[str, float], model: str) -> float:
    """Look up a learned blended rate with the same matching as prices."""

    name = str(model or "").strip().casefold()
    if not name:
        return 0.0
    direct = rates.get(name)
    if direct is not None and direct > 0:
        return float(direct)
    best: tuple[int, float] | None = None
    for key, value in rates.items():
        candidate = str(key).strip().casefold()
        if len(candidate) < 3 or value <= 0:
            continue
        if candidate in name or name in candidate:
            if best is None or len(candidate) > best[0]:
                best = (len(candidate), float(value))
    return best[1] if best is not None else 0.0


def _non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _bounded_price(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed != parsed or parsed < 0:
        return 0.0
    return min(parsed, 100_000.0)


__all__ = [
    "COST_ANCHOR_FILE_NAME",
    "COST_ANCHOR_FORMAT",
    "COST_ANCHOR_SCHEMA_VERSION",
    "DEFAULT_MODEL_PRICES",
    "FALLBACK_MODEL_KEY",
    "CostAnchor",
    "CostBreakdown",
    "ModelPrice",
    "cost_breakdown",
    "derive_cost_anchor",
    "estimate_event_cost_usd",
    "load_cost_anchor",
    "merge_cost_anchors",
    "normalize_model_prices",
    "resolve_price",
    "save_cost_anchor",
]
