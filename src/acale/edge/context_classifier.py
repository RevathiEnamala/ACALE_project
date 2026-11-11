"""Adaptive context-aware classification for ACALE sensor readings.

Configurable simulation heuristic; not a crop-specific agronomic diagnosis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import math


@dataclass(frozen=True)
class ClassifierConfig:
    """Demo thresholds aligned with the current normal simulator dataset."""
    ewma_alpha: float = 0.30
    low_moisture_threshold: float = 20.0
    recovery_moisture_threshold: float = 25.0
    falling_slope_threshold: float = -2.0
    falling_slope_moisture_ceiling: float = 35.0
    trigger_persistence: int = 3
    recovery_persistence: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.ewma_alpha <= 1:
            raise ValueError("ewma_alpha must be in the interval (0, 1].")
        if self.trigger_persistence < 1 or self.recovery_persistence < 1:
            raise ValueError("Persistence values must be at least 1.")
        if self.low_moisture_threshold >= self.recovery_moisture_threshold:
            raise ValueError("Recovery threshold must exceed the low-moisture threshold.")


def _event_text(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key, "") or "").strip().upper()
        for key in ("event_type", "device_status")
    )


def _immediate_alert(record: dict[str, Any], moisture: float) -> tuple[bool, str]:
    event = _event_text(record)
    if "TAMPERING" in event:
        return True, "IMMEDIATE_SIMULATED_TAMPERING_ALERT"
    if "EMERGENCY" in event:
        return True, "IMMEDIATE_EMERGENCY_EVENT_BYPASS"
    if not math.isfinite(moisture):
        return True, "IMMEDIATE_INVALID_MOISTURE_VALUE"
    if moisture < 0 or moisture > 100:
        return True, "IMMEDIATE_OUT_OF_RANGE_SENSOR_VALUE"
    return False, ""


def classify_readings(
    readings: Iterable[dict[str, Any]],
    config: ClassifierConfig | None = None,
) -> list[dict[str, Any]]:
    """Classify readings independently per sensor in timestamp order.

    NORMAL -> CRITICAL after persistent low moisture or a strong falling trend.
    CRITICAL -> RECOVERY after persistent readings at/above recovery threshold.
    RECOVERY -> NORMAL after a second recovery confirmation period.
    A renewed risk during RECOVERY returns the state to CRITICAL.
    Emergency/tampering events and invalid/out-of-range values bypass persistence.
    """
    cfg = config or ClassifierConfig()
    rows = [dict(row) for row in readings]
    rows.sort(key=lambda row: (str(row.get("sensor_id", "")),
                               str(row.get("timestamp", ""))))
    states: dict[str, dict[str, Any]] = {}
    output: list[dict[str, Any]] = []

    for row in rows:
        sensor_id = str(row.get("sensor_id", "UNKNOWN_SENSOR"))
        try:
            moisture = float(row["soil_moisture"])
        except (KeyError, TypeError, ValueError):
            moisture = float("nan")

        state = states.setdefault(sensor_id, {
            "ewma": None,
            "context_state": "NORMAL",
            "trigger_streak": 0,
            "recovery_streak": 0,
        })

        immediate, immediate_reason = _immediate_alert(row, moisture)
        if math.isfinite(moisture):
            previous_ewma = state["ewma"]
            ewma = moisture if previous_ewma is None else (
                cfg.ewma_alpha * moisture + (1 - cfg.ewma_alpha) * previous_ewma
            )
            slope = None if previous_ewma is None else ewma - previous_ewma
            state["ewma"] = ewma
        else:
            ewma = state["ewma"]
            slope = None

        trend_risk = (
            slope is not None
            and slope <= cfg.falling_slope_threshold
            and ewma is not None
            and ewma <= cfg.falling_slope_moisture_ceiling
        )
        moisture_risk = math.isfinite(moisture) and (
            moisture <= cfg.low_moisture_threshold
        )
        risk = moisture_risk or trend_risk

        reason = "NO_PERSISTENT_RISK"
        if immediate:
            state["context_state"] = "CRITICAL"
            state["trigger_streak"] = cfg.trigger_persistence
            state["recovery_streak"] = 0
            reason = immediate_reason
        elif risk:
            state["trigger_streak"] += 1
            state["recovery_streak"] = 0
            if state["context_state"] == "RECOVERY":
                state["context_state"] = "CRITICAL"
                reason = "RISK_RETURNED_DURING_RECOVERY"
            elif state["context_state"] == "CRITICAL":
                reason = "CRITICAL_CONDITION_CONTINUES"
            elif state["trigger_streak"] >= cfg.trigger_persistence:
                state["context_state"] = "CRITICAL"
                reason = "PERSISTENT_MOISTURE_OR_FALLING_TREND"
            else:
                reason = "RISK_PENDING_PERSISTENCE"
        else:
            state["trigger_streak"] = 0
            if state["context_state"] == "CRITICAL":
                if math.isfinite(moisture) and moisture >= cfg.recovery_moisture_threshold:
                    state["recovery_streak"] += 1
                    if state["recovery_streak"] >= cfg.recovery_persistence:
                        state["context_state"] = "RECOVERY"
                        state["recovery_streak"] = 0
                        reason = "RECOVERY_THRESHOLD_PERSISTED"
                    else:
                        reason = "RECOVERY_CONFIRMATION_PENDING"
                else:
                    state["recovery_streak"] = 0
                    reason = "WAITING_FOR_RECOVERY_THRESHOLD"
            elif state["context_state"] == "RECOVERY":
                if math.isfinite(moisture) and moisture >= cfg.recovery_moisture_threshold:
                    state["recovery_streak"] += 1
                    if state["recovery_streak"] >= cfg.recovery_persistence:
                        state["context_state"] = "NORMAL"
                        state["recovery_streak"] = 0
                        reason = "RETURNED_TO_NORMAL_AFTER_RECOVERY"
                    else:
                        reason = "NORMAL_CONFIRMATION_PENDING"
                else:
                    state["context_state"] = "CRITICAL"
                    state["recovery_streak"] = 0
                    reason = "RECOVERY_THRESHOLD_NOT_MAINTAINED"
            else:
                state["recovery_streak"] = 0
                reason = "NORMAL_CONDITION"

        result = dict(row)
        result.update({
            "context_state": state["context_state"],
            "classification_reason": reason,
            "ewma_soil_moisture": round(ewma, 4) if ewma is not None else None,
            "ewma_slope": round(slope, 4) if slope is not None else None,
            "trigger_streak": state["trigger_streak"],
            "recovery_streak": state["recovery_streak"],
            "immediate_alert": immediate,
        })
        output.append(result)

    return output
