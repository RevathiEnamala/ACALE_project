"""ACALE Phase 7: reproducible performance evaluation from phase artifacts."""
from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any, Iterable


STATE_KEYS = ("context_state", "state", "risk_state", "classification", "current_state")


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_packets(payload: Any) -> list[dict[str, Any]]:
    """Read Phase 4 packet lists or Phase 5 batch output."""
    if isinstance(payload, list):
        packets = payload
    elif isinstance(payload, dict) and isinstance(payload.get("batches"), list):
        packets = []
        for batch in payload["batches"]:
            if isinstance(batch, dict) and isinstance(batch.get("packets"), list):
                packets.extend(batch["packets"])
    elif isinstance(payload, dict):
        packets = payload.get("packets", payload.get("encrypted_packets"))
    else:
        packets = None
    if not isinstance(packets, list) or any(not isinstance(p, dict) for p in packets):
        raise ValueError("Could not locate a list of encrypted packet objects in the JSON file.")
    return packets


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100.0
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def timing_summary(milliseconds: list[float]) -> dict[str, Any]:
    if not milliseconds:
        return {"sample_count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None, "min_ms": None, "max_ms": None}
    return {
        "sample_count": len(milliseconds),
        "mean_ms": round(statistics.mean(milliseconds), 6),
        "median_ms": round(statistics.median(milliseconds), 6),
        "p95_ms": round(percentile(milliseconds, 95), 6),
        "min_ms": round(min(milliseconds), 6),
        "max_ms": round(max(milliseconds), 6),
    }


def count_context_states(payload: Any) -> dict[str, int]:
    """Count context labels from Phase 3 JSON without assuming one exact wrapper."""
    counts: dict[str, int] = {}
    seen_dict_ids: set[int] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            # Count each record-like dictionary at most once.
            if id(node) not in seen_dict_ids:
                seen_dict_ids.add(id(node))
                for key in STATE_KEYS:
                    value = node.get(key)
                    if isinstance(value, str) and value.strip():
                        label = value.strip().upper()
                        counts[label] = counts.get(label, 0) + 1
                        break
            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(payload)
    return dict(sorted(counts.items()))


def count_csv_rows(path: str | Path) -> int:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def packet_size_bytes(packet: dict[str, Any]) -> int:
    return len(json.dumps(packet, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def transmission_metrics(phase4_count: int, phase5_payload: Any) -> dict[str, Any]:
    if not isinstance(phase5_payload, dict):
        raise ValueError("Phase 5 output must be a JSON object containing metrics.")
    metrics = phase5_payload.get("metrics", {})
    before = int(metrics.get("transmissions_before", phase4_count))
    after = int(metrics.get("transmissions_after", len(phase5_payload.get("batches", []))))
    reduction = ((before - after) / before * 100.0) if before else 0.0
    return {
        "phase4_encrypted_packets": phase4_count,
        "transmissions_before_batching": before,
        "transmissions_after_batching": after,
        "transmission_reduction_percent": round(reduction, 3),
        "normal_packets_batched": metrics.get("normal_packets_batched"),
        "immediate_packets": metrics.get("immediate_packets"),
        "estimated_energy_before_mj": metrics.get("estimated_energy_before_mj"),
        "estimated_energy_after_mj": metrics.get("estimated_energy_after_mj"),
        "estimated_energy_saved_mj": metrics.get("estimated_energy_saved_mj"),
        "estimated_energy_saving_percent": metrics.get("estimated_energy_saving_percent"),
        "energy_estimate_status": (metrics.get("energy_model") or {}).get(
            "status", "status_not_provided_by_phase5"
        ),
    }


def fog_metrics(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Phase 6 output must be a JSON object.")
    total = int(payload.get("total_packets", 0))
    accepted = int(payload.get("accepted_packets", 0))
    rejected = int(payload.get("rejected_packets", 0))
    replayed = int(payload.get("replayed_packets", 0))
    return {
        "packets_checked": total,
        "accepted_packets": accepted,
        "rejected_packets": rejected,
        "replayed_packets": replayed,
        "acceptance_percent": round(accepted / total * 100.0, 3) if total else None,
        "rejection_percent": round(rejected / total * 100.0, 3) if total else None,
        "replay_detection_count": replayed,
    }


def benchmark_crypto(
    encrypted_packets: list[dict[str, Any]],
    master_secret: bytes,
    nonce_database: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Measure real local SecureChannel API timings; plaintext stays in memory.

    Decryption uses actual Phase 4 packets and the existing Phase 4 key/nonce
    state. Encryption uses a fresh, independent benchmark-only master key and
    temporary nonce DB to avoid nonce reuse with production/simulation keys.
    """
    from src.acale.edge.secure_channel import SecureChannel

    decrypt_ms: list[float] = []
    records: list[dict[str, Any]] = []
    receiver_channels: dict[tuple[str, int], SecureChannel] = {}

    for packet in encrypted_packets:
        device_id = packet.get("device_id")
        epoch = packet.get("key_epoch")
        if not isinstance(device_id, str) or not isinstance(epoch, int):
            raise ValueError("An encrypted packet is missing device_id or key_epoch.")
        channel_key = (device_id, epoch)
        if channel_key not in receiver_channels:
            receiver_channels[channel_key] = SecureChannel(
                master_secret=master_secret,
                nonce_database=nonce_database,
                device_id=device_id,
                key_epoch=epoch,
            )
        start = time.perf_counter_ns()
        record = receiver_channels[channel_key].decrypt_record(packet)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        decrypt_ms.append(elapsed)
        records.append(record)

    # Independent benchmark key + independent SQLite nonce store. This is
    # deliberately not the Phase 4 master key or nonce database.
    import secrets

    benchmark_secret = secrets.token_bytes(32)
    # Keep the benchmark nonce database outside a temporary directory. SQLite
    # may retain database/WAL handles briefly on Windows, preventing temporary
    # directory cleanup (WinError 32). A fresh random benchmark key is created
    # for each run, so its derived key IDs have independent nonce counters.
    benchmark_nonce_db = Path(nonce_database).with_name("phase7_benchmark_nonce.sqlite")
    benchmark_nonce_db.parent.mkdir(parents=True, exist_ok=True)
    sender_channels: dict[tuple[str, int], SecureChannel] = {}
    encrypt_ms: list[float] = []
    for record in records:
        device_id = str(record.get("sensor_id") or "BENCHMARK_DEVICE")
        epoch = 1
        channel_key = (device_id, epoch)
        if channel_key not in sender_channels:
            sender_channels[channel_key] = SecureChannel(
                master_secret=benchmark_secret,
                nonce_database=benchmark_nonce_db,
                device_id=device_id,
                key_epoch=epoch,
            )
        start = time.perf_counter_ns()
        sender_channels[channel_key].encrypt_record(record)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        encrypt_ms.append(elapsed)
    # Release channel objects before returning; the benchmark database is
    # intentionally retained and is never the Phase 4 nonce database.
    sender_channels.clear()

    return {
        "algorithm": "ChaCha20-Poly1305",
        "key_derivation": "HKDF-SHA256",
        "measurement_method": "local wall-clock SecureChannel API timing using time.perf_counter_ns",
        "encryption_api_latency": timing_summary(encrypt_ms),
        "decryption_api_latency": timing_summary(decrypt_ms),
        "encryption_timing_note": "Includes persistent SQLite nonce allocation and packet envelope construction.",
        "decryption_timing_note": "Measures authenticated decryption of the actual Phase 4 encrypted packets.",
        "hardware_energy_measured": False,
    }, records


def write_csv(path: str | Path, rows: list[tuple[str, Any, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value", "unit_or_note"])
        writer.writerows(rows)


def create_charts(output_dir: str | Path, transmission: dict[str, Any], crypto: dict[str, Any], fog: dict[str, Any]) -> list[str]:
    """Create simple PNG charts; returns generated filenames."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    before = transmission["transmissions_before_batching"]
    after = transmission["transmissions_after_batching"]
    fig, ax = plt.subplots()
    ax.bar(["Before batching", "After batching"], [before, after])
    ax.set_title("Transmission Events: Baseline vs ACALE")
    ax.set_ylabel("Transmission events")
    fig.tight_layout()
    path = output_dir / "transmission_comparison.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    generated.append(path.name)

    enc = crypto["encryption_api_latency"]["mean_ms"]
    dec = crypto["decryption_api_latency"]["mean_ms"]
    fig, ax = plt.subplots()
    ax.bar(["Encryption API", "Decryption API"], [enc or 0, dec or 0])
    ax.set_title("Mean Cryptographic API Latency")
    ax.set_ylabel("Milliseconds per packet")
    fig.tight_layout()
    path = output_dir / "crypto_latency.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    generated.append(path.name)

    fig, ax = plt.subplots()
    ax.bar(["Accepted", "Rejected", "Replay"], [
        fog["accepted_packets"], fog["rejected_packets"], fog["replayed_packets"]
    ])
    ax.set_title("Fog Node Verification Results")
    ax.set_ylabel("Packets")
    fig.tight_layout()
    path = output_dir / "fog_verification.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    generated.append(path.name)
    return generated


def evaluate_project(
    sensor_csv: str | Path,
    classification_json: str | Path,
    encrypted_json: str | Path,
    batches_json: str | Path,
    fog_json: str | Path,
    master_secret: bytes,
    nonce_database: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sensor_count = count_csv_rows(sensor_csv)
    classification_payload = load_json(classification_json)
    state_counts = count_context_states(classification_payload)
    encrypted_packets = extract_packets(load_json(encrypted_json))
    batch_payload = load_json(batches_json)
    fog_payload = load_json(fog_json)

    crypto, _records = benchmark_crypto(encrypted_packets, master_secret, nonce_database)
    transmission = transmission_metrics(len(encrypted_packets), batch_payload)
    fog = fog_metrics(fog_payload)

    packet_sizes = [packet_size_bytes(packet) for packet in encrypted_packets]
    result = {
        "project": "ACALE",
        "phase": 7,
        "evaluation_scope": "software simulation and local API timing",
        "sensor_readings_in_csv": sensor_count,
        "context_classification_state_counts": state_counts,
        "encrypted_packet_count": len(encrypted_packets),
        "encrypted_packet_size_bytes": {
            "mean": round(statistics.mean(packet_sizes), 2) if packet_sizes else None,
            "min": min(packet_sizes) if packet_sizes else None,
            "max": max(packet_sizes) if packet_sizes else None,
            "total": sum(packet_sizes),
        },
        "cryptographic_performance": crypto,
        "transmission_performance": transmission,
        "fog_verification_performance": fog,
        "limitations": [
            "Encryption and decryption timings are local software wall-clock measurements and vary by computer load and hardware.",
            "Encryption timing includes persistent SQLite nonce allocation and envelope construction.",
            "Phase 5 energy figures are illustrative simulation estimates, not physical hardware measurements.",
            "Classification counts are descriptive only; accuracy, precision, recall and F1 require ground-truth labels.",
            "No physical radio, sensor battery, or agricultural field deployment was measured.",
        ],
    }

    json_path = output_dir / "phase7_performance_report.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    rows = [
        ("Sensor readings", sensor_count, "records"),
        ("Encrypted packets", len(encrypted_packets), "packets"),
        ("Mean encrypted packet size", result["encrypted_packet_size_bytes"]["mean"], "bytes"),
        ("Mean encryption API latency", crypto["encryption_api_latency"]["mean_ms"], "ms/packet"),
        ("Mean decryption API latency", crypto["decryption_api_latency"]["mean_ms"], "ms/packet"),
        ("Transmission events before batching", transmission["transmissions_before_batching"], "events"),
        ("Transmission events after batching", transmission["transmissions_after_batching"], "events"),
        ("Transmission reduction", transmission["transmission_reduction_percent"], "%"),
        ("Estimated energy saving", transmission["estimated_energy_saving_percent"], "% (simulation estimate)"),
        ("Fog accepted", fog["accepted_packets"], "packets"),
        ("Fog rejected", fog["rejected_packets"], "packets"),
        ("Fog replay detected", fog["replayed_packets"], "packets"),
    ]
    for state, count in state_counts.items():
        rows.append((f"Context state: {state}", count, "records"))
    write_csv(output_dir / "phase7_metrics.csv", rows)
    charts = create_charts(output_dir, transmission, crypto, fog)
    result["generated_charts"] = charts
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    return result
