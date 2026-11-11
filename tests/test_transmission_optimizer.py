import copy
import pytest
from src.acale.edge.transmission_optimizer import optimize_transmissions

def packet(i, state="NORMAL"):
    return {"packet_id": f"P{i}", "aad": {"context_state": state},
            "ciphertext": f"cipher-{i}", "nonce": f"nonce-{i}", "tag": f"tag-{i}"}

def test_normal_packets_are_batched():
    batches, metrics = optimize_transmissions([packet(i) for i in range(12)], 5)
    assert [b["packet_count"] for b in batches] == [5, 5, 2]
    assert metrics["transmissions_after"] == 3

def test_urgent_packet_flushes_and_sends_immediately():
    items = [packet(1), packet(2), packet(3, "CRITICAL"), packet(4)]
    batches, metrics = optimize_transmissions(items, 5)
    assert [b["batch_type"] for b in batches] == ["NORMAL_BATCH", "IMMEDIATE", "NORMAL_BATCH"]
    assert metrics["immediate_packets"] == 1

def test_packet_content_and_order_preserved():
    items = [packet(1), packet(2, "EMERGENCY"), packet(3)]
    original = copy.deepcopy(items)
    batches, _ = optimize_transmissions(items, 5)
    assert [p for b in batches for p in b["packets"]] == original
    assert items == original

def test_string_aad_supported():
    p = {"aad": '{"context_state":"TAMPERING"}', "ciphertext": "x"}
    batches, _ = optimize_transmissions([p])
    assert batches[0]["batch_type"] == "IMMEDIATE"

def test_invalid_batch_size():
    with pytest.raises(ValueError):
        optimize_transmissions([packet(1)], 0)

def test_invalid_packet():
    with pytest.raises(ValueError):
        optimize_transmissions([packet(1), "bad"])

def test_empty_input():
    batches, metrics = optimize_transmissions([])
    assert batches == [] and metrics["packet_count"] == 0

def test_estimated_energy_reduced():
    _, metrics = optimize_transmissions([packet(i) for i in range(10)], 5)
    assert metrics["estimated_energy_after_mj"] < metrics["estimated_energy_before_mj"]

def test_multiple_urgent_packets_are_singletons():
    batches, metrics = optimize_transmissions([packet(1, "CRITICAL"), packet(2, "EMERGENCY")], 5)
    assert len(batches) == 2
    assert metrics["immediate_packets"] == 2
