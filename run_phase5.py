import argparse
from pathlib import Path
from src.acale.edge.transmission_optimizer import run_optimizer

def main():
    parser = argparse.ArgumentParser(description="Run ACALE Phase 5 transmission optimizer.")
    parser.add_argument("--input", default="data/simulation_results/encrypted_sensor_packets.json")
    parser.add_argument("--output", default="data/simulation_results/transmission_batches.json")
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()
    metrics = run_optimizer(args.input, args.output, args.batch_size)
    print("\\nACALE Phase 5: Adaptive Transmission Optimization")
    print("-----------------------------------------------")
    for label, key in [
        ("Encrypted packets processed", "packet_count"),
        ("Transmission events before", "transmissions_before"),
        ("Transmission events after", "transmissions_after"),
        ("Normal packets batched", "normal_packets_batched"),
        ("Immediate packets", "immediate_packets"),
        ("Estimated energy before (mJ)", "estimated_energy_before_mj"),
        ("Estimated energy after (mJ)", "estimated_energy_after_mj"),
        ("Estimated energy saved (mJ)", "estimated_energy_saved_mj"),
        ("Estimated saving (%)", "estimated_energy_saving_percent")]:
        print(f"{label}: {metrics[key]}")
    print(f"Output: {Path(args.output).resolve()}")
    print("Note: energy values are illustrative estimates, not measured hardware energy.")

if __name__ == "__main__":
    main()
