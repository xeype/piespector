from __future__ import annotations

from typing import Any

from .models import OptionList


def normalize_value(value: str, options: OptionList) -> str:
    """Return *value* if it exists in *options*, otherwise the first option's value."""
    option_values = {opt.value for opt in options}
    return value if value in option_values else options[0].value


def compute_signature(options: OptionList, value: str) -> tuple[Any, ...]:
    """Return an equality-comparable signature for *options* + *value*."""
    return (options, value)


def sync_needed(
    options: OptionList,
    value: str,
    current_signature: tuple[Any, ...] | None,
) -> bool:
    """Return ``True`` if the widget needs to be updated."""
    return compute_signature(options, value) != current_signature
