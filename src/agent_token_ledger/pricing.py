"""Model price table and reference cost estimation.

The ledger never invents a bill. It keeps two numbers apart:

* ``known`` - cost that a source log already provided.
* ``estimated`` - a reference supplement for events that carry tokens but no
  cost, priced with the best available rate.

Rate lookup order for a token event without a collected cost:

1. the implied blended rate of the same model (derived from its own costed
   events), which self-calibrates to whatever the user actually pays;
2. an explicit per-model price entry in the editable table stored in
   ``settings.json``;
3. the implied blended rate of the whole snapshot;
4. the ``"*"`` fallback entry of the price table.

This guarantees a reference amount whenever tokens exist, which is what the
dashboard shows as the ``estimated supplement`` and ``reference total``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .model import UsageEvent

MILLION = 1_000_000.0
PRICE_FIELDS = ("input", "cached_input", "output")
FALLBACK_MODEL_KEY = "*"

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
) -> tuple[float, str]:
    """Return ``(usd, source)`` for one event that has no collected cost."""

    if event.processed_tokens <= 0:
        return 0.0, "empty"
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
) -> CostBreakdown:
    """Split known and estimated cost for a set of events."""

    items = list(events)
    breakdown = CostBreakdown(events=len(items))

    model_totals: dict[str, list[float]] = {}
    total_cost = 0.0
    total_tokens = 0
    for event in items:
        if event.cost_usd is None:
            continue
        breakdown.costed_events += 1
        breakdown.known_usd += event.cost_usd
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
        )
        if source == "unpriced" or value <= 0:
            breakdown.unpriced_events += 1
            continue
        breakdown.estimated_usd += value
        breakdown.estimated_events += 1

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


def _bounded_price(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed != parsed or parsed < 0:
        return 0.0
    return min(parsed, 100_000.0)


__all__ = [
    "DEFAULT_MODEL_PRICES",
    "FALLBACK_MODEL_KEY",
    "CostBreakdown",
    "ModelPrice",
    "cost_breakdown",
    "estimate_event_cost_usd",
    "normalize_model_prices",
    "resolve_price",
]
