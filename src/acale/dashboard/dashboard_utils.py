
"""Safe data-loading and summary utilities for the ACALE dashboard.

The dashboard reads existing Phase 2–7 outputs. It does not modify
sensor data, encryption state, nonce databases, or replay-protection state.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    """Load a JSON file safely. Return None if unavailable or invalid."""

    path = Path(path)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    except (OSError, json.JSONDecodeError):
        return None


def load_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load CSV rows as dictionaries."""

    path = Path(path)

    if not path.exists():
        return []

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:

            return list(csv.DictReader(handle))

    except OSError:
        return []


def find_dicts_with_key(
    value: Any,
    key: str,
) -> list[dict[str, Any]]:
    """Recursively find dictionaries containing a given key."""

    found: list[dict[str, Any]] = []

    if isinstance(value, dict):

        if key in value:
            found.append(value)

        for child in value.values():
            found.extend(
                find_dicts_with_key(child, key)
            )

    elif isinstance(value, list):

        for child in value:
            found.extend(
                find_dicts_with_key(child, key)
            )

    return found


def extract_packet_count(value: Any) -> int:
    """Count packets in common Phase 4, 5, and 6 JSON structures."""

    if isinstance(value, list):

        return sum(
            1 for item in value
            if isinstance(item, dict)
        )

    if not isinstance(value, dict):
        return 0

    # Check common top-level packet collections.
    for key in (
        "packets",
        "encrypted_packets",
        "results",
        "batches",
    ):

        child = value.get(key)

        if isinstance(child, list):

            if key == "batches":

                total = 0

                for batch in child:

                    if isinstance(batch, dict):

                        packets = batch.get("packets", [])

                        if isinstance(packets, list):
                            total += len(packets)

                if total:
                    return total

            else:
                return len(child)

    # Fallback: count dictionaries containing ciphertext.
    return len(
        find_dicts_with_key(value, "ciphertext")
    )


def extract_batch_count(value: Any) -> int:
    """Return the number of transmission batches."""

    if isinstance(value, dict):

        batches = value.get("batches")

        if isinstance(batches, list):
            return len(batches)

    return 0


def safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value to a finite-looking numeric fallback."""

    try:

        result = float(value)

        if result != result:
            return default

        return result

    except (TypeError, ValueError):
        return default


def read_metric(
    report: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    """Read a metric from a flat or nested Phase 7 report."""

    if not isinstance(report, dict):
        return default

    containers = [report]

    if isinstance(report.get("metrics"), dict):
        containers.insert(
            0,
            report["metrics"],
        )

    for container in containers:

        for key in keys:

            if key in container:
                return container[key]

    return default
