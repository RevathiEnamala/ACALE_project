"""Encrypt Phase 3 classified readings and verify authenticated decryption."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from acale.edge.secure_channel import SecureChannel  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    secret_hex = os.getenv("ACALE_MASTER_SECRET", "").strip()
    if not secret_hex:
        raise RuntimeError(
            "ACALE_MASTER_SECRET is missing. Create a root .env file as "
            "described in PHASE4_README.txt. Never paste the secret into chat."
        )
    try:
        master_secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise RuntimeError("ACALE_MASTER_SECRET must be hexadecimal.") from exc
    if len(master_secret) < 32:
        raise RuntimeError("ACALE_MASTER_SECRET must decode to at least 32 bytes.")

    input_path = ROOT / "data" / "simulation_results" / "context_classification.json"
    output_dir = ROOT / "data" / "simulation_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "encrypted_sensor_packets.json"
    nonce_db = ROOT / "data" / "security" / "nonce_state.sqlite"

    if not input_path.exists():
        raise FileNotFoundError(
            "Phase 3 output was not found. Run `python run_phase3.py` first."
        )

    with input_path.open("r", encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list):
        raise ValueError("Phase 3 JSON must contain a list of readings.")

    encrypted_packets = []
    decrypted_count = 0
    for record in records:
        device_id = str(record.get("sensor_id", "UNKNOWN_SENSOR"))
        channel = SecureChannel(
            master_secret=master_secret,
            nonce_database=nonce_db,
            device_id=device_id,
            key_epoch=1,
        )
        packet = channel.encrypt_record(record)
        # Verify authentication/decryption locally; do not print plaintext.
        recovered = channel.decrypt_record(packet)
        if recovered != record:
            raise RuntimeError(f"Round-trip verification failed for {device_id}.")
        encrypted_packets.append(packet)
        decrypted_count += 1

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(encrypted_packets, file, indent=2, ensure_ascii=False)

    print("ACALE Phase 4: Secure Encryption Demonstration")
    print("----------------------------------------------")
    print(f"Input readings: {len(records)}")
    print(f"Encrypted packets: {len(encrypted_packets)}")
    print(f"Successful authenticated decryptions: {decrypted_count}")
    print(f"Encryption: ChaCha20-Poly1305")
    print(f"Key derivation: HKDF-SHA256")
    print(f"Key epoch: 1")
    print(f"Nonce state database: {nonce_db}")
    print(f"Encrypted output: {output_path}")
    print("Master key and plaintext records were not printed.")


if __name__ == "__main__":
    main()
