"""Run ACALE Phase 7 performance evaluation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from src.acale.evaluation.performance_evaluator import evaluate_project  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ACALE using Phase 2-6 output files.")
    parser.add_argument("--sensor-csv", default="data/sensor_data/sensor_readings.csv")
    parser.add_argument("--classification-json", default="data/simulation_results/context_classification.json")
    parser.add_argument("--encrypted-json", default="data/simulation_results/encrypted_sensor_packets.json")
    parser.add_argument("--batches-json", default="data/simulation_results/transmission_batches.json")
    parser.add_argument("--fog-json", default="data/simulation_results/fog_verification_results.json")
    parser.add_argument("--nonce-db", default="data/security/nonce_state.sqlite")
    parser.add_argument("--output-dir", default="results/performance")
    args = parser.parse_args()

    secret_hex = os.getenv("ACALE_MASTER_SECRET", "").strip()
    if not secret_hex:
        raise RuntimeError("ACALE_MASTER_SECRET is missing. Check the root .env file. Never paste it into chat.")
    try:
        master_secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise RuntimeError("ACALE_MASTER_SECRET must be hexadecimal.") from exc
    if len(master_secret) < 32:
        raise RuntimeError("ACALE_MASTER_SECRET must decode to at least 32 bytes.")

    result = evaluate_project(
        sensor_csv=args.sensor_csv,
        classification_json=args.classification_json,
        encrypted_json=args.encrypted_json,
        batches_json=args.batches_json,
        fog_json=args.fog_json,
        master_secret=master_secret,
        nonce_database=args.nonce_db,
        output_dir=args.output_dir,
    )

    crypto = result["cryptographic_performance"]
    tx = result["transmission_performance"]
    fog = result["fog_verification_performance"]
    print("\\nACALE Phase 7: Performance Evaluation")
    print("-------------------------------------")
    print(f"Sensor readings:                 {result['sensor_readings_in_csv']}")
    print(f"Encrypted packets:               {result['encrypted_packet_count']}")
    print(f"Mean encryption API latency:     {crypto['encryption_api_latency']['mean_ms']} ms/packet")
    print(f"Mean decryption API latency:     {crypto['decryption_api_latency']['mean_ms']} ms/packet")
    print(f"Transmission events before:      {tx['transmissions_before_batching']}")
    print(f"Transmission events after:       {tx['transmissions_after_batching']}")
    print(f"Transmission reduction:          {tx['transmission_reduction_percent']}%")
    print(f"Estimated energy saving:         {tx['estimated_energy_saving_percent']}% (simulation estimate)")
    print(f"Fog accepted/rejected/replayed:  {fog['accepted_packets']}/{fog['rejected_packets']}/{fog['replayed_packets']}")
    print(f"Report: {Path(args.output_dir, 'phase7_performance_report.json').resolve()}")
    print(f"Metrics CSV: {Path(args.output_dir, 'phase7_metrics.csv').resolve()}")
    print("Charts: transmission_comparison.png, crypto_latency.png, fog_verification.png")
    print("\\nNote: timing is local software measurement; energy is an illustrative simulation estimate.")


if __name__ == "__main__":
    main()
