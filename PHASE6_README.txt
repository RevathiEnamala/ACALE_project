ACALE PHASE 6 — FOG NODE VERIFICATION AND REPLAY PROTECTION
===========================================================

Purpose
-------
Phase 6 simulates a fog node receiving Phase 5 transmission batches. It:
1. Reads encrypted packets from Phase 5.
2. Reconstructs the device/epoch secure channel using the same ACALE master
   secret and the existing Phase 4 key-derivation settings.
3. Authenticates and decrypts each packet with ChaCha20-Poly1305.
4. Rejects invalid envelopes, modified AAD, altered ciphertext, wrong keys,
   or failed authentication.
5. After successful authentication only, records the packet nonce and reading
   ID in a persistent SQLite replay database.
6. Detects duplicate nonces and duplicate reading IDs for the same device and
   key epoch.
7. Writes a verification summary without writing decrypted sensor readings.

INSTALLATION
------------
1. Extract ACALE_Phase6_Code.zip into the ACALE_Project root folder.
2. Merge the src and tests folders if Windows asks.
3. Do not overwrite your existing Phase 4 secure_channel.py.
4. Keep the root .env file and ACALE_MASTER_SECRET unchanged.
5. Keep data/security/nonce_state.sqlite. Never delete, roll back, or restore
   an older nonce database while continuing to use the same key/epoch.

RUN
---
Activate the project virtual environment and run from ACALE_Project:

    python run_phase6.py

Optional custom input/output:

    python run_phase6.py --input data/simulation_results/transmission_batches.json --output data/simulation_results/fog_verification_results.json

Run tests:

    python -m pytest tests/test_fog_verifier.py -v

INPUT
-----
data/simulation_results/transmission_batches.json
This is the Phase 5 output. The loader also accepts a direct packet list or a
JSON object containing a packets/encrypted_packets list.

OUTPUT
------
data/simulation_results/fog_verification_results.json

PERSISTENT DATABASES
--------------------
Phase 4 nonce database (existing; do not delete/rollback):
    data/security/nonce_state.sqlite

Phase 6 replay database (created automatically):
    data/security/fog_replay_state.sqlite

REPLAY DETECTION DESIGN
-----------------------
Authentication happens before replay registration. A packet that fails AEAD
authentication is rejected and is NOT inserted into the replay database.
After successful authentication, the fog node atomically registers the
(device ID, key epoch, nonce) tuple. It also checks a non-empty reading ID.
SQLite transactions serialize concurrent registrations.

A repeated nonce is reported as REPLAYED_NONCE. A different valid packet
reusing an already accepted reading ID for the same device/epoch is reported
as REPLAYED_READING_ID. These checks are a prototype replay policy; production
systems may need a bounded replay window, sequence numbers, retention policy,
and coordinated state replication across multiple fog nodes.

IMPORTANT
---------
- Use the same root ACALE_MASTER_SECRET as Phase 4. Do not paste it into chat.
- Do not reset the replay database during an active deployment, or previously
  accepted packets could be accepted again.
- If Phase 4 keys are rotated, the packet's key_epoch must match the epoch
  and key provisioning at the fog node. This prototype derives keys from the
  same master secret locally.
- The software project simulates sensors and fog verification; no physical
  agricultural IoT hardware is required.
- Successful authentication is not proof that a sensor reading is truthful;
  it only confirms integrity and possession of the correct key.
