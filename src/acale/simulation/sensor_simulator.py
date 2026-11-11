"""Reproducible agricultural IoT sensor simulation for ACALE Phase 2."""

from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SUPPORTED_SCENARIOS = {
    "normal",
    "gradual_moisture_reduction",
    "sudden_moisture_drop",
    "temperature_variation",
    "humidity_variation",
    "emergency",
    "sensor_tampering",
}

CSV_FIELDS = [
    "reading_id",
    "sensor_id",
    "timestamp",
    "soil_moisture",
    "temperature",
    "humidity",
    "event_type",
    "device_status",
]


@dataclass(frozen=True)
class SensorConfig:
    """Settings for the simulated sensors. Values can be changed by the user."""

    sensor_ids: tuple[str, ...] = (
        "SENSOR_001",
        "SENSOR_002",
        "SENSOR_003",
        "SENSOR_004",
        "SENSOR_005",
    )
    soil_moisture_min: float = 25.0
    soil_moisture_max: float = 70.0
    temperature_min: float = 20.0
    temperature_max: float = 35.0
    humidity_min: float = 35.0
    humidity_max: float = 85.0
    sampling_interval_seconds: int = 60
    random_seed: int = 42
    start_time: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __post_init__(self) -> None:
        if not self.sensor_ids:
            raise ValueError("At least one sensor ID must be configured.")
        if len(set(self.sensor_ids)) != len(self.sensor_ids):
            raise ValueError("Sensor IDs must be unique.")
        if any(not isinstance(item, str) or not item.strip() for item in self.sensor_ids):
            raise ValueError("Every sensor ID must be a non-empty string.")

        ranges = (
            ("soil moisture", self.soil_moisture_min, self.soil_moisture_max, True),
            ("temperature", self.temperature_min, self.temperature_max, False),
            ("humidity", self.humidity_min, self.humidity_max, True),
        )
        for label, low, high, percentage in ranges:
            if not math.isfinite(low) or not math.isfinite(high) or low >= high:
                raise ValueError(f"Invalid {label} range: minimum must be below maximum.")
            if percentage and (low < 0 or high > 100):
                raise ValueError(f"{label.title()} range must be within 0–100%.")
        if self.sampling_interval_seconds <= 0:
            raise ValueError("Sampling interval must be a positive number of seconds.")
        if self.start_time.tzinfo is None:
            raise ValueError("start_time must include a timezone.")


class AgriculturalSensorSimulator:
    """Generate deterministic sensor readings for a group of field devices."""

    def __init__(self, config: SensorConfig | None = None, seed: int | None = None):
        self.config = config or SensorConfig()
        actual_seed = self.config.random_seed if seed is None else seed
        self._rng = random.Random(actual_seed)
        self._counters = {sensor_id: 0 for sensor_id in self.config.sensor_ids}
        self._state: dict[str, dict[str, float]] = {}

        for sensor_id in self.config.sensor_ids:
            self._state[sensor_id] = {
                "soil_moisture": self._rng.uniform(
                    self.config.soil_moisture_min, self.config.soil_moisture_max
                ),
                "temperature": self._rng.uniform(
                    self.config.temperature_min, self.config.temperature_max
                ),
                "humidity": self._rng.uniform(
                    self.config.humidity_min, self.config.humidity_max
                ),
            }

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return round(max(low, min(high, value)), 2)

    def _next_reading(
        self, sensor_id: str, step: int, scenario: str
    ) -> dict[str, Any]:
        state = self._state[sensor_id]
        self._counters[sensor_id] += 1

        # Small random changes make ordinary readings vary naturally.
        moisture = state["soil_moisture"] + self._rng.uniform(-1.2, 1.2)
        temperature = state["temperature"] + self._rng.uniform(-0.8, 0.8)
        humidity = state["humidity"] + self._rng.uniform(-1.5, 1.5)

        low_m = self.config.soil_moisture_min
        high_m = self.config.soil_moisture_max
        low_t = self.config.temperature_min
        high_t = self.config.temperature_max
        low_h = self.config.humidity_min
        high_h = self.config.humidity_max

        event_type = "NORMAL"
        device_status = "ACTIVE"

        if scenario == "gradual_moisture_reduction":
            # Reduce moisture progressively, with a small random variation.
            moisture -= 1.5
            event_type = "GRADUAL_MOISTURE_REDUCTION"
        elif scenario == "sudden_moisture_drop":
            if step == max(0, 5 // 2):
                moisture -= 18.0
                event_type = "SUDDEN_MOISTURE_DROP"
            elif step > max(0, 5 // 2):
                event_type = "POST_MOISTURE_DROP"
        elif scenario == "temperature_variation":
            temperature += self._rng.uniform(-2.5, 2.5)
            event_type = "TEMPERATURE_VARIATION"
        elif scenario == "humidity_variation":
            humidity += self._rng.uniform(-5.0, 5.0)
            event_type = "HUMIDITY_VARIATION"
        elif scenario == "emergency":
            if step == 0:
                moisture -= 22.0
                temperature += 8.0
                event_type = "EMERGENCY_ENVIRONMENTAL_CHANGE"
                device_status = "EMERGENCY"
        elif scenario == "sensor_tampering":
            if step == 0:
                # Deliberately implausible test value; this is simulated tampering,
                # not a claim that a real attack has been detected.
                moisture = 145.0
                event_type = "SIMULATED_SENSOR_TAMPERING"
                device_status = "TAMPERING_SIMULATED"

        # The tampering scenario deliberately preserves its out-of-range value.
        if not (scenario == "sensor_tampering" and step == 0):
            # A stressed field may fall below the normal operating range.
            # Keep it within the physical percentage range, not the normal
            # baseline range, so gradual drying remains visible in the data.
            moisture = self._clamp(moisture, 0.0, 100.0)
        temperature = self._clamp(temperature, low_t, high_t)
        humidity = self._clamp(humidity, low_h, high_h)

        state["soil_moisture"] = moisture if 0 <= moisture <= 100 else state["soil_moisture"]
        state["temperature"] = temperature
        state["humidity"] = humidity

        timestamp = self.config.start_time + timedelta(
            seconds=step * self.config.sampling_interval_seconds
        )
        reading_id = f"{sensor_id}-R{self._counters[sensor_id]:06d}"

        return {
            "reading_id": reading_id,
            "sensor_id": sensor_id,
            "timestamp": timestamp.isoformat(),
            "soil_moisture": round(moisture, 2),
            "temperature": round(temperature, 2),
            "humidity": round(humidity, 2),
            "event_type": event_type,
            "device_status": device_status,
        }

    def generate_readings(
        self,
        readings_per_sensor: int = 20,
        scenario: str = "normal",
    ) -> list[dict[str, Any]]:
        """Generate readings for every configured sensor.

        The scenario is applied to each sensor. Calling this method repeatedly
        continues each sensor's reading counter and sensor state.
        """
        if not isinstance(readings_per_sensor, int) or isinstance(readings_per_sensor, bool):
            raise ValueError("readings_per_sensor must be an integer.")
        if readings_per_sensor < 0:
            raise ValueError("readings_per_sensor cannot be negative.")
        if scenario not in SUPPORTED_SCENARIOS:
            allowed = ", ".join(sorted(SUPPORTED_SCENARIOS))
            raise ValueError(f"Unknown scenario '{scenario}'. Choose one of: {allowed}")

        records: list[dict[str, Any]] = []
        for step in range(readings_per_sensor):
            for sensor_id in self.config.sensor_ids:
                records.append(self._next_reading(sensor_id, step, scenario))
        return records

    @staticmethod
    def validate_reading(reading: dict[str, Any]) -> None:
        """Validate required fields and ordinary physical ranges.

        The explicitly labelled simulated-tampering record is allowed to contain
        an out-of-range moisture value so it can be used as a test input later.
        """
        missing = [field for field in CSV_FIELDS if field not in reading]
        if missing:
            raise ValueError(f"Reading is missing required fields: {missing}")
        for field in ("soil_moisture", "temperature", "humidity"):
            value = reading[field]
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field} must be a finite number.")

        tampering = reading["event_type"] == "SIMULATED_SENSOR_TAMPERING"
        if not tampering:
            if not 0 <= reading["soil_moisture"] <= 100:
                raise ValueError("soil_moisture must be between 0 and 100.")
            if not 0 <= reading["humidity"] <= 100:
                raise ValueError("humidity must be between 0 and 100.")
        if not isinstance(reading["timestamp"], str) or not reading["timestamp"]:
            raise ValueError("timestamp must be a non-empty ISO 8601 string.")

    @classmethod
    def export_csv(
        cls,
        readings: list[dict[str, Any]],
        output_path: str | Path,
        allow_overwrite: bool = False,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not allow_overwrite:
            raise FileExistsError(
                f"{path} already exists. Set allow_overwrite=True to replace it."
            )
        for reading in readings:
            cls.validate_reading(reading)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(readings)
        return path

    @classmethod
    def export_json(
        cls,
        readings: list[dict[str, Any]],
        output_path: str | Path,
        allow_overwrite: bool = False,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not allow_overwrite:
            raise FileExistsError(
                f"{path} already exists. Set allow_overwrite=True to replace it."
            )
        for reading in readings:
            cls.validate_reading(reading)
        with path.open("w", encoding="utf-8") as file:
            json.dump(readings, file, indent=4, ensure_ascii=False)
        return path
