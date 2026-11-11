"""Run ACALE Phase 3 context-aware classification on Phase 2 CSV data."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from acale.edge.context_classifier import classify_readings  # noqa: E402


def main() -> None:
    input_path = ROOT / "data" / "sensor_data" / "sensor_readings.csv"
    output_dir = ROOT / "data" / "simulation_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_output = output_dir / "context_classification.csv"
    json_output = output_dir / "context_classification.json"

    if not input_path.exists():
        raise FileNotFoundError(
            f"Phase 2 input not found: {input_path}. Run `python main.py` first."
        )

    with input_path.open("r", newline="", encoding="utf-8") as file:
        readings = list(csv.DictReader(file))

    results = classify_readings(readings)
    if not results:
        raise ValueError("The input CSV contains no sensor readings.")

    fields = list(results[0].keys())
    with csv_output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    with json_output.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    counts = {}
    for result in results:
        label = result["context_state"]
        counts[label] = counts.get(label, 0) + 1

    print("ACALE Phase 3: Context-Aware Classification")
    print("-------------------------------------------")
    print(f"Input readings: {len(readings)}")
    print(f"Output CSV: {csv_output}")
    print(f"Output JSON: {json_output}")
    print("\nClassification counts:")
    for label in ("NORMAL", "CRITICAL", "RECOVERY"):
        print(f"{label}: {counts.get(label, 0)}")
    print("\nSample classified readings:")
    for item in results[:5]:
        print(
            f'{item.get("sensor_id")} | '
            f'Moisture: {item.get("soil_moisture")}% | '
            f'State: {item.get("context_state")} | '
            f'Reason: {item.get("classification_reason")}'
        )


if __name__ == "__main__":
    main()
