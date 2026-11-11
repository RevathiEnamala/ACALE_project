"""Command-line demonstration for ACALE Phase 2 sensor simulation."""

import argparse
from pathlib import Path

from src.acale.simulation import AgriculturalSensorSimulator, SensorConfig, SUPPORTED_SCENARIOS


def parse_args():
    parser = argparse.ArgumentParser(description="Run the ACALE agricultural sensor simulator.")
    parser.add_argument("--readings", type=int, default=20,
                        help="Number of readings generated per sensor (default: 20).")
    parser.add_argument("--scenario", choices=sorted(SUPPORTED_SCENARIOS), default="normal",
                        help="Sensor scenario to simulate.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible results.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing existing output files.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.readings < 0:
        raise SystemExit("Error: --readings must be zero or greater.")

    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "data" / "sensor_data"
    config = SensorConfig(random_seed=args.seed)
    simulator = AgriculturalSensorSimulator(config)

    print("\nACALE Agricultural Sensor Simulation")
    print("------------------------------------")
    print(f"Scenario: {args.scenario}")
    print(f"Number of sensors: {len(config.sensor_ids)}")
    print(f"Readings per sensor: {args.readings}")

    readings = simulator.generate_readings(args.readings, args.scenario)
    print(f"Total readings generated: {len(readings)}")

    print("\nSample readings:")
    for reading in readings[: min(5, len(readings))]:
        print(
            f"{reading['sensor_id']} | "
            f"Moisture: {reading['soil_moisture']:.2f}% | "
            f"Temperature: {reading['temperature']:.2f} C | "
            f"Humidity: {reading['humidity']:.2f}% | "
            f"Event: {reading['event_type']}"
        )

    csv_path = AgriculturalSensorSimulator.export_csv(
        readings, output_dir / "sensor_readings.csv", allow_overwrite=args.overwrite
    )
    json_path = AgriculturalSensorSimulator.export_json(
        readings, output_dir / "sensor_readings.json", allow_overwrite=args.overwrite
    )

    print("\nExport completed:")
    print(csv_path)
    print(json_path)
    print("\nPhase 2 simulation finished.")


if __name__ == "__main__":
    main()
