import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acale.edge.secure_channel import SecureChannel


MASTER = bytes.fromhex("11" * 32)
RECORD = {
    "reading_id": "R-001",
    "sensor_id": "SENSOR_001",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "soil_moisture": 42.5,
    "context_state": "NORMAL",
}


def make_channel(tmp_path, device="SENSOR_001", epoch=1):
    return SecureChannel(MASTER, tmp_path / "nonce.sqlite", device, epoch)


def test_encrypt_decrypt_round_trip(tmp_path):
    channel = make_channel(tmp_path)
    packet = channel.encrypt_record(RECORD)
    assert channel.decrypt_record(packet) == RECORD


def test_ciphertext_does_not_contain_plaintext(tmp_path):
    channel = make_channel(tmp_path)
    packet = channel.encrypt_record(RECORD)
    assert b"42.5" not in packet["ciphertext"].encode()
    assert "soil_moisture" not in packet["ciphertext"]


def test_each_packet_uses_a_different_nonce(tmp_path):
    channel = make_channel(tmp_path)
    first = channel.encrypt_record(RECORD)
    second = channel.encrypt_record(RECORD)
    assert first["nonce"] != second["nonce"]


def test_nonce_counter_persists_across_channel_instances(tmp_path):
    first_channel = make_channel(tmp_path)
    first = first_channel.encrypt_record(RECORD)
    second_channel = make_channel(tmp_path)
    second = second_channel.encrypt_record(RECORD)
    assert first["nonce"] != second["nonce"]


def test_tampered_ciphertext_is_rejected(tmp_path):
    channel = make_channel(tmp_path)
    packet = channel.encrypt_record(RECORD)
    packet["ciphertext"] = packet["ciphertext"][:-4] + "AAAA"
    with pytest.raises(ValueError, match="authentication/decryption failed"):
        channel.decrypt_record(packet)


def test_tampered_authenticated_metadata_is_rejected(tmp_path):
    channel = make_channel(tmp_path)
    packet = channel.encrypt_record(RECORD)
    packet["aad"]["sensor_id"] = "ATTACKER_SENSOR"
    with pytest.raises(ValueError, match="authentication/decryption failed"):
        channel.decrypt_record(packet)


def test_wrong_device_key_is_rejected(tmp_path):
    sender = make_channel(tmp_path, device="SENSOR_001")
    receiver = make_channel(tmp_path, device="SENSOR_002")
    packet = sender.encrypt_record(RECORD)
    with pytest.raises(ValueError):
        receiver.decrypt_record(packet)


def test_different_epoch_key_is_rejected(tmp_path):
    epoch_one = make_channel(tmp_path, epoch=1)
    epoch_two = make_channel(tmp_path, epoch=2)
    packet = epoch_one.encrypt_record(RECORD)
    with pytest.raises(ValueError):
        epoch_two.decrypt_record(packet)


def test_short_master_secret_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="at least 32 bytes"):
        SecureChannel(b"short", tmp_path / "nonce.sqlite", "SENSOR_001")
