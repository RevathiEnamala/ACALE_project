import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acale.edge.context_classifier import ClassifierConfig, classify_readings


def make_rows(values, sensor="S1"):
    return [
        {"sensor_id": sensor, "timestamp": f"2026-01-01T00:{i:02d}:00+00:00",
         "soil_moisture": value, "event_type": "NORMAL", "device_status": "OK"}
        for i, value in enumerate(values)
    ]


def test_normal_readings_remain_normal():
    result = classify_readings(make_rows([50, 49, 51, 50, 52]))
    assert all(row["context_state"] == "NORMAL" for row in result)


def test_persistent_low_moisture_becomes_critical():
    result = classify_readings(make_rows([45, 15, 14, 13]))
    assert result[1]["context_state"] == "NORMAL"
    assert result[3]["context_state"] == "CRITICAL"


def test_single_low_reading_does_not_trigger_critical():
    result = classify_readings(make_rows([45, 15, 45, 45]))
    assert all(row["context_state"] == "NORMAL" for row in result)


def test_emergency_bypasses_persistence():
    rows = make_rows([50, 50, 50])
    rows[1]["event_type"] = "EMERGENCY_ENVIRONMENTAL_CHANGE"
    result = classify_readings(rows)
    assert result[1]["context_state"] == "CRITICAL"
    assert result[1]["immediate_alert"] is True


def test_tampering_bypasses_persistence():
    rows = make_rows([50, 50, 145])
    rows[2]["event_type"] = "SIMULATED_SENSOR_TAMPERING"
    result = classify_readings(rows)
    assert result[2]["context_state"] == "CRITICAL"
    assert result[2]["classification_reason"] == "IMMEDIATE_SIMULATED_TAMPERING_ALERT"


def test_out_of_range_value_is_flagged():
    result = classify_readings(make_rows([50, 145]))
    assert result[1]["immediate_alert"] is True
    assert result[1]["context_state"] == "CRITICAL"


def test_sensors_are_classified_independently():
    rows = make_rows([50, 15, 14, 13], "S1") + make_rows([50, 50, 50, 50], "S2")
    result = classify_readings(rows)
    s2 = [row for row in result if row["sensor_id"] == "S2"]
    assert all(row["context_state"] == "NORMAL" for row in s2)


def test_recovery_transition():
    result = classify_readings(make_rows([45, 15, 14, 13, 40, 40, 40, 40, 40, 40]))
    assert result[3]["context_state"] == "CRITICAL"
    assert result[6]["context_state"] == "RECOVERY"
    assert result[9]["context_state"] == "NORMAL"


def test_config_validation():
    try:
        ClassifierConfig(ewma_alpha=0)
    except ValueError:
        return
    raise AssertionError("Invalid EWMA alpha should raise ValueError.")
