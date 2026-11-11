import json
from src.acale.evaluation.performance_evaluator import (
    extract_packets, count_context_states, timing_summary,
    transmission_metrics, fog_metrics, packet_size_bytes,
)

def test_extract_phase4_packet_list():
    packets = [{"device_id": "S1"}, {"device_id": "S2"}]
    assert extract_packets(packets) == packets

def test_extract_phase5_batches():
    p1, p2 = {"id": 1}, {"id": 2}
    payload = {"batches": [{"packets": [p1]}, {"packets": [p2]}]}
    assert extract_packets(payload) == [p1, p2]

def test_context_state_counts_nested_json():
    payload = {"records": [
        {"context_state": "NORMAL"},
        {"context_state": "CRITICAL"},
        {"context_state": "NORMAL"},
    ]}
    assert count_context_states(payload) == {"CRITICAL": 1, "NORMAL": 2}

def test_timing_summary_statistics():
    summary = timing_summary([1.0, 2.0, 3.0, 4.0])
    assert summary["sample_count"] == 4
    assert summary["mean_ms"] == 2.5
    assert summary["median_ms"] == 2.5
    assert summary["min_ms"] == 1.0

def test_transmission_reduction_calculation():
    payload = {"metrics": {"transmissions_before": 100, "transmissions_after": 20}}
    result = transmission_metrics(100, payload)
    assert result["transmission_reduction_percent"] == 80.0

def test_fog_metrics_percentages():
    result = fog_metrics({
        "total_packets": 100, "accepted_packets": 98,
        "rejected_packets": 1, "replayed_packets": 1,
    })
    assert result["acceptance_percent"] == 98.0
    assert result["rejection_percent"] == 1.0

def test_packet_size_is_positive():
    assert packet_size_bytes({"ciphertext": "abc"}) > 0

def test_empty_timing_summary():
    assert timing_summary([])["mean_ms"] is None
