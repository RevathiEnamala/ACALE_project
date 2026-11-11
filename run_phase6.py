"""Run ACALE Phase 6: fog-node authentication and replay verification."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from src.acale.fog.fog_verifier import verify_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACALE Phase 6 fog verification.")
    parser.add_argument(
        "--input",
        default="data/simulation_results/transmission_batches.json",
        help="Phase 5 transmission-batches JSON file.",
    )
    parser.add_argument(
        "--output",
        default="data/simulation_results/fog_verification_results.json",
        help="Fog verification summary JSON file.",
    )
    parser.add_argument(
        "--nonce-db",
        default="data/security/nonce_state.sqlite",
        help="Existing Phase 4 nonce database (must not be deleted or rolled back).",
    )
    parser.add_argument(
        "--replay-db",
        default="data/security/fog_replay_state.sqlite",
        help="Persistent fog replay-protection database.",
    )
    args = parser.parse_args()

    secret_hex = os.getenv("ACALE_MASTER_SECRET", "").strip()
    if not secret_hex:
        raise RuntimeError(
            "ACALE_MASTER_SECRET is missing. Check the root .env file. "
            "Never paste the secret into chat."
        )
    try:
        master_secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise RuntimeError("ACALE_MASTER_SECRET must be hexadecimal.") from exc
    if len(master_secret) < 32:
        raise RuntimeError("ACALE_MASTER_SECRET must decode to at least 32 bytes.")

    result = verify_file(
        input_path=args.input,
        output_path=args.output,
        master_secret=master_secret,
        nonce_database=args.nonce_db,
        replay_database=args.replay_db,
    )
    print("\\nACALE Phase 6: Fog Node Verification")
    print("------------------------------------")
    print(f"Packets checked:   {result['total_packets']}")
    print(f"Accepted:          {result['accepted_packets']}")
    print(f"Rejected:          {result['rejected_packets']}")
    print(f"Replay detected:   {result['replayed_packets']}")
    print(f"Results: {Path(args.output).resolve()}")
    print("Plaintext sensor readings and master secret were not written to the result file.")


if __name__ == "__main__":
    main()
