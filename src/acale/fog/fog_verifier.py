"""Fog-side authenticated packet verification and replay protection."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from src.acale.edge.secure_channel import SecureChannel
from src.acale.fog.replay_protection import ReplayProtectionStore


def flatten_packet_input(payload: Any) -> list[tuple[int, str, dict[str, Any]]]:
    """Accept Phase 5 batch output, a direct packet list, or packet wrapper."""
    flattened: list[tuple[int, str, dict[str, Any]]] = []
    if isinstance(payload, list):
        source_batches = [{"batch_type": "DIRECT", "packets": payload}]
    elif isinstance(payload, dict) and isinstance(payload.get("batches"), list):
        source_batches = payload["batches"]
    elif isinstance(payload, dict):
        packets = payload.get("packets", payload.get("encrypted_packets"))
        if isinstance(packets, list):
            source_batches = [{"batch_type": "DIRECT", "packets": packets}]
        else:
            raise ValueError("Input JSON must contain a packet list or a 'batches' list.")
    else:
        raise ValueError("Unsupported encrypted packet JSON structure.")

    index = 0
    for batch in source_batches:
        if not isinstance(batch, dict) or not isinstance(batch.get("packets"), list):
            raise ValueError("Each batch must be an object containing a 'packets' list.")
        batch_type = str(batch.get("batch_type", "UNKNOWN"))
        for packet in batch["packets"]:
            flattened.append((index, batch_type, packet))
            index += 1
    return flattened


class FogNodeVerifier:
    def __init__(
        self,
        master_secret: bytes,
        nonce_database: str | Path,
        replay_database: str | Path,
    ):
        if not isinstance(master_secret, bytes) or len(master_secret) < 32:
            raise ValueError("master_secret must contain at least 32 bytes.")
        self.master_secret = master_secret
        self.nonce_database = Path(nonce_database)
        self.replay_store = ReplayProtectionStore(replay_database)
        self._channels: dict[tuple[str, int], SecureChannel] = {}

    def _channel_for(self, device_id: str, key_epoch: int) -> SecureChannel:
        key = (device_id, key_epoch)
        if key not in self._channels:
            self._channels[key] = SecureChannel(
                master_secret=self.master_secret,
                nonce_database=self.nonce_database,
                device_id=device_id,
                key_epoch=key_epoch,
            )
        return self._channels[key]

    def verify_one(self, packet: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        """Authenticate first, then atomically register replay identifiers."""
        if not isinstance(packet, dict):
            return "REJECTED", "INVALID_PACKET_FORMAT", {}

        device_id = packet.get("device_id")
        key_epoch = packet.get("key_epoch")
        nonce = packet.get("nonce")
        aad = packet.get("aad")
        if (
            not isinstance(device_id, str) or not device_id
            or not isinstance(key_epoch, int) or key_epoch < 0
            or not isinstance(nonce, str) or not nonce
            or not isinstance(aad, dict)
        ):
            return "REJECTED", "MISSING_OR_INVALID_ENVELOPE_METADATA", {}

        try:
            # Strict base64 validation prevents ambiguous nonce encodings.
            base64.b64decode(nonce, validate=True)
            channel = self._channel_for(device_id, key_epoch)
            record = channel.decrypt_record(packet)
        except Exception:
            return "REJECTED", "AUTHENTICATION_OR_DECRYPTION_FAILED", {}

        reading_id = str(aad.get("reading_id", "") or "")
        accepted, reason = self.replay_store.register_packet(
            device_id=device_id,
            key_epoch=key_epoch,
            nonce=nonce,
            reading_id=reading_id,
        )
        if not accepted:
            return "REPLAY", reason, {}
        return "ACCEPTED", "AUTHENTICATED_AND_NOT_REPLAYED", record

    def verify_batches(self, batches: list[tuple[int, str, dict[str, Any]]]) -> dict[str, Any]:
        results = []
        accepted = rejected = replayed = 0
        for packet_index, batch_type, packet in batches:
            status, reason, record = self.verify_one(packet)
            if status == "ACCEPTED":
                accepted += 1
            elif status == "REPLAY":
                replayed += 1
            else:
                rejected += 1

            aad = packet.get("aad", {}) if isinstance(packet, dict) else {}
            results.append({
                "packet_index": packet_index,
                "batch_type": batch_type,
                "device_id": packet.get("device_id") if isinstance(packet, dict) else None,
                "key_epoch": packet.get("key_epoch") if isinstance(packet, dict) else None,
                "reading_id": aad.get("reading_id") if isinstance(aad, dict) else None,
                "status": status,
                "reason": reason,
                # Keep verified plaintext out of the audit summary file.
                "verified_sensor_id": record.get("sensor_id") if status == "ACCEPTED" else None,
            })

        return {
            "phase": 6,
            "component": "fog_node_verification_and_replay_protection",
            "total_packets": len(results),
            "accepted_packets": accepted,
            "rejected_packets": rejected,
            "replayed_packets": replayed,
            "results": results,
        }


def verify_file(
    input_path: str | Path,
    output_path: str | Path,
    master_secret: bytes,
    nonce_database: str | Path,
    replay_database: str | Path,
) -> dict[str, Any]:
    with Path(input_path).open("r", encoding="utf-8") as file:
        payload = json.load(file)
    flattened = flatten_packet_input(payload)
    verifier = FogNodeVerifier(master_secret, nonce_database, replay_database)
    result = verifier.verify_batches(flattened)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)
    return result
