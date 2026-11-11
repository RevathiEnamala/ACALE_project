import csv
import json
from datetime import datetime, timezone

import pytest

from src.acale.simulation.sensor_simulator import (
    AgriculturalSensorSimulator,
    SensorConfig,
    SUPPORTED_SCENARIOS,
)


def make_simulator(seed=123):
    return AgriculturalSensorSimulator(SensorConfig(random_seed=seed))


def test_default_sensor_initialization_and_unique_ids():
    simulator = make_simulator()
    assert len(simulator.config.sensor_ids) == 5
    assert len(set(simulator.config.sensor_ids)) == 5


def test_reading_fields_and_unique_reading_ids():
    readings = make_simulator().generate_readings(3)
    assert len(readings) == 15
    expected = {
        "reading_id", "sensor_id", "timestamp", "soil_moisture",
        "temperature", "humidity", "event_type", "device_status",
    }
    assert all(set(row) == expected for row in readings)
    ids = [row["reading_id"] for row in readings]
    assert len(ids) == len(set(ids))


def test_timestamps_are_iso_8601_and_timezone_aware():
    readings = make_simulator().generate_readings(2)
    parsed = [datetime.fromisoformat(row["timestamp"]) for row in readings]
    assert all(value.tzinfo is not None for value in parsed)


def test_normal_values_are_in_physical_ranges():
    readings = make_simulator().generate_readings(20, "normal")
    for row in readings:
        assert 0 <= row["soil_moisture"] <= 100
        assert 0 <= row["humidity"] <= 100
        assert 0 <= row["temperature"] <= 100


def test_gradual_moisture_scenario_is_labelled_and_decreases():
    readings = make_simulator().generate_readings(8, "gradual_moisture_reduction")
    first_sensor = [r for r in readings if r["sensor_id"] == "SENSOR_001"]
    assert all(r["event_type"] == "GRADUAL_MOISTURE_REDUCTION" for r in first_sensor)
    assert first_sensor[-1]["soil_moisture"] < first_sensor[0]["soil_moisture"]


def test_sudden_drop_is_labelled():
    readings = make_simulator().generate_readings(5, "sudden_moisture_drop")
    assert any(r["event_type"] == "SUDDEN_MOISTURE_DROP" for r in readings)


def test_temperature_scenario_is_labelled():
    readings = make_simulator().generate_readings(3, "temperature_variation")
    assert all(r["event_type"] == "TEMPERATURE_VARIATION" for r in readings)


def test_humidity_scenario_is_labelled():
    readings = make_simulator().generate_readings(3, "humidity_variation")
    assert all(r["event_type"] == "HUMIDITY_VARIATION" for r in readings)


def test_emergency_scenario_is_labelled():
    readings = make_simulator().generate_readings(2, "emergency")
    assert sum(r["event_type"] == "EMERGENCY_ENVIRONMENTAL_CHANGE" for r in readings) == 5
    assert all(
        r["device_status"] == "EMERGENCY"
        for r in readings
        if r["event_type"] == "EMERGENCY_ENVIRONMENTAL_CHANGE"
    )


def test_tampering_is_explicitly_labelled_and_can_be_out_of_range():
    readings = make_simulator().generate_readings(2, "sensor_tampering")
    tampered = [r for r in readings if r["event_type"] == "SIMULATED_SENSOR_TAMPERING"]
    assert len(tampered) == 5
    assert all(r["soil_moisture"] > 100 for r in tampered)
    assert all(r["device_status"] == "TAMPERING_SIMULATED" for r in tampered)


def test_same_seed_produces_same_readings():
    a = AgriculturalSensorSimulator(SensorConfig(random_seed=777)).generate_readings(4)
    b = AgriculturalSensorSimulator(SensorConfig(random_seed=777)).generate_readings(4)
    assert a == b


def test_different_seed_changes_readings():
    a = AgriculturalSensorSimulator(SensorConfig(random_seed=1)).generate_readings(2)
    b = AgriculturalSensorSimulator(SensorConfig(random_seed=2)).generate_readings(2)
    assert a != b


def test_csv_export(tmp_path):
    readings = make_simulator().generate_readings(2)
    path = AgriculturalSensorSimulator.export_csv(
        readings, tmp_path / "nested" / "readings.csv"
    )
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len(readings)
    assert rows[0]["sensor_id"] == readings[0]["sensor_id"]


def test_json_export(tmp_path):
    readings = make_simulator().generate_readings(2)
    path = AgriculturalSensorSimulator.export_json(readings, tmp_path / "readings.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == readings


def test_empty_dataset_export(tmp_path):
    csv_path = AgriculturalSensorSimulator.export_csv([], tmp_path / "empty.csv")
    json_path = AgriculturalSensorSimulator.export_json([], tmp_path / "empty.json")
    assert len(list(csv.DictReader(csv_path.open(encoding="utf-8")))) == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == []


def test_existing_file_is_not_overwritten_by_default(tmp_path):
    path = tmp_path / "readings.json"
    path.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        AgriculturalSensorSimulator.export_json([], path)
    assert path.read_text(encoding="utf-8") == "keep me"


def test_invalid_sensor_count_and_duplicate_ids():
    with pytest.raises(ValueError):
        SensorConfig(sensor_ids=())
    with pytest.raises(ValueError):
        SensorConfig(sensor_ids=("SENSOR_001", "SENSOR_001"))


def test_invalid_reading_count_and_scenario():
    simulator = make_simulator()
    with pytest.raises(ValueError):
        simulator.generate_readings(-1)
    with pytest.raises(ValueError):
        simulator.generate_readings(1, "not_a_real_scenario")


def test_validate_rejects_invalid_normal_moisture():
    invalid = {
        "reading_id": "r1",
        "sensor_id": "s1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "soil_moisture": 120,
        "temperature": 25,
        "humidity": 50,
        "event_type": "NORMAL",
        "device_status": "ACTIVE",
    }
    with pytest.raises(ValueError):
        AgriculturalSensorSimulator.validate_reading(invalid)


def test_all_scenario_names_are_available():
    assert {
        "normal", "gradual_moisture_reduction", "sudden_moisture_drop",
        "temperature_variation", "humidity_variation", "emergency",
        "sensor_tampering",
    } == SUPPORTED_SCENARIOS
