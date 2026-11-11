import base64
import json

from src.acale.edge.secure_channel import SecureChannel
from src.acale.fog.fog_verifier import FogNodeVerifier, flatten_packet_input


def make_channel(tmp_path):
    return SecureChannel(
        master_secret=b"A" * 32,
        nonce_database=tmp_path / "nonce_state.sqlite",
        device_id="SENSOR_TEST",
        key_epoch=1,
    )


def make_packet(channel, reading_id="R1"):
    return channel.encrypt_record({
        "reading_id": reading_id,
        "sensor_id": "SENSOR_TEST",
        "timestamp": "2026-11-04T10:00:00Z",
        "context_state": "NORMAL",
        "soil_moisture": 42.5,
    })


def make_verifier(tmp_path):
    return FogNodeVerifier(
        master_secret=b"A" * 32,
        nonce_database=tmp_path / "nonce_state.sqlite",
        replay_database=tmp_path / "fog_replay.sqlite",
    )


def test_valid_packet_accepted(tmp_path):
    channel = make_channel(tmp_path)
    packet = make_packet(channel)
    verifier = make_verifier(tmp_path)
    status, reason, record = verifier.verify_one(packet)
    assert status == "ACCEPTED"
    assert record["reading_id"] == "R1"


def test_same_packet_detected_as_replay(tmp_path):
    channel = make_channel(tmp_path)
    packet = make_packet(channel)
    verifier = make_verifier(tmp_path)
    assert verifier.verify_one(packet)[0] == "ACCEPTED"
    status, reason, _ = verifier.verify_one(packet)
    assert status == "REPLAY"
    assert reason == "REPLAYED_NONCE"


def test_duplicate_reading_id_with_new_nonce_detected(tmp_path):
    channel = make_channel(tmp_path)
    first = make_packet(channel, "DUPLICATE_ID")
    second = make_packet(channel, "DUPLICATE_ID")
    verifier = make_verifier(tmp_path)
    assert verifier.verify_one(first)[0] == "ACCEPTED"
    status, reason, _ = verifier.verify_one(second)
    assert status == "REPLAY"
    assert reason == "REPLAYED_READING_ID"


def test_tampered_ciphertext_rejected_and_not_registered(tmp_path):
    channel = make_channel(tmp_path)
    packet = make_packet(channel)
    damaged = dict(packet)
    raw = bytearray(base64.b64decode(damaged["ciphertext"]))
    raw[0] ^= 1
    damaged["ciphertext"] = base64.b64encode(raw).decode("ascii")
    verifier = make_verifier(tmp_path)
    assert verifier.verify_one(damaged)[0] == "REJECTED"
    # The original valid packet remains eligible because failed authentication
    # must not poison the replay database.
    assert verifier.verify_one(packet)[0] == "ACCEPTED"


def test_tampered_aad_rejected(tmp_path):
    channel = make_channel(tmp_path)
    packet = make_packet(channel)
    packet["aad"] = dict(packet["aad"])
    packet["aad"]["context_state"] = "CRITICAL"
    assert make_verifier(tmp_path).verify_one(packet)[0] == "REJECTED"


def test_wrong_master_secret_rejected(tmp_path):
    packet = make_packet(make_channel(tmp_path))
    verifier = FogNodeVerifier(
        master_secret=b"B" * 32,
        nonce_database=tmp_path / "other_nonce.sqlite",
        replay_database=tmp_path / "other_replay.sqlite",
    )
    assert verifier.verify_one(packet)[0] == "REJECTED"


def test_phase5_batch_structure_flattened_in_order():
    packets = [{"id": 1}, {"id": 2}, {"id": 3}]
    payload = {"batches": [
        {"batch_type": "NORMAL_BATCH", "packets": packets[:2]},
        {"batch_type": "IMMEDIATE", "packets": packets[2:]},
    ]}
    flattened = flatten_packet_input(payload)
    assert [item[0] for item in flattened] == [0, 1, 2]
    assert [item[1] for item in flattened] == ["NORMAL_BATCH", "NORMAL_BATCH", "IMMEDIATE"]
    assert [item[2] for item in flattened] == packets


def test_result_summary_counts_statuses(tmp_path):
    channel = make_channel(tmp_path)
    packet = make_packet(channel)
    verifier = make_verifier(tmp_path)
    batch_items = [(0, "NORMAL_BATCH", packet), (1, "NORMAL_BATCH", packet)]
    result = verifier.verify_batches(batch_items)
    assert result["accepted_packets"] == 1
    assert result["replayed_packets"] == 1
    assert result["rejected_packets"] == 0
