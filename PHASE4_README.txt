ACALE PHASE 4 — SECURE KEY MANAGEMENT AND AUTHENTICATED ENCRYPTION

WHAT THIS PHASE ADDS
- HKDF-SHA256 derives a 256-bit key from a master secret, device ID and key epoch.
- ChaCha20-Poly1305 encrypts each sensor/classification record and authenticates it.
- Device ID, epoch, sensor ID, reading ID, timestamp and context state are AAD.
- A persistent SQLite counter allocates 96-bit nonces:
  4-byte key-specific prefix + 8-byte monotonic counter.
- Counter allocation uses SQLite transactions to serialize concurrent writers.
- A key epoch change derives a different key for the same device.
- The demo verifies authenticated decryption for every encrypted record.

IMPORTANT SECURITY LIMITATIONS
1. This is a software prototype. Protect the master secret in a real deployment
   with a hardware-backed keystore, secure element, or managed secret store.
2. Keep the nonce database durable. NEVER delete, roll back, or restore an older
   copy of data/security/nonce_state.sqlite while continuing with the same
   device/epoch key. Counter rollback can cause catastrophic nonce reuse.
3. Back up the nonce database consistently and restrict write access.
4. Use a new key epoch when rotating keys. Keep old keys available only as long
   as needed to decrypt retained packets, then retire them securely.
5. The demo uses one shared master secret as a root for per-device derived keys.
   Production provisioning should use a unique protected root/credential per
   device or a managed key hierarchy.
6. This phase does not yet implement fog-side replay-window checking or network
   transport. Those belong in a later phase.
7. Do not claim the prototype is Ascon. The implemented AEAD is ChaCha20-Poly1305.

INSTALL / SETUP
1. Extract this ZIP into the existing ACALE_Project folder.
2. Allow the new files to merge. Do not replace main.py, run_phase3.py,
   config files, or Phase 2/3 modules.
3. cryptography and python-dotenv should already be installed. If imports fail:
   pip install cryptography python-dotenv

CREATE THE MASTER SECRET
In PowerShell run:
   python -c "import secrets; print(secrets.token_hex(32))"

Copy the 64-character hexadecimal output into a root-level .env file:
   ACALE_MASTER_SECRET=PASTE_YOUR_GENERATED_HEX_VALUE_HERE

Do not paste the generated secret into ChatGPT, source code, screenshots,
reports, or Git. Ensure .env is listed in .gitignore.

RUN
1. First make sure Phase 3 output exists:
   python run_phase3.py
2. Test Phase 4:
   python -m pytest tests/test_secure_channel.py -v
3. Run the encryption demonstration:
   python run_phase4.py

OUTPUT
- data/simulation_results/encrypted_sensor_packets.json
- data/security/nonce_state.sqlite

The JSON contains ciphertext and non-secret packet metadata. The SQLite database
stores nonce counters, not encryption keys. Treat both files as project data.
