from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from .pricing import DEFAULT_MODEL_PRICES, normalize_model_prices

DEFAULT_PREFERENCES: dict[str, Any] = {
    "language": "zh-CN",
    "currency": "CNY",
    "exchange_rate": 7.2,
    "refresh_seconds": 30,
    "theme": "light",
    "model_prices": {name: dict(price) for name, price in DEFAULT_MODEL_PRICES.items()},
}

SUPPORTED_LANGUAGES = {"zh-CN", "en-US"}
SUPPORTED_CURRENCIES = {"CNY", "USD"}
SUPPORTED_THEMES = {"light", "dark", "system"}


class PreferenceStore:
    """Read and write validated application preferences on the local machine."""

    def __init__(self, path: Path):
        self.path = Path(path)

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return copy.deepcopy(DEFAULT_PREFERENCES)
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return copy.deepcopy(DEFAULT_PREFERENCES)
        return normalize_preferences(value)

    def save(self, value: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_preferences(value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            temporary.replace(self.path)
        except OSError as exc:
            # EFS-encrypted directories can reject os.replace with WinError 17
            # even when the temporary and target files are in the same folder.
            if getattr(exc, "winerror", None) != 17:
                raise
            shutil.copyfile(temporary, self.path)
            temporary.unlink(missing_ok=True)
        return normalized


def normalize_preferences(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    normalized = copy.deepcopy(DEFAULT_PREFERENCES)

    language = str(data.get("language") or "").strip()
    if language in SUPPORTED_LANGUAGES:
        normalized["language"] = language

    currency = str(data.get("currency") or "").strip().upper()
    if currency in SUPPORTED_CURRENCIES:
        normalized["currency"] = currency

    exchange_rate = _bounded_float(
        data.get("exchange_rate"),
        minimum=0.01,
        maximum=100.0,
        default=float(DEFAULT_PREFERENCES["exchange_rate"]),
    )
    normalized["exchange_rate"] = round(exchange_rate, 4)

    refresh_seconds = _bounded_int(
        data.get("refresh_seconds"),
        minimum=10,
        maximum=3600,
        default=int(DEFAULT_PREFERENCES["refresh_seconds"]),
    )
    normalized["refresh_seconds"] = refresh_seconds

    theme = str(data.get("theme") or "").strip().lower()
    if theme in SUPPORTED_THEMES:
        normalized["theme"] = theme

    normalized["model_prices"] = normalize_model_prices(
        data.get("model_prices")
    )

    return normalized


def merge_preferences(
    current: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(current)
    merged.update(updates)
    return normalize_preferences(merged)


def _bounded_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def _bounded_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    default: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return min(maximum, max(minimum, parsed))
