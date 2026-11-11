import json
from pathlib import Path

URGENT = {"CRITICAL", "EMERGENCY", "TAMPERING", "SIMULATED_SENSOR_TAMPERING"}

def context_state(packet):
    candidates = [packet]
    for key in ("aad", "associated_data", "metadata", "header"):
        value = packet.get(key)
        if isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            except json.JSONDecodeError:
                pass
    for item in candidates:
        for key in ("context_state", "state", "risk_state", "classification"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().upper()
    return "NORMAL"

def load_packets(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Encrypted packet file not found: {path}")
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        packets = payload
    elif isinstance(payload, dict):
        packets = payload.get("packets", payload.get("encrypted_packets"))
    else:
        packets = None
    if not isinstance(packets, list) or any(not isinstance(p, dict) for p in packets):
        raise ValueError("Expected a list of packet objects, or an object containing 'packets'/'encrypted_packets'.")
    return packets

def optimize_transmissions(packets, batch_size=5, fixed_tx_energy_mj=1.0, energy_per_byte_mj=0.0001):
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer.")
    if fixed_tx_energy_mj < 0 or energy_per_byte_mj < 0:
        raise ValueError("Energy parameters cannot be negative.")
    packets = list(packets)
    if any(not isinstance(p, dict) for p in packets):
        raise ValueError("Every packet must be a dictionary.")
    batches, pending = [], []
    def flush():
        nonlocal pending
        if pending:
            batches.append({"batch_type": "NORMAL_BATCH", "packet_count": len(pending), "packets": pending})
            pending = []
    for packet in packets:
        state = context_state(packet)
        if state in URGENT or state.startswith(("CRITICAL", "EMERGENCY")):
            flush()
            batches.append({"batch_type": "IMMEDIATE", "packet_count": 1, "packets": [packet]})
        else:
            pending.append(packet)
            if len(pending) >= batch_size:
                flush()
    flush()
    sizes = [len(json.dumps(p, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) for p in packets]
    total_bytes = sum(sizes)
    before = len(packets) * fixed_tx_energy_mj + total_bytes * energy_per_byte_mj
    after = len(batches) * fixed_tx_energy_mj + total_bytes * energy_per_byte_mj
    saved = max(0.0, before - after)
    normal = sum(b["packet_count"] for b in batches if b["batch_type"] == "NORMAL_BATCH")
    immediate = sum(b["packet_count"] for b in batches if b["batch_type"] == "IMMEDIATE")
    metrics = {
        "packet_count": len(packets),
        "transmissions_before": len(packets),
        "transmissions_after": len(batches),
        "normal_packets_batched": normal,
        "immediate_packets": immediate,
        "payload_bytes": total_bytes,
        "estimated_energy_before_mj": round(before, 6),
        "estimated_energy_after_mj": round(after, 6),
        "estimated_energy_saved_mj": round(saved, 6),
        "estimated_energy_saving_percent": round(saved / before * 100, 3) if before else 0.0,
        "energy_model": {
            "fixed_energy_per_transmission_mj": fixed_tx_energy_mj,
            "energy_per_payload_byte_mj": energy_per_byte_mj,
            "status": "illustrative_simulation_estimate_not_hardware_measurement"
        }
    }
    return batches, metrics

def run_optimizer(input_path, output_path, batch_size=5):
    packets = load_packets(input_path)
    batches, metrics = optimize_transmissions(packets, batch_size=batch_size)
    output = {"phase": 5, "algorithm": "context_aware_adaptive_packet_batching",
              "batch_size": batch_size, "metrics": metrics, "batches": batches}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    return metrics
