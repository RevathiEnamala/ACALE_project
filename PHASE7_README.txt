ACALE PHASE 7 — PERFORMANCE EVALUATION
======================================

Purpose
-------
Phase 7 evaluates the outputs already produced by Phases 2-6. It summarizes:
- Sensor reading and context-state counts.
- Encrypted packet counts and envelope sizes.
- Local encryption/decryption API latency.
- Transmission event reduction from Phase 5 batching.
- Phase 5 illustrative energy estimates.
- Fog-node accepted, rejected, and replayed packet counts.
- CSV metrics and PNG charts.

No performance values are fabricated. Timings are measured on the computer
running the script. Phase 5 energy values are imported as illustrative
simulation estimates, not measured hardware energy.

INSTALLATION
------------
1. Extract ACALE_Phase7_Code.zip into your ACALE_Project root folder.
2. Merge the src and tests folders if Windows asks.
3. Keep your existing .env and Phase 4 nonce database unchanged.
4. Confirm the Phase 2-6 output files listed below exist.

RUN
---
Activate .venv and run from the ACALE_Project root:

    python run_phase7.py

Run unit tests:

    python -m pytest tests/test_performance_evaluator.py -v

EXPECTED INPUT FILES
--------------------
Phase 2:
    data/sensor_data/sensor_readings.csv

Phase 3 (default expected name):
    data/simulation_results/context_classification.json

Phase 4:
    data/simulation_results/encrypted_sensor_packets.json
    data/security/nonce_state.sqlite

Phase 5:
    data/simulation_results/transmission_batches.json

Phase 6:
    data/simulation_results/fog_verification_results.json

If your Phase 3 JSON has a different filename, run:

    python run_phase7.py --classification-json "YOUR_PHASE3_JSON_PATH"

Other input paths can also be changed with the command-line arguments shown by:

    python run_phase7.py --help

OUTPUTS
-------
results/performance/phase7_performance_report.json
results/performance/phase7_metrics.csv
results/performance/transmission_comparison.png
results/performance/crypto_latency.png
results/performance/fog_verification.png

CRYPTOGRAPHIC TIMING METHOD
---------------------------
- Decryption latency measures actual Phase 4 packets using the existing
  ACALE_MASTER_SECRET and the SecureChannel.decrypt_record API.
- Encryption latency measures SecureChannel.encrypt_record using an
  independent temporary benchmark key and temporary SQLite nonce database.
  This avoids reusing the Phase 4 key/nonce space.
- Encryption API timing includes persistent nonce allocation and envelope
  construction, not only the ChaCha20-Poly1305 primitive.
- The report keeps decrypted sensor records in memory and does not save them.

IMPORTANT INTERPRETATION
------------------------
1. Timing results vary with CPU, disk, background processes, and software
   environment. Report the machine/software context with measured values.
2. The energy estimate comes from Phase 5's simplified model. It is not
   physical battery or radio measurement.
3. Classification state counts are descriptive. Do not claim accuracy,
   precision, recall, or F1 without labelled ground-truth data.
4. This is a software simulation; no physical IoT radio or sensor battery
   measurements are performed.
5. Keep the existing Phase 4 nonce database. The evaluator only decrypts
   actual Phase 4 packets; its encryption microbenchmark uses a temporary
   independent key and nonce database.
