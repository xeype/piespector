from __future__ import annotations


def format_bytes(size: int) -> str:
    units = ("B", "kB", "MB", "GB", "TB")
    value = float(max(size, 0))
    unit_index = 0

    while value >= 1000 and unit_index < len(units) - 1:
        value /= 1000
        unit_index += 1

    if unit_index < len(units) - 1 and round(value, 1) >= 1000:
        value /= 1000
        unit_index += 1

    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"

    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{formatted} {units[unit_index]}"
